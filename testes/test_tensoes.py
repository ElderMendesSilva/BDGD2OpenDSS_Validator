# -*- coding: utf-8 -*-
"""Codigos de tensao e lista de bases.

Achados 2 e 5 de ACHADOS_GENERALIZACAO.md. Os testes marcados
`expectedFailure` documentam defeito CONHECIDO e ainda nao corrigido: a suite
fica verde, e no dia em que a correcao entrar o unittest reporta "unexpected
success" e obriga a atualizar o teste. E o oposto de deixar teste vermelho,
que todo mundo aprende a ignorar.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
from bdgd2dss import diagnostico, tensoes         # noqa: E402
from bdgd2dss.leitor import BDGD                  # noqa: E402

GDB = None


def setUpModule():
    global GDB
    GDB = fixture.garantir()


class CodigoParaKv(unittest.TestCase):

    def test_codigo_conhecido(self):
        self.assertEqual(tensoes.kv('49', 13.8), 13.8)
        self.assertEqual(tensoes.kv('72', 13.8), 34.5)
        self.assertEqual(tensoes.kv('84', 13.8), 88.0)

    def test_codigo_desconhecido_cai_no_padrao(self):
        """`67` aparece na Enel SP e em 132 alimentadores da Light, sem valor
        confirmado em nenhuma. Tem de cair no padrao, nao explodir."""
        self.assertEqual(tensoes.kv('67', 13.8), 13.8)
        self.assertEqual(tensoes.kv('67', 34.5), 34.5)

    def test_codigo_desconhecido_avisa_uma_vez_so(self):
        tensoes._avisados.clear()
        avisos = []
        tensoes.kv('999', 13.8, log=avisos.append, contexto='TESTE')
        tensoes.kv('999', 13.8, log=avisos.append, contexto='TESTE')
        self.assertEqual(len(avisos), 1, 'deve avisar uma unica vez por codigo')
        self.assertIn('999', avisos[0])
        self.assertIn('999', tensoes.desconhecidos())

    def test_codigo_vazio_ou_nulo(self):
        self.assertEqual(tensoes.kv(None, 13.8), 13.8)
        self.assertEqual(tensoes.kv('', 13.8), 13.8)
        self.assertEqual(tensoes.kv('   ', 13.8), 13.8)


class ListaDeBases(unittest.TestCase):

    def test_so_tensoes_de_linha(self):
        """A lista do Voltagebases e de tensoes de LINHA. Fase-neutro ali
        dentro faz o CalcVoltagebases casar barra de 127 V com base errada —
        foi o que colocou 2.805 barras acima de 1,10 pu na DALP."""
        b = tensoes.bases(13.8)
        for fn in (0.127, 0.12, 0.11, 0.0733):
            self.assertNotIn(fn, b, f'{fn} e fase-neutro, nao pode entrar')

    def test_inclui_os_niveis_pedidos(self):
        b = tensoes.bases(13.8, 88.0, 34.5)
        for kv in (13.8, 88.0, 34.5):
            self.assertIn(kv, b)

    def test_ordenada_e_sem_repeticao(self):
        b = tensoes.bases(13.8, 13.8, 0.22)
        self.assertEqual(b, sorted(set(b), reverse=True))

    def test_bases_da_propria_base_entram(self):
        """Achado 5, corrigido no passo 5: 0,216 e 0,4 sao tensoes reais da
        Light. Vindas do censo dela, entram no Voltagebases."""
        b = tensoes.bases(13.8, bt=[0.216, 0.4, 0.22])
        self.assertIn(0.216, b)
        self.assertIn(0.4, b)

    def test_o_piso_da_enel_sp_nao_some(self):
        """A base nova nao pode ELIMINAR tensoes: uma subestacao pode nao
        declarar 0,44 e ainda assim ter uma barra nela."""
        b = tensoes.bases(13.8, bt=[0.216])
        for x in (0.44, 0.38, 0.24, 0.23, 0.22, 0.208):
            self.assertIn(x, b)

    def test_bases_sem_censo_mantem_o_comportamento_antigo(self):
        self.assertEqual(tensoes.bases(13.8), tensoes.bases(13.8, bt=None))

    def test_o_censo_le_a_base_e_normaliza(self):
        """`censo_bt` le TEN_LIN_SE do fixture, passa pela regra de
        fase-neutro e devolve tensoes de LINHA. O fixture traz 0,22 normal,
        7,96 (que e MT, nao BT), 0,216 (real e ausente da lista antiga) e
        0,127 (fase-neutro de 220/127)."""
        from bdgd2dss import transformadores as tr
        tr._niveis_extra.clear()
        b = BDGD(GDB, verbose=False)
        v = tensoes.censo_bt(b, log=lambda *a: None)
        self.assertIn(0.216, v, '216 V e tensao de atendimento real')
        self.assertIn(0.22, v, '0,127 tem de ter virado 0,22')
        self.assertNotIn(0.127, v, 'fase-neutro nao entra no Voltagebases')
        self.assertTrue(all(x <= 1.0 for x in v),
                        'o censo de BT nao pode trazer tensao de MT')
        tr._niveis_extra.clear()


class ReferenciaDaPropriaBase(unittest.TestCase):
    """Achado 3: o limiar de REDE_EXTENSA saia do censo da Enel SP e a
    mensagem citava a mediana dela. Em Roraima, com alimentadores de 288 a
    424 km, isso classificava 4 de 20 subestacoes contra um numero que nao
    era daquela concessao."""

    def _resumos(self, km_por_alim, n=10):
        return [{'alimentadores': 2, 'km_MT': 2 * k}
                for k in ([km_por_alim] * n)]

    def test_mediana_sai_da_base(self):
        r = diagnostico.referencia_de(self._resumos(300.0))
        self.assertAlmostEqual(r['km_alim_mediana'], 300.0, places=3)

    def test_limiar_acompanha_a_mediana(self):
        """Roraima nao pode ser medida com o limiar da Enel SP: 300 km ali e
        o normal, nao a excecao."""
        rr = diagnostico.referencia_de(self._resumos(300.0))
        sp = diagnostico.referencia_de(self._resumos(8.9))
        self.assertGreater(rr['km_alim_alto'], 300.0)
        self.assertLess(sp['km_alim_alto'], 100.0)

    def test_amostra_pequena_cai_no_piso_declarado(self):
        r = diagnostico.referencia_de(self._resumos(300.0, n=3))
        self.assertIsNone(r['km_alim_mediana'])
        self.assertEqual(r['km_alim_alto'], diagnostico.KM_ALIM_ALTO)

    def test_rede_extensa_cita_a_mediana_certa(self):
        v = {'compila': True, 'converge': True, 'V_MT_mediana': 0.85,
             'perdas_pct': 5.0}
        resumo = {'alimentadores': 1, 'km_MT': 400.0, 'kW_BT': 0, 'kW_MT': 0}
        ref = diagnostico.referencia_de(self._resumos(8.9))
        causa, detalhe, _ = diagnostico.classificar(v, resumo, {}, ref)
        self.assertEqual(causa, 'REDE_EXTENSA')
        self.assertIn('8.9', detalhe.replace(',', '.'))
        self.assertNotIn('concessao: 8,9', detalhe)

    def test_normal_para_a_base_nao_vira_rede_extensa(self):
        """O caso de Roraima: 300 km por alimentador, com a mediana da
        propria base em 300 km, nao e anomalia nenhuma."""
        v = {'compila': True, 'converge': True, 'V_MT_mediana': 0.85,
             'perdas_pct': 5.0}
        resumo = {'alimentadores': 1, 'km_MT': 300.0, 'kW_BT': 0, 'kW_MT': 0}
        ref = diagnostico.referencia_de(self._resumos(300.0))
        causa, _, _ = diagnostico.classificar(v, resumo, {}, ref)
        self.assertNotEqual(causa, 'REDE_EXTENSA')

    def test_sem_referencia_mantem_o_comportamento_antigo(self):
        v = {'compila': True, 'converge': True, 'V_MT_mediana': 0.85,
             'perdas_pct': 5.0}
        resumo = {'alimentadores': 1, 'km_MT': 400.0, 'kW_BT': 0, 'kW_MT': 0}
        causa, detalhe, _ = diagnostico.classificar(v, resumo, {})
        self.assertEqual(causa, 'REDE_EXTENSA')
        self.assertIn('Enel SP', detalhe)


if __name__ == '__main__':
    unittest.main()
