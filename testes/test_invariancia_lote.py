# -*- coding: utf-8 -*-
"""O lote e otimizacao, e otimizacao nao pode mudar a saida.

A leitura filtrada por CTMT e o gargalo do conversor: o `OpenFileGDB` nao tem
indice em `CTMT`, entao toda leitura varre a camada inteira. Medido na
Cemig-D, cuja SSDMT tem 5,6 milhoes de linhas: UMA leitura custa 88,7 s
trazendo 76 mil linhas e 152,0 s trazendo 1,25 milhao — o preco e da
varredura, nao do dado. Amortizar a mesma varredura sobre 100 subestacoes em
vez de 10 vale 6x.

O QUE ESTES TESTES PROTEGEM. O lote le um SUPERCONJUNTO e depois filtra o
alvo exato. Se o filtro errar, o modelo passa a conter rede de outra
subestacao — e o argumento do artigo e fidelidade a BDGD. Entao: mudar o
tamanho do lote nao pode mudar UMA LINHA do que sai.

Conferido tambem de ponta a ponta, em 8 subestacoes da Cemig-D convertidas
com composicoes de lote diferentes: 142 arquivos .dss identicos, zero
diferentes. Estes testes trancam a invariancia onde ela mora, para que a
proxima otimizacao nao a quebre em silencio.
"""
import os
import sys
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
from bdgd2dss.leitor import BDGD, txt                 # noqa: E402
import fixture                                        # noqa: E402

GDB = None
COLS = ['COD_ID', 'PAC_1', 'PAC_2', 'COMP', 'CTMT']


def setUpModule():
    global GDB
    GDB = fixture.garantir()


def _iguais(a, b):
    """Mesmas chaves, mesmo comprimento, mesmo conteudo, mesma ORDEM."""
    if set(a) != set(b):
        return False
    for k in a:
        x, y = np.asarray(a[k]), np.asarray(b[k])
        if len(x) != len(y):
            return False
        if not all(txt(i) == txt(j) for i, j in zip(x, y)):
            return False
    return True


class OLoteNaoMudaOQueSai(unittest.TestCase):

    def setUp(self):
        self.b = BDGD(GDB, verbose=False)

    def _le(self, alvo, lote=None):
        if lote:
            self.b.abrir_lote(lote)
        try:
            return self.b.ler_filtrado('SSDMT', 'CTMT', alvo, COLS)
        finally:
            self.b.fechar_lote()

    def test_com_lote_e_sem_lote_dao_o_mesmo(self):
        """O caminho do lote e o do disco tem de convergir."""
        self.assertTrue(_iguais(self._le({'F1'}),
                                self._le({'F1'}, lote={'F1'})))

    def test_o_tamanho_do_lote_nao_muda_o_resultado(self):
        """Lote maior le um superconjunto maior — e filtra igual."""
        so_ele = self._le({'F1'}, lote={'F1'})
        no_meio = self._le({'F1'}, lote={'F1', 'F2', 'F3'})
        self.assertTrue(_iguais(so_ele, no_meio))

    def test_a_ordem_das_linhas_nao_muda(self):
        """Ordem diferente nao e erro de valor, mas e diferenca de arquivo:
        dois modelos que deveriam ser identicos deixariam de ser."""
        a = self._le({'F1'}, lote={'F1'})
        b = self._le({'F1'}, lote={'F3', 'F2', 'F1'})
        self.assertEqual([txt(x) for x in a['COD_ID']],
                         [txt(x) for x in b['COD_ID']])

    def test_nao_vaza_rede_de_outro_alimentador(self):
        """O que o lote traz a mais NAO pode chegar ao modelo. Se vazar, a
        subestacao ganha rede que nao e dela — e o argumento de fidelidade
        a BDGD cai junto."""
        col = self._le({'F1'}, lote={'F1', 'F2', 'F3'})
        self.assertEqual({txt(x) for x in col['CTMT']}, {'F1'})

    def test_alimentador_sem_rede_devolve_vazio_com_ou_sem_lote(self):
        for lote in (None, {'F1', 'F2', 'F3'}):
            col = self._le({'NAO_EXISTE'}, lote=lote)
            self.assertEqual(len(col['COD_ID']), 0)

    def test_pedir_fora_do_lote_cai_no_disco_e_acerta_igual(self):
        """`ler_filtrado` so serve do cache quando o alvo esta CONTIDO no
        lote. Fora disso vai ao disco — e tem de dar o mesmo."""
        self.b.abrir_lote({'F2'})
        try:
            fora = self.b.ler_filtrado('SSDMT', 'CTMT', {'F1'}, COLS)
        finally:
            self.b.fechar_lote()
        self.assertTrue(_iguais(fora, self._le({'F1'})))


if __name__ == '__main__':
    unittest.main()
