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
from . import escrita

MIN_CARGAS = 20          # abaixo disso e ruido, nao alimentador

# ...MAS RUIDO E RELATIVO, E NAO SO ABSOLUTO.
#
# ACHADO 25. `MIN_CARGAS` sozinho descartava a subestacao INTEIRA. Na ROL da
# CEEE Equatorial, a componente desenergizada tinha 212 barras e 13 cargas, e
# 13 < 20 — descartada por "poucas cargas". So que a ROL tem 13 cargas NO
# TOTAL: o que foi jogado fora como ruido era 100% da subestacao. O modelo
# saiu com a fonte energizando 16 barras de 228, convergindo em 2 iteracoes
# porque nao havia carga alguma ligada, e o `P_fonte_kW` era 0,1 kW.
#
# O limiar existe para nao inventar elo para fragmento solto. Uma componente
# que carrega a maior parte das cargas da subestacao nao e fragmento solto,
# tenha ela 13 cargas ou 13 mil — o numero absoluto nao diz nada sem o
# denominador. Agora ela sobrevive por qualquer um dos dois criterios.
FRACAO_RELEVANTE = 0.10  # 10% das cargas da subestacao ja e alimentador

R3 = 3 ** 0.5


def kv_de_fase(kv, n_fases):
    """A tensao do enrolamento, convertida para FASE-NEUTRO.

    ACHADO 41. `decidir` compara a tensao da barra com a dos vaos, e os dois
    lados vinham em convencoes diferentes:

        `dss.Bus.kVBase()`        sempre fase-neutro
        `dss.Transformers.kV()`   linha-linha, quando o enrolamento e trifasico

    Medido nos transformadores da UTN da Equatorial PA: os de 3 fases devolvem
    13,8 e a barra viva deles devolve 7,9674 — a MESMA tensao, com 73% de
    diferenca, contra uma tolerancia de 5%. A componente era descartada com o
    motivo `nenhuma barra na tensao de um vao`.

    Custo do defeito, medido na V16: 64.726 cargas na Equatorial PA (88% do
    que ainda estava no escuro), 17.201 na Cemig-D e 2.049 na CPFL.

    E por isso a premissa funcionava pela metade: onde o transformador e
    monofasico o conversor ja escrevia `kvp/sqrt(3)`, e os dois lados batiam.
    Na UTN eram 902 trifasicos contra 4 monofasicos nas barras mortas.
    """
    return kv / R3 if n_fases >= 2 else kv


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


def alcancavel_por_chave(comp, aberto, mortas):
    """A componente toca a rede VIVA por um elemento que nao conduz?

    ISTO E INFORMACAO, E NAO CRITERIO — e a distincao custou uma geracao.

    A primeira versao RECUSAVA ligar essas componentes, com o argumento de que
    a BDGD declara aquela chave aberta e inventar um elo ali seria apagar o
    dado. Medido, o argumento estava errado, e a propria BDGD diz por que.

    Cruzando as componentes mortas da SUB 1645246100 da Cemig-D com o
    `SSDMT.CTMT`: **84% a 88% das barras de cada uma pertencem a alimentadores
    DESTA subestacao**, e nenhuma delas contem cabeceira — sao trechos de meio
    de alimentador, cortados. Ou seja, o mesmo cadastro afirma duas coisas
    incompativeis:

        SSDMT.CTMT      este trecho e do alimentador X da subestacao S
        UNSEMT.P_N_OPE  o unico caminho de X ate ele esta aberto

    Qual vence tem criterio: **a atribuicao por CTMT e a que a distribuidora
    usa na propria contabilidade**. O PERD_A4 e declarado por CTMT e a energia
    das unidades consumidoras e atribuida por CTMT. Deixar o trecho escuro faz
    o modelo do alimentador X excluir rede que a distribuidora conta como de
    X — e ai a validacao compara perda de duas redes diferentes.

    E ligar nao fecha a chave declarada: o elo vai da barra de MT da
    subestacao ate a componente, e a chave continua aberta onde a BDGD a poe.
    O que se faz e ALIMENTAR o trecho a partir da subestacao que o cadastro
    nomeia como dona dele.

    Recusar custou, na V15: Cemig-D de 90,0% para 79,7% de carga energizada, e
    Roraima de 8 para 826 cargas sem tensao. A funcao fica porque a condicao
    vale a pena aparecer no arquivo gerado — quem le tem direito de saber que
    aquele trecho so alcanca a rede viva por uma chave aberta.
    """
    if not aberto:
        return False
    return any(v not in mortas
               for b in comp for v in aberto.get(b, ()))


