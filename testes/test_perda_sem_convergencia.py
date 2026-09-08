# -*- coding: utf-8 -*-
"""Solução que não fechou não tem percentual — achado 33.

O percentual de perda é a razão de dois números da MESMA solução. Quando ela
diverge, as parcelas viram lixo mas a razão entre elas sai **plausível** — e
plausível é pior que absurdo, porque passa.

Medido na V32: a ENERGISA_R369/19778164 para em 500 iterações com
**7,9 × 10⁶³ kW** de perda e publica `perdas_pct = 12,16%`. Das 29 subestações
que não convergem, **19 publicam um percentual entre 0 e 15%** —
indistinguíveis, para quem agrega, de uma rede sadia. E `valida_perdas.py`,
`auditoria.py` e `relatorio.py` leem `perdas_pct` sem olhar `converge`.

O mesmo módulo já fazia isto para o NaN, três linhas acima do cálculo: `None`
diz "não sei", e o número inventado não avisa nada. Faltava o caso da
divergência.

As parcelas em kW ficam de propósito: 7,9e63 grita que algo estourou, e é por
elas que se acha o caso. O que sai é só a razão.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CAMINHO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'etapas', 'validador.py')


class TestOGuarda(unittest.TestCase):
    """Lido do fonte: o efeito só aparece com OpenDSS divergindo de verdade,
    que é caro de montar. O que se trava aqui é a existência do guarda."""

    def setUp(self):
        self.fonte = open(CAMINHO, encoding='utf-8').read()

    def test_zera_os_percentuais_quando_nao_converge(self):
        self.assertRegex(
            self.fonte,
            r"if not r\.get\('converge'\):\s*\n\s*for campo in \([^)]*"
            r"'perdas_pct'[^)]*'perdas_pct_dia'[^)]*'perdas_trafos_pct'",
            'o guarda de divergencia sumiu do validador')

    def test_o_guarda_vem_depois_da_perda_do_dia(self):
        """Zerar antes de `_perda_do_dia` não adianta: ela grava por cima."""
        i_dia = self.fonte.index("r['perdas_pct_dia'] = _perda_do_dia")
        i_guarda = self.fonte.index("if not r.get('converge'):\n        for campo")
        self.assertLess(i_dia, i_guarda,
                        'o guarda precisa rodar DEPOIS de gravar a perda do dia')

    def test_as_parcelas_em_kw_nao_sao_zeradas(self):
        """`perdas_kW` é o que denuncia o estouro — tem de sobreviver."""
        trecho = self.fonte[self.fonte.index("if not r.get('converge'):\n        for campo"):]
        alvo = trecho[:trecho.index('\n\n')]
        for campo in ('perdas_kW', 'P_gd_kW', 'P_fonte_kW', 'P_injetada_kW'):
            self.assertNotIn(campo, alvo,
                             f'{campo} nao pode ser zerado: e a evidencia')

    def test_a_linha_de_log_nao_imprime_None(self):
        """`r.get('perdas_pct','—')` devolve None quando a chave existe."""
        self.assertNotIn("perdas={r.get('perdas_pct','—')}", self.fonte)


class TestQuemConsome(unittest.TestCase):
    """Os três que liam o percentual sem olhar convergência."""

    def test_valida_perdas_trata_none(self):
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fonte = open(os.path.join(raiz, 'etapas', 'valida_perdas.py'),
                     encoding='utf-8').read()
        self.assertIn("perdas_pct'] is None", fonte,
                      'valida_perdas precisa continuar tratando o None')


if __name__ == '__main__':
    unittest.main()
