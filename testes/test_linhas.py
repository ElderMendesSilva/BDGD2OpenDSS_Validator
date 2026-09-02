# -*- coding: utf-8 -*-
"""Comprimento de trecho — achado 16.

Um trecho de 1 mm na Equatorial PA parou a subestacao CUO e consumiu ~3,5 h
das 3,7 h que o `verifica` levou na rodada V10:

    (#183) Y matrix build aborted due to error in primitive Y calculations
    Matrix Inversion Error for Line "13302_10678971"

O conversor tem guarda para comprimento nulo — `if comp <= 0: comp = 1.0` —
mas o guarda olha a ENTRADA e o defeito nasce na SAIDA: `Length={comp:.2f}`
escreve `0.00` para qualquer valor abaixo de 0,005 m. Com comprimento zero a
matriz de impedancia fica toda nula, o OpenDSS nao consegue inverte-la e
aborta a montagem da Y da REDE INTEIRA — uma linha derruba a subestacao.

Censo nas sete bases: 6 trechos em 24,4 milhoes, e NENHUM deles tem COMP <= 0.
O guarda existente nunca disparou uma vez. O caso que ele cobre nao e o que
aparece.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
from bdgd2dss import linhas                          # noqa: E402

MAPA = {'C1': {1: 'CND_C1_1F', 2: 'CND_C1_2F', 3: 'CND_C1_3F',
               'r1': 0.5, 'x1': 0.35}}


def _col(comps, fases='ABC'):
    """Uma leitura de SSDMT/SSDBT ja feita, no formato que `gerar` aceita."""
    n = len(comps)
    s = lambda *v: np.array(v, dtype=object)          # noqa: E731
    return {'COD_ID': s(*[f'S{i}' for i in range(n)]),
            'PAC_1': s(*[f'B{i}' for i in range(n)]),
            'PAC_2': s(*[f'B{i+100}' for i in range(n)]),
            'CTMT': s(*['F1'] * n),
            'FAS_CON': s(*[fases] * n),
            'TIP_CND': s(*['C1'] * n),
            'COMP': np.array(comps, dtype=float)}


def _gera(comps, fn='gerar', **kw):
    tmp = tempfile.mkdtemp()
    dest = os.path.join(tmp, 'Linhas.dss')
    getattr(linhas, fn)(None, MAPA, ['F1'], dest, col=_col(comps, **kw))
    with open(dest, encoding='utf-8') as fh:
        return fh.read()


def _lengths(txt, prefixo='New Line.'):
    """Os valores escritos em Length=, na ordem."""
    out = []
    for l in txt.splitlines():
        if l.startswith(prefixo) and 'Length=' in l:
            out.append(l.split('Length=')[1].split()[0])
    return out


class OGuardaAtual(unittest.TestCase):
    """O que ja funciona, e que precisa continuar funcionando."""

    def test_comprimento_zero_vira_um_metro(self):
        self.assertEqual(_lengths(_gera([0.0]))[0], '1.00')

    def test_comprimento_negativo_vira_um_metro(self):
        self.assertEqual(_lengths(_gera([-5.0]))[0], '1.00')

    def test_comprimento_ausente_vira_um_metro(self):
        """`num(None, 1.0)` devolve o padrao, e o padrao ja e 1 m."""
        col = _col([10.0])
        col['COMP'] = np.array([float('nan')])
        tmp = tempfile.mkdtemp()
        dest = os.path.join(tmp, 'Linhas.dss')
        linhas.gerar(None, MAPA, ['F1'], dest, col=col)
        with open(dest, encoding='utf-8') as fh:
            self.assertEqual(_lengths(fh.read())[0], '1.00')

    def test_comprimento_normal_passa_intacto(self):
        self.assertEqual(_lengths(_gera([120.0, 7.1]))[:2], ['120.00', '7.10'])


class ComprimentoQueZeraNoFormato(unittest.TestCase):
    """O achado 16. O trecho e positivo, passa no guarda, e vira 0.00.

    Marcado como defeito conhecido: a correcao muda a saida do conversor e
    ficou retida enquanto a rodada V10 esta em voo, para nao deixar tres bases
    geradas com um codigo e quatro com outro.
    """
    def test_corrigido_um_milimetro_vira_zero(self):
        """COMP = 0,001 m. O valor real do trecho 13302_10678971 da CUO."""
        self.assertNotEqual(_lengths(_gera([0.001]))[0], '0.00')
    def test_corrigido_nenhum_comprimento_escrito_e_zero(self):
        """A propriedade que importa, independente do valor de entrada:
        nenhuma linha pode sair com comprimento nulo."""
        for v in _lengths(_gera([0.001, 0.0023, 0.0043, 0.0046, 0.00361])):
            self.assertNotEqual(float(v), 0.0)
    def test_corrigido_o_neutro_da_bt_zera_igual(self):
        """A BT escreve o neutro em km com `{comp/1000:.5f}` — mesmo limiar de
        0,005 m, e este e o pior dos tres porque a rede de BT e onde estao 4
        dos 5 casos da Equatorial PA."""
        txt = _gera([0.001], fn='gerar_bt')
        neutros = [l for l in txt.splitlines() if l.startswith('New Line.N_')]
        self.assertTrue(neutros, 'a BT precisa emitir o neutro')
        v = neutros[0].split('Length=')[1].split()[0]
        self.assertNotEqual(float(v), 0.0)


class OPisoDeUmCentimetro(unittest.TestCase):
    """`COMP_MINIMO = 0,01 m`. Abaixo dele o `{:.2f}` em metros e o `{:.5f}`
    em km zerariam, e comprimento zero aborta a montagem da Y da rede inteira.

    1 cm esta abaixo de qualquer medicao real — o menor piso entre as sete
    distribuidoras e 0,10 m, da Cemig-D —, acima da resolucao dos dois
    formatos, e nao move o km do relatorio."""

    def test_o_piso_e_aplicado_e_o_resto_passa_intacto(self):
        self.assertEqual(_lengths(_gera([0.0049]))[0], '0.01')
        self.assertEqual(_lengths(_gera([0.001]))[0], '0.01')
        self.assertEqual(_lengths(_gera([3.24]))[0], '3.24')

    def test_o_piso_nao_sobe_para_um_metro(self):
        """Preservar o valor declarado importa: um vao de 1 mm continua sendo
        um vao curto, e nao um vao de um metro. O 1,0 m e so para campo
        AUSENTE, onde nao ha dado nenhum a preservar."""
        self.assertNotEqual(_lengths(_gera([0.001]))[0], '1.00')

    def test_km_do_relatorio_nao_e_afetado(self):
        """O `km` devolvido soma o comprimento REAL, nao o escrito. Um trecho
        de 1 mm nao move o total — o que confirma que o dano e so eletrico."""
        tmp = tempfile.mkdtemp()
        _, km, _, _ = linhas.gerar(None, MAPA, ['F1'],
                                os.path.join(tmp, 'L.dss'),
                                col=_col([1000.0, 0.001]))
        self.assertAlmostEqual(km, 1.0, places=5)


if __name__ == '__main__':
    unittest.main()
