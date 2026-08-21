# -*- coding: utf-8 -*-
"""Codigo de tensao da BDGD -> kV de linha.

A TABELA E A `TTEN` DO DICIONARIO DE DADOS DA ANEEL, e nao uma leitura nossa.
Fonte: Manual de Instrucoes da BDGD, Anexo II, secao 2.17 "Tipo de Tensao
(TTEN)", pagina 250, vigencia 1/12/2021. O campo `TEN` daquela tabela e o valor
em VOLTS; aqui ele vira kV.

POR QUE ISTO IMPORTA. Antes desta tabela o modulo tinha cinco codigos e um
padrao para o resto. Medido nas sete bases da V17, isso deixava **1.421
alimentadores de 9.130 (15,6%)** caindo no padrao:

    CPFL Paulista   1.219 de 1.636 (74,5%)   codigos 41, 46, 42, 77
    Light             132 de 1.713 ( 7,7%)   codigo 67
    Cemig-D            58 de 2.456 ( 2,4%)   codigo 61
    Enel SP            12 de 1.806 ( 0,7%)   codigos 62, 27

Quatro caminhos foram tentados para deduzir os codigos do proprio dado, e
NENHUM decidiu: o `TEN_REG` do regulador e p.u.; o `GRU_TEN` do consumidor so
diz "MT"; o `TEN_FORN` usa este mesmo dominio; e o `TEN_SEC` do transformador
de AT, cruzado pelo `UNI_TR_AT` que o proprio CTMT aponta, discorda em 1.302 de
1.595 casos. Deducao aqui era chute, e a tabela existia.

UM ERRO CORRIGIDO NA PASSAGEM: o codigo 59 estava como 20 kV e vale **21 kV**.

Codigo fora desta tabela continua caindo no padrao, com aviso — mas agora isso
significa "a BDGD tem um codigo que o dicionario nao preve", que e achado, e
nao lacuna nossa.
"""

# codigo -> kV de linha. Tabela TTEN completa, 103 codigos.
TENSAO_KV = {
    '0': 0,           # 0 V
    '1': 0.11,        # 110 V
    '2': 0.115,       # 115 V
    '3': 0.12,        # 120 V
    '4': 0.121,       # 121 V
    '5': 0.125,       # 125 V
    '6': 0.127,       # 127 V
    '7': 0.208,       # 208 V
    '8': 0.216,       # 216 V
    '9': 0.2165,      # 216 V
    '10': 0.22,       # 220 V
    '11': 0.23,       # 230 V
    '12': 0.231,      # 231 V
    '13': 0.24,       # 240 V
    '14': 0.254,      # 254 V
    '15': 0.38,       # 380 V
    '16': 0.4,        # 400 V
    '17': 0.44,       # 440 V
    '18': 0.48,       # 480 V
    '19': 0.5,        # 500 V
    '20': 0.6,        # 600 V
    '21': 0.75,       # 750 V
    '22': 1,          # 1.000 V
    '23': 2.2,        # 2.200 V
    '24': 3.2,        # 3.200 V
    '25': 3.6,        # 3.600 V
    '26': 3.785,      # 3.785 V
    '27': 3.8,        # 3.800 V
    '28': 3.848,      # 3.848 V
    '29': 3.985,      # 3.985 V
    '30': 4.16,       # 4.160 V
    '31': 4.2,        # 4.200 V
    '32': 4.207,      # 4.207 V
    '33': 4.368,      # 4.368 V
    '34': 4.56,       # 4.560 V
    '35': 5,          # 5.000 V
    '36': 6,          # 6.000 V
    '37': 6.6,        # 6.600 V
    '38': 6.93,       # 6.930 V
    '39': 7.96,       # 7.960 V
    '40': 8.67,       # 8.670 V
    '41': 11.4,       # 11.400 V
    '42': 11.9,       # 11.900 V
    '43': 12,         # 12.000 V
    '44': 12.6,       # 12.600 V
    '45': 12.7,       # 12.700 V
    '46': 13.2,       # 13.200 V
    '47': 13.337,     # 13.337 V
    '48': 13.53,      # 13.530 V
    '49': 13.8,       # 13.800 V
    '50': 13.86,      # 13.860 V
    '51': 14.14,      # 14.140 V
    '52': 14.19,      # 14.190 V
    '53': 14.4,       # 14.400 V
    '54': 14.835,     # 14.835 V
    '55': 15,         # 15.000 V
    '56': 15.2,       # 15.200 V
    '57': 19.053,     # 19.053 V
    '58': 19.919,     # 19.919 V
    '59': 21,         # 21.000 V
    '60': 21.5,       # 21.500 V
    '61': 22,         # 22.000 V
    '62': 23,         # 23.000 V
    '63': 23.1,       # 23.100 V
    '64': 23.827,     # 23.827 V
    '65': 24,         # 24.000 V
    '66': 24.2,       # 24.200 V
    '67': 25,         # 25.000 V
    '68': 25.8,       # 25.800 V
    '69': 27,         # 27.000 V
    '70': 30,         # 30.000 V
    '71': 33,         # 33.000 V
    '72': 34.5,       # 34.500 V
    '73': 36,         # 36.000 V
    '74': 38,         # 38.000 V
    '75': 40,         # 40.000 V
    '76': 44,         # 44.000 V
    '77': 45,         # 45.000 V
    '78': 45.4,       # 45.400 V
    '79': 48,         # 48.000 V
    '80': 60,         # 60.000 V
    '81': 66,         # 66.000 V
    '82': 69,         # 69.000 V
    '83': 72.5,       # 72.500 V
    '84': 88,         # 88.000 V
    '85': 88.2,       # 88.200 V
    '86': 92,         # 92.000 V
    '87': 100,        # 100.000 V
    '88': 120,        # 120.000 V
    '89': 121,        # 121.000 V
    '90': 123,        # 123.000 V
    '91': 131.6,      # 131.600 V
    '92': 131.63,     # 131.630 V
    '93': 131.635,    # 131.635 V
    '94': 138,        # 138.000 V
    '95': 145,        # 145.000 V
    '96': 230,        # 230.000 V
    '97': 345,        # 345.000 V
    '98': 500,        # 500.000 V
    '99': 750,        # 750.000 V
    '100': 1000,      # 1.000.000 V
    '101': 245,       # 245.000 V
    '102': 550,       # 550.000 V
}


