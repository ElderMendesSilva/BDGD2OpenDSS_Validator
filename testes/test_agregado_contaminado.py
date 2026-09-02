# -*- coding: utf-8 -*-
"""Achado 58 — o agregado sai acompanhado da contaminação, sempre.

O aviso JA EXISTIA. `concordancia.implausivel` calculava
`fatia_da_perda_pct`, e o docstring dele ja dizia que fatia alta significa
"agregado feito por defeito, e nao por rede". Nao adiantou nada: o aviso morava
num campo separado, e ninguem juntou os dois.

O QUE ISSO CUSTOU. A `ENERGISA_M405` da V21 publicou perda agregada de
**4.271.643,88%** — quatro milhoes de por cento — com **99,9999%** dela vinda
de 17 alimentadores de 395. Atravessou 103 subestacoes e um relatorio de fecho
de sessao sem ninguem tropecar.

E NAO E UMA BASE. Nas 97 da V21, **34 das 81** com agregado carregam
contribuicao de alimentador implausivel:

    ENERGISA_M405   99,9999%      Roraima          24,34%
    Copel-Dis         92,55%      CEA              18,59%
    Equatorial 37     35,37%      Cemig-D          11,49%
    Enel RJ           34,30%      Enel SP           1,35%

Roraima PASSA na ancora externa com 4,84%, e um quarto dessa perda vem de
alimentador que o proprio validador marca como fisicamente impossivel.

A RELACAO E DE MAO UNICA, e vale registrar porque eu errei ao afirmar o
contrario: **todas as 7 que reprovam estao contaminadas, mas contaminacao
sozinha nao reprova** — 27 bases contaminadas passam.

POR QUE PUBLICAR OS DOIS E NUNCA TROCAR. Filtrar o que incomoda e exatamente o
grau de liberdade do achado 44 — escolher a composicao ate o numero ficar
bonito. Entao o bruto continua sendo `pct_modelo`, o contrafactual entra como
`pct_modelo_sem_implausiveis`, e a `contaminacao_pct` fica no MESMO dicionario.
Quem le um tropeca no outro.
"""
import io
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))

from bdgd2dss import concordancia as cc        # noqa: E402
import auditoria as au                         # noqa: E402


def par(m, d, kwh_m=1000.0, kwh_d=365000.0):
    return (m, d, kwh_m, kwh_d)


class OAgregadoDeclaraOQueOSujou(unittest.TestCase):

    def test_base_limpa_nao_tem_contaminacao(self):
        a = cc.agregado([par(3.0, 2.0) for _ in range(10)])
        self.assertAlmostEqual(a['contaminacao_pct'], 0.0)
        self.assertEqual(a['implausiveis'], 0)
        self.assertAlmostEqual(a['pct_modelo'],
                               a['pct_modelo_sem_implausiveis'], places=6)

    def test_o_caso_da_energisa_um_punhado_domina_tudo(self):
        """Dezessete de 395 carregando a perda inteira. Aqui, dois de 102."""
        sadios = [par(3.0, 3.0, kwh_m=1e6, kwh_d=1e6) for _ in range(100)]
        quebrados = [par(5.0e6, 3.0, kwh_m=1e6, kwh_d=1e6) for _ in range(2)]
        a = cc.agregado(sadios + quebrados)
        self.assertGreater(a['contaminacao_pct'], 99.0)
        self.assertEqual(a['implausiveis'], 2)
        self.assertAlmostEqual(a['pct_modelo_sem_implausiveis'], 3.0, places=3)
        self.assertGreater(a['pct_modelo'], 1000.0)

    def test_o_bruto_NUNCA_e_substituido(self):
        """A licao do achado 44: filtrar o que incomoda e o grau de liberdade
        que ja custou uma correcao. O bruto continua sendo `pct_modelo`."""
        a = cc.agregado([par(3.0, 3.0, kwh_m=1e6, kwh_d=1e6),
                         par(900.0, 3.0, kwh_m=1e6, kwh_d=1e6)])
        self.assertAlmostEqual(a['pct_modelo'], 451.5, places=1)
        self.assertAlmostEqual(a['pct_modelo_sem_implausiveis'], 3.0, places=3)
        self.assertNotAlmostEqual(a['pct_modelo'],
                                  a['pct_modelo_sem_implausiveis'])

    def test_os_dois_numeros_moram_no_MESMO_dicionario(self):
        """Este e o achado inteiro. O aviso ja existia noutro campo e nao
        adiantou; o que faltava era ele estar ao lado do numero que suja."""
        a = cc.agregado([par(3.0, 3.0)])
        for c in ('pct_modelo', 'pct_modelo_sem_implausiveis',
                  'contaminacao_pct', 'implausiveis', 'teto_implausivel'):
            self.assertIn(c, a, c)

    def test_o_teto_e_o_mesmo_do_implausivel(self):
        """Se os dois divergirem, o agregado passa a contar uma historia e o
        aviso outra — que e o defeito que este achado desfaz."""
        self.assertEqual(cc.agregado([par(3.0, 3.0)])['teto_implausivel'],
                         cc.TETO_MODELO)
        self.assertEqual(cc.implausivel([par(3.0, 3.0)])['teto'],
                         cc.TETO_MODELO)

    def test_no_teto_nao_e_acima_do_teto(self):
        """A comparacao e estrita. Um alimentador exatamente no teto e caso de
        rede ruim, e nao de modelo destruido."""
        a = cc.agregado([par(cc.TETO_MODELO, 3.0)])
        self.assertEqual(a['implausiveis'], 0)

    def test_vazio_nao_derruba(self):
        a = cc.agregado([])
        self.assertIsNone(a['contaminacao_pct'])
        self.assertIsNone(a['pct_modelo_sem_implausiveis'])
        self.assertEqual(a['implausiveis'], 0)

    def test_a_energia_tambem_sai_do_contrafactual(self):
        """Tirar a perda do alimentador quebrado e deixar a energia dele no
        denominador daria um numero menor que a rede sadia, e nao igual."""
        a = cc.agregado([par(3.0, 3.0, kwh_m=1e6, kwh_d=1e6),
                         par(900.0, 3.0, kwh_m=1e6, kwh_d=1e6)])
        self.assertAlmostEqual(a['pct_modelo_sem_implausiveis'], 3.0, places=3)


