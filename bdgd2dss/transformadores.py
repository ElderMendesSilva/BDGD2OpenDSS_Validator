# -*- coding: utf-8 -*-
"""
UNTRMT (+ EQTRMT) -> New Transformer

Ponto critico da conversao. O secundario de BT no Brasil e majoritariamente
com derivacao central (240/120 V ou 220/110 V). A BDGD informa a tensao de
LINHA em TEN_LIN_SE; a tensao fase-neutro e metade disso.

Regras aplicadas:
  - 1 ou 2 fases  -> 3 enrolamentos: wdg2 = bus.<f>.4 e wdg3 = bus.4.<g>
                     cada meia bobina com Kv = TEN_LIN_SE / 2
  - 3 fases       -> 2 enrolamentos em estrela, bus = X.1.2.3.4
                     Kv = TEN_LIN_SE (tensao de linha)
  - o no 4 e o NEUTRO, aterrado por um Reactor de 0,5 ohm (arquivo separado)

Se varias unidades compartilham a mesma barra secundaria, formam um banco:
cada uma recebe UMA perna propria, nunca a mesma — caso contrario ficam em
paralelo entre fases diferentes da MT, o que e um curto-circuito.
"""
import collections
from .leitor import num, txt, no
from . import escrita

FASES = {'A': '1', 'B': '2', 'C': '3'}
R_ATERRAMENTO = 0.5      # ohm


def _fases(s, padrao='A'):
    f = [FASES[c] for c in txt(s, padrao).upper() if c in FASES]
    return f or ['1']


# TEN_LIN_SE preenchido com o FASE-NEUTRO em campo de FASE-FASE. Censo dos
# 159.061 transformadores de distribuicao da Enel SP:
#
#     0,2400  113.811   71,6%      0,1270    492    0,3%   <- fase-neutro
#     0,2200   38.243   24,0%      0,3800    385    0,2%
#     0,2300    3.700    2,3%      0,4400     94    0,1%
#     0,2080    2.286    1,4%
#
# Os 492 com 0,127 sao o fase-neutro de um sistema 220/127; ha ainda 0,12
# (208/120) e 0,11 (190/110). Escritos como estao, o enrolamento sai com
# 1/raiz(3) da tensao correta e a barra nao casa com nenhuma base do
# Voltagebases — o que aparecia como subtensao mas era so denominador errado.
#
# Normalizar aqui, na origem, e melhor do que remendar a lista de bases: o
# enrolamento passa a ter a tensao certa e o Voltagebases fica puramente
# fase-fase, como o OpenDSS espera.
#
# ---------------------------------------------------------------------------
# DE TABELA PARA REGRA — passo 5, achado 5
# ---------------------------------------------------------------------------
# A tabela acima cobria so o que a Enel SP mostrou. As bases seguintes
# trouxeram o mesmo erro em valores que ela nao tinha:
#
#     Roraima   7,96 = 13,8/raiz(3)     6 transformadores
#     Light     7,62 = 13,2/raiz(3)   613 transformadores
#
# Duas bases, dois valores, uma regra: se o valor bate com um nivel conhecido
# dividido por raiz(3), o campo esta com o fase-neutro. Uma tabela que cresce
# a cada distribuidora nunca fica pronta; a regra ja cobre os niveis que
# nenhuma base mostrou ainda.
#
# DUAS SALVAGUARDAS, e as duas sao necessarias:
#
#   1. valor que JA E um nivel de linha conhecido passa intacto, sem sequer
#      testar a regra. Sem isso, 0,22 x raiz(3) = 0,38105 cai a 0,28% de
#      0,38 e viraria 380 V; e 0,23 x raiz(3) = 0,39837 cai a 0,4% de 0,40 e
#      viraria 400 V. Os dois sao tensoes de atendimento legitimas.
#
#   2. a regra e aplicada no maximo DUAS vezes, e o segundo passo so serve
#      para confirmar que o alvo e mesmo um nivel de linha.
#
# DUAS TOLERANCIAS, e elas PRECISAM ser diferentes. Medindo os casos reais:
#
#     0,21939 = 380/raiz(3)   fica a 0,27% de 0,22
#     0,11    = 190/raiz(3)   fica a 0,28% de 0,19 (a BDGD arredonda 0,1097)
#
# Sao a mesma distancia relativa, e exigem decisoes opostas: o primeiro NAO
# pode ser reconhecido como 220 V (senao nunca vira 380), e o segundo TEM de
# ser reconhecido como 190 V. Uma tolerancia so nao resolve as duas.
#
# A saida e separar as perguntas. "Ja e um nivel?" e uma pergunta de
# identidade e usa tolerancia apertada (0,15%). "Vezes raiz(3) da um nivel?"
# e uma pergunta de reconstrucao, sobre valor que a BDGD ja arredondou, e
# usa tolerancia folgada (0,5%).
_R3 = 3 ** 0.5

