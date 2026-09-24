# -*- coding: utf-8 -*-
"""Liga a subtransmissao solta as subestacoes, pela geometria — achado 74.

O CASO. Na Equatorial PA, os 22.037 trechos da SSDAT usam nos `A<numero>`
(A100275), e as chaves, transformadores e barras de AT usam
`<sigla>_<codigo>` (MON_490000059): zero no em comum. A rede de linhas fica
solta e o conversor, que guarda so as componentes que tocam transformador, a
descartava inteira. O censo das 99 (job 37060) achou 23 bases assim e 20
parciais — 42% da AT cadastrada do pais.

A REGRA. Cada PONTA de circuito (no de grau 1 da SSDAT) que nao e no de
subestacao procura, pela geometria, o equipamento de subestacao (UNSEAT ou
UNTRAT) mais proximo, ate `LIMITE_M`. Achado, liga-se a ponta a BARRA DAQUELA
SUBESTACAO NO MESMO NIVEL DE TENSAO DO CIRCUITO (`CTAT.TEN_NOM` =
`BAR.TEN_NOM`, o mesmo dominio TTEN). Sem barra no nivel, nao liga — uma
ponta de 138 kV perto de uma subestacao so de 69 kV e passagem, e nao chegada.

A ligacao e uma chave fechada VIRTUAL (`LIGAT_<n>`) acrescentada a UNSEAT em
memoria: componentes, patios, linhas, fontes e o MASTER tratam a rede como
ligada sem mudar uma linha deles. Cada elo sai no `_AT/ligacao_at.json`, com a
distancia e o circuito, e as pontas que ficaram soltas sao contadas.

O QUE NAO LIGA, e e dito: ponta longe de subestacao (consumidor de AT,
fronteira com outra distribuidora), ponta sem geometria, e ponta cujo nivel
nao existe na subestacao mais proxima.
"""
import collections
import json
import math
import struct

from .leitor import txt, no as _no_leitor
from .coordenadas import _pontas_wkb

# Na PA, 59% das pontas soltas estao a ate 200 m de uma subestacao e 65% a ate
# 500 m; acima disso o ganho e pequeno e o risco de ligar na subestacao errada
# cresce. O nivel de tensao igual e a segunda trava.
LIMITE_M = 500.0


def _no(x):
    """O MESMO nome de barra do conversor (`leitor.no`): minusculo e sem os
    caracteres que o OpenDSS nao aceita. Normalizar diferente aqui faria o elo
    apontar para uma barra que ninguem cria."""
    return _no_leitor(x)


def _ponto_wkb(b):
    """(x, y) de Point ou do 1o ponto de MultiPoint. None se nao der."""
    if b is None or len(b) < 21:
        return None
    try:
        end = '<' if b[0] == 1 else '>'
        tipo = struct.unpack_from(end + 'I', b, 1)[0] & 0xFF
        if tipo == 1:
            return struct.unpack_from(end + 'dd', b, 5)
        if tipo == 4:
            end2 = '<' if b[9] == 1 else '>'
            return struct.unpack_from(end2 + 'dd', b, 14)
    except Exception:                                              # noqa: BLE001
        return None
    return None


def metros(lon1, lat1, lon2, lat2):
    """Haversine, em metros. A BDGD vem em graus (SIRGAS 2000)."""
    r = 6371000.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _geometria(gdb, camada, cols):
    from pyogrio import raw
    try:
        meta, _fid, geom, dados = raw.read(gdb, layer=camada, columns=cols,
                                           read_geometry=True)
    except Exception:                                              # noqa: BLE001
        return None, None
    return dict(zip(meta['fields'], dados)), geom


