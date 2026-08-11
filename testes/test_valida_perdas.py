# -*- coding: utf-8 -*-
"""Cruzamento com o PERD_* declarado — e o erro de METODO que ele carrega.

Achado 9 de ACHADOS_GENERALIZACAO.md, com a correcao registrada no achado 10.

A leitura de 10/08 dizia que o vies "troca de sinal entre distribuidoras"
(Enel SP 1,88x, Light 0,19x). Era verdadeira como observacao e errada como
diagnostico: em 11/08 a validacao por medicao mostrou que a Enel SP tinha
defeito de dado localizado, e que parte do resto era erro nosso de metodo.

O erro de metodo e este arquivo. O modelo roda com `--bt agregado`: nao ha
rede de baixa tensao, e portanto ele nao produz perda de BT. Mesmo assim a
comparacao cobra dele `PERD_A4 + PERD_B + PERD_A4_B`. Estamos exigindo do
modelo uma parcela que ele estruturalmente nao gera, e depois lendo a
diferenca como discordancia entre modelo e declaracao.

Os testes verdes fixam o que o codigo faz hoje e MEDEM o tamanho do erro. O
ultimo enuncia o requisito do passo 5.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
import valida_perdas as vp                        # noqa: E402
from bdgd2dss.leitor import BDGD, num, txt        # noqa: E402

GDB = None


def setUpModule():
    global GDB
    GDB = fixture.garantir()


class PerdaDeclaradaNaCTMT(unittest.TestCase):
    """O que `declarado` le, e como compoe.

    No fixture, F1 declara PERD_A4=100, PERD_B=80 e PERD_A4_B=20 sobre
    12.000 kWh injetados. Os numeros sao redondos de proposito: qualquer
    mudanca na composicao aparece como fracao exata.
    """

    def setUp(self):
        self.d = vp.declarado(GDB)

    def test_as_parcelas_sao_as_tres_que_o_modelo_reproduziria(self):
        """PERD_MED (medicao) e PERD_A3a (subtransmissao) ficam de fora — a
        primeira nao e eletrica, a segunda esta acima do recorte."""
        self.assertEqual(vp.PARCELAS, ['PERD_A4', 'PERD_B', 'PERD_A4_B'])

    def test_soma_as_tres_parcelas(self):
        self.assertAlmostEqual(self.d['F1']['perda_ano'], 200.0, places=3)
        self.assertAlmostEqual(self.d['F2']['perda_ano'], 100.0, places=3)

    def test_percentual_e_sobre_a_energia_anual(self):
        """Razao adimensional: e o que torna comparavel um dia simulado com
        uma declaracao anual."""
        self.assertAlmostEqual(self.d['F1']['pct'], 100 * 200.0 / 12000, 4)
        self.assertAlmostEqual(self.d['F2']['pct'], 100 * 100.0 / 6000, 4)

    def test_traz_a_subestacao(self):
        self.assertEqual(self.d['F1']['sub'], 'SE1')

    def test_alimentador_sem_energia_nao_vira_percentual(self):
        """Divisao por zero viraria razao infinita e destruiria a mediana."""
        for v in self.d.values():
            self.assertTrue(v['pct'] is None or v['ene_ano'] > 0)


class ErroDeMetodoNaComparacao(unittest.TestCase):
    """Mede o tamanho do que estamos cobrando a mais.

    Nao e argumento retorico: e uma razao calculavel a partir da propria
    CTMT, alimentador a alimentador, sem rodar modelo nenhum.
    """

    def setUp(self):
        self.d = vp.declarado(GDB)

    def _pct(self, cod, parcelas):
        """A mesma conta de `declarado`, restrita a algumas parcelas."""
        b = BDGD(GDB, verbose=False)
        c = b.ler('CTMT', ['COD_ID'] + parcelas
                  + [f'ENE_{i:02d}' for i in range(1, 13)])
        i = [txt(x).strip().upper() for x in c['COD_ID']].index(cod)
        ene = sum(num(c[f'ENE_{k:02d}'][i]) for k in range(1, 13))
        return 100.0 * sum(num(c[p][i]) for p in parcelas) / ene

    def test_a_parcela_de_bt_dobra_o_que_se_cobra_do_modelo(self):
        """F1: PERD_A4 sozinho da 0,833%; com PERD_B e PERD_A4_B da 1,667%.

        O modelo rodado com `--bt agregado` so pode responder pelo primeiro.
        Cobrar o segundo o faz parecer subestimar por fator 2 — e foi assim
        que as bases que PASSAM no teste fisico apareceram com razao de 0,15x
        a 0,60x contra o declarado.
        """
        so_a4 = self._pct('F1', ['PERD_A4'])
        tudo = self.d['F1']['pct']
        self.assertAlmostEqual(so_a4, 100 * 100.0 / 12000, places=4)
        self.assertAlmostEqual(tudo / so_a4, 2.0, places=3)

    def test_o_fator_varia_por_alimentador(self):
        """Nao da para consertar com uma constante global: a proporcao de
        PERD_B muda de alimentador para alimentador."""
        f1 = self.d['F1']['pct'] / self._pct('F1', ['PERD_A4'])
        f3 = self.d['F3']['pct'] / self._pct('F3', ['PERD_A4'])
        self.assertNotAlmostEqual(f1, f3, places=2)

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_deveria_cobrar_so_o_que_o_modelo_gera(self):
        """O requisito do passo 5: as parcelas comparadas tem de acompanhar o
        modo de BT com que o modelo foi gerado.

        Com `--bt agregado` a comparacao e contra PERD_A4 apenas; com
        `--bt completo` volta a ser contra as tres. Hoje `declarado` nao
        aceita escolha e sempre soma as tres.
        """
        d = vp.declarado(GDB, parcelas=['PERD_A4'])
        self.assertAlmostEqual(d['F1']['pct'], 100 * 100.0 / 12000, places=4)
        self.assertAlmostEqual(d['F1']['perda_ano'], 100.0, places=3)


if __name__ == '__main__':
    unittest.main()