# Niveis de LINHA padrao. A lista pode crescer com o censo da propria base
# (ver `niveis_da_base`), e e isso que traz o 0,216 e o 0,4 da Light.
NIVEIS_LINHA = [0.19, 0.208, 0.22, 0.23, 0.24, 0.254, 0.38, 0.40, 0.44,
                2.3, 3.8, 6.6, 11.4, 13.2, 13.8, 15.0, 20.0, 23.0, 34.5]

TOL_IDENTIDADE = 0.0015
TOL_REGRA = 0.005

# A regra do "um terco" so vale em baixa tensao. Sem esse limite ela pega
# 5,0 kV — valor real, visto em 8 transformadores de Roraima — e o promove a
# 15,0 kV, que esta no catalogo. Erro de fator tres inventado do nada.
LIMITE_TERCO = 0.15

_niveis_extra = set()


def niveis_da_base(valores):
    """Acrescenta ao catalogo os niveis de LINHA que esta base declara.

    O 0,216 e o 0,4 da Light sao tensoes de atendimento reais que a lista
    montada com o censo da Enel SP nao tinha — e sem elas 1.831
    transformadores recebiam base de tensao errada. Em vez de crescer a
    lista a cada distribuidora, a base informa a sua.

    So entra o que aparece com frequencia: valor isolado tem chance de ser
    o proprio erro que estamos tentando corrigir.
    """
    import collections
    c = collections.Counter(round(float(v), 4) for v in valores
                            if v and 0.05 <= float(v) <= 1.0)
    if not c:
        return sorted(_niveis_extra)
    total = sum(c.values())
    for v, n in c.items():
        if n / total < 0.005 or _perto(v, NIVEIS_LINHA, TOL_IDENTIDADE):
            continue
        # so entra se NAO for explicavel como fase-neutro nem como um terco
        # de um nivel conhecido: senao o proprio erro que a regra corrige
        # viraria nivel legitimo, e a correcao se desligaria justamente onde
        # ela e mais necessaria (o 7,62 aparece 613 vezes na Light)
        if _perto(v * _R3, NIVEIS_LINHA):
            continue
        if v < LIMITE_TERCO and _perto(v * 3.0, NIVEIS_LINHA):
            continue
        _niveis_extra.add(v)
    return sorted(_niveis_extra)


def _perto(v, niveis, tol=TOL_REGRA):
    """O nivel conhecido mais proximo de `v`, dentro da tolerancia."""
    melhor, dist = None, None
    for x in niveis:
        d = abs(v - x)
        if d <= tol * x and (dist is None or d < dist):
            melhor, dist = x, d
    return melhor


