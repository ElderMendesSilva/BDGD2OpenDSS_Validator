# -*- coding: utf-8 -*-
"""Chave fechada em paralelo com regulador e um curto sobre o regulador.

O achado 32 ja tinha estabelecido que o regulador da BDGD nao se liga a
SSDMT: ele fica ENTRE DUAS CHAVES, e os dois PACs dele so existem na
UNSEMT. O que faltava ver e que a CPFL declara DEZENAS de chaves no MESMO
par de PACs — 58 no ESM01, 73 no RIB02 —, todas com `P_N_OPE='F'`.

Emitidas fechadas, ficam em paralelo com o regulador, cujo XHL e 0,04%. O
ramo paralelo tem cerca de 0,0007 ohm; o RegControl le subtensao, sobe o
tape ao maximo, e a corrente de circulacao explode.

MEDIDO NO ESM01 DA CPFL, V18, com as 58 chaves fechadas:
    tape 1,1000 (maximo), barra de 11,4 kV em 0,1012 pu,
    7.565 A no vao e 83.166 A no regulador, perda da subestacao 53,02%
com as 58 abertas:
    tape 1,0437, barra 0,9981 pu, perda 0,75%

Sao 8 reguladores na CPFL e ZERO nas outras seis bases — e sete deles sao
os sete alimentadores da CPFL com perda modelada acima de 2.500% na V18.

O QUE ESTES TESTES TRANCAM

1. A CHAVE SAI ABERTA NOS DOIS LUGARES. O estado da chave e emitido duas
   vezes de proposito: no `SwtControl` e no `Open Line.<nome> 1` do MASTER.
   Abrir so um dos dois nao abre nada com `controlmode=off`.

2. SO O PAR EXATO DO REGULADOR. Abrir chave que apenas ENCOSTA num PAC do
   regulador cortaria o tronco. O criterio e o par inteiro.

3. CHAVE JA ABERTA CONTINUA ABERTA, e nao entra na conta do aviso.

4. BASE SEM UNREMT NAO MUDA NADA. Seis das sete bases nao tem um caso
   sequer; nelas o arquivo tem de sair identico ao de antes.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import chaves                                # noqa: E402


class BDGDdeMentira:
    """UNSEMT e UNREMT em memoria, no formato do `ler_filtrado`."""

    def __init__(self, chaves_, regs):
        self.chaves = chaves_
        self.regs = regs

    def ler_filtrado(self, tabela, _campo, _valores, colunas):
        if tabela == 'UNREMT':
            if self.regs is None:
                raise RuntimeError('UNREMT indisponivel')
            linhas = self.regs
        else:
            linhas = self.chaves
        return {c: [l.get(c) for l in linhas] for c in colunas}


def sw(cod, p1, p2, ope='F'):
    return {'COD_ID': cod, 'PAC_1': p1, 'PAC_2': p2, 'CTMT': 'A',
            'FAS_CON': 'ABC', 'P_N_OPE': ope, 'COR_NOM': '', 'TIP_UNID': ''}


def gera(bd, tmp):
    return chaves.gerar(bd, ['A'], os.path.join(tmp, 'Chaves.dss'),
                        os.path.join(tmp, 'Controles.dss'),
                        barras={'x', 'y', 'z'})


class OBypassSaiAberto(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix='bypass_')

    def _le(self, arq):
        return open(os.path.join(self.tmp, arq), encoding='utf-8').read()

    def test_a_chave_no_par_do_regulador_sai_aberta(self):
        bd = BDGDdeMentira([sw('C1', 'x', 'y')], [{'PAC_1': 'x', 'PAC_2': 'y'}])
        n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(n, 1, 'a chave continua sendo emitida, so que aberta')
        self.assertIn('C1', abertas,
                      'sem entrar em `abertas` o MASTER nao emite '
                      'Open Line.C1 1, e com controlmode=off ela fecha')
        self.assertIn('State=Open', self._le('Controles.dss'))

    def test_o_par_invertido_tambem_conta(self):
        """A BDGD nao garante a ordem dos PACs entre as duas tabelas."""
        bd = BDGDdeMentira([sw('C1', 'y', 'x')], [{'PAC_1': 'x', 'PAC_2': 'y'}])
        _n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertIn('C1', abertas)

    def test_todas_as_chaves_do_par_saem_abertas(self):
        """No ESM01 sao 58; abrir uma so nao tira o curto."""
        bd = BDGDdeMentira([sw(f'C{k}', 'x', 'y') for k in range(58)],
                           [{'PAC_1': 'x', 'PAC_2': 'y'}])
        _n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(len(abertas), 58)


class OQueNaoPodeSerAberto(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix='bypass_')

    def test_chave_que_so_encosta_num_pac_continua_fechada(self):
        """Abrir por UM PAC em comum cortaria o tronco logo depois do
        regulador — o oposto do que se quer."""
        bd = BDGDdeMentira([sw('C1', 'x', 'z')], [{'PAC_1': 'x', 'PAC_2': 'y'}])
        _n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(abertas, [])

    def test_sem_regulador_nada_muda(self):
        bd = BDGDdeMentira([sw('C1', 'x', 'y')], [])
        _n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(abertas, [])

    def test_base_sem_UNREMT_nao_quebra(self):
        bd = BDGDdeMentira([sw('C1', 'x', 'y')], None)
        n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual((n, abertas), (1, []))

    def test_chave_ja_aberta_nao_entra_no_aviso(self):
        bd = BDGDdeMentira([sw('C1', 'x', 'y', ope='A')],
                           [{'PAC_1': 'x', 'PAC_2': 'y'}])
        _n, abertas, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(abertas, ['C1'])
        txt = open(os.path.join(self.tmp, 'Chaves.dss'), encoding='utf-8').read()
        self.assertNotIn('paralelo com um regulador', txt,
                         'chave que ja vinha aberta nao foi mudada por nos')


class OArquivoConta(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix='bypass_')

    def test_o_aviso_sai_no_proprio_arquivo(self):
        bd = BDGDdeMentira([sw('C1', 'x', 'y')], [{'PAC_1': 'x', 'PAC_2': 'y'}])
        gera(bd, self.tmp)
        txt = open(os.path.join(self.tmp, 'Chaves.dss'), encoding='utf-8').read()
        self.assertIn('1 chave(s) ABERTA(S)', txt)
        self.assertIn('C1', txt)

    def test_a_contagem_devolvida_nao_conta_as_linhas_de_aviso(self):
        """`len(ch) - 3` sabia de cor o tamanho do cabecalho, e errava assim
        que o arquivo ganhava uma linha."""
        bd = BDGDdeMentira([sw('C1', 'x', 'y'), sw('C2', 'x', 'z')],
                           [{'PAC_1': 'x', 'PAC_2': 'y'}])
        n, _ab, _il, _cr = gera(bd, self.tmp)
        self.assertEqual(n, 2)


if __name__ == '__main__':
    unittest.main()
