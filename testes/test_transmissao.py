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
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
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


def _fontes(pac_at, kv_at, componentes, por_sub=None):
    tmp = tempfile.mkdtemp()
    cam = os.path.join(tmp, 'Fontes.dss')
    info = {'pac_at': pac_at, 'kv_at_do_trafo': kv_at,
            'por_sub': por_sub or {'SUB': list(pac_at)}}
    r = transmissao.fontes(componentes, info, set(), {}, cam)
    with open(cam, encoding='utf-8') as fh:
        return fh.read(), r


def _basekv(txt):
    """{barra: basekV} das fontes escritas, Circuit inclusive."""
    out = {}
    for l in txt.splitlines():
        if l.startswith(('New Vsource.', 'New Circuit.')) and 'bus1=' in l:
            b = l.split('bus1=')[1].split()[0]
            out[b] = float(l.split('basekV=')[1].split()[0])
    return out


class TensaoDaFonteVemDoPatio(unittest.TestCase):
    """Achado 19 — e a correcao da propria correcao.

    A primeira versao escolhia o nivel MAIS ALTO do patio. Medido na
    Equatorial PA reconvertida, isso produziu 3 fontes com basekV que a barra
    nao tem: `jui_03b1` recebeu 138 kV numa barra de 13,8. A tensao da fonte
    tem de ser a do transformador que esta NAQUELA barra; o mais alto so vale
    como ultimo recurso.
    """

    def test_um_nivel_so_sai_nele(self):
        txt, _ = _fontes({'T1': 'b138'}, {'T1': 138.0}, [{'b138'}])
        self.assertEqual(list(_basekv(txt).values()), [138.0])

    def test_sem_dado_cai_no_padrao(self):
        txt, _ = _fontes({'T1': 'bx'}, {}, [{'bx'}])
        self.assertEqual(list(_basekv(txt).values()), [88.0])

    def test_patio_misto_usa_o_trafo_DA_BARRA(self):
        """Dois trafos no mesmo patio, 138 e 88, e a injecao cai na barra do
        de 88. A fonte tem de sair em 88 — nao em 138."""
        txt, _ = _fontes({'T138': 'outra', 'T88': 'ponto'},
                         {'T138': 138.0, 'T88': 88.0},
                         [{'outra', 'ponto'}])
        # `barra` = pac_at do primeiro trafo da componente, em ordem de dict
        kv = _basekv(txt)
        self.assertEqual(len(kv), 1)
        barra, base = next(iter(kv.items()))
        esperado = {'outra': 138.0, 'ponto': 88.0}[barra]
        self.assertEqual(base, esperado,
                         f'a fonte injeta em {barra}, cujo trafo e de '
                         f'{esperado:g} kV')

    def test_a_escolha_fica_escrita(self):
        txt, r = _fontes({'T138': 'p', 'T88': 'p2'},
                         {'T138': 138.0, 'T88': 88.0}, [{'p', 'p2'}])
        self.assertIn('ATENCAO', txt)
        self.assertEqual(r['patios_multinivel'], 1)

    def test_o_relatorio_conta_por_nivel(self):
        txt, r = _fontes({'A': 'ba', 'B': 'bb'}, {'A': 138.0, 'B': 88.0},
                         [{'ba'}, {'bb'}])
        self.assertEqual(r['niveis'], {'138': 1, '88': 1})

    def test_nivel_confirmado_pela_barra_nao_conta_como_deduzido(self):
        _, r = _fontes({'T1': 'b1'}, {'T1': 138.0}, [{'b1'}])
        self.assertEqual(r['nivel_deduzido'], 0)

    def test_sem_trafo_na_barra_o_nivel_e_DEDUZIDO_e_dito(self):
        """A componente tem 138 e 88, e a injecao cai numa barra que nao e de
        nenhum dos dois transformadores — o caso do `jui_03b1` da Equatorial
        PA, cuja barra esta em 13,8 kV. Nenhuma tensao de fonte estaria certa
        ali; o minimo e nao deixar essa fonte sair igual as outras."""
        txt, r = _fontes({'T138': 'pa', 'T88': 'pb'},
                         {'T138': 138.0, 'T88': 88.0},
                         [{'pa', 'pb', 'terceira'}])
        # a barra escolhida e o pac_at do primeiro trafo, entao ha confirmacao;
        # o caso deduzido exige que a injecao caia FORA das barras de trafo
        self.assertIn('nivel_deduzido', r)

    def test_cabeceira_ctat_fora_das_barras_de_trafo_e_deduzida(self):
        tmp = tempfile.mkdtemp()
        cam = os.path.join(tmp, 'Fontes.dss')
        info = {'pac_at': {'T138': 'pa', 'T88': 'pb'},
                'kv_at_do_trafo': {'T138': 138.0, 'T88': 88.0},
                'por_sub': {'SUB': ['T138', 'T88']}}
        # `head` esta na componente e NAO e barra de transformador nenhum
        transmissao.fontes([{'pa', 'pb', 'head'}], info, {'head'}, {}, cam)
        with open(cam, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertIn('bus1=head', txt)
        self.assertIn('nivel deduzido do patio', txt)


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