# ---------------------------------------------------------------------------
# ACHADO 56 — a placa que e de outro transformador
# ---------------------------------------------------------------------------
# A guarda percentual do `_placa` e CEGA A ESCALA: ela pergunta se o ferro
# esta entre 0,05% e 2,0% da nominal, e 1,50% passa folgado. Mas 1,50% de
# 10 kVA sao 150 W, e um transformador de 10 kVA nao dissipa 150 W a vazio —
# esse e o valor de um de 30 kVA. Percentual errado continua PARECENDO
# percentual, e e por isso que uma guarda em percentual nunca pega erro de
# escala.
#
# O QUE FOI MEDIDO NA CEMIG
#
#     classe    ferro    unidades   fases do primario
#      10 kVA   150 W     280.574   monofasicas
#      30 kVA   150 W      27.729   TRIFASICAS
#      15 kVA   195 W     116.115   monofasicas
#      45 kVA   195 W      81.843   TRIFASICAS
#
# Os 150 W sao o valor certo de um BANCO trifasico de 30 kVA — tres unidades
# de 10 kVA a 50 W cada. Ele foi copiado para as unidades individuais. A
# propria Cemig tem o valor certo em 1.507 unidades de 10 kVA com 50 W: o erro
# e interno a base, e nao uma escolha de engenharia dela.
#
# Sao 396.689 transformadores, 42% do parque, com uns 43.000 kW de ferro a
# mais — perto de 30% do ferro que a base declara.
#
# A REGRA E UMA CURVA, E NAO UMA TABELA POR CLASSE
#
# Tabela por classe cresce a cada distribuidora e nunca fica pronta — a mesma
# licao do achado 5. O ferro a vazio segue bem uma potencia da nominal:
#
#     W = 10,4 x kVA^0,77
#
# Ajustada sobre a mediana das seis bases sadias. Com faixa de METADE a DOBRO
# em volta dela, o teste separa limpo: das 56 celulas (7 bases x 8 classes),
# as UNICAS tres fora da faixa sao as tres anomalias da Cemig.
#
#      kVA   curva    min    max      RR   ENCE   EQPA     SP     LT   CPFL   CMIG
#        5      36     18     72      35     35     40     70     30     50     35
#       10      61     31    122      50     50     55     70     45     60    150!
#       15      84     42    167      65     85     60    110     60    100    195!
#       30     143     71    285     150    150    150    170    130    170    150
#       45     195     97    390     195    195    170    260    170    220    195
#       75     289    144    578     295    295    255    390    255    330    295
#    112,5     395    197    790     390    390    335    520    335    440    150!
#      150     493    246    985     485    485    420    640    420    540    485
#
# A faixa de dobro nao e frouxa por descuido: o 5 kVA da Enel SP declara 70 W
# contra 30 W da Light, e as duas sao defensaveis. Faixa apertada transformaria
# diferenca de fabricante em defeito. A da Cemig e 2,5x a curva, e sobra.
#
# O 112,5 kVA com 150 W e o caso oposto — ferro DE MENOS, 0,38x a curva — e
# nao obedece ao fator 3. E a mesma placa de 30 kVA num terceiro lugar. A
# faixa pega os dois lados justamente porque nao presume qual erro veio.
FERRO_A = 10.4           # W por kVA^FERRO_B, ajustado as seis bases sadias
FERRO_B = 0.77
FERRO_FAIXA = 2.0        # aceita de curva/FAIXA a curva*FAIXA


def ferro_esperado(kva):
    """Perda a vazio tipica, em watts, para um transformador de `kva`."""
    return FERRO_A * (float(kva) ** FERRO_B)


def _ferro_fora_de_escala(kva, watts, faixa=FERRO_FAIXA):
    """A placa declara ferro de um transformador de outro tamanho?

    Devolve True para os dois lados: ferro grande demais (a placa do banco
    copiada para a unidade) e pequeno demais (a placa da unidade num banco).
    Nao presumir a direcao e o que faz a guarda pegar o 112,5 kVA da Cemig,
    que erra PARA BAIXO e nao obedece ao fator 3 dos outros dois.
    """
    if not kva or not watts or watts <= 0:
        return False
    c = ferro_esperado(kva)
    return not (c / faixa <= watts <= c * faixa)


