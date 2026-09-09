# -*- coding: utf-8 -*-
"""Chamada a nome que nao existe em escopo nenhum — o erro da V33.

A V33 caiu em 35 das 99 bases com `NameError: name 'log' is not defined`. A
linha estava dentro de `_uma_se`, onde `log` nao existe — ele e do escopo do
`main` —, e so era ALCANCADA quando a base tinha uma unidade de GD
implausivel. As 64 bases sem nenhuma passaram, e o teste de fumaca na `.gdb`
minima tambem passou, por nao ter nenhuma.

E o pior formato de erro deste projeto: nao aparece no caminho comum, aparece
so no caminho que importa. Python nao acusa nome indefinido ate EXECUTAR a
linha, entao o que resta e ler a arvore sintatica e perguntar, para cada
chamada, se aquele nome existe em algum escopo que a alcance.

Nao substitui um linter de verdade — cobre UMA classe de erro, que e a que ja
custou uma rodada nacional.
"""
import ast
import builtins


def _globais(arv):
    """Nomes visiveis no topo do modulo, inclusive os criados dentro de `if`,
    `try` e afins — import opcional em `try/except ImportError` e comum aqui."""
    g = set()

    def registra(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            g.add(n.name)
        elif isinstance(n, ast.Assign):
            for alvo in n.targets:
                g.update(x.id for x in ast.walk(alvo) if isinstance(x, ast.Name))
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                g.add((a.asname or a.name).split('.')[0])

    for no in arv.body:
        registra(no)
        if isinstance(no, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
            for sub in ast.walk(no):
                registra(sub)
    return g


def _locais(fn):
    """Tudo que a funcao cria: argumentos, atribuicoes, imports, `except as`,
    funcoes e classes aninhadas."""
    d = {a.arg for a in
         fn.args.args + fn.args.kwonlyargs + getattr(fn.args, 'posonlyargs', [])}
    if fn.args.vararg:
        d.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        d.add(fn.args.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            d.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                d.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            d.add(n.name)
        elif isinstance(n, ast.arg):
            d.add(n.arg)
    return d


def _funcoes(no):
    """As funcoes deste nivel, atravessando `if`/`try`/`for`/`class` mas SEM
    entrar nas funcoes — quem entra e a recursao, levando o escopo junto."""
    achadas = []
    for filho in ast.iter_child_nodes(no):
        if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
            achadas.append(filho)
        elif not isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
            achadas.extend(_funcoes(filho))
    return achadas


def indefinidos(arquivos):
    """`[(arquivo, linha, funcao, nome)]` de cada chamada a nome sem escopo.

    O ESCOPO DE FECHAMENTO CONTA, e ignorar isso e o que torna um verificador
    destes inutil: `bdgd2dss/pool.py` chama `log(m)` dentro de `_diz`, e `log`
    e argumento de `encerrar`, a funcao de fora. Sem descer levando o escopo,
    a checagem acusa codigo correto e ninguem mais olha para ela.
    """
    embutidos = set(dir(builtins))
    ruins = []
    for arq in arquivos:
        with open(arq, encoding='utf-8') as fh:
            arv = ast.parse(fh.read(), arq)
        visiveis_no_topo = _globais(arv) | embutidos

        def desce(no, de_fora):
            for fn in _funcoes(no):
                visiveis = de_fora | _locais(fn)
                for c in ast.walk(fn):
                    if (isinstance(c, ast.Call)
                            and isinstance(c.func, ast.Name)
                            and c.func.id not in visiveis
                            and c.func.id not in visiveis_no_topo):
                        ruins.append((arq, c.lineno, fn.name, c.func.id))
                desce(fn, visiveis)

        desce(arv, set())
    return ruins
