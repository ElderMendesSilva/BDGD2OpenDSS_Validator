# -*- coding: utf-8 -*-
"""A AT ligada (achado 74, `--ligar-at`) contra a rodada de referencia, base a base.

    python diagnosticos/teste_at_ligada.py --bases ~/elder/bdgds_2025 \\
        --censo medicoes/at_2025.json --ref V39 --sufixo ATT --jobs 16 \\
        --saida-json medicoes/teste_at_ligada.json

Para cada base que o censo (`diagnosticos/at_desconexa.py`) deu como
`desligada` ou `parcial`: converte com `--ligar-at` em
`MODELOS_<TAG>_<sufixo>/` e compara o MASTER-AT e o MASTER-GERAL com os da
rodada `--ref`. Converge? Tensao minima e mediana? Perda? Quantos trechos de
AT? Algum laco incoerente (achado 70)?

POR QUE ANTES DE LIGAR POR PADRAO. No primeiro teste, tres subestacoes da
Equatorial PA, a ligacao colapsou o MASTER-GERAL (73,7% de perda, 0,68 pu).
As tres causas foram corrigidas e o mesmo recorte ficou sao — mas tres
subestacoes de uma base nao dizem nada sobre as outras 42.

O modelo por subestacao nao muda com a ligacao; o teste nao o compara.
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def _tags(raiz, ref):
    """{nome da .gdb: tag de rodada}, lido do `relatorio_rede.json` de cada
    pasta da rodada de referencia — o nome exato, e nao o codigo."""
    out = {}
    for pasta in glob.glob(os.path.join(raiz, f'MODELOS_*_{ref}')):
        try:
            with open(os.path.join(pasta, 'relatorio_rede.json'), encoding='utf-8') as fh:
                g = json.load(fh).get('gdb')
        except Exception:                                          # noqa: BLE001
            continue
        if g:
            out[os.path.basename(g)] = os.path.basename(pasta)[len('MODELOS_'):-len(ref) - 1]
    return out


def medir(master):
    """Compila e resolve um MASTER; devolve as metricas ou o erro."""
    from bdgd2dss import lacos
    import opendssdirect as dss
    if not os.path.exists(master):
        return {'erro': 'sem arquivo'}
    try:
        aviso = lacos.compilar(dss, master)
        p = -dss.Circuit.TotalPower()[0]
        perda = dss.Circuit.Losses()[0] / 1000.0
        vs = sorted(v for v in dss.Circuit.AllBusMagPu() if v > 1e-3)
        n_at = sum(1 for e in dss.Circuit.AllElementNames()
                   if e.lower().startswith('line.at_'))
        inc = [x for x in lacos.lacos(dss, set()) if lacos.incoerente(x)]
        return {'converge': bool(dss.Solution.Converged()) and not aviso,
                'fonte_kw': round(p, 1), 'perda_kw': round(perda, 1),
                'v_min': round(vs[0], 4) if vs else None,
                'v_mediana': round(vs[len(vs) // 2], 4) if vs else None,
                'nos': len(vs), 'trechos_at': n_at,
                'lacos_incoerentes': len(inc)}
    except Exception as e:                                         # noqa: BLE001
        return {'erro': f'{type(e).__name__}: {str(e)[:160]}'}


def uma(args):
    gdb, tag, raiz, ref, suf = args
    t0 = time.time()
    saida = os.path.join(raiz, f'MODELOS_{tag}_{suf}')
    r = {'tag': tag, 'gdb': os.path.basename(gdb)}
    p = subprocess.run([sys.executable, '-u',
                        os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                        '--saida', saida, '--ligar-at', '--refazer'],
                       cwd=RAIZ, capture_output=True, text=True)
    r['converter_rc'] = p.returncode
    m = re.search(r'ACHADO 74: (\d+) de (\d+) pontas', p.stdout)
    if m:
        r['elos'], r['pontas_soltas'] = int(m.group(1)), int(m.group(2))
    r['min_converter'] = round((time.time() - t0) / 60, 1)
    if p.returncode != 0:
        r['erro'] = p.stderr[-400:]
        return r
    for nome in ('MASTER-AT.dss', 'MASTER-GERAL.dss'):
        chave = nome.split('.')[0].lower().replace('master-', '')
        r[chave] = {'ligada': medir(os.path.join(saida, nome)),
                    'ref': medir(os.path.join(raiz, f'MODELOS_{tag}_{ref}', nome))}
    r['minutos'] = round((time.time() - t0) / 60, 1)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', required=True, help='pasta das .gdb')
    ap.add_argument('--censo', required=True, help='saida do at_desconexa')
    ap.add_argument('--raiz', default='.')
    ap.add_argument('--ref', default='V39')
    ap.add_argument('--sufixo', default='ATT')
    ap.add_argument('--so', default='', help='gdb (inicio do nome) separados por espaco')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--saida-json', required=True)
    a = ap.parse_args(argv)

    with open(a.censo, encoding='utf-8') as fh:
        censo = json.load(fh)['bases']
    alvo = [c for c in censo if c.get('estado') in ('desligada', 'parcial')]
    if a.so:
        filtros = a.so.split()
        alvo = [c for c in alvo if any(c['gdb'].startswith(f) for f in filtros)]
    tarefas = []
    tags = _tags(a.raiz, a.ref)
    for c in alvo:
        gdb = os.path.join(os.path.expanduser(a.bases), c['gdb'])
        tag = tags.get(c['gdb'])
        if not tag:
            print(f'  sem rodada {a.ref} para {c["gdb"]}: pulada', flush=True)
            continue
        tarefas.append((gdb, tag, a.raiz, a.ref, a.sufixo))
    print(f'{len(tarefas)} base(s) com a AT desligada ou parcial', flush=True)

    res = []
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for r in ex.map(uma, tarefas):
            res.append(r)
            at = (r.get('at') or {}).get('ligada') or {}
            print(f'  {r["tag"]:20s} elos {r.get("elos", "-")}/{r.get("pontas_soltas", "-")} '
                  f'AT conv={at.get("converge")} Vmin={at.get("v_min")} '
                  f'inc={at.get("lacos_incoerentes")} {r.get("erro", "")[:80]}', flush=True)
            with open(a.saida_json, 'w', encoding='utf-8') as fh:
                json.dump({'ref': a.ref, 'bases': res}, fh, ensure_ascii=False, indent=1)
    print(f'-> {a.saida_json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
