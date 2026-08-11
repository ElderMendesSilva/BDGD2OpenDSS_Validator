# -*- coding: utf-8 -*-
"""
SEGCON -> New LineCode

Gera um LineCode por (condutor x numero de fases). A BDGD traz apenas R1 e X1;
nao ha sequencia zero. Adotam-se as relacoes tipicas de rede aerea de
distribuicao, aplicadas de forma explicita e documentada no arquivo gerado:

    R0 = 3,0 x R1        X0 = 3,5 x X1

Essas razoes vem da pratica de modelagem de redes aereas com retorno pelo
neutro/terra. Sao PREMISSA, nao dado da BDGD — se a distribuidora fornecer a
tabela de estruturas, o correto e migrar para LineGeometry (ver README).

--------------------------------------------------------------------------
Coerencia entre resistencia e ampacidade
--------------------------------------------------------------------------
Parte dos registros da SEGCON traz resistencia incompativel com a corrente
nominal declarada. Nesta base (Enel SP 2024-12-31), por exemplo:

    condutor 1863:  R1 = 8,43 ohm/km  com  CNOM = 1500 A
    condutor 3445:  R1 = 5,48 ohm/km  com  CNOM = 1500 A
    condutor  219:  R1 = 3,51 ohm/km  com  CNOM =  720 A

Um condutor de 1500 A tem resistencia da ordem de 0,04 ohm/km — os valores
acima sao de 100 a 200 vezes maiores. Sao 803 km de rede de media tensao
(3,6% do total) em condutores assim, e como costumam estar no tronco, o
efeito na tensao a jusante e desproporcional: subestacoes com apenas 25% de
utilizacao do transformador apareciam com 20 a 30% de queda.

O que este modulo faz: ajusta R1 = a x CNOM^b sobre o MIOLO COERENTE da
propria SEGCON (percentis 5 a 95 do produto R1 x CNOM) e, com esse ajuste,
substitui a resistencia dos condutores que estao MUITO acima do previsto.

Tres decisoes deliberadas:

  1. O ajuste e calibrado na propria base a cada execucao, nao numa tabela
     externa. Assim vale para qualquer BDGD e reflete os condutores que a
     distribuidora de fato usa.
  2. So corrige PARA BAIXO. Condutor com R1 muito ABAIXO do previsto e quase
     sempre barramento, jumper ou trecho ideal declarado de proposito
     (ha um com R1 = 0,001 e CNOM = 500 A); eleva-lo introduziria impedancia
     que nao existe.
  3. Toda substituicao vai comentada no proprio LineCodes.dss e devolvida em
     lista, para entrar no relatorio. Nada e corrigido em silencio.

Para desligar: FATOR_CORRIGE = 0.
"""
import collections
import math

from .leitor import num, txt

# razoes de sequencia zero adotadas na ausencia do dado
K_R0 = 3.0
K_X0 = 3.5

# Quantas vezes acima do previsto R1 precisa estar para ser substituido.
# e^2 ~ 7,4: erro de fator 7 nao e dispersao de catalogo, e registro errado.
FATOR_CORRIGE = 7.4

CABECALHO = """! ==========================================================
! LINECODES — gerados de SEGCON
! R1/X1: dado da BDGD (ohm/km)
! R0/X0: PREMISSA — R0={kr} x R1, X0={kx} x X1
!        A BDGD nao traz sequencia zero. Ver README, secao "Limitacoes".
! normamps = CNOM (capacidade nominal), emergamps = CMAX
!
! COERENCIA R1 x CNOM: {n_corr} condutores tiveram a resistencia substituida
! por estarem mais de {fator:g}x acima do previsto pelo ajuste calibrado nesta
! propria base ({ajuste}). Cada um esta
! marcado com "!! R1 CORRIGIDO" na sua linha. Ver README.
! ==========================================================
"""


def _ajuste(pares):
    """Ajusta log(R1) = b + a*log(CNOM) sobre o miolo coerente.

    Devolve (a, b, texto) ou None se nao houver amostra suficiente."""
    val = [(r, c) for r, c in pares if r > 1e-4 and c > 0]
    if len(val) < 50:
        return None
    prod = sorted(r * c for r, c in val)
    lo = prod[int(0.05 * len(prod))]
    hi = prod[int(0.95 * len(prod)) - 1]
    nucleo = [(r, c) for r, c in val if lo <= r * c <= hi]
    if len(nucleo) < 50:
        return None
    n = len(nucleo)
    sx = sum(math.log(c) for _, c in nucleo)
    sy = sum(math.log(r) for r, _ in nucleo)
    sxy = sum(math.log(c) * math.log(r) for r, c in nucleo)
    sxx = sum(math.log(c) ** 2 for _, c in nucleo)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return None
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    return a, b, f'R1 = {math.exp(b):.1f} x CNOM^{a:.3f}, n={n}'


