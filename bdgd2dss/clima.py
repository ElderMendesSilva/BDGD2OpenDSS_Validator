# -*- coding: utf-8 -*-
from . import escrita
"""
CLIMA DA REGIAO DA PROPRIA BASE — irradiancia e temperatura por coordenada.
==========================================================================

    python -m bdgd2dss.clima <caminho.gdb> --mes 1

POR QUE ESTE MODULO EXISTE
--------------------------
Achado 4. O conversor recebia uma pasta de dados MEDIDOS de Sao Paulo e a
aplicava a qualquer base sem uma palavra. Roraima foi convertida com a
irradiancia e a temperatura de Sao Paulo.

Medido em 11/08/2026, com o centroide que a propria BDGD fornece:

    base              lon      lat    kWh/m2/dia   temperatura
    Enel SP        -46,65   -23,57       5,36      15,5 a 35,7 C
    Roraima        -60,70    +2,77       5,62      25,1 a 40,9 C
    Equatorial PA  -49,35    -2,77       5,12      22,9 a 33,8 C
    CPFL interior  -48,11   -21,60       6,28      16,0 a 37,2 C

E O ERRO NAO ESTAVA ONDE EU PROCURAVA. A irradiancia de Roraima e apenas 5%
maior que a de Sao Paulo — janeiro e estacao chuvosa perto do equador. O que
estava grosseiramente errado era a TEMPERATURA: o conversor aplicava
"19,3 a 26,1 C" numa regiao cuja MINIMA e 25,1 C. Temperatura de celula
comanda o derating do painel, entao a geracao de Roraima saia fria demais,
logo eficiente demais.

Dois subprodutos da medicao, os dois uteis:

  * A CPFL Paulista, do interior de Sao Paulo, e 17% mais ensolarada que a
    capital (6,28 contra 5,36 kWh/m2/dia). Usar o clima da capital nela NAO
    e aproximacao inofensiva — foi o que decidiu nao usar `--clima-forcar`
    na regeracao.

  * O arquivo medido de Sao Paulo declara 6,22 kWh/m2/dia, e o
    `complementos.carregar_clima` ja registrava a suspeita de que isso fosse
    ~10% acima da faixa tipica (5,0 a 5,8). A NASA POWER da 5,36, DENTRO da
    faixa. Duas fontes independentes apontando para o mesmo lado.

A FONTE, E O QUE ELA NAO E
--------------------------
NASA POWER (`power.larc.nasa.gov`): gratuita, sem cadastro nem chave, global,
horaria desde 1981, resolucao de 0,5 x 0,625 grau. Acessada com `urllib` da
biblioteca padrao — nenhuma dependencia nova entra no projeto por isso.

E dado de SATELITE E REANALISE, nao medicao de solo. Isso tem de ser dito no
artigo. E incomparavelmente melhor que aplicar Sao Paulo em Roraima, e ainda
assim nao e estacao meteorologica. As referencias para validar sao o Atlas
Brasileiro de Energia Solar (INPE/LABREN), que e a referencia nacional mas
nao tem API, e as estacoes do INMET, que medem radiacao global no solo.

A REDE NUNCA E TOCADA DURANTE A CONVERSAO
-----------------------------------------
Baixar e um passo EXPLICITO e separado, que grava um cache em disco. A
conversao le o cache. Sem isso, um modelo deixaria de ser reproduzivel offline
e passaria a depender de um servico externo continuar no ar — o oposto da
premissa do projeto, que e cuspir a rede a partir da BDGD.

O cache carrega a procedencia: fonte, URL, coordenada, periodo e a data em que
foi baixado. Um modelo cujo clima nao se sabe de onde veio nao serve para
artigo nenhum.
"""
import argparse
import json
import os
import time
import urllib.request

# Modelo NOCT, o MESMO do `complementos.carregar_clima`. Repetir a constante
# seria criar duas verdades; ela fica aqui com o nome explicito e o outro
# modulo continua com a sua, porque sao caminhos independentes que precisam
# dar o mesmo numero — e ha teste conferindo que dao.
NOCT_A, NOCT_REF, NOCT_G = 45.0, 20.0, 800.0

