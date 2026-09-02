# -*- coding: utf-8 -*-
"""Ligacao a componente desenergizada — achado 33, forma B.

Fechado o achado 32, 61,9% do residuo da Cemig-D esta em 29 alimentadores
grandes com a rede inteira numa componente conexa e a cabeceira declarada numa
ilha ao lado — a UHST04 tem 14.749 barras numa componente e a cabeceira na de
129.

Esta e a unica premissa do projeto que INVENTA um elo. Por isso a regra e
estreita e cada elo sai contado: quem le o modelo tem de conseguir dizer
quanto do resultado depende dela.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
from bdgd2dss import ligacao                          # noqa: E402


def _adj(*pares):
    a = {}
    for x, y in pares:
        a.setdefault(x, set()).add(y)
        a.setdefault(y, set()).add(x)
    return a


class Componentes(unittest.TestCase):

    def test_separa_duas_ilhas_mortas(self):
        adj = _adj(('a', 'b'), ('b', 'c'), ('x', 'y'))
        c = ligacao.componentes(adj, {'a', 'b', 'c', 'x', 'y'})
        self.assertEqual([len(v) for v in c], [3, 2], 'maior primeiro')

    def test_nao_atravessa_barra_viva(self):
        """`b` esta viva: `a` e `c` sao ilhas separadas, e nao uma so."""
        adj = _adj(('a', 'b'), ('b', 'c'))
        c = ligacao.componentes(adj, {'a', 'c'})
        self.assertEqual([len(v) for v in c], [1, 1])

    def test_barra_isolada_e_componente_de_uma(self):
        self.assertEqual(ligacao.componentes({}, {'z'}), [{'z'}])


class Ancora(unittest.TestCase):

    def test_escolhe_a_de_maior_grau(self):
        adj = _adj(('t', 'a'), ('t', 'b'), ('t', 'c'), ('a', 'b'))
        self.assertEqual(ligacao.ancora({'t', 'a', 'b', 'c'}, adj), 't')

    def test_empate_resolvido_pelo_nome_para_ser_deterministico(self):
        """Duas rodadas do mesmo modelo tem de produzir o mesmo elo, senao a
        premissa muda sozinha entre execucoes."""
        adj = _adj(('m', 'x'), ('n', 'y'))
        self.assertEqual(ligacao.ancora({'m', 'n'}, adj), 'm')
        self.assertEqual(ligacao.ancora({'n', 'm'}, adj), 'm')

    def test_sem_vizinho_nao_ha_ancora(self):
        self.assertIsNone(ligacao.ancora({'sozinha'}, {}))


class Decisao(unittest.TestCase):

    def setUp(self):
        self.adj = _adj(('t', 'a'), ('t', 'b'), ('t', 'c'))
        self.kv = {b: 13.8 for b in 'tabc'}

    def _dec(self, cargas, **kw):
        return ligacao.decidir([{'t', 'a', 'b', 'c'}], self.adj, cargas,
                               self.kv, [13.8], **kw)

    def test_componente_grande_com_carga_e_ligada(self):
        lig, fora = self._dec({'a': 500})
        self.assertEqual(len(lig), 1)
        self.assertEqual(lig[0]['barra'], 't')
        self.assertEqual(lig[0]['cargas'], 500)

    def test_componente_sem_carga_nao_e_ligada(self):
        """Ligar o que nao tem carga nao muda resultado e so aumenta a chance
        de erro."""
        lig, fora = self._dec({})
        self.assertEqual(lig, [])
        self.assertEqual(fora[0]['motivo'], 'poucas cargas')

    def test_componente_pequena_e_ruido(self):
        lig, _ = self._dec({'a': 3})
        self.assertEqual(lig, [])

    def test_o_limiar_e_configuravel(self):
        lig, _ = self._dec({'a': 3}, min_cargas=2)
        self.assertEqual(len(lig), 1)

    def test_nao_liga_tensao_que_nenhum_vao_atende(self):
        """Ligar 13,8 kV a 34,5 kV seria pior que deixar desligado."""
        lig, fora = ligacao.decidir([{'t', 'a'}], self.adj, {'a': 500},
                                    self.kv, [34.5])
        self.assertEqual(lig, [])
        self.assertIn('tensao', fora[0]['motivo'])

    def test_a_tolerancia_de_tensao_aceita_o_quase_igual(self):
        kv = {'t': 13.79, 'a': 13.79}
        lig, _ = ligacao.decidir([{'t', 'a'}], _adj(('t', 'a')), {'a': 500},
                                 kv, [13.8])
        self.assertEqual(len(lig), 1)


class Arquivo(unittest.TestCase):

    def setUp(self):
        self.alvo = os.path.join(tempfile.mkdtemp(), '_LIGACAO.dss')

    def _gera(self, lig, fora=()):
        ligacao.escrever(self.alvo, lig, lambda kv: 'barra_se', fora)
        return open(self.alvo, encoding='utf-8').read()

    def test_o_elo_e_uma_chave_de_impedancia_desprezivel(self):
        """Ele representa o arranjo interno da SE, que a BDGD nao modela — e
        nao um trecho de rede que alguem esqueceu de cadastrar."""
        t = self._gera([{'barra': 'tronco', 'kv': 13.8, 'cargas': 900,
                         'barras': 14749, 'grau': 4}])
        self.assertIn('New Line.VAO_EXTRA_1', t)
        self.assertIn('Bus1=barra_se.1.2.3', t)
        self.assertIn('Bus2=tronco.1.2.3', t)
        self.assertIn('Switch=y', t)

    def test_cada_elo_sai_contado(self):
        t = self._gera([{'barra': 'tronco', 'kv': 13.8, 'cargas': 900,
                         'barras': 14749, 'grau': 4}])
        self.assertIn('14,749', t)
        self.assertIn('900', t)
        self.assertIn('grau 4', t)

    def test_o_cabecalho_admite_que_inventa_o_elo(self):
        t = self._gera([{'barra': 't', 'kv': 13.8, 'cargas': 900,
                         'barras': 100, 'grau': 2}])
        self.assertIn('INVENTA UM ELO QUE A BDGD NAO DECLARA', t)
        self.assertIn('_LIGACAO.dss', t, 'tem de dizer como desfazer')

    def test_o_que_foi_descartado_tambem_fica_escrito(self):
        t = self._gera([], [{'barras': 5, 'cargas': 1,
                             'motivo': 'poucas cargas'}])
        self.assertIn('descartada', t)
        self.assertIn('poucas cargas', t)

    def test_sem_ligacao_o_arquivo_existe_e_diz_que_nao_houve(self):
        """O MASTER redireciona sempre; arquivo ausente derrubaria a
        compilacao da subestacao inteira."""
        self.assertIn('nenhuma componente', self._gera([]))


if __name__ == '__main__':
    unittest.main()


class AceitaUmAUm(unittest.TestCase):
    """Elo que quebra a solucao nao entra — a regressao da EQPA V13.

    A primeira versao escrevia todos os elos de uma vez e mantinha mesmo
    divergindo: tres subestacoes de 119 pararam de convergir, com tensao em
    7,8e+23, 56.029 e 10,28 pu. A V11 tinha 119/119.
    """

    def _c(self, nome, cargas):
        return {'barra': nome, 'kv': 13.8, 'cargas': cargas, 'barras': cargas,
                'grau': 3}

    def test_mantem_o_que_passa_e_recusa_o_que_quebra(self):
        cand = [self._c('bom', 100), self._c('mau', 90)]
        m, r = ligacao.aceitar(cand, lambda l: l['barra'] != 'mau')
        self.assertEqual([x['barra'] for x in m], ['bom'])
        self.assertEqual([x['barra'] for x in r], ['mau'])

    def test_vai_do_maior_para_o_menor(self):
        """Se algum elo tiver de cair, que caia o que menos entrega."""
        vistos = []
        cand = [self._c('a', 10), self._c('b', 900), self._c('c', 50)]
        ligacao.aceitar(cand, lambda l: vistos.append(l['barra']) or True)
        self.assertEqual(vistos, ['b', 'c', 'a'])

    def test_a_ordem_e_deterministica_no_empate(self):
        vistos = []
        cand = [self._c('z', 10), self._c('a', 10)]
        ligacao.aceitar(cand, lambda l: vistos.append(l['barra']) or True)
        self.assertEqual(vistos, ['a', 'z'])

    def test_todos_recusados_devolve_lista_vazia_e_nao_quebra(self):
        m, r = ligacao.aceitar([self._c('x', 5)], lambda l: False)
        self.assertEqual((m, len(r)), ([], 1))

    def test_sem_candidato_nao_chama_o_motor(self):
        chamou = []
        m, r = ligacao.aceitar([], lambda l: chamou.append(1))
        self.assertEqual((m, r, chamou), ([], [], []))

    def test_o_recusado_fica_escrito_com_o_motivo_certo(self):
        import tempfile as _t
        alvo = os.path.join(_t.mkdtemp(), '_LIGACAO.dss')
        ligacao.escrever(alvo, [], lambda kv: 'se',
                         [{'barras': 8453, 'cargas': 1354,
                           'motivo': 'quebrou a convergencia'}])
        t = open(alvo, encoding='utf-8').read()
        self.assertIn('RECUSADO', t)
        self.assertIn('8,453', t)
        self.assertIn('premissa que piora o modelo nao entra', t)


class ChaveAbertaNaoEAresta(unittest.TestCase):
    """A distincao que separa modelar de sobrescrever o dado.

    Medido na Equatorial PA: 174.578 cargas sem tensao, 55,2% da base. Metade
    delas esta atras de uma chave que a BDGD declara ABERTA — o trecho existe,
    o caminho existe, e quem alimentaria e outro alimentador. A outra metade
    e ilha de verdade, e e para ela que a premissa existe.

    Ate a V14 o grafo da premissa ligava as duas barras de TODA linha,
    inclusive as abertas: a rede morta virava uma componente gigante, ligava-se
    uma ancora so, e o resto continuava escuro.
    """

    def test_componente_atras_de_chave_aberta_fica_de_fora(self):
        comp = {'a', 'b'}
        aberto = {'a': {'viva'}}
        self.assertTrue(ligacao.alcancavel_por_chave(comp, aberto,
                                                     mortas={'a', 'b'}))

    def test_ilha_de_verdade_nao_e_alcancavel(self):
        """Sem elemento nenhum entre ela e a rede viva."""
        self.assertFalse(ligacao.alcancavel_por_chave({'a', 'b'}, {}, {'a'}))

    def test_chave_aberta_para_outra_barra_morta_nao_conta(self):
        """Duas ilhas ligadas entre si por chave aberta continuam ilhas: o que
        importa e alcancar a rede VIVA."""
        aberto = {'a': {'c'}}
        self.assertFalse(ligacao.alcancavel_por_chave(
            {'a', 'b'}, aberto, mortas={'a', 'b', 'c'}))

    def test_decidir_liga_e_ANOTA_que_so_alcanca_por_chave(self):
        """A condicao vira informacao no arquivo gerado, e nao recusa.

        Recusar custou uma geracao: a Cemig-D caiu de 90,0% para 79,7% de
        carga energizada e a Roraima foi de 8 para 826 cargas sem tensao,
        porque a rede recusada e — pelo `SSDMT.CTMT` — dos alimentadores da
        propria subestacao.
        """
        comps = [{'x', 'y'}]
        lig, fora = ligacao.decidir(comps, {'x': {'y'}, 'y': {'x'}},
                                    {'x': 50}, {'x': 13.8, 'y': 13.8},
                                    [13.8], min_cargas=20,
                                    aberto={'x': {'viva'}}, mortas={'x', 'y'})
        self.assertEqual(len(lig), 1)
        self.assertTrue(lig[0]['so_por_chave'])
        self.assertEqual(fora, [])

    def test_ilha_de_verdade_e_ligada_sem_a_marca(self):
        lig, _ = ligacao.decidir([{'x', 'y'}], {'x': {'y'}, 'y': {'x'}},
                                 {'x': 50}, {'x': 13.8, 'y': 13.8},
                                 [13.8], min_cargas=20,
                                 aberto={}, mortas={'x', 'y'})
        self.assertEqual(len(lig), 1)
        self.assertFalse(lig[0]['so_por_chave'])

    def test_sem_o_grafo_aberto_o_comportamento_e_o_de_antes(self):
        """Quem chamar sem `aberto` continua ligando tudo — os testes antigos
        e qualquer uso externo nao mudam de resposta."""
        comps = [{'x', 'y'}]
        lig, fora = ligacao.decidir(comps, {'x': {'y'}, 'y': {'x'}},
                                    {'x': 50}, {'x': 13.8, 'y': 13.8},
                                    [13.8], min_cargas=20)
        self.assertEqual(len(lig), 1)
