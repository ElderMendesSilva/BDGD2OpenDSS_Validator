# -*- coding: utf-8 -*-
"""A impedancia dos condutores explica a diferenca de perdas entre as bases?"""
import os
import re
import statistics
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num          # noqa: E402

RX = re.compile(r'New LineCode\.(\S+).*?r1=([\d.eE+-]+) x1=([\d.eE+-]+).*?'
                r'normamps=([\d.]+)')

CASOS = [
    ('Enel SP', r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb',
     os.path.join(P, 'MODELOS_V9', '_global', 'LineCodes.dss')),
    ('Light  ', r'D:\Elder\Elder\BDGDs\Light_382_2024-12-31_V11_20250925-1811.gdb',
     os.path.join(P, 'MODELOS_LT', '_global', 'LineCodes.dss')),
]


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


for rot, gdb, lc in CASOS:
    # 1. a SEGCON crua
    b = BDGD(gdb, verbose=False)
    s = b.ler('SEGCON', ['R1', 'CNOM'])
    r_bruto = [num(x) for x in s['R1'] if num(x) > 0]

    # 2. o que foi realmente escrito nos LineCodes (pos auto-ajuste)
    r_dss, amp = [], []
    with open(lc, encoding='utf-8', errors='replace') as fh:
        for l in fh:
            m = RX.search(l)
            if m and m.group(1).endswith('_3F'):
                r_dss.append(float(m.group(2)))
                amp.append(float(m.group(4)))

    # 3. quanto de rede em cada faixa de resistencia, ponderado por km
    ss = b.ler('SSDMT', ['TIP_CND', 'COMP'])
    print(f'--- {rot}   ({len(r_bruto)} condutores na SEGCON)')
    print(f'   R1 na SEGCON      mediana {statistics.median(r_bruto):6.3f}  '
          f'p10 {q(r_bruto,.1):6.3f}  p90 {q(r_bruto,.9):6.3f} ohm/km')
    if r_dss:
        print(f'   R1 nos LineCodes  mediana {statistics.median(r_dss):6.3f}  '
              f'p10 {q(r_dss,.1):6.3f}  p90 {q(r_dss,.9):6.3f} ohm/km')
        print(f'   ampacidade        mediana {statistics.median(amp):6.0f} A   '
              f'p90 {q(amp,.9):6.0f} A')

    # R1 ponderado pelo comprimento de rede que usa cada condutor
    km_por_cnd = {}
    for i in range(len(ss['TIP_CND'])):
        k = str(ss['TIP_CND'][i]).strip()
        km_por_cnd[k] = km_por_cnd.get(k, 0.0) + num(ss['COMP'][i]) / 1000.0
    seg = b.ler('SEGCON', ['COD_ID', 'R1'])
    r_por_cod = {str(seg['COD_ID'][i]).strip(): num(seg['R1'][i])
                 for i in range(len(seg['COD_ID']))}
    pares = [(r_por_cod[k], v) for k, v in km_por_cnd.items()
             if k in r_por_cod and r_por_cod[k] > 0]
    km_tot = sum(v for _, v in pares)
    if km_tot:
        med = sum(r * v for r, v in pares) / km_tot
        print(f'   R1 medio PONDERADO por km de rede: {med:6.3f} ohm/km  '
              f'({km_tot:,.0f} km cobertos)')
    print()
