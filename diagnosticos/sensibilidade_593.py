# -*- coding: utf-8 -*-
"""SENSIBILIDADE: e se o condutor 593 fosse o condutor mediano da propria rede?

NAO e uma correcao. E uma pergunta: quanto do fracasso da Enel SP no teste
fisico se deve a esse unico registro da SEGCON.

Metodo — muda UMA variavel e so ela:
  1. copia os modelos ja gerados (topologia, cargas, trafos, curvas: idem)
  2. reescreve so as definicoes `New LineCode.CND_593_*` com os parametros do
     CND_1664, o condutor de 254 A que cobre 2.230 km da mesma concessao
  3. roda energia + balanco nas MESMAS subestacoes e compara

Nada mais e tocado. Diferenca observada e atribuivel ao condutor.
"""
import collections
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
GDB = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'
PY = r'C:\Users\Elder\AppData\Local\Programs\Python\Python314\python.exe'
ORIG, SENS = os.path.join(P, 'MODELOS_V9'), os.path.join(P, 'MODELOS_SENS')
os.environ['BDGD_SEM_JANELA'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

bal0 = json.load(open(os.path.join(ORIG, 'validacao_balanco.json'), encoding='utf-8'))
maus = {x['ctmt'] for x in bal0 if x['viola_limite'] and x['pct_total_medido'] >= 2.0}
subs = collections.Counter(x['sub'] for x in bal0 if x['ctmt'] in maus)
alvo = [s for s, _ in subs.most_common(30)]
print(f'sensibilidade em {len(alvo)} subestacoes, '
      f'{sum(subs[s] for s in alvo)} dos {len(maus)} alimentadores maus\n')

# --- 1. copia so as subestacoes de interesse ------------------------------
t0 = time.time()
if os.path.isdir(SENS):
    shutil.rmtree(SENS, ignore_errors=True)
os.makedirs(SENS, exist_ok=True)
for se in alvo:
    shutil.copytree(os.path.join(ORIG, se), os.path.join(SENS, se))
for extra in ('_global',):
    if os.path.isdir(os.path.join(ORIG, extra)):
        shutil.copytree(os.path.join(ORIG, extra), os.path.join(SENS, extra))
print(f'copiado em {time.time()-t0:.0f} s', flush=True)

# --- 2. troca os parametros do 593 pelos do 1664 --------------------------
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402
b = BDGD(GDB, verbose=False)
sc = b.ler('SEGCON', ['COD_ID', 'R1', 'X1', 'CNOM', 'CMAX'])
par = {}
for i in range(len(sc['COD_ID'])):
    par[txt(sc['COD_ID'][i]).strip()] = (num(sc['R1'][i]), num(sc['X1'][i]),
                                         num(sc['CNOM'][i]), num(sc['CMAX'][i]))
r_old, x_old, a_old, _ = par['593']
r_new, x_new, a_new, m_new = par['1664']
print(f'593  : R1={r_old:7.3f}  X1={x_old:6.3f}  CNOM={a_old:6.1f} A')
print(f'1664 : R1={r_new:7.3f}  X1={x_new:6.3f}  CNOM={a_new:6.1f} A '
      f'(2.230 km da mesma concessao)\n')

RX = re.compile(r'^(New LineCode\.CND_593_\d F?|New LineCode\.CND_593_\dF)\s',
                re.I)
n_arq = n_lin = 0
for raiz, _, arqs in os.walk(SENS):
    for a in arqs:
        if a.lower() != 'linecodes.dss':
            continue
        cam = os.path.join(raiz, a)
        saida, mudou = [], False
        with open(cam, encoding='utf-8', errors='replace') as fh:
            for l in fh:
                if l.startswith('New LineCode.CND_593_'):
                    nf = l.split('_')[2].split()[0]
                    saida.append(
                        f'New LineCode.CND_593_{nf} nphases={nf[0]} basefreq=60 '
                        f'units=km r1={r_new:.5f} x1={x_new:.5f} '
                        f'r0={r_new*3:.5f} x0={x_new*3.5:.5f} '
                        f'normamps={a_new:.1f} emergamps={m_new or a_new*1.2:.1f}'
                        f'   !! SENSIBILIDADE: era r1={r_old:.3f} '
                        f'normamps={a_old:.0f}\n')
                    mudou, n_lin = True, n_lin + 1
                else:
                    saida.append(l)
        if mudou:
            open(cam, 'w', encoding='utf-8').write(''.join(saida))
            n_arq += 1
print(f'{n_lin} definicoes trocadas em {n_arq} arquivos\n', flush=True)

# --- 3. energia + balanco -------------------------------------------------
for rot, cmd in (('energia', [PY, '-u', 'energia.py', 'MODELOS_SENS',
                              '--se'] + alvo),
                 ('valida_balanco', [PY, '-u', 'valida_balanco.py',
                                     'MODELOS_SENS', GDB])):
    t = time.time()
    r = subprocess.run(cmd, cwd=P, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    print(f'   {rot:16s} {"ok" if r.returncode == 0 else "FALHOU"} '
          f'{(time.time()-t)/60:5.1f} min', flush=True)
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-800:])
        sys.exit(1)

# --- 4. comparacao --------------------------------------------------------
bal1 = json.load(open(os.path.join(SENS, 'validacao_balanco.json'),
                      encoding='utf-8'))
d0 = {x['ctmt']: x for x in bal0}
d1 = {x['ctmt']: x for x in bal1}
comuns = [c for c in d1 if c in d0]
print(f'\n{len(comuns)} alimentadores comparaveis\n')


def resumo(rot, d, cods):
    v = [d[c] for c in cods]
    viol = [x for x in v if x['viola_limite'] and x['pct_total_medido'] >= 2.0]
    tec = [x['pct_tecnica_modelo'] for x in v]
    nt = [x['pct_nao_tecnica_implicita'] for x in v]
    print(f'{rot:22s} tecnica mediana {statistics.median(tec):6.2f}%   '
          f'violam {len(viol):4d} ({100*len(viol)/len(v):5.1f}%)   '
          f'nao tecnica implicita {statistics.median(nt):6.2f}%')


resumo('ANTES (593 original)', d0, comuns)
resumo('DEPOIS (593=1664)', d1, comuns)

mm = [c for c in comuns if c in maus]
print()
resumo('   so os que violavam', d0, mm)
resumo('   idem, depois', d1, mm)

print('\nos 8 que mais mudaram:')
dif = sorted(mm, key=lambda c: d0[c]['pct_tecnica_modelo']
             - d1[c]['pct_tecnica_modelo'], reverse=True)[:8]
for c in dif:
    print(f'   {d0[c]["sub"]:8s} {c[:14]:14s} '
          f'{d0[c]["pct_tecnica_modelo"]:7.2f}% -> {d1[c]["pct_tecnica_modelo"]:6.2f}%   '
          f'(medida {d0[c]["pct_total_medido"]:6.2f}%)  '
          f'{"ainda viola" if d1[c]["viola_limite"] else "resolvido"}')
