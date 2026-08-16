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