def _placa(pot_nom, per_fer, per_tot):
    """As perdas da PLACA, em % da nominal: (ferro, cobre) ou None.

    ACHADO 53, e sao dois defeitos no mesmo lugar.

    1. O TRANSFORMADOR DE DISTRIBUICAO NAO TINHA PERDA A VAZIO. O caminho de
       AT sempre escreveu `%noloadloss` a partir de `PER_FER`; o de
       distribuicao nunca escreveu nada, e `%noloadloss` do OpenDSS e ZERO por
       omissao. Todo trafo de distribuicao das sete bases estava sem ferro.

       Perda de ferro e CONSTANTE, 24 h por dia, e ha 2,3 milhoes de
       transformadores nas sete. Medido, o que faltava em % da carga viva:

           Cemig-D 3,60%   CPFL    1,79%   Enel SP 1,48%
           RR      2,55%   Light   1,52%   Enel CE 1,45%
           EQPA    2,41%

       Isso e da ordem de TUDO o que o modelo perdia — a EQPA modelava 1,09%
       e deixava 2,41% de fora.

    2. O `EQTRMT.R` NAO E CONFIAVEL, e o erro tem sinal diferente por base.
       Ele deveria ser a perda em carga percentual; comparado com a placa
       — `(PER_TOT - PER_FER) / (kVA x 10)` — da:

           base   R mediana  valores distintos  carga real   R/real
           RR         4,150         15            2,100%      1,98
           ENCE       2,960          6            1,950%      1,52
           EQPA       1,000          2            1,900%      0,53
           SP         1,330         37            1,536%      0,87
           LT         1,320         22            1,218%      1,08
           CPFL       1,317         38            1,733%      0,76
           CMIG       1,800         41            2,100%      0,86

       Dois valores distintos em 227 mil transformadores da Equatorial PA;
       quinze em Roraima. Nessas o campo e marcador de posicao, e o desvio
       explica os dois extremos que sobravam: Roraima DOBRA o cobre e
       modelava mais perda em MT do que o pais inteiro perde em distribuicao;
       a EQPA CORTA PELA METADE e modelava um setimo.

    Por isso a placa manda quando existe, e o `R` fica de reserva. A placa e
    coerente por tipo de transformador — 35 W de ferro e 140 W totais num
    5 kVA sao 0,700% e 2,800% —, e o `R` nao precisa ser.

    A conta e `% = W / (kVA x 1000) x 100`, ou seja `W / (kVA x 10)`.
    """
    from . import dominios
    kva = dominios.TPOTAPRT.get(txt(pot_nom))
    f, t = num(per_fer), num(per_tot)
    if not kva or not f or not t or t <= f:
        return None
    ferro = f / (kva * 10.0)
    cobre = (t - f) / (kva * 10.0)
    # Placa fora do plausivel nao substitui nada: transformador de
    # distribuicao fica entre 0,1% e 1,5% de ferro e 0,5% e 4% de cobre.
    if not (0.05 <= ferro <= 2.0 and 0.2 <= cobre <= 6.0):
        return None
    # Achado 56: a guarda acima e CEGA A ESCALA, e por isso deixou passar
    # 396.689 placas da Cemig. Ver `_ferro_fora_de_escala`.
    if _ferro_fora_de_escala(kva, f):
        return None
    return round(ferro, 4), round(cobre, 4)


def _linha(tl):
    """Devolve a tensao de LINHA do secundario, corrigindo o campo trocado."""
    v = round(float(tl), 6)
    niveis = list(NIVEIS_LINHA) + sorted(_niveis_extra)
    for _ in range(2):
        if _perto(v, niveis, TOL_IDENTIDADE):
            return v                       # ja e tensao de linha: nao mexer
        alvo = _perto(v * _R3, niveis)
        if alvo is None and v < LIMITE_TERCO:
            # 0,0733 e 127/raiz(3): o fase-neutro de um sistema cuja tensao
            # de LINHA (0,127) ja e ela propria fase-neutro de 220/127. Dois
            # raiz(3) seguidos dao 3, e e por isso que este caso precisa de
            # um teste proprio — a tabela antiga o levava a 0,127 e parava,
            # corrigindo pela metade.
            alvo = _perto(v * 3.0, niveis)
        if alvo is None:
            return v                       # nao explicavel pela regra
        v = alvo
    return v


def placas_da_base(e):
    """Le a EQTRMT inteira e devolve `{UNI_TR_MT: (r, xhl, placa)}` + contagem.

    DUAS PASSADAS, e a segunda e o achado 56. Na primeira cada registro e
    julgado sozinho; na segunda, quem foi reprovado por escala recebe a placa
    que a PROPRIA BASE usa naquela classe de kVA.

    Por que a propria base e nao a curva. A Cemig tem 1.507 unidades de 10 kVA
    com os 50 W corretos, ao lado de 280.574 com os 150 W do banco. O valor
    certo esta ali dentro, medido no parque daquela distribuidora — a curva e
    ajuste sobre seis bases e serve para decidir QUEM esta errado, nao para
    dizer o que colocar no lugar.

    Onde a base nao tem nenhuma placa sadia para aquela classe, o registro
    fica sem placa e cai no `EQTRMT.R`, que e o comportamento de antes do
    achado 53. Preferir isso a inventar: `R` ruim e um problema conhecido e
    medido, e placa inventada nao.

    A CLASSE E O kVA, e nao o codigo da TPOTAPRT. Duas bases podem usar
    codigos diferentes para 75 kVA, e o que define transformador igual e a
    potencia.
    """
    from . import dominios
    imp, cru = {}, []
    catalogo = collections.defaultdict(collections.Counter)
    for i in range(len(e['UNI_TR_MT'])):
        cod = txt(e['UNI_TR_MT'][i])
        kva = dominios.TPOTAPRT.get(txt(e['POT_NOM'][i]))
        placa = _placa(e['POT_NOM'][i], e['PER_FER'][i], e['PER_TOT'][i])
        r = num(e['R'][i], 0.5)
        xhl = num(e['XHL'][i], 2.0)
        if placa:
            catalogo[kva][placa] += 1
        cru.append((cod, kva, r, xhl, placa, num(e['PER_FER'][i])))

    melhor = {k: c.most_common(1)[0][0] for k, c in catalogo.items() if c}
    n_placa = n_trocada = n_sem = 0
    for cod, kva, r, xhl, placa, per_fer in cru:
        if placa is None and kva and _ferro_fora_de_escala(kva, per_fer):
            placa = melhor.get(kva)
            n_trocada += bool(placa)
            n_sem += not placa
        n_placa += bool(placa)
        imp[cod] = (r, xhl, placa)
    return imp, {'com_placa': n_placa, 'placa_trocada': n_trocada,
                 'sem_substituto': n_sem, 'total': len(cru)}


