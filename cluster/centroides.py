# -*- coding: utf-8 -*-
"""Onde fica, geograficamente, cada uma das bases. Roda no NO.

    python cluster/centroides.py --saida medicoes/centroides.json

POR QUE ISTO E UM PASSO SEPARADO. Para baixar o clima da regiao de uma base
precisa-se de duas coisas que NAO moram no mesmo lugar: a coordenada, que sai
da `.gdb` (no cluster, e por isso job — o head node nao processa), e a internet
para consultar a NASA POWER, que o no de calculo nao tem.

Entao o fluxo se parte em dois, e este e o primeiro:

    1. aqui:    .gdb  ->  medicoes/centroides.json      (no, por PBS)
    2. na casa: centroides.json  ->  dados/clima/*.json  (maquina com internet)

O JSON e de kilobytes e vai para o git junto com o resto, entao a maquina que
baixa nao precisa de acesso nenhum ao cluster.

Uma base sem geometria utilizavel entra com `erro` e nao derruba as outras: 97
leituras de `.gdb` e uma falhar e o caso normal, nao a excecao.
"""
import argparse
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import regerar_v10 as r                                # noqa: E402
from bdgd2dss import clima, escrita                    # noqa: E402
from bdgd2dss.leitor import BDGD, txt                  # noqa: E402


def de_uma(caminho):
    """`{dist, lon, lat}` de uma `.gdb`, ou `{erro}`."""
    b = BDGD(caminho, verbose=False)
    try:
        dist = txt(b.ler('BASE', ['DIST'])['DIST'][0]).strip()
    except Exception as e:                             # noqa: BLE001
        return {'erro': 'BASE.DIST ilegivel: %s' % str(e)[:60]}
    p = clima.centroide(b)
    if not p:
        return {'dist': dist, 'erro': 'sem geometria utilizavel'}
    lon, lat = p
    return {'dist': dist, 'lon': round(lon, 4), 'lat': round(lat, 4)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--saida', default=os.path.join('medicoes',
                                                    'centroides.json'))
    ap.add_argument('--so', default='', help='tags separadas por espaco')
    a = ap.parse_args(argv)

    so = {x for x in a.so.split() if x}
    bases = [(t, c) for t, c, _ in r.BASES if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada em BDGD2DSS_BASES', file=sys.stderr)
        return 1

    saida, erros = {}, 0
    for tag, cam in bases:
        t0 = time.time()
        try:
            d = de_uma(cam)
        except Exception as e:                         # noqa: BLE001
            d = {'erro': str(e)[:100]}
        d['gdb'] = os.path.basename(cam)
        saida[tag] = d
        erros += 'erro' in d
        print('  %-24s %-10s %s  %4.0fs'
              % (tag, d.get('dist', '?'),
                 d.get('erro') or 'lat %.4f  lon %.4f' % (d['lat'], d['lon']),
                 time.time() - t0), flush=True)

    os.makedirs(os.path.dirname(a.saida) or '.', exist_ok=True)
    with open(a.saida, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'medido_em': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'bases': saida}, fh, ensure_ascii=False, indent=1,
                  sort_keys=True)
    print('\n%d bases, %d sem coordenada  ->  %s'
          % (len(saida), erros, a.saida))
    return 0


if __name__ == '__main__':
    sys.exit(main())
