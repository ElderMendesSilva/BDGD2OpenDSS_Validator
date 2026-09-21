# -*- coding: utf-8 -*-
"""Achado 71: `Converged()` pode dizer sim com a solucao em NaN.

Medido na Enel SP, DBFU, com BT completa: o passo 37 voltou convergido com
potencia e perda NaN, o modo diario herdou o estado, e 59 dos 96 passos se
perderam. Com o NaN contado como falha — e recompilando —, 96 de 96.

O motor falso abaixo reproduz so o que importa: um `Solve` que "converge" em
NaN a partir de um instante, e que so volta a dar numero depois de uma
recompilacao. Com a regra antiga (so `Converged()`), o dia termina com 59
falhas; com a nova, com zero.
"""
import math
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))

import energia                                             # noqa: E402

NAN = float('nan')


class _Motor(object):
    """Um OpenDSS de brinquedo com o defeito do achado 71.

    A partir de `envenena_em`, o `Solve` sem recompilacao desde entao
    devolve NaN com `Converged()` verdadeiro — e o estado persiste ate o
    proximo `Clear`/`Compile`.
    """

    def __init__(self, envenena_em=37):
        self.envenena_em = envenena_em
        self.envenenado = False
        self.hora = 0.0
        self.recompilou_no_passo = set()
        self.passo = 0
        outer = self

        class Text(object):
            def Command(self, cmd):
                c = cmd.strip().lower()
                if c.startswith('clear'):
                    outer.envenenado = False
                    outer.recompilou_no_passo.add(outer.passo)
                elif c.startswith('set hour='):
                    outer.hora = float(c.split('=')[1])
                elif c.startswith('set sec='):
                    outer.hora += float(c.split('=')[1]) / 3600.0
                    outer.passo = int(round(outer.hora * 4))
                elif c == 'solve':
                    ja_limpo = outer.passo in outer.recompilou_no_passo
                    if outer.passo == outer.envenena_em and not ja_limpo:
                        outer.envenenado = True

        class Solution(object):
            def Converged(self):
                return True                  # o defeito: diz sim mesmo em NaN

        class Circuit(object):
            def TotalPower(self):
                return [NAN, NAN] if outer.envenenado else [-100.0, -30.0]

            def Losses(self):
                return [NAN, NAN] if outer.envenenado else [2000.0, 500.0]

        class _Vazio(object):
            def First(self):
                return 0

        class Meters(object):
            def First(self):
                return 0

            def RegisterNames(self):
                return ['Zone kWh', 'Zone Losses kWh']

        self.Text, self.Solution, self.Circuit = Text(), Solution(), Circuit()
        self.PVsystems = self.Generators = _Vazio()
        self.Meters = Meters()


class TestPassoSadio(unittest.TestCase):

    def _com(self, conv, p, perdas):
        class S(object):
            def Converged(self):
                return conv

        class C(object):
            def TotalPower(self):
                return [p, 0.0]

            def Losses(self):
                return [perdas, 0.0]

        class D(object):
            Solution = S()
            Circuit = C()
        return energia.passo_sadio(D())

    def test_convergido_com_numero_e_sadio(self):
        self.assertTrue(self._com(True, -100.0, 2000.0))

    def test_convergido_com_nan_na_potencia_nao_e_sadio(self):
        self.assertFalse(self._com(True, NAN, 2000.0))

    def test_convergido_com_nan_na_perda_nao_e_sadio(self):
        self.assertFalse(self._com(True, -100.0, NAN))

    def test_nao_convergido_nao_e_sadio(self):
        self.assertFalse(self._com(False, -100.0, 2000.0))


class TestDiaNaoHerdaONaN(unittest.TestCase):

    def test_o_dia_fecha_inteiro_depois_do_nan(self):
        """O caso da DBFU: NaN no passo 37 nao pode levar o resto do dia."""
        motor = _Motor(envenena_em=37)
        _, _, ok, falhos, n_comp, _, _ = energia.dia(motor, 'x.dss', 96)
        self.assertEqual(falhos, [])
        self.assertEqual(ok, 96)
        self.assertGreaterEqual(n_comp, 2)       # recompilou para limpar

    def test_o_retry_usa_passo_sadio_e_nao_so_converged(self):
        """Quem 'simplificar' de volta para `Converged()` quebra aqui."""
        fonte = open(os.path.join(os.path.dirname(AQUI), 'etapas',
                                  'energia.py'), encoding='utf-8').read()
        corpo = fonte.split('def dia(')[1]
        self.assertIn('if passo_sadio(dss):', corpo)
        self.assertNotIn('if dss.Solution.Converged():\n                break',
                         corpo)


if __name__ == '__main__':
    unittest.main()
