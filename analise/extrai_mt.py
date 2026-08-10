# -*- coding: utf-8 -*-
"""
EXTRACAO DA MEDIA TENSAO E DA GERACAO DISTRIBUIDA, POR ALIMENTADOR
==================================================================

    python analise/extrai_mt.py                       abre o painel e pergunta
    python analise/extrai_mt.py --gdb ..\\X.gdb --saida dados\\extraido_bdgd

Le a UCMT_tab inteira (energia mensal, DIC e demanda contratada de cada
unidade consumidora de media tensao) e as duas camadas de geracao distribuida
(UGBT_tab e UGMT_tab), e resume tudo por CTMT.

Sai `mt_todos.json` e `gd_todos.json` na pasta de saida — duas das seis
entradas do criticidade.py. Sao tabelas pequenas (16 mil e 33 mil registros),
entao a leitura e de uma vez so, sem fatiar.
"""
import argparse
import collections
import json
import os
import sys

import numpy as np
import pyogrio

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                 # a raiz do projeto, onde esta o interativo.py
sys.path.insert(0, RAIZ)

# A .gdb fica AO LADO do projeto, e a saida DENTRO dele. Tudo relativo a este
# arquivo, e nao ao diretorio de onde se chamou: o script roda igual sendo
# chamado da raiz (`python analise/extrai_mt.py`) ou de dentro da propria pasta.
GDB = os.path.normpath(os.path.join(RAIZ, os.pardir,
                                    'Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'))
SAIDA = os.path.join(RAIZ, 'dados', 'extraido_bdgd')


def le(gdb, lay, cols):
    """Camada inteira -> (coluna->array, numero de registros)."""
    m, f, g, d = pyogrio.raw.read(gdb, layer=lay, columns=cols,
                                  read_geometry=False)
    cs = list(m['fields'])
    return {c: d[cs.index(c)] for c in cs}, len(d[0])


def extrai(gdb, saida):
    os.makedirs(saida, exist_ok=True)
    # --- UCMT
    col, n = le(gdb, 'UCMT_tab',
                ['CTMT', 'TIP_CC', 'DEM_CONT']
                + [f'ENE_{m:02d}' for m in range(1, 13)]
                + [f'DIC_{m:02d}' for m in range(1, 13)])
    mt = collections.defaultdict(lambda: {'n': 0, 'ene': np.zeros(12),
                                          'dem': 0.0, 'dic': 0.0})
    ene = np.vstack([np.nan_to_num(col[f'ENE_{m:02d}'].astype(float)) for m in range(1, 13)])
    dic = np.nan_to_num(np.sum([col[f'DIC_{m:02d}'].astype(float) for m in range(1, 13)], axis=0))
    dem = np.nan_to_num(col['DEM_CONT'].astype(float))
    for i in range(n):
        k = col['CTMT'][i]
        if not k:
            continue
        a = mt[k]; a['n'] += 1; a['ene'] += ene[:, i]; a['dem'] += dem[i]; a['dic'] += dic[i]
    print('UCMT:', n, 'em', len(mt), 'alimentadores', flush=True)
    p_mt = os.path.join(saida, 'mt_todos.json')
    json.dump({k: {'n_uc': v['n'], 'ene': [round(x, 1) for x in v['ene']],
                   'dem_cont': round(v['dem'], 1), 'dic_total': round(v['dic'], 1)}
               for k, v in mt.items()}, open(p_mt, 'w'))
    # --- GD (UGBT + UGMT)
    gd = collections.defaultdict(lambda: {'n': 0, 'pot': 0.0})
    for lay in ['UGBT_tab', 'UGMT_tab']:
        try:
            c2, n2 = le(gdb, lay, ['CTMT', 'POT_INST'])
            p = np.nan_to_num(c2['POT_INST'].astype(float))
            for i in range(n2):
                k = c2['CTMT'][i]
                if k:
                    gd[k]['n'] += 1; gd[k]['pot'] += p[i]
            print(lay, n2, flush=True)
        except Exception as e:
            print(lay, 'ERRO', str(e)[:70], flush=True)
    p_gd = os.path.join(saida, 'gd_todos.json')
    json.dump({k: {'n': v['n'], 'kW': round(v['pot'], 1)} for k, v in gd.items()},
              open(p_gd, 'w'))
    print('GD em', len(gd), 'alimentadores')
    print('saida:', p_mt)
    print('       ', p_gd)


def _painel():
    import interativo
    v = interativo.formulario('extrai_mt', 'Extrair a MT e a GD da BDGD', [
        {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
         'padrao': interativo.bdgd_recente() or GDB,
         'dica': 'o File Geodatabase é uma PASTA terminada em .gdb'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Pasta de saída',
         'padrao': SAIDA,
         'dica': 'recebe o mt_todos.json e o gd_todos.json'},
    ], ajuda='Resume por alimentador a energia, o DIC e a demanda contratada '
             'das unidades de média tensão, e a potência instalada de geração '
             'distribuída. Leva menos de um minuto.')
    if not v:
        return False
    sys.argv += ['--gdb', v['gdb'], '--saida', v['saida']]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--gdb', default=GDB, help='a BDGD (pasta .gdb)')
    ap.add_argument('--saida', default=SAIDA, help='onde gravar os JSON')
    a = ap.parse_args()

    if not os.path.exists(a.gdb):
        raise SystemExit(f'BDGD nao encontrada: {a.gdb}')
    extrai(a.gdb, a.saida)


if __name__ == '__main__':
    main()