_avisados = set()


def kv(codigo, padrao, log=None, contexto=''):
    """Converte o codigo em kV. Cai no padrao quando o codigo e desconhecido,
    avisando uma unica vez por codigo para nao poluir a saida."""
    c = '' if codigo is None else str(codigo).strip()
    v = TENSAO_KV.get(c)
    if v:
        return v
    if c and c not in _avisados:
        _avisados.add(c)
        if log:
            log(f'    AVISO: codigo de tensao {c!r} desconhecido{" em " + contexto if contexto else ""} '
                f'— adotando {padrao} kV. Preencha em bdgd2dss/tensoes.py se souber o valor.')
    return padrao


def desconhecidos():
    """Codigos que apareceram na conversao sem valor definido."""
    return sorted(_avisados)


def bases(*niveis, bt=None):
    """Monta o Voltagebases do MASTER: os niveis usados + as tensoes de BT.

    SO VALORES FASE-FASE. O `Voltagebases` do OpenDSS e uma lista de tensoes
    de LINHA: o CalcVoltagebases compara cada barra com base/raiz(3) e adota a
    mais proxima. A lista antiga trazia tambem 0,127, 0,12 e 0,11 — que sao os
    fase-neutro de 220/127, 208/120 e 190/110, ja representados por 0,22,
    0,208 e 0,19.

    O estrago: uma barra de 127 V casava com a entrada 0,127 lida como linha,
    ganhava base fase-neutro de 0,0733 e aparecia a 1,73 pu. Com a fonte em
    1,09 pu chegava a ~1,9. Medido na DALP: 2.805 barras acima de 1,10 pu
    antes, 21 depois. Isso inflava a tensao de BT da concessao inteira, e o
    validador nao via porque so media as barras de MT (kVBase > 1).

    A lista saiu do CENSO de TEN_LIN_SE dos 159.061 transformadores de
    distribuicao, nao de suposicao — 0,24 (71,6%), 0,22 (24,0%), 0,23 (2,3%),
    0,208 (1,4%), 0,38 (0,2%) e 0,44 (0,1%). Os valores fase-neutro que
    apareciam no cadastro (0,127, 0,12, 0,11) sao normalizados na origem, em
    `transformadores._linha`, e por isso nao entram aqui.

    ...MAS O CENSO ERA DE UMA BASE SO, e isso quebrou na segunda
    -----------------------------------------------------------
    Achado 5: a Light declara 1.659 transformadores em 0,216 (216 V) e 172 em
    0,4 (400 V). Sao tensoes de atendimento legitimas dela, e nenhuma existe
    na Enel SP. Sem elas na lista, **1.831 transformadores recebiam base de
    tensao errada** — o mesmo mecanismo que ja tinha posto 2.805 barras acima
    de 1,10 pu.

    Uma lista que cresce a cada distribuidora nunca fica pronta. Agora o
    censo e da BASE SENDO CONVERTIDA (`bt`), com a lista da Enel SP apenas
    como piso — nenhuma tensao some, e as da base entram. E a mesma disciplina
    do `linecodes._ajuste`, que calibra R1 na propria SEGCON a cada execucao.
    """
    piso = [0.44, 0.38, 0.24, 0.23, 0.22, 0.208]
    medidas = [round(float(x), 4) for x in (bt or []) if x]
    v = sorted({round(float(x), 4) for x in niveis if x}
               | set(piso) | set(medidas), reverse=True)
    return v


def censo_bt(bdgd, log=None):
    """As tensoes de BT que ESTA base declara, ja normalizadas.

    Le TEN_LIN_SE de UNTRMT, passa pela regra de fase-neutro do
    `transformadores._linha` e devolve os niveis que aparecem com frequencia.
    Alimenta tanto o catalogo da regra quanto o `Voltagebases`.

    Frequencia minima de propostio: um valor isolado tem chance de ser o
    proprio erro de cadastro que se esta tentando corrigir, e promove-lo a
    base de tensao desligaria a correcao.
    """
    from . import transformadores
    from .leitor import num
    try:
        col = bdgd.ler('UNTRMT', ['TEN_LIN_SE'])
    except Exception as e:
        if log:
            log(f'  censo de BT indisponivel ({str(e)[:60]}) — usando o piso')
        return []
    brutos = [num(x) for x in col['TEN_LIN_SE']]
    # 1. o que a base declara e a regra NAO explica vira nivel legitimo
    transformadores.niveis_da_base(brutos)
    # 2. e o censo do que sai da normalizacao vira Voltagebases
    import collections
    c = collections.Counter(round(transformadores._linha(v), 4)
                            for v in brutos if 0.05 <= v <= 1.0)
    if not c:
        return []
    total = sum(c.values())
    fora = sorted(v for v, n in c.items() if n / total >= 0.001)
    if log and fora:
        det = ', '.join(f'{v:g} ({100*c[v]/total:.1f}%)' for v in
                        sorted(c, key=c.get, reverse=True)[:6])
        log(f'  tensoes de BT desta base: {det}')
    return fora
