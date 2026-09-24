# -*- coding: utf-8 -*-
"""A subtransmissao de cada base: existe, liga nas subestacoes, e se nao liga,
a que distancia fica delas.

    python diagnosticos/at_desconexa.py --pasta ~/elder/bdgds_2025 --jobs 8 \\
        --saida-json medicoes/at_2025.json

POR QUE A PERGUNTA. Na V39 a Equatorial PA saiu com 0 trechos de AT e 96
fontes equivalentes, e a BDGD dela tem 22.037 trechos na SSDAT. Os nos da
SSDAT e da CTAT sao `A<numero>` (A100275); os das chaves, transformadores e
barras de AT sao `<sigla>_<codigo>` (MON_490000059) — 22.204 nos, ZERO em
comum. A rede de linhas fica solta, o conversor guarda so o que toca
transformador, e a perda de subtransmissao some do modelo. Na mesma V39,
CPFL, as quatro Equatoriais, Light, Enel RJ e quatro Neoenergias tambem
sairam com 0 trechos de AT e dezenas de equivalentes.

O QUE ELE MEDE, por base:

- quantos trechos a SSDAT tem, e quantos nos dela sao nos de subestacao
  (UNSEAT, UNTRAT, BAR): `ligada`, `parcial`, `desligada` ou `sem_ssdat`;
- se o no inicial da CTAT esta no sistema da SSDAT ou no das subestacoes;
- para a rede desligada, a distancia de cada PONTA de circuito (no de grau 1
  da SSDAT) ao equipamento de subestacao mais proximo, pela geometria — que e
  o que diz se ligar pela geometria e viavel.

So le a BDGD; e calculo sobre as 99, entao no cluster e job.
"""
import argparse
import collections
import glob
import json
import math
import os
import struct
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import leitor                                   # noqa: E402
from bdgd2dss.coordenadas import _pontas_wkb                  # noqa: E402

LIGADA = 0.5          # mais da metade das pontas em no de subestacao
LIMIARES_M = (50, 200, 500, 2000)


def _no(x):
    return leitor.txt(x).strip().upper()


def _ponto_wkb(b):
    """(x, y) de Point, ou o 1o ponto de MultiPoint/LineString. None se nao der."""
    if not b or len(b) < 21:
        return None
    try:
        end = '<' if b[0] == 1 else '>'
        tipo = struct.unpack_from(end + 'I', b, 1)[0] & 0xFF
        if tipo == 1:
            return struct.unpack_from(end + 'dd', b, 5)
        if tipo == 4:                                  # MultiPoint
            end2 = '<' if b[9] == 1 else '>'
            return struct.unpack_from(end2 + 'dd', b, 9 + 5)
        p = _pontas_wkb(b)
        return (p[0], p[1]) if p else None
    except Exception:                                              # noqa: BLE001
        return None


def _metros(lon1, lat1, lon2, lat2):
    """Haversine, em metros. A BDGD vem em graus (SIRGAS 2000)."""
    r = 6371000.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _ler(gdb, camada, cols, geometria=False):
    from pyogrio import raw
    try:
        meta, _fid, geom, dados = raw.read(gdb, layer=camada, columns=cols,
                                           read_geometry=geometria)
    except Exception:                                              # noqa: BLE001
        return None, None
    return dict(zip(meta['fields'], dados)), geom


