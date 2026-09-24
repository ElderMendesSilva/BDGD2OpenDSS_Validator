# -*- coding: utf-8 -*-
"""Ponto isolado zerado na curva de carga — achado 78.

A Elektro traz POT_96 = 0 em TODAS as curvas da CRVCRG (e a Cosern em 242 de
243). As 23:45 a carga do modelo some, a rede fica so com a perda no ferro,
a perda passa da energia que entra e o passo sai da conta pelo achado 67:
84 das 153 subestacoes da Elektro perderam o dia na V39.

So o zero ENTRE DOIS POSITIVOS e preenchido. Zero ao lado de zero e curva que
desliga de verdade (iluminacao publica de dia) e fica.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
import fixture                                        # noqa: E402
from bdgd2dss import complementos                     # noqa: E402
from bdgd2dss.leitor import BDGD                      # noqa: E402


class Completar(unittest.TestCase):

    def test_o_ultimo_ponto_zerado_vira_a_media_dos_vizinhos(self):
        """O dia e circular: o vizinho do POT_96 e o POT_01."""
        v, n = complementos.completar([2.0] + [1.0] * 94 + [0.0])
        self.assertEqual(n, 1)
        self.assertAlmostEqual(v[-1], 1.5)

    def test_zero_no_meio_entre_positivos(self):
        v, n = complementos.completar([1.0, 3.0, 0.0, 5.0])
        self.assertEqual((v[2], n), (4.0, 1))

    def test_iluminacao_publica_fica_como_esta(self):
        ip = [2.0] * 24 + [0.0] * 48 + [2.0] * 24
        v, n = complementos.completar(ip)
        self.assertEqual((v, n), (ip, 0))

    def test_curva_sadia_nao_muda(self):
        c = [1.0 + 0.1 * (k % 7) for k in range(96)]
        self.assertEqual(complementos.completar(c), (c, 0))


class NoCurvasDss(unittest.TestCase):

    def test_a_variante_sai_sem_zero_e_avisada(self):
        tmp = tempfile.mkdtemp()
        gdb = fixture.gerar(os.path.join(tmp, 'z.gdb'),
                            variante='curva_com_ponto_zerado')
        caminho = os.path.join(tmp, 'Curvas.dss')
        avisos = []
        complementos.curvas(BDGD(gdb, verbose=False), caminho, 'DU', log=avisos.append)
        with open(caminho, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertIn('ACHADO 78', txt)
        self.assertTrue(any('ACHADO 78' in a for a in avisos))
        for linha in txt.splitlines():
            if linha.startswith('New LoadShape.') and 'IRRAD' not in linha \
                    and 'FIRME' not in linha:
                pontos = linha.split('mult=(')[1].rstrip(')').split()
                self.assertNotEqual(float(pontos[-1]), 0.0, linha[:40])


if __name__ == '__main__':
    unittest.main()
