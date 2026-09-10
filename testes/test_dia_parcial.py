# -*- coding: utf-8 -*-
"""Dia parcial não é o dia — a razão herda a validade do denominador.

O achado 29 mandou o classificador usar a perda do DIA em vez da do
instantâneo, e com razão. Só que o dia pode vir incompleto: passo que não
converge, ou que devolve mais geração do que existe (achado 64), sai da conta
— e o percentual continuava sendo publicado como se fosse o dia inteiro.

Medido na V33: **189 subestações** publicavam a perda do dia sobre um dia
parcial, a pior delas com **34,4% de cobertura** (33 dos 96 passos)
declarando 5,058%.

`None` devolve a decisão ao instantâneo, que é o que se conhece por inteiro,
e é conservador na direção certa — o instantâneo põe toda carga no pico e
fica ACIMA do dia.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    'val', os.path.join(RAIZ, 'etapas', 'validador.py'))
val = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(val)


def _monta(passos_ok, passos=96, pct=5.058):
    """Uma base com uma subestação, e a pasta dela dentro."""
    base = tempfile.mkdtemp()
    se = os.path.join(base, 'SE1')
    os.makedirs(se)
    with open(os.path.join(base, 'energia_dia.json'), 'w', encoding='utf-8') as fh:
        json.dump([{'se': 'SE1', 'passos_ok': passos_ok, 'passos': passos,
                    'perdas_pct': pct}], fh)
    val._CACHE_DIA.clear()
    return se


class TestDiaParcial(unittest.TestCase):

    def test_dia_inteiro_vale(self):
        self.assertEqual(val._perda_do_dia(_monta(96), 'SE1'), 5.058)

    def test_dia_parcial_nao_vale(self):
        """33 de 96 passos não autorizam a frase «a perda do dia é 5,058%»."""
        self.assertIsNone(val._perda_do_dia(_monta(33), 'SE1'))

    def test_falta_um_passo_ja_desqualifica(self):
        """Sem limiar arbitrário: ou cobre o dia, ou não é o dia."""
        self.assertIsNone(val._perda_do_dia(_monta(95), 'SE1'))

    def test_etapa_que_nao_rodou_continua_None(self):
        base = tempfile.mkdtemp()
        se = os.path.join(base, 'SE1')
        os.makedirs(se)
        val._CACHE_DIA.clear()
        self.assertIsNone(val._perda_do_dia(se, 'SE1'))


if __name__ == '__main__':
    unittest.main()
