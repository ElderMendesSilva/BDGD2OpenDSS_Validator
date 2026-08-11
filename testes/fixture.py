# -*- coding: utf-8 -*-
"""BDGD MINIMA para os testes — um FileGeodatabase de verdade, com 73 KB.

Por que .gdb e nao um formato mais comodo: e o formato que o caminho de
producao le. Teste que passa num formato que o codigo real nunca ve vale
menos. O GeoPackage tambem funciona (conferido) e fica como reserva.

Por que `pyogrio.raw.write` e nao `write_dataframe`: o segundo exige geopandas,
que o projeto nao usa. O `raw.write` aceita arrays numpy direto e e irmao do
`raw.read` que o `bdgd2dss.leitor` ja usa — fixture sem dependencia nova.

SEM GEOMETRIA. As tabelas de atributo sao o que o conversor consome; o leitor
le sempre com `read_geometry=False`. O unico modulo que fica sem cobertura por
isso e o `coordenadas.py`, e coordenada errada aparece na figura, nao no
resultado eletrico.

OS VALORES NAO SAO ARBITRARIOS. Cada um reproduz um achado real do
levantamento de generalizacao (ver ACHADOS_GENERALIZACAO.md):

    TEN_NOM='67'        codigo sem valor confirmado, visto na Enel SP e em 132
                        alimentadores da Light
    TEN_LIN_SE=7.96     13,8/raiz(3) — fase-neutro em campo de fase-fase, visto
                        em Roraima
    TEN_LIN_SE=7.62     13,2/raiz(3) — o mesmo padrao, visto na Light
    TEN_LIN_SE=0.216    216 V, tensao de BT real da Light, ausente da lista
                        montada com o censo da Enel SP
    R1=8.43 / CNOM=1500 condutor com resistencia incoerente com a ampacidade,
                        o caso que o auto-ajuste do linecodes.py corrige
    R1=8.232 / CNOM=31  o condutor 593 da Enel SP: internamente COERENTE (31 A
                        pede mesmo ~8 ohm/km), e por isso o auto-ajuste nao o
                        toca — e mesmo assim carrega a maior fatia de km da
                        rede. Achado 11: o defeito esta no uso, nao no par
    faturado > injetado alimentador com medicao degenerada, que reprova o
                        limite fisico sem que o modelo tenha culpa. Achado 10
    SUB com duas barras de origem no mesmo nivel derivado — o caso que gera
                        transformador de barra duplicado
"""
import os
import shutil

import numpy as np
import pyogrio

AQUI = os.path.dirname(os.path.abspath(__file__))
PADRAO = os.path.join(AQUI, 'bdgd_minima.gdb')


def _mes(v):
    """Uma coluna ENE_01..ENE_12 com o mesmo valor, como a BDGD traz."""
    return {f'ENE_{i:02d}': np.array(v, dtype=float) for i in range(1, 13)}