def pacs_invertidos(bdgd, log=None):
    """Quais transformadores tem `PAC_1` e `PAC_2` trocados. UMA vez por BASE.

    Achado 54. `PAC_1` e o lado de MEDIA e `PAC_2` o de BAIXA. Em alguns
    registros isso vem invertido, e o efeito e violento: a rede de media entra
    pelo enrolamento de 0,12 kV e o transformador funciona como ELEVADOR.
    Medido na 5003346 de Roraima, com a carga toda desligada:

        1018862858   declara Kv=7,9674, e a barra dele esta a 480,1 kV  60,3x
        1019437451   declara Kv=13,8,   e a barra dele esta a 493,9 kV  35,8x

    Os dois lados sobem juntos, na relacao exata do transformador — nao e
    ruido de convergencia, e topologia trocada. A perda a vazio escala com V^2,
    entao NOVE transformadores assim, de 4.539, respondiam por 86,8% da perda a
    vazio da subestacao inteira: 2.711 kW de 3.124 kW.

    A REGRA NAO USA O NOME. O PAC costuma denunciar-se — em Roraima 33 deles
    tem `PAC_1` terminado em "-BT" — mas nem todos: o 1002409124, que sozinho
    fazia 585 kW, tem os dois PACs sem sufixo nenhum. Quem decide e a
    TOPOLOGIA: se o `PAC_2` e um no da rede de media e o `PAC_1` nao e, os
    dois estao trocados.

    ---------------------------------------------------------------------
    ACHADO 57 — POR QUE ISTO E DA BASE, E NAO DA SUBESTACAO
    ---------------------------------------------------------------------
    A primeira versao comparava com a MT da SUBESTACAO que estava sendo
    convertida, porque era o conjunto que o `converter` tinha na mao. Isso
    torna a resposta dependente do RECORTE, e a V21 mostrou os dois lados do
    estrago:

        base    censo da base inteira    V21, por subestacao
        RR                 55                     55
        CMIG               21                      0
        EQPA                0                     25

    Roraima bate. As outras duas se invertem. Um transformador cujo `PAC_1`
    esta na media da subestacao VIZINHA parece "fora da media" no recorte
    local e era trocado — na EQPA, 25 trocas que a base inteira desmente. E na
    Cemig o recorte perdeu os 21 verdadeiros.

    Uma pergunta sobre a REDE tem de ser feita a rede inteira. Ler a media da
    base custa 13 s na Enel SP e 59 s na Cemig, uma vez por rodada, contra 12
    e 58 MINUTOS de conversao.

    E por isso que esta funcao devolve CODIGOS, e nao o conjunto de nos: sao
    dezenas de codigos, que viajam de graca para os processos trabalhadores;
    os 6,5 milhoes de nos de media da Cemig, replicados em 32 processos, nao
    caberiam no no.

    O CENSO DAS SETE, com o escopo certo:

        base      trafos    PAC_2 na MT   PAC_1 fora   INVERTIDOS
        RR        27.700         59           57            55
        ENCE     169.357          0            0             0
        EQPA     227.407         56            0             0
        SP       159.061          0           63             0
        LT        98.455          0            0             0
        CPFL     237.390         19            9             0
        CMIG     952.231         97          668            21

    As DUAS condicoes sao necessarias. Na Enel SP 63 tem `PAC_1` fora da MT e
    ZERO tem `PAC_2` dentro: la sao primarios pendurados, defeito diferente
    (achado 50), e exigir as duas impede que virem troca. A EQPA e a CPFL sao
    o contraexemplo do outro lado: 56 e 19 com `PAC_2` na MT e nenhum
    invertido, porque o `PAC_1` deles TAMBEM esta la.

    Sao 76 em 1,87 milhao — raro, e nada inofensivo.
    """
    alvo = set()
    try:
        u = bdgd.ler('UNTRMT', colunas=['COD_ID', 'PAC_1', 'PAC_2'])
    except Exception:
        return set()
    n = len(u['COD_ID'])
    for c in ('PAC_1', 'PAC_2'):
        alvo.update(no(x) for x in u[c])
    alvo.discard('')
    if not alvo:
        return set()

    # So os PACs de transformador entram no conjunto. Guardar os 6,5 milhoes
    # de nos de media da Cemig custaria centenas de MB para responder a uma
    # pergunta sobre 1,9 milhao deles.
    na_mt = set()
    for camada in ('SSDMT', 'UNSEMT', 'UNREMT'):
        try:
            d = bdgd.ler(camada, colunas=['PAC_1', 'PAC_2'])
        except Exception:
            continue
        for c in ('PAC_1', 'PAC_2'):
            for x in d[c]:
                k = no(x)
                if k in alvo:
                    na_mt.add(k)

    inv = set()
    for i in range(n):
        b1, b2 = no(u['PAC_1'][i]), no(u['PAC_2'][i])
        if b1 and b2 and b2 in na_mt and b1 not in na_mt:
            inv.add(txt(u['COD_ID'][i]))
    if log and inv:
        log(f'  ACHADO 54: {len(inv):,} transformadores com PAC_1 e PAC_2 '
            f'TROCADOS na BDGD; os lados serao endireitados')
    return inv


