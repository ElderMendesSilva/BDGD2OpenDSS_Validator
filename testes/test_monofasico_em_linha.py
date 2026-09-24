# -*- coding: utf-8 -*-
"""O monofasico que ja declara a tensao de linha — achado 80.

O achado 41 le o TEN_PRI do trafo de um no como fase-neutro e multiplica por
raiz(3). A Equatorial PA declara assim (19,919 kV -> 34,5). As Energisa, nao:
declaram 34,5 no monofasico, e o voto virava 59,8 kV — 198 alimentadores da
Energisa MT e 108 da TO trocados na V39, cada um atras de um transformador de
barra inventado.

A trava: raiz(3) so vale se levar a um nivel de linha que os trafos de dois
ou tres nos da base declaram; se o valor cru ja e um desses, fica.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import tensoes                          # noqa: E402

COD = {v: k for k, v in tensoes.TENSAO_KV.items()}


def _cod(kv):
    """O codigo TTEN cujo valor e `kv` (o mais proximo)."""
    return COD[min(COD, key=lambda x: abs(x - kv))]


class _Base:
    """`trafos` = lista de (ctmt, fases_do_primario, kv)."""
    def __init__(self, trafos):
        self.t = trafos

    def ler(self, camada, colunas=None):
        if camada == 'UNTRMT':
            return {'COD_ID': [f'T{i}' for i in range(len(self.t))],
                    'CTMT': [c for c, _, _ in self.t],
                    'FAS_CON_P': [f for _, f, _ in self.t]}
        return {'UNI_TR_MT': [f'T{i}' for i in range(len(self.t))],
                'TEN_PRI': [_cod(kv) for _, _, kv in self.t]}


def _energisa():
    """Alimentador A: 30 monofasicos declarando 34,5; trifasicos em 34,5 e
    13,8 noutros alimentadores dao os niveis da base."""
    return ([('A', 'A', 34.5)] * 30 + [('B', 'ABC', 34.5)] * 10
            + [('C', 'ABC', 13.8)] * 10)


def _equatorial():
    """Alimentador A: 30 monofasicos em 19,919 (fase-neutro de 34,5)."""
    return ([('A', 'A', 19.919)] * 30 + [('B', 'ABC', 34.5)] * 10
            + [('C', 'ABC', 13.8)] * 10)


class MonofasicoEmLinha(unittest.TestCase):

    def test_energisa_fica_em_34p5_e_nao_59p8(self):
        out = tensoes.por_equipamento(_Base(_energisa()))
        self.assertAlmostEqual(out['A'][0], 34.5, places=1)

    def test_equatorial_continua_multiplicando(self):
        out = tensoes.por_equipamento(_Base(_equatorial()))
        self.assertAlmostEqual(out['A'][0], 34.5, places=1)

    def test_sem_trifasico_na_base_vale_o_achado_41(self):
        out = tensoes.por_equipamento(_Base([('A', 'A', 7.96)] * 30))
        self.assertAlmostEqual(out['A'][0], 13.8, places=1)

    def test_o_log_conta_os_que_declaram_linha(self):
        msgs = []
        tensoes.por_equipamento(_Base(_energisa()), log=msgs.append)
        self.assertTrue(any('ACHADO 80: 30 ' in m for m in msgs), msgs)


if __name__ == '__main__':
    unittest.main()
