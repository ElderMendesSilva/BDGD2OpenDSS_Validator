# -*- coding: utf-8 -*-
"""O censo de posse dos transformadores le o que a base declara, e nao cai
quando ela nao declara.

Na FORCEL83, 46% dos kVA instalados nao sao da distribuidora
(`UNTRMT.POS = 'O'`), e o ferro deles entrava na perda modelada como se fosse
da rede. `diagnosticos/posse.py` mede isso nas 99 bases; este teste garante
que ele conta certo e que uma base sem o campo nao derruba a rodada inteira.
"""
import os
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'diagnosticos'))
sys.path.insert(0, AQUI)

import fixture                                             # noqa: E402
import posse                                               # noqa: E402

import numpy as np                                         # noqa: E402


class TestOCenso(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _gdb(self, nome, mexe=None):
        t = fixture.tabelas()
        if mexe:
            mexe(t)
        import pyogrio
        p = os.path.join(self.tmp, nome + '.gdb')
        for i, (tab, cols) in enumerate(t.items()):
            pyogrio.raw.write(p, geometry=None,
                              field_data=[cols[c] for c in cols],
                              fields=list(cols), layer=tab,
                              driver='OpenFileGDB', geometry_type=None,
                              crs=None, append=(i > 0))
        return p

    def test_base_sem_POS_nem_PER_FER_nao_cai(self):
        """A fixture nao declara nenhum dos dois."""
        r = posse.posse_da_base(self._gdb('sem'))
        self.assertEqual(list(r), ['(sem POS)'])
        self.assertEqual(r['(sem POS)']['trafos'], 4)
        self.assertEqual(r['(sem POS)']['ferro_kw'], 0.0)

    def test_separa_por_posse_e_soma_a_placa(self):
        def mexe(t):
            t['UNTRMT']['POS'] = np.array(['PD', 'PD', 'O', 'O'], dtype=object)
            t['UNTRMT']['PER_FER'] = np.array([100.0, 200.0, 300.0, 400.0])
        r = posse.posse_da_base(self._gdb('com', mexe))
        self.assertEqual(r['PD']['trafos'], 2)
        self.assertEqual(r['O']['trafos'], 2)
        self.assertAlmostEqual(r['PD']['kva'], 75.0 + 45.0)
        self.assertAlmostEqual(r['O']['kva'], 112.5 + 30.0)
        self.assertAlmostEqual(r['O']['ferro_kw'], 0.7)

    def test_conta_quem_tem_cliente_de_BT(self):
        """Os quatro trafos da fixture tem UCBT pendurada."""
        def mexe(t):
            t['UNTRMT']['POS'] = np.array(['PD', 'PD', 'O', 'O'], dtype=object)
        r = posse.posse_da_base(self._gdb('bt', mexe))
        self.assertEqual(r['PD']['com_uc_bt'] + r['O']['com_uc_bt'], 4)


if __name__ == '__main__':
    unittest.main()
