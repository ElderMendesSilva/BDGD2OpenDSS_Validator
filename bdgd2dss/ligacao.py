# -*- coding: utf-8 -*-
"""Ligacao da barra da subestacao a componente desenergizada — achado 33, B.

O QUE ISTO E, E O QUE NAO E
---------------------------
Isto NAO e conversao. E MODELAGEM, e **inventa um elo que a BDGD nao
declara**. A premissa tem de aparecer no texto de quem usar o modelo.

O DEFEITO QUE ELA TRATA
-----------------------
Fechado o achado 32, sobra na Cemig-D um residuo de 3,9% da rede que nao e
uniforme. A maior parte dele — 61,9% — esta em 29 alimentadores grandes com
esta forma:

    UHST04    15.141 barras   3 componentes  maiores=[14749, 263, 129]
                              cabeceira na de 129
    CMH80     13.823 barras   3 componentes  maiores=[13688, 133, 2]
                              cabeceira na de 133

A rede esta INTEIRA numa componente gigante, e a cabeceira declarada esta numa
ilha pequena ao lado. Nao e rede partida: e cabeceira no lugar errado, ou
falta o elo entre as duas. A BDGD nao diz qual.

A REGRA
-------
So se liga componente que:

  1. esteja DESENERGIZADA depois de resolver o fluxo — o criterio e eletrico,
     nao topologico, porque e a energizacao que interessa;
  2. tenha carga: componente sem carga nao muda resultado nenhum e ligar so
     aumenta a chance de erro;
  3. seja GRANDE o bastante para nao ser ruido (`min_cargas`);
  4. tenha barra na mesma tensao de base de algum vao existente — ligar 13,8
     kV a 34,5 kV seria pior que deixar desligado.

A ancora e a barra de MAIOR GRAU da componente: e a que mais se parece com um
tronco, e a escolha e deterministica, que importa mais do que ser otima —
duas rodadas do mesmo modelo tem de dar o mesmo elo.

O elo copia o vao existente: `Switch=y`, impedancia desprezivel. Ele
representa o arranjo interno da subestacao, que a BDGD nao modela, e nao um
trecho de rede que alguem esqueceu de cadastrar.

E CADA ELO SAI CONTADO
----------------------
Numero de cargas que ele energiza, kW que ele traz, barra escolhida. Elo
silencioso seria pior que o defeito: quem le o modelo tem de conseguir dizer
quanto do resultado depende desta premissa.
"""
import collections

MIN_CARGAS = 20          # abaixo disso e ruido, nao alimentador


def componentes(adjacencia, mortas):
    """Agrupa as barras mortas em componentes conexas.

    `adjacencia` e barra -> conjunto de barras vizinhas, e `mortas` o conjunto
    das que ficaram sem tensao. A busca anda SO por barras mortas: uma
    componente viva do outro lado nao e problema nosso.
    """
    vis = set()
    out = []
    for b in mortas:
        if b in vis:
            continue
        pilha, cur = [b], set()
        while pilha:
            x = pilha.pop()
            if x in cur:
                continue
            cur.add(x)
            pilha.extend(v for v in adjacencia.get(x, ()) if v in mortas
                         and v not in cur)
        vis |= cur
        out.append(cur)
    out.sort(key=len, reverse=True)
    return out


def ancora(comp, adjacencia, grau_min=1):
    """A barra de maior grau da componente — a que mais parece tronco.

    Empate resolvido pelo nome, para a escolha ser deterministica: duas
    rodadas do mesmo modelo tem de produzir o mesmo elo, senao a premissa
    muda sozinha entre execucoes.
    """
    cand = [(len(adjacencia.get(b, ())), b) for b in comp]
    cand = [(g, b) for g, b in cand if g >= grau_min]
    if not cand:
        return None
    g = max(x[0] for x in cand)
    return min(b for gg, b in cand if gg == g)


