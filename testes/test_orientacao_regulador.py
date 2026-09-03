# -*- coding: utf-8 -*-
"""A orientacao do regulador de tensao — achado 30.

O `RegControl` e emitido com `winding=2`, assumindo que o `PAC_2` do UNREMT e
o lado da carga. A BDGD nao declara direcao, e quando o `PAC_2` e o lado da
FONTE o controle regula o que nao pode mudar: corre o tape ate o limite e,
porque o tape no enrolamento da fonte DIVIDE o lado da carga, deixa a rede
pior do que ficaria sem regulador nenhum.

Medido com o tape zerado para separar o efeito da causa:

    subestacao   sem regulador   como estava   controle no lado certo
    NHER3            0,9869        0,8984            1,0266
    IJI              0,9960        0,9056            1,0194

O CRITERIO E A DIRECAO DO FLUXO, e chegou-se a ele depois de duas medidas
erradas: "qual lado tem maior tensao" e ruido, porque o regulador tem
impedancia quase nula (os dois lados diferem por 0,0002 pu); e "qual lado
esta mais perto da fonte" tambem nao serve, porque o elemento tem
comprimento zero e `Bus.Distance()` da o mesmo valor nos dois lados.

Estes testes cobrem a logica pura de `orientacao.py`, sem OpenDSS — a parte
que decide, e que e onde um erro se esconde sem barulho.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import orientacao                           # noqa: E402


class TestLadoDaFonte(unittest.TestCase):

    def test_potencia_positiva_no_terminal_1_e_a_fonte(self):
        """Positivo = entrando no elemento. Se entra pelo terminal 1, a
        fonte esta do lado 1."""
        self.assertEqual(orientacao.lado_da_fonte([100.0, -99.5]), 1)

    def test_potencia_positiva_no_terminal_2_e_a_fonte(self):
        self.assertEqual(orientacao.lado_da_fonte([-99.5, 100.0]), 2)

    def test_sem_fluxo_devolve_none(self):
        """Sem corrente nao ha direcao. Regulador em trecho morto ou em
        alimentador desligado fica sem resposta, e nao com uma resposta
        arbitraria."""
        self.assertIsNone(orientacao.lado_da_fonte([0.0, 0.0]))
        self.assertIsNone(orientacao.lado_da_fonte([0.0000001, -0.0000001]))

    def test_lista_vazia_ou_curta_devolve_none(self):
        self.assertIsNone(orientacao.lado_da_fonte([]))
        self.assertIsNone(orientacao.lado_da_fonte([5.0]))
        self.assertIsNone(orientacao.lado_da_fonte(None))

    def test_fluxo_abaixo_do_minimo_nao_decide(self):
        """Ruido numerico nao pode virar decisao — o mesmo erro que a
        comparacao de tensao cometeu (0,0002 pu de diferenca virando
        "resultado")."""
        quase_zero = orientacao.FLUXO_MINIMO_KW * 0.5
        self.assertIsNone(orientacao.lado_da_fonte([quase_zero, -quase_zero]))

    def test_fluxo_no_limiar_decide(self):
        acima = orientacao.FLUXO_MINIMO_KW * 2
        self.assertEqual(orientacao.lado_da_fonte([acima, -acima]), 1)


class TestCorrigir(unittest.TestCase):

    def test_controle_no_lado_da_fonte_e_corrigido(self):
        """O caso da NHER3 e da IJI: fonte no terminal 1, controle no
        enrolamento 1 -> esta errado, tem que ir para o 2."""
        regs = [{'nome': 'RC1', 'winding': 1, 'p_terminais': [50.0, -49.9]}]
        corr, sem = orientacao.corrigir(regs)
        self.assertEqual(len(corr), 1)
        self.assertEqual(corr[0]['nome'], 'RC1')
        self.assertEqual(corr[0]['de'], 1)
        self.assertEqual(corr[0]['para'], 2)
        self.assertEqual(sem, [])

    def test_controle_no_lado_da_carga_nao_e_tocado(self):
        """Fonte no terminal 1, controle no enrolamento 2 -> ja esta certo."""
        regs = [{'nome': 'RC1', 'winding': 2, 'p_terminais': [50.0, -49.9]}]
        corr, sem = orientacao.corrigir(regs)
        self.assertEqual(corr, [])
        self.assertEqual(sem, [])

    def test_sem_fluxo_fica_registrado_e_nao_corrigido(self):
        """Regulador em trecho morto: nao adivinha, so declara que nao deu
        para decidir."""
        regs = [{'nome': 'RC1', 'winding': 2, 'p_terminais': [0.0, 0.0]}]
        corr, sem = orientacao.corrigir(regs)
        self.assertEqual(corr, [])
        self.assertEqual(sem, ['RC1'])

    def test_kw_registrado_e_o_maior_dos_dois_terminais(self):
        """Fonte no terminal 1 (positivo), controle no enrolamento 1 ->
        errado, e o kW registrado e o maior dos dois terminais."""
        regs = [{'nome': 'RC1', 'winding': 1, 'p_terminais': [51.2, -51.1]}]
        corr, _sem = orientacao.corrigir(regs)
        self.assertAlmostEqual(corr[0]['kW'], 51.2, places=3)

    def test_lista_vazia_ou_none_nao_quebra(self):
        self.assertEqual(orientacao.corrigir([]), ([], []))
        self.assertEqual(orientacao.corrigir(None), ([], []))

    def test_multiplos_reguladores_mistos(self):
        """Reproduz o caso real da NHER3: 6 reguladores, 3 com fluxo real (e
        errados), 3 sem fluxo."""
        regs = [
            {'nome': 'RC1', 'winding': 1, 'p_terminais': [51.1, -51.0]},
            {'nome': 'RC2', 'winding': 1, 'p_terminais': [52.3, -52.2]},
            {'nome': 'RC3', 'winding': 1, 'p_terminais': [51.8, -51.7]},
            {'nome': 'RC4', 'winding': 2, 'p_terminais': [0.0, 0.0]},
            {'nome': 'RC5', 'winding': 2, 'p_terminais': [0.0, 0.0]},
            {'nome': 'RC6', 'winding': 2, 'p_terminais': [0.0, 0.0]},
        ]
        corr, sem = orientacao.corrigir(regs)
        self.assertEqual(len(corr), 3)
        self.assertEqual(len(sem), 3)
        self.assertEqual({c['nome'] for c in corr}, {'RC1', 'RC2', 'RC3'})
        # `corrigir` nao ordena — quem ordena por kW e' `escrever`, na
        # hora de montar o arquivo. Aqui so a composicao do conjunto importa.


class TestEscrever(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='orient_')
        self.caminho = os.path.join(self.d, '_REGULADORES.dss')

    def test_arquivo_vazio_quando_nao_ha_correcao(self):
        """SEMPRE escrito, mesmo vazio: o MASTER redireciona sem condicao, e
        `redirect` de arquivo ausente aborta a compilacao."""
        orientacao.escrever(self.caminho, [], 0, ())
        self.assertTrue(os.path.exists(self.caminho))
        txt = open(self.caminho, encoding='utf-8').read()
        self.assertIn('nenhum regulador invertido', txt)

    def test_arquivo_com_correcao_tem_o_comando_dss(self):
        corr = [{'nome': 'RC1', 'de': 1, 'para': 2, 'kW': 51.1}]
        orientacao.escrever(self.caminho, corr, 1, ())
        txt = open(self.caminho, encoding='utf-8').read()
        self.assertIn('RegControl.RC1.winding=2', txt)
        self.assertIn('51.1', txt)

    def test_cabecalho_conta_corrigidos_total_e_sem_fluxo(self):
        corr = [{'nome': 'RC1', 'de': 1, 'para': 2, 'kW': 10.0}]
        orientacao.escrever(self.caminho, corr, 4, ('RC2', 'RC3', 'RC4'))
        txt = open(self.caminho, encoding='utf-8').read()
        self.assertIn('1 regulador(es) corrigido(s) de 4 medido(s)', txt)
        self.assertIn('3 sem fluxo', txt)

    def test_maior_kw_primeiro(self):
        """O regulador que mais pesa vem no topo do arquivo, para quem le
        saber por onde comecar a conferir."""
        corr = [{'nome': 'RC_pequeno', 'de': 1, 'para': 2, 'kW': 5.0},
                {'nome': 'RC_grande', 'de': 1, 'para': 2, 'kW': 500.0}]
        orientacao.escrever(self.caminho, corr, 2, ())
        txt = open(self.caminho, encoding='utf-8').read()
        self.assertLess(txt.index('RC_grande'), txt.index('RC_pequeno'))

    def test_apagar_o_redirect_e_dito_no_cabecalho(self):
        """A premissa tem que dizer como se desfaz, como as outras tres."""
        orientacao.escrever(self.caminho, [], 0, ())
        txt = open(self.caminho, encoding='utf-8').read()
        self.assertIn('_REGULADORES.dss', txt)
        self.assertIn('apague', txt.lower())


if __name__ == '__main__':
    unittest.main()