PASSOS = 96                      # o passo da CRVCRG, 15 min
FONTE = 'NASA POWER (ALLSKY_SFC_SW_DWN, T2M) — satelite/reanalise'
URL = ('https://power.larc.nasa.gov/api/temporal/hourly/point'
       '?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE'
       '&longitude={lon:.4f}&latitude={lat:.4f}'
       '&start={ini}&end={fim}&format=JSON')

FALTANTE = -900.0                # a NASA POWER marca ausencia com -999


# ====================================================================== onde
def centroide(bdgd, camadas=('SSDAT', 'SSDMT'), limite=20000):
    """(lon, lat) da rede, pela MEDIANA dos vertices — nao pela media.

    A mediana e deliberada: uma base com um ponto solto no oceano, ou com
    coordenada zerada em alguns registros, desloca a media e nao a mediana.

    A BDGD e SIRGAS 2000 (EPSG:4674), que e GEOGRAFICO — os valores ja sao
    grau decimal, sem reprojecao. Conferido nas sete bases: todos os
    centroides caem onde a concessao de fato opera.
    """
    from . import coordenadas
    co = {}
    for c in camadas:
        try:
            co = coordenadas.coletar(bdgd, c, coords=co)
        except Exception:
            pass
        if len(co) >= limite:
            break
    if not co:
        return None
    xs = sorted(x for x, _ in co.values())
    ys = sorted(y for _, y in co.values())
    lon, lat = xs[len(xs) // 2], ys[len(ys) // 2]
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return round(lon, 4), round(lat, 4)


# =================================================================== formato
def para_96(horario):
    """24 valores horarios -> 96 de 15 min, por interpolacao linear circular.

    Circular porque o dia fecha: o passo entre 23h e 0h existe. Sem isso
    aparecia um degrau a meia-noite que, em irradiancia, nao incomoda (e
    zero dos dois lados), mas em temperatura sim.
    """
    if not horario:
        return [0.0] * PASSOS
    n = len(horario)
    out = []
    for k in range(PASSOS):
        pos = k * n / PASSOS
        i = int(pos)
        f = pos - i
        a = horario[i % n]
        b = horario[(i + 1) % n]
        out.append(a + (b - a) * f)
    return out


def celula(irr_kw, amb_c):
    """Temperatura de celula pelo modelo NOCT, a partir da ambiente."""
    return [round(a + (NOCT_A - NOCT_REF) / NOCT_G * (g * 1000.0), 2)
            for g, a in zip(irr_kw, amb_c)]


def _media_por_hora(serie):
    """{AAAAMMDDHH: valor} -> 24 medias, uma por hora do dia."""
    acc = {}
    for k, v in (serie or {}).items():
        if v is None or v <= FALTANTE:
            continue
        acc.setdefault(k[-2:], []).append(float(v))
    if not acc:
        return []
    return [sum(acc[f'{h:02d}']) / len(acc[f'{h:02d}']) if f'{h:02d}' in acc
            else 0.0 for h in range(24)]


# ==================================================================== baixar
def baixar(lon, lat, mes=1, ano=2024, timeout=90, url=URL, abrir=None):
    """Perfil medio do mes naquele ponto. Devolve o dicionario do cache.

    `abrir` existe para o teste: qualquer coisa que devolva o JSON serve, e
    a suite nao precisa de rede.
    """
    dias = [31, 29 if ano % 4 == 0 and (ano % 100 or not ano % 400) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    ini = f'{ano}{mes:02d}01'
    fim = f'{ano}{mes:02d}{dias:02d}'
    alvo = url.format(lon=lon, lat=lat, ini=ini, fim=fim)
    if abrir is None:
        def abrir(u):
            with urllib.request.urlopen(u, timeout=timeout) as r:
                return json.load(r)
    d = abrir(alvo)
    p = (d.get('properties') or {}).get('parameter') or {}
    ghi = _media_por_hora(p.get('ALLSKY_SFC_SW_DWN'))
    amb = _media_por_hora(p.get('T2M'))
    if not ghi or not amb:
        raise ValueError('resposta sem ALLSKY_SFC_SW_DWN ou T2M utilizaveis')

    irr = [max(0.0, v) / 1000.0 for v in para_96(ghi)]      # W/m2 -> kW/m2
    # Ruido de borda: irradiancia nao nula com o sol sob o horizonte. O
    # `carregar_clima` ja zerava abaixo de 2 W/m2 no arquivo local; o mesmo
    # criterio aqui, para os dois caminhos darem a mesma coisa.
    irr = [v if v >= 0.002 else 0.0 for v in irr]
    amb96 = para_96(amb)
    return {
        'fonte': FONTE, 'url': alvo, 'lon': lon, 'lat': lat,
        'mes': mes, 'ano': ano, 'periodo': f'{ini}-{fim}',
        'baixado_em': time.strftime('%Y-%m-%d %H:%M:%S'),
        'passos': PASSOS,
        'irradiancia_kw_m2': [round(v, 6) for v in irr],
        'ambiente_c': [round(v, 2) for v in amb96],
        'celula_c': celula(irr, amb96),
        'media_kw_m2': round(sum(irr) / PASSOS, 4),
        'kwh_m2_dia': round(sum(irr) * 24.0 / PASSOS, 2),
    }


# ===================================================================== cache
def caminho_cache(raiz, dist, mes):
    return os.path.join(raiz, 'dados', 'clima', f'{dist}_{mes:02d}.json')


def gravar(dado, caminho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
        json.dump(dado, fh, indent=1, ensure_ascii=False)
    return caminho


def carregar(caminho, log=None):
    """Le o cache e devolve (irradiancia, temperatura de celula), o MESMO
    contrato de `complementos.carregar_clima`. None se nao servir."""
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding='utf-8') as fh:
            d = json.load(fh)
        irr = [float(x) for x in d['irradiancia_kw_m2']]
        cel = [float(x) for x in d['celula_c']]
    except Exception as e:
        if log:
            log(f'  clima: cache ilegivel ({str(e)[:60]}) — ignorado')
        return None
    if len(irr) != PASSOS or len(cel) != PASSOS or max(irr) <= 0:
        if log:
            log('  clima: cache com formato inesperado ou sem sol — ignorado')
        return None
    if log:
        log(f'  clima: {d.get("fonte", "?")}, ({d.get("lat")}, {d.get("lon")}), '
            f'{d.get("kwh_m2_dia")} kWh/m2/dia, baixado em '
            f'{d.get("baixado_em", "?")}')
    return irr, cel


# ======================================================================= CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Baixa o clima da regiao da propria BDGD e grava o cache.')
    ap.add_argument('gdb')
    ap.add_argument('--mes', type=int, default=1)
    ap.add_argument('--ano', type=int, default=2024)
    ap.add_argument('--saida', default=None,
                    help='caminho do cache (padrao: dados/clima/<DIST>_<mes>.json)')
    a = ap.parse_args(argv)

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from .leitor import BDGD, txt

    b = BDGD(a.gdb, verbose=False)
    try:
        dist = txt(b.ler('BASE', ['DIST'])['DIST'][0]).strip()
    except Exception:
        dist = 'DESCONHECIDA'
    p = centroide(b)
    if not p:
        raise SystemExit('a base nao tem geometria utilizavel — sem coordenada, '
                         'nao ha de onde tirar o clima')
    lon, lat = p
    print(f'distribuidora {dist}, centroide da rede ({lat:.4f}, {lon:.4f})')
    print('consultando a NASA POWER...', flush=True)
    d = baixar(lon, lat, a.mes, a.ano)
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest = a.saida or caminho_cache(raiz, dist, a.mes)
    gravar(d, dest)
    print(f'  media {d["media_kw_m2"]:.4f} kW/m2, {d["kwh_m2_dia"]:.2f} '
          f'kWh/m2/dia, ambiente {min(d["ambiente_c"]):.1f} a '
          f'{max(d["ambiente_c"]):.1f} C')
    print(f'  cache em {dest}')


if __name__ == '__main__':
    main()
