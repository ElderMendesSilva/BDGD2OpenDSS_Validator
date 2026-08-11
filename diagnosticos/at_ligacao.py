# -*- coding: utf-8 -*-
"""Se o UNTRAT da Light nao liga por PAC, liga por que? Testa BARR contra BAR."""
import sys

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
sys.path.insert(0, P)
from bdgd2dss.leitor import BDGD, txt          # noqa: E402

BASES = {
    'Enel SP': r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\Enel_SP_390_2024-12-31_V11_20250702-2009.gdb',
    'Light  ': r'D:\Elder\Elder\BDGDs\Light_382_2024-12-31_V11_20250925-1811.gdb',
}


def col(d, c):
    return [txt(x).strip() for x in d[c]]


for rot, gdb in BASES.items():
    b = BDGD(gdb, verbose=False)
    bar = b.ler('BAR', ['COD_ID', 'PAC'])
    t = b.ler('UNTRAT', ['COD_ID', 'BARR_1', 'BARR_2', 'PAC_1', 'PAC_2'])
    s = b.ler('SSDAT', ['PAC_1', 'PAC_2'])

    bar_cod = set(col(bar, 'COD_ID'))
    bar_pac = set(col(bar, 'PAC'))
    ssd_pac = set(col(s, 'PAC_1')) | set(col(s, 'PAC_2'))
    n = len(t['COD_ID'])

    def pct(v):
        return f'{v:5d}/{n:<5d} ({100*v/max(n,1):5.1f}%)'

    print(f'--- {rot}   ({n} transformadores de potencia)')
    print(f'   UNTRAT.PAC_1  na SSDAT  : {pct(sum(1 for x in col(t,"PAC_1") if x in ssd_pac))}')
    print(f'   UNTRAT.PAC_1  em BAR.PAC: {pct(sum(1 for x in col(t,"PAC_1") if x in bar_pac))}')
    print(f'   UNTRAT.BARR_1 em BAR.COD: {pct(sum(1 for x in col(t,"BARR_1") if x in bar_cod))}')
    print(f'   UNTRAT.BARR_2 em BAR.COD: {pct(sum(1 for x in col(t,"BARR_2") if x in bar_cod))}')
    # e as barras da BAR, aparecem na SSDAT?
    nb = len(bar['COD_ID'])
    print(f'   BAR.PAC na SSDAT        : '
          f'{sum(1 for x in col(bar,"PAC") if x in ssd_pac):5d}/{nb:<5d} '
          f'({100*sum(1 for x in col(bar,"PAC") if x in ssd_pac)/max(nb,1):5.1f}%)')
    print()
