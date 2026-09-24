# -*- coding: utf-8 -*-
"""Sem alimentador comparavel, a ancora da ANEEL continua — achado 75.

Ate a V39, `valida_perdas` terminava em `SystemExit('nenhum alimentador casou
entre modelo e CTMT')` quando nenhum alimentador passava o corte de
declaracao (0,5% a 40%). O `validacao_perdas.json` nao era escrito, e com ele
sumia a comparacao com a perda regulatoria da ANEEL, que nao depende da CTMT.

Nove bases da V39 sairam assim. A Cosern declara `PERD_A4` na casa de 0,001%
em 342 alimentadores; o modelo dela perdia 10,4% so na MT — acima dos 9,16%
da ANEEL para o sistema INTEIRO — e nao reprovou, porque a ancora nao existia.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
import valida_perdas as vp                        # noqa: E402

GDB = 'Neoenergia_Cosern_40_2025-12-31_V11_teste.gdb'


def _modelo(pct=10.0):
    """Uma subestacao que fechou o dia, com dois alimentadores."""
    return [{'se': 'APD', 'passos': 96, 'passos_ok': 96,
             'alimentadores': {
                 '1769': {'kWh': 1000.0, 'kWh_perdas': 10.0 * pct,
                          'perdas_pct': pct},
                 '1795': {'kWh': 3000.0, 'kWh_perdas': 30.0 * pct,
                          'perdas_pct': pct}}}]


def _decl(pct):
    return {'1769': {'sub': 'APD', 'ene_ano': 1e6, 'perda_ano': 1e4 * pct,
                     'por_parcela': {'PERD_A4': 1e4 * pct}, 'parcelas': ['PERD_A4'],
                     'pct': pct},
            '1795': {'sub': 'APD', 'ene_ano': 1e6, 'perda_ano': 1e4 * pct,
                     'por_parcela': {'PERD_A4': 1e4 * pct}, 'parcelas': ['PERD_A4'],
                     'pct': pct}}


class TestAncoraSemPar(unittest.TestCase):

    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        with open(os.path.join(self.raiz, 'energia_dia.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(_modelo(), fh)

    def tearDown(self):
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _rodar(self, decl):
        argv = ['valida_perdas.py', self.raiz, GDB, '--parcelas', 'PERD_A4']
        with mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(vp, 'declarado', return_value=decl), \
                mock.patch.object(vp, '_agente', return_value='40'), \
                mock.patch('builtins.print'):
            vp.main()
        with open(os.path.join(self.raiz, 'validacao_perdas.json'),
                  encoding='utf-8') as fh:
            return json.load(fh)

    def test_declaracao_degenerada_nao_derruba_a_ancora(self):
        """O caso da Cosern: todo alimentador declara ~0,001%."""
        v = self._rodar(_decl(0.0012))
        self.assertFalse(v['comparacao_por_alimentador'])
        self.assertEqual(v['base_da_ancora'], 'comparados')
        ext = v['referencia_externa']
        self.assertAlmostEqual(ext['pct_modelo'], 10.0)
        self.assertTrue(ext['de_agente'])
        self.assertTrue(ext['reprova'], 'MT acima do sistema inteiro reprova')

    def test_sem_declaracao_nenhuma_a_ancora_usa_o_modelo_inteiro(self):
        v = self._rodar({})
        self.assertEqual(v['base_da_ancora'], 'modelo_inteiro')
        self.assertAlmostEqual(v['referencia_externa']['pct_modelo'], 10.0)
        self.assertEqual(v['populacao']['comparados'], 0)

    def test_com_pares_nada_muda(self):
        v = self._rodar(_decl(5.0))
        self.assertTrue(v['comparacao_por_alimentador'])
        self.assertEqual(v['base_da_ancora'], 'comparados')
        self.assertEqual(len(v['alimentadores']), 2)

    def test_o_systemexit_nao_voltou(self):
        with open(os.path.join(RAIZ, 'etapas', 'valida_perdas.py'),
                  encoding='utf-8') as fh:
            self.assertNotIn("SystemExit('nenhum alimentador casou", fh.read())


if __name__ == '__main__':
    unittest.main()