def coerencia_de_uso(trechos, margem=1.0):
    """Coerencia entre a ampacidade DECLARADA e a corrente CALCULADA.

    A verificacao acima (`_ajuste`) confere R1 contra CNOM dentro da SEGCON.
    Ela nao pega o caso mais caro que este projeto encontrou: o condutor 593
    da Enel SP, 31 A com 8,232 ohm/km — um par internamente coerente, e por
    isso intocado, cobrindo 13,5% de uma rede metropolitana de media tensao.
    O defeito nao esta no registro; esta no USO. E uso so aparece depois de
    resolver o fluxo.

    `trechos` e uma lista de dicionarios, um por trecho de linha resolvido:

        {'linecode': str, 'km': float, 'corrente': float, 'amps': float,
         'perda_kw': float (opcional)}

    Devolve, por linecode:

        km                    quilometragem total da rede naquele condutor
        km_sobrecarga         quanto dela opera acima de `margem` x amps
        pct_do_proprio_km     ...em fracao do proprio condutor
        pct_da_rede           fatia do condutor na rede inteira
        pct_da_sobrecarga     fatia dele na sobrecarga total
        enriquecimento        pct_da_sobrecarga / pct_da_rede
        perda_kw, pct_da_perda_em_sobrecarga

    O ENRIQUECIMENTO e o numero que denuncia. Um condutor que carrega a
    sobrecarga na mesma proporcao em que carrega a rede tem enriquecimento
    1,0 — e nao ha nada de especial nele. O 593 mediu **4,64x**: era 20,4%
    da rede dos alimentadores rastreados e 94,7% da sobrecarga deles.
    """
    tot = collections.defaultdict(
        lambda: {'km': 0.0, 'km_sobrecarga': 0.0, 'perda_kw': 0.0,
                 'perda_kw_sobrecarga': 0.0, 'trechos': 0,
                 'trechos_sobrecarga': 0})
    for t in trechos:
        lc = str(t.get('linecode') or '').strip()
        if not lc:
            continue
        km = float(t.get('km') or 0.0)
        amps = float(t.get('amps') or 0.0)
        corr = float(t.get('corrente') or 0.0)
        p = float(t.get('perda_kw') or 0.0)
        d = tot[lc]
        d['km'] += km
        d['perda_kw'] += p
        d['trechos'] += 1
        if amps > 0 and corr > margem * amps:
            d['km_sobrecarga'] += km
            d['perda_kw_sobrecarga'] += p
            d['trechos_sobrecarga'] += 1

    km_rede = sum(d['km'] for d in tot.values())
    km_sob = sum(d['km_sobrecarga'] for d in tot.values())
    p_sob = sum(d['perda_kw_sobrecarga'] for d in tot.values())

    saida = {}
    for lc, d in tot.items():
        pct_rede = 100.0 * d['km'] / km_rede if km_rede else 0.0
        pct_sob = 100.0 * d['km_sobrecarga'] / km_sob if km_sob else 0.0
        saida[lc] = {
            'km': d['km'], 'km_sobrecarga': d['km_sobrecarga'],
            'trechos': d['trechos'],
            'trechos_sobrecarga': d['trechos_sobrecarga'],
            'pct_do_proprio_km': (100.0 * d['km_sobrecarga'] / d['km']
                                  if d['km'] else 0.0),
            'pct_da_rede': pct_rede,
            'pct_da_sobrecarga': pct_sob,
            # None, e nao 1,0: sem sobrecarga na rede o enriquecimento nao
            # esta definido, e devolver 1,0 fingiria uma medida que nao houve
            'enriquecimento': (pct_sob / pct_rede) if (pct_rede and km_sob)
                              else None,
            'perda_kw': d['perda_kw'],
            'perda_kw_sobrecarga': d['perda_kw_sobrecarga'],
            'pct_da_perda_em_sobrecarga': (100.0 * d['perda_kw_sobrecarga']
                                           / p_sob) if p_sob else 0.0,
        }
    return saida


def concentracao(coer, minimo_km=1.0):
    """O alerta: um unico condutor concentra a sobrecarga?

    Devolve (linecode, enriquecimento, pct_da_sobrecarga) do pior caso, ou
    None se nao ha sobrecarga. Referencia medida entre bases: a Enel CE tem
    0,0% da quilometragem em sobrecarga; a Enel SP tem 8,5% a 12,8%, e o
    campeao dela concentra 94,7% dela com enriquecimento 4,64x.
    """
    cand = [(v['enriquecimento'], k, v) for k, v in coer.items()
            if v['enriquecimento'] is not None and v['km'] >= minimo_km]
    if not cand:
        return None
    _, k, v = max(cand, key=lambda x: (x[2]['pct_da_sobrecarga'], x[0]))
    return k, v['enriquecimento'], v['pct_da_sobrecarga']


