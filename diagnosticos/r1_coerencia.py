# -*- coding: utf-8 -*-
"""Os 458 usam condutor com R1 incoerente com a propria ampacidade?

O `linecodes._ajuste` ja calibra R1 = a x CNOM^b no miolo coerente da SEGCON e
substitui quem esta acima de FATOR_CORRIGE = 7,4x o previsto. A suspeita: o
limiar de 7,4 pega so o extremo, e sobra uma populacao de condutores 2 a 7x
acima que ninguem corrige — e que inflaria a perda justamente nos alimentadores
que os usam.
"""
import collections
import json
import os
import statistics
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
GDB = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402
from bdgd2dss import linecodes                      # noqa: E402

bal = json.load(open(os.path.join(P, 'MODELOS_V9', 'validacao_balanco.json'),
                     encoding='utf-8'))
maus = {x['ctmt'] for x in bal if x['viola_limite'] and x['pct_total_medido'] >= 2.0}
bons = {x['ctmt'] for x in bal} - maus

b = BDGD(GDB, verbose=False)
sc = b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
pares = [(num(sc['R1'][i]), num(sc['CNOM'][i])) for i in range(len(sc['COD_ID']))]
aj = linecodes._ajuste(pares)
a, bb, txt_aj = aj
print(f'ajuste calibrado na propria SEGCON:  {txt_aj}')
print(f'limiar de correcao atual: FATOR_CORRIGE = {linecodes.FATOR_CORRIGE}\n')

import math
razao_cnd, r1_cnd = {}, {}
for i in range(len(sc['COD_ID'])):
    cod = txt(sc['COD_ID'][i]).strip()
    r1, cn = num(sc['R1'][i]), num(sc['CNOM'][i])
    r1_cnd[cod] = r1
    if r1 > 0 and cn > 0:
        prev = math.exp(bb) * cn ** a
        razao_cnd[cod] = r1 / prev

r = sorted(razao_cnd.values())
print(f'{len(r):,} condutores com R1 e CNOM validos')
print(f'   razao R1 declarado / R1 previsto pela ampacidade:')
print(f'      mediana {statistics.median(r):5.2f}x   '
      f'p90 {r[9*len(r)//10]:6.2f}x   p99 {r[99*len(r)//100]:7.2f}x')
for lim in (2, 3, 5, 7.4, 10):
    n = sum(1 for x in r if x > lim)
    print(f'      acima de {lim:4.1f}x: {n:5,} ({100*n/len(r):5.1f}%)')

# --- por alimentador: razao ponderada pelo km de rede ---------------------
s = b.ler('SSDMT', ['CTMT', 'COMP', 'TIP_CND'])
km_cnd = collections.defaultdict(collections.Counter)
for i in range(len(s['CTMT'])):
    c = txt(s['CTMT'][i]).strip().upper()
    km_cnd[c][txt(s['TIP_CND'][i]).strip()] += num(s['COMP'][i]) / 1000.0


def razao_alim(c):
    tot = sum(km_cnd[c].values())
    if not tot:
        return None
    v = sum(razao_cnd.get(k, 1.0) * L for k, L in km_cnd[c].items()) / tot
    return v


def km_acima(c, lim):
    """Fracao do km do alimentador em condutor acima de `lim`x o previsto."""
    tot = sum(km_cnd[c].values())
    if not tot:
        return None
    return sum(L for k, L in km_cnd[c].items()
               if razao_cnd.get(k, 1.0) > lim) / tot


print(f'\n{"grupo":14s} {"razao pond.":>12s} {"km acima 2x":>13s} '
      f'{"km acima 3x":>13s} {"km acima 7,4x":>14s}')
for rot, cods in (('VIOLAM (458)', maus), ('nao violam', bons)):
    rz = [razao_alim(c) for c in cods if razao_alim(c) is not None]
    f2 = [km_acima(c, 2) for c in cods if km_acima(c, 2) is not None]
    f3 = [km_acima(c, 3) for c in cods if km_acima(c, 3) is not None]
    f7 = [km_acima(c, 7.4) for c in cods if km_acima(c, 7.4) is not None]
    print(f'{rot:14s} {statistics.median(rz):11.2f}x '
          f'{100*statistics.median(f2):12.1f}% '
          f'{100*statistics.median(f3):12.1f}% '
          f'{100*statistics.median(f7):13.1f}%')

# --- os piores alimentadores ---------------------------------------------
piores = sorted([x for x in bal if x['ctmt'] in maus],
                key=lambda z: z['pct_tecnica_modelo'], reverse=True)[:8]
print(f'\n{"alimentador":16s} {"modelo":>8s} {"medida":>8s} {"razao R1":>10s} '
      f'{"km >2x":>8s} {"km >7,4x":>9s}')
for x in piores:
    c = x['ctmt']
    rz, f2, f7 = razao_alim(c), km_acima(c, 2), km_acima(c, 7.4)
    print(f'{c[:16]:16s} {x["pct_tecnica_modelo"]:7.2f}% '
          f'{x["pct_total_medido"]:7.2f}% '
          f'{(rz or 0):9.2f}x {100*(f2 or 0):7.1f}% {100*(f7 or 0):8.1f}%')
