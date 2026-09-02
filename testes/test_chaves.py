# -*- coding: utf-8 -*-
"""Chave que nao toca a rede — achado 28.

Na Cemig-D V11, 72 subestacoes de 413 foram reprovadas por exatamente 2 nos
NaN cada, sempre na mesma forma:

    Line.2294073839 len=0.001 Switch=Y C1=1.1 R1=0.0001
    barras=['node_2553646456.1', 'node_2553646457.1']

As duas barras existem SO por causa dessa chave. E uma ilha de dois nos, sem
fonte e sem caminho para a terra: a matriz de admitancia daquele pedaco fica
singular e a tensao sai NaN. Foram 2 elementos NaN em 25.326 — e bastaram.

O estrago nao e local. `Circuit.Losses()` soma tudo, entao a perda da
subestacao inteira vira NaN, o `energia` perde os 96 passos do dia e a
subestacao sai da medicao. Foi assim que 72 subestacoes com rede boa
desapareceram da cobertura.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
from bdgd2dss import chaves                           # noqa: E402


class _Leitor:
    def __init__(self, unsemt):
        self.unsemt = unsemt

    def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
        return self.unsemt


def _unsemt(*linhas):
    """Cada linha: (cod, pac1, pac2, estado)."""
    a = lambda *v: np.array(v, dtype=object)          # noqa: E731
    return {'COD_ID': a(*[x[0] for x in linhas]),
            'PAC_1': a(*[x[1] for x in linhas]),
            'PAC_2': a(*[x[2] for x in linhas]),
            'CTMT': a(*['F1'] * len(linhas)),
            'FAS_CON': a(*['ABC'] * len(linhas)),
            'P_N_OPE': a(*[x[3] for x in linhas]),
            'COR_NOM': np.array([400.0] * len(linhas)),
            'TIP_UNID': a(*['1'] * len(linhas))}


def _gera(linhas, barras=None):
    tmp = tempfile.mkdtemp()
    c = os.path.join(tmp, 'Chaves.dss')
    k = os.path.join(tmp, 'Controles.dss')
    n, ab, ilh, _criadas = chaves.gerar(_Leitor(_unsemt(*linhas)), ['F1'], c, k,
                                        barras=barras)
    return n, ab, ilh, open(c, encoding='utf-8').read()


def _criadas(linhas, barras=None):
    """So o quarto retorno: as barras que as chaves emitidas trazem."""
    tmp = tempfile.mkdtemp()
    return chaves.gerar(_Leitor(_unsemt(*linhas)), ['F1'],
                        os.path.join(tmp, 'Chaves.dss'),
                        os.path.join(tmp, 'Controles.dss'), barras=barras)[3]


REDE = {'b1', 'b2', 'b3'}


class ChaveIlhada(unittest.TestCase):

    def test_as_duas_pontas_fora_da_rede_nao_e_emitida(self):
        n, _, ilh, txt = _gera([('SW1', 'node_a', 'node_b', 'F')], REDE)
        self.assertEqual(n, 0)
        self.assertEqual(ilh, ['SW1'])
        self.assertNotIn('New Line.SW1', txt)

    def test_uma_ponta_na_rede_continua_valendo(self):
        """Ali a chave energiza um trecho: o dado e legitimo e nao pode sumir
        junto com o caso doente."""
        n, _, ilh, txt = _gera([('SW1', 'b1', 'node_b', 'F')], REDE)
        self.assertEqual(n, 1)
        self.assertEqual(ilh, [])
        self.assertIn('New Line.SW1', txt)

    def test_as_duas_pontas_na_rede_e_o_caso_normal(self):
        n, _, ilh, _ = _gera([('SW1', 'b1', 'b2', 'F')], REDE)
        self.assertEqual((n, ilh), (1, []))

    def test_sem_a_rede_nada_e_filtrado(self):
        """Compatibilidade: chamada antiga, sem `barras`, mantem tudo."""
        n, _, ilh, txt = _gera([('SW1', 'node_a', 'node_b', 'F')], None)
        self.assertEqual((n, ilh), (1, []))
        self.assertIn('New Line.SW1', txt)

    def test_a_omissao_fica_escrita_no_arquivo(self):
        _, _, _, txt = _gera([('SW1', 'x', 'y', 'F'), ('SW2', 'b1', 'b2', 'F')],
                             REDE)
        self.assertIn('omitida', txt)
        self.assertIn('SW1', txt)

    def test_a_contagem_de_abertas_nao_conta_a_ilhada(self):
        """Chave que nao foi emitida nao pode entrar no `Open` do
        _CHAVES_ABERTAS.dss: o OpenDSS recusaria o comando."""
        n, ab, ilh, _ = _gera([('SW1', 'x', 'y', 'A'),
                               ('SW2', 'b1', 'b2', 'A')], REDE)
        self.assertEqual(ab, ['SW2'])
        self.assertEqual(ilh, ['SW1'])
        self.assertEqual(n, 1)

    def test_varias_ilhadas_de_uma_vez(self):
        linhas = [(f'SW{i}', f'n{i}a', f'n{i}b', 'F') for i in range(5)]
        linhas.append(('BOA', 'b1', 'b3', 'F'))
        n, _, ilh, _ = _gera(linhas, REDE)
        self.assertEqual(n, 1)
        self.assertEqual(len(ilh), 5)


class BarrasQueAChaveTraz(unittest.TestCase):
    """Achado 32. O regulador da BDGD nao toca a SSDMT: ele fica ENTRE DUAS
    CHAVES, com par de nos proprio, fora do conjunto de PACs da SSDMT. Se a
    rede for definida so pela SSDMT, os dois lados do regulador caem fora, ele
    e descartado inteiro e o tronco morre logo depois da cabeceira.

    O NOME NAO E A REGRA. Na Cemig-D esses PACs saem como `segm_*`, mas a
    Enel CE tem 1.056 reguladores sem um unico `segm_` e quebra igual: o
    alcance a partir da cabeceira cai de 99,6% para 25,1%. Guarda escrita
    contra o prefixo conserta uma distribuidora e deixa as outras seis
    quebradas.

    Medido nas sete bases: o alcance sem os elementos em serie vai de 98,6%
    na Enel SP a 25,1% na Enel CE. A Enel SP e a menos afetada — e e a base
    em que o conversor foi escrito, que e por que isto passou despercebido.
    """

    def test_devolve_as_duas_barras_da_chave_emitida(self):
        c = _criadas([('SW1', 'b1', 'segm_9', 'F')], REDE)
        self.assertEqual(c, {'b1', 'segm_9'})

    def test_a_chave_ilhada_nao_contribui_barra(self):
        """Se ela nao foi emitida, as barras dela nao existem no modelo."""
        c = _criadas([('SW1', 'x', 'y', 'F')], REDE)
        self.assertEqual(c, set())

    def test_a_chave_aberta_tambem_traz_as_barras(self):
        """Aberta ou fechada, a Line existe e as barras existem com ela."""
        c = _criadas([('SW1', 'b1', 'segm_9', 'A')], REDE)
        self.assertEqual(c, {'b1', 'segm_9'})

    def test_e_o_segm_que_sustenta_o_regulador(self):
        """O caso medido: o regulador liga segm_X a segm_Y, e cada um deles
        chega a rede por uma chave fechada."""
        c = _criadas([('SW1', 'b1', 'segm_603', 'F'),
                      ('SW2', 'b2', 'segm_542', 'F')], REDE)
        self.assertIn('segm_603', c)
        self.assertIn('segm_542', c)


if __name__ == '__main__':
    unittest.main()
