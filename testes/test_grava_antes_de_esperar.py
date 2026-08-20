# -*- coding: utf-8 -*-
"""Resultado pronto tem de estar em disco ANTES de qualquer espera.

Escrito depois de custar seis horas. Na V16 o `verifica` da Cemig-D processou
as 413 subestacoes — os indices [1/413] a [413/413] estao todos no log — e foi
morto pelo limite de tempo sem escrever `verificacao.json`. Seis horas de
trabalho correto descartadas.

O motivo esta na forma do codigo, e nao no OpenDSS:

    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for f_ in cf.as_completed(fut):
            por_se[se] = registra(...)
    saida = [...]                      # <- fora do `with`
    json.dump(saida, ...)              # <- so chega aqui depois do shutdown

Sair do `with` e `shutdown(wait=True)`: esperar cada processo trabalhador
morrer. O `verifica` roda tambem o motor COM, e servidor COM que nao solta
segura o processo vivo — a espera nunca volta, e o `json.dump` nunca roda.

Nao e defeito de uma etapa. Medido, as quatro etapas paralelas tinham a mesma
forma; so o `energia` escapou, porque chama `grava()` dentro do laco, e e o
unico que sempre sobreviveu a uma queda.

O teste le a arvore: no corpo do `with` que abre o pool tem de haver escrita em
disco. Nao verifica O QUE se escreve — verifica que se escreve antes de esperar.
"""
import ast
import os
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

ETAPAS = ['verifica.py', 'ampacidade.py', 'validador.py', 'ligacao.py',
          'energia.py']

ESCRITA = ('dump', 'write', 'writelines')


def _arvore(caminho):
    with open(caminho, encoding='utf-8') as fh:
        return ast.parse(fh.read().lstrip('﻿'))


def _escreve(no, funcoes):
    """True se `no` escreve em disco, direto ou por funcao deste modulo."""
    for x in ast.walk(no):
        if not isinstance(x, ast.Call):
            continue
        if isinstance(x.func, ast.Attribute) and x.func.attr in ESCRITA:
            return True
        # chamada a uma funcao do proprio modulo que escreve — o `grava()`
        # do `energia` e exatamente este caso
        if isinstance(x.func, ast.Name) and x.func.id in funcoes:
            if any(isinstance(y, ast.Call)
                   and isinstance(y.func, ast.Attribute)
                   and y.func.attr in ESCRITA
                   for y in ast.walk(funcoes[x.func.id])):
                return True
    return False


def _pools(arvore):
    for n in ast.walk(arvore):
        if isinstance(n, ast.With) and any(
                isinstance(i.context_expr, ast.Call)
                and 'ProcessPoolExecutor' in ast.dump(i.context_expr)
                for i in n.items):
            yield n


class GravaAntesDeEsperar(unittest.TestCase):

    def test_toda_etapa_paralela_grava_dentro_do_with(self):
        sem_gravar = []
        for script in ETAPAS:
            caminho = os.path.join(RAIZ, script)
            arvore = _arvore(caminho)
            funcoes = {f.name: f for f in ast.walk(arvore)
                       if isinstance(f, ast.FunctionDef)}
            achou_pool = False
            for w in _pools(arvore):
                achou_pool = True
                if not any(_escreve(b, funcoes) for b in w.body):
                    sem_gravar.append(f'{script}:{w.lineno}')
            self.assertTrue(achou_pool,
                            f'{script}: nenhum ProcessPoolExecutor — o teste '
                            f'perdeu o alvo, corrija a lista ETAPAS')
        self.assertEqual(
            sem_gravar, [],
            'etapa que so escreve DEPOIS de fechar o pool: se a espera do '
            '`shutdown` travar, todo o trabalho ja feito e descartado')


if __name__ == '__main__':
    unittest.main()