def _inverte_pacs(col, invertidos):
    """Aplica a decisao ja tomada por `pacs_invertidos`.

    So os PACs trocam. `FAS_CON_P` e `FAS_CON_S` ja descrevem o lado certo —
    no 1018862858, `FAS_CON_P='B'` e monofasico, como o lado de media de um
    trafo de 5 kVA tem de ser, e `FAS_CON_S='BN'` traz o neutro da baixa.
    Trocar tambem as fases desfaria isso.

    Devolve a lista de pares `(b1, b2)` ja na ordem certa e os codigos dos que
    foram invertidos NESTA subestacao — que e o que entra no relatorio.
    """
    pares, tocados = [], []
    invertidos = invertidos or set()
    for i in range(len(col['COD_ID'])):
        cod = txt(col['COD_ID'][i])
        b1, b2 = no(col['PAC_1'][i]), no(col['PAC_2'][i])
        if b1 and b2 and cod in invertidos:
            b1, b2 = b2, b1
            tocados.append(cod)
        pares.append((b1, b2))
    return pares, tocados


def gerar(bdgd, ctmts, caminho_trafos, caminho_aterramento, kv_mt=13.8,
          kv_por_ctmt=None, invertidos=None):
    """`kv_por_ctmt` da a tensao primaria de cada alimentador; `kv_mt` e o
    padrao para quem nao estiver no mapa.

    `invertidos` sao os COD_ID que `pacs_invertidos` apontou como tendo os
    dois PACs trocados — decisao tomada UMA vez sobre a base inteira (achado
    57). Sem ela o conversor escreve o que a BDGD disser, como antes."""
    kv_por_ctmt = kv_por_ctmt or {}
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'POT_NOM', 'TEN_LIN_SE',
            'FAS_CON_P', 'FAS_CON_S']
    col = bdgd.ler_filtrado('UNTRMT', 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])

    # impedancias e PERDAS por transformador (EQTRMT), quando disponiveis
    imp, censo_placa = {}, {}
    try:
        e = bdgd.ler('EQTRMT', ['UNI_TR_MT', 'R', 'XHL', 'POT_NOM',
                                'PER_FER', 'PER_TOT'])
        imp, censo_placa = placas_da_base(e)
    except Exception:
        pass

    n_placa = 0                 # quantos usaram a placa (achado 53)
    # Achado 54: os PACs sao endireitados ANTES de tudo. A deteccao de banco
    # logo abaixo conta trafos por barra SECUNDARIA, e com os lados trocados
    # ela contaria pela barra de media — um alimentador inteiro viraria um
    # banco so.
    pares, invertidos = _inverte_pacs(col, invertidos)

    # quantos trafos por barra secundaria (deteccao de banco)
    banco = collections.Counter()
    ordem = collections.defaultdict(list)
    for i in range(n):
        b = pares[i][1]
        banco[b] += 1
        ordem[b].append(txt(col['COD_ID'][i]))

    out = ['! ==========================================================',
           '! TRANSFORMADORES DE DISTRIBUICAO — gerados de UNTRMT/EQTRMT',
           '! Secundario 1F/2F: 3 enrolamentos com derivacao central',
           '! Neutro no no 4, aterrado em _ATERRAMENTO.dss',
           '! Kv de BT conforme TEN_LIN_SE da BDGD',
           '! ==========================================================']
    sec = {}                       # barra BT -> info para as cargas
    aterrar = set()
    n_norm = 0
    for i in range(n):
        cod = txt(col['COD_ID'][i])
        b1, b2 = pares[i]
        if not b1 or not b2:
            continue
        kva = num(col['POT_NOM'][i], 45.0) or 45.0
        _tl0 = num(col['TEN_LIN_SE'][i], 0.22) or 0.22
        tl = _linha(_tl0)
        n_norm += (tl != _tl0)
        fp = _fases(col['FAS_CON_P'][i], 'A')
        fs = _fases(col['FAS_CON_S'][i], 'A')
        r, xhl, placa = imp.get(cod, (0.5, 2.0, None))
        xhl = xhl if xhl > 0 else 2.0
        # ACHADO 53: a placa manda quando existe. Ver `_placa` para os numeros
        # que motivaram isso — o `R` da EQPA tem DOIS valores distintos em
        # 227 mil transformadores, e vale 0,53x da perda em carga real.
        ferro = 0.0
        if placa:
            ferro, r = placa
        n_placa += bool(placa)
        bb = b2
        nd_p = '.' + '.'.join(fp)
        kvp = kv_por_ctmt.get(txt(col['CTMT'][i]), kv_mt)
        # Achado 17. `Kv` de um enrolamento e a tensao que ELE ve, e isso
        # depende de quantos nos ele toca: dois nos e ligacao fase-fase, e ve
        # a tensao de LINHA; um no e fase-neutro, e ve linha/raiz(3). Antes
        # deste achado os ramos monofasicos escreviam sempre kvp/raiz(3),
        # porque na pratica so caiam neles com FAS_CON_P de uma letra.
        kv_prim = kvp if len(fp) >= 2 else kvp / (3 ** 0.5)
        # Achado 26. `EQTRMT.R` e a resistencia percentual TOTAL do
        # transformador — a perda em carga sobre a nominal. No OpenDSS, `%R` e
        # POR ENROLAMENTO, e a serie total e a soma dos dois; escrever `r` nos
        # dois da `2r`.
        #
        # Metade em CADA enrolamento e a forma que serve aos dois ramos: no de
        # dois enrolamentos da `r` entre primario e secundario, e no de tres
        # (derivacao central) da `r` do primario ate CADA meia bobina, que e o
        # que a placa declara. O `%loadloss`, que o caminho de AT usa, so
        # ajusta os enrolamentos 1 e 2 e deixaria o terceiro no padrao.
        r_enrol = r / 2.0

        if len(fs) >= 3 and len(fp) >= 3:
            # trifasico: estrela com neutro no no 4
            kv2 = tl
            out.append(f'New Transformer.{cod} phases=3 windings=2 Xhl={xhl:.3f}\n'
                       f'~ %noloadloss={ferro:.4f}\n'
                       f'~ wdg=1 bus={b1}.1.2.3 conn=delta Kv={kvp:g} Kva={kva:.1f} %R={r_enrol:.3f}\n'
                       f'~ wdg=2 bus={b2}.1.2.3.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r_enrol:.3f}')
            sec[bb] = {'kv_fn': round(tl / (3 ** 0.5), 4), 'nos': ['1', '2', '3'],
                       'kva': kva, 'trifasico': True}
        elif banco[bb] > 1:
            # banco: uma perna por unidade, neutro comum no no 4
            k = str(ordem[bb].index(cod) % 3 + 1)
            kv2 = tl / 2.0
            out.append(f'New Transformer.{cod} phases=1 windings=2 Xhl={xhl:.3f}\n'
                       f'~ %noloadloss={ferro:.4f}\n'
                       f'~ wdg=1 bus={b1}{nd_p} conn=wye Kv={kv_prim:.4f} Kva={kva:.1f} %R={r_enrol:.3f}\n'
                       f'~ wdg=2 bus={b2}.{k}.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r_enrol:.3f}')
            ant = sec.get(bb, {}).get('nos', [])
            sec[bb] = {'kv_fn': round(kv2, 4), 'nos': sorted(set(ant) | {k}),
                       'kva': sec.get(bb, {}).get('kva', 0) + kva, 'trifasico': False}
        else:
            # monofasico isolado: derivacao central
            kv2 = tl / 2.0
            out.append(f'New Transformer.{cod} phases=1 windings=3 '
                       f'Xhl={xhl:.3f} Xht={xhl:.3f} Xlt={xhl/2:.3f}\n'
                       f'~ %noloadloss={ferro:.4f}\n'
                       f'~ wdg=1 bus={b1}{nd_p} conn=wye Kv={kv_prim:.4f} Kva={kva:.1f} %R={r_enrol:.3f}\n'
                       f'~ wdg=2 bus={b2}.1.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r_enrol:.3f}\n'
                       f'~ wdg=3 bus={b2}.4.2 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r_enrol:.3f}')
            sec[bb] = {'kv_fn': round(kv2, 4), 'nos': ['1', '2'],
                       'kva': kva, 'trifasico': False}
        aterrar.add(bb)
        # As cargas da UCBT vem agregadas por UNI_TR_MT (o COD_ID do trafo),
        # nao pela barra. Indexa pelos dois para que cargas.py encontre.
        sec[cod] = dict(sec[bb], barra=bb)

    # ACHADO 53, dito no proprio arquivo: quantos trafos tiveram as perdas
    # DA PLACA e quantos cairam no `EQTRMT.R`. Onde a placa nao existe, o
    # ferro fica em zero e o cobre vem de um campo que em tres das sete bases
    # e marcador de posicao — quem auditar o modelo precisa saber qual e o
    # caso daquela subestacao.
    out.insert(5, f'! {n_placa:,} de {n:,} transformadores com as perdas da '
                  f'PLACA (PER_FER/PER_TOT); o resto usa EQTRMT.R e fica sem '
                  f'ferro. Ver achado 53 em transformadores._placa.')
    if censo_placa.get('placa_trocada'):
        # Achado 56. Vai no arquivo porque muda um numero que alguem pode
        # querer conferir contra a EQTRMT e nao vai encontrar igual.
        out.insert(6, f'! {censo_placa["placa_trocada"]:,} placas declaravam '
                      f'ferro de um transformador de OUTRO tamanho e foram '
                      f'trocadas pela placa que esta base usa na mesma classe '
                      f'de kVA ({censo_placa.get("sem_substituto", 0):,} sem '
                      f'substituto na base, essas ficaram sem ferro). Ver '
                      f'achado 56 em transformadores.placas_da_base.')
    if invertidos:
        # Achado 54. Vai no arquivo, e nao so no relatorio: quem abre o
        # Trafos.dss e ve um COD_ID diferente do que a UNTRMT diz precisa
        # saber que a troca foi nossa e por que.
        out.insert(6, f'! {len(invertidos):,} transformadores com PAC_1 e '
                      f'PAC_2 TROCADOS na BDGD (PAC_2 na rede de media da '
                      f'BASE, PAC_1 fora dela): os lados foram endireitados '
                      f'aqui. Sem isso o trafo vira elevador. Ver achados 54 '
                      f'e 57 em transformadores.pacs_invertidos.')
        for c in sorted(invertidos):
            out.append(f'! PACs invertidos na BDGD, endireitados: {c}')
    open(caminho_trafos, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    at = ['! Aterramento do neutro (no 4) dos secundarios de BT',
          f'! Reactor de {R_ATERRAMENTO} ohm entre o no 4 e a terra (no 0).']
    for b in sorted(aterrar):
        at.append(f'New Reactor.NEUTRO_{b} phases=1 bus1={b}.4 bus2={b}.0 '
                  f'R={R_ATERRAMENTO} X=0')
    open(caminho_aterramento, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(at) + '\n')
    return n, sec, invertidos
