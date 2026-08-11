# -*- coding: utf-8 -*-
"""A ampacidade que cada base declara, PONDERADA pelo km de rede que a usa.

Se a Enel SP construir a rede com condutor de 30 a 100 A onde a Enel CE usa
200 a 400 A, a sobrecarga do modelo nao e defeito nosso — e o que a SEGCON
daquela base declara.
"""
import collections
import statistics
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402

BASES = [
    ('Enel SP', r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'),
    ('Enel CE', r'D:\Elder\Elder\BDGDs\Enel_CE_39_2024-12-31_V11_20250822-1151.gdb'),
    ('Light  ', r'D:\Elder\Elder\BDGDs\Light_382_2024-12-31_V11_20250925-1811.gdb'),
]

FAIXAS = [(0, 50), (50, 100), (100, 200), (200, 400), (400, 1e9)]

for rot, gdb in BASES:
    b = BDGD(gdb, verbose=False)
    sc = b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
    cn = {txt(sc['COD_ID'][i]).strip(): num(sc['CNOM'][i])
          for i in range(len(sc['COD_ID']))}
    r1 = {txt(sc['COD_ID'][i]).strip(): num(sc['R1'][i])
          for i in range(len(sc['COD_ID']))}
    s = b.ler('SSDMT', ['COMP', 'TIP_CND'])
    km = collections.Counter()
    for i in range(len(s['COMP'])):
        km[txt(s['TIP_CND'][i]).strip()] += num(s['COMP'][i]) / 1000.0
    tot = sum(km.values())
    if not tot:
        continue

    med = sum(cn.get(k, 0) * v for k, v in km.items()) / tot
    medr = sum(r1.get(k, 0) * v for k, v in km.items()) / tot
    print(f'--- {rot}   {tot:,.0f} km de MT, {len(cn):,} condutores')
    print(f'    CNOM ponderado por km: {med:7.1f} A     '
          f'R1 ponderado: {medr:6.3f} ohm/km')
    print('    distribuicao do km por faixa de ampacidade:')
    for lo, hi in FAIXAS:
        v = sum(x for k, x in km.items() if lo <= cn.get(k, 0) < hi)
        rot2 = f'{lo}-{hi:g} A' if hi < 1e9 else f'>{lo} A'
        print(f'       {rot2:>12s} {v:10,.0f} km  ({100*v/tot:5.1f}%)')
    # os condutores que mais aparecem
    print('    os 5 condutores com mais km:')
    for k, v in km.most_common(5):
        print(f'       cnd {k:>6s}  {v:9,.0f} km ({100*v/tot:4.1f}%)  '
              f'CNOM {cn.get(k, 0):7.1f} A   R1 {r1.get(k, 0):7.3f}')
    print()
