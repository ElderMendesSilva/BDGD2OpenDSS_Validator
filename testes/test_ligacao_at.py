# -*- coding: utf-8 -*-
"""A subtransmissao solta ligada pela geometria — achado 74.

Na Equatorial PA os nos da SSDAT (`A100275`) nao sao nos de subestacao
(`MON_490000059`): zero em comum, e a rede de linhas inteira caia fora do
modelo. Em 23 das 99 bases. A regra liga cada ponta solta a barra da
subestacao mais proxima NO MESMO NIVEL DE TENSAO, ate 500 m.

Desligada por padrao (`--ligar-at`): no teste com tres subestacoes da PA o
MASTER-GERAL colapsou, pela regra de fontes e por um elo que fechou laco por
transformador. Estes testes travam a regra dos elos; o padrao do conversor e
travado pelo pre-voo, que nao muda.
"""
import os
import struct
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss import ligacao_at, subtransmissao              # noqa: E402

# ~0,001 grau de longitude no equador sao ~111 m
LON0, LAT0 = -48.0, -1.0


def _ponto(x, y):
    return struct.pack('<BIdd', 1, 1, x, y)


def _linha(x0, y0, x1, y1):
    return struct.pack('<BII', 1, 2, 2) + struct.pack('<dddd', x0, y0, x1, y1)


def _dados():
    """Um circuito de 69 kV (codigo 82) A1-A2-A3 e uma subestacao SE1 com
    barras de 69 kV (82) e 138 kV (94), sem no em comum com a SSDAT."""
    return {
        'ssdat': {'COD_ID': ['T1', 'T2'], 'PAC_1': ['A1', 'A2'],
                  'PAC_2': ['A2', 'A3'], 'CTAT': ['C1', 'C1'],
                  'FAS_CON': ['ABC', 'ABC'], 'TIP_CND': ['X', 'X'],
                  'COMP': [100.0, 100.0]},
        'unseat': {'COD_ID': ['S1'], 'PAC_1': ['SE1_B69'], 'PAC_2': ['SE1_X'],
                   'FAS_CON': ['ABC'], 'P_N_OPE': ['F'], 'SUB': ['SE1'],
                   'SIT_ATIV': ['AT']},
        'untrat': {'COD_ID': ['TR1'], 'PAC_1': ['SE1_B138'], 'PAC_2': ['SE1_MT']},
        'bar': {'COD_ID': ['B69', 'B138'], 'SUB': ['SE1', 'SE1'],
                'TEN_NOM': ['82', '94'], 'PAC': ['SE1_B69', 'SE1_B138'],
                'TIP_INST': ['1', '1']},
        'ctat': {'COD_ID': ['C1'], 'NOME': ['X'], 'TEN_NOM': ['82'],
                 'PAC_INI': ['A1']},
    }


def _geometria_falsa(dist_graus, sub_pts=((LON0, LAT0),)):
    """A1 fica a `dist_graus` da subestacao; A3, a 1 grau (longe)."""
    def geo(_gdb, camada, _cols):
        if camada == 'SSDAT':
            a1 = (LON0 + dist_graus, LAT0)
            a2 = (LON0 + 0.5, LAT0)
            a3 = (LON0 + 1.0, LAT0)
            return ({'PAC_1': ['A1', 'A2'], 'PAC_2': ['A2', 'A3']},
                    [_linha(*a1, *a2), _linha(*a2, *a3)])
        if camada == 'UNSEAT':
            return ({'SUB': ['SE1'] * len(sub_pts)}, [_ponto(*p) for p in sub_pts])
        if camada == 'UNTRAT':
            return ({'SUB': []}, [])
        return None, None
    return geo


class TestElos(unittest.TestCase):

    def setUp(self):
        self._orig = ligacao_at._geometria

    def tearDown(self):
        ligacao_at._geometria = self._orig

    def test_ponta_perto_liga_na_barra_do_mesmo_nivel(self):
        ligacao_at._geometria = _geometria_falsa(0.001)           # ~111 m
        elos, censo = ligacao_at.elos('x.gdb', _dados())
        self.assertEqual(len(elos), 1)
        self.assertEqual(elos[0]['ponta'], 'a1')
        self.assertEqual(elos[0]['barra'], 'se1_b69')             # 69 kV, nao 138
        self.assertLess(elos[0]['metros'], 150)
        self.assertEqual(censo['pontas_soltas'], 2)
        self.assertEqual(censo['longe_de_subestacao'], 1)          # A3

    def test_ponta_longe_nao_liga(self):
        ligacao_at._geometria = _geometria_falsa(0.01)            # ~1,1 km
        elos, censo = ligacao_at.elos('x.gdb', _dados())
        self.assertEqual(elos, [])
        self.assertEqual(censo['longe_de_subestacao'], 2)

    def test_sem_barra_no_nivel_nao_liga(self):
        """Circuito de 138 kV perto de subestacao sem barra de 138 kV: e
        passagem, e nao chegada."""
        d = _dados()
        d['ctat']['TEN_NOM'] = ['96']
        ligacao_at._geometria = _geometria_falsa(0.001)
        elos, censo = ligacao_at.elos('x.gdb', d)
        self.assertEqual(elos, [])
        self.assertEqual(censo['sem_barra_no_nivel'], 1)

    def test_rede_ja_ligada_nao_ganha_elo(self):
        d = _dados()
        d['ssdat']['PAC_1'] = ['SE1_B69', 'A2']                    # A1 vira no de SE
        ligacao_at._geometria = _geometria_falsa(0.001)
        elos, censo = ligacao_at.elos('x.gdb', d)
        self.assertEqual(elos, [])
        self.assertEqual(censo['pontas_soltas'], 1)                # so A3

    def test_aplicar_junta_as_componentes(self):
        ligacao_at._geometria = _geometria_falsa(0.001)
        d = _dados()
        antes, _ = subtransmissao.componentes(d)
        elos, _ = ligacao_at.elos('x.gdb', d)
        ligacao_at.aplicar(d, elos)
        depois, _ = subtransmissao.componentes(d)
        self.assertEqual(len(depois), len(antes) - 1)
        self.assertIn('LIGAT_1', d['unseat']['COD_ID'])
        junta = [c for c in depois if 'a3' in c][0]
        self.assertIn('se1_b69', junta)


class TestOpcao(unittest.TestCase):

    def test_desligada_por_padrao(self):
        with open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn("'--ligar-at', action='store_true'", src)
        self.assertIn("getattr(a, 'ligar_at', False)", src)


if __name__ == '__main__':
    unittest.main()
