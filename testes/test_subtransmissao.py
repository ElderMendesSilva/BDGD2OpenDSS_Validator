# -*- coding: utf-8 -*-
"""Vaos e transformadores de barra.

Achado 1 de ACHADOS_GENERALIZACAO.md: `Transformer.TRB_5003585_34p5` definido
duas vezes em Roraima, impedindo a compilacao da subestacao inteira. Nunca
disparou na Enel SP.
"""
import inspect
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss import subtransmissao as st         # noqa: E402


def _ctmt(cod, sub, barr, pac, kv, tr='T1'):
    return {'sub': sub, 'barr': barr, 'pac_ini': pac, 'uni_tr_at': tr,
            'kv': kv, 'ten_nom': '49'}


def _info(barras, mva=100.0, kv_barra=13.8):
    """`barra_do_trafo` e `kv_da_barra` sao indexados pelo NOME NORMALIZADO
    da barra — o `vaos` aplica `_no()` ao CTMT.BARR antes de consultar. Montar
    o dicionario com o nome cru faz a consulta falhar em silencio e nenhuma
    derivacao acontecer, que foi o que mascarou este teste na primeira versao.
    """
    bt = {tr: st._no(b) for tr, b in barras.items()}
    return {'barra_do_trafo': bt,
            'kv_da_barra': {b: kv_barra for b in bt.values()},
            'mva_por_sub': {'SE1': mva}}


def _nomes_de_trafo(por_se):
    """Todos os `New Transformer.X` que sairam, por subestacao."""
    out = []
    for _, linhas in (por_se or {}).items():
        for bloco in linhas:
            out += re.findall(r'New Transformer\.(\S+)', bloco)
    return out


class BarraDerivada(unittest.TestCase):
    """A BDGD poe alimentadores de niveis diferentes no mesmo CTMT.BARR.

    Quando a tensao do alimentador difere da barra, ele vai para uma barra
    derivada, ligada a original por um transformador de barra.
    """

    def test_mesmo_nivel_nao_deriva(self):
        """Alimentador na tensao da propria barra nao precisa de derivacao."""
        info = _info({'T1': 'BMT1'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 13.8)}
        ligados, sem_vao, por_se = st.vaos(ctmt, info, set())
        self.assertEqual(sem_vao, [])
        self.assertFalse(ligados['F1']['derivada'])
        self.assertEqual(_nomes_de_trafo(por_se), [])

    def test_nivel_diferente_cria_barra_derivada(self):
        info = _info({'T1': 'BMT1'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 34.5)}
        ligados, _, por_se = st.vaos(ctmt, info, set())
        self.assertTrue(ligados['F1']['derivada'])
        self.assertAlmostEqual(ligados['F1']['kv'], 34.5)
        self.assertEqual(len(_nomes_de_trafo(por_se)), 1,
                         'um transformador de barra por nivel derivado')

    def test_dois_alimentadores_mesmo_nivel_um_so_trafo(self):
        """Dois alimentadores de 34,5 kV na MESMA barra compartilham o
        transformador de barra — nao pode sair um por alimentador."""
        info = _info({'T1': 'BMT1'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 34.5),
                'F2': _ctmt('F2', 'SE1', 'BMT1', 'P2', 34.5)}
        _, _, por_se = st.vaos(ctmt, info, set())
        self.assertEqual(len(_nomes_de_trafo(por_se)), 1)

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_duas_barras_de_origem_geram_nome_repetido(self):
        """O caso de Roraima, subestacao 5003585.

        Duas barras de origem DISTINTAS (BMT1 e BMT2) na mesma subestacao,
        ambas com alimentador de 34,5 kV. O dicionario `derivadas` e indexado
        por (sub, barra_original, kv), mas o transformador e nomeado
        `TRB_{sub}_{kv}` — SEM a barra de origem. Saem dois elementos com o
        mesmo nome e o OpenDSS recusa:

            (#266) Duplicate new element definition: Transformer.TRB_..._34p5

        Correcao proposta no passo 5: nomear a partir da barra derivada, que
        ja e unica por chave.
        """
        info = _info({'T1': 'BMT1', 'T2': 'BMT2'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 34.5, tr='T1'),
                'F2': _ctmt('F2', 'SE1', 'BMT2', 'P2', 34.5, tr='T2')}
        _, _, por_se = st.vaos(ctmt, info, set())
        nomes = _nomes_de_trafo(por_se)
        self.assertEqual(len(nomes), len(set(nomes)),
                         f'nomes repetidos: {nomes}')


