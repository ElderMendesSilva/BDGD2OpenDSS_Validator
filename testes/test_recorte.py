# -*- coding: utf-8 -*-
"""O recorte por subestação separa o que a rede declara junto?

O achado 12 mostrou que a fragmentação é característica POR DISTRIBUIDORA: 40
de 76 bases com mediana ZERO de ramos isolados por km, e a Light com 45,8. O
conversor é o mesmo para as 97, então o gatilho está no dado — ou na interação
dele com uma premissa nossa.

A premissa suspeita é o recorte: o `converter.py` monta um modelo por
subestação e filtra a SSDMT pelos CTMTs daquela SE. Trecho de CTMT alheio fica
de fora, e o que vinha depois dele vira ramo isolado.

Um PAC tocado por trechos de duas subestações é um ponto de corte. Contá-los é
o teste, e ele não precisa de OpenDSS.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'diagnosticos'))
import recorte                                          # noqa: E402


class _BDGDFalsa:
    """`ctmt` = [(cod, sub)], `ssdmt` = [(pac1, pac2, ctmt)]."""

    def __init__(self, ctmt, ssdmt):
        import numpy as np
        self._c = {'COD_ID': np.array([x[0] for x in ctmt], dtype=object),
                   'SUB': np.array([x[1] for x in ctmt], dtype=object)}
        self._m = {'PAC_1': np.array([x[0] for x in ssdmt], dtype=object),
                   'PAC_2': np.array([x[1] for x in ssdmt], dtype=object),
                   'CTMT': np.array([x[2] for x in ssdmt], dtype=object)}

    def ler(self, camada, cols):
        return self._c if camada == 'CTMT' else self._m


def _mede(ctmt, ssdmt):
    real = recorte.BDGD
    recorte.BDGD = lambda *a, **k: _BDGDFalsa(ctmt, ssdmt)
    try:
        return recorte.cortes_da_base('/qualquer.gdb')
    finally:
        recorte.BDGD = real


class OPontoDeCorteEUmPACDeDuasSubestacoes(unittest.TestCase):

    def test_rede_de_uma_SE_so_nao_tem_corte(self):
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 0)
        self.assertEqual(r['pacs'], 3)

    def test_PAC_compartilhado_por_duas_SEs_e_corte(self):
        """`p2` liga um trecho da SE_A a um da SE_B. O conversor monta as duas
        separadamente, e o que estiver do outro lado de `p2` some de cada uma."""
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_B')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 1)
        self.assertAlmostEqual(r['pct_pacs_multi_se'], 100 / 3, places=2)

    def test_CTMTs_DIFERENTES_da_MESMA_SE_nao_sao_corte(self):
        """Este é o falso positivo que invalidaria a medida: o recorte é por
        SUBESTAÇÃO, não por alimentador. Dois CTMTs da mesma SE entram juntos
        no mesmo modelo, e o PAC entre eles não separa nada."""
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 0)

    def test_trecho_com_CTMT_desconhecido_e_contado_e_ignorado(self):
        """CTMT que não está na tabela CTMT não tem SE, e chutar uma seria
        inventar topologia. Fica de fora da conta e é RELATADO."""
        r = _mede([('C1', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p9', 'p8', 'FANTASMA')])
        self.assertEqual(r['trechos_sem_ctmt_conhecido'], 1)
        self.assertEqual(r['pacs'], 2, 'os PACs do trecho orfao nao entram')

    def test_PAC_vazio_nao_vira_no(self):
        r = _mede([('C1', 'SE_A')], [('p1', '', 'C1'), ('', 'p2', 'C1')])
        self.assertEqual(r['pacs'], 2)

    def test_tres_SEs_no_mesmo_PAC_conta_uma_vez(self):
        r = _mede([('C1', 'A'), ('C2', 'B'), ('C3', 'C')],
                  [('x', 'p', 'C1'), ('p', 'y', 'C2'), ('p', 'z', 'C3')])
        self.assertEqual(r['pacs_multi_se'], 1)
        self.assertEqual(r['subestacoes_no_ctmt'], 3)

    def test_base_vazia_nao_derruba(self):
        r = _mede([], [])
        self.assertEqual((r['pacs'], r['pacs_multi_se']), (0, 0))
        self.assertEqual(r['pct_pacs_multi_se'], 0.0)


if __name__ == '__main__':
    unittest.main()
