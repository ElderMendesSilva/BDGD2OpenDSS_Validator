# -*- coding: utf-8 -*-
"""Base com medicao 100% degenerada nao pode derrubar o balanco.

MEDIDO NA V21, em 26/08/2026: **21 das 97 bases do pais** morriam aqui —

    statistics.StatisticsError: no median for empty data
    valida_balanco.py, NIVEL 3 — COBERTURA

Todas cooperativas pequenas, todas com `faturado >= injetado` em **100%** dos
alimentadores. Sem alimentador com medida utilizavel, a lista de cobertura sai
vazia e a mediana estoura.

O QUE TORNAVA O DEFEITO CARO nao era o estouro: era ONDE ele acontecia. O
`json.dump` do `validacao_balanco.json` vem DEPOIS dos prints, entao a base
perdia tambem o dado bruto que ja tinha calculado. Sem esse arquivo o ciclo nao
fecha, a base some do resumo e parece que nao rodou — quando na verdade rodou
inteira e o que faltou foi imprimir uma mediana que nao existe.

NAO HAVER MEDIANA E RESULTADO, e nao falha. A base declara energia faturada
maior que a injetada: defeito de cadastro, nao de modelo. O achado 10 ja
separava `medida degenerada` de violacao real; faltava o caso em que a base
INTEIRA e degenerada.
"""
import os
import statistics
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
import valida_balanco as vb                          # noqa: E402


class MedianaOuMotivo(unittest.TestCase):

    def test_com_amostra_devolve_a_mediana(self):
        self.assertEqual(vb.mediana_ou_motivo([1.0, 3.0, 5.0]), '3.00%')

    def test_sem_amostra_devolve_o_motivo_e_nao_estoura(self):
        """Era aqui que 21 bases morriam."""
        self.assertEqual(vb.mediana_ou_motivo([]), vb.SEM_AMOSTRA)

    def test_o_motivo_diz_o_que_faltou(self):
        """Mensagem tem de nomear a causa, senao vira 'deu erro' de novo."""
        self.assertIn('medida utilizavel', vb.SEM_AMOSTRA)

    def test_casas_decimais_respeitadas(self):
        self.assertEqual(vb.mediana_ou_motivo([10.0, 20.0], 1), '15.0%')

    def test_um_elemento_so_tem_mediana(self):
        """Amostra de um nao e amostra vazia — nao pode cair no motivo."""
        self.assertEqual(vb.mediana_ou_motivo([7.5]), '7.50%')

    def test_o_caso_original_realmente_estourava(self):
        """Prova que o guarda protege de algo real, e nao de hipotese."""
        with self.assertRaises(statistics.StatisticsError):
            statistics.median([])


if __name__ == '__main__':
    unittest.main()
