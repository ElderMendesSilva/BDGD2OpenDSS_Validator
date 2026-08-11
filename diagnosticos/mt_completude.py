# -*- coding: utf-8 -*-
"""A rede de MT que o modelo tem bate com a que a BDGD declara?

Se a Light perde trechos de MT na conversao, as cargas ficam eletricamente
perto da fonte e a perda desaba — que e exatamente o sintoma (1,01% contra
5,17% declarado, tensao 0,99 em toda parte).
"""
import json
import os
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402

CASOS = [
    ('Enel SP', r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb',
     os.path.join(P, 'MODELOS_V9')),
    ('Light  ', r'D:\Elder\Elder\BDGDs\Light_382_2024-12-31_V11_20250925-1811.gdb',
     os.path.join(P, 'MODELOS_LT')),
]

for rot, gdb, pasta in CASOS:
    b = BDGD(gdb, verbose=False)
    s = b.ler('SSDMT', ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'COMP'])
    n = len(s['COD_ID'])
    km_bdgd = sum(num(x) for x in s['COMP']) / 1000.0

    rel = json.load(open(os.path.join(pasta, 'relatorio_rede.json'),
                         encoding='utf-8'))['subestacoes']
    km_modelo = sum(x.get('km_MT', 0) or 0 for x in rel)
    linhas = sum(x.get('linhas', 0) or 0 for x in rel)
    alim = sum(x.get('alimentadores', 0) or 0 for x in rel)
    barras = sum(x.get('barras', 0) or 0 for x in rel)
    kw = sum((x.get('kW_BT', 0) or 0) + (x.get('kW_MT', 0) or 0) for x in rel)

    print(f'--- {rot}')
    print(f'   SSDMT declara      {n:9,} trechos   {km_bdgd:10,.1f} km')
    print(f'   modelo tem         {linhas:9,} linhas    {km_modelo:10,.1f} km   '
          f'({100*km_modelo/max(km_bdgd,1e-9):5.1f}% do declarado)')
    print(f'   {alim:,} alimentadores -> {km_modelo/max(alim,1):6.2f} km/alim   '
          f'{barras:,} barras   {kw/1000:,.0f} MW')

    # quantos trechos da SSDMT tem PAC que aparece em outro trecho (topologia)
    pacs = {}
    for i in range(n):
        for c in ('PAC_1', 'PAC_2'):
            k = txt(s[c][i]).strip()
            pacs[k] = pacs.get(k, 0) + 1
    orfaos = sum(1 for i in range(n)
                 if pacs.get(txt(s['PAC_1'][i]).strip(), 0) < 2
                 and pacs.get(txt(s['PAC_2'][i]).strip(), 0) < 2)
    print(f'   trechos com os dois PACs sem vizinho: {orfaos:,} '
          f'({100*orfaos/max(n,1):.2f}%)')
    print()
