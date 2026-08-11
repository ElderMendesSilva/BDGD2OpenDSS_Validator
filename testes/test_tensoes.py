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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss import tensoes                      # noqa: E402


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

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_bases_da_enel_sp(self):
        """A lista de BT sai do censo dos 159.061 transformadores da Enel SP.

        A Light declara 216 V em 1.659 transformadores e 400 V em 172 — os
        dois legitimos, os dois ausentes da lista. 1.831 transformadores
        recebem base de tensao errada.

        Passo 5 do PLANO.md: a lista tem de sair do censo da base sendo
        convertida, como o `linecodes._ajuste` ja faz para R1.
        """
        b = tensoes.bases(13.8)
        self.assertIn(0.216, b, '216 V — tensao de BT real da Light')
        self.assertIn(0.4, b, '400 V — tensao de BT real da Light')


if __name__ == '__main__':
    unittest.main()
