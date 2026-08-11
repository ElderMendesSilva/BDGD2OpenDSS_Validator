# -*- coding: utf-8 -*-
"""O que distingue os 458 alimentadores da Enel SP que violam o limite fisico?

Compara-os contra os demais em atributos MEDIVEIS da propria BDGD. Nao chuta
causa: procura o atributo que separa os dois grupos.
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

bal = json.load(open(os.path.join(P, 'MODELOS_V9', 'validacao_balanco.json'),
                     encoding='utf-8'))
maus = {x['ctmt'] for x in bal if x['viola_limite'] and x['pct_total_medido'] >= 2.0}
bons = {x['ctmt'] for x in bal} - maus
print(f'{len(maus)} violam de verdade | {len(bons)} nao violam\n')

b = BDGD(GDB, verbose=False)

# --- rede de MT por alimentador -------------------------------------------
print('lendo SSDMT...', flush=True)
s = b.ler('SSDMT', ['CTMT', 'COMP', 'TIP_CND'])
km = collections.defaultdict(float)
ntr = collections.Counter()
cnd_por_ctmt = collections.defaultdict(collections.Counter)
for i in range(len(s['CTMT'])):
    c = txt(s['CTMT'][i]).strip().upper()
    L = num(s['COMP'][i]) / 1000.0
    km[c] += L
    cnd_por_ctmt[c][txt(s['TIP_CND'][i]).strip()] += L

print('lendo SEGCON...', flush=True)
sc = b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
r_por_cnd = {txt(sc['COD_ID'][i]).strip(): num(sc['R1'][i])
             for i in range(len(sc['COD_ID']))}
a_por_cnd = {txt(sc['COD_ID'][i]).strip(): num(sc['CNOM'][i])
             for i in range(len(sc['COD_ID']))}

print('lendo UNTRMT...', flush=True)
t = b.ler('UNTRMT', ['CTMT', 'POT_NOM'])
kva = collections.defaultdict(float)
for i in range(len(t['CTMT'])):
    c = txt(t['CTMT'][i]).strip().upper()
    kva[c] += num(t['POT_NOM'][i])
    ntr[c] += 1


def r_medio(c):
    """R1 ponderado pelo km de rede daquele alimentador."""
    tot = sum(cnd_por_ctmt[c].values())
    if not tot:
        return None
    return sum(r_por_cnd.get(k, 0.4) * v for k, v in cnd_por_ctmt[c].items()) / tot


def amp_media(c):
    tot = sum(cnd_por_ctmt[c].values())
    if not tot:
        return None
    return sum(a_por_cnd.get(k, 200.0) * v for k, v in cnd_por_ctmt[c].items()) / tot


por_cod = {x['ctmt']: x for x in bal}


def perfil(rot, cods):
    def m(f):
        v = [f(c) for c in cods if f(c) is not None]
        return statistics.median(v) if v else float('nan')
    kwh = lambda c: por_cod[c]['GWh_injetado'] * 1e6                # noqa: E731
    ucs = lambda c: por_cod[c]['ucs'] or None                       # noqa: E731
    print(f'{rot:16s} '
          f'km {m(lambda c: km.get(c)):7.2f}  '
          f'trafos {m(lambda c: ntr.get(c)):6.0f}  '
          f'kVA {m(lambda c: kva.get(c)):9.0f}  '
          f'GWh {m(lambda c: por_cod[c]["GWh_injetado"]):6.2f}  '
          f'UCs {m(ucs):7.0f}  '
          f'R1 {m(r_medio):6.3f}  '
          f'CNOM {m(amp_media):6.0f}  '
          f'kW/km {m(lambda c: (kwh(c)/8760)/km[c] if km.get(c) else None):8.1f}  '
          f'kVA/GWh {m(lambda c: (kva[c]/por_cod[c]["GWh_injetado"]) if (kva.get(c) and por_cod[c]["GWh_injetado"]) else None):8.1f}')


print()
print(f'{"grupo":16s} {"km":>10s} {"trafos":>13s} {"kVA":>13s} {"GWh":>10s} '
      f'{"UCs":>11s} {"R1":>9s} {"CNOM":>11s} {"kW/km":>14s} {"kVA/GWh":>16s}')
perfil('VIOLAM (458)', maus)
perfil('nao violam', bons)

# --- razao de carregamento: demanda media contra capacidade instalada ------
print('\ncarregamento medio do alimentador (kW medio / kVA instalado):')
for rot, cods in (('VIOLAM', maus), ('nao violam', bons)):
    v = [(por_cod[c]['GWh_injetado'] * 1e6 / 8760) / kva[c]
         for c in cods if kva.get(c)]
    v = sorted(v)
    if v:
        print(f'   {rot:12s} mediana {statistics.median(v):6.3f}   '
              f'p10 {v[len(v)//10]:6.3f}   p90 {v[9*len(v)//10]:6.3f}   '
              f'acima de 1,0: {100*sum(1 for x in v if x > 1)/len(v):5.1f}%')

# --- alimentadores sem transformador declarado ----------------------------
print('\nalimentadores sem transformador ou sem rede na BDGD:')
for rot, cods in (('VIOLAM', maus), ('nao violam', bons)):
    sem_tr = sum(1 for c in cods if not ntr.get(c))
    sem_km = sum(1 for c in cods if not km.get(c))
    print(f'   {rot:12s} sem trafo {sem_tr:4d} ({100*sem_tr/len(cods):5.1f}%)   '
          f'sem rede {sem_km:4d} ({100*sem_km/len(cods):5.1f}%)')
