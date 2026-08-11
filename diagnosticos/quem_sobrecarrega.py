# -*- coding: utf-8 -*-
"""Nos 458 alimentadores que violam o limite fisico, QUAL condutor sobrecarrega?

Nao basta o 593 ser maioria da sobrecarga: ele ja e 13,5% da rede. O numero
que decide e o ENRIQUECIMENTO — a fracao dele na sobrecarga dividida pela
fracao dele na rede daqueles mesmos alimentadores.
"""
import collections
import json
import os
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
os.chdir(P)
CWD = os.getcwd()
sys.path.insert(0, P)
import opendssdirect as dss                          # noqa: E402

UNI = {1: 1609.344, 2: 304.8, 3: 1000.0, 4: 1.0, 5: 0.3048, 6: 0.0254, 7: 0.01}

bal = json.load(open(os.path.join(P, 'MODELOS_V9', 'validacao_balanco.json'),
                     encoding='utf-8'))
maus = {x['ctmt'] for x in bal if x['viola_limite'] and x['pct_total_medido'] >= 2.0}
subs = collections.Counter(x['sub'] for x in bal if x['ctmt'] in maus)
alvo = [s for s, _ in subs.most_common(30)]
cobre = sum(subs[s] for s in alvo)
print(f'{len(maus)} alimentadores violam, em {len(subs)} subestacoes.')
print(f'amostra: {len(alvo)} subestacoes, cobrindo {cobre} deles '
      f'({100*cobre/len(maus):.0f}%)\n', flush=True)

km_rede = collections.Counter()      # linecode -> km, so nos alimentadores maus
km_sobre = collections.Counter()     # linecode -> km em sobrecarga
perda_sobre = collections.Counter()
n_ok = 0
for k, se in enumerate(alvo, 1):
    m = os.path.join(P, 'MODELOS_V9', se, f'MASTER-{se}.dss')
    if not os.path.exists(m):
        continue
    dss.Text.Command('Clear')
    dss.Text.Command(f'Compile "{m}"')
    os.chdir(CWD)
    dss.Text.Command('Set mode=snap')
    dss.Text.Command('Set controlmode=static')
    dss.Text.Command('Solve')
    os.chdir(CWD)
    if not dss.Solution.Converged():
        continue
    n_ok += 1

    zonas = {}
    j = dss.Meters.First()
    while j:
        nome = dss.Meters.Name()
        alim = (nome[3:] if nome.lower().startswith('em_') else nome).upper()
        if alim in maus:
            for e in (dss.Meters.AllBranchesInZone() or []):
                if e.lower().startswith('line.'):
                    zonas[e.split('.', 1)[1].lower()] = alim
        dss.Meters.Name(nome)
        j = dss.Meters.Next()

    i = dss.Lines.First()
    while i:
        nome = dss.Lines.Name()
        if nome.lower() in zonas:
            dss.Circuit.SetActiveElement('Line.' + nome)
            na = dss.CktElement.NormalAmps()
            cur = dss.CktElement.CurrentsMagAng()[0::2]
            nc = dss.CktElement.NumConductors()
            im = max(cur[:nc]) if nc else 0.0
            pl = max(dss.CktElement.Losses()[0] / 1000.0, 0.0)
            dss.Lines.Name(nome)
            lc = (dss.Lines.LineCode() or '?').upper()
            km = dss.Lines.Length() * UNI.get(dss.Lines.Units(), 1.0) / 1000.0
            km_rede[lc] += km
            if na > 1 and im == im and im > na:
                km_sobre[lc] += km
                perda_sobre[lc] += pl
        i = dss.Lines.Next()
    if k % 5 == 0:
        print(f'   {k}/{len(alvo)} subestacoes', flush=True)

tot_rede = sum(km_rede.values())
tot_sobre = sum(km_sobre.values())
tot_perda = sum(perda_sobre.values())
print(f'\n{n_ok} subestacoes resolvidas | {tot_rede:,.0f} km nos alimentadores '
      f'maus | {tot_sobre:,.0f} km em sobrecarga ({100*tot_sobre/tot_rede:.1f}%)\n')

print(f'{"linecode":20s} {"km na rede":>12s} {"km sobrec.":>12s} '
      f'{"% da sobrec.":>13s} {"% da rede":>11s} {"ENRIQUEC.":>10s} {"perda kW":>11s}')
for lc, kms in km_sobre.most_common(12):
    f_s = kms / tot_sobre
    f_r = km_rede[lc] / tot_rede
    print(f'{lc[:20]:20s} {km_rede[lc]:12,.1f} {kms:12,.1f} '
          f'{100*f_s:12.1f}% {100*f_r:10.1f}% '
          f'{(f_s/f_r if f_r else 0):9.2f}x {perda_sobre[lc]:10,.0f}')

n593 = sum(v for k, v in km_sobre.items() if k.startswith('CND_593'))
r593 = sum(v for k, v in km_rede.items() if k.startswith('CND_593'))
p593 = sum(v for k, v in perda_sobre.items() if k.startswith('CND_593'))
print(f'\nCONDUTOR 593 (todas as variantes de fase):')
print(f'   {r593:,.0f} km nos alimentadores maus ({100*r593/tot_rede:.1f}% da rede deles)')
print(f'   {n593:,.0f} km em sobrecarga ({100*n593/tot_sobre:.1f}% de toda a sobrecarga)')
print(f'   enriquecimento {(n593/tot_sobre)/(r593/tot_rede) if r593 else 0:.2f}x')
print(f'   {p593:,.0f} kW de perda ({100*p593/tot_perda:.1f}% da perda em sobrecarga)')
print(f'   fracao do proprio 593 que esta sobrecarregada: '
      f'{100*n593/r593 if r593 else 0:.1f}%')