def uma(gdb):
    t0 = time.time()
    r = {'gdb': os.path.basename(gdb)}
    try:
        s, gs = _ler(gdb, 'SSDAT', ['PAC_1', 'PAC_2', 'CTAT', 'COMP'], True)
        n_s = len(s['PAC_1']) if s else 0
        r['ssdat'] = n_s
        est_nos, est_pts = set(), []
        for camada in ('UNSEAT', 'UNTRAT'):
            d, g = _ler(gdb, camada, ['PAC_1', 'PAC_2'], True)
            if not d:
                continue
            r[camada.lower()] = len(d['PAC_1'])
            for k in range(len(d['PAC_1'])):
                est_nos.add(_no(d['PAC_1'][k]))
                est_nos.add(_no(d['PAC_2'][k]))
                p = _ponto_wkb(g[k]) if g is not None else None
                if p:
                    est_pts.append(p)
        d, _g = _ler(gdb, 'BAR', ['PAC'])
        if d:
            r['bar'] = len(d['PAC'])
            est_nos |= {_no(x) for x in d['PAC']}
        est_nos.discard('')
        if not n_s:
            r['estado'] = 'sem_ssdat'
            return r

        grau = collections.Counter()
        coord = {}
        for k in range(n_s):
            a, b = _no(s['PAC_1'][k]), _no(s['PAC_2'][k])
            if not a or not b or a == b:
                continue
            grau[a] += 1
            grau[b] += 1
            p = _pontas_wkb(gs[k]) if gs is not None else None
            if p:
                coord.setdefault(a, (p[0], p[1]))
                coord.setdefault(b, (p[2], p[3]))
        nos = set(grau)
        pontas = [n for n, g in grau.items() if g == 1]
        comum = nos & est_nos
        pontas_em_est = sum(1 for n in pontas if n in est_nos)
        r.update({'nos_ssdat': len(nos), 'nos_em_comum': len(comum),
                  'pontas': len(pontas), 'pontas_em_subestacao': pontas_em_est})
        c, _g = _ler(gdb, 'CTAT', ['PAC_INI'])
        if c:
            pi = [_no(x) for x in c['PAC_INI']]
            r['ctat'] = len(pi)
            r['ctat_ini_na_ssdat'] = sum(1 for x in pi if x in nos)
            r['ctat_ini_em_subestacao'] = sum(1 for x in pi if x in est_nos)
        frac = pontas_em_est / len(pontas) if pontas else 0.0
        r['estado'] = ('ligada' if frac >= LIGADA else
                       'parcial' if comum else 'desligada')

        # A GEOMETRIA: distancia de cada ponta ao equipamento de SE mais
        # proximo. So para as pontas que nao caem em no de subestacao.
        soltas = [coord[n] for n in pontas if n not in est_nos and n in coord]
        r['pontas_soltas_com_geometria'] = len(soltas)
        r['pontos_de_subestacao'] = len(est_pts)
        if soltas and est_pts:
            ds = []
            for (x, y) in soltas:
                ds.append(min(_metros(x, y, ex, ey) for ex, ey in est_pts))
            ds.sort()
            q = lambda f: round(ds[min(len(ds) - 1, int(f * len(ds)))], 1)  # noqa: E731
            r['distancia_m'] = {'p10': q(0.10), 'mediana': q(0.5), 'p90': q(0.9)}
            r['pontas_ate_m'] = {str(m): round(100 * sum(1 for d_ in ds if d_ <= m) / len(ds), 1)
                                 for m in LIMIARES_M}
    except Exception as e:                                         # noqa: BLE001
        r['erro'] = f'{type(e).__name__}: {str(e)[:200]}'
    finally:
        r['segundos'] = round(time.time() - t0, 1)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('gdbs', nargs='*')
    ap.add_argument('--pasta')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--saida-json')
    a = ap.parse_args(argv)
    gdbs = list(a.gdbs)
    if a.pasta:
        gdbs += sorted(glob.glob(os.path.join(os.path.expanduser(a.pasta), '*.gdb')))
    if not gdbs:
        ap.error('nenhuma .gdb')
    print(f'{len(gdbs)} base(s)', flush=True)
    if a.jobs > 1 and len(gdbs) > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = list(ex.map(uma, gdbs))
    else:
        res = [uma(g) for g in gdbs]
    print(f'\n{"base":40s} {"estado":10s} {"SSDAT":>7s} {"comum":>6s} {"pontas":>7s} '
          f'{"em SE":>6s} {"<=200m":>7s} {"<=500m":>7s} {"mediana m":>10s}')
    cont = collections.Counter()
    for r in res:
        if r.get('erro'):
            print(f'{r["gdb"][:40]:40s} ERRO {r["erro"]}')
            continue
        cont[r['estado']] += 1
        pa = r.get('pontas_ate_m') or {}
        print(f'{r["gdb"][:40]:40s} {r["estado"]:10s} {r.get("ssdat", 0):7d} '
              f'{r.get("nos_em_comum", 0):6d} {r.get("pontas", 0):7d} '
              f'{r.get("pontas_em_subestacao", 0):6d} {pa.get("200", 0):7.1f} '
              f'{pa.get("500", 0):7.1f} {(r.get("distancia_m") or {}).get("mediana", 0):10.1f}')
    print(f'\nPAIS: {dict(cont)}')
    if a.saida_json:
        os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
        with open(a.saida_json, 'w', encoding='utf-8') as fh:
            json.dump({'bases': res, 'estados': dict(cont)}, fh, ensure_ascii=False, indent=1)
        print(f'-> {a.saida_json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
