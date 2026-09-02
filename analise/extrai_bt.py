# -*- coding: utf-8 -*-
"""
EXTRACAO DA BAIXA TENSAO (UCBT_tab), POR ALIMENTADOR
====================================================

    python analise/extrai_bt.py                     abre o painel e pergunta
    python analise/extrai_bt.py 0 700000            so a primeira fatia
    python analise/extrai_bt.py 700000 8258035      continua de onde parou
    python analise/extrai_bt.py --gdb ..\\X.gdb --saida dados\\extraido_bdgd

Sao 8,26 milhoes de unidades consumidoras de baixa tensao. A leitura e em
fatias, e o acumulado por alimentador fica num pickle na pasta de saida — o
que permite rodar em pedacos e continuar depois, sem reler o que ja passou.

`bt_todos.json` so e escrito quando a leitura chega ao fim da tabela; ate la
existe apenas o parcial. Sem argumento, o painel ja propoe a tabela inteira.
"""
import argparse
import collections
import json
import os
import pickle
import sys
import time

import numpy as np
import pyogrio

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                 # a raiz do projeto, onde esta o interativo.py
sys.path.insert(0, RAIZ)

GDB = os.path.normpath(os.path.join(RAIZ, os.pardir,
                                    'Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'))
SAIDA = os.path.join(RAIZ, 'dados', 'extraido_bdgd')
PASSO = 700000
PARCIAL = '_bt_parcial.pkl'

COLS = (['CTMT', 'TIP_CC']
        + [f'ENE_{m:02d}' for m in range(1, 13)]
        + [f'DIC_{m:02d}' for m in range(1, 13)])


def novo():
    return {'n': 0, 'ene': np.zeros(12), 'dic': 0.0, 'cur': collections.Counter()}


def extrai(gdb, saida, ini=0, fim=None, passo=PASSO):
    os.makedirs(saida, exist_ok=True)
    pk = os.path.join(saida, PARCIAL)
    tot = pyogrio.read_info(gdb, layer='UCBT_tab')['features']
    fim = tot if not fim else min(fim, tot)
    acc = collections.defaultdict(novo)
    if ini > 0 and os.path.exists(pk):
        acc.update(pickle.load(open(pk, 'rb')))
        print(f'retomando de {ini:,} com {len(acc):,} alimentadores ja lidos', flush=True)
    t0 = time.time()
    for skip in range(ini, fim, passo):
        meta, fids, geom, data = pyogrio.raw.read(
            gdb, layer='UCBT_tab', columns=COLS, read_geometry=False,
            skip_features=skip, max_features=passo)
        cs = list(meta['fields']); col = {c: data[cs.index(c)] for c in cs}
        ct = col['CTMT']
        ene = np.vstack([np.nan_to_num(col[f'ENE_{m:02d}'].astype(float)) for m in range(1, 13)])
        dic = np.nan_to_num(np.sum([col[f'DIC_{m:02d}'].astype(float) for m in range(1, 13)], axis=0))
        for i in range(len(ct)):
            k = ct[i]
            if not k:
                continue
            a = acc[k]; a['n'] += 1; a['ene'] += ene[:, i]; a['dic'] += dic[i]
            a['cur'][col['TIP_CC'][i]] += 1
        print(f'  {min(skip+passo,fim):,}/{tot:,} ({time.time()-t0:.0f}s) '
              f'ctmts={len(acc):,}', flush=True)
    pickle.dump(dict(acc), open(pk, 'wb'))
    print(f'salvo ate {fim:,}', flush=True)
    if fim >= tot:
        out = {k: {'n_uc': v['n'], 'ene': [round(x, 1) for x in v['ene']],
                   'dic_total': round(v['dic'], 1),
                   'curva': v['cur'].most_common(1)[0][0] if v['cur'] else None}
               for k, v in acc.items()}
        p = os.path.join(saida, 'bt_todos.json')
        json.dump(out, open(p, 'w'))
        # a tabela inteira ja esta no JSON: o parcial so atrapalharia a
        # proxima rodada, que voltaria a somar em cima do que ja foi contado
        os.remove(pk)
        print('COMPLETO:', len(out), 'alimentadores')
        print('saida:', p)
    else:
        print(f'parcial em {pk}')
        print(f'continue com: python analise/extrai_bt.py {fim} {tot}')


def _painel():
    from bdgd2dss import interativo
    v = interativo.formulario('extrai_bt', 'Extrair a baixa tensão da BDGD', [
        {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
         'padrao': interativo.bdgd_recente() or GDB,
         'dica': 'o File Geodatabase é uma PASTA terminada em .gdb'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Pasta de saída',
         'padrao': SAIDA, 'dica': 'recebe o bt_todos.json'},
        {'chave': 'ini', 'tipo': 'inteiro', 'rotulo': 'Do registro',
         'padrao': 0, 'minimo': 0, 'maximo': 99000000},
        {'chave': 'fim', 'tipo': 'inteiro', 'rotulo': 'Até o registro',
         'padrao': 0, 'minimo': 0, 'maximo': 99000000,
         'dica': '0 = até o fim da tabela. Os dois campos só servem para '
                 'quebrar a leitura em pedaços e continuar depois'},
        {'chave': 'passo', 'tipo': 'inteiro', 'rotulo': 'Registros por fatia',
         'padrao': PASSO, 'minimo': 50000, 'maximo': 2000000,
         'dica': 'quanto se lê de cada vez; diminua se faltar memória'},
    ], ajuda='Soma por alimentador a energia mensal e o DIC dos 8,26 milhões '
             'de consumidores de baixa tensão, e guarda a curva de carga mais '
             'frequente. É a extração mais demorada das três.')
    if not v:
        return False
    sys.argv += [str(v['ini']), str(v['fim']), '--gdb', v['gdb'],
                 '--saida', v['saida'], '--passo', str(v['passo'])]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('ini', nargs='?', type=int, default=0,
                    help='primeiro registro a ler')
    ap.add_argument('fim', nargs='?', type=int, default=0,
                    help='ultimo registro a ler (0 = ate o fim da tabela)')
    ap.add_argument('--gdb', default=GDB, help='a BDGD (pasta .gdb)')
    ap.add_argument('--saida', default=SAIDA, help='onde gravar o JSON')
    ap.add_argument('--passo', type=int, default=PASSO,
                    help='registros lidos por fatia')
    a = ap.parse_args()

    if not os.path.exists(a.gdb):
        raise SystemExit(f'BDGD nao encontrada: {a.gdb}')
    extrai(a.gdb, a.saida, a.ini, a.fim, a.passo)


if __name__ == '__main__':
    main()
