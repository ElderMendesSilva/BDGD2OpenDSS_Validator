# -*- coding: utf-8 -*-
"""Quais guardas de achado o ciclo executa DE FATO, e quais nunca rodam.

POR QUE EXISTE. Os achados são leis, e cada lei mora num guarda de código.
Um guarda que nenhum teste alcança não é lei — é intenção. A V33 caiu em 35
das 99 bases num guarda do achado 61 que a `.gdb` mínima nunca tocava, e a
suíte inteira estava verde.

O QUE ELE MEDE, E O QUE NÃO. Ele roda o ciclo sob `sys.settrace`, junta as
linhas executadas e cruza com os comentários `# ACHADO N` do código. Para um
`if`, o que conta é o CORPO: a condição ser avaliada e dar falso não prova
nada — foi exatamente assim que o `NameError` da V33 passou.

Não é cobertura de linha do projeto, e não substitui um `coverage`. É a
pergunta estreita que interessa: **cada lei é exercitada por alguma fixture?**

    python analise/cobertura_achados.py                 # a .gdb minima so
    python analise/cobertura_achados.py --variantes     # e as de testes/fixture
    python analise/cobertura_achados.py --frios         # so o que nao roda

Em 10/09/2026, com a `.gdb` mínima sozinha: 41 achados com guarda marcado, 22
com pelo menos um guarda frio. Com as cinco variantes: 19.

`--jobs` fica em 1 de propósito: acima disso o conversor usa
`ProcessPoolExecutor`, e `settrace` não atravessa processo — a medição sairia
otimista sem avisar.
"""
import argparse
import ast
import glob
import io
import json
import os
import re
import runpy
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PAT = re.compile(r'ACHADO\s+(\d+)', re.I)


# ------------------------------------------------------------------ traço
def _tracar(alvo, argv, acumulado):
    """Roda um script do projeto no processo atual, sob `settrace`."""
    vistas = {}

    def _tr(frame, evento, arg):
        f = frame.f_code.co_filename
        if f.startswith(RAIZ):
            vistas.setdefault(os.path.normcase(f), set()).add(frame.f_lineno)
            return _tr
        return None

    argv_velho, cwd_velho = sys.argv, os.getcwd()
    sys.argv = [alvo] + list(argv)
    os.chdir(RAIZ)
    sys.settrace(_tr)
    try:
        runpy.run_path(alvo, run_name='__main__')
    except SystemExit:
        pass
    except Exception as e:                       # noqa: BLE001
        print(f'  ({os.path.basename(alvo)} parou: {type(e).__name__}: {e})')
    finally:
        sys.settrace(None)
        sys.argv, _ = argv_velho, os.chdir(cwd_velho)
    for f, ls in vistas.items():
        acumulado[f] = acumulado.get(f, set()) | ls


def _ciclo(gdb, saida, acumulado, completo=True):
    """converter -> ligacao -> reguladores -> ampacidade -> verifica ->
    energia -> validador, e as validações que leem a .gdb de volta."""
    e = lambda n: os.path.join(RAIZ, 'etapas', n)          # noqa: E731
    _tracar(e('converter.py'), [gdb, '--saida', saida], acumulado)
    if not glob.glob(os.path.join(saida, '*', 'MASTER-*.dss')):
        return                                   # nada foi gerado: achado 65
    for nome in ('ligacao.py', 'reguladores.py', 'ampacidade.py',
                 'verifica.py', 'energia.py'):
        _tracar(e(nome), [saida], acumulado)
    _tracar(e('validador.py'), [saida, '--ses'], acumulado)
    if completo:
        _tracar(e('valida_perdas.py'), [saida, gdb], acumulado)
        _tracar(e('valida_balanco.py'), [saida, gdb], acumulado)
        _tracar(os.path.join(RAIZ, 'relatorio.py'), [saida], acumulado)