def decidir(comps, adjacencia, cargas_por_barra, kv_por_barra, kvs_de_vao,
            min_cargas=MIN_CARGAS, tol_kv=0.05, aberto=None, mortas=frozenset(),
            fracao_relevante=FRACAO_RELEVANTE):
    """Escolhe quais componentes ligar, e a que tensao.

    `kvs_de_vao` sao as tensoes de base das barras de onde os vaos partem —
    e so nelas que se pode pendurar o elo novo.

    `aberto` e a adjacencia do que existe e NAO conduz. Componente que
    alcanca a rede viva por ali fica de fora — ver `alcancavel_por_chave`.

    Devolve (ligacoes, descartadas). Cada ligacao:

        {'barra', 'kv', 'cargas', 'barras', 'grau'}
    """
    lig, fora = [], []
    # O DENOMINADOR. Sem ele "poucas cargas" e uma frase sem referencia: 13 e
    # pouco numa subestacao de 5.000 cargas e e TUDO numa de 13.
    total_cargas = sum(cargas_por_barra.values()) or 0
    piso_relativo = fracao_relevante * total_cargas
    registro_relativo = []

    for comp in comps:
        n_cargas = sum(cargas_por_barra.get(b, 0) for b in comp)
        # ZERO CARGAS NUNCA LIGA, por nenhum dos dois criterios. Ligar o que
        # nao tem carga nao muda resultado nenhum e so acrescenta um elo
        # inventado — e com o criterio relativo sozinho o zero passava, porque
        # numa subestacao inteiramente morta `piso_relativo` tambem e zero e
        # `0 < 0` e falso. O teste pegou.
        if not n_cargas or (n_cargas < min_cargas and n_cargas < piso_relativo):
            fora.append({'barras': len(comp), 'cargas': n_cargas,
                         'motivo': 'poucas cargas'})
            continue
        if n_cargas < min_cargas:
            # Sobreviveu SO pelo criterio relativo. Fica registrado, porque e
            # exatamente o caso que o limiar absoluto descartava sozinho.
            registro_relativo.append(n_cargas)
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
                    'grau': len(adjacencia.get(a, ())),
                    # so para o arquivo gerado dizer em que condicao o trecho
                    # estava — ver `alcancavel_por_chave`
                    'so_por_chave': alcancavel_por_chave(comp, aberto, mortas)})
    return lig, fora


def aceitar(candidatos, tenta):
    """Adiciona os elos UM A UM e mantem so o que nao quebra a solucao.

    POR QUE ISTO EXISTE. A primeira versao escrevia todos os elos de uma vez,
    resolvia, e — se o modelo divergisse — registrava `convergiu: False` e
    mantinha os elos assim mesmo. Medido na Equatorial PA V13: tres
    subestacoes de 119 pararam de convergir, com tensao em 7,8e+23, 56.029 e
    10,28 pu. Eram exatamente as tres em que houve elo. A V11 tinha 119/119.

    Premissa que PIORA o modelo nao se sustenta. Nao e questao de engenharia,
    e de defesa: um revisor que veja "religamos a rede desenergizada" e
    encontre tres modelos divergentes pergunta, com razao, o que mais a
    premissa quebrou sem que ninguem tenha olhado.

    A ordem e do maior para o menor em carga: se algum elo tiver de cair, que
    caia o que menos entrega. `tenta(elo)` devolve True se o modelo continua
    convergindo com ele dentro — quem chama e que sabe resolver o fluxo.

    Devolve (mantidos, recusados). Recusado nao some: vai escrito no arquivo,
    porque elo que a gente tentou e desistiu e informacao sobre a rede.
    """
    mantidos, recusados = [], []
    for c in sorted(candidatos, key=lambda x: (-x.get('cargas', 0),
                                               str(x.get('barra')))):
        if tenta(c):
            mantidos.append(c)
        else:
            recusados.append(c)
    return mantidos, recusados


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
            f"cargas, ancora de grau {l['grau']} em {l['kv']:g} kV"
            + ('; so alcancava a rede viva por chave declarada ABERTA'
               if l.get('so_por_chave') else ''))
    if not ligacoes:
        out.append('! nenhuma componente desenergizada relevante nesta '
                   'subestacao.')
    for d in descartadas:
        if d.get('motivo') == 'quebrou a convergencia':
            # este merece destaque: a rede existe, o elo foi tentado, e o
            # modelo divergiu com ele dentro. E informacao sobre a REDE
            out.append(f"! RECUSADO: {d['barras']:,} barras, {d['cargas']:,} "
                       f"cargas — o elo fez o modelo divergir, e premissa "
                       f"que piora o modelo nao entra")
        else:
            out.append(f"! descartada: {d['barras']:,} barras, "
                       f"{d['cargas']:,} cargas — {d['motivo']}")
    open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    return len(ligacoes)
