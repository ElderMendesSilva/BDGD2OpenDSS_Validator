# -*- coding: utf-8 -*-
"""Fracao da quilometragem que carrega corrente acima da ampacidade.

Compara alimentadores que VIOLAM o limite fisico contra os que nao violam,
DENTRO DAS MESMAS SUBESTACOES — assim o efeito nao se confunde com
caracteristica da subestacao.
"""
import collections
import json
import os
import statistics
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
os.chdir(P)
CWD = os.getcwd()
sys.path.insert(0, P)
import opendssdirect as dss                          # noqa: E402

# codigo de unidade do OpenDSS -> metros
UNI = {1: 1609.344, 2: 304.8, 3: 1000.0, 4: 1.0, 5: 0.3048, 6: 0.0254, 7: 0.01}

bal = json.load(open(os.path.join(P, 'MODELOS_V9', 'validacao_balanco.json'),
                     encoding='utf-8'))
maus = {x['ctmt'] for x in bal if x['viola_limite'] and x['pct_total_medido'] >= 2.0}
por_sub = collections.defaultdict(lambda: [0, 0])
for x in bal:
    por_sub[x['sub']][0 if x['ctmt'] in maus else 1] += 1

# subestacoes com pelo menos 2 de cada — comparacao controlada
mistas = [s for s, (m, b) in por_sub.items() if m >= 2 and b >= 2]
mistas.sort(key=lambda s: -(por_sub[s][0] + por_sub[s][1]))
alvo = mistas[:6]
print(f'{len(mistas)} subestacoes tem os dois grupos; usando {alvo}\n')

linhas = []
for se in alvo:
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
        print(f'   {se}: nao convergiu, pulando')
        continue

    # medidor -> zona: usa o EnergyMeter para saber de que alimentador e a linha
    zonas = {}
    j = dss.Meters.First()
    while j:
        nome = dss.Meters.Name()
        alim = (nome[3:] if nome.lower().startswith('em_') else nome).upper()
        for e in (dss.Meters.AllBranchesInZone() or []):
            if e.lower().startswith('line.'):
                zonas[e.split('.', 1)[1].lower()] = alim
        dss.Meters.Name(nome)
        j = dss.Meters.Next()

    acc = collections.defaultdict(lambda: collections.Counter())
    i = dss.Lines.First()
    while i:
        nome = dss.Lines.Name()
        alim = zonas.get(nome.lower())
        if alim:
            dss.Circuit.SetActiveElement('Line.' + nome)
            na = dss.CktElement.NormalAmps()
            cur = dss.CktElement.CurrentsMagAng()[0::2]
            nc = dss.CktElement.NumConductors()
            im = max(cur[:nc]) if nc else 0.0
            dss.Lines.Name(nome)
            km = dss.Lines.Length() * UNI.get(dss.Lines.Units(), 1.0) / 1000.0
            pl = dss.CktElement.Losses()[0] / 1000.0
            a = acc[alim]
            a['km'] += km
            a['perda'] += max(pl, 0.0)
            if na > 1 and im == im:
                if im > na:
                    a['km_sobre'] += km
                    a['perda_sobre'] += max(pl, 0.0)
                if im > 2 * na:
                    a['km_2x'] += km
        i = dss.Lines.Next()

    for alim, a in acc.items():
        if a['km'] > 0.1:
            linhas.append({
                'se': se, 'ctmt': alim, 'mau': alim in maus,
                'km': a['km'],
                'f_sobre': a['km_sobre'] / a['km'],
                'f_2x': a['km_2x'] / a['km'],
                'f_perda_sobre': (a['perda_sobre'] / a['perda']
                                  if a['perda'] > 0 else 0.0)})
    print(f'   {se}: {len(acc)} alimentadores medidos', flush=True)

print(f'\n{len(linhas)} alimentadores no total\n')
print(f'{"grupo":16s} {"n":>4s} {"km":>8s} {"km>Inom":>10s} {"km>2xInom":>11s} '
      f'{"perda em sobrecarga":>21s}')
for rot, sel in (('VIOLAM', True), ('nao violam', False)):
    g = [x for x in linhas if x['mau'] == sel]
    if not g:
        continue
    print(f'{rot:16s} {len(g):4d} '
          f'{statistics.median([x["km"] for x in g]):8.2f} '
          f'{100*statistics.median([x["f_sobre"] for x in g]):9.1f}% '
          f'{100*statistics.median([x["f_2x"] for x in g]):10.1f}% '
          f'{100*statistics.median([x["f_perda_sobre"] for x in g]):20.1f}%')

print('\nalimentador a alimentador (ordenado pela fracao em sobrecarga):')
for x in sorted(linhas, key=lambda z: -z['f_sobre'])[:18]:
    print(f'   {x["se"]:6s} {x["ctmt"][:14]:14s} '
          f'{"VIOLA" if x["mau"] else "  ok ":6s} '
          f'km {x["km"]:7.2f}  >Inom {100*x["f_sobre"]:5.1f}%  '
          f'>2x {100*x["f_2x"]:5.1f}%  perda ali {100*x["f_perda_sobre"]:5.1f}%')
