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

    def test_fase_neutro_de_mt_roraima(self):
        """7,96 = 13,8/raiz(3). Seis transformadores em Roraima."""
        self.assertAlmostEqual(tr._linha(7.96), 13.8, places=2)

    def test_fase_neutro_de_mt_light(self):
        """7,62 = 13,2/raiz(3). 613 transformadores na Light."""
        self.assertAlmostEqual(tr._linha(7.62), 13.2, places=2)

    def test_e_regra_e_nao_tabela(self):
        """A correcao do passo 5: em vez de tabela fixa, procurar se o valor
        bate com algum nivel conhecido dividido por raiz(3).

        Qualquer nivel padrao dividido por raiz(3) tem de ser reconhecido,
        inclusive os que nenhuma base mostrou ainda.
        """
        for linha in (0.22, 0.208, 0.38, 13.8, 13.2, 34.5, 23.0):
            self.assertAlmostEqual(tr._linha(round(linha / R3, 4)), linha,
                                   places=2,
                                   msg=f'{linha}/raiz(3) deveria virar {linha}')

    def test_um_terco_da_tensao_de_linha(self):
        """0,0733 = 127/raiz(3), e 0,127 ja e o fase-neutro de 220/127. Dois
        raiz(3) seguidos dao 3. A tabela antiga levava a 0,127 e parava."""
        self.assertAlmostEqual(tr._linha(0.0733), 0.22, places=3)

    def test_380_escrito_em_fase_neutro_e_corrigido(self):
        """O caso apertado que definiu a tolerancia: 380/raiz(3) = 0,21939
        fica a 0,27% de 0,22. Com tolerancia de 0,5% ele seria lido como
        220 V e ficaria assim; com 0,2% e corrigido."""
        self.assertAlmostEqual(tr._linha(0.2194), 0.38, places=3)

    def test_tensao_real_de_bt_fora_da_lista_nao_e_convertida(self):
        """0,216 e tensao de atendimento legitima da Light. Nao pode virar
        380 nem 400 V so por nao estar no catalogo."""
        self.assertAlmostEqual(tr._linha(0.216), 0.216, places=4)

    def test_valor_sem_explicacao_passa_intacto(self):
        """A regra corrige o que ela explica. O resto tem de chegar ao
        relatorio como esta, e nao ser empurrado para o nivel mais proximo."""
        for v in (5.0, 4.207, 0.35, 1.7):
            self.assertAlmostEqual(tr._linha(v), v, places=4)


class NiveisVindosDaBase(unittest.TestCase):
    """Achado 5: `0,216` e `0,4` sao tensoes reais da Light, ausentes da lista
    montada com o censo da Enel SP — 1.831 transformadores recebiam base de
    tensao errada. A base passa a informar as suas."""

    def setUp(self):
        tr._niveis_extra.clear()

    def tearDown(self):
        tr._niveis_extra.clear()

    def test_nivel_frequente_entra_no_catalogo(self):
        tr.niveis_da_base([0.216] * 100 + [0.22] * 100)
        self.assertIn(0.216, tr._niveis_extra)

    def test_valor_raro_nao_entra(self):
        """Valor isolado tem chance de ser o proprio erro que a regra
        corrige. Se ele virasse nivel legitimo, a regra pararia de agir."""
        tr.niveis_da_base([0.216] + [0.22] * 1000)
        self.assertNotIn(0.216, tr._niveis_extra)

    def test_fase_neutro_frequente_nao_vira_nivel(self):
        """O 7,62 aparece 613 vezes na Light. Frequencia sozinha nao pode
        promove-lo a nivel: ele e explicavel como 13,2/raiz(3), e promove-lo
        desligaria a correcao justamente onde ela e mais necessaria."""
        tr.niveis_da_base([0.127] * 500 + [0.22] * 500)
        self.assertNotIn(0.127, tr._niveis_extra)
        self.assertAlmostEqual(tr._linha(0.127), 0.22, places=3)


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
