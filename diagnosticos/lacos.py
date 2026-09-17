# -*- coding: utf-8 -*-
"""Quantos lacos fechados a media tensao tem, e quantos passam por regulador.

    python diagnosticos/lacos.py --raiz . --sufixo V36 --jobs 16 \\
        --saida-json medicoes/lacos_v36.json

POR QUE A PERGUNTA. Na EQUATORIAL6072 (V34), 42% da energia estava em
subestacoes que colapsavam — 77% de perda, tensao mediana de 0,38 pu, 36
reguladores saturados. Quatro hipoteses cairam (PT de regulador, raiz de 3 nos
monofasicos, transformador depois de abaixador, achado 49). O que ficou de pe,
medido em 17/09/2026 nas duas piores:

    SE        lacos   perda como esta   perda com os lacos abertos
    5001306      38         77,2%                  11,5%
    5001242      55         66,8%                  14,6%

Os lacos vem da propria BDGD (`SSDMT` e `UNSEMT` fechadas), e nenhum no
perde tensao quando eles sao abertos — sao lacos de verdade. Na 5001306, 6
deles tem um regulador dentro, todos com 8 elementos e com os maiores fluxos
(394 a 2.027 A): o arranjo de campo de chave de entrada, regulador, chave de
saida e CHAVE DE BYPASS. A trava do achado 48 so reconhece o bypass que liga
exatamente os dois PACs do regulador, e este liga os das chaves vizinhas.

Duas SEs de uma base nao fazem lei. Este censo conta, em cada subestacao de
uma rodada:

- os lacos fechados por FASE (um trecho na fase A e outro na B entre as
  mesmas barras nao sao laco);
- quantos tem um regulador num ciclo curto — a forma do bypass;
- quantos atravessam uma mudanca de tensao (achado 70): relacao liquida em
  volta do laco diferente de 1, como o do abaixador da 5001306;
- quantos sao fechados por elo que NOS criamos (`VAO_EXTRA_*`, achado 33) e
  nao pela BDGD.

COMO. Compila cada subestacao e le a topologia do OpenDSS, sem resolver
(`bdgd2dss/lacos.py`). As chaves abertas (`_CHAVES_ABERTAS.dss` e `SwtControl State=Open`) ficam fora do
grafo — sem isso, uma chave normalmente aberta fecha um "laco" que nao
conduz, que foi o erro da primeira medida. Transformadores entram primeiro na
arvore, entao o regulador nunca e escolhido como o elemento que fecha.

Roda sobre modelos ja gerados; e calculo, entao e job.
"""
import argparse
import collections
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

# O grafo mora em `bdgd2dss/lacos.py` desde que a etapa `reguladores.py`
# passou a usa-lo para achar o bypass de regulador (achado 69).
from bdgd2dss.lacos import lacos_da_se                     # noqa: E402,F401


def _uma(master):
    try:
        return master, lacos_da_se(master), None
    except Exception as e:                               # noqa: BLE001
        return master, None, f'{type(e).__name__}: {str(e)[:120]}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--raiz', default='.')
    ap.add_argument('--sufixo', required=True)
    ap.add_argument('--so', default='', help='tags separadas por espaco')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--saida-json', default=None)
    a = ap.parse_args(argv)

    so = {x for x in a.so.split() if x}
    masters = []
    for pasta in sorted(glob.glob(os.path.join(a.raiz, f'MODELOS_*_{a.sufixo}'))):
        tag = os.path.basename(pasta)[len('MODELOS_'):-len(a.sufixo) - 1]
        if so and tag not in so:
            continue
        for m in sorted(glob.glob(os.path.join(pasta, '*', 'MASTER-*.dss'))):
            if os.path.basename(os.path.dirname(m)).startswith('_'):
                continue
            masters.append((tag, m))
    if not masters:
        print('nenhuma subestacao encontrada', file=sys.stderr)
        return 1
    print(f'{len(masters)} subestacoes', flush=True)

    por_base = collections.defaultdict(dict)
    erros = 0
    if a.jobs > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = ex.map(_uma, [m for _, m in masters], chunksize=4)
            itens = list(zip([t for t, _ in masters], res))
    else:
        itens = [(t, _uma(m)) for t, m in masters]
    for tag, (m, r, err) in itens:
        se = os.path.basename(os.path.dirname(m))
        if err:
            erros += 1
            print(f'  ERRO {tag}/{se}: {err}', flush=True)
            continue
        por_base[tag][se] = r

    print(f'\n{"base":20s} {"SEs":>5s} {"com laco":>9s} {"lacos":>7s} {"c/ reg":>7s} {"c/ trf":>7s} {"nossos":>7s}')
    tot = collections.Counter()
    for tag in sorted(por_base):
        ses = por_base[tag]
        n_l = sum(1 for r in ses.values() if r['lacos'])
        c = collections.Counter()
        for r in ses.values():
            c['lacos'] += r['lacos']
            c['reg'] += r['com_regulador']
            c['trf'] += r.get('atraves_de_transformador', 0)
            c['nossos'] += r['por_elo_nosso']
        tot['ses'] += len(ses)
        tot['com_laco'] += n_l
        tot['com_reg'] += sum(1 for r in ses.values() if r['com_regulador'])
        tot['com_trf'] += sum(1 for r in ses.values()
                              if r.get('atraves_de_transformador'))
        tot.update(c)
        print(f'{tag[:20]:20s} {len(ses):5d} {n_l:9d} {c["lacos"]:7d} {c["reg"]:7d} {c["trf"]:7d} {c["nossos"]:7d}')
    print(f'\nPAIS: {tot["ses"]} SEs | {tot["com_laco"]} com laco | '
          f'{tot["com_reg"]} com laco passando por regulador | '
          f'{tot["com_trf"]} com laco atraves de transformador | '
          f'{tot["lacos"]} lacos, {tot["reg"]} com regulador, '
          f'{tot["trf"]} atraves de transformador, '
          f'{tot["nossos"]} fechados por elo nosso | {erros} erros')
    if a.saida_json:
        os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
        with open(a.saida_json, 'w', encoding='utf-8') as fh:
            json.dump({'sufixo': a.sufixo, 'bases': por_base,
                       'total': dict(tot), 'erros': erros}, fh,
                      ensure_ascii=False, indent=1)
        print(f'-> {a.saida_json}')
    return 0 if por_base else 1


if __name__ == '__main__':
    sys.exit(main())
