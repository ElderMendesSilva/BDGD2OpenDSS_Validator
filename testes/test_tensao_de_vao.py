# -*- coding: utf-8 -*-
"""Achado 41: a premissa comparava tensao de linha com tensao de fase.

`decidir` so pendura elo em barra cuja tensao de base case, a 5%, com a de
algum vao. Os dois lados vinham em convencoes diferentes:

    `dss.Bus.kVBase()`        sempre fase-neutro
    `dss.Transformers.kV()`   linha-linha, quando o enrolamento e trifasico

Medido nos transformadores da UTN da Equatorial PA: os de 3 fases devolvem
13,8 e a barra viva deles devolve 7,9674. E a mesma tensao — 13,8/sqrt(3) —
com 73% de diferenca contra uma tolerancia de 5%.

A premissa funcionava pela metade, e por isso ninguem viu: onde o
transformador e monofasico o conversor ja escreve `kvp/sqrt(3)` e os dois
lados batem. O teste de `ligacao` existente usa transformador MONOFASICO,
exatamente o caso que passa — por isso este arquivo e novo, e nao um caso a
mais no antigo.

Custo do defeito, medido na V16: 64.726 cargas na Equatorial PA (88% do que
ainda estava no escuro), 17.201 na Cemig-D e 2.049 na CPFL.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import ligacao                            # noqa: E402

R3 = 3 ** 0.5


class AConversaoDoEnrolamento(unittest.TestCase):

    def test_trifasico_vira_fase_neutro(self):
        self.assertAlmostEqual(ligacao.kv_de_fase(13.8, 3), 7.9674, places=3)

    def test_trifasico_de_34_5(self):
        self.assertAlmostEqual(ligacao.kv_de_fase(34.5, 3), 19.9186, places=3)

    def test_bifasico_tambem_e_linha_linha(self):
        """Enrolamento de 2 fases declara tensao de linha, como o de 3."""
        self.assertAlmostEqual(ligacao.kv_de_fase(13.8, 2), 7.9674, places=3)

    def test_monofasico_ja_vem_em_fase_e_nao_se_mexe(self):
        """O conversor escreve `kvp/sqrt(3)` para 1 fase — converter de novo
        dividiria duas vezes e criaria o defeito espelhado."""
        self.assertEqual(ligacao.kv_de_fase(7.9674, 1), 7.9674)


class OQueOAchado41Quebrava(unittest.TestCase):
    """O caso real: componente morta, trafo trifasico, vao na mesma tensao."""

    def setUp(self):
        # duas barras mortas ligadas entre si, com carga suficiente
        self.adj = {'m1': {'m2'}, 'm2': {'m1'}}
        self.comps = [['m1', 'm2']]
        self.cargas = {'m1': 60, 'm2': 40}
        self.kvs_vao = [7.9674]            # como sai de `Bus.kVBase()`

    def test_sem_a_conversao_a_componente_e_descartada(self):
        """Reproduz o defeito: 13,8 cru contra 7,9674 do vao."""
        kv = {'m1': 13.8, 'm2': 13.8}      # `Transformers.kV()` sem converter
        lig, fora = ligacao.decidir(self.comps, self.adj, self.cargas, kv,
                                    self.kvs_vao)
        self.assertEqual(lig, [])
        self.assertEqual(fora[0]['motivo'], 'nenhuma barra na tensao de um vao')
        self.assertEqual(fora[0]['cargas'], 100)

    def test_com_a_conversao_a_componente_e_ligada(self):
        kv = {b: ligacao.kv_de_fase(13.8, 3) for b in ('m1', 'm2')}
        lig, fora = ligacao.decidir(self.comps, self.adj, self.cargas, kv,
                                    self.kvs_vao)
        self.assertEqual(len(lig), 1)
        self.assertEqual(lig[0]['cargas'], 100)
        self.assertAlmostEqual(lig[0]['kv'], 7.9674, places=3)

    def test_tensao_de_outro_nivel_continua_recusada(self):
        """A conversao nao pode virar um passe livre.

        Rede de 34,5 kV numa subestacao cujo unico vao e de 13,8 kV tem de
        seguir de fora: nao ha onde pendura-la. Sao os 6,8% do residuo que o
        achado 41 mediu e que NAO sao defeito de codigo — e a familia do
        achado 40.
        """
        kv = {b: ligacao.kv_de_fase(34.5, 3) for b in ('m1', 'm2')}
        lig, fora = ligacao.decidir(self.comps, self.adj, self.cargas, kv,
                                    self.kvs_vao)
        self.assertEqual(lig, [])
        self.assertEqual(fora[0]['motivo'], 'nenhuma barra na tensao de um vao')


class OUsoNoRadiografia(unittest.TestCase):
    """`radiografia` roda contra o OpenDSS e nao entra em teste de unidade.

    O que da para trancar sem motor e que ela CHAMA a conversao — sem isso o
    conserto fica no modulo e nao chega ao caminho que roda.
    """

    def test_ligacao_py_converte_a_tensao_do_enrolamento(self):
        with open(os.path.join(RAIZ, 'etapas', 'ligacao.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn('kv_de_fase(', fonte,
                      'ligacao.py le Transformers.kV() sem converter para '
                      'fase-neutro — o achado 41 volta')
        self.assertNotIn('kv_prim[bs[0]] = dss.Transformers.kV()', fonte,
                         'a atribuicao crua continua no codigo')


if __name__ == '__main__':
    unittest.main()