def _base_at(pac_1_do_trafo):
    """Base minima de alta tensao: uma malha de SSDAT e um trafo de potencia.

    O unico parametro e o que o achado 7 mede — por onde o UNTRAT diz que se
    liga. O resto e identico nos dois cenarios, para que a diferenca
    observada nao possa vir de outra coisa.
    """
    return {
        'untrat': {'COD_ID': ['T1'], 'SUB': ['SE1'],
                   'BARR_1': ['BAT1'], 'BARR_2': ['BMT1'],
                   'PAC_1': [pac_1_do_trafo], 'PAC_2': ['B1'],
                   'POT_NOM': [25.0], 'FAS_CON_P': ['ABC'],
                   'FAS_CON_S': ['ABC'], 'SIT_ATIV': ['AT']},
        'eqtrat': {},
        'ssdat': {'COD_ID': ['A1'], 'PAC_1': ['PAT1'], 'PAC_2': ['PAT2'],
                  'CTAT': ['CT1'], 'FAS_CON': ['ABC'], 'TIP_CND': ['C1'],
                  'COMP': [1000.0]},
        'unseat': {k: [] for k in ('COD_ID', 'PAC_1', 'PAC_2', 'FAS_CON',
                                   'P_N_OPE', 'SUB', 'SIT_ATIV')},
        'ctat': {'COD_ID': ['CT1'], 'NOME': ['LTA XXX-YYY 1'],
                 'TEN_NOM': ['84'], 'PAC_INI': ['PAT1']},
        # BAT1 existe e e o que BARR_1 aponta — nos DOIS cenarios.
        'bar': {'COD_ID': ['BAT1'], 'SUB': ['SE1'], 'TEN_NOM': ['84'],
                'PAC': ['PAT1'], 'TIP_INST': ['SE_AT']},
    }


class AncoragemDaAltaTensao(unittest.TestCase):
    """Achado 7: a chave que liga UNTRAT a rede de AT muda entre bases.

    Medido nas duas bases de porte comparavel:

        UNTRAT.PAC_1 presente na SSDAT     Enel SP 94,2%    Light  0,0%
        UNTRAT.BARR_1 em BAR.COD_ID        Enel SP 94,8%    Light 94,6%

    O conversor amarra por PAC porque foi assim que a convencao da Enel SP
    foi decifrada por engenharia reversa. Resultado na Light: 0 trechos de
    AT, 0 fontes, 0 km — a camada inteira saiu vazia, com uma SSDAT
    impecavel de 7.909 trechos e 2.380,8 km do lado.

    A SSDAT dos dois cenarios abaixo e a MESMA. So muda o campo de ligacao.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _monta(self, pac):
        dados = _base_at(pac)
        info = st.trafos(dados, os.path.join(self.tmp, 'Trafos_AT.dss'),
                         subs_alvo={'SE1'})
        comps, _ = st.componentes(dados)
        malha = set().union(*comps) if comps else set()
        return dados, info, malha

    def test_a_malha_existe_e_e_a_mesma_nos_dois_cenarios(self):
        """Controle. Se a malha diferisse, o teste seguinte nao provaria
        nada sobre a ancoragem."""
        _, _, m1 = self._monta('PAT1')
        _, _, m2 = self._monta('SE1_TRAFO_01')
        self.assertEqual(m1, m2)
        self.assertEqual(m1, {'pat1', 'pat2'})

    def test_convencao_da_enel_sp_o_trafo_cai_dentro_da_malha(self):
        _, info, malha = self._monta('PAT1')
        self.assertEqual(info['n'], 1)
        self.assertIn(info['pac_at']['T1'], malha)

    def test_convencao_da_light_o_trafo_cai_numa_ilha(self):
        """O defeito, medido. O transformador continua sendo emitido — nada
        avisa —, so que o primario dele fica num no que nao existe na rede de
        AT. E o `converter` seleciona os patios pela intersecao entre esses
        nos e as componentes: intersecao vazia, nenhum trecho emitido."""
        _, info, malha = self._monta('SE1_TRAFO_01')
        self.assertEqual(info['n'], 1, 'o trafo sai mesmo assim')
        self.assertNotIn(info['pac_at']['T1'], malha)
        self.assertFalse(set(info['pac_at'].values()) & malha,
                         'e essa intersecao vazia que zera a camada de AT')

    def test_barr_1_e_lido_da_base_e_nunca_consultado(self):
        """`carregar` traz BARR_1 de UNTRAT e nenhum modulo o usa — so
        BARR_2, para o secundario. O campo que casa nas duas bases esta na
        memoria do processo o tempo todo, sem ser olhado."""
        fonte = inspect.getsource(st)
        self.assertEqual(fonte.count('BARR_1'), 1,
                         'unica ocorrencia: a lista de colunas de carregar()')
        self.assertIn("'BARR_1'", inspect.getsource(st.carregar))
        self.assertGreater(fonte.count('BARR_2'), 1,
                           'BARR_2 e lido E usado — a diferenca e o achado 7')

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_o_primario_tem_de_cair_na_malha(self):
        """O criterio de aceitacao do passo 5, enunciado pelo RESULTADO e nao
        pelo mecanismo: o primario do transformador de potencia tem de chegar
        na rede de AT, seja qual for a ancora que se adote.

        Duas candidatas estao registradas no achado 7 e nenhuma foi decidida:
        BARR_1 -> BAR.COD_ID -> BAR.PAC (que resolve a Enel SP, onde BAR.PAC
        cai na SSDAT em 45,0%, mas nao a Light, onde cai em 0,0%), ou ancorar
        na barra de AT da subestacao que o `malha_at` ja cria a partir de
        UNSEAT.SUB e UNTRAT.SUB. O teste aceita as duas.
        """
        _, info, malha = self._monta('SE1_TRAFO_01')
        self.assertTrue(set(info['pac_at'].values()) & malha,
                        'trafo de potencia ilhado: a camada de AT sai vazia')


if __name__ == '__main__':
    unittest.main()
