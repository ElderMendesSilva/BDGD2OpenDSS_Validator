# -*- coding: utf-8 -*-
"""Componentes órfãs e o `NaN` que elas produzem — achado 27.

Uma componente sem nada em derivação e sem contato com o resto do circuito é
pura impedância série flutuando: submatriz de admitância singular, tensão
`NaN`. E o `NaN` não fica quieto — contamina o `Circuit.Losses()` da
subestação inteira.

Medido na CMIG 1726588 da safra 2025: seis nós com `NaN`, em duas barras, e o
culpado era **uma linha de um centímetro** cujos dois nomes de barra aparecem
uma única vez no modelo inteiro.

O que estes testes travam é o CRITÉRIO, que custou duas tentativas erradas
antes de acertar — as duas estão aqui como caso de teste, porque um critério
plausível que destrói o modelo é exatamente o que volta se ninguém registrar.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import ligacao                              # noqa: E402


class TestInertes(unittest.TestCase):

    def test_a_componente_orfa_e_encontrada(self):
        """Duas barras, uma linha, nada mais tocando nenhuma das duas."""
        comps = [{'a', 'b'}]
        ramos = [('Line.orfa', 'a', 'b')]
        elem = {'a': {'Line.orfa'}, 'b': {'Line.orfa'}}
        r = ligacao.inertes(comps, {}, elem, ramos)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['linhas'], ['Line.orfa'])

    def test_um_unico_elemento_externo_desqualifica(self):
        """A PRIMEIRA tentativa errada: raciocinar sobre o grafo de barras
        mortas em vez de perguntar ao motor.

        `componentes(adj, mortas)` corta a rede na fronteira do que está sem
        tensão, e um pedaço morto pendurado na rede viva vira ali uma
        «componente» que parece isolada e não está. Na CMIG 1726588 isso deu
        45 componentes e 432 linhas; desabilitá-las levou as cargas sem tensão
        de 27 para 186 e as perdas para 1,4e14 kW.
        """
        comps = [{'a', 'b'}]
        ramos = [('Line.dentro', 'a', 'b')]
        elem = {'a': {'Line.dentro'},
                'b': {'Line.dentro', 'Line.para_a_rede_viva'}}
        self.assertEqual(ligacao.inertes(comps, {}, elem, ramos), [])

    def test_derivacao_na_propria_componente_desqualifica(self):
        """Trafo, capacitor ou reator de neutro dão caminho para a terra: a
        matriz não é singular e não há `NaN` a evitar.

        O critério não lista tipos de elemento de propósito — lista de tipos
        esquece um, e o reator de neutro foi o que quase passou.
        """
        for externo in ('Transformer.t1', 'Capacitor.c1', 'Reactor.neutro_a',
                        'PVSystem.gd1', 'Vsource.fonte'):
            comps = [{'a', 'b'}]
            ramos = [('Line.dentro', 'a', 'b')]
            elem = {'a': {'Line.dentro', externo}, 'b': {'Line.dentro'}}
            self.assertEqual(ligacao.inertes(comps, {}, elem, ramos), [],
                             'passou com %s na componente' % externo)

    def test_componente_com_carga_nunca_e_orfa(self):
        """Ela é o caso do achado 33: falta o elo, e o remédio é ligar — não
        desligar."""
        comps = [{'a', 'b'}]
        ramos = [('Line.dentro', 'a', 'b')]
        elem = {'a': {'Line.dentro'}, 'b': {'Line.dentro'}}
        self.assertEqual(ligacao.inertes(comps, {'b': 3}, elem, ramos), [])

    def test_componente_sem_linha_interna_nao_gera_disable(self):
        """Nada a desabilitar não é achado: seria uma linha de arquivo
        anunciando zero ação."""
        self.assertEqual(ligacao.inertes([{'a'}], {}, {'a': set()}, []), [])

    def test_so_as_linhas_de_dentro_sao_desligadas(self):
        """A SEGUNDA tentativa errada: usar `barra -> linhas`.

        Uma linha com uma ponta na componente e a outra fora entrava na lista,
        e desligá-la cortava o lado de fora, que pode estar vivo.
        """
        comps = [{'a', 'b'}]
        ramos = [('Line.dentro', 'a', 'b'), ('Line.sai', 'b', 'longe')]
        elem = {'a': {'Line.dentro'}, 'b': {'Line.dentro', 'Line.sai'}}
        # com a saída, a componente nem é órfã — mas se algum dia o critério
        # afrouxar, a linha que sai não pode ir junto.
        for r in ligacao.inertes(comps, {}, elem, ramos):
            self.assertNotIn('Line.sai', r['linhas'])


class TestOEscritoNoArquivo(unittest.TestCase):

    def test_o_arquivo_conta_o_que_desligou(self):
        """Premissa silenciosa é premissa que ninguém pode conferir — a regra
        do projeto desde o `_LIGACAO.dss` original."""
        import tempfile
        d = tempfile.mkdtemp()
        caminho = os.path.join(d, '_LIGACAO.dss')
        ligacao.escrever(caminho, [], lambda kv: None, (),
                         [{'barras': 2, 'linhas': ['Line.orfa']}])
        with open(caminho, encoding='utf-8') as fh:
            texto = fh.read()
        self.assertIn('achado 27', texto)
        self.assertIn('1 componente(s), 2 barra(s), 1 linha(s)', texto)
        self.assertIn('Line.orfa.enabled=no', texto)

    def test_sem_inerte_o_arquivo_nao_inventa_secao(self):
        import tempfile
        d = tempfile.mkdtemp()
        caminho = os.path.join(d, '_LIGACAO.dss')
        ligacao.escrever(caminho, [], lambda kv: None, (), [])
        with open(caminho, encoding='utf-8') as fh:
            self.assertNotIn('achado 27', fh.read())


class TestNaNEscapaDaComparacao(unittest.TestCase):
    """A barra com `NaN` é a mais morta que existe, e escapava do conjunto.

    `max(v) < MORTA_V` é **False** quando `v` é `NaN`, porque toda comparação
    com `NaN` é falsa. A barra nunca entrava em componente nenhuma, e o
    detector de órfã deixava de fora justamente a que produzia o `NaN`.
    """

    def test_a_forma_negada_pega_o_nan(self):
        nan = float('nan')
        self.assertFalse(nan < 1.0)              # a armadilha
        self.assertTrue(not (nan >= 1.0))        # a forma usada no código

    def test_o_codigo_usa_a_forma_negada(self):
        caminho = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'etapas', 'ligacao.py')
        with open(caminho, encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn('not (max(v) >= MORTA_V)', fonte,
                      'a comparação voltou à forma que o NaN atravessa')


if __name__ == '__main__':
    unittest.main()
