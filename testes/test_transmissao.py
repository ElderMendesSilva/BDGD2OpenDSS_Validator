# -*- coding: utf-8 -*-
"""Subestacoes da transmissora — uma fonte por patio, nao por nivel de MT.

Achado 18. A decomposicao AT-SE nao rodou na Equatorial PA:

    (#266) Duplicate new element definition: "Vsource.FONTE_SSB_88kv".
    Element being redefined.
    [file: _AT/Trafos_Transmissora.dss, line: 112]

`trafos_transmissora` percorre (subestacao, nivel de MT), mas a fonte
pertence ao patio, que e (subestacao, nivel de AT). Uma subestacao que
alimenta 13,8 kV e 34,5 kV a partir do mesmo barramento de 88 kV passava duas
vezes pela mesma fonte.

A linha repetida era IDENTICA — nome, barra, basekV e MVAsc saem todos de
(sub, kv1) —, entao nao havia diferenca eletrica nenhuma. O estrago era o
tratamento: o C-API recusa a redefinicao e o MASTER-AT inteiro deixa de
compilar; o motor da EPRI aceita calado e a segunda definicao apaga a
primeira. Duplicata exata nao deveria produzir nem uma coisa nem outra.

Medido nas quatro bases ja regeradas na V10: 2 duplicatas na Equatorial PA
(SSB e TUR), 0 em Roraima, 0 na Enel CE, 0 na Enel SP — de 19.484 elementos
de AT na Enel SP, que e a maior.
"""
import os
import re
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import transmissao                     # noqa: E402

RX = re.compile(r'^New\s+(\S+?)\.(\S+)', re.M)


def _gera(orfas, isa=None):
    tmp = tempfile.mkdtemp()
    cam = os.path.join(tmp, 'Trafos_Transmissora.dss')
    barras, info = transmissao.trafos_transmissora(orfas, isa or {}, cam)
    with open(cam, encoding='utf-8') as fh:
        return fh.read(), barras, info


def _nomes(txt):
    return [f'{t}.{n}' for t, n in RX.findall(txt)]


class UmaFontePorPatio(unittest.TestCase):

    def test_dois_niveis_de_mt_no_mesmo_patio_dao_UMA_fonte(self):
        """O caso da SSB: 13,8 kV e 34,5 kV saindo do mesmo 88 kV."""
        txt, _, _ = _gera({'SSB': {13.8: ['A1', 'A2'], 34.5: ['A3']}})
        fontes = [n for n in _nomes(txt) if n.startswith('Vsource.')]
        self.assertEqual(fontes, ['Vsource.FONTE_SSB_88kv'])

    def test_nenhum_nome_se_repete(self):
        """A propriedade que importa, e nao so para a Vsource: um arquivo do
        OpenDSS nao pode definir o mesmo elemento duas vezes."""
        txt, _, _ = _gera({'SSB': {13.8: ['A1'], 34.5: ['A2'], 20.0: ['A3']},
                           'TUR': {13.8: ['B1'], 34.5: ['B2']},
                           'ALC': {13.8: ['C1']}})
        nomes = _nomes(txt)
        self.assertEqual(len(nomes), len(set(nomes)),
                         f'duplicados: {[n for n in nomes if nomes.count(n) > 1]}')

    def test_o_trafo_continua_um_por_nivel_de_mt(self):
        """A fonte e por patio; o TRANSFORMADOR e por nivel de MT, e essa
        distincao e o ponto. Deduplicar a fonte nao pode levar o trafo junto."""
        txt, _, _ = _gera({'SSB': {13.8: ['A1'], 34.5: ['A2']}})
        tt = [n for n in _nomes(txt) if n.startswith('Transformer.')]
        self.assertEqual(sorted(tt),
                         ['Transformer.TT_SSB_13p8', 'Transformer.TT_SSB_34p5'])

    def test_cada_alimentador_continua_com_a_sua_barra_de_mt(self):
        """A deduplicacao nao pode custar o mapeamento: os tres alimentadores
        continuam apontando para a barra do seu proprio nivel."""
        _, barras, _ = _gera({'SSB': {13.8: ['A1', 'A2'], 34.5: ['A3']}})
        self.assertEqual(barras['A1']['barra'], barras['A2']['barra'])
        self.assertNotEqual(barras['A1']['barra'], barras['A3']['barra'])
        self.assertEqual(barras['A3']['kv'], 34.5)

    def test_a_omissao_fica_escrita_no_arquivo(self):
        """Linha suprimida em silencio e linha que ninguem sabe que faltou."""
        txt, _, _ = _gera({'SSB': {13.8: ['A1'], 34.5: ['A2']}})
        self.assertIn('ja foi emitida', txt)

    def test_subestacoes_diferentes_no_mesmo_nivel_nao_colidem(self):
        txt, _, _ = _gera({'SSB': {13.8: ['A1']}, 'TUR': {13.8: ['B1']}})
        fontes = sorted(n for n in _nomes(txt) if n.startswith('Vsource.'))
        self.assertEqual(fontes,
                         ['Vsource.FONTE_SSB_88kv', 'Vsource.FONTE_TUR_88kv'])

    def test_contagem_do_relatorio_nao_muda(self):
        """`n_eq` conta PARES (sub, nivel de MT), que e o que dimensiona os
        equivalentes. Ele nao pode cair junto com a fonte deduplicada."""
        _, _, info = _gera({'SSB': {13.8: ['A1'], 34.5: ['A2']}})
        self.assertEqual(info['equivalente'], 2)


class NiveisDeAtDiferentesContinuamSeparados(unittest.TestCase):
    """O motivo pelo qual a barra depende do nivel de AT, ja registrado no
    codigo: com uma barra so, duas Vsource caiam no mesmo no com basekV
    diferente e 29 alimentadores da TBAN ficavam sem tensao."""

    def test_dois_niveis_de_at_dao_duas_fontes(self):
        isa = {'TBAN': [{'kv1': 345.0, 'kv2': 34.5, 'mva': 100.0},
                        {'kv1': 88.0, 'kv2': 20.0, 'mva': 50.0}]}
        txt, _, _ = _gera({'TBAN': {34.5: ['A1'], 20.0: ['A2']}}, isa)
        fontes = sorted(n for n in _nomes(txt) if n.startswith('Vsource.'))
        self.assertEqual(fontes,
                         ['Vsource.FONTE_TBAN_345kv', 'Vsource.FONTE_TBAN_88kv'])


if __name__ == '__main__':
    unittest.main()
