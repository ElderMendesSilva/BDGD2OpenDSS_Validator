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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'etapas'))
from bdgd2dss import malha_at                     # noqa: E402
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

    def test_duas_barras_de_origem_geram_nomes_distintos(self):
        """O caso de Roraima, subestacao 5003585.

        Duas barras de origem DISTINTAS (BMT1 e BMT2) na mesma subestacao,
        ambas com alimentador de 34,5 kV. O dicionario `derivadas` e indexado
        por (sub, barra_original, kv), mas o transformador era nomeado
        `TRB_{sub}_{kv}` — SEM a barra de origem. Saiam dois elementos com o
        mesmo nome e o OpenDSS recusava o arquivo inteiro:

            (#266) Duplicate new element definition: Transformer.TRB_..._34p5

        Corrigido no passo 5: o nome sai da barra derivada, que ja e unica
        por chave.
        """
        info = _info({'T1': 'BMT1', 'T2': 'BMT2'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 34.5, tr='T1'),
                'F2': _ctmt('F2', 'SE1', 'BMT2', 'P2', 34.5, tr='T2')}
        _, _, por_se = st.vaos(ctmt, info, set())
        nomes = _nomes_de_trafo(por_se)
        self.assertEqual(len(nomes), 2, 'um transformador por barra de origem')
        self.assertEqual(len(nomes), len(set(nomes)),
                         f'nomes repetidos: {nomes}')

    def test_o_nome_do_trafo_de_barra_acompanha_a_barra_derivada(self):
        """Nao basta ser unico: tem de ser rastreavel ate a barra que ele
        alimenta, senao ninguem liga um ao outro lendo o .dss."""
        info = _info({'T1': 'BMT1'})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT1', 'P1', 34.5)}
        ligados, _, por_se = st.vaos(ctmt, info, set())
        nomes = _nomes_de_trafo(por_se)
        self.assertEqual(nomes, ['TRB_' + ligados['F1']['barra']])


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
        # A chave de AT declara a subestacao a que pertence, e os PACs dela
        # estao na malha. E o que a medicao encontrou em todas as sete bases:
        # `UNTRAT.SUB` aparece em `UNSEAT.SUB` de 75,9% a 100%.
        'unseat': {'COD_ID': ['SW1'], 'PAC_1': ['PAT1'], 'PAC_2': ['PAT2'],
                   'FAS_CON': ['ABC'], 'P_N_OPE': ['F'], 'SUB': ['SE1'],
                   'SIT_ATIV': ['AT']},
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

    def _monta(self, pac, com_reserva=False):
        """Monta a camada de AT na MESMA ordem do converter.

        `com_reserva=False` reproduz o comportamento antigo — ancora so por
        PAC_1 — para que o contraste entre as duas convencoes continue
        medivel depois da correcao.
        """
        dados = _base_at(pac)
        comps, _ = st.componentes(dados)
        malha = set().union(*comps) if comps else set()
        extra = {}
        if com_reserva:
            anc = malha_at.ancoras(dados)
            com_barra = {s for n, ss in anc.items() if n in malha for s in ss}
            extra = {'nos_malha': malha,
                     'barra_de_sub': lambda s: (malha_at.barra_de(s)
                                                if s in com_barra else '')}
        info = st.trafos(dados, os.path.join(self.tmp, 'Trafos_AT.dss'),
                         subs_alvo={'SE1'}, **extra)
        return dados, info, malha

    def _ligado(self, dados, info, malha):
        """O primario chega na rede de AT? Direto, ou pela barra da SE que o
        `malha_at` liga aos trechos que a reivindicam."""
        anc = malha_at.ancoras(dados)
        comps, _ = st.componentes(dados)
        m = malha_at.gerar(comps, anc, os.path.join(self.tmp, 'Barras_AT.dss'))
        alcancaveis = set(malha) | set(m['barra_por_sub'].values())
        return set(info['pac_at'].values()) & alcancaveis

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

    def test_sem_a_reserva_a_convencao_da_light_ilha_o_trafo(self):
        """O defeito de partida, preservado como medida. Ancorando so por
        PAC_1, o transformador continua sendo emitido — nada avisa —, mas o
        primario fica num no que nao existe na rede de AT. E o `converter`
        seleciona os patios pela intersecao entre esses nos e as componentes:
        intersecao vazia, nenhum trecho emitido."""
        _, info, malha = self._monta('SE1_TRAFO_01', com_reserva=False)
        self.assertEqual(info['n'], 1, 'o trafo sai mesmo assim')
        self.assertNotIn(info['pac_at']['T1'], malha)
        self.assertFalse(set(info['pac_at'].values()) & malha,
                         'e essa intersecao vazia que zera a camada de AT')

    def test_a_reserva_traz_o_trafo_para_a_barra_da_subestacao(self):
        _, info, malha = self._monta('SE1_TRAFO_01', com_reserva=True)
        self.assertEqual(info['ancorados_por_barra_sub'], 1)
        self.assertEqual(info['pac_at']['T1'], malha_at.barra_de('SE1'))

    def test_a_reserva_nao_mexe_em_quem_ja_esta_na_malha(self):
        """A convencao da Enel SP nao pode regredir: 99,5% dos trafos dela
        casam por PAC_1, e trocar isso por uma barra sintetica perderia a
        topologia real do patio."""
        _, info, malha = self._monta('PAT1', com_reserva=True)
        self.assertEqual(info['ancorados_por_barra_sub'], 0)
        self.assertEqual(info['pac_at']['T1'], 'pat1')

    def test_barra_recusada_mantem_o_pac_original(self):
        """Subestacao que a malha nao vai ligar nao ganha barra. Apontar o
        primario para uma barra que ninguem cria seria trocar um trafo
        ilhado por outro, so que mais dificil de rastrear."""
        dados = _base_at('SE1_TRAFO_01')
        comps, _ = st.componentes(dados)
        malha = set().union(*comps) if comps else set()
        info = st.trafos(dados, os.path.join(self.tmp, 'Trafos_AT.dss'),
                         subs_alvo={'SE1'}, nos_malha=malha,
                         barra_de_sub=lambda s: '')
        self.assertEqual(info['ancorados_por_barra_sub'], 0)
        self.assertEqual(info['pac_at']['T1'], 'se1_trafo_01')

    def test_barr_1_e_lido_da_base_e_nunca_consultado(self):
        """`carregar` traz BARR_1 de UNTRAT e nenhum modulo o usa — so
        BARR_2, para o secundario. O campo que casa nas duas bases esta na
        memoria do processo o tempo todo, sem ser olhado."""
        fonte = inspect.getsource(st)
        self.assertIn("'BARR_1'", inspect.getsource(st.carregar),
                      'a coluna e lida da base')
        self.assertNotIn("u['BARR_1']", fonte,
                         'lida e nunca indexada: nenhum modulo a consulta')
        self.assertIn("u['BARR_2']", fonte,
                      'BARR_2 e lido E usado — a diferenca e o achado 7')

    def test_e_usar_barr_1_nao_teria_resolvido(self):
        """O desfecho do achado 7, e a licao dele.

        Parecia obvio que bastava trocar a ancora para `BARR_1`, que casa
        com `BAR.COD_ID` de 86% a 100% em todas as bases. A medicao mostrou
        que nao: o `BAR.PAC` daquela barra nao esta na SSDAT em nenhuma base
        alem da Enel SP. `BARR_1` identifica a barra e nao chega a rede.

        Este teste tranca o caso: mesmo com BARR_1 apontando para uma barra
        que existe em BAR, se o PAC dela nao estiver na malha, a ancora por
        barra nao liga nada.
        """
        dados = _base_at('SE1_TRAFO_01')
        bar = dados['bar']
        bar['PAC'] = ['FORA_DA_MALHA']            # o caso das seis bases
        comps, _ = st.componentes(dados)
        malha = set().union(*comps) if comps else set()
        pac_da_barra = {bar['COD_ID'][0]: malha_at._no(bar['PAC'][0])}
        self.assertIn('BAT1', pac_da_barra, 'BARR_1 casa com BAR.COD_ID')
        self.assertNotIn(pac_da_barra['BAT1'], malha,
                         'e mesmo assim nao chega na rede de AT')

    def test_o_primario_chega_na_rede_nas_duas_convencoes(self):
        """O criterio de aceitacao do passo 5, enunciado pelo RESULTADO e nao
        pelo mecanismo — e foi bom que tenha sido.

        As duas candidatas registradas no achado 7 eram BARR_1 -> BAR.COD_ID
        -> BAR.PAC, e a barra de AT da subestacao. A medicao nas SETE bases
        (`diagnosticos/at_cobertura.py`) refutou a primeira: BARR_1 casa com
        BAR.COD_ID de 86% a 100%, mas o BAR.PAC correspondente nao esta na
        SSDAT em nenhuma base alem da Enel SP (0,0%). Ela identifica a barra
        e nao chega a rede.

        A que sobrou — UNTRAT.SUB em UNSEAT.SUB — cobre de 75,9% (Roraima) a
        100%, mediana 98,2%. Um teste escrito pelo mecanismo teria travado a
        correcao errada.
        """
        for pac in ('PAT1', 'SE1_TRAFO_01'):
            dados, info, malha = self._monta(pac, com_reserva=True)
            self.assertTrue(self._ligado(dados, info, malha),
                            f'com PAC_1={pac} o trafo ficou ilhado')


