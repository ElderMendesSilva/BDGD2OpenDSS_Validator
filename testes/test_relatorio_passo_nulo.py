# -*- coding: utf-8 -*-
"""O passo que nao convergiu nao derruba a figura da subestacao.

Ele chega como `None` nas series de fonte e de GD, e `None > 0` levantava
"'>' not supported between instances of 'NoneType' and 'int'" — a figura da
subestacao inteira saia FALHOU (PPR01 da Elektro no T41; MAT, MED e MER da
Equatorial PA na V39).
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import relatorio                                      # noqa: E402


class PassoNulo(unittest.TestCase):

    def test_none_nas_series_nao_levanta(self):
        extra = relatorio._extra_do_modelo([], [], [100.0, None, -50.0],
                                           [10.0, None, 80.0])
        self.assertIn('passos_reversos', extra)

    def test_o_passo_nulo_fica_fora_da_conta(self):
        com = relatorio._extra_do_modelo([], [], [-50.0, None], [80.0, None])
        sem = relatorio._extra_do_modelo([], [], [-50.0], [80.0])
        self.assertEqual(com['passos_reversos'], sem['passos_reversos'])


if __name__ == '__main__':
    unittest.main()
