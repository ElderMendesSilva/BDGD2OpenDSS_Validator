# -*- coding: utf-8 -*-
"""
Codigo de tensao da BDGD -> kV.

A BDGD nao carrega a tensao em kV: TEN_NOM (em CTMT, BAR, CTAT) e TEN_PRI/
TEN_SEC (em EQTRAT) sao codigos de um dominio da ANEEL que NAO acompanha o
.gdb. Ate a versao anterior o conversor contornava isso assumindo 13,8 kV
para toda a MT e 88 kV para toda a AT — o que esta certo para a maior parte
da concessao e ERRADO para 122 alimentadores.

De onde vem cada valor abaixo:

  84 -> 88 kV    282 das 306 barras de AT se chamam '...-B88-...'.
  72 -> 34,5 kV  a ISA declara tres trafos 345/34,5 kV na ETT Bandeirantes e
                 os alimentadores da TBAN que saem dali tem TEN_NOM=72.
  59 -> 20 kV    a ISA declara 230/20 kV na ETT Centro e 345/20 kV na ETT
                 Miguel Reale; TODOS os alimentadores da TCTR e o da TMRE
                 tem TEN_NOM=59. Duas confirmacoes independentes.
  94 -> 138 kV   unico nivel de subtransmissao acima de 88 kV que a ISA
                 declara em SP (230/138 na B. Santista, 440/138 em Embu).
  49 -> 13,8 kV  1.678 dos 1.806 alimentadores. E a tensao de distribuicao
                 da Enel SP e o valor que os modelos ja validados usam.

Os codigos 27, 55, 62, 67, 73 e 74 aparecem em poucos registros e NAO foram
confirmados por nenhuma fonte. Ficam como None de proposito: o conversor
avisa e aplica o padrao da camada em vez de fingir precisao que nao tem.
Se voce obtiver a tabela de dominio da distribuidora, preencha aqui — e o
unico lugar que precisa mudar.
"""

# codigo -> kV de linha. None = desconhecido (o conversor avisa e usa o padrao)
TENSAO_KV = {
    '27': None,
    '49': 13.8,
    '55': None,
    '59': 20.0,
    '62': None,
    '67': None,
    '72': 34.5,
    '73': None,
    '74': None,
    '84': 88.0,
    '94': 138.0,
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


def bases(*niveis):
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

    A lista sai do CENSO de TEN_LIN_SE dos 159.061 transformadores de
    distribuicao, nao de suposicao — 0,24 (71,6%), 0,22 (24,0%), 0,23 (2,3%),
    0,208 (1,4%), 0,38 (0,2%) e 0,44 (0,1%). Os valores fase-neutro que
    apareciam no cadastro (0,127, 0,12, 0,11) sao normalizados na origem, em
    `transformadores._linha`, e por isso nao entram aqui. `0,215` e `0,19`
    saem: nenhum transformador da concessao os declara.
    """
    bt = [0.44, 0.38, 0.24, 0.23, 0.22, 0.208]
    v = sorted({round(float(x), 4) for x in niveis if x} | set(bt), reverse=True)
    return v
