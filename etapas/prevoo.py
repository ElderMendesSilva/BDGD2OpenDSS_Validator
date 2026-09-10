# -*- coding: utf-8 -*-
"""O ciclo inteiro sobre as fixtures, conferido contra referência gravada.

    python etapas/prevoo.py                  # confere e sai 0 ou 1
    python etapas/prevoo.py --gravar         # (re)grava a referência
    python etapas/prevoo.py --selo logs/prevoo   # grava <commit>.ok se passar

POR QUE EXISTE. Uma rodada nacional custa 99 jobs e horas de cluster. A V33
gastou tudo isso para descobrir um `NameError` de uma linha, e a V29 e a
primeira V30 rodaram inteiras sem chamar o `reguladores.py` — o `regerar_v10`
listava a etapa e nunca a invocava. Nenhum dos dois aparecia na suíte: um
exigia GD implausível, o outro exigia rodar o orquestrador de verdade.

O QUE ELE FAZ, E POR QUE NESTA ORDEM:

1. **a suíte** — se um teste de unidade caiu, não há o que discutir adiante;
2. **o ciclo completo** em cada fixture de `testes/fixture.py`, incluindo as
   variantes que ligam um achado cada;
3. **a comparação** contra `dados/referencia_prevoo.json`: mesma rede, mesmos
   números. Diferença não é reprovação automática — é uma pergunta que alguém
   tem de responder antes de gastar o cluster.

O QUE ELE NÃO É. Não afere engenharia: a rede mínima perde 97% de propósito.
Ele responde "o código faz hoje o que fazia quando a referência foi gravada?",
que é a pergunta que as três regressões silenciosas de setembro burlaram.

SOBRE MUDAR A REFERÊNCIA. `--gravar` é para quando a mudança de número é
**pretendida e explicada** — o commit que a regrava tem de dizer por quê. Uma
referência que se regrava sozinha ao primeiro desacordo não guarda nada.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REFERENCIA = os.path.join(RAIZ, 'dados', 'referencia_prevoo.json')

# As etapas do ciclo, na ordem em que o `regerar_v10` as roda. A ordem importa:
# a `ligacao` energiza rede que estava no escuro e a `ampacidade` decide pela
# corrente que passa — invertê-las mede corrente numa rede menor.
ETAPAS = ('ligacao', 'reguladores', 'ampacidade', 'verifica', 'energia')

# Campos comparados do `validacao.json`. São os que mudam quando o modelo muda,
# e não mudam sozinhos: contagem de elementos, convergência, causa e as
# grandezas que os achados de 2026 moveram.
CAMPOS = ('causa', 'converge', 'compila', 'n_barras', 'n_cargas', 'n_linhas',
          'n_trafos', 'reguladores', 'reguladores_saturados',
          'linhas_acima_ampacidade')
# Grandezas de ponto flutuante, com a casa em que se comparam.
FLUTUANTES = {'perdas_pct': 2, 'V_MT_max': 3, 'V_MT_min': 3,
              'V_MT_mediana': 3, 'P_gd_kW': 1}


def _roda(script, *args, esperado=0):
    """Uma etapa, como PROCESSO — código de retorno conta."""
    caminho = (os.path.join(RAIZ, 'etapas', script)
               if os.path.exists(os.path.join(RAIZ, 'etapas', script))
               else os.path.join(RAIZ, script))
    p = subprocess.run([sys.executable, '-u', caminho] + list(args),
                       cwd=RAIZ, capture_output=True, text=True, timeout=1800)
    return p


def _achados_no_log(texto):
    """Quais achados o ciclo ANUNCIOU. Um guarda que parou de disparar é
    regressão mesmo quando os números continuam iguais — foi o caso do
    `reguladores.py`, que sumiu do ciclo sem mudar nada visível."""
    marcas = set()
    for l in texto.splitlines():
        if 'ACHADO' in l.upper():
            for pedaco in l.upper().split('ACHADO')[1:]:
                num = pedaco.strip().split(':')[0].split()[0].strip(':.,')
                if num.isdigit():
                    marcas.add(int(num))
    return sorted(marcas)


def _medida(saida):
    """O que sobrou no disco, reduzido ao que se compara."""
    caminho = os.path.join(saida, 'validacao.json')
    if not os.path.exists(caminho):
        return None
    ses = json.load(open(caminho, encoding='utf-8'))
    out = {}
    for s in ses:
        r = {c: s.get(c) for c in CAMPOS}
        for c, casas in FLUTUANTES.items():
            v = s.get(c)
            r[c] = None if v is None else round(float(v), casas)
        out[str(s.get('modelo'))] = r
    return out


def um_caso(variante, tmp, verboso=True):
    """Gera a fixture, roda o ciclo e devolve o que se compara."""
    sys.path.insert(0, os.path.join(RAIZ, 'testes'))
    import fixture                                          # noqa: PLC0415

    nome = variante or 'minima'
    gdb = fixture.gerar(os.path.join(tmp, nome + '.gdb'), variante=variante)
    saida = os.path.join(tmp, 'MODELOS_' + nome)
    log = []

    p = _roda('converter.py', gdb, '--saida', saida)
    log.append(p.stdout + p.stderr)
    caso = {'converter_rc': p.returncode}

    # Base que não gerou subestação nenhuma para aqui de propósito: é o
    # achado 65, e o ciclo adiante não teria o que medir.
    if p.returncode == 0 and glob.glob(os.path.join(saida, '*', 'MASTER-*.dss')):
        for etapa in ETAPAS:
            q = _roda(etapa + '.py', saida)
            log.append(q.stdout + q.stderr)
            caso[etapa + '_rc'] = q.returncode
        q = _roda('validador.py', saida, '--ses')
        log.append(q.stdout + q.stderr)
        caso['validador_rc'] = q.returncode
        caso['ses'] = _medida(saida)

    caso['achados'] = _achados_no_log('\n'.join(log))
    if verboso:
        print(f'   achados anunciados: {caso["achados"] or "nenhum"}', flush=True)
    return caso


def compara(atual, gravado):
    """As diferenças, em linguagem de quem vai decidir se submete."""
    fora = []
    for nome in sorted(set(atual) | set(gravado)):
        a, g = atual.get(nome), gravado.get(nome)
        if a is None or g is None:
            fora.append(f'{nome}: {"sumiu" if a is None else "e nova"}')
            continue
        for k in sorted(set(a) | set(g)):
            if k == 'ses':
                continue
            if a.get(k) != g.get(k):
                fora.append(f'{nome}.{k}: {g.get(k)!r} -> {a.get(k)!r}')
        for se in sorted(set(a.get('ses') or {}) | set(g.get('ses') or {})):
            va = (a.get('ses') or {}).get(se, {})
            vg = (g.get('ses') or {}).get(se, {})
            for k in sorted(set(va) | set(vg)):
                if va.get(k) != vg.get(k):
                    fora.append(f'{nome}/{se}.{k}: {vg.get(k)!r} -> {va.get(k)!r}')
    return fora


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--gravar', action='store_true',
                    help='(re)grava a referencia com o que sair agora')
    ap.add_argument('--sem-testes', action='store_true',
                    help='pula a suite (para depurar so o ciclo)')
    ap.add_argument('--selo', metavar='PASTA',
                    help='grava PASTA/<commit>.ok quando tudo passa — e o que '
                         'o submeter_todas.sh confere antes de gastar o cluster')
    a = ap.parse_args()

    if not a.sem_testes:
        print('== a suite', flush=True)
        p = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                            '-s', 'testes', '-q'], cwd=RAIZ,
                           capture_output=True, text=True, timeout=3600)
        if p.returncode != 0:
            print(p.stdout[-4000:] + p.stderr[-4000:])
            print('\n*** a suite reprovou. Nao ha o que discutir adiante. ***')
            return 1
        print('   ' + (p.stderr.strip().splitlines() or ['ok'])[-3], flush=True)

    sys.path.insert(0, os.path.join(RAIZ, 'testes'))
    import fixture                                          # noqa: PLC0415

    atual, tmp = {}, tempfile.mkdtemp(prefix='prevoo_')
    try:
        for variante in [None] + sorted(fixture.VARIANTES):
            nome = variante or 'minima'
            print(f'== {nome}', flush=True)
            atual[nome] = um_caso(variante, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if a.gravar:
        os.makedirs(os.path.dirname(REFERENCIA), exist_ok=True)
        json.dump(atual, open(REFERENCIA, 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False, sort_keys=True)
        print(f'\nreferencia gravada em {os.path.relpath(REFERENCIA, RAIZ)}')
        print('DIGA NO COMMIT POR QUE OS NUMEROS MUDARAM.')
        return 0

    if not os.path.exists(REFERENCIA):
        print(f'\n*** sem referencia em {os.path.relpath(REFERENCIA, RAIZ)}. '
              f'Grave uma com --gravar. ***')
        return 1

    fora = compara(atual, json.load(open(REFERENCIA, encoding='utf-8')))
    print()
    if fora:
        print(f'*** {len(fora)} diferenca(s) contra a referencia: ***')
        for f in fora:
            print(f'   {f}')
        print('\nSe a mudanca e pretendida, regrave com --gravar e explique no '
              'commit. Se nao e, achou-se um defeito antes de gastar 99 jobs.')
        return 1

    print('PRE-VOO APROVADO — o ciclo faz o que fazia quando a referencia foi '
          'gravada.')
    if a.selo:
        os.makedirs(a.selo, exist_ok=True)
        # O COMMIT VEM DO `carimbo`, E NAO DE `git` DIRETO. O no de calculo
        # NAO TEM GIT — a primeira execucao real gravou `sem_commit.ok`, e a
        # porta, que le o commit no no de acesso onde o git responde, jamais
        # acharia esse arquivo. O `carimbo` ja cai para `BDGD2DSS_COMMIT`,
        # que a submissao passa por `-v`.
        from bdgd2dss import carimbo                        # noqa: PLC0415
        commit = carimbo.commit(curto=False)
        if not commit:
            print('*** sem commit: nem `git` responde aqui, nem '
                  '`BDGD2DSS_COMMIT` veio da submissao. Sem isso o selo nao '
                  'identifica codigo nenhum, e nao vale como porta. ***')
            return 1
        alvo = os.path.join(a.selo, commit + '.ok')
        with open(alvo, 'w', encoding='utf-8') as fh:
            fh.write(commit + '\n')
        print(f'selo: {alvo}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
