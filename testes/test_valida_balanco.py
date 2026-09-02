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
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
import valida_balanco as vb                       # noqa: E402

GDB = None


def setUpModule():
    global GDB
    # `garantir`, nao `gerar`. O `gerar` reescrevia a .gdb a cada execucao e o
    # GDAL nao produz os mesmos bytes duas vezes: rodar a suite deixava dois
    # .gdbtable modificados e a arvore SUJA. Isso corrompe a procedencia — o
    # `_procedencia.json` marca `sujo` para dizer qual codigo gerou o modelo,
    # e um `sujo` que so significa "a suite rodou" nao diz nada. O `garantir`
    # ja regera quando o `fixture.py` muda, que e o caso que importa.
    GDB = fixture.garantir()


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


class MedicaoDegenerada(unittest.TestCase):
    """Achado 10: violar o limite fisico pode ser duas coisas diferentes.

    Ou o modelo esta alto demais, ou a MEDICAO daquele alimentador nao fecha
    — energia faturada maior que a injetada na cabeceira, que e impossivel de
    medir e portanto erro de cadastro. Nos dois casos `pct_tecnica > pct_total`
    fica verdadeiro, e o codigo de hoje nao distingue.

    Separar os dois foi o corte que mudou a leitura de todo o levantamento:

        base             violam   degenerada   violacao real
        Equatorial PA   124 (20,0%)     121      5 (0,8%)
        Light           165 (10,7%)     196      4 (0,3%)
        Enel SP         482 (30,6%)      29    458 (29,1%)

    Sem o corte, a Equatorial pareceria 25x pior do que e e a Enel SP
    apareceria como diferenca de grau, nao de natureza. F3 do fixture fatura
    6.000 kWh com 4.800 injetados: e o caso, em miniatura.
    """

    def setUp(self):
        self.inj, self.fat, self.sub, self.n_uc = vb.energia_medida(
            GDB, log=lambda *a: None)

    def _cruza(self, pcts):
        return vb.cruzar(_modelo(pcts), self.inj, self.fat, self.sub, self.n_uc)

    def test_perda_total_medida_fica_negativa(self):
        linhas, _ = self._cruza({'F3': 1.0})
        self.assertAlmostEqual(linhas[0]['pct_total_medido'], -25.0, places=2)

    def test_qualquer_modelo_reprova_num_alimentador_assim(self):
        """Ate 0,01% de perda tecnica viola — e nao ha modelo que nao viole.
        A reprovacao nao carrega informacao nenhuma sobre a conversao."""
        for pct in (0.01, 1.0, 50.0):
            linhas, _ = self._cruza({'F3': pct})
            self.assertTrue(linhas[0]['viola_limite'],
                            f'{pct}% deveria violar num alimentador degenerado')

    def test_cobertura_nao_e_calculada_quando_a_medida_nao_fecha(self):
        """Uma protecao que ja existe: dividir por perda total negativa daria
        cobertura negativa, que nao quer dizer nada."""
        linhas, _ = self._cruza({'F3': 1.0})
        self.assertIsNone(linhas[0]['cobertura'])

    def test_a_contagem_de_violacoes_de_hoje_mistura_as_duas_causas(self):
        """Mede a confusao no fixture: 1 de 3 alimentadores viola, e nenhuma
        das violacoes e defeito de modelo."""
        linhas, _ = self._cruza({'F1': 5.0, 'F2': 3.0, 'F3': 0.01})
        viol = [x for x in linhas if x['viola_limite']]
        self.assertEqual(len(viol), 1)
        self.assertEqual(viol[0]['ctmt'], 'F3')
        self.assertLess(viol[0]['pct_total_medido'], 0,
                        'o unico que viola e o que nao tem medida coerente')

    def test_separa_cadastro_de_modelo(self):
        """A separacao que sustenta o achado 10, agora no codigo de producao
        e nao num script de diagnostico fora do repositorio."""
        linhas, _ = self._cruza({'F1': 5.0, 'F2': 3.0, 'F3': 0.01})
        d = {x['ctmt']: x for x in linhas}
        self.assertTrue(d['F3']['medida_degenerada'])
        self.assertTrue(d['F3']['faturado_maior_que_injetado'])
        self.assertFalse(d['F3']['viola_de_verdade'])
        self.assertFalse(d['F1']['medida_degenerada'])
        self.assertFalse(d['F1']['faturado_maior_que_injetado'])
        self.assertEqual(sum(1 for x in linhas if x['viola_de_verdade']), 0)

    def test_modelo_alto_num_alimentador_de_medida_boa_viola_de_verdade(self):
        """O contraste: F1 mede 20% de perda total, referencia utilizavel.
        25% de perda tecnica ali e defeito de modelo, e tem de ser contado."""
        linhas, _ = self._cruza({'F1': 25.0})
        self.assertTrue(linhas[0]['viola_de_verdade'])
        self.assertFalse(linhas[0]['medida_degenerada'])

    def test_o_piso_e_parametro_e_nao_numero_solto(self):
        """O piso de 2% e escolha, nao lei. Fica exposto para que outra base
        possa ser medida com outro criterio — e para que a escolha apareca."""
        self.assertEqual(vb.PISO_MEDIDA, 2.0)
        linhas, _ = self._cruza({'F1': 25.0})
        self.assertTrue(linhas[0]['viola_de_verdade'])
        linhas, _ = vb.cruzar(_modelo({'F1': 25.0}), self.inj, self.fat,
                              self.sub, self.n_uc, piso=50.0)
        self.assertTrue(linhas[0]['medida_degenerada'],
                        'com piso de 50%, os 20% de F1 deixam de servir')
        self.assertFalse(linhas[0]['viola_de_verdade'])


if __name__ == '__main__':
    unittest.main()
