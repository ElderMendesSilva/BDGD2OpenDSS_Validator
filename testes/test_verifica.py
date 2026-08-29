# -*- coding: utf-8 -*-
"""Convergir nao e atestado de plausibilidade fisica.

V23, COPELDIS2866: 71 subestacoes com veredicto `OK` — convergidas, sem NaN,
sem chave ilhada — publicando perda modelada de ate 10.309.528%. O que as
separava das outras 103 da MESMA base era tensao: mediana do `V_MT_min` em
0,082 pu contra 0,938 pu.

A fisica explica o numero inteiro. Carga de potencia constante a 0,08 pu puxa
~12x a corrente nominal para entregar a mesma potencia, e a perda joule, que
vai com o quadrado da corrente, sobe ~150x. Nao e defeito de cadastro nem de
condutor: e um modelo que o solver resolveu com a rede no chao, e o veredicto
nao tinha como dizer isso porque so sabia perguntar se a conta fechou.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import verifica as vf                                  # noqa: E402


def _m(**kw):
    """Uma medicao sadia, para o teste mexer so no que importa."""
    d = {'compila': True, 'convergiu': True, 'nan_com_pce': False,
         'nan_nos': 0, 'P_kW': 1000.0, 'perdas_kW': 50.0, 'V_mediana': 0.98}
    d.update(kw)
    return d


class TensaoImplausivelReprova(unittest.TestCase):

    def test_rede_no_chao_deixa_de_sair_OK(self):
        v = vf.veredicto(_m(V_mediana=0.082), None)
        self.assertTrue(v.startswith('TENSAO_IMPLAUSIVEL'), v)
        self.assertIn('0.08', v, 'o valor medido tem de aparecer no rotulo')

    def test_rede_sadia_continua_OK(self):
        self.assertEqual(vf.veredicto(_m(V_mediana=0.938), None), 'OK')

    def test_o_limiar_e_exclusivo(self):
        """Exatamente no limiar ainda passa: o corte e `menor que`."""
        self.assertEqual(vf.veredicto(_m(V_mediana=vf.LIMIAR_TENSAO), None),
                         'OK')
        self.assertTrue(vf.veredicto(_m(V_mediana=vf.LIMIAR_TENSAO - 0.001),
                                     None).startswith('TENSAO_IMPLAUSIVEL'))

    def test_qualquer_um_dos_dois_motores_basta(self):
        """Se um motor viu a rede no chao, o modelo nao serve."""
        v = vf.veredicto(_m(), _m(V_mediana=0.1))
        self.assertTrue(v.startswith('TENSAO_IMPLAUSIVEL'), v)
        self.assertIn('COM', v, 'o rotulo diz qual motor mediu')


class ADefeitoMaisGraveNaoPerdeORotulo(unittest.TestCase):
    """A rede cai junto com quase todo defeito grave, entao este veredicto
    roubaria o rotulo dos outros se viesse antes. A ordem e o que preserva o
    diagnostico: quem nao converge tem de continuar dizendo que nao converge.
    """

    def test_nao_converge_vence_tensao(self):
        v = vf.veredicto(_m(convergiu=False, iteracoes=15, V_mediana=0.05),
                         None)
        self.assertTrue(v.startswith('NAO_CONVERGE'), v)

    def test_nan_com_carga_vence_tensao(self):
        v = vf.veredicto(_m(nan_com_pce=True, nan_nos=42, V_mediana=0.05),
                         None)
        self.assertTrue(v.startswith('NAN['), v)

    def test_potencia_nan_vence_tensao(self):
        v = vf.veredicto(_m(P_kW=None, V_mediana=0.05), None)
        self.assertTrue(v.startswith('POTENCIA_NAN'), v)

    def test_nao_compila_vence_tudo(self):
        v = vf.veredicto(_m(compila=False, V_mediana=0.05), None)
        self.assertTrue(v.startswith('NAO_COMPILA'), v)


class SemMedidaNaoSeInventa(unittest.TestCase):

    def test_tensao_ausente_nao_reprova(self):
        """Modelo antigo nao tem `V_mediana`, e ausencia nao e defeito."""
        m = _m()
        del m['V_mediana']
        self.assertEqual(vf.veredicto(m, None), 'OK')

    def test_tensao_None_nao_reprova(self):
        """Subestacao sem barra energizada devolve None, e isso ja e contado
        por outros criterios — nao por este."""
        self.assertEqual(vf.veredicto(_m(V_mediana=None), None), 'OK')

    def test_motor_ausente_nao_quebra(self):
        self.assertEqual(vf.veredicto(None, _m()), 'OK')


class AMedianaVemDaMedicao(unittest.TestCase):

    def test_mede_devolve_mediana_das_barras_energizadas(self):
        v = [0.9, 0.95, 1.0, 0.001, 0.002]      # as duas ultimas sao mortas
        r = vf._mede(v, ['a.1', 'b.1', 'c.1', 'd.1', 'e.1'],
                     -1000.0, 50.0, True, 3)
        self.assertEqual(r['V_mediana'], 0.95,
                         'barra abaixo de 0,01 pu nao entra na conta')

    def test_sem_barra_viva_a_mediana_e_None(self):
        r = vf._mede([0.001, 0.002], ['a.1', 'b.1'], -1.0, 0.1, True, 1)
        self.assertIsNone(r['V_mediana'])

    def test_a_mediana_nao_se_deixa_puxar_por_uma_ponta(self):
        """O ponto de usar mediana e este: uma barra ruim no fim de um ramal
        nao pode condenar a subestacao inteira."""
        v = [0.98] * 50 + [0.04]
        r = vf._mede(v, ['b%d.1' % i for i in range(51)],
                     -1000.0, 50.0, True, 3)
        self.assertEqual(r['V_min'], 0.04)
        self.assertEqual(r['V_mediana'], 0.98)
        self.assertEqual(vf.veredicto(dict(r, compila=True), None), 'OK')


if __name__ == '__main__':
    unittest.main()