class TensaoDeCabeceiraUnica(unittest.TestCase):
    """A subestacao nao pode ter duas tensoes de cabeceira.

    No modelo GERAL quem sustenta a barra de MT e o transformador de AT, com
    `tap` = mediana de CTMT.TEN_OPE. No modelo ISOLADO nao ha esse
    transformador: a fonte o substitui, e tem de reproduzir o mesmo pu.

    Nao reproduzia. O `converter` calculava o pu do isolado por outro caminho
    — o primeiro alimentador da iteracao, ou um `1.0` embutido no fallback —
    e 5 das 150 subestacoes com trafo de AT ficavam com pu != tap, sempre por
    0,09 pu, que e a distancia entre operar a 1,09 e operar a 1,00.

    Uma equipe externa relatou subtensao generalizada na DALP: abriram o
    modelo isolado, que dizia 1,00, enquanto o geral dizia 1,09. Depois da
    correcao a tensao media da DALP foi de 0,9351 para 1,0144, e a DVTA — que
    ja concordava — nao mudou nem na quarta casa.

    Este teste guarda a regra: uma grandeza, uma fonte de verdade.
    """

    def test_a_mediana_e_a_regra_para_o_tap(self):
        """O tap sai da MEDIANA dos alimentadores, nao do primeiro. Com 14
        alimentadores em 1,09 e um em 1,00, a barra opera em 1,09."""
        import statistics
        ope = [1.09] * 14 + [1.00]
        self.assertEqual(statistics.median(ope), 1.09)

    def test_primeiro_alimentador_nao_representa_a_barra(self):
        """O caso da DALP invertido: se o primeiro da iteracao declarar 1,00
        e a maioria 1,09, escolher o primeiro erra por 0,09 pu."""
        import statistics
        ope = [1.00] + [1.09] * 13
        self.assertNotEqual(ope[0], statistics.median(ope))
        self.assertAlmostEqual(abs(ope[0] - statistics.median(ope)), 0.09, 3)

    def test_o_converter_usa_a_mesma_fonte_nos_dois_caminhos(self):
        """Trava estrutural: o `pu` do MASTER isolado tem de sair de
        `tap_por_se`, o mesmo dicionario que alimenta o tap do trafo de AT.
        Se alguem voltar a derivar o pu de `ten_ope` diretamente ali, as duas
        tensoes de cabeceira divergem de novo e ninguem percebe."""
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(raiz, 'etapas', 'converter.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn("tap_se = (est_at.get('tap_por_se') or {}).get(se)", fonte,
                      'o pu do isolado tem de vir do mesmo tap do trafo de AT')
        self.assertIn("tap_se or ctmt_info[c]['ten_ope']", fonte,
                      'o tap manda; ten_ope so entra como reserva')
        # O ULTIMO RECURSO, conferido no proprio trecho e nao no arquivo
        # inteiro. Ate 24/08/2026 esta linha procurava o literal
        # `(kv_se, tap_se or 1.0)`. O achado 52 trocou aquele `1.0` cego pelo
        # `ten_ope` DECLARADO de cada alimentador, que e mais forte — e o
        # teste quebrou por procurar a forma em vez da garantia.
        #
        # A garantia e uma so: o pu do ultimo recurso nao pode ser 1,0 fixo
        # quando ha tap. Foi assim que a DALP saiu com 1,00 no modelo isolado
        # e 1,09 no geral, e uma equipe de fora relatou subtensao que nao
        # existia.
        i = fonte.index('SEM VAO NENHUM')
        ultimo = fonte[i:i + 1400]
        self.assertIn('tap_se or', ultimo,
                      'o ultimo recurso ignorou o tap da subestacao')
        self.assertNotIn('or 1.0)', ultimo,
                         'voltou o 1.0 fixo no ultimo recurso: e a divergencia '
                         'de 0,09 pu da DALP de novo')


