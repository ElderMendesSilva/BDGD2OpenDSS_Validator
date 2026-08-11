# -*- coding: utf-8 -*-
"""Validacao por balanco de energia — o criterio que usa MEDICAO.

`CTMT.ENE_XX` (injetada na cabeceira) e a energia faturada das UCs sao
grandezas de medidor. A diferenca e a perda TOTAL, tecnica mais nao tecnica.
O modelo produz so a tecnica, entao ela tem de caber dentro da total — e esse
limite e o unico teste do projeto que pode reprovar um modelo sozinho, sem
depender de referencia que seja saida de outro modelo.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
import valida_balanco as vb                       # noqa: E402

GDB = None


def setUpModule():
    global GDB
    GDB = fixture.gerar()          # regenera: as tabelas de UC sao novas


def _modelo(pct_por_alim):
    """Imita o energia_dia.json: perdas tecnicas em % por alimentador."""
    return [{'se': 'SE1', 'alimentadores':
             {k: {'perdas_pct': v} for k, v in pct_por_alim.items()}}]


class LeEnergiaMedida(unittest.TestCase):

    def setUp(self):
        self.inj, self.fat, self.sub, self.n_uc = vb.energia_medida(
            GDB, log=lambda *a: None)

    def test_injetada_vem_da_ctmt(self):
        self.assertAlmostEqual(self.inj['F1'], 12000.0, places=3)
        self.assertAlmostEqual(self.inj['F2'], 6000.0, places=3)

    def test_faturada_soma_bt_e_mt(self):
        """F1: duas UCs de BT (7.200 + 1.200) e uma de MT (1.200) = 9.600."""
        self.assertAlmostEqual(self.fat['F1'], 9600.0, places=3)
        self.assertAlmostEqual(self.fat['F2'], 5400.0, places=3)

    def test_conta_as_unidades(self):
        self.assertEqual(self.n_uc['F1'], 3)
        self.assertEqual(self.n_uc['F2'], 2)

    def test_traz_a_subestacao(self):
        self.assertEqual(self.sub['F1'], 'SE1')


class LimiteRigido(unittest.TestCase):
    """Nivel 1: tecnica do modelo <= total medida."""

    def setUp(self):
        self.inj, self.fat, self.sub, self.n_uc = vb.energia_medida(
            GDB, log=lambda *a: None)

    def _cruza(self, pcts):
        return vb.cruzar(_modelo(pcts), self.inj, self.fat, self.sub, self.n_uc)

    def test_perda_total_medida(self):
        linhas, _ = self._cruza({'F1': 5.0, 'F2': 3.0})
        d = {x['ctmt']: x for x in linhas}
        self.assertAlmostEqual(d['F1']['pct_total_medido'], 20.0, places=2)
        self.assertAlmostEqual(d['F2']['pct_total_medido'], 10.0, places=2)

    def test_modelo_dentro_do_limite_passa(self):
        linhas, _ = self._cruza({'F1': 5.0, 'F2': 3.0})
        self.assertFalse(any(x['viola_limite'] for x in linhas))

    def test_modelo_acima_da_total_medida_reprova(self):
        """25% de perda tecnica onde a total medida e 20% e impossivel:
        a tecnica esta CONTIDA na total."""
        linhas, _ = self._cruza({'F1': 25.0, 'F2': 3.0})
        d = {x['ctmt']: x for x in linhas}
        self.assertTrue(d['F1']['viola_limite'])
        self.assertFalse(d['F2']['viola_limite'])

    def test_residuo_e_a_nao_tecnica_implicita(self):
        linhas, _ = self._cruza({'F1': 5.0, 'F2': 3.0})
        d = {x['ctmt']: x for x in linhas}
        self.assertAlmostEqual(d['F1']['pct_nao_tecnica_implicita'], 15.0, 2)
        self.assertAlmostEqual(d['F2']['pct_nao_tecnica_implicita'], 7.0, 2)

    def test_residuo_negativo_acompanha_a_violacao(self):
        linhas, _ = self._cruza({'F1': 25.0})
        self.assertLess(linhas[0]['pct_nao_tecnica_implicita'], 0)
        self.assertTrue(linhas[0]['viola_limite'])

    def test_cobertura(self):
        """Quanto da perda total o modelo explica: 5 de 20 = 25%."""
        linhas, _ = self._cruza({'F1': 5.0})
        self.assertAlmostEqual(linhas[0]['cobertura'], 25.0, places=1)

    def test_alimentador_sem_par_e_contado_nao_ignorado(self):
        linhas, sem_par = self._cruza({'F1': 5.0, 'NAO_EXISTE': 9.0})
        self.assertEqual(len(linhas), 1)
        self.assertEqual(sem_par, 1)

    def test_casa_sem_depender_de_caixa(self):
        """O medidor do OpenDSS devolve o nome em minusculas."""
        linhas, sem_par = self._cruza({'f1': 5.0})
        self.assertEqual(sem_par, 0)
        self.assertEqual(linhas[0]['ctmt'], 'F1')


if __name__ == '__main__':
    unittest.main()
