# -*- coding: utf-8 -*-
"""Vaos e transformadores de barra.

Achado 1 de ACHADOS_GENERALIZACAO.md: `Transformer.TRB_5003585_34p5` definido
duas vezes em Roraima, impedindo a compilacao da subestacao inteira. Nunca
disparou na Enel SP.
"""
import os
import re
import sys
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


class AncoragemDaAltaTensao(unittest.TestCase):
    """Achado 7: a chave que liga UNTRAT a rede de AT muda entre bases.

    Medido: `UNTRAT.PAC_1` casa com a SSDAT em 94,2% na Enel SP e 0,0% na
    Light; `BARR_1` casa com `BAR.COD_ID` em 94,8% e 94,6%. O conversor usa
    PAC, e por isso a camada de AT da Light saiu com 0 trechos e 0 fontes.

    Este teste enuncia o requisito. Vai ficar como falha esperada ate o passo
    5 migrar a ancoragem — e ai vira o teste de nao-regressao da mudanca mais
    arriscada do plano.
    """

    @unittest.expectedFailure
    def test_DEFEITO_CONHECIDO_ancora_deveria_aceitar_barr(self):
        self.assertTrue(
            hasattr(st, 'ancorar_por_barr'),
            'a ancoragem por BARR->BAR.COD_ID ainda nao existe; hoje so ha '
            'a ancoragem por PAC, que falha em 100% dos trafos da Light')


if __name__ == '__main__':
    unittest.main()