def gerar(bdgd, caminho_saida):
    """Escreve LineCodes.dss e devolve (mapa, n_condutores, correcoes).

    mapa: {cod_condutor: {fases: nome_linecode, 'r1': .., 'x1': ..}}
    correcoes: lista dos condutores cuja resistencia foi substituida.
    """
    col = bdgd.ler('SEGCON', ['COD_ID', 'R1', 'X1', 'CNOM', 'CMAX',
                              'BIT_FAS_1', 'MAT_FAS_1'])
    n = len(col['COD_ID'])
    pares = [(num(col['R1'][i]), num(col['CNOM'][i])) for i in range(n)]
    aj = _ajuste(pares) if FATOR_CORRIGE else None

    correcoes = []
    linhas = []
    mapa = {}
    corpo = []
    for i in range(n):
        cod = txt(col['COD_ID'][i])
        r1 = num(col['R1'][i])
        x1 = num(col['X1'][i])
        cnom = num(col['CNOM'][i])
        cmax = num(col['CMAX'][i]) or cnom * 1.2
        if r1 <= 0 and x1 <= 0:
            continue

        marca = ''
        if aj and r1 > 0 and cnom > 0:
            a, b, _ = aj
            prev = math.exp(b) * cnom ** a
            if r1 > FATOR_CORRIGE * prev:
                correcoes.append({'cod': cod, 'cnom': cnom,
                                  'r1_bdgd': round(r1, 4),
                                  'r1_adotado': round(prev, 4),
                                  'fator': round(r1 / prev, 1),
                                  'bitola': txt(col['BIT_FAS_1'][i]),
                                  'material': txt(col['MAT_FAS_1'][i])})
                marca = (f'   !! R1 CORRIGIDO: BDGD dizia {r1:.3f} ohm/km para '
                         f'{cnom:.0f} A ({r1/prev:.0f}x o previsto)')
                r1 = prev

        mapa[cod] = {'r1': r1, 'x1': x1}
        for nf in (1, 2, 3):
            nome = f'CND_{cod}_{nf}F'
            mapa[cod][nf] = nome
            corpo.append(
                f'New LineCode.{nome} nphases={nf} basefreq=60 units=km '
                f'r1={r1:.5f} x1={x1:.5f} r0={r1*K_R0:.5f} x0={x1*K_X0:.5f} '
                f'normamps={cnom:.1f} emergamps={cmax:.1f}' + (marca if nf == 1 else ''))

    linhas.append(CABECALHO.format(
        kr=K_R0, kx=K_X0, n_corr=len(correcoes), fator=FATOR_CORRIGE,
        ajuste=(aj[2] if aj else 'ajuste indisponivel — nada corrigido')))
    linhas += corpo

    # condutor generico para trechos sem TIP_CND valido
    linhas.append('\n! condutor generico para trechos sem TIP_CND na base')
    for nf in (1, 2, 3):
        linhas.append(f'New LineCode.CND_GENERICO_{nf}F nphases={nf} basefreq=60 units=km '
                      f'r1=0.40000 x1=0.40000 r0={0.4*K_R0:.5f} x0={0.4*K_X0:.5f} '
                      f'normamps=200.0 emergamps=240.0')
    # trecho ideal (chaves, conexoes)
    for nf in (1, 2, 3):
        linhas.append(f'New LineCode.CND_IDEAL_{nf}F nphases={nf} basefreq=60 units=km '
                      f'r1=0.00010 x1=0.00010 r0=0.00010 x0=0.00010 '
                      f'normamps=9999 emergamps=9999')

    open(caminho_saida, 'w', encoding='utf-8').write('\n'.join(linhas) + '\n')
    return mapa, len(mapa), correcoes


def escrever_usados(origem, destino, pasta_dss):
    """Copia de `origem` so as definicoes de LineCode citadas nos .dss de
    `pasta_dss`.

    O arquivo global tem 10.500 definicoes — as tres variantes de fase de
    cada um dos 3.500 condutores da SEGCON. Uma subestacao usa mediana de
    152. Copiar o arquivo inteiro para as 155 pastas gerava 215 MB de
    conteudo byte a byte identico; o modelo por subestacao continua
    autocontido, so que sem o peso morto.

    O corte e feito sobre o que foi REALMENTE escrito, varrendo os .dss ja
    gerados: assim nao depende de nenhum modulo lembrar de declarar o que
    usou, e cobre tambem LinhasBT.dss e Ramais.dss no modo --bt completo.
    """
    import glob
    import os
    import re

    usados = set()
    for arq in glob.glob(os.path.join(pasta_dss, '*.dss')):
        if os.path.basename(arq).lower() == 'linecodes.dss':
            continue
        with open(arq, encoding='utf-8', errors='replace') as fh:
            for l in fh:
                m = _REF.search(l)
                if m:
                    usados.add(m.group(1).lower())

    saida, guardar = [], True
    with open(origem, encoding='utf-8', errors='replace') as fh:
        for l in fh:
            if l.startswith('New LineCode.'):
                guardar = l.split('.', 1)[1].split(None, 1)[0].lower() in usados
            elif not l.startswith('~'):
                guardar = True          # comentarios e cabecalho ficam
            if guardar:
                saida.append(l)
    open(destino, 'w', encoding='utf-8').write(''.join(saida))
    return len(usados)


_REF = __import__('re').compile(r'[Ll]ine[Cc]ode=(\S+)')
