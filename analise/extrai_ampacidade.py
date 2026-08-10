# -*- coding: utf-8 -*-
"""
AMPACIDADE DO TRONCO DE SAIDA DE CADA ALIMENTADOR (SSDMT x SEGCON)
==================================================================

    python analise/extrai_ampacidade.py                    abre o painel
    python analise/extrai_ampacidade.py --gdb ..\\X.gdb --saida dados\\extraido_bdgd

Percorre o 1,4 milhao de trechos de media tensao e guarda, por CTMT, a MAIOR
capacidade entre os trechos TRIFASICOS — que e o tronco de saida, o gargalo
que define o carregamento do alimentador. Trecho monofasico ou bifasico entra
so na quilometragem, porque nao carrega a corrente do alimentador inteiro.

Sai `amp_todos.json` com cnom, cmax, numero de trechos e km de rede.
A leitura e em fatias: a camada nao cabe confortavelmente na memoria de uma vez.
"""
import argparse
import collections
import json
import os
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
PASSO = 400000


def extrai(gdb, saida, passo=PASSO):
    os.makedirs(saida, exist_ok=True)
    t0 = time.time()
    # SEGCON: codigo do condutor -> CNOM/CMAX
    m, f, g, d = pyogrio.raw.read(gdb, layer='SEGCON',
                                  columns=['COD_ID', 'CNOM', 'CMAX'],
                                  read_geometry=False)
    cs = list(m['fields']); c = {x: d[cs.index(x)] for x in cs}
    seg = {c['COD_ID'][i]: (float(c['CNOM'][i] or 0), float(c['CMAX'][i] or 0))
           for i in range(len(c['COD_ID']))}
    print('SEGCON:', len(seg), flush=True)
    # SSDMT: por CTMT, a maior ampacidade trifasica (tronco de saida).
    # O total vem da propria camada, e nao de uma constante: trocar a .gdb no
    # painel nao pode deixar a barra de progresso mentindo nem a leitura curta.
    tot = pyogrio.read_info(gdb, layer='SSDMT')['features']
    amp = collections.defaultdict(lambda: {'cnom': 0.0, 'cmax': 0.0, 'n': 0, 'km': 0.0})
    for skip in range(0, tot, passo):
        m, f, g, d = pyogrio.raw.read(gdb, layer='SSDMT',
                                      columns=['CTMT', 'TIP_CND', 'FAS_CON', 'COMP'],
                                      read_geometry=False, skip_features=skip,
                                      max_features=passo)
        cs = list(m['fields']); c = {x: d[cs.index(x)] for x in cs}
        comp = np.nan_to_num(c['COMP'].astype(float))
        for i in range(len(c['CTMT'])):
            k = c['CTMT'][i]
            if not k:
                continue
            a = amp[k]; a['n'] += 1; a['km'] += comp[i] / 1000.0
            fa = c['FAS_CON'][i] or ''
            if len([x for x in fa if x in 'ABC']) >= 3:
                cn, cm = seg.get(c['TIP_CND'][i], (0, 0))
                if cn > a['cnom']:
                    a['cnom'] = cn
                if cm > a['cmax']:
                    a['cmax'] = cm
        print(f'  {min(skip+passo,tot):,}/{tot:,} ({time.time()-t0:.0f}s)', flush=True)
    p = os.path.join(saida, 'amp_todos.json')
    json.dump({k: {'cnom': round(v['cnom'], 1), 'cmax': round(v['cmax'], 1),
                   'trechos': v['n'], 'km': round(v['km'], 2)}
               for k, v in amp.items()}, open(p, 'w'))
    print('ampacidade em', len(amp), 'alimentadores')
    print('saida:', p)


def _painel():
    import interativo
    v = interativo.formulario('extrai_ampacidade',
                              'Extrair a ampacidade dos alimentadores', [
        {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
         'padrao': interativo.bdgd_recente() or GDB,
         'dica': 'o File Geodatabase é uma PASTA terminada em .gdb'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Pasta de saída',
         'padrao': SAIDA, 'dica': 'recebe o amp_todos.json'},
        {'chave': 'passo', 'tipo': 'inteiro', 'rotulo': 'Trechos por fatia',
         'padrao': PASSO, 'minimo': 50000, 'maximo': 2000000,
         'dica': 'quanto se lê de cada vez; diminua se faltar memória'},
    ], ajuda='Cruza os 1,4 milhão de trechos de MT (SSDMT) com a tabela de '
             'condutores (SEGCON) e guarda, por alimentador, a capacidade do '
             'tronco trifásico de saída. Leva alguns minutos.')
    if not v:
        return False
    sys.argv += ['--gdb', v['gdb'], '--saida', v['saida'],
                 '--passo', str(v['passo'])]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--gdb', default=GDB, help='a BDGD (pasta .gdb)')
    ap.add_argument('--saida', default=SAIDA, help='onde gravar o JSON')
    ap.add_argument('--passo', type=int, default=PASSO,
                    help='trechos lidos por fatia')
    a = ap.parse_args()

    if not os.path.exists(a.gdb):
        raise SystemExit(f'BDGD nao encontrada: {a.gdb}')
    extrai(a.gdb, a.saida, a.passo)


if __name__ == '__main__':
    main()
