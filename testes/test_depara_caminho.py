# -*- coding: utf-8 -*-
"""Trava o achado 30-B: etapas/converter.py monta o caminho de
dados/de_para_mnemonicos.csv relativo a etapas/, entao mover converter.py
de pasta (ou qualquer refactor no calculo do caminho) tem que quebrar a
suite aqui, e nao falhar em silencio numa rodada de producao.

O bug: apos a reorganizacao de 02/09/2026 (commit a10ab11) o caminho
passou a apontar para etapas/dados/de_para_mnemonicos.csv, que nao existe.
malha_at.carregar_depara() aceita caminho ausente e devolve {} sem lancar
erro, entao o de-para sumiu de toda rodada nacional desde a V26 sem nenhum
teste pegar (commit 7d96ffc corrigiu).
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import malha_at                      # noqa: E402


def caminho_depara_de_converter():
    """Reproduz o calculo de etapas/converter.py:149-151."""
    import converter
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(converter.__file__))),
        'dados', 'de_para_mnemonicos.csv')


class TestCaminhoDePara(unittest.TestCase):

    def test_caminho_montado_por_converter_existe(self):
        caminho = caminho_depara_de_converter()
        self.assertTrue(
            os.path.exists(caminho),
            f'etapas/converter.py monta {caminho}, que nao existe — '
            'o de-para de mnemonicos vai sumir em silencio da rodada')

    def test_depara_carregado_desse_caminho_nao_fica_vazio(self):
        caminho = caminho_depara_de_converter()
        depara = malha_at.carregar_depara(caminho)
        self.assertGreater(
            len(depara), 0,
            'carregar_depara() devolveu vazio para o caminho que '
            'converter.py monta — de-para nao esta sendo lido')


if __name__ == '__main__':
    unittest.main()
