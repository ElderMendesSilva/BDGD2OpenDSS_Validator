# -*- coding: utf-8 -*-
"""Sonda uma BDGD antes de converter: o que tem, e quais premissas nossas quebram.

    python sonda_bdgd.py <caminho.gdb>

Nao converte nada. So le e compara com o que o conversor assume.
"""
import collections
import os
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402
from bdgd2dss import tensoes, transformadores       # noqa: E402

GDB = sys.argv[1]
print(f'BDGD: {os.path.basename(GDB)}\n')

# --- 1. camadas presentes -------------------------------------------------
import pyogrio
camadas = {c[0] for c in pyogrio.list_layers(GDB)}
PRECISA = ['CTMT', 'SSDMT', 'SSDBT', 'RAMLIG', 'UCBT_tab', 'UCMT_tab',
           'UGBT_tab', 'UGMT_tab', 'UNTRMT', 'EQTRMT', 'SEGCON', 'UNSEMT',
           'UNCRMT', 'UNREMT', 'SSDAT', 'UNSEAT', 'UNTRAT', 'EQTRAT', 'CRVCRG',
           'UCAT_tab', 'UGAT_tab', 'UNCRAT', 'BAR', 'CTAT']
falta = [t for t in PRECISA if t not in camadas]
print(f'1. CAMADAS: {len(camadas)} na base')
print(f'   o conversor procura {len(PRECISA)}; AUSENTES: '
      f'{", ".join(falta) if falta else "nenhuma"}')

b = BDGD(GDB, verbose=False)

# --- 2. porte -------------------------------------------------------------
c = b.ler('CTMT', ['COD_ID', 'SUB', 'TEN_NOM'])
subs = {txt(x).strip() for x in c['SUB']}
print(f'\n2. PORTE: {len(subs)} subestacoes, {len(c["COD_ID"])} alimentadores')

# --- 3. codigos de tensao (fragilidade conhecida n.1) ---------------------
cod = collections.Counter(txt(x).strip() for x in c['TEN_NOM'])
print(f'\n3. CODIGOS DE TENSAO em CTMT.TEN_NOM')
desconhecidos = 0
for k, n in cod.most_common():
    v = tensoes.TENSAO_KV.get(k)
    marca = f'{v} kV' if v else '*** SEM VALOR — cai no padrao 13.8 kV'
    if not v:
        desconhecidos += n
    print(f'   {k:>4s}  {n:5d} alimentadores   {marca}')
print(f'   -> {desconhecidos} de {len(c["COD_ID"])} alimentadores '
      f'({100*desconhecidos/len(c["COD_ID"]):.1f}%) com tensao ADIVINHADA')

# --- 4. tensoes de BT (fragilidade n.2) -----------------------------------
try:
    t = b.ler('UNTRMT', ['TEN_LIN_SE'])
    tl = collections.Counter(round(num(x), 4) for x in t['TEN_LIN_SE'])
    print(f'\n4. TEN_LIN_SE dos {sum(tl.values())} transformadores')
    bases_nossas = set(tensoes.bases())
    fora = 0
    for k, n in tl.most_common(10):
        norm = transformadores._linha(k)
        ok = round(norm, 4) in bases_nossas
        if not ok:
            fora += n
        print(f'   {k:<8} {n:6d}  -> linha {norm:<8} '
              f'{"ok" if ok else "*** FORA do Voltagebases"}')
    print(f'   -> {fora} transformadores em tensao que o conversor nao declara')
except Exception as e:
    print(f'\n4. UNTRMT: ERRO — {e}')

# --- 5. condutores --------------------------------------------------------
try:
    s = b.ler('SEGCON', ['COD_ID', 'R1', 'X1', 'CNOM'])
    r = [num(x) for x in s['R1']]
    x = [num(x) for x in s['X1']]
    print(f'\n5. SEGCON: {len(r)} condutores')
    print(f'   R1 zerado ou negativo: {sum(1 for v in r if v <= 0)}')
    print(f'   X1 zerado ou negativo: {sum(1 for v in x if v <= 0)}')
except Exception as e:
    print(f'\n5. SEGCON: ERRO — {e}')

# --- 6. subtransmissao ----------------------------------------------------
for tab in ('SSDAT', 'UNTRAT', 'UNSEAT'):
    try:
        d = b.ler(tab, ['COD_ID'])
        print(f'\n6. {tab}: {len(d["COD_ID"])} registros')
    except Exception as e:
        print(f'\n6. {tab}: ERRO — {str(e)[:80]}')
