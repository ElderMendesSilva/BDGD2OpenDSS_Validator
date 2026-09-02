# -*- coding: utf-8 -*-
"""Achado 51: o achado 28 se repetindo na baixa tensao.

O achado 28 era a chave com os DOIS PACs fora da rede de MT: ilha de duas
barras, sem fonte e sem caminho para a terra, matriz singular, tensao NaN. E o
NaN nao fica quieto — ele contamina o `Circuit.Losses()` da subestacao
inteira. A MT ganhou defesa em `chaves.gerar`; a BT ficou sem.

MEDIDO em Roraima com `--bt completo`, antes: a soma de `Circuit.Losses()` das
20 subestacoes saia NaN. A culpa era de QUATRO linhas numa delas —

    New Line.1019529892   Bus1=6358977.1.2.3  Bus2=6358869.1.2.3
    New Line.N_1019529892 Bus1=6358977.4      Bus2=6358869.4

e nada mais no modelo tocava `6358977` nem `6358869`.

DEPOIS, na base inteira: 8.688 trechos ilhados suprimidos, e

    perda        NaN  ->  8.244 kW (6,20%)
    carga morta  5,2% ->  0,3%

POR QUE A CONTA NAO CABE NO `gerar_bt`, e este e o ponto de projeto: ele roda
DUAS vezes, uma para a SSDBT e outra para a RAMLIG, escrevendo arquivos
separados. Um trecho da SSDBT pode chegar a rede SO atraves de um ramal da
RAMLIG. A pergunta "isto se liga em algum lugar?" so tem resposta sobre a
UNIAO dos dois, mais os secundarios dos transformadores.

O QUE ESTES TESTES TRANCAM

1. A UNIAO DOS DOIS CONJUNTOS. Conferir a SSDBT sozinha suprimiria trechos
   legitimos que se ligam pela RAMLIG — trocaria um defeito por outro pior,
   porque este apaga rede boa em silencio.

2. ANCORA E SECUNDARIO DE TRAFO, e nao "qualquer barra". A BT so existe
   pendurada num secundario; sem essa referencia, uma ilha grande o bastante
   se auto-justificaria.

3. O ARQUIVO SAI NOS DOIS MODOS. O MASTER redireciona `_BT_ILHADA.dss` sem
   condicao, e `redirect` de arquivo ausente ABORTA a compilacao. Com
   `--bt agregado` ele sai vazio, e vazio tambem e informacao.

4. A ASSINATURA. `gerar_bt` passou a devolver quatro itens, e o `converter`
   chama duas vezes. E a mesma armadilha do `agregado_pip` e do `pool`: a
   suite passa inteira com o chamador quebrado.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import linhas                                # noqa: E402


class OQueEIlha(unittest.TestCase):

    def test_o_par_solto_e_ilha(self):
        """O caso de Roraima: duas barras penduradas uma na outra."""
        r = [('tronco', 'sec1', 'b2'), ('1019529892', '6358977', '6358869')]
        self.assertEqual(linhas.ilhadas_bt(r, {'sec1'}), {'1019529892'})

    def test_o_que_chega_ao_secundario_fica(self):
        r = [('a', 'sec1', 'b2'), ('b', 'b2', 'b3'), ('c', 'b3', 'b4')]
        self.assertEqual(linhas.ilhadas_bt(r, {'sec1'}), set())

    def test_a_ancora_e_o_secundario_e_nao_qualquer_barra(self):
        """Sem essa referencia, uma ilha grande se auto-justificaria."""
        r = [('a', 'x1', 'x2'), ('b', 'x2', 'x3'), ('c', 'x3', 'x4'),
             ('d', 'x4', 'x5')]
        self.assertEqual(linhas.ilhadas_bt(r, {'sec1'}),
                         {'a', 'b', 'c', 'd'},
                         'quatro trechos ligados entre si continuam ilha se '
                         'nenhum toca secundario')

    def test_a_ancora_nao_depende_de_caixa(self):
        r = [('a', 'sec1', 'b2')]
        self.assertEqual(linhas.ilhadas_bt(r, {'SEC1'}), set())

    def test_sem_ramo_nenhum_nao_quebra(self):
        self.assertEqual(linhas.ilhadas_bt([], {'sec1'}), set())

    def test_sem_ancora_tudo_e_ilha(self):
        r = [('a', 'b1', 'b2')]
        self.assertEqual(linhas.ilhadas_bt(r, set()), {'a'})


class AUniaoDosDoisConjuntos(unittest.TestCase):
    """Conferir a SSDBT sozinha apagaria rede boa, em silencio."""

    def test_trecho_que_so_chega_pela_ramlig_e_preservado(self):
        ssdbt = [('ssd1', 'b9', 'b10')]          # solto, olhando so a SSDBT
        ramlig = [('ram1', 'sec1', 'b9')]        # e o ramal que o liga
        self.assertEqual(linhas.ilhadas_bt(ssdbt, {'sec1'}), {'ssd1'},
                         'sozinha, a SSDBT parece ilha — e por isso a conta '
                         'nao pode ser feita separada')
        self.assertEqual(linhas.ilhadas_bt(ssdbt + ramlig, {'sec1'}), set(),
                         'com a RAMLIG junto, o trecho se liga e tem de ficar')


class OConversorUsaCerto(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8') as fh:
            self.fonte = fh.read().lstrip('﻿')

    def test_a_conta_e_sobre_os_dois_conjuntos(self):
        self.assertIn('linhas.ilhadas_bt(rm_bt + rm_rm', self.fonte,
                      'a conta voltou a ser sobre um conjunto so')

    def test_o_arquivo_sai_nos_dois_modos(self):
        """O MASTER redireciona sem condicao; ausente, aborta a compilacao."""
        i = self.fonte.index("'_BT_ILHADA.dss'")
        antes = self.fonte[:i]
        self.assertIn('ilhadas = set()', antes,
                      'o modo agregado precisa definir `ilhadas` para o '
                      'arquivo sair vazio em vez de nao sair')

    def test_o_master_redireciona(self):
        with open(os.path.join(RAIZ, 'bdgd2dss', 'master.py'),
                  encoding='utf-8') as fh:
            self.assertIn('redirect _BT_ILHADA.dss', fh.read())

    def test_o_resumo_publica_a_contagem(self):
        self.assertIn("info['bt_ilhada']", self.fonte,
                      'suprimir trecho sem contar e suprimir em silencio')

    def test_gerar_bt_devolve_quatro_e_o_chamador_desempacota(self):
        """A licao do agregado_pip: a suite passa com o chamador quebrado."""
        arvore = ast.parse(open(os.path.join(RAIZ, 'bdgd2dss', 'linhas.py'),
                                encoding='utf-8').read())
        f = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == 'gerar_bt'][0]
        ret = [n for n in ast.walk(f) if isinstance(n, ast.Return)][-1]
        self.assertEqual(len(ret.value.elts), 4,
                         'gerar_bt deixou de devolver quatro itens')
        self.assertEqual(self.fonte.count('linhas.gerar_bt('), 2)
        for pedaco in ('n_bt, km_bt, bb_bt, rm_bt', 'n_rm, km_rm, bb_rm, rm_rm'):
            self.assertIn(pedaco, self.fonte,
                          f'chamador nao desempacota os quatro: {pedaco}')


if __name__ == '__main__':
    unittest.main()