def elos(gdb, dados, limite_m=LIMITE_M):
    """Os elos a acrescentar e o censo: `(lista de elos, censo)`.

    `dados` e o `subtransmissao.carregar` (SSDAT, UNSEAT, BAR, CTAT ja lidos);
    a geometria e lida aqui, da `gdb`, so das camadas que precisam.
    """
    censo = collections.Counter()
    s = dados['ssdat']
    if not len(s['COD_ID']):
        return [], dict(censo)

    # nos de subestacao: tudo que as chaves, os trafos e as barras de AT tocam
    est = set()
    u = dados['unseat']
    for k in range(len(u['COD_ID'])):
        est.add(_no(u['PAC_1'][k])); est.add(_no(u['PAC_2'][k]))
    t = dados['untrat']
    for k in range(len(t['COD_ID'])):
        est.add(_no(t['PAC_1'][k])); est.add(_no(t['PAC_2'][k]))
    bar = dados['bar']
    est |= {_no(x) for x in bar['PAC']}
    est.discard('')

    # o nivel de cada circuito, e o grau de cada no da SSDAT
    nivel_ct = {txt(c): txt(n) for c, n in zip(dados['ctat']['COD_ID'],
                                               dados['ctat']['TEN_NOM'])}
    grau = collections.Counter()
    nivel_no = {}
    for k in range(len(s['COD_ID'])):
        a, b = _no(s['PAC_1'][k]), _no(s['PAC_2'][k])
        if not a or not b or a == b:
            continue
        grau[a] += 1
        grau[b] += 1
        nv = nivel_ct.get(txt(s['CTAT'][k]), '')
        nivel_no.setdefault(a, nv)
        nivel_no.setdefault(b, nv)
    pontas = [n for n, g in grau.items() if g == 1 and n not in est]
    censo['pontas_soltas'] = len(pontas)
    if not pontas:
        return [], dict(censo)

    # geometria: pontas da SSDAT e pontos dos equipamentos de subestacao
    gs, gg = _geometria(gdb, 'SSDAT', ['PAC_1', 'PAC_2'])
    coord = {}
    if gs:
        for k in range(len(gs['PAC_1'])):
            p = _pontas_wkb(gg[k])
            if p:
                coord.setdefault(_no(gs['PAC_1'][k]), (p[0], p[1]))
                coord.setdefault(_no(gs['PAC_2'][k]), (p[2], p[3]))
    pts = []                                        # (x, y, SUB)
    for camada in ('UNSEAT', 'UNTRAT'):
        g, geo = _geometria(gdb, camada, ['SUB'])
        if not g:
            continue
        for k in range(len(g['SUB'])):
            p = _ponto_wkb(geo[k])
            sub = txt(g['SUB'][k])
            if p and sub:
                pts.append((p[0], p[1], sub))
    if not pts:
        censo['sem_geometria_de_subestacao'] = len(pontas)
        return [], dict(censo)

    # a barra de cada (subestacao, nivel): a mais ligada por chave
    uso = collections.Counter(_no(x) for x in list(u['PAC_1']) + list(u['PAC_2']))
    barra = {}
    for sub, nv, pac in zip(bar['SUB'], bar['TEN_NOM'], bar['PAC']):
        chave = (txt(sub), txt(nv))
        p = _no(pac)
        if p and (chave not in barra or uso[p] > uso[barra[chave]]):
            barra[chave] = p

    saida = []
    for n in pontas:
        c = coord.get(n)
        if not c:
            censo['sem_geometria'] += 1
            continue
        # vizinho mais proximo por forca bruta: as subestacoes sao centenas
        d_min, sub_min = None, None
        for x, y, sub in pts:
            if abs(x - c[0]) > 0.05 or abs(y - c[1]) > 0.05:    # ~5 km: corte
                continue
            d = metros(c[0], c[1], x, y)
            if d_min is None or d < d_min:
                d_min, sub_min = d, sub
        if d_min is None or d_min > limite_m:
            censo['longe_de_subestacao'] += 1
            continue
        alvo = barra.get((sub_min, nivel_no.get(n, '')))
        if not alvo:
            censo['sem_barra_no_nivel'] += 1
            continue
        saida.append({'ponta': n, 'barra': alvo, 'sub': sub_min,
                      'nivel': nivel_no.get(n, ''), 'metros': round(d_min, 1)})
    censo['ligadas'] = len(saida)
    return saida, dict(censo)


def aplicar(dados, lista):
    """Acrescenta os elos a `dados['unseat']` como chaves fechadas virtuais."""
    if not lista:
        return dados
    u = dados['unseat']
    novo = {k: list(v) for k, v in u.items()}
    for i, e in enumerate(lista, 1):
        novo['COD_ID'].append(f'LIGAT_{i}')
        novo['PAC_1'].append(e['ponta'])
        novo['PAC_2'].append(e['barra'])
        novo['FAS_CON'].append('ABC')
        novo['P_N_OPE'].append('F')
        novo['SUB'].append(e['sub'])
        novo['SIT_ATIV'].append('AT')
    dados['unseat'] = novo
    return dados


def gravar(caminho, lista, censo, limite_m=LIMITE_M):
    from . import escrita
    escrita.escreve(caminho, json.dumps(
        {'achado': 74, 'limite_m': limite_m, 'censo': censo, 'elos': lista},
        ensure_ascii=False, indent=1) + '\n')
