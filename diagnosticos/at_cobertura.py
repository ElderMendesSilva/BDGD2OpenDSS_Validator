# -*- coding: utf-8 -*-
"""
QUAL CHAVE LIGA O TRAFO DE POTENCIA A REDE DE AT?  — achado 7
=============================================================

    python at_cobertura.py <caminho.gdb> [<caminho.gdb> ...]

O conversor amarra o primario do trafo de AT por `UNTRAT.PAC_1`, porque foi
assim que a convencao da Enel SP foi decifrada por engenharia reversa. Medido
depois: casa 94,2% na Enel SP e **0,0% na Light**, e por isso a camada de AT
da Light saiu com 0 trechos, 0 fontes e 0 km — com uma SSDAT impecavel de
7.909 trechos do lado.

Este script mede, para cada base, a cobertura de CADA candidata a ancora:

    PAC_1 na SSDAT           o que o conversor usa hoje
    BARR_1 em BAR.COD_ID     a chave que a Light preserva
    BAR.PAC na SSDAT         o elo que faria BARR_1 chegar na rede
    UNTRAT.SUB em UNSEAT.SUB a ancora por subestacao, que o malha_at ja usa

A decisao do passo 5 sai daqui e nao de preferencia: a ancora escolhida tem
de ser a que cobre mais bases, nao a que funciona na primeira.

Versao parametrizada do `at_ligacao.py`, que so rodava em duas bases com
caminho embutido.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss.leitor import BDGD, txt              # noqa: E402
from bdgd2dss.malha_at import _no                  # noqa: E402


def medir(gdb):
    b = BDGD(gdb, verbose=False)
    r = {'gdb': os.path.basename(gdb)}
    try:
        r['dist'] = txt(b.ler('BASE', ['DIST'])['DIST'][0]).strip()
    except Exception:
        r['dist'] = '?'

    t = b.ler('UNTRAT', ['COD_ID', 'SUB', 'BARR_1', 'BARR_2', 'PAC_1',
                         'PAC_2', 'SIT_ATIV'])
    ativos = [i for i in range(len(t['COD_ID']))
              if txt(t['SIT_ATIV'][i]).strip() in ('AT', '')]
    n = len(ativos)
    r['trafos'] = n
    if not n:
        return r

    s = b.ler('SSDAT', ['PAC_1', 'PAC_2'])
    nos_ssdat = {_no(s['PAC_1'][i]) for i in range(len(s['PAC_1']))}
    nos_ssdat |= {_no(s['PAC_2'][i]) for i in range(len(s['PAC_2']))}
    nos_ssdat.discard('')
    r['nos_ssdat'] = len(nos_ssdat)

    bar = b.ler('BAR', ['COD_ID', 'PAC', 'SUB', 'TIP_INST'])
    bar_cod = {txt(bar['COD_ID'][i]).strip() for i in range(len(bar['COD_ID']))}
    pac_de_barra = {txt(bar['COD_ID'][i]).strip(): _no(bar['PAC'][i])
                    for i in range(len(bar['COD_ID']))}
    r['barras'] = len(bar_cod)
    r['bar_pac_na_ssdat'] = round(
        100.0 * sum(1 for v in pac_de_barra.values() if v in nos_ssdat)
        / max(len(pac_de_barra), 1), 1)

    try:
        u = b.ler('UNSEAT', ['SUB', 'SIT_ATIV'])
        subs_unseat = {txt(u['SUB'][i]).strip() for i in range(len(u['SUB']))
                       if txt(u['SIT_ATIV'][i]).strip() in ('AT', '')}
        subs_unseat.discard('')
    except Exception:
        subs_unseat = set()
    r['subs_unseat'] = len(subs_unseat)

    c = collections.Counter()
    for i in ativos:
        if _no(t['PAC_1'][i]) in nos_ssdat:
            c['pac_1'] += 1
        b1 = txt(t['BARR_1'][i]).strip()
        if b1 in bar_cod:
            c['barr_1'] += 1
            if pac_de_barra.get(b1) in nos_ssdat:
                c['barr_1_ate_ssdat'] += 1
        if txt(t['SUB'][i]).strip() in subs_unseat:
            c['sub_em_unseat'] += 1
    for k in ('pac_1', 'barr_1', 'barr_1_ate_ssdat', 'sub_em_unseat'):
        r[k] = round(100.0 * c[k] / n, 1)
    # a ancora combinada: PAC_1, ou BARR_1->BAR.PAC, ou a subestacao
    for i in ativos:
        b1 = txt(t['BARR_1'][i]).strip()
        if (_no(t['PAC_1'][i]) in nos_ssdat
                or pac_de_barra.get(b1) in nos_ssdat
                or txt(t['SUB'][i]).strip() in subs_unseat):
            c['combinada'] += 1
    r['combinada'] = round(100.0 * c['combinada'] / n, 1)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('gdb', nargs='+')
    a = ap.parse_args()

    print(f'{"base":34s} {"dist":>5s} {"trafos":>7s} {"PAC_1":>7s} '
          f'{"BARR_1":>7s} {"->SSDAT":>8s} {"SUB":>7s} {"combin":>7s}')
    linhas = []
    for g in a.gdb:
        try:
            r = medir(g)
        except Exception as e:
            print(f'{os.path.basename(g)[:34]:34s} ERRO: {str(e)[:60]}')
            continue
        linhas.append(r)
        print(f'{r["gdb"][:34]:34s} {r["dist"]:>5s} {r.get("trafos",0):7,} '
              f'{r.get("pac_1","—"):>6}% {r.get("barr_1","—"):>6}% '
              f'{r.get("barr_1_ate_ssdat","—"):>7}% '
              f'{r.get("sub_em_unseat","—"):>6}% {r.get("combinada","—"):>6}%')

    if len(linhas) > 1:
        print('\nO MINIMO DE CADA ANCORA — e o minimo que decide, nao a media:')
        for k, rot in (('pac_1', 'PAC_1 na SSDAT (em uso hoje)'),
                       ('barr_1_ate_ssdat', 'BARR_1 -> BAR.PAC -> SSDAT'),
                       ('sub_em_unseat', 'UNTRAT.SUB em UNSEAT.SUB'),
                       ('combinada', 'as tres, na ordem')):
            v = [x[k] for x in linhas if k in x]
            if v:
                print(f'   {rot:34s} min {min(v):5.1f}%   mediana '
                      f'{sorted(v)[len(v)//2]:5.1f}%')


if __name__ == '__main__':
    main()
