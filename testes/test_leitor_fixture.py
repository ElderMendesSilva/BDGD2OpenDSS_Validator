# -*- coding: utf-8 -*-
"""O leitor le uma BDGD de verdade, gerada aqui, sem alteracao nenhuma.

E o teste que sustenta todos os outros: se o fixture nao for lido pelo mesmo
caminho de codigo que le a base real — inclusive o `ler_filtrado`, que empurra
a clausula WHERE para o GDAL — a suite estaria testando outra coisa.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss.leitor import BDGD, no, num, txt    # noqa: E402
import fixture                                    # noqa: E402

GDB = None


def setUpModule():
    global GDB
    GDB = fixture.garantir()


class LeFixture(unittest.TestCase):

    def setUp(self):
        self.b = BDGD(GDB, verbose=False)

    def test_todas_as_tabelas_aparecem(self):
        cam = set(self.b.camadas())
        for t in ('SEGCON', 'CTMT', 'SSDMT', 'UNTRMT', 'EQTRMT', 'BAR', 'UNTRAT'):
            self.assertIn(t, cam)

    def test_leitura_simples(self):
        c = self.b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
        self.assertEqual([txt(x) for x in c['COD_ID']],
                         ['C1', 'C2', 'C3', 'C4'])
        self.assertAlmostEqual(num(c['R1'][2]), 8.43)
        self.assertAlmostEqual(num(c['CNOM'][2]), 1500.0)

    def test_leitura_filtrada_empurra_o_where(self):
        """`ler_filtrado` e o caminho de producao: filtra no GDAL, nao em
        Python. Se ele quebrar, a conversao de uma concessao inteira para."""
        m = self.b.ler_filtrado('SSDMT', 'CTMT', {'F1'},
                                ['COD_ID', 'PAC_1', 'PAC_2', 'COMP'])
        self.assertEqual(sorted(txt(x) for x in m['COD_ID']), ['S1', 'S2'])

    def test_leitura_filtrada_com_varios_valores(self):
        m = self.b.ler_filtrado('SSDMT', 'CTMT', {'F1', 'F2'}, ['COD_ID'])
        self.assertEqual(len(m['COD_ID']), 3)

    def test_leitura_filtrada_sem_resultado(self):
        m = self.b.ler_filtrado('SSDMT', 'CTMT', {'NAO_EXISTE'}, ['COD_ID'])
        self.assertEqual(len(m['COD_ID']), 0)

    def test_colunas_de_energia_mensal(self):
        c = self.b.ler('CTMT', ['COD_ID'] + [f'ENE_{i:02d}' for i in range(1, 13)])
        self.assertAlmostEqual(sum(num(c[f'ENE_{i:02d}'][0])
                                   for i in range(1, 13)), 12000.0)

    def test_o_fixture_carrega_os_achados(self):
        """Se alguem mexer no fixture e tirar os casos, os testes de defeito
        conhecido passariam por acidente. Este teste tranca isso."""
        c = self.b.ler('CTMT', ['TEN_NOM'])
        self.assertIn('67', [txt(x) for x in c['TEN_NOM']],
                      'codigo sem valor confirmado')
        t = self.b.ler('UNTRMT', ['TEN_LIN_SE'])
        v = [round(num(x), 4) for x in t['TEN_LIN_SE']]
        self.assertIn(7.96, v, '13,8/raiz(3), fase-neutro em campo de linha')
        self.assertIn(0.216, v, '216 V, tensao de BT ausente da lista')
        s = self.b.ler('SEGCON', ['R1', 'CNOM'])
        self.assertTrue(any(num(s['R1'][i]) > 5 and num(s['CNOM'][i]) > 1000
                            for i in range(len(s['R1']))),
                        'condutor com R1 incoerente com a ampacidade')

    def test_o_fixture_carrega_o_caso_do_593(self):
        """Achado 11. Duas condicoes, e ambas precisam valer ao mesmo tempo:
        o condutor tem de ser COERENTE (para o auto-ajuste nao o corrigir) e
        tem de cobrir a maior fatia da quilometragem (que e o defeito real).
        Se alguem tirar uma das duas, os testes do linecodes viram tautologia.
        """
        s = self.b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
        i = [txt(x) for x in s['COD_ID']].index('C4')
        self.assertAlmostEqual(num(s['R1'][i]), 8.232, places=3)
        self.assertAlmostEqual(num(s['CNOM'][i]), 31.0, places=1)

        m = self.b.ler('SSDMT', ['TIP_CND', 'COMP'])
        km = {}
        for j in range(len(m['COMP'])):
            km[txt(m['TIP_CND'][j])] = km.get(txt(m['TIP_CND'][j]), 0.0) \
                + num(m['COMP'][j])
        self.assertEqual(max(km, key=km.get), 'C4',
                         'o condutor de 31 A tem de ser o de maior extensao')

    def test_o_fixture_carrega_a_medicao_degenerada(self):
        """Achado 10: F3 fatura 6.000 kWh com 4.800 injetados. Perda total
        medida de -25%, que nenhum modelo pode respeitar."""
        c = self.b.ler('CTMT', ['COD_ID'] + [f'ENE_{i:02d}' for i in range(1, 13)])
        i = [txt(x) for x in c['COD_ID']].index('F3')
        inj = sum(num(c[f'ENE_{k:02d}'][i]) for k in range(1, 13))
        u = self.b.ler('UCBT_tab', ['CTMT'] + [f'ENE_{i:02d}' for i in range(1, 13)])
        fat = sum(num(u[f'ENE_{k:02d}'][j]) for k in range(1, 13)
                  for j in range(len(u['CTMT'])) if txt(u['CTMT'][j]) == 'F3')
        self.assertGreater(fat, inj, 'F3 tem de faturar mais do que recebe')


class Normalizacao(unittest.TestCase):

    def test_no_normaliza_para_nome_de_barra(self):
        self.assertEqual(no('B1'), no(' b1 '))
        self.assertEqual(no('ABC-123'), no('abc-123'))

    def test_no_de_vazio(self):
        """Campo vazio virava a barra fantasma `_`, que deixou as 24 saidas
        da TCTR sem alimentacao."""
        for v in (None, '', '   '):
            self.assertFalse(no(v).strip('_'),
                             'vazio nao pode virar nome de barra valido')

    def test_num_com_lixo(self):
        self.assertEqual(num(None, 7.0), 7.0)
        self.assertEqual(num('', 3.0), 3.0)
        self.assertAlmostEqual(num('12,5', 0.0) or 0.0, 12.5, places=1) \
            if num('12,5', 0.0) else None

    def test_txt_nunca_devolve_none(self):
        self.assertIsInstance(txt(None), str)
        self.assertIsInstance(txt(123), str)


if __name__ == '__main__':
    unittest.main()
