# -*- coding: utf-8 -*-
"""Achado 54 — os dois PACs do transformador trocados de lugar.
Achado 57 — e por que a pergunta e da BASE, e nao da subestacao.

`PAC_1` e o lado de MEDIA e `PAC_2` o de BAIXA. Quando vem invertido, a rede
de media entra pelo enrolamento de 0,12 kV e o transformador funciona como
ELEVADOR. Os dois lados sobem juntos, na relacao exata do trafo, e a perda a
vazio — que escala com V^2 — explode.

MEDIDO na 5003346 de Roraima, carga toda desligada:

    perda a vazio total                    3.124,2 kW
    NOVE trafos com V/Kv > 2                2.711,1 kW   86,8%
    os outros 4.530                           413,2 kW
    esperado pela placa                       396,0 kW

Depois de endireitar: 399,5 kW contra 396,0 esperados, fator 1,009.

O ACHADO 57. A primeira versao comparava com a MT da SUBESTACAO, porque era o
conjunto que o `converter` tinha na mao. Isso torna a resposta dependente do
RECORTE, e a V21 mostrou os dois lados do estrago:

    base    censo da base inteira    V21, por subestacao
    RR                 55                     55
    CMIG               21                      0
    EQPA                0                     25

Um trafo cujo `PAC_1` esta na media da subestacao VIZINHA parecia estar fora
dela e era trocado — 25 trocas falsas na EQPA. E na Cemig o recorte perdeu os
21 verdadeiros. **Uma pergunta sobre a rede tem de ser feita a rede inteira.**

A DECISAO E TOMADA UMA VEZ e viaja como COD_ID. Ler a media da base custa 13 s
na Enel SP e 59 s na Cemig, contra 12 e 58 MINUTOS de conversao; guardar os
6,5 milhoes de nos de media da Cemig em 32 processos trabalhadores, nao.

O QUE ESTES TESTES TRANCAM

1. A REGRA E TOPOLOGICA, e nao de nome. Em Roraima 33 dos invertidos tem
   `PAC_1` terminado em "-BT", mas o 1002409124 — 585 kW sozinho — nao tem
   sufixo nenhum nos dois lados.

2. AS DUAS CONDICOES SAO NECESSARIAS. A Enel SP tem 63 trafos com `PAC_1` fora
   da MT e ZERO com `PAC_2` dentro (primario pendurado, achado 50); a EQPA tem
   56 e a CPFL 19 com `PAC_2` na MT e nenhum invertido, porque o `PAC_1` deles
   tambem esta la.

3. O ESCOPO E A BASE. O trafo da subestacao vizinha nao pode virar troca.

4. SO OS PACS TROCAM. `FAS_CON_P` e `FAS_CON_S` ja descrevem o lado certo.

5. O BANCO E CONTADO DEPOIS DA TROCA.

6. A CORRECAO E DECLARADA no proprio `Trafos.dss`.
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


class _Base:
    """O minimo que `pacs_invertidos` consome: a UNTRMT e a rede de media.

    `mt` e a lista de pares (PAC_1, PAC_2) dos trechos de media da BASE — de
    proposito, e nao um conjunto de nos: o teste tem de exercitar o mesmo
    caminho de leitura que a base real, que entrega colunas.
    """

    def __init__(self, untrmt, mt=(), unsemt=(), unremt=()):
        self.untrmt = untrmt
        self.camadas = {'SSDMT': list(mt), 'UNSEMT': list(unsemt),
                        'UNREMT': list(unremt)}

    def ler(self, camada, colunas=None, **kw):
        if camada == 'UNTRMT':
            return self.untrmt
        pares = self.camadas.get(camada)
        if pares is None:
            raise KeyError(camada)
        if not pares:
            return {'PAC_1': _a(), 'PAC_2': _a()}
        return {'PAC_1': _a(*[p[0] for p in pares]),
                'PAC_2': _a(*[p[1] for p in pares])}

    def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
        return self.untrmt


class ARegraETopologica(unittest.TestCase):

    def test_pac2_na_mt_e_pac1_fora_e_troca(self):
        """O caso do achado: a media esta no PAC_2."""
        b = _Base(_col('931212-BT', 'YDIJL62'), mt=[('YDIJL62', 'OUTRO')])
        self.assertEqual(tr.pacs_invertidos(b), {'TX'})

    def test_o_caso_normal_nao_e_tocado(self):
        b = _Base(_col('MT1', 'BT1'), mt=[('MT1', 'MT9')])
        self.assertEqual(tr.pacs_invertidos(b), set())

    def test_os_dois_na_mt_nao_trocam(self):
        """A EQPA: 56 com PAC_2 na MT e nenhum invertido, porque o PAC_1
        deles tambem esta la. Trocar seria inventar um defeito."""
        b = _Base(_col('MT1', 'MT2'), mt=[('MT1', 'MT2')])
        self.assertEqual(tr.pacs_invertidos(b), set())

    def test_nenhum_na_mt_nao_troca(self):
        """A Enel SP: 63 com PAC_1 fora da MT e ZERO com PAC_2 dentro. Sao
        primarios PENDURADOS — achado 50, nao achado 54."""
        b = _Base(_col('X1', 'X2'), mt=[('MT1', 'MT9')])
        self.assertEqual(tr.pacs_invertidos(b), set())

    def test_nao_olha_o_nome_da_barra(self):
        """33 dos 55 de Roraima se denunciam com '-BT' no PAC_1; o
        1002409124, que sozinho fazia 585 kW, nao tem sufixo nenhum."""
        b = _Base(_col('6C0O-I9K7', '96XC769I'), mt=[('96XC769I', 'Z')])
        self.assertEqual(tr.pacs_invertidos(b), {'TX'},
                         'sem sufixo tambem tem de ser pego')
        b = _Base(_col('931212-BT', 'YDIJL62'), mt=[('931212-BT', 'Z')])
        self.assertEqual(tr.pacs_invertidos(b), set(),
                         'o nome nao pode decidir contra a topologia')

    def test_o_regulador_e_a_chave_tambem_sao_media(self):
        """A media nao e so a SSDMT. Um trafo pendurado num regulador tem o
        PAC ali, e ignora-lo inventaria uma troca."""
        b = _Base(_col('R1', 'R2'), mt=[], unremt=[('R1', 'R2')])
        self.assertEqual(tr.pacs_invertidos(b), set())
        b = _Base(_col('S1', 'S2'), mt=[], unsemt=[('S2', 'Z')])
        self.assertEqual(tr.pacs_invertidos(b), {'TX'})

    def test_pac_vazio_nao_troca_nem_derruba(self):
        b = _Base(_col('', 'YDIJL62'), mt=[('YDIJL62', 'Z')])
        self.assertEqual(tr.pacs_invertidos(b), set())

    def test_base_sem_untrmt_devolve_vazio(self):
        class Seca:
            def ler(self, *a, **k):
                raise KeyError('UNTRMT')
        self.assertEqual(tr.pacs_invertidos(Seca()), set())


class OEscopoEABase(unittest.TestCase):
    """Achado 57. O defeito que a V21 expos: com o recorte por subestacao, a
    EQPA ganhou 25 trocas que a base inteira desmente, e a Cemig perdeu os 21
    verdadeiros."""

    def test_o_trafo_da_subestacao_vizinha_nao_vira_troca(self):
        """`SE_A` tem o trecho de media que contem o `PAC_1` do trafo; o trafo
        e da `SE_B`. Perguntando so a `SE_B`, o `PAC_1` some da media e a
        troca acontece. Perguntando a BASE, nao."""
        u = {'COD_ID': _a('T1'), 'PAC_1': _a('MT_DA_VIZINHA'),
             'PAC_2': _a('MT_DAQUI'), 'CTMT': _a('F_B'),
             'POT_NOM': np.array([75.0]), 'TEN_LIN_SE': np.array([0.22]),
             'FAS_CON_P': _a('ABC'), 'FAS_CON_S': _a('ABCN')}
        base = _Base(u, mt=[('MT_DA_VIZINHA', 'X'), ('MT_DAQUI', 'Y')])
        self.assertEqual(tr.pacs_invertidos(base), set(),
                         'os dois PACs estao na media da BASE: nao e troca')

    def test_a_decisao_viaja_como_codigo(self):
        """O que vai para os processos trabalhadores sao COD_ID, e nao nos.
        Os 6,5 milhoes de nos de media da Cemig em 32 processos nao cabem."""
        b = _Base(_col('931212-BT', 'YDIJL62'), mt=[('YDIJL62', 'Z')])
        r = tr.pacs_invertidos(b)
        self.assertIsInstance(r, set)
        for x in r:
            self.assertIsInstance(x, str)


class _Leitor:
    def __init__(self, col):
        self.col = col

    def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
        return self.col

    def ler(self, camada, colunas=None, **kw):
        raise KeyError(camada)


def _gera(col, invertidos):
    tmp = tempfile.mkdtemp()
    t = os.path.join(tmp, 'Trafos.dss')
    n, sec, inv = tr.gerar(_Leitor(col), ['F1'], t,
                           os.path.join(tmp, 'Aterr.dss'), kv_mt=13.8,
                           invertidos=invertidos)
    with open(t, encoding='utf-8') as fh:
        return fh.read(), sec, inv


class OQueSaiNoArquivo(unittest.TestCase):

    def test_o_primario_vai_para_a_barra_de_media(self):
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'TX'})
        self.assertIn('~ wdg=1 bus=ydijl62', txt)
        self.assertIn('bus=931212-bt', txt)
        self.assertEqual(inv, ['TX'])

    def test_sem_decisao_nada_e_tocado(self):
        """Chamador que nao passa `invertidos` recebe o que a BDGD disser."""
        for vazio in (None, set(), frozenset()):
            txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), vazio)
            self.assertEqual(inv, [])
            self.assertIn('~ wdg=1 bus=931212-bt', txt)

    def test_o_secundario_e_que_vira_barra_de_carga(self):
        """`sec` alimenta cargas.py. Se ele apontar para a barra de media, as
        cargas de BT sao penduradas na media — o defeito ao contrario."""
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'TX'})
        self.assertIn('931212-bt', sec)
        self.assertNotIn('ydijl62', sec)

    def test_as_fases_nao_trocam(self):
        """FAS_CON_P ja descreve o lado de media. No 1018862858 ele e 'B',
        monofasico, como o primario de um 5 kVA tem de ser."""
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62', fp='B', fs='BN'),
                              {'TX'})
        self.assertIn('~ wdg=1 bus=ydijl62.2 ', txt,
                      "FAS_CON_P='B' e o no 2 do lado de MEDIA")

    def test_a_troca_e_declarada_no_arquivo(self):
        txt, sec, inv = _gera(_col('931212-BT', 'YDIJL62'), {'TX'})
        self.assertIn('TROCADOS', txt)
        self.assertIn('achados 54', txt)
        self.assertIn('pacs_invertidos', txt)
        self.assertIn('TX', txt.split('endireitados:')[1])

    def test_arquivo_limpo_nao_ganha_aviso(self):
        txt, sec, inv = _gera(_col('MT1', 'BT1'), set())
        self.assertNotIn('TROCADOS', txt)
        self.assertNotIn('endireitados', txt)

    def test_codigo_de_outra_subestacao_nao_afeta_esta(self):
        """A decisao e da base inteira, mas o relatorio de CADA subestacao so
        conta os que ela realmente tocou."""
        txt, sec, inv = _gera(_col('MT1', 'BT1'), {'DE_OUTRA_SE'})
        self.assertEqual(inv, [])


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
        txt, sec, inv = _gera(self._dois(), {'T1', 'T2'})
        self.assertEqual(sorted(inv), ['T1', 'T2'])
        self.assertEqual(txt.count('windings=3'), 2,
                         'os dois compartilham a MEDIA, nao a baixa — nao sao '
                         'banco, e cada um tem de sair com derivacao central')

    def test_sem_a_troca_eles_pareceriam_banco(self):
        """A prova de que a ordem importa: sem a decisao, o codigo le a barra
        compartilhada como secundaria e monta banco."""
        txt, sec, inv = _gera(self._dois(), set())
        self.assertEqual(inv, [])
        self.assertEqual(txt.count('windings=3'), 0)
        self.assertEqual(txt.count('windings=2'), 2)


if __name__ == '__main__':
    unittest.main()
