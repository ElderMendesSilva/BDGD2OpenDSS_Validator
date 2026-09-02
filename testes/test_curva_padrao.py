# -*- coding: utf-8 -*-
"""A curva de recurso sai da BASE, e nao de uma constante da Enel SP.

Em 25/08/2026 as 97 BDGDs do pais foram convertidas no cluster Ubiratan. As 97
CONVERTERAM. Mas 49 nao puderam ser validadas, todas pelo mesmo motivo:

    DSSException: (#401) Load.bt_1_11_1.Daily:
                 LoadShape object "RES-Tipo02" not found

`cargas.py` caia em `RES-Tipo02` sempre que o `TIP_CC` da UC nao estivesse
entre as curvas validas — em QUATRO pontos —, sem nunca conferir se a propria
`RES-Tipo02` existia. E a MT caia em `MT-Tipo02`, quinto ponto, pelo mesmo
mecanismo.

O MECANISMO EXPLICA POR QUE SOBREVIVEU A DEZENOVE RODADAS:

    base          LoadShapes   tem RES-Tipo02   resultado
    Cocel                 59            nao       PASSOU
    Castro-Dis             1            nao       falhou

A Cocel tambem nao tem a curva E FUNCIONA, porque as UCs dela acham a propria
entre as 59 e o recurso nunca e alcancado. **O recurso so e alcancado quando o
catalogo da base e pobre — e e exatamente ai que ele proprio falta.**

As sete bases do projeto sao todas grandes: mediana de 377 alimentadores contra
8 das que falharam. O defeito era estruturalmente invisivel.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
from bdgd2dss import cargas                          # noqa: E402
import collections                                   # noqa: E402


class ORecursoSaiDaBase(unittest.TestCase):

    def test_a_mais_usada_que_existe_ganha(self):
        """Nao e a mais usada em absoluto: a mais usada QUE EXISTE."""
        uso = collections.Counter({'FANTASMA': 900, 'COM-A': 50, 'RES-B': 10})
        self.assertEqual(
            cargas.curva_padrao({'COM-A', 'RES-B'}, uso), 'COM-A',
            'FANTASMA e a mais usada e nao foi gerada — nao pode ser o recurso')

    def test_sem_uso_cai_no_historico_SE_ele_existir(self):
        self.assertEqual(
            cargas.curva_padrao({'RES-Tipo02', 'X'}, None), 'RES-Tipo02')

    def test_historico_ausente_nao_e_inventado(self):
        """O caso das 49: a base nao publicou RES-Tipo02."""
        r = cargas.curva_padrao({'CURVA-A', 'CURVA-B'}, None)
        self.assertIn(r, {'CURVA-A', 'CURVA-B'})
        self.assertNotEqual(r, 'RES-Tipo02')

    def test_base_sem_curva_nenhuma_devolve_None(self):
        """Nao ha o que apontar. `None` vira carga sem Daily, e nao erro."""
        self.assertIsNone(cargas.curva_padrao(set(), None))
        self.assertIsNone(cargas.curva_padrao(None, collections.Counter()))

    def test_e_determinista(self):
        """Duas rodadas do mesmo modelo tem de sair byte a byte iguais."""
        v = {'B', 'A', 'C'}
        self.assertEqual({cargas.curva_padrao(v, None) for _ in range(20)},
                         {cargas.curva_padrao(v, None)})


class CargaSemCurvaNaoViraErro(unittest.TestCase):
    """Base sem LoadShape gera carga PLANA, e nao referencia quebrada."""

    def test_com_curva_emite_daily(self):
        self.assertEqual(cargas._daily('RES-Tipo02'), ' Daily=RES-Tipo02')

    def test_sem_curva_nao_emite_nada(self):
        self.assertEqual(cargas._daily(None), '')
        self.assertEqual(cargas._daily(''), '')


if __name__ == '__main__':
    unittest.main()
