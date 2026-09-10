# -*- coding: utf-8 -*-
"""O veredicto de tensão implausível — achados 1, 60 e 61.

Este veredicto já existiu. Nasceu no achado 1 (28/08/2026), quando 71
subestações da COPELDIS2866 saíam `OK` publicando perda de até 10.309.528%
com `V_MT_min` mediano em 0,082 pu, e **sumiu** quando o classificador
graduado dos achados 25 e 29 substituiu o código antigo — sem herdeiro e sem
que ninguém notasse.

A falta dele foi medida em 08/09/2026: das 18 subestações que continuavam
`REGULADOR_SATURADO` na V31, cinco tinham tensão mediana abaixo de 0,5 pu, a
pior em 0,109, e carregavam o mesmo rótulo de uma subestação em 0,90 pu.

O que estes testes protegem é a **precedência**. `CARGA_ALTA`, `REDE_EXTENSA`
e `REGULADOR_SATURADO` costumam ser verdade nessas subestações — a demanda
excede mesmo, o alimentador é longo mesmo, os reguladores estão no tape máximo
mesmo. Só que os três descrevem o sintoma, e quem lê o rótulo vai depurar a
coisa errada. Se alguém reordenar a cascata, a suíte tem de quebrar aqui.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import diagnostico as d                      # noqa: E402


def classificar(vmed, resumo=None, extra=None, **troca):
    """Uma subestação saudável em tudo, menos no que o teste mexe."""
    v = {'compila': True, 'converge': True, 'V_MT_mediana': vmed,
         'perdas_pct': 40.0, 'cargas_sem_tensao': 0, 'n_cargas': 1000}
    v.update(troca)
    return d.classificar(v, resumo or {'alimentadores': 1, 'km_MT': 10},
                         extra or {})


class TestCorte(unittest.TestCase):

    def test_abaixo_de_meio_pu_e_implausivel(self):
        causa, det, acionavel = classificar(0.109)
        self.assertEqual(causa, 'TENSAO_IMPLAUSIVEL')
        self.assertIn('0.109', det)
        self.assertTrue(acionavel)

    def test_o_detalhe_diz_por_que_o_numero_nao_serve(self):
        """O rótulo tem de dizer o que fazer, e aqui é: não agregue."""
        _, det, _ = classificar(0.2)
        self.assertIn('agregado', det)

    def test_logo_acima_do_corte_nao_e_implausivel(self):
        """0,5 é o corte; 0,51 pu é subtensão grave, e tem outro nome."""
        self.assertNotEqual(classificar(0.51)[0], 'TENSAO_IMPLAUSIVEL')

    def test_o_corte_e_exclusivo(self):
        """Exatamente 0,5 pu não é implausível — o teste é `<`, não `<=`."""
        self.assertNotEqual(classificar(d.V_IMPLAUSIVEL)[0],
                            'TENSAO_IMPLAUSIVEL')

    def test_tensao_boa_nao_dispara(self):
        self.assertEqual(classificar(1.0, perdas_pct=2.0)[0], 'OK')


class TestPrecedencia(unittest.TestCase):
    """Os três rótulos que ela tira da frente. Todos SÃO verdade aqui."""

    def test_vence_regulador_saturado(self):
        """O caso do achado 60: 5 subestações com o rótulo errado na V31."""
        extra = {'reg_total': 19, 'reg_saturados': 19}
        self.assertEqual(classificar(0.109, extra=extra)[0],
                         'TENSAO_IMPLAUSIVEL')
        # e o rótulo antigo continua valendo quando a tensão é só baixa
        self.assertEqual(classificar(0.88, extra=extra)[0],
                         'REGULADOR_SATURADO')

    def test_vence_rede_extensa(self):
        """601 km por alimentador é verdade na EQUATORIAL6072/5002404."""
        longo = {'alimentadores': 4, 'km_MT': 2405.0}
        self.assertEqual(classificar(0.109, resumo=longo)[0],
                         'TENSAO_IMPLAUSIVEL')
        self.assertEqual(classificar(0.88, resumo=longo)[0], 'REDE_EXTENSA')

    def test_vence_carga_alta(self):
        extra = {'mva_instalado': 1.0}
        cheia = {'alimentadores': 1, 'km_MT': 10, 'kW_MT': 5000}
        self.assertEqual(classificar(0.109, resumo=cheia, extra=extra)[0],
                         'TENSAO_IMPLAUSIVEL')
        self.assertEqual(classificar(0.88, resumo=cheia, extra=extra)[0],
                         'CARGA_ALTA')

    def test_nao_vence_carga_sem_tensao(self):
        """Rede que não chega à fonte é outra história, e vem antes.

        Numa subestação ilhada a tensão mediana também despenca, e ali o que
        descreve o problema é a carga morta — não adianta dizer que o número
        não serve quando a causa já tem nome e é acionável.
        """
        causa, _, _ = classificar(0.109, cargas_sem_tensao=1000,
                                  n_cargas=1000)
        self.assertEqual(causa, 'SUBESTACAO_ILHADA')

    def test_nao_vence_modelo_quebrado(self):
        self.assertEqual(classificar(0.109, compila=False)[0],
                         'MODELO_QUEBRADO')


class TestContrato(unittest.TestCase):

    def test_esta_em_acionavel(self):
        """A ação é nossa: não publicar o número dessa subestação."""
        self.assertIn('TENSAO_IMPLAUSIVEL', d.ACIONAVEL)

    def test_nao_entra_no_conjunto_de_sem_tensao(self):
        """`SEM_TENSAO` é o grupo que reproduz a contagem velha do achado 25."""
        self.assertNotIn('TENSAO_IMPLAUSIVEL', d.SEM_TENSAO)



class TestSoValeComTensaoRuim(unittest.TestCase):
    """`REDE_EXTENSA` e `REGULADOR_SATURADO` explicam queda de tensão — e
    com a tensão adequada não há queda a explicar (achado 62-B).

    Medido na V32: 3 das 11 `REDE_EXTENSA` e 5 das 12 `REGULADOR_SATURADO`
    tinham tensão acima de 0,90 pu, e a NEOENERGIA47/SBC estava em 1,036 pu —
    acima da nominal — carimbada como rede extensa demais para sustentar
    tensão.
    """

    LONGO = {'alimentadores': 1, 'km_MT': 5000.0}
    SATURADO = {'reg_total': 9, 'reg_saturados': 9}

    def test_rede_extensa_com_tensao_boa_vira_perda_alta(self):
        causa, _, _ = classificar(0.938, resumo=self.LONGO, perdas_pct=26.7)
        self.assertEqual(causa, 'PERDA_ALTA')

    def test_rede_extensa_com_tensao_ruim_continua_valendo(self):
        causa, _, _ = classificar(0.85, resumo=self.LONGO, perdas_pct=26.7)
        self.assertEqual(causa, 'REDE_EXTENSA')

    def test_regulador_saturado_com_tensao_boa_vira_perda_alta(self):
        """O caso da NEOENERGIA385/UBA02: 0,938 pu e perda de 16,2%."""
        causa, _, _ = classificar(0.938, extra=self.SATURADO, perdas_pct=16.2)
        self.assertEqual(causa, 'PERDA_ALTA')

    def test_regulador_saturado_com_tensao_ruim_continua_valendo(self):
        causa, _, _ = classificar(0.85, extra=self.SATURADO, perdas_pct=16.2)
        self.assertEqual(causa, 'REGULADOR_SATURADO')

    def test_tensao_acima_da_nominal_nunca_e_rede_extensa(self):
        """1,036 pu não é problema de queda de tensão, por definição."""
        self.assertEqual(
            classificar(1.036, resumo=self.LONGO, perdas_pct=26.7)[0],
            'PERDA_ALTA')

    def test_carga_alta_nao_ganhou_a_trava(self):
        """Ela afirma algo sobre CAPACIDADE, não sobre tensão."""
        cheia = {'alimentadores': 1, 'km_MT': 10, 'kW_MT': 5000}
        causa, _, _ = classificar(0.989, resumo=cheia,
                                  extra={'mva_instalado': 1.0}, perdas_pct=21.3)
        self.assertEqual(causa, 'CARGA_ALTA')

    def test_nenhuma_delas_vira_OK(self):
        """A perda continua reprovando: é relabelagem, não aprovação."""
        for r, e in ((self.LONGO, {}), ({'alimentadores': 1, 'km_MT': 10},
                                        self.SATURADO)):
            self.assertNotEqual(classificar(0.938, resumo=r, extra=e,
                                            perdas_pct=26.7)[0], 'OK')


if __name__ == '__main__':
    unittest.main()
