# -*- coding: utf-8 -*-
"""Ramais de ligacao e medidores pelo Modulo 7 do PRODIST, por base.

    python etapas/modulo7.py <base.gdb> [<base.gdb> ...] --saida-json medicoes/modulo7_2025.json
    python etapas/modulo7.py --pasta ~/elder/bdgds_2025 --jobs 16 --saida-json ...

Os dois segmentos que a referencia da ANEEL soma e o modelo com BT agregada
nao tem. Le so a BDGD — nao precisa de modelo convertido — e devolve, por
base, a perda anual em MWh e em percentual da energia injetada nos
alimentadores (soma de `CTMT.ENE_01..12`). Ver `bdgd2dss/modulo7.py` para as
regras e as premissas.

Medido na FORCEL83 em 22/09/2026: medidores 110 MWh (piso 78, teto 156),
ramais 38 MWh, 0,18% da energia injetada — contra 3,78% de perda tecnica da
referencia. E calculo sobre a base inteira, entao no cluster e job.
"""
import argparse
import glob
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import leitor, modulo7                              # noqa: E402


def uma(gdb, ano):
    t0 = time.time()
    try:
        b = leitor.BDGD(gdb, verbose=False)
        med = modulo7.perda_medidores(b, ano)
        ram, censo = modulo7.perda_ramais(b, ano)
        # O DENOMINADOR NAO PODE SER SO A CTMT. Na primeira medida nacional
        # (22/09/2026) as cooperativas deram ramal em 918% e medidor em 300%
        # da "energia injetada": a soma de `CTMT.ENE` nelas e quase zero,
        # enquanto as unidades consumidoras declaram energia. Vale a MAIOR
        # entre a energia dos alimentadores e a fornecida as unidades, e o
        # arquivo diz qual foi usada.
        ct = b.ler('CTMT', ['COD_ID'] + [f'ENE_{m:02d}' for m in range(1, 13)])
        inj_ctmt = sum(leitor.num(ct[f'ENE_{m:02d}'][i])
                       for i in range(len(ct['COD_ID'])) for m in range(1, 13)) / 1000.0
        forn = 0.0
        for tab in ('UCBT_tab', 'UCMT_tab', 'UCAT_tab'):
            try:
                u = b.ler(tab, [f'ENE_{m:02d}' for m in range(1, 13)])
            except Exception:                                        # noqa: BLE001
                continue
            forn += sum(leitor.num(x) for m in range(1, 13)
                        for x in u[f'ENE_{m:02d}']) / 1000.0
        inj = max(inj_ctmt, forn)
    except Exception as e:                                           # noqa: BLE001
        return {'gdb': os.path.basename(gdb), 'erro': f'{type(e).__name__}: {str(e)[:200]}'}
    m = {k: sum(v[k] for v in med.values()) for k in ('provavel', 'teto', 'piso', 'n', 'sem_tipo')}
    r = sum(ram.values())

    def pct(x):
        return round(100 * x / inj, 4) if inj > 0 else None

    dist = re.search(r'_(\d+)_\d{4}-\d{2}-\d{2}', os.path.basename(gdb))
    return {'gdb': os.path.basename(gdb), 'dist': dist.group(1) if dist else None,
            'energia_injetada_mwh': round(inj, 1),
            'energia_ctmt_mwh': round(inj_ctmt, 1),
            'energia_fornecida_mwh': round(forn, 1),
            'denominador': 'CTMT' if inj_ctmt >= forn else 'unidades',
            'unidades_bt': m['n'], 'medidores_sem_tipo': m['sem_tipo'],
            'medidores_mwh': {k: round(m[k], 2) for k in ('provavel', 'piso', 'teto')},
            'ramais_mwh': round(r, 2), 'ramais_censo': censo,
            # achado 73: ramais acima de 2x a ampacidade, fora da soma
            'ramais_implausiveis_mwh': censo.get('mwh_implausivel', 0.0),
            'pct': {'medidores': pct(m['provavel']), 'ramais': pct(r),
                    'soma': pct(m['provavel'] + r),
                    'soma_teto': pct(m['teto'] + r), 'soma_piso': pct(m['piso'] + r)},
            'segundos': round(time.time() - t0, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('gdbs', nargs='*')
    ap.add_argument('--pasta', help='todas as .gdb desta pasta')
    ap.add_argument('--ano', type=int, default=2025)
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--saida-json')
    a = ap.parse_args(argv)
    gdbs = list(a.gdbs)
    if a.pasta:
        gdbs += sorted(glob.glob(os.path.join(os.path.expanduser(a.pasta), '*.gdb')))
    if not gdbs:
        ap.error('nenhuma .gdb')
    print(f'{len(gdbs)} base(s), ano {a.ano}', flush=True)
    if a.jobs > 1 and len(gdbs) > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = list(ex.map(uma, gdbs, [a.ano] * len(gdbs)))
    else:
        res = [uma(g, a.ano) for g in gdbs]
    print(f'\n{"base":44s} {"inj GWh":>9s} {"medid %":>8s} {"ramais %":>9s} {"soma %":>7s}')
    for r in res:
        if r.get('erro'):
            print(f'{r["gdb"][:44]:44s} ERRO {r["erro"]}')
            continue
        p = r['pct']
        print(f'{r["gdb"][:44]:44s} {r["energia_injetada_mwh"]/1000:9.1f} '
              f'{p["medidores"] or 0:8.3f} {p["ramais"] or 0:9.3f} {p["soma"] or 0:7.3f}')
    if a.saida_json:
        os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
        with open(a.saida_json, 'w', encoding='utf-8') as fh:
            json.dump({'ano': a.ano, 'bases': res}, fh, ensure_ascii=False, indent=1)
        print(f'-> {a.saida_json}')
    return 0 if any(not r.get('erro') for r in res) else 1


if __name__ == '__main__':
    sys.exit(main())
