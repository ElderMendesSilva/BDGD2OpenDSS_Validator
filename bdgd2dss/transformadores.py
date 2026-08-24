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


def gerar(bdgd, ctmts, caminho_trafos, caminho_aterramento, kv_mt=13.8,
          kv_por_ctmt=None):
    """`kv_por_ctmt` da a tensao primaria de cada alimentador; `kv_mt` e o
    padrao para quem nao estiver no mapa."""
    kv_por_ctmt = kv_por_ctmt or {}
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'POT_NOM', 'TEN_LIN_SE',
            'FAS_CON_P', 'FAS_CON_S']
    col = bdgd.ler_filtrado('UNTRMT', 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])

    # impedancias e PERDAS por transformador (EQTRMT), quando disponiveis
    imp = {}
    try:
        e = bdgd.ler('EQTRMT', ['UNI_TR_MT', 'R', 'XHL', 'POT_NOM',
                                'PER_FER', 'PER_TOT'])
        for i in range(len(e['UNI_TR_MT'])):
            imp[txt(e['UNI_TR_MT'][i])] = (
                num(e['R'][i], 0.5), num(e['XHL'][i], 2.0),
                _placa(e['POT_NOM'][i], e['PER_FER'][i], e['PER_TOT'][i]))
    except Exception:
        pass

    n_placa = 0                 # quantos usaram a placa (achado 53)
    # quantos trafos por barra secundaria (deteccao de banco)
    banco = collections.Counter()
    ordem = collections.defaultdict(list)
    for i in range(n):
        b = no(col['PAC_2'][i])
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
        b1 = no(col['PAC_1'][i])
        b2 = no(col['PAC_2'][i])
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
    open(caminho_trafos, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    at = ['! Aterramento do neutro (no 4) dos secundarios de BT',
          f'! Reactor de {R_ATERRAMENTO} ohm entre o no 4 e a terra (no 0).']
    for b in sorted(aterrar):
        at.append(f'New Reactor.NEUTRO_{b} phases=1 bus1={b}.4 bus2={b}.0 '
                  f'R={R_ATERRAMENTO} X=0')
    open(caminho_aterramento, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(at) + '\n')
    return n, sec
