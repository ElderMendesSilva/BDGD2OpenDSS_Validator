# -*- coding: utf-8 -*-
"""Achado 50: regulador com UMA ponta fora da rede compila e nao regula nada.

O achado 28 ja tratava o regulador com as DUAS pontas fora: vira ilha de duas
barras, a matriz fica singular e a tensao sai NaN. Esse e descartado.

Uma ponta so e pior, porque nao aparece: o regulador COMPILA, entra no
arquivo, o `Show Meters` conta ele, e a barra da ponta solta e tocada apenas
por ele. Nao ha caminho para a corrente, o tape sobe ate o maximo e fica la, e
o tronco segue sem apoio nenhum de tensao.

OS PACs DE JUSANTE NAO EXISTEM. Foi conferido camada a camada: nomes como
`mt2_1019345202` aparecem em `UNREMT.PAC_2` e em nenhuma das outras 19
camadas da BDGD de Roraima.

CENSO NAS SETE — 298 de 5.444 reguladores pendurados de um lado:

    RR      24 de    40  (60,0%) jusante   <- o caso do BF_AL2-01
    CPFL   157 de   863  (18,2%) jusante
    LT       2 de    14  (14,3%) jusante
    SP      55 de    77  (71,4%) MONTANTE
    CMIG    33 de 3.099  ( 1,1%) os dois
    EQPA     2 de   295  ( 0,7%) jusante
    ENCE     8 de 1.056  ( 0,8%) montante

MEDIDO no BF_AL2-01 de Roraima: 5 dos 10 reguladores da subestacao conduzem
0 A. Sem eles o tronco de 155 km cai a 0,45 pu e a subestacao fica com 35,23%
de perda, mesmo depois do achado 49. Alimentador longo sem regulador tem a
perda SUPERESTIMADA.

O QUE ESTES TESTES TRANCAM

1. O REGULADOR CONTINUA SENDO EMITIDO. Descartar em silencio esconderia que a
   BDGD declara um regulador ali. O que muda e ele passar a ser CONTADO e
   NOMEADO.

2. A ASSINATURA. `reguladores` passou a devolver uma tupla. A suite inteira
   passou com o `converter` ainda esperando um inteiro — e foi exatamente
   assim que o `agregado_pip` quase foi enviado quebrado. Teste que confere o
   chamador, e nao so a funcao.

3. AS DUAS PONTAS CONTINUAM SENDO DESCARTADAS (achado 28), e nao entram na
   conta de pendurados: sao coisas diferentes.
"""
import ast
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import complementos                          # noqa: E402


class BDGDdeMentira:
    def __init__(self, regs):
        """`regs` = [(cod, pac1, pac2), ...]"""
        self.r = regs

    def ler_filtrado(self, tabela, campo, valores, colunas):
        return {'COD_ID': [x[0] for x in self.r],
                'PAC_1': [x[1] for x in self.r],
                'PAC_2': [x[2] for x in self.r],
                'CTMT': ['A'] * len(self.r),
                'FAS_CON': ['ABC'] * len(self.r)}

    def ler(self, tabela, colunas=None):
        raise RuntimeError('sem EQRE')

    def log(self, *a):
        pass


def gera(regs, barras, tmp):
    return complementos.reguladores(BDGDdeMentira(regs), ['A'],
                                    os.path.join(tmp, 'Reguladores.dss'),
                                    barras=barras)


class OPenduradoEContado(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='reg_')

    def _texto(self):
        return open(os.path.join(self.tmp, 'Reguladores.dss'),
                    encoding='utf-8').read()

    def test_jusante_fora_da_rede_e_reportado(self):
        """O caso de Roraima: PAC_2 nao existe em tabela nenhuma."""
        n, pend = gera([('5801121', 'x', 'mt2_1005283961')], {'x', 'y'},
                       self.tmp)
        self.assertEqual([c for c, _ in pend], ['5801121'])
        self.assertEqual(pend[0][1], 'mt2_1005283961',
                         'a ponta solta tem de vir junto, para dar para ir '
                         'olhar')

    def test_montante_fora_da_rede_tambem(self):
        """A Enel SP tem 55 de 77 assim."""
        _n, pend = gera([('361481287', 'nao_existe', 'y')], {'x', 'y'},
                        self.tmp)
        self.assertEqual(len(pend), 1)

    def test_o_regulador_continua_no_arquivo(self):
        """Descartar em silencio esconde que a BDGD declara um ali."""
        n, _pend = gera([('R1', 'x', 'fantasma')], {'x'}, self.tmp)
        self.assertEqual(n, 3, 'tres fases emitidas')
        self.assertIn('New Transformer.REG_R1_1', self._texto())

    def test_o_aviso_sai_no_proprio_arquivo(self):
        gera([('R1', 'x', 'fantasma')], {'x'}, self.tmp)
        t = self._texto()
        self.assertIn('1 regulador(es) com um PAC que nao existe', t)
        self.assertIn('SUPERESTIMADA', t,
                      'quem le o arquivo tem de saber para que lado a perda '
                      'esta errada')
        self.assertIn('R1', t)

    def test_regulador_inteiro_na_rede_nao_e_pendurado(self):
        _n, pend = gera([('R1', 'x', 'y')], {'x', 'y'}, self.tmp)
        self.assertEqual(pend, [])
        self.assertNotIn('ATENCAO', self._texto())

    def test_as_duas_pontas_fora_continuam_descartadas(self):
        """Achado 28: ilha de duas barras devolve NaN. Coisa diferente."""
        n, pend = gera([('R1', 'a', 'b')], {'x', 'y'}, self.tmp)
        self.assertEqual(n, 0, 'nao pode ser emitido')
        self.assertEqual(pend, [], 'nem contado como pendurado')

    def test_sem_lista_de_barras_nada_e_pendurado(self):
        """Quem chama sem `barras` nao sabe o que existe; nao acusa nada."""
        n, pend = gera([('R1', 'x', 'y')], None, self.tmp)
        self.assertEqual((n, pend), (3, []))


class AAssinaturaNaoPodeQuebrarOChamador(unittest.TestCase):
    """A licao do `agregado_pip`: a suite inteira passou com o chamador
    quebrado, porque nenhum teste exercitava o caminho."""

    def setUp(self):
        with open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8') as fh:
            self.fonte = fh.read().lstrip('﻿')

    def test_devolve_tupla_de_dois(self):
        d = tempfile.mkdtemp()
        r = gera([('R1', 'x', 'y')], {'x', 'y'}, d)
        self.assertIsInstance(r, tuple)
        self.assertEqual(len(r), 2)

    def test_o_conversor_desempacota_os_dois(self):
        self.assertIn('n_rg, reg_pendurados = complementos.reguladores(',
                      self.fonte,
                      'o converter voltou a tratar o retorno como inteiro')

    def test_o_resumo_publica_a_contagem(self):
        self.assertIn("'reguladores_pendurados'", self.fonte,
                      'sem isso o numero morre dentro da funcao e ninguem '
                      'consegue medir a base inteira')
        self.assertIn("'reguladores_pendurados_cod'", self.fonte,
                      'contar sem nomear nao deixa ninguem ir olhar')


if __name__ == '__main__':
    unittest.main()
