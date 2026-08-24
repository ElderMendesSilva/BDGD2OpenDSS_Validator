# -*- coding: utf-8 -*-
"""Achado 54 — os dois PACs do transformador trocados de lugar.

`PAC_1` e o lado de MEDIA e `PAC_2` o de BAIXA. Quando vem invertido, a rede
de media entra pelo enrolamento de 0,12 kV e o transformador funciona como
ELEVADOR. Os dois lados sobem juntos, na relacao exata do trafo, e a perda a
vazio — que escala com V^2 — explode.

MEDIDO na 5003346 de Roraima, carga toda desligada:

    perda a vazio total                    3.124,2 kW
    NOVE trafos com V/Kv > 2                2.711,1 kW   86,8%
    os outros 4.530                           413,2 kW

    esperado pela placa                       396,0 kW

Depois de endireitar os PACs: 399,5 kW medidos contra 396,0 esperados, fator
1,009. O `%noloadloss` do achado 53 estava certo desde o inicio — o que
parecia um erro de 4,9x no ferro eram nove transformadores de cabeca para
baixo.

Os piores:

    1019437451   Kv=13,8000   barra a 493,9 kV    35,8x   1.496,8 kW
    1002409124   Kv=13,8000   barra a 497,8 kV    36,1x     584,8 kW
    1018862858   Kv= 7,9674   barra a 480,1 kV    60,3x     108,9 kW

O QUE ESTES TESTES TRANCAM

1. A REGRA E TOPOLOGICA, e nao de nome. Em Roraima 33 dos invertidos tem
   `PAC_1` terminado em "-BT", mas o 1002409124 — 585 kW sozinho — nao tem
   sufixo nenhum nos dois lados.

2. AS DUAS CONDICOES SAO NECESSARIAS. O censo das sete bases mostra os
   contraexemplos: a Enel SP tem 63 trafos com `PAC_1` fora da MT e ZERO com
   `PAC_2` dentro (primario pendurado, defeito diferente); a EQPA tem 56 e a
   CPFL 19 com `PAC_2` na MT e nenhum invertido, porque o `PAC_1` deles
   tambem esta la. Invertido mesmo so em duas bases: 55 em Roraima e 21 na
   CEMIG, de 1,87 milhao de transformadores.

3. SO OS PACS TROCAM. `FAS_CON_P` e `FAS_CON_S` ja descrevem o lado certo.

4. O BANCO E CONTADO DEPOIS DA TROCA. A deteccao de banco conta trafos por
   barra secundaria; com os lados invertidos ela contaria pela barra de
   media, e um alimentador inteiro viraria um banco so.

5. A CORRECAO E DECLARADA. Quem abrir o Trafos.dss e vir um lado diferente
   do que a UNTRMT diz tem de achar ali por que.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss import transformadores as tr        # noqa: E402


def _a(*v):
    return np.array(v, dtype=object)


def _col(p1, p2, fp='ABC', fs='ABCN', cod='TX'):
    """Uma UNTRMT de um transformador so."""
    return {'COD_ID': _a(cod), 'PAC_1': _a(p1), 'PAC_2': _a(p2),
            'CTMT': _a('F1'), 'POT_NOM': np.array([75.0]),
            'TEN_LIN_SE': np.array([0.22]),
            'FAS_CON_P': _a(fp), 'FAS_CON_S': _a(fs)}


class ARegraETopologica(unittest.TestCase):

    def test_pac2_na_mt_e_pac1_fora_e_troca(self):
        """O caso do achado: a media esta no PAC_2."""
        pares, inv = tr._inverte_pacs(_col('931212-BT', 'YDIJL62'), {'ydijl62'})
        self.assertEqual(pares, [('ydijl62', '931212-bt')])
        self.assertEqual(inv, ['TX'])

    def test_o_caso_normal_nao_e_tocado(self):
        pares, inv = tr._inverte_pacs(_col('MT1', 'BT1'), {'mt1'})
        self.assertEqual(pares, [('mt1', 'bt1')])
        self.assertEqual(inv, [])

    def test_os_dois_na_mt_nao_trocam(self):
        """A EQPA: 56 com PAC_2 na MT e nenhum invertido, porque o PAC_1
        deles tambem esta la. Trocar seria inventar um defeito."""
        pares, inv = tr._inverte_pacs(_col('MT1', 'MT2'), {'mt1', 'mt2'})
        self.assertEqual(pares, [('mt1', 'mt2')])
        self.assertEqual(inv, [])

    def test_nenhum_na_mt_nao_troca(self):
        """A Enel SP: 63 com PAC_1 fora da MT e ZERO com PAC_2 dentro. Sao
        primarios PENDURADOS — achado 50, nao achado 54. Exigir as duas
        condicoes e o que separa os dois defeitos."""
        pares, inv = tr._inverte_pacs(_col('X1', 'X2'), {'mt1'})
        self.assertEqual(pares, [('x1', 'x2')])
        self.assertEqual(inv, [])

    def test_nao_olha_o_nome_da_barra(self):
        """33 dos 55 de Roraima se denunciam com '-BT' no PAC_1; o
        1002409124, que sozinho fazia 585 kW, nao tem sufixo nenhum. Um
        detector por sufixo perderia o maior deles."""
        pares, inv = tr._inverte_pacs(_col('6C0O-I9K7', '96XC769I'),
                                      {'96xc769i'})
        self.assertEqual(inv, ['TX'], 'sem sufixo tambem tem de ser pego')
        # e o inverso: sufixo "-bt" sozinho nao basta
        pares, inv = tr._inverte_pacs(_col('931212-BT', 'YDIJL62'),
                                      {'931212-bt'})
        self.assertEqual(inv, [], 'o nome nao pode decidir contra a topologia')

    def test_sem_rede_de_mt_a_deteccao_fica_desligada(self):
        """Chamador que nao passa `barras_mt` recebe o que a BDGD disser."""
        for vazio in (None, set(), frozenset()):
            pares, inv = tr._inverte_pacs(_col('931212-BT', 'YDIJL62'), vazio)
            self.assertEqual(pares, [('931212-bt', 'ydijl62')])
            self.assertEqual(inv, [])

    def test_pac_vazio_nao_troca_nem_derruba(self):
        pares, inv = tr._inverte_pacs(_col('', 'YDIJL62'), {'ydijl62'})
        self.assertEqual(pares, [('', 'ydijl62')])
        self.assertEqual(inv, [])


class _Leitor:
    def __init__(self, col):
        self.col = col

    def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
        return self.col

    def ler(self, camada, colunas=None, **kw):
        raise KeyError(camada)


def _gera(col, barras_mt):
    tmp = tempfile.mkdtemp()
    t = os.path.join(tmp, 'Trafos.dss')
    n, sec, inv = tr.gerar(_Leitor(col), ['F1'], t,
                           os.path.join(tmp, 'Aterr.dss'), kv_mt=13.8,
                           barras_mt=barras_mt)
    with open(t, encoding='utf-8') as fh:
        return fh.read(), sec, inv


class OQueSaiNoArquivo(unittest.TestCase):

    def test_o_primario_vai_para_a_barra_de_media(self):
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'ydijl62'})
        self.assertIn('~ wdg=1 bus=ydijl62', txt)
        self.assertIn('bus=931212-bt', txt)
        self.assertEqual(inv, ['TX'])

    def test_o_secundario_e_que_vira_barra_de_carga(self):
        """`sec` alimenta cargas.py. Se ele apontar para a barra de media, as
        cargas de BT sao penduradas na media — o defeito ao contrario."""
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'ydijl62'})
        self.assertIn('931212-bt', sec)
        self.assertNotIn('ydijl62', sec)

    def test_as_fases_nao_trocam(self):
        """FAS_CON_P ja descreve o lado de media. No 1018862858 ele e 'B',
        monofasico, como o primario de um 5 kVA tem de ser; FAS_CON_S e 'BN'
        e traz o neutro da baixa. Trocar as fases desfaria isso."""
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62', fp='B', fs='BN'),
                              {'ydijl62'})
        self.assertIn('~ wdg=1 bus=ydijl62.2 ', txt,
                      "FAS_CON_P='B' e o no 2 do lado de MEDIA")

    def test_a_troca_e_declarada_no_arquivo(self):
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'ydijl62'})
        self.assertIn('TROCADOS', txt)
        self.assertIn('achado 54', txt)
        self.assertIn('TX', txt.split('endireitados:')[1])

    def test_arquivo_limpo_nao_ganha_aviso(self):
        txt, sec, inv = _gera(_col('MT1', 'BT1'), {'mt1'})
        self.assertNotIn('TROCADOS', txt)
        self.assertNotIn('endireitados', txt)


class OBancoEContadoDepoisDaTroca(unittest.TestCase):
    """A deteccao de banco conta trafos por barra SECUNDARIA. Com os lados
    invertidos ela contaria pela barra de MEDIA, e dois trafos do mesmo
    alimentador virariam um banco — cada um recebendo uma perna diferente de
    um secundario que nao compartilham."""

    def _dois(self):
        return {'COD_ID': _a('T1', 'T2'),
                'PAC_1': _a('BT1', 'BT2'), 'PAC_2': _a('MTX', 'MTX'),
                'CTMT': _a('F1', 'F1'),
                'POT_NOM': np.array([75.0, 75.0]),
                'TEN_LIN_SE': np.array([0.22, 0.22]),
                'FAS_CON_P': _a('A', 'A'), 'FAS_CON_S': _a('AN', 'AN')}

    def test_mesma_barra_de_media_nao_e_banco(self):
        txt, sec, inv = _gera(self._dois(), {'mtx'})
        self.assertEqual(sorted(inv), ['T1', 'T2'])
        # cada um e monofasico ISOLADO: tres enrolamentos, derivacao central
        self.assertEqual(txt.count('windings=3'), 2,
                         'os dois compartilham a MEDIA, nao a baixa — nao sao '
                         'banco, e cada um tem de sair com derivacao central')

    def test_sem_a_troca_eles_pareceriam_banco(self):
        """A prova de que a ordem importa: sem `barras_mt` o codigo le a
        barra compartilhada como secundaria e monta banco."""
        txt, sec, inv = _gera(self._dois(), None)
        self.assertEqual(inv, [])
        self.assertEqual(txt.count('windings=3'), 0)
        self.assertEqual(txt.count('windings=2'), 2)


if __name__ == '__main__':
    unittest.main()
