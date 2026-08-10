# -*- coding: utf-8 -*-
"""
COORDENADAS DAS BARRAS — o arquivo BusCoords do OpenDSS.

A BDGD e uma base geografica: SSDAT, SSDMT e SSDBT sao camadas de linha em
SIRGAS 2000 (EPSG:4674). O primeiro vertice de cada trecho e o PAC_1 e o
ultimo e o PAC_2, entao da para extrair a posicao de cada barra sem nenhuma
tabela auxiliar.

Com o BusCoords carregado, valem no OpenDSS:

    Plot Circuit  Power  max=2000  dots=n  labels=n  C1=Blue
    Plot Circuit  Voltage
    Plot profile phases=all

e, do lado do Python, qualquer desenho em coordenadas reais.

O WKB e lido aqui na mao (struct) para nao acrescentar shapely/geopandas
como dependencia — sao ~30 linhas e so precisamos do primeiro e do ultimo
ponto de cada geometria.
"""
import struct

from .leitor import txt


def _pontas_wkb(b):
    """(x0, y0, x1, y1) do primeiro e do ultimo vertice. None se nao der."""
    if not b or len(b) < 9:
        return None
    try:
        end = '<' if b[0] == 1 else '>'
        tipo = struct.unpack_from(end + 'I', b, 1)[0] & 0xFF
        p = 5
        if tipo == 5:                      # MultiLineString: pega a 1a parte
            n = struct.unpack_from(end + 'I', b, p)[0]
            if n < 1:
                return None
            p += 4
            end = '<' if b[p] == 1 else '>'
            tipo = struct.unpack_from(end + 'I', b, p + 1)[0] & 0xFF
            p += 5
        if tipo != 2:                      # so LineString interessa
            return None
        npt = struct.unpack_from(end + 'I', b, p)[0]
        if npt < 2:
            return None
        p += 4
        x0, y0 = struct.unpack_from(end + 'dd', b, p)
        fim = p + (npt - 1) * 16
        x1, y1 = struct.unpack_from(end + 'dd', b, fim)
        return x0, y0, x1, y1
    except Exception:
        return None


def coletar(bdgd, camada, ctmts=None, coords=None, chave='CTMT'):
    """Acumula {barra: (x, y)} lendo a geometria de uma camada de linha."""
    coords = {} if coords is None else coords
    import pyogrio
    cols = ['COD_ID', 'PAC_1', 'PAC_2']
    where = None
    if ctmts:
        lista = ','.join("'" + str(v).replace("'", "''") + "'" for v in ctmts if v)
        if lista:
            cols = cols + [chave]
            where = f'{chave} IN ({lista})'
    try:
        r = pyogrio.raw.read(bdgd.gdb, layer=camada, columns=cols,
                             read_geometry=True, where=where)
    except Exception:
        return coords
    meta, _, geom, data = r
    cs = list(meta['fields'])
    col = {c: data[cs.index(c)] for c in cs}
    if geom is None:
        return coords
    for i in range(len(geom)):
        pt = _pontas_wkb(geom[i])
        if not pt:
            continue
        b1 = txt(col['PAC_1'][i]).strip().lower()
        b2 = txt(col['PAC_2'][i]).strip().lower()
        if b1 and b1 not in coords:
            coords[b1] = (pt[0], pt[1])
        if b2 and b2 not in coords:
            coords[b2] = (pt[2], pt[3])
    return coords


def escrever(coords, caminho, extras=None):
    """BusCoords no formato do OpenDSS: barra, x, y (uma por linha).

    `extras` permite posicionar barras que nao existem na geometria — as
    barras de AT das subestacoes, por exemplo, que sao nos criados por nos.
    """
    linhas = []
    for b, (x, y) in coords.items():
        linhas.append(f'{b}, {x:.8f}, {y:.8f}')
    for b, (x, y) in (extras or {}).items():
        if b not in coords:
            linhas.append(f'{b}, {x:.8f}, {y:.8f}')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(linhas) + '\n')
    return len(linhas)


def centroide(coords, nos):
    """Posicao media de um conjunto de barras — serve para colocar a barra
    de AT de uma subestacao no meio do seu patio."""
    p = [coords[n] for n in nos if n in coords]
    if not p:
        return None
    return (sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p))