def decidir(comps, adjacencia, cargas_por_barra, kv_por_barra, kvs_de_vao,
            min_cargas=MIN_CARGAS, tol_kv=0.05):
    """Escolhe quais componentes ligar, e a que tensao.

    `kvs_de_vao` sao as tensoes de base das barras de onde os vaos partem —
    e so nelas que se pode pendurar o elo novo.

    Devolve (ligacoes, descartadas). Cada ligacao:

        {'barra', 'kv', 'cargas', 'barras', 'grau'}
    """
    lig, fora = [], []
    for comp in comps:
        n_cargas = sum(cargas_por_barra.get(b, 0) for b in comp)
        if n_cargas < min_cargas:
            fora.append({'barras': len(comp), 'cargas': n_cargas,
                         'motivo': 'poucas cargas'})
            continue
        # so barras cuja tensao de base case com a de algum vao
        elegiveis = [b for b in comp
                     if any(abs(kv_por_barra.get(b, 0.0) - k) <= tol_kv * k
                            for k in kvs_de_vao)]
        if not elegiveis:
            fora.append({'barras': len(comp), 'cargas': n_cargas,
                         'motivo': 'nenhuma barra na tensao de um vao'})
            continue
        a = ancora(set(elegiveis), adjacencia)
        if a is None:
            fora.append({'barras': len(comp), 'cargas': n_cargas,
                         'motivo': 'sem barra com vizinho'})
            continue
        lig.append({'barra': a, 'kv': kv_por_barra.get(a, 0.0),
                    'cargas': n_cargas, 'barras': len(comp),
                    'grau': len(adjacencia.get(a, ()))})
    return lig, fora


CABECALHO = """! ==========================================================================
!  LIGACAO A COMPONENTE DESENERGIZADA — achado 33, forma B
! ==========================================================================
!  ISTO E MODELAGEM, NAO CONVERSAO, E INVENTA UM ELO QUE A BDGD NAO DECLARA.
!
!  A rede destes alimentadores esta inteira numa componente conexa grande,
!  e a cabeceira declarada no CTMT.PAC_INI esta numa ilha pequena ao lado.
!  A BDGD nao diz qual e o elo entre as duas. Aqui ele e criado, ligando a
!  barra de MT da subestacao a barra de MAIOR GRAU da componente — a que
!  mais se parece com um tronco.
!
!  O elo e do mesmo tipo do vao de saida: chave de impedancia desprezivel.
!  Ele representa o arranjo interno da subestacao, que a BDGD nao modela.
!
!  {n} elo(s), energizando {cargas:,} cargas em {barras:,} barras.
!
!  Para rodar SEM esta premissa, apague o `redirect _LIGACAO.dss` do MASTER.
!  O modelo continua valido; o que muda e quanta rede fica energizada.
! ==========================================================================
"""


def escrever(caminho, ligacoes, barra_por_kv, descartadas=()):
    """Escreve o `_LIGACAO.dss`: uma Line por componente ligada."""
    tot_c = sum(l['cargas'] for l in ligacoes)
    tot_b = sum(l['barras'] for l in ligacoes)
    out = [CABECALHO.format(n=len(ligacoes), cargas=tot_c, barras=tot_b)]
    for i, l in enumerate(ligacoes, 1):
        de = barra_por_kv(l['kv'])
        if not de:
            continue
        out.append(
            f"New Line.VAO_EXTRA_{i} phases=3 Bus1={de}.1.2.3 "
            f"Bus2={l['barra']}.1.2.3 Switch=y r1=0.0001 r0=0.0001 "
            f"x1=0 x0=0 c1=0 c0=0"
            f"   ! componente de {l['barras']:,} barras e {l['cargas']:,} "
            f"cargas, ancora de grau {l['grau']} em {l['kv']:g} kV")
    if not ligacoes:
        out.append('! nenhuma componente desenergizada relevante nesta '
                   'subestacao.')
    for d in descartadas:
        out.append(f"! descartada: {d['barras']:,} barras, {d['cargas']:,} "
                   f"cargas — {d['motivo']}")
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return len(ligacoes)
