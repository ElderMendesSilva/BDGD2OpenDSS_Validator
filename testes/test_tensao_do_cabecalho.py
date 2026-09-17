# -*- coding: utf-8 -*-
"""`--tensao-do-cabecalho` desliga o achado 49, e so quando pedido.

POR QUE EXISTE. Na EQUATORIAL6072 (V34) o achado 49 trocou 142 alimentadores
de 34,5 para 13,8 kV, e a rede colapsa perto de 13,8/34,5 = 0,40 pu. A
suspeita e a troca; a unica prova e reconverter sem ela e comparar. A opcao e
o instrumento desse experimento — o padrao continua sendo conciliar, porque
em Roraima o achado 49 esta certo.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
sys.path.insert(0, AQUI)

import converter                                           # noqa: E402
import fixture                                             # noqa: E402


class _BDGD:
    """So o que `ler_ctmt` e `por_equipamento` leem: um alimentador com
    cabecalho de 34,5 kV e um parque inteiro de 13,8 kV — o caso da troca."""

    def ler(self, tabela, colunas=None):
        import numpy as np
        s = lambda *v: np.array(v, dtype=object)            # noqa: E731
        if tabela == 'CTMT':
            return {'COD_ID': s('F1'), 'SUB': s('S'), 'NOME': s('F1'),
                    'UNI_TR_AT': s(''), 'PAC_INI': s('P'), 'BARR': s('B'),
                    'TEN_NOM': s('72'), 'TEN_OPE': s('1.0')}
        if tabela == 'UNTRMT':
            return {'COD_ID': s(*[f'T{i}' for i in range(10)]),
                    'CTMT': s(*['F1'] * 10), 'FAS_CON_P': s(*['ABC'] * 10)}
        if tabela == 'EQTRMT':
            return {'UNI_TR_MT': s(*[f'T{i}' for i in range(10)]),
                    'TEN_PRI': s(*['49'] * 10)}
        raise KeyError(tabela)


class TestAChave(unittest.TestCase):

    def _kv(self, **kw):
        return converter.ler_ctmt(_BDGD(), 13.8, lambda *_: None, **kw)['F1']

    def test_por_padrao_o_parque_decide(self):
        """O comportamento de sempre nao muda."""
        c = self._kv()
        self.assertAlmostEqual(c['kv'], 13.8, places=1)
        self.assertAlmostEqual(c['kv_do_cabecalho'], 34.5, places=1)

    def test_desligada_vale_o_cabecalho(self):
        c = self._kv(conciliar=False)
        self.assertAlmostEqual(c['kv'], 34.5, places=1)
        self.assertNotIn('kv_do_cabecalho', c)


class TestOConversor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        gdb = fixture.garantir()
        cls.saidas = {}
        for nome, extra in (('padrao', []), ('cabecalho', ['--tensao-do-cabecalho'])):
            s = os.path.join(cls.tmp, nome)
            p = subprocess.run([sys.executable, '-u',
                                os.path.join(RAIZ, 'etapas', 'converter.py'),
                                gdb, '--saida', s] + extra,
                               cwd=RAIZ, capture_output=True, text=True, timeout=600)
            cls.saidas[nome] = (s, p)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _rel(self, nome):
        s, p = self.saidas[nome]
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        with io.open(os.path.join(s, 'relatorio_rede.json'), encoding='utf-8') as fh:
            return json.load(fh), p.stdout

    def test_o_padrao_se_declara_conciliado(self):
        rel, _ = self._rel('padrao')
        self.assertTrue(rel['tensao_conciliada_pelo_parque'])

    def test_a_opcao_se_declara_e_avisa(self):
        """Premissa desligada tem de ficar escrita no modelo e no log."""
        rel, log = self._rel('cabecalho')
        self.assertFalse(rel['tensao_conciliada_pelo_parque'])
        self.assertIn('ACHADO 49 DESLIGADO', log)


if __name__ == '__main__':
    unittest.main()
