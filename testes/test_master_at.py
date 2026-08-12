# -*- coding: utf-8 -*-
"""MASTER-AT: a metade de cima da decomposicao — achado 13.

O MASTER-GERAL da Enel SP tem 2,39 milhoes de elementos e nao cabe em 15,8 GB.
A saida nao foi apagar a baixa tensao, foi parar de exigir que tudo caiba
junto: a rede de AT resolve com as subestacoes como carga equivalente, e os
modelos por subestacao continuam intactos.

Medido em Roraima, onde o monolito CABE e portanto serve de referencia:

    erro contra o monolito        mediano      p90     pior
    premissa declarada (hoje)      0,0220   0,0439   0,0807
    decomposicao AT<->SE           0,0081   0,0267   0,0439

A decomposicao erra 2,7x menos que a premissa que ela substitui. Nao e
exata — e melhor, e isso esta medido e nao suposto.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import master                       # noqa: E402


def _ses(n=3):
    return [{'SE': f'SE{i}', 'barra_mt': f'barra{i}', 'kv_mt': 13.8,
             'kW_BT': 1000.0 * i, 'kW_MT': 500.0 * i} for i in range(1, n + 1)]


class CargaEquivalente(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cam = os.path.join(self.tmp, 'MASTER-AT.dss')

    def _gera(self, ses, **kw):
        n, mw = master.gerar_at(self.cam, ['_AT/Fontes.dss', '_AT/Linhas_AT.dss'],
                                ses, [88.0, 13.8], **kw)
        with open(self.cam, encoding='utf-8') as fh:
            return n, mw, fh.read()

    def test_uma_carga_por_subestacao(self):
        n, _, txt = self._gera(_ses(3))
        self.assertEqual(n, 3)
        for i in (1, 2, 3):
            self.assertIn(f'New Load.SE_SE{i} ', txt)

    def test_a_carga_soma_bt_e_mt(self):
        _, _, txt = self._gera(_ses(1))
        self.assertIn('kW=1500.000', txt)

    def test_o_total_em_mw(self):
        _, mw, _ = self._gera(_ses(3))
        self.assertAlmostEqual(mw, (1500 + 3000 + 4500) / 1000.0, places=3)

    def test_potencia_constante_e_deliberada(self):
        """Model=1. Com impedancia constante a carga cairia junto com a
        tensao, e o resultado sairia otimista justamente no caso que
        interessa medir: o da subestacao mal alimentada."""
        _, _, txt = self._gera(_ses(1))
        self.assertIn('Model=1', txt)

    def test_a_barra_e_a_de_mt_da_subestacao(self):
        _, _, txt = self._gera(_ses(1))
        self.assertIn('Bus1=barra1.1.2.3', txt)

    def test_o_fator_multiplica_a_demanda(self):
        """O `mw` devolvido e arredondado a uma casa, para relatorio; o kW
        escrito no arquivo e que precisa ser exato."""
        _, mw, txt = self._gera(_ses(1), fator=0.5)
        self.assertIn('kW=750.000', txt)
        self.assertAlmostEqual(mw, 0.75, delta=0.06)

    def test_subestacao_sem_barra_ou_sem_carga_fica_de_fora(self):
        """Subestacao sem demanda nao e carga zero: e subestacao que nao
        entra. Carga de 0 kW numa barra criaria um no sem efeito e contaria
        como se estivesse representada."""
        ses = _ses(3)
        ses[0]['barra_mt'] = ''
        ses[1]['kW_BT'] = ses[1]['kW_MT'] = 0
        n, _, txt = self._gera(ses)
        self.assertEqual(n, 1)
        self.assertNotIn('SE_SE1', txt)
        self.assertNotIn('SE_SE2', txt)
        self.assertIn('SE_SE3', txt)

    def test_kv_invalido_fica_de_fora(self):
        ses = _ses(1)
        ses[0]['kv_mt'] = 0
        n, _, _ = self._gera(ses)
        self.assertEqual(n, 0)


class OrdemDosRedirects(unittest.TestCase):
    """A ordem nao e estetica: custou duas depuracoes.

    O `New Circuit` nasce no Fontes.dss, e sem circuito o OpenDSS recusa
    qualquer definicao com o erro #265. Os LineCodes sao globais, e sem eles
    o Linhas_AT.dss recusa na primeira linha com o erro #401.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cam = os.path.join(self.tmp, 'MASTER-AT.dss')

    def _ordem(self):
        master.gerar_at(self.cam,
                        ['_AT/Linhas_AT.dss', '_AT/Chaves_AT.dss',
                         '_AT/Fontes.dss', '_AT/Trafos_AT.dss'],
                        _ses(1), [88.0, 13.8],
                        arquivos_globais=['_global/LineCodes.dss'])
        with open(self.cam, encoding='utf-8') as fh:
            return [l.split()[1] for l in fh if l.startswith('redirect ')]

    def test_fontes_vem_primeiro(self):
        self.assertEqual(self._ordem()[0], '_AT/Fontes.dss')

    def test_linecodes_antes_das_linhas(self):
        o = self._ordem()
        self.assertLess(o.index('_global/LineCodes.dss'),
                        o.index('_AT/Linhas_AT.dss'))

    def test_nenhum_arquivo_se_perde(self):
        o = self._ordem()
        self.assertEqual(sorted(o), sorted([
            '_AT/Linhas_AT.dss', '_AT/Chaves_AT.dss', '_AT/Fontes.dss',
            '_AT/Trafos_AT.dss', '_global/LineCodes.dss']))

    def test_a_carga_vem_depois_de_tudo(self):
        self._ordem()
        with open(self.cam, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertLess(txt.index('redirect _AT/Trafos_AT.dss'),
                        txt.index('New Load.SE_SE1'),
                        'a barra de MT precisa existir antes da carga')


if __name__ == '__main__':
    unittest.main()
