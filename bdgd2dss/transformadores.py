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

    # impedancias por transformador (EQTRMT), quando disponiveis
    imp = {}
    try:
        e = bdgd.ler('EQTRMT', ['UNI_TR_MT', 'R', 'XHL', 'POT_NOM'])
        for i in range(len(e['UNI_TR_MT'])):
            imp[txt(e['UNI_TR_MT'][i])] = (num(e['R'][i], 0.5), num(e['XHL'][i], 2.0))
    except Exception:
        pass

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
        r, xhl = imp.get(cod, (0.5, 2.0))
        xhl = xhl if xhl > 0 else 2.0
        bb = b2
        nd_p = '.' + '.'.join(fp)
        kvp = kv_por_ctmt.get(txt(col['CTMT'][i]), kv_mt)
        # Achado 17. `Kv` de um enrolamento e a tensao que ELE ve, e isso
        # depende de quantos nos ele toca: dois nos e ligacao fase-fase, e ve
        # a tensao de LINHA; um no e fase-neutro, e ve linha/raiz(3). Antes
        # deste achado os ramos monofasicos escreviam sempre kvp/raiz(3),
        # porque na pratica so caiam neles com FAS_CON_P de uma letra.
        kv_prim = kvp if len(fp) >= 2 else kvp / (3 ** 0.5)

        if len(fs) >= 3 and len(fp) >= 3:
            # trifasico: estrela com neutro no no 4
            kv2 = tl
            out.append(f'New Transformer.{cod} phases=3 windings=2 Xhl={xhl:.3f}\n'
                       f'~ wdg=1 bus={b1}.1.2.3 conn=delta Kv={kvp:g} Kva={kva:.1f} %R={r:.3f}\n'
                       f'~ wdg=2 bus={b2}.1.2.3.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r:.3f}')
            sec[bb] = {'kv_fn': round(tl / (3 ** 0.5), 4), 'nos': ['1', '2', '3'],
                       'kva': kva, 'trifasico': True}
        elif banco[bb] > 1:
            # banco: uma perna por unidade, neutro comum no no 4
            k = str(ordem[bb].index(cod) % 3 + 1)
            kv2 = tl / 2.0
            out.append(f'New Transformer.{cod} phases=1 windings=2 Xhl={xhl:.3f}\n'
                       f'~ wdg=1 bus={b1}{nd_p} conn=wye Kv={kv_prim:.4f} Kva={kva:.1f} %R={r:.3f}\n'
                       f'~ wdg=2 bus={b2}.{k}.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r:.3f}')
            ant = sec.get(bb, {}).get('nos', [])
            sec[bb] = {'kv_fn': round(kv2, 4), 'nos': sorted(set(ant) | {k}),
                       'kva': sec.get(bb, {}).get('kva', 0) + kva, 'trifasico': False}
        else:
            # monofasico isolado: derivacao central
            kv2 = tl / 2.0
            out.append(f'New Transformer.{cod} phases=1 windings=3 '
                       f'Xhl={xhl:.3f} Xht={xhl:.3f} Xlt={xhl/2:.3f}\n'
                       f'~ wdg=1 bus={b1}{nd_p} conn=wye Kv={kv_prim:.4f} Kva={kva:.1f} %R={r:.3f}\n'
                       f'~ wdg=2 bus={b2}.1.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r:.3f}\n'
                       f'~ wdg=3 bus={b2}.4.2 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r:.3f}')
            sec[bb] = {'kv_fn': round(kv2, 4), 'nos': ['1', '2'],
                       'kva': kva, 'trifasico': False}
        aterrar.add(bb)
        # As cargas da UCBT vem agregadas por UNI_TR_MT (o COD_ID do trafo),
        # nao pela barra. Indexa pelos dois para que cargas.py encontre.
        sec[cod] = dict(sec[bb], barra=bb)

    open(caminho_trafos, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    at = ['! Aterramento do neutro (no 4) dos secundarios de BT',
          f'! Reactor de {R_ATERRAMENTO} ohm entre o no 4 e a terra (no 0).']
    for b in sorted(aterrar):
        at.append(f'New Reactor.NEUTRO_{b} phases=1 bus1={b}.4 bus2={b}.0 '
                  f'R={R_ATERRAMENTO} X=0')
    open(caminho_aterramento, 'w', encoding='utf-8').write('\n'.join(at) + '\n')
    return n, sec
