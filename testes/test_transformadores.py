# -*- coding: utf-8 -*-
"""Normalizacao de TEN_LIN_SE — o campo trocado.

Achado 5 de ACHADOS_GENERALIZACAO.md, observado em DUAS bases independentes:
7,96 = 13,8/raiz(3) em Roraima e 7,62 = 13,2/raiz(3) na Light. Duas
observacoes independentes da mesma regra sao um argumento bem mais forte do
que uma tabela que cresce a cada distribuidora.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss import transformadores as tr        # noqa: E402

R3 = math.sqrt(3)


class NormalizaTensaoDeLinha(unittest.TestCase):

    def test_tensoes_normais_passam_intactas(self):
        for v in (0.22, 0.24, 0.23, 0.208, 0.38, 0.44):
            self.assertEqual(tr._linha(v), v, f'{v} e tensao de linha valida')

    def test_fase_neutro_de_bt_ja_tratado(self):
        """Os casos que a tabela atual cobre, vindos do censo da Enel SP."""
        self.assertEqual(tr._linha(0.127), 0.22)     # 220/127
        self.assertEqual(tr._linha(0.12), 0.208)     # 208/120
        self.assertEqual(tr._linha(0.11), 0.19)      # 190/110

    def test_arredondamento_nao_atrapalha(self):
        self.assertEqual(tr._linha(0.12700001), 0.22)

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_fase_neutro_de_mt_roraima(self):
        """7,96 = 13,8/raiz(3). Seis transformadores em Roraima.

        Hoje passa intacto e a barra nao casa com nenhuma base do
        Voltagebases.
        """
        self.assertAlmostEqual(tr._linha(7.96), 13.8, places=2)

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_fase_neutro_de_mt_light(self):
        """7,62 = 13,2/raiz(3). 613 transformadores na Light."""
        self.assertAlmostEqual(tr._linha(7.62), 13.2, places=2)

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_deveria_ser_regra_nao_tabela(self):
        """A correcao proposta no passo 5: em vez de tabela fixa, procurar
        se o valor bate com algum nivel conhecido dividido por raiz(3).

        Este teste enuncia a regra. Qualquer nivel padrao dividido por raiz(3)
        tem de ser reconhecido, inclusive os que nenhuma base mostrou ainda.
        """
        for linha in (0.22, 0.208, 0.38, 13.8, 13.2, 34.5, 23.0):
            self.assertAlmostEqual(tr._linha(round(linha / R3, 4)), linha,
                                   places=2,
                                   msg=f'{linha}/raiz(3) deveria virar {linha}')


class Fases(unittest.TestCase):

    def test_letras_viram_nos(self):
        self.assertEqual(tr._fases('ABC'), ['1', '2', '3'])
        self.assertEqual(tr._fases('A'), ['1'])
        self.assertEqual(tr._fases('BC'), ['2', '3'])

    def test_vazio_cai_no_padrao(self):
        self.assertEqual(tr._fases('', 'A'), ['1'])
        self.assertEqual(tr._fases(None, 'B'), ['2'])

    def test_lixo_nao_derruba(self):
        self.assertEqual(tr._fases('XYZ'), ['1'])


if __name__ == '__main__':
    unittest.main()
