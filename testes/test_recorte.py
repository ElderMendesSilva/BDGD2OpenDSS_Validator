# -*- coding: utf-8 -*-
"""O recorte por subestação separa o que a rede declara junto?

O achado 12 mostrou que a fragmentação é característica POR DISTRIBUIDORA: 40
de 76 bases com mediana ZERO de ramos isolados por km, e a Light com 45,8. O
conversor é o mesmo para as 97, então o gatilho está no dado — ou na interação
dele com uma premissa nossa.

A premissa suspeita é o recorte: o `converter.py` monta um modelo por
subestação e filtra a SSDMT pelos CTMTs daquela SE. Trecho de CTMT alheio fica
de fora, e o que vinha depois dele vira ramo isolado.

Um PAC tocado por trechos de duas subestações é um ponto de corte. Contá-los é
o teste, e ele não precisa de OpenDSS.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'diagnosticos'))
import recorte                                          # noqa: E402


class _BDGDFalsa:
    """`ctmt` = [(cod, sub)], demais camadas = [(pac1, pac2, ctmt)].

    Cada camada devolve o SEU dado. A primeira versao devolvia o mesmo para
    todas, e por isso nao provava nada sobre chaves e reguladores costurarem
    trechos — que e justamente o que o diagnostico passou a medir.
    """

    def __init__(self, ctmt, **camadas):
        import numpy as np
        self._c = {'COD_ID': np.array([x[0] for x in ctmt], dtype=object),
                   'SUB': np.array([x[1] for x in ctmt], dtype=object)}
        self._cam = {}
        for nome, linhas in camadas.items():
            self._cam[nome.upper()] = {
                'PAC_1': np.array([x[0] for x in linhas], dtype=object),
                'PAC_2': np.array([x[1] for x in linhas], dtype=object),
                'CTMT': np.array([x[2] for x in linhas], dtype=object)}

    def ler(self, camada, cols):
        if camada == 'CTMT':
            return self._c
        if camada not in self._cam:
            raise KeyError(camada)          # como a BDGD real, sem a camada
        return self._cam[camada]


def _mede(ctmt, ssdmt, **outras):
    real = recorte.BDGD
    recorte.BDGD = lambda *a, **k: _BDGDFalsa(ctmt, SSDMT=ssdmt, **outras)
    try:
        return recorte.cortes_da_base('/qualquer.gdb')
    finally:
        recorte.BDGD = real


class OPontoDeCorteEUmPACDeDuasSubestacoes(unittest.TestCase):

    def test_rede_de_uma_SE_so_nao_tem_corte(self):
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 0)
        self.assertEqual(r['pacs'], 3)

    def test_PAC_compartilhado_por_duas_SEs_e_corte(self):
        """`p2` liga um trecho da SE_A a um da SE_B. O conversor monta as duas
        separadamente, e o que estiver do outro lado de `p2` some de cada uma."""
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_B')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 1)
        self.assertAlmostEqual(r['pct_pacs_multi_se'], 100 / 3, places=2)

    def test_CTMTs_DIFERENTES_da_MESMA_SE_nao_sao_corte(self):
        """Este é o falso positivo que invalidaria a medida: o recorte é por
        SUBESTAÇÃO, não por alimentador. Dois CTMTs da mesma SE entram juntos
        no mesmo modelo, e o PAC entre eles não separa nada."""
        r = _mede([('C1', 'SE_A'), ('C2', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C2')])
        self.assertEqual(r['pacs_multi_se'], 0)

    def test_trecho_com_CTMT_desconhecido_e_contado_e_ignorado(self):
        """CTMT que não está na tabela CTMT não tem SE, e chutar uma seria
        inventar topologia. Fica de fora da conta e é RELATADO."""
        r = _mede([('C1', 'SE_A')],
                  [('p1', 'p2', 'C1'), ('p9', 'p8', 'FANTASMA')])
        self.assertEqual(r['trechos_sem_ctmt_conhecido'], 1)
        self.assertEqual(r['pacs'], 2, 'os PACs do trecho orfao nao entram')

    def test_PAC_vazio_nao_vira_no(self):
        r = _mede([('C1', 'SE_A')], [('p1', '', 'C1'), ('', 'p2', 'C1')])
        self.assertEqual(r['pacs'], 2)

    def test_tres_SEs_no_mesmo_PAC_conta_uma_vez(self):
        r = _mede([('C1', 'A'), ('C2', 'B'), ('C3', 'C')],
                  [('x', 'p', 'C1'), ('p', 'y', 'C2'), ('p', 'z', 'C3')])
        self.assertEqual(r['pacs_multi_se'], 1)
        self.assertEqual(r['subestacoes_no_ctmt'], 3)

    def test_base_vazia_nao_derruba(self):
        r = _mede([], [])
        self.assertEqual((r['pacs'], r['pacs_multi_se']), (0, 0))
        self.assertEqual(r['pct_pacs_multi_se'], 0.0)


class AsComponentesDizemSeARedeEncadeia(unittest.TestCase):
    """As duas primeiras hipóteses caíram; esta mede o que sobrou.

    O recorte por SE não corta (92 de 97 bases com ZERO PACs multi-SE, e a
    Light — a pior em fragmentação — com zero) e trecho órfão tampouco (82 de
    97 com zero, Light com zero). Sobra a possibilidade de os PACs simplesmente
    NÃO ENCADEAREM dentro da própria subestação.

    Uma SE radial sadia tem UMA componente. Milhares significam que a BDGD
    declara pedaços que não se tocam — e aí o ramo isolado não é efeito do
    nosso recorte, é o que está escrito na tabela.
    """

    def test_rede_encadeada_da_uma_componente(self):
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C1'), ('p3', 'p4', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 1)
        self.assertEqual(r['pct_ses_fragmentadas'], 0.0)

    def test_dois_pedacos_que_nao_se_tocam_dao_duas(self):
        r = _mede([('C1', 'A')], [('p1', 'p2', 'C1'), ('p9', 'p8', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 2)
        self.assertEqual(r['pct_ses_fragmentadas'], 100.0)

    def test_conta_por_SUBESTACAO_e_nao_pela_base_toda(self):
        """Duas SEs sadias e separadas NÃO são fragmentação: cada uma vira o
        seu próprio modelo. Contar a base como um grafo só diria 2 componentes
        e acusaria rede perfeita."""
        r = _mede([('C1', 'A'), ('C2', 'B')],
                  [('a1', 'a2', 'C1'), ('b1', 'b2', 'C2')])
        self.assertEqual(r['componentes_por_se_mediana'], 1)
        self.assertEqual(r['ses_com_uma_componente'], 2)
        self.assertEqual(r['pct_ses_fragmentadas'], 0.0)

    def test_o_mesmo_PAC_em_SEs_diferentes_nao_une_as_duas(self):
        """`p` aparece nas duas, mas cada SE vira um modelo separado — unir
        contaria como conexa uma rede que o conversor separa."""
        r = _mede([('C1', 'A'), ('C2', 'B')],
                  [('p', 'a2', 'C1'), ('p', 'b2', 'C2')])
        self.assertEqual(r['ses_medidas'], 2)
        self.assertEqual(r['componentes_por_se_mediana'], 1)

    def test_anel_nao_conta_duas_vezes(self):
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p2', 'p3', 'C1'), ('p3', 'p1', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 1)

    def test_base_vazia_nao_divide_por_zero(self):
        r = _mede([], [])
        self.assertEqual(r['pct_ses_fragmentadas'], 0.0)
        self.assertEqual(r['componentes_por_se_max'], 0)


class ARedeNaoESoASSDMT(unittest.TestCase):
    """Medir só a SSDMT mede uma rede que nunca foi construída.

    A primeira execução deu 384 componentes por subestação na mediana nacional
    — e a CEREJ5352, que tem ZERO ramos isolados no modelo, apareceu com 42. O
    modelo que o `converter` emite inclui CHAVES (UNSEMT) e REGULADORES
    (UNREMT), que também têm PAC_1/PAC_2 e costuram trechos.
    """

    def test_a_chave_costura_dois_pedacos(self):
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p3', 'p4', 'C1')],
                  UNSEMT=[('p2', 'p3', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 1,
                         'a chave liga os dois trechos')

    def test_sem_a_chave_ficam_dois(self):
        """O contraste que dá sentido ao teste anterior."""
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p3', 'p4', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 2)

    def test_o_regulador_tambem_costura(self):
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p3', 'p4', 'C1')],
                  UNREMT=[('p2', 'p3', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 1)

    def test_camada_ausente_nao_derruba(self):
        """Base sem UNREMT é comum, e não pode virar erro."""
        r = _mede([('C1', 'A')], [('p1', 'p2', 'C1')])
        self.assertEqual(r['componentes_por_se_mediana'], 1)

    def test_conta_quantas_ligacoes_cada_camada_deu(self):
        """Sem isso não dá para saber de qual tabela a rede depende."""
        r = _mede([('C1', 'A')],
                  [('p1', 'p2', 'C1'), ('p3', 'p4', 'C1')],
                  UNSEMT=[('p2', 'p3', 'C1')])
        self.assertEqual(r['ligacoes_por_camada']['SSDMT'], 2)
        self.assertEqual(r['ligacoes_por_camada']['UNSEMT'], 1)

    def test_laco_no_mesmo_PAC_nao_conta_como_ligacao(self):
        r = _mede([('C1', 'A')], [('p1', 'p1', 'C1'), ('p1', 'p2', 'C1')])
        self.assertEqual(r['ligacoes_por_camada']['SSDMT'], 1)


class QuaisSubestacoesAguentamABTCompleta(unittest.TestCase):
    """A mediana esconde a cauda, e e a cauda que decide o caso da Cemig.

    Ela tem mediana 5 e MAXIMO 1.844 componentes por subestacao: poucas SEs
    catastroficas ao lado de muitas trataveis. Como o `converter` aceita
    `--se`, a pergunta util deixa de ser "a base aguenta BT completa?" e passa
    a ser "QUAIS subestacoes aguentam?" — e so a lista por SE responde.
    """

    def test_a_lista_so_sai_quando_pedida(self):
        """Carregar milhares de SEs em toda medicao inflaria o JSON das 97."""
        real = recorte.BDGD
        recorte.BDGD = lambda *a, **k: _BDGDFalsa(
            [('C1', 'A')], SSDMT=[('p1', 'p2', 'C1')])
        try:
            self.assertIsNone(recorte.cortes_da_base('/x.gdb')['por_se'])
            d = recorte.cortes_da_base('/x.gdb', por_se=True)
        finally:
            recorte.BDGD = real
        self.assertEqual(d['por_se'], [{'se': 'A', 'componentes': 1}])

    def test_a_sadia_vem_antes_da_fragmentada(self):
        real = recorte.BDGD
        recorte.BDGD = lambda *a, **k: _BDGDFalsa(
            [('C1', 'A'), ('C2', 'B')],
            SSDMT=[('b1', 'b2', 'C2'), ('b9', 'b8', 'C2'),
                   ('a1', 'a2', 'C1')])
        try:
            d = recorte.cortes_da_base('/x.gdb', por_se=True)
        finally:
            recorte.BDGD = real
        self.assertEqual([x['se'] for x in d['por_se']], ['A', 'B'])
        self.assertEqual([x['componentes'] for x in d['por_se']], [1, 2])


if __name__ == '__main__':
    unittest.main()
