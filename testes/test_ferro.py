# -*- coding: utf-8 -*-
"""Trafo sem `PER_FER` não pode virar trafo com ferro zero.

Essa confusão é exatamente o achado 53: o caminho de distribuição não escrevia
`%noloadloss`, o OpenDSS assume zero por omissão, e todo transformador de
distribuição das sete bases ficou sem ferro. Perda a vazio AUSENTE passava por
perda a vazio NULA, e o erro valia 1,45% a 3,60% da carga viva.

Aqui se mede a parcela de ferro para testar o achado 10 — o viés de 1,42x entre
o modelo e o `PERD_*` declarado. Se a contagem repetir a mesma confusão, a
medida do viés herda o defeito que ela quer investigar.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'diagnosticos'))
import ferro                                            # noqa: E402


class _BDGDFalsa:
    def __init__(self, per_fer):
        self._d = {'PER_FER': per_fer, 'POT_NOM': [75.0] * len(per_fer)}

    def ler(self, camada, cols):
        return self._d


class OFerroSeSomaEmKW(unittest.TestCase):

    def _mede(self, per_fer):
        real = ferro.BDGD
        ferro.BDGD = lambda *a, **k: _BDGDFalsa(per_fer)
        try:
            return ferro.ferro_da_base('/qualquer.gdb')
        finally:
            ferro.BDGD = real

    def test_watts_viram_kW(self):
        """`PER_FER` vem em WATTS na EQTRMT — 35 W de ferro num trafo de 75
        kVA é a ordem de grandeza citada no achado 53."""
        n, kw, sem = self._mede([1000.0, 2000.0])
        self.assertEqual((n, kw, sem), (2, 3.0, 0))

    def test_ausente_e_contado_e_nao_somado_como_zero(self):
        """O achado 53 em uma linha: ausência não é zero."""
        n, kw, sem = self._mede([1000.0, None, 0.0, ''])
        self.assertEqual(n, 4, 'os quatro entram na contagem de trafos')
        self.assertEqual(kw, 1.0, 'so o que declara entra na soma')
        self.assertEqual(sem, 3, 'e os que nao declaram sao RELATADOS')

    def test_negativo_conta_como_ausente(self):
        """Perda de ferro negativa não existe; é campo mal preenchido."""
        _, kw, sem = self._mede([-50.0, 1000.0])
        self.assertEqual((kw, sem), (1.0, 1))

    def test_base_sem_EQTRMT_nao_derruba(self):
        n, kw, sem = self._mede([])
        self.assertEqual((n, kw, sem), (0, 0.0, 0))


if __name__ == '__main__':
    unittest.main()
