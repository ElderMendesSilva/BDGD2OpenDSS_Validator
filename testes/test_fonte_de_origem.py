# -*- coding: utf-8 -*-
"""Fonte na barra de origem morta de transformador de barra — achado 79.

O `converter` so dava fonte as barras de ORIGEM dos `TRB_*` quando todas as
barras da subestacao eram derivadas. No caso misto a origem ficava sem
caminho ate a fonte: na 71700 da Copel, 4.581 de 5.253 cargas sem tensao; 13
das 96 subestacoes da Energisa MT.

A fonte entra na etapa de ligacao, e so em origem MORTA depois de resolver:
por-la as cegas fechava circuito entre duas fontes quando a origem ja era
alimentada por outro caminho (70 MW circulando na mesma 71700).
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
import opendssdirect as dss                           # noqa: E402
import ligacao as etapa                               # noqa: E402

# fonte na barra A (34,5 kV); a origem B (13,8 kV) nao se liga a A por nada
CIRCUITO = """clear
New Circuit.T79 basekV=34.5 pu=1.0 phases=3 bus1=a MVAsc3=1000 MVAsc1=800
New Line.VAO_1 phases=3 bus1=a bus2=fa r1=0.0001 x1=0 r0=0.0001 x0=0 c1=0 c0=0 switch=y
New Load.LA bus1=fa kV=34.5 kW=100 pf=0.95
New Transformer.TRB_b_23p9kv phases=3 windings=2 Xhl=7
~ wdg=1 bus=b conn=delta kV=13.8 kVA=10000
~ wdg=2 bus=b_23p9kv conn=wye kV=23.9 kVA=10000
New Line.VAO_2 phases=3 bus1=b_23p9kv bus2=fb r1=0.0001 x1=0 r0=0.0001 x0=0 c1=0 c0=0 switch=y
New Load.LB bus1=fb kV=23.9 kW=500 pf=0.95
Set Voltagebases=[34.5 23.9 13.8]
CalcVoltagebases
Solve
"""


def _montar(extra=''):
    for linha in (CIRCUITO + extra).splitlines():
        if linha.strip():
            dss.Text.Command(linha)
    dss.Text.Command('Solve')


def _v(barra):
    dss.Circuit.SetActiveBus(barra)
    return max(dss.Bus.VMagAngle()[0::2] or [0.0])


class FonteDeOrigem(unittest.TestCase):

    def test_origem_morta_ganha_fonte_e_a_carga_acende(self):
        _montar()
        self.assertLess(_v('fb'), etapa.MORTA_V)
        fontes = etapa.fontes_de_origem('SE1')
        self.assertEqual([f['barra'] for f in fontes], ['b'])
        self.assertEqual(fontes[0]['nome'], 'FONTE_TRB_SE1_1')
        self.assertAlmostEqual(fontes[0]['kv'], 13.8)
        self.assertGreater(_v('fb'), 1000.0)

    def test_origem_viva_nao_ganha_fonte(self):
        """A origem ja alimentada por outro caminho: fonte a mais fecharia
        circuito entre duas fontes."""
        _montar('New Transformer.ELO phases=3 windings=2 Xhl=5\n'
                '~ wdg=1 bus=a conn=delta kV=34.5 kVA=10000\n'
                '~ wdg=2 bus=b conn=wye kV=13.8 kVA=10000\n')
        self.assertGreater(_v('b'), 1000.0)
        self.assertEqual(etapa.fontes_de_origem('SE1'), [])

    def test_o_nome_leva_a_subestacao(self):
        """O MASTER-GERAL carrega o `_LIGACAO.dss` de todas: nome repetido
        entre subestacoes seria #266."""
        _montar()
        self.assertIn('SE9', etapa.fontes_de_origem('SE9')[0]['nome'])

    def test_a_fonte_vai_para_o_arquivo(self):
        import tempfile
        from bdgd2dss import ligacao
        _montar()
        fontes = etapa.fontes_de_origem('SE1')
        caminho = os.path.join(tempfile.mkdtemp(), '_LIGACAO.dss')
        ligacao.escrever(caminho, [], lambda kv: None, fontes=fontes)
        with open(caminho, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertIn('New Vsource.FONTE_TRB_SE1_1 bus1=b basekV=13.8', txt)
        self.assertIn('achado 79', txt)


if __name__ == '__main__':
    unittest.main()