def tabelas():
    """As tabelas da BDGD minima, como dicionarios de arrays."""
    s = lambda *v: np.array(v, dtype=object)      # noqa: E731  (coluna de texto)
    f = lambda *v: np.array(v, dtype=float)       # noqa: E731  (coluna numerica)

    return {
        'SEGCON': {
            'COD_ID': s('C1', 'C2', 'C3', 'C4'),
            # C3: 8,43 ohm/km com 1500 A e incoerente — o auto-ajuste corrige
            # C4: o caso do condutor 593 da Enel SP. 8,232 ohm/km com 31 A e
            #     um par COERENTE, entao o auto-ajuste passa por ele sem tocar.
            #     O que esta errado e a quilometragem que ele cobre.
            'R1': f(0.5, 1.2, 8.43, 8.232),
            'X1': f(0.35, 0.40, 0.38, 0.42),
            'CNOM': f(250.0, 100.0, 1500.0, 31.0),
            'CMAX': f(300.0, 120.0, 1800.0, 37.0),
            'BIT_FAS_1': s('4/0', '2', '336', '2'),
            'MAT_FAS_1': s('CA', 'CA', 'CA', 'CA'),
        },
        'CTMT': {
            'COD_ID': s('F1', 'F2', 'F3'),
            'SUB': s('SE1', 'SE1', 'SE1'),
            # F2 usa o codigo 67, sem valor confirmado em nenhuma base
            'TEN_NOM': s('49', '67', '72'),
            'BARR': s('BAT1', 'BAT1', 'BAT2'),
            'PAC_INI': s('B1', 'B10', 'B20'),
            'UNI_TR_AT': s('T1', 'T1', 'T2'),
            'PERD_A4': f(100.0, 50.0, 40.0),
            'PERD_B': f(80.0, 40.0, 30.0),
            'PERD_A4_B': f(20.0, 10.0, 8.0),
            **_mes([1000.0, 500.0, 400.0]),
        },
        # S4 poe METADE da quilometragem no condutor C4, o de 31 A: e a
        # assinatura do 593 — a rede se concentra no cabo mais fino, e nenhum
        # teste feito SO na SEGCON pode perceber isso, porque o par (R1, CNOM)
        # do C4 e coerente. So a corrente calculada denuncia.
        'SSDMT': {
            'COD_ID': s('S1', 'S2', 'S3', 'S4'),
            'PAC_1': s('B1', 'B2', 'B10', 'B20'),
            'PAC_2': s('B2', 'B3', 'B11', 'B21'),
            'CTMT': s('F1', 'F1', 'F2', 'F3'),
            'TIP_CND': s('C1', 'C3', 'C2', 'C4'),
            'COMP': f(120.0, 80.0, 300.0, 500.0),
            'FAS_CON': s('ABC', 'ABC', 'ABC', 'ABC'),
        },
        'UNTRMT': {
            'COD_ID': s('TR1', 'TR2', 'TR3', 'TR4'),
            'PAC_1': s('B2', 'B3', 'B11', 'B11'),
            'PAC_2': s('N1', 'N2', 'N3', 'N4'),
            'CTMT': s('F1', 'F1', 'F2', 'F2'),
            'POT_NOM': f(75.0, 45.0, 112.5, 30.0),
            # 0,22 normal | 7,96 = 13,8/r3 | 0,216 tensao real ausente da lista
            # | 0,127 fase-neutro que a tabela atual ja trata
            'TEN_LIN_SE': f(0.22, 7.96, 0.216, 0.127),
            'FAS_CON_P': s('ABC', 'A', 'ABC', 'A'),
            'FAS_CON_S': s('ABC', 'A', 'ABC', 'A'),
        },
        'EQTRMT': {
            'UNI_TR_MT': s('TR1', 'TR2', 'TR3', 'TR4'),
            'R': f(0.5, 0.5, 0.6, 0.5),
            'XHL': f(2.0, 2.0, 2.5, 2.0),
            'POT_NOM': f(75.0, 45.0, 112.5, 30.0),
        },
        # Duas barras de origem (BAT1 e BAT2) na MESMA subestacao, ambas
        # precisando de derivacao para 34,5 kV: o caso que hoje gera dois
        # `Transformer.TRB_SE1_34p5` com o mesmo nome.
        'BAR': {
            'COD_ID': s('BAT1', 'BAT2'),
            'SUB': s('SE1', 'SE1'),
            'TEN_NOM': s('84', '84'),
            'PAC': s('PA1', 'PA2'),
            'TIP_INST': s('1', '1'),
        },
        # Energia faturada, para a validacao por balanco. Os numeros sao
        # escolhidos para dar perda total conhecida:
        #   F1: injetada 12.000, faturada 9.600  -> 20,0% de perda total
        #   F2: injetada  6.000, faturada 5.400  -> 10,0% de perda total
        #   F3: injetada  4.800, faturada 6.000  -> -25,0%, IMPOSSIVEL
        #
        # O F3 e a MEDICAO DEGENERADA do achado 10: mais energia faturada do
        # que injetada na cabeceira. Nenhum modelo pode caber ai dentro, e a
        # culpa nao e dele — e cadastro. Separar isto da violacao real foi o
        # corte que revelou a Enel SP como discrepante por fator 40.
        'UCBT_tab': {
            'COD_ID': s('U1', 'U2', 'U3', 'U4'),
            'CTMT': s('F1', 'F1', 'F2', 'F3'),
            'UNI_TR_MT': s('TR1', 'TR2', 'TR3', 'TR4'),
            'TIP_CC': s('BT', 'BT', 'BT', 'BT'),
            **_mes([600.0, 100.0, 400.0, 500.0]),   # 7.200+1.200 | 4.800 | 6.000
        },
        'UCMT_tab': {
            'COD_ID': s('M1', 'M2'),
            'CTMT': s('F1', 'F2'),
            'PAC': s('B3', 'B11'),
            'TIP_CC': s('MT', 'MT'),
            **_mes([100.0, 50.0]),              # 1.200 | 600
        },
        'UNTRAT': {
            'COD_ID': s('T1', 'T2'),
            'SUB': s('SE1', 'SE1'),
            'BARR_1': s('BAT1', 'BAT2'),
            'BARR_2': s('BAT1', 'BAT2'),
            'PAC_1': s('PA1', 'PA2'),
            'PAC_2': s('B1', 'B20'),
            'POT_NOM': f(25000.0, 10000.0),
            'FAS_CON_P': s('ABC', 'ABC'),
            'FAS_CON_S': s('ABC', 'ABC'),
            'SIT_ATIV': s('AT', 'AT'),
        },
    }


def gerar(destino=PADRAO, driver='OpenFileGDB'):
    """(Re)escreve a BDGD minima e devolve o caminho."""
    if os.path.isdir(destino):
        shutil.rmtree(destino, ignore_errors=True)
    elif os.path.exists(destino):
        os.remove(destino)
    for i, (nome, cols) in enumerate(tabelas().items()):
        pyogrio.raw.write(destino, geometry=None,
                          field_data=[cols[c] for c in cols],
                          fields=list(cols), layer=nome, driver=driver,
                          geometry_type=None, crs=None, append=(i > 0))
    return destino


def garantir(destino=PADRAO):
    """Gera se nao existir OU se este arquivo mudou depois dele.

    A comparacao de data nao e zelo: sem ela, mexer numa tabela aqui deixava
    a `.gdb` antiga no disco e a suite continuava verde testando o dado
    anterior — o modo mais silencioso de um teste mentir.
    """
    if not os.path.isdir(destino):
        return gerar(destino)
    nascido = max((os.path.getmtime(os.path.join(d, f))
                   for d, _, fs in os.walk(destino) for f in fs), default=0.0)
    if os.path.getmtime(os.path.abspath(__file__)) > nascido:
        return gerar(destino)
    return destino


if __name__ == '__main__':
    p = gerar()
    tam = sum(os.path.getsize(os.path.join(d, f))
              for d, _, fs in os.walk(p) for f in fs)
    print(f'{p}  ({tam/1024:.0f} KB, {len(tabelas())} tabelas)')
