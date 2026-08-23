# -*- coding: utf-8 -*-
"""Achado 49: o CTMT diz uma tensao, os trafos DELE dizem outra.

`CTMT.TEN_NOM` e UM campo por alimentador. `EQTRMT.TEN_PRI` e um campo por
transformador, e um alimentador tem centenas. No BF_AL2-01 de Roraima o
cabecalho diz 34,5 kV e 603 dos 714 trafos dizem 13,8 kV — e a subestacao
dele tem um unico trafo de AT, 69 -> 13,8 kV.

Acreditar no cabecalho fazia a maquina do achado 39 criar uma barra derivada
de 34,5 kV e INVENTAR um transformador de barra de 10 MVA para alimenta-la.
O alimentador ficava com 155 km de tronco na tensao errada, 459 dos 716
trafos mortos e 390% de perda modelada.

Nao e classe de isolamento: a EQTRMT traz `CLAS_TEN` num campo separado.

CENSO NAS SETE (maioria >= 60%, diferenca > 0,5 kV): 510 de 8.049
alimentadores, 29,8 GWh/dia. A Light e o extremo, com 371 (25,3%).

O QUE ESTES TESTES TRANCAM

1. O ACHADO 41 DENTRO DA URNA. `TEN_PRI` de trafo MONOFASICO e fase-neutro
   (codigo 39 = 7,96 kV = 13,8/raiz(3)); `TEN_NOM` e tensao de LINHA. Sem
   multiplicar o voto do monofasico por raiz(3), TODA base acusaria
   discordancia — e a correcao passaria a estragar em vez de consertar.

2. MAIORIA DE VERDADE. Alimentador com 3 trafos nao decide nada, e 51% nao
   e maioria para trocar a tensao de uma rede inteira.

3. O QUE MUDOU FICA REGISTRADO. Trocar a tensao de um alimentador em
   silencio e a ultima coisa que se quer num modelo que alguem vai auditar.

4. OS DOIS SENTIDOS. A EQPA e a Cemig-D tem cabecalho ALTO com parque baixo;
   a Enel SP tem cabecalho 13,8 com parque em 23,9. A regra nao pode ter
   sentido preferido.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import tensoes                              # noqa: E402


class BDGDdeMentira:
    """`trafos` = [(cod, ctmt, fas_con_p, codigo_de_ten_pri), ...]"""

    def __init__(self, trafos):
        self.t = trafos

    def ler(self, tabela, colunas=None):
        if tabela == 'UNTRMT':
            return {'COD_ID': [x[0] for x in self.t],
                    'CTMT': [x[1] for x in self.t],
                    'FAS_CON_P': [x[2] for x in self.t]}
        if tabela == 'EQTRMT':
            return {'UNI_TR_MT': [x[0] for x in self.t],
                    'TEN_PRI': [x[3] for x in self.t]}
        raise RuntimeError(tabela)

    def log(self, *a):
        pass


# codigos da TTEN usados aqui: 39 = 7,96 kV (13,8/raiz3), 49 = 13,8, 72 = 34,5
def monof(n, ctmt, cod='39'):
    return [(f'{ctmt}_m{k}', ctmt, 'A', cod) for k in range(n)]


def trif(n, ctmt, cod='49'):
    return [(f'{ctmt}_t{k}', ctmt, 'ABC', cod) for k in range(n)]


class OAchado41DentroDaUrna(unittest.TestCase):
    """Sem isto a correcao estraga tudo em vez de consertar."""

    def test_o_voto_do_monofasico_vira_tensao_de_linha(self):
        r = tensoes.por_equipamento(BDGDdeMentira(monof(20, 'A')))
        self.assertAlmostEqual(r['A'][0], 13.8, places=1,
                               msg='7,96 kV fase-neutro tem de virar 13,8 de '
                                   'linha antes de comparar com TEN_NOM')

    def test_monofasico_e_trifasico_do_mesmo_sistema_votam_junto(self):
        """561 em 7,96 e 152 em 13,8 sao o MESMO sistema de 13,8 kV."""
        r = tensoes.por_equipamento(BDGDdeMentira(monof(561, 'A') +
                                                  trif(152, 'A')))
        self.assertAlmostEqual(r['A'][0], 13.8, places=1)
        self.assertEqual(r['A'][1], 713, 'os dois grupos tem de somar votos')

    def test_o_trifasico_nao_e_multiplicado(self):
        r = tensoes.por_equipamento(BDGDdeMentira(trif(20, 'A', '72')))
        self.assertAlmostEqual(r['A'][0], 34.5, places=1)


class AMaioriaTemDeSerMaioria(unittest.TestCase):

    def test_amostra_minuscula_nao_decide(self):
        r = tensoes.por_equipamento(BDGDdeMentira(trif(3, 'A')))
        self.assertNotIn('A', r, 'tres trafos nao trocam a tensao de uma rede')

    def test_maioria_apertada_nao_decide(self):
        r = tensoes.por_equipamento(BDGDdeMentira(
            [(f'x{k}', 'A', 'ABC', '49') for k in range(51)] +
            [(f'y{k}', 'A', 'ABC', '72') for k in range(49)]))
        self.assertNotIn('A', r, '51% nao e maioria para trocar a tensao')

    def test_o_caso_do_bf_al2_01_decide(self):
        """603 de 714 = 84%."""
        r = tensoes.por_equipamento(BDGDdeMentira(
            [(f'x{k}', 'BF_AL2-01', 'A', '39') for k in range(603)] +
            [(f'y{k}', 'BF_AL2-01', 'ABC', '72') for k in range(111)]))
        self.assertAlmostEqual(r['BF_AL2-01'][0], 13.8, places=1)
        self.assertEqual(tuple(r['BF_AL2-01'][1:]), (603, 714))


class AConciliacao(unittest.TestCase):

    def test_troca_e_guarda_o_que_havia(self):
        info = {'BF_AL2-01': {'kv': 34.5}}
        mudou = tensoes.concilia(info, {'BF_AL2-01': (13.8, 603, 714)})
        self.assertEqual(info['BF_AL2-01']['kv'], 13.8)
        self.assertEqual(info['BF_AL2-01']['kv_do_cabecalho'], 34.5,
                         'o valor do cabecalho tem de sobreviver para o '
                         'relatorio')
        self.assertEqual(info['BF_AL2-01']['kv_votos'], [603, 714])
        self.assertEqual(len(mudou), 1)

    def test_concordancia_nao_mexe_em_nada(self):
        info = {'X': {'kv': 13.8}}
        self.assertEqual(tensoes.concilia(info, {'X': (13.8, 500, 500)}), [])
        self.assertNotIn('kv_do_cabecalho', info['X'])

    def test_diferenca_de_arredondamento_nao_troca(self):
        info = {'X': {'kv': 13.8}}
        tensoes.concilia(info, {'X': (13.9, 500, 500)})
        self.assertEqual(info['X']['kv'], 13.8)

    def test_o_sentido_contrario_tambem_vale(self):
        """Enel SP: JAC0106 tem cabecalho 13,8 e parque em 23,9."""
        info = {'JAC0106': {'kv': 13.8}}
        tensoes.concilia(info, {'JAC0106': (23.9, 108, 180)})
        self.assertEqual(info['JAC0106']['kv'], 23.9)

    def test_alimentador_sem_voto_fica_como_estava(self):
        info = {'X': {'kv': 34.5}}
        self.assertEqual(tensoes.concilia(info, {}), [])
        self.assertEqual(info['X']['kv'], 34.5)


class QuandoNaoDaParaDecidir(unittest.TestCase):

    def test_base_sem_as_tabelas_nao_quebra(self):
        class Sem:
            def ler(self, *a, **k):
                raise RuntimeError('camada inexistente')
        self.assertEqual(tensoes.por_equipamento(Sem()), {})

    def test_codigo_de_tensao_desconhecido_nao_vota(self):
        r = tensoes.por_equipamento(BDGDdeMentira(
            [(f'x{k}', 'A', 'ABC', 'ZZZ') for k in range(50)] +
            trif(10, 'A', '49')))
        self.assertAlmostEqual(r['A'][0], 13.8, places=1)
        self.assertEqual(r['A'][2], 10, 'codigo invalido nao entra na urna')

    def test_trafo_sem_ctmt_nao_vota(self):
        r = tensoes.por_equipamento(BDGDdeMentira(
            [(f'x{k}', '', 'ABC', '49') for k in range(50)]))
        self.assertEqual(r, {})


class QuemUsa(unittest.TestCase):

    def test_o_conversor_concilia_ao_ler_o_ctmt(self):
        with open(os.path.join(RAIZ, 'converter.py'), encoding='utf-8') as fh:
            fonte = fh.read().lstrip('﻿')
        arvore = ast.parse(fonte)
        f = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == 'ler_ctmt'][0]
        chamadas = {n.func.id for n in ast.walk(f)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn('concilia_tensao', chamadas,
                      'ler_ctmt devolve a tensao do cabecalho sem conferir '
                      'com o parque')


if __name__ == '__main__':
    unittest.main()