# ------------------------------------------------------------------ leitura
def _corpo(no):
    """As linhas que só rodam se a condição do guarda for verdadeira."""
    if not isinstance(no, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
        return [no.lineno]
    ls = []
    for f in no.body:
        ls += [n.lineno for n in ast.walk(f) if hasattr(n, 'lineno')]
    return sorted(set(ls))


def guardas():
    """Todo comentário `# ACHADO N` do projeto, com o nó de código que ele
    guarda. Só comentário de linha: docstring é prosa, não guarda."""
    out = {}
    alvos = sorted(glob.glob(os.path.join(RAIZ, 'bdgd2dss', '*.py'))
                   + glob.glob(os.path.join(RAIZ, 'etapas', '*.py'))
                   + glob.glob(os.path.join(RAIZ, '*.py')))
    tipos = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Assign,
             ast.Expr, ast.Return, ast.AugAssign)
    for caminho in alvos:
        src = io.open(caminho, encoding='utf-8').read()
        try:
            arv = ast.parse(src)
        except SyntaxError:
            continue
        fonte = src.splitlines()
        nos = sorted((n for n in ast.walk(arv) if hasattr(n, 'lineno')),
                     key=lambda n: n.lineno)
        for i, l in enumerate(fonte, 1):
            m = PAT.search(l)
            if not m or not l.strip().startswith('#'):
                continue
            seg = next((n for n in nos if n.lineno > i
                        and isinstance(n, tipos)), None)
            if seg is None:
                continue
            out.setdefault(int(m.group(1)), []).append(
                (os.path.relpath(caminho, RAIZ), seg.lineno, _corpo(seg),
                 fonte[seg.lineno - 1].strip()[:64]))
    return out


def estado(cobertura):
    """Por achado, a situação de cada guarda: ok, corpo frio, ou não rodou."""
    out = {}
    for n, gs in guardas().items():
        linhas = []
        for rel, ln, corpo, txt in gs:
            vistas = cobertura.get(os.path.normcase(os.path.join(RAIZ, rel)))
            if vistas is None:
                e = 'arquivo nao rodou'
            elif any(x in vistas for x in corpo):
                e = 'ok'
            else:
                e = 'CORPO NAO RODA'
            linhas.append((rel, ln, e, txt))
        out[n] = linhas
    return out


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--variantes', action='store_true',
                    help='roda tambem as variantes de testes/fixture.py')
    ap.add_argument('--frios', action='store_true',
                    help='lista so os achados com algum guarda frio')
    ap.add_argument('--json', metavar='ARQ', help='grava o resultado')
    a = ap.parse_args()

    sys.path.insert(0, RAIZ)
    sys.path.insert(0, os.path.join(RAIZ, 'testes'))
    import fixture                                          # noqa: PLC0415

    cob, tmp = {}, tempfile.mkdtemp(prefix='cobertura_')
    try:
        casos = [(None, 'minima')]
        if a.variantes:
            casos += [(v, v) for v in sorted(fixture.VARIANTES)]
        for variante, nome in casos:
            print(f'== {nome}', flush=True)
            gdb = fixture.gerar(os.path.join(tmp, nome + '.gdb'),
                                variante=variante)
            # a pasta segue o padrao `MODELOS_<TAG>_<SUFIXO>` porque a
            # auditoria varre por sufixo, e ela e parte do ciclo
            _ciclo(gdb, os.path.join(tmp, f'MODELOS_{nome}_COB'), cob,
                   completo=(variante is None))
        print('== auditoria', flush=True)
        # `--saida` no temporario: sem ele a auditoria publica em
        # `resultados/`, que E versionado — a regua nao suja o repositorio.
        _tracar(os.path.join(RAIZ, 'etapas', 'auditoria.py'),
                ['--sufixo', 'COB', '--raiz', tmp,
                 '--saida', os.path.join(tmp, 'resultados')], cob)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    st = estado(cob)
    frios = {n: v for n, v in st.items()
             if any(e != 'ok' for _, _, e, _ in v)}
    print(f'\nachados com guarda marcado no codigo: {len(st)}')
    print(f'com pelo menos um guarda FRIO:        {len(frios)}\n')
    for n in sorted(frios if a.frios else st):
        alvo = frios.get(n) if a.frios else st[n]
        print(f'--- achado {n}')
        for rel, ln, e, txt in alvo:
            print(f'      {rel}:{ln}  [{e}]  {txt}')
    if a.json:
        json.dump({str(n): v for n, v in st.items()},
                  open(a.json, 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
        print(f'\ndetalhe em {a.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
