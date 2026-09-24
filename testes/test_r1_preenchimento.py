# -*- coding: utf-8 -*-
"""R1 de preenchimento na SEGCON — achado 76.

A Cosern traz R1 = 2,179 ohm/km em 545 dos 598 condutores, o mesmo para cabo
de 230 A e de 530 A. O ajuste que o `linecodes` calibra NA PROPRIA BASE
aprende o defeito (sai plano, expoente -0,026) e nada e corrigido. Na V39 a
Cosern perdeu 10,4% so na MT; com o valor trocado, a APD foi de 17,3% para
5,9%.

A regra so dispara com as DUAS condicoes: um valor em mais da metade da
tabela E um ajuste com expoente acima de -0,3. Sete bases sadias medidas
(expoente de -0,86 a -1,41, valor mais repetido em 9% a 21%) nao disparam.
"""
import math
import os
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import linecodes                        # noqa: E402

K = 156.4


def _sadia(n=80):
    """R1 = K/CNOM com dispersao deterministica, como no test_linecodes."""
    return [(K / (20.0 + i * 10.0) * (1.0 + 0.15 * math.sin(i)), 20.0 + i * 10.0)
            for i in range(n)]


def _cosern(n_pre=545, n_resto=53):
    """Muitos condutores de 100 a 600 A todos com 2,179, e um resto sadio."""
    pre = [(2.179, 100.0 + (i % 50) * 10.0) for i in range(n_pre)]
    return pre + _sadia(n_resto)


class Calibracao(unittest.TestCase):

    def test_base_sadia_nao_dispara(self):
        aj, pre = linecodes.calibracao(_sadia())
        self.assertIsNone(pre)
        self.assertEqual(aj, linecodes._ajuste(_sadia()))

    def test_o_caso_da_cosern_dispara(self):
        _, pre = linecodes.calibracao(_cosern())
        self.assertEqual(pre, 2.179)

    def test_o_ajuste_usado_cai_com_a_ampacidade(self):
        aj, _ = linecodes.calibracao(_cosern())
        self.assertLess(aj[0], linecodes.EXPOENTE_MAXIMO)
        r530 = math.exp(aj[1]) * 530 ** aj[0]
        self.assertLess(r530, 0.5, 'cabo de 530 A nao tem 2 ohm/km')

    def test_resto_pequeno_cai_na_referencia(self):
        aj, pre = linecodes.calibracao(_cosern(n_resto=10))
        self.assertEqual(pre, 2.179)
        self.assertEqual(aj, linecodes.REFERENCIA)

    def test_valor_repetido_com_ajuste_fisico_nao_dispara(self):
        """Fatia alta sozinha nao basta: o expoente tem de estar plano."""
        pares = _sadia(200) + [(K / 300.0, 300.0)] * 250
        _, pre = linecodes.calibracao(pares)
        self.assertIsNone(pre)

    def test_a_referencia_e_fisica(self):
        a, b, _ = linecodes.REFERENCIA
        self.assertAlmostEqual(math.exp(b) * 240 ** a, 0.46, delta=0.03)
        self.assertAlmostEqual(math.exp(b) * 530 ** a, 0.22, delta=0.02)


class _Leitor:
    def __init__(self, pares):
        self.pares = pares

    def ler(self, camada, cols):
        n = len(self.pares)
        return {'COD_ID': np.array([f'C{i}' for i in range(n)], dtype=object),
                'R1': np.array([r for r, _ in self.pares]),
                'X1': np.array([0.4] * n),
                'CNOM': np.array([c for _, c in self.pares]),
                'CMAX': np.array([c * 1.2 for _, c in self.pares]),
                'BIT_FAS_1': np.array(['1'] * n, dtype=object),
                'MAT_FAS_1': np.array(['1'] * n, dtype=object)}


class Gerar(unittest.TestCase):

    def test_o_linecode_sai_corrigido_e_marcado(self):
        caminho = os.path.join(tempfile.mkdtemp(), 'LineCodes.dss')
        mapa, _, corr = linecodes.gerar(_Leitor(_cosern()), caminho)
        self.assertTrue(all(v['r1'] < 1.0 for k, v in mapa.items()
                            if int(k[1:]) < 545 and 500 <= 100.0 + (int(k[1:]) % 50) * 10.0))
        pre = [c for c in corr if c.get('motivo') == 'preenchimento']
        self.assertEqual(len(pre), 545)
        txt = open(caminho, encoding='utf-8').read()
        self.assertIn('R1 DE PREENCHIMENTO', txt)
        self.assertIn('ACHADO 76', txt)

    def test_base_sadia_sai_igual(self):
        caminho = os.path.join(tempfile.mkdtemp(), 'LineCodes.dss')
        _, _, corr = linecodes.gerar(_Leitor(_sadia()), caminho)
        self.assertFalse([c for c in corr if c.get('motivo') == 'preenchimento'])
        self.assertNotIn('ACHADO 76', open(caminho, encoding='utf-8').read())


if __name__ == '__main__':
    unittest.main()
