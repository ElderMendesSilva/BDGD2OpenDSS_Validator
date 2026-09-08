# -*- coding: utf-8 -*-
"""O veredicto de tensão implausível — achados 1, 31 e 32.

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
        """O caso do achado 31: 5 subestações com o rótulo errado na V31."""
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


if __name__ == '__main__':
    unittest.main()
