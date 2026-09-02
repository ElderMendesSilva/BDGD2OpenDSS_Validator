# -*- coding: utf-8 -*-
"""Inversor de BT em barra de MT — achado 30.

Depois que o achado 28 devolveu as 72 subestacoes que a chave ilhada tinha
tirado da medicao, a Cemig-D V12 fechou em 412 de 413. A unica que sobrou
tinha 6 nos NaN em 31.834, nas duas mesmas barras, com os dois motores
concordando no a no:

    New Transformer.484736801_484736800 phases=1 windings=3
    ~ wdg=1 bus=node_754880953.3 conn=wye Kv=7.9674          <- MT
    New Line.244637127 Bus1=node_754880953.3 ...             <- MT
    New PVSystem.GD_acab...891_1 bus1=node_754880953.1.4 kv=0.1270   <- BT!

`node_754880953` e barra de MEDIA: e o primario do trafo e a ponta de uma
linha, e so a fase C existe nela. O inversor de 127 V foi escrito nos nos 1,
2 e 4 dessa barra, que ninguem mais toca — tres nos que nascem do proprio
PVSystem, sem caminho para a fonte. Um PVSystem assim e uma fonte de corrente
solta, e a solucao devolve NaN.

A causa esta na condicao que aceitava o PAC: `pac not in barras`, sendo
`barras` a rede INTEIRA. Casar com uma barra de MT contava como "ja esta na
rede" e desligava o plano B do `UNI_TR_MT`. Pertencer a BT tem de ser
verificado contra a BT.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
from bdgd2dss import complementos                      # noqa: E402

MT = 'node_754880953'            # primario do trafo, 7,9674 kV, so fase C
BT = 'node_457463634'            # secundario do mesmo trafo, 0,12 kV


class _Leitor:
    """So responde o que a `geracao` pergunta: UCMT_tab, UGBT_tab, UGMT_tab."""

    def __init__(self, ugbt):
        self.ugbt = ugbt

    def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
        a = lambda *v: np.array(v, dtype=object)        # noqa: E731
        if camada == 'UGBT_tab':
            return self.ugbt
        if camada == 'UCMT_tab':
            return {'CEG_GD': a(), 'PAC': a()}
        return {c: a() for c in (colunas or ['COD_ID'])}


def _ugbt(pac, uni_tr='TR1', ene=1000.0, fas='AB', com_coluna=True):
    a = lambda *v: np.array(v, dtype=object)            # noqa: E731
    d = {'COD_ID': a('G1'), 'PAC': a(pac), 'CTMT': a('F1'),
         'POT_INST': np.array([5.0]), 'FAS_CON': a(fas), 'CEG_GD': a(''),
         'ENE_01': np.array([ene])}
    if com_coluna:
        d['UNI_TR_MT'] = a(uni_tr)
    return d


def _gera(pac, sec, barras, barras_bt=None, **kw):
    tmp = tempfile.mkdtemp()
    alvo = os.path.join(tmp, 'GD.dss')
    r = complementos.geracao(_Leitor(_ugbt(pac, **kw)), ['F1'], sec, alvo,
                             barras=barras, barras_bt=barras_bt)
    return r, open(alvo, encoding='utf-8').read()


def _sec():
    """O secundario real do trafo, como o `cargas` monta."""
    return {'TR1': {'barra': BT, 'nos': ['1', '2'], 'kv_fn': 0.12,
                    'kva': 15.0}}


class InversorDeBTNaoVaiParaBarraDeMT(unittest.TestCase):

    def test_pac_que_casa_com_barra_de_mt_nao_recebe_o_inversor(self):
        """O caso medido: o PAC da UGBT e o primario do trafo."""
        (n, _, realoc, sem_rede, _, _, _), txt = _gera(
            MT, _sec(), barras={MT, BT})
        self.assertNotIn(MT, txt,
                         'inversor de 127 V escrito na barra de 7,97 kV')
        self.assertEqual(sem_rede, 0, 'havia plano B: o UNI_TR_MT')
        self.assertEqual(realoc, 1)
        self.assertIn(BT, txt, 'devia ter ido para o secundario do trafo')
        self.assertEqual(n, 2, 'duas pernas do secundario, uma unidade cada')

    def test_sem_plano_b_a_unidade_e_descartada_e_nao_vira_nan(self):
        """Sem `UNI_TR_MT` nao ha para onde realocar. O certo e descartar e
        contar — nunca escrever numa barra que nao e de BT."""
        (n, _, _, sem_rede, _, _, _), txt = _gera(
            MT, _sec(), barras={MT}, com_coluna=False)
        self.assertEqual((n, sem_rede), (0, 1))
        self.assertNotIn(MT, txt)

    def test_pac_que_e_secundario_de_trafo_continua_valendo(self):
        """O caminho normal nao pode ter sido estreitado junto."""
        sec = _sec()
        sec[BT] = sec['TR1']
        (n, _, realoc, sem_rede, _, _, _), txt = _gera(BT, sec, barras={MT, BT})
        self.assertEqual((realoc, sem_rede), (0, 0))
        self.assertIn(BT, txt)
        self.assertEqual(n, 2)

    def test_barra_de_bt_a_jusante_vale_quando_a_rede_de_bt_existe(self):
        """Com --bt completo o PAC da UGBT e a ponta do RAMLIG, que nao e
        secundario de trafo nenhum. Ela e legitima e nao pode ser realocada."""
        ponta = 'node_999'
        (n, _, realoc, sem_rede, _, _, _), txt = _gera(
            ponta, _sec(), barras={MT, BT, ponta}, barras_bt={ponta})
        self.assertEqual((realoc, sem_rede), (0, 0))
        self.assertIn(ponta, txt)
        self.assertEqual(n, 2)

    def test_a_mesma_ponta_sem_rede_de_bt_declarada_e_realocada(self):
        """Sem `barras_bt`, `node_999` e so um nome: pode ser qualquer coisa.
        O conservador e mandar para o secundario, que se sabe ser de BT."""
        (_, _, realoc, _, _, _, _), txt = _gera(
            'node_999', _sec(), barras={MT, BT, 'node_999'})
        self.assertEqual(realoc, 1)
        self.assertIn(BT, txt)


class OQueAConversaoEscreveu(unittest.TestCase):
    """Trava a forma do defeito, nao so a contagem: o que fazia NaN era o
    par (barra de MT, no de BT)."""

    def test_o_inversor_realocado_sai_com_a_tensao_do_secundario(self):
        _, txt = _gera(MT, _sec(), barras={MT, BT})
        linhas = [l for l in txt.splitlines() if l.startswith('New PVSystem')]
        self.assertTrue(linhas)
        for l in linhas:
            self.assertIn('kv=0.1200', l.replace('kv=0.12 ', 'kv=0.1200 '))

    def test_nenhum_pvsystem_de_bt_em_barra_so_de_mt(self):
        _, txt = _gera(MT, _sec(), barras={MT, BT})
        for l in txt.splitlines():
            if l.startswith('New PVSystem'):
                self.assertNotIn(f'bus1={MT}', l)


if __name__ == '__main__':
    unittest.main()