def _base(nome, perda=3.0, cont=0.0, reprova=False, commit='abc123',
          pac=0):
    return {'base': nome, 'perda_modelo_pct': perda, 'contaminacao_pct': cont,
            'reprova_ancora': reprova, 'commit': commit,
            'trafos_pac_invertido': pac}


class ORelatorioContaSozinho(unittest.TestCase):
    """As tres lacunas achadas a mao na V21 tinham a mesma forma: o numero
    existia no artefato e ninguem olhou. Ler com mais cuidado nao e conserto."""

    def _saida(self, indice):
        antigo, sys.stdout = sys.stdout, io.StringIO()
        try:
            au._relata(indice)
            return sys.stdout.getvalue()
        finally:
            sys.stdout = antigo

    def test_lista_quem_reprova_a_ancora(self):
        t = self._saida([_base('BOA'), _base('MA', perda=40.0, reprova=True)])
        self.assertIn('reprovam a ancora externa', t)
        self.assertIn('MA', t)
        self.assertIn('1 de 2', t)

    def test_perda_impossivel_e_categoria_PROPRIA(self):
        """Reprovar a ancora e ficar acima do teto da ANEEL, que rede ruim
        faz. Perda impossivel e um numero que rede nenhuma tem, e denuncia
        modelo destruido. Confundir as duas perde a ENERGISA_M405 no meio de
        seis bases que so perdem muito."""
        t = self._saida([_base('SO_RUIM', perda=9.0, reprova=True),
                         _base('DESTRUIDA', perda=4.2e6, reprova=True)])
        linha = [x for x in t.splitlines() if 'impossivel' in x][0]
        self.assertIn('DESTRUIDA', linha)
        self.assertNotIn('SO_RUIM', linha)

    def test_conta_as_contaminadas(self):
        t = self._saida([_base('A', cont=24.3), _base('B', cont=1.3),
                         _base('C', cont=99.99)])
        linha = [x for x in t.splitlines() if 'contaminada' in x][0]
        self.assertIn('A', linha)
        self.assertIn('C', linha)
        self.assertNotIn(' B,', linha)

    def test_rodada_sem_commit_e_denunciada(self):
        """A V21 saiu com `commit: ''` nas 97, e o relatorio de fecho afirmava
        que o no ficou pinado num commit. A rodada era verificavel so pela
        palavra de quem a rodou."""
        t = self._saida([_base('A', commit=''), _base('B', commit='')])
        self.assertIn('NAO rastreavel', t)

    def test_dois_commits_nao_sao_uma_rodada(self):
        t = self._saida([_base('A', commit='aaa'), _base('B', commit='bbb')])
        self.assertIn('NAO e uma rodada so', t)

    def test_rodada_com_um_commit_nao_reclama(self):
        t = self._saida([_base('A'), _base('B')])
        self.assertNotIn('NAO rastreavel', t)
        self.assertNotIn('NAO e uma rodada', t)

    def test_indice_vazio_nao_derruba(self):
        self.assertIn('reprovam', self._saida([]))

    def test_campo_ausente_ou_nulo_nao_derruba(self):
        t = self._saida([{'base': 'X'},
                         {'base': 'Y', 'perda_modelo_pct': None,
                          'contaminacao_pct': None}])
        self.assertIn('reprovam a ancora externa', t)


class OColetorLeAsDuasOrigens(unittest.TestCase):
    """`contaminacao_pct` nasceu no `agregado`; antes dele a mesma grandeza
    vivia em `modelo_implausivel`, longe do numero que ela suja. Ler as duas
    faz o relato valer para rodada gerada antes da mudanca — e a V21, que e a
    rodada que precisamos auditar, e uma delas."""

    def test_os_limiares_existem_e_sao_distintos(self):
        self.assertGreater(au.PERDA_IMPOSSIVEL, au.CONTAMINACAO_ALTA)
        self.assertEqual(au.CONTAMINACAO_ALTA, 10.0)
        self.assertEqual(au.PERDA_IMPOSSIVEL, 30.0)

    def test_o_teto_de_perda_impossivel_passa_das_bases_reais(self):
        """A pior base sadia das 97 perde 7,4%; a Copel-Dis, que reprova,
        perde 41,6%. O teto tem de ficar entre as duas."""
        self.assertGreater(au.PERDA_IMPOSSIVEL, 7.4)
        self.assertLess(au.PERDA_IMPOSSIVEL, 41.62)


if __name__ == '__main__':
    unittest.main()
