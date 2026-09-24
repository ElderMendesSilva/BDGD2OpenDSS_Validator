# -*- coding: utf-8 -*-
"""Quatro censos de BDGD antes da V40, uma linha por base. So le a BDGD.

    python diagnosticos/censo_v40.py --pasta ~/elder/bdgds_2025 --jobs 8 \\
        --saida-json medicoes/censo_v40.json

1. R1 DE PREENCHIMENTO (achado 76). O valor de R1 mais repetido da SEGCON,
   que fatia da tabela ele ocupa, o expoente do `linecodes._ajuste` e se a
   `linecodes.calibracao` dispara. A Cosern tem 2,179 ohm/km em 91% dos
   condutores, e o ajuste da propria base sai plano.

2. DECLARACAO DEGENERADA (achado 75). A perda declarada por alimentador
   (`PERD_A4` / energia da CTMT): mediana, e quantos ficam dentro do corte do
   `valida_perdas` (0,5% a 40%). Sem nenhum dentro, a comparacao por
   alimentador nao existe — e ate a V39 a ancora da ANEEL morria junto.

3. CODIGO REPETIDO ENTRE CHAVE E TRECHO. `COD_ID` da UNSEMT que tambem e
   `COD_ID` da SSDMT: os dois viram `Line.<cod>` e o OpenDSS recusa o
   segundo (#266). Duas subestacoes da Cosern nao compilaram por isso na V39.

4. PONTO ISOLADO ZERADO NA CURVA DE CARGA (achado 78). Quantas curvas da
   CRVCRG tem um ponto zerado entre dois positivos, e em que posicao. A
   Elektro tem POT_96 = 0 em todas, e 84 subestacoes perderam o passo 95.
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import statistics
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def uma(gdb):
    from bdgd2dss.leitor import BDGD, num, txt
    from bdgd2dss import linecodes
    import collections
    t0 = time.time()
    r = {'gdb': os.path.basename(gdb)}
    try:
        b = BDGD(gdb, verbose=False)
    except Exception as e:                                         # noqa: BLE001
        r['erro'] = f'{type(e).__name__}: {e}'[:200]
        return r

    # 1. SEGCON
    try:
        s = b.ler('SEGCON', ['R1', 'CNOM'])
        pares = [(num(x), num(c)) for x, c in zip(s['R1'], s['CNOM'])]
        val = [round(x, 4) for x, c in pares if x > 1e-4 and c > 0]
        aj = linecodes._ajuste(pares)
        cal, pre = linecodes.calibracao(pares)
        topo = collections.Counter(val).most_common(1)[0] if val else (None, 0)
        r['segcon'] = {'n': len(pares), 'r1_topo': topo[0],
                       'fatia_topo': round(topo[1] / len(val), 3) if val else None,
                       'expoente': round(aj[0], 3) if aj else None,
                       'preenchimento': pre,
                       'ajuste_usado': cal[2] if cal else None}
    except Exception as e:                                         # noqa: BLE001
        r['segcon'] = {'erro': f'{type(e).__name__}: {e}'[:200]}

    # 2. CTMT
    try:
        cols = ['COD_ID'] + [f'ENE_{i:02d}' for i in range(1, 13)] + ['PERD_A4']
        c = b.ler('CTMT', cols)
        pct = []
        for i in range(len(c['COD_ID'])):
            ene = sum(num(c[f'ENE_{k:02d}'][i]) for k in range(1, 13))
            if ene > 0:
                pct.append(100.0 * num(c['PERD_A4'][i]) / ene)
        dentro = sum(1 for p in pct if 0.5 <= p <= 40.0)
        r['ctmt'] = {'n': len(c['COD_ID']), 'com_energia': len(pct),
                     'mediana_pct': round(statistics.median(pct), 5) if pct else None,
                     'dentro_do_corte': dentro,
                     'zeradas': sum(1 for p in pct if p == 0)}
    except Exception as e:                                         # noqa: BLE001
        r['ctmt'] = {'erro': f'{type(e).__name__}: {e}'[:200]}

    # 3. UNSEMT x SSDMT
    try:
        ch = {txt(x).strip() for x in b.ler('UNSEMT', ['COD_ID'])['COD_ID']}
        tr = {txt(x).strip() for x in b.ler('SSDMT', ['COD_ID'])['COD_ID']}
        ch.discard(''); tr.discard('')
        rep = ch & tr
        r['nomes'] = {'chaves': len(ch), 'trechos': len(tr),
                      'repetidos': len(rep), 'exemplos': sorted(rep)[:5]}
    except Exception as e:                                         # noqa: BLE001
        r['nomes'] = {'erro': f'{type(e).__name__}: {e}'[:200]}

    # 4. CRVCRG
    try:
        from bdgd2dss import complementos
        cols = ['COD_ID'] + [f'POT_{k:02d}' for k in range(1, 97)]
        cv = b.ler('CRVCRG', cols)
        pos = collections.Counter()
        n_c = 0
        for i in range(len(cv['COD_ID'])):
            v = [num(cv[f'POT_{k:02d}'][i]) for k in range(1, 97)]
            novo, feitos = complementos.completar(v)
            if feitos:
                n_c += 1
                for k in range(96):
                    if novo[k] != v[k]:
                        pos[k + 1] += 1
        r['curvas'] = {'n': len(cv['COD_ID']), 'com_zero_isolado': n_c,
                       'posicoes': dict(pos.most_common(5))}
    except Exception as e:                                         # noqa: BLE001
        r['curvas'] = {'erro': f'{type(e).__name__}: {e}'[:200]}

    r['segundos'] = round(time.time() - t0, 1)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pasta', required=True)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--saida-json', required=True)
    a = ap.parse_args(argv)
    gdbs = sorted(glob.glob(os.path.join(os.path.expanduser(a.pasta), '*.gdb')))
    print(f'{len(gdbs)} bases', flush=True)
    res = []
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for r in ex.map(uma, gdbs):
            res.append(r)
            sg, ct, nm = r.get('segcon') or {}, r.get('ctmt') or {}, r.get('nomes') or {}
            cv = r.get('curvas') or {}
            print(f'  {r["gdb"][:34]:34s} R1topo={sg.get("r1_topo")} '
                  f'({sg.get("fatia_topo")}) exp={sg.get("expoente")} '
                  f'PREENCH={sg.get("preenchimento")} | decl med='
                  f'{ct.get("mediana_pct")}% dentro={ct.get("dentro_do_corte")}/'
                  f'{ct.get("com_energia")} | repetidos={nm.get("repetidos")} '
                  f'| zero isolado={cv.get("com_zero_isolado")}/{cv.get("n")} '
                  f'{r.get("erro", "")}', flush=True)
            with open(a.saida_json, 'w', encoding='utf-8') as fh:
                json.dump({'bases': res}, fh, ensure_ascii=False, indent=1)
    print(f'-> {a.saida_json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