class BarraDaSubestacaoNoGrupo(unittest.TestCase):
    """A barra de AT de uma subestacao pertence ao grupo que ela liga.

    Parece detalhe de contabilidade e nao e. O `transmissao.fontes` procura,
    em cada grupo, os transformadores cujo primario esta ali; se a barra
    ficar de fora, todo trafo ancorado por ela (achado 7) fica sem fonte.

    Medido em Roraima no dia em que a ancora nova entrou: **1 fonte para 12
    patios** e 88,8% das cargas do MASTER-GERAL sem tensao. Depois da
    correcao, 12 fontes e 13,2%. Defeito introduzido pela propria correcao,
    invisivel nos modelos por subestacao — que tem fonte propria e passavam
    20 de 20.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_a_barra_entra_no_grupo(self):
        dados = _base_at('SE1_TRAFO_01')
        comps, _ = st.componentes(dados)
        anc = malha_at.ancoras(dados)
        m = malha_at.gerar(comps, anc,
                           os.path.join(self.tmp, 'Barras_AT.dss'))
        barra = malha_at.barra_de('SE1')
        self.assertIn(barra, m['barra_por_sub'].values())
        self.assertTrue(any(barra in g for g in m['grupos']),
                        'sem isso o patio inteiro fica sem fonte')

    def test_a_barra_fica_no_grupo_dos_trechos_dela(self):
        """Nao basta estar em ALGUM grupo: tem de estar no mesmo dos trechos
        que ela liga, senao a fonte nasce noutro patio."""
        dados = _base_at('SE1_TRAFO_01')
        comps, _ = st.componentes(dados)
        anc = malha_at.ancoras(dados)
        m = malha_at.gerar(comps, anc,
                           os.path.join(self.tmp, 'Barras_AT.dss'))
        barra = malha_at.barra_de('SE1')
        g = [x for x in m['grupos'] if barra in x][0]
        self.assertIn('pat1', g, 'a barra e os trechos no mesmo grupo')


if __name__ == '__main__':
    unittest.main()


def _info_com_sub(barras, kv_por_barra, por_sub, mva=100.0):
    """Como `_info`, mas com `por_sub` — o elo que a quarta preferencia usa.

    `por_sub` mapeia a subestacao para os COD_ID dos transformadores de AT
    dela, que e exatamente o que a UNTRAT declara e o `vaos` ate hoje so
    alcancava pelo `UNI_TR_AT` do alimentador.
    """
    bt = {tr: st._no(b) for tr, b in barras.items()}
    return {'barra_do_trafo': bt,
            'kv_da_barra': {st._no(b): kv for b, kv in kv_por_barra.items()},
            'mva_por_sub': {s: mva for s in por_sub},
            'por_sub': por_sub}


class AncoraPelaSubestacao(unittest.TestCase):
    """Achado 31 — sem BARR e sem UNI_TR_AT valido, resta a propria SE.

    Na Cemig-D isso valia a subestacao 1726751 inteira: cinco alimentadores
    sem vao, logo sem EnergyMeter, logo 7.803 cargas fora de toda medicao de
    perda. Os dois transformadores de AT dela sempre estiveram na UNTRAT.
    """

    def setUp(self):
        self.info = _info_com_sub({'T1': 'BMT1'}, {'BMT1': 13.8},
                                  {'SE1': ['T1']})

    def test_sem_barr_e_sem_trafo_valido_usa_o_trafo_da_sub(self):
        # o caso da Cemig-D: BARR com um espaco, UNI_TR_AT que nao existe
        ctmt = {'F1': _ctmt('F1', 'SE1', ' ', 'P1', 13.8, tr='0')}
        ligados, sem_vao, _ = st.vaos(ctmt, self.info, set())
        self.assertEqual(sem_vao, [], 'o alimentador continuou sem vao')
        self.assertEqual(ligados['F1']['barra'], st._no('BMT1'))

    def test_sai_o_vao_e_o_monitor(self):
        """Sem a Line.VAO nao ha onde pendurar o EnergyMeter, que e o ponto
        inteiro do achado."""
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 13.8, tr='0')}
        _, _, por_se = st.vaos(ctmt, self.info, set())
        texto = '\n'.join(por_se['SE1'])
        self.assertIn('New Line.VAO_F1', texto)
        self.assertIn('New Monitor.M_F1', texto)

    def test_nao_atropela_as_preferencias_anteriores(self):
        """BARR valida continua mandando: a nova regra e ULTIMA."""
        info = _info_com_sub({'T1': 'BMT1', 'T2': 'BMT2'},
                             {'BMT1': 13.8, 'BMT2': 13.8},
                             {'SE1': ['T1', 'T2']})
        ctmt = {'F1': _ctmt('F1', 'SE1', 'BMT2', 'P1', 13.8, tr='T1')}
        ligados, _, _ = st.vaos(ctmt, info, set())
        self.assertEqual(ligados['F1']['barra'], st._no('BMT2'))

    def test_prefere_o_trafo_que_ja_esta_na_tensao_do_alimentador(self):
        """Escolher pela tensao evita criar barra derivada onde nao precisa."""
        info = _info_com_sub({'T1': 'B138', 'T2': 'B345'},
                             {'B138': 13.8, 'B345': 34.5},
                             {'SE1': ['T1', 'T2']})
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 34.5, tr='0')}
        ligados, _, por_se = st.vaos(ctmt, info, set())
        self.assertEqual(ligados['F1']['barra'], st._no('B345'))
        self.assertFalse(ligados['F1']['derivada'])
        self.assertEqual(_nomes_de_trafo(por_se), [],
                         'escolheu a barra certa e ainda assim derivou')

    def test_sem_trafo_na_tensao_certa_deriva_como_sempre(self):
        info = _info_com_sub({'T1': 'B138'}, {'B138': 13.8}, {'SE1': ['T1']})
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 34.5, tr='0')}
        ligados, _, por_se = st.vaos(ctmt, info, set())
        self.assertTrue(ligados['F1']['derivada'])
        self.assertEqual(len(_nomes_de_trafo(por_se)), 1)

    def test_a_escolha_nao_depende_da_ordem_de_leitura(self):
        """Duas rodadas com a lista de trafos embaralhada dao o mesmo vao —
        senao o modelo mudaria sem ninguem ter mexido em nada."""
        a = _info_com_sub({'T2': 'BX', 'T1': 'BY'}, {'BX': 13.8, 'BY': 13.8},
                          {'SE1': ['T2', 'T1']})
        b = _info_com_sub({'T1': 'BY', 'T2': 'BX'}, {'BY': 13.8, 'BX': 13.8},
                          {'SE1': ['T1', 'T2']})
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 13.8, tr='0')}
        self.assertEqual(st.vaos(ctmt, a, set())[0]['F1']['barra'],
                         st.vaos(ctmt, b, set())[0]['F1']['barra'])

    def test_subestacao_sem_trafo_nenhum_continua_sem_vao(self):
        """A regra nao inventa barra: sem trafo de AT declarado, nao ha ancora
        e o alimentador segue reportado."""
        info = _info_com_sub({}, {}, {'SE9': []})
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 13.8, tr='0')}
        _, sem_vao, _ = st.vaos(ctmt, info, set())
        self.assertEqual(sem_vao, ['F1'])

    def test_o_pac_igual_a_ancora_nao_vira_vao_de_comprimento_zero(self):
        info = _info_com_sub({'T1': 'P1'}, {'P1': 13.8}, {'SE1': ['T1']})
        ctmt = {'F1': _ctmt('F1', 'SE1', '', 'P1', 13.8, tr='0')}
        _, sem_vao, _ = st.vaos(ctmt, info, set())
        self.assertEqual(sem_vao, ['F1'])


class DoisNiveisNaMesmaBarra(unittest.TestCase):
    """Achado 39 — `BARR_2` nomeia o patio, nao a barra.

    Na Equatorial PA, 18 das 112 barras de secundario aparecem com DUAS
    tensoes. Na subestacao RIM os dois transformadores de AT declaram
    `BARR_2=RIM01B1` com secundarios de 13,8 e 34,5 kV. Escritos na mesma
    barra, os dois enrolamentos disputam: o de 13,8 kV e 12,5 MVA vencia o de
    34,5 kV e 6,3 MVA, e os tres alimentadores de 34,5 kV pendurados ali
    ficavam com 40% da tensao. Medido na RIM: perdas de 78,26%, Vmin 0,658.
    Corrigido: 0,44% e 0,987.
    """

    def _info(self, barras, kvs, por_sub):
        bt = {tr: st._no(b) for tr, b in barras.items()}
        return {'barra_do_trafo': bt,
                'kv_da_barra': {st._no(b): kv for b, kv in kvs.items()},
                'mva_por_sub': {s: 100.0 for s in por_sub},
                'por_sub': por_sub}

    def test_um_nivel_so_nao_muda_nada(self):
        """A regra e cirurgica: fora da subestacao multi-nivel ela nao opina,
        e as preferencias de sempre decidem."""
        info = self._info({'T1': 'B1', 'T2': 'B2'},
                          {'B1': 13.8, 'B2': 13.8}, {'SE1': ['T1', 'T2']})
        c = _ctmt('F1', 'SE1', 'B1', 'P1', 13.8)
        self.assertIsNone(st._barra_no_nivel(c, info, 13.8, None))

    def test_com_dois_niveis_a_tensao_manda(self):
        info = self._info({'T1': 'B138', 'T2': 'B345'},
                          {'B138': 13.8, 'B345': 34.5}, {'SE1': ['T1', 'T2']})
        c = _ctmt('F1', 'SE1', 'B138', 'P1', 34.5)   # BARR aponta para a errada
        self.assertEqual(st._barra_no_nivel(c, info, 13.8, None),
                         st._no('B345'))

    def test_a_barra_declarada_perde_para_a_tensao(self):
        """O caso da RIM: o CTMT.BARR dos alimentadores de 34,5 kV aponta para
        `RIM09B1`, que nenhum transformador declara. Seguir a BARR levava
        todos para a barra de 13,8."""
        info = self._info({'T1': 'RIM01B1', 'T2': 'RIM01B1_34p5kv'},
                          {'RIM01B1': 13.8, 'RIM01B1_34p5kv': 34.5},
                          {'RIM': ['T1', 'T2']})
        c = _ctmt('RIM09W1', 'RIM', 'RIM09B1', 'P1', 34.5)
        ligados, sem_vao, _ = st.vaos({'RIM09W1': c}, info, set())
        self.assertEqual(sem_vao, [])
        self.assertEqual(ligados['RIM09W1']['barra'],
                         st._no('RIM01B1_34p5kv'))
        self.assertFalse(ligados['RIM09W1']['derivada'],
                         'ancorou na tensao certa e ainda assim derivou')

    def test_sem_trafo_na_tensao_do_alimentador_devolve_nada(self):
        info = self._info({'T1': 'B138', 'T2': 'B345'},
                          {'B138': 13.8, 'B345': 34.5}, {'SE1': ['T1', 'T2']})
        c = _ctmt('F1', 'SE1', 'B138', 'P1', 69.0)
        self.assertIsNone(st._barra_no_nivel(c, info, 13.8, None))


class UmaBarraPorNivelDeSecundario(unittest.TestCase):
    """O nome da barra tem de ser estavel entre rodadas."""

    def _tabela(self, linhas):
        import numpy as np
        cols = {k: np.array([l[i] for l in linhas], dtype=object)
                for i, k in enumerate(('COD_ID', 'SUB', 'BARR_2', 'PAC_2',
                                       'SIT_ATIV'))}
        return cols

    def test_barra_com_duas_tensoes_e_reconhecida(self):
        u = self._tabela([('T1', 'RIM', 'RIM01B1', 'P95', 'AT'),
                          ('T2', 'RIM', 'RIM01B1', 'P96', 'AT')])
        eq = {'T1': {'ten_sec': '49'}, 'T2': {'ten_sec': '72'}}
        n = st._niveis_por_barra(u, eq, 2, 13.8, None)
        self.assertEqual(n[st._no('RIM01B1')], {13.8, 34.5})

    def test_desativado_nao_conta(self):
        u = self._tabela([('T1', 'RIM', 'RIM01B1', 'P95', 'AT'),
                          ('T2', 'RIM', 'RIM01B1', 'P96', 'DS')])
        eq = {'T1': {'ten_sec': '49'}, 'T2': {'ten_sec': '72'}}
        n = st._niveis_por_barra(u, eq, 2, 13.8, None)
        self.assertEqual(n[st._no('RIM01B1')], {13.8})
