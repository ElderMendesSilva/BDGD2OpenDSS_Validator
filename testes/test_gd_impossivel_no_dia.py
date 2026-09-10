# -*- coding: utf-8 -*-
"""Passo que devolve mais geração do que existe é reprovado — achado 35.

`Converged()` no OpenDSS fala da **tolerância de tensão**, não da física. Um
ponto de operação espúrio pode satisfazê-la e ser reportado como sucesso.

Medido na NEOENERGIA385/MOG02, com **4.341,2 kWp** de `PVSystem` instalados:
no cluster a série diária reportou pico de **164.668 kW** — 37,9x o instalado
— com 96 de 96 passos "convergidos", e daí saiu uma perda do dia de 72,265%.
Na mesma revisão do OpenDSS e sobre o mesmo modelo, a mesma função nesta
máquina reprova 15 passos e devolve outro número. É determinístico em cada
máquina e diferente entre elas: o modelo está no limiar, e diferenças
numéricas de plataforma decidem se o passo cai no ponto bom ou no espúrio.

E a perda do dia alimenta o `PERDA_ALTA` desde o achado 29 — sem o teto, a
causa atribuída à subestação depende da máquina que rodou.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTE = os.path.join(RAIZ, 'etapas', 'energia.py')


class TestOTeto(unittest.TestCase):

    def setUp(self):
        with open(FONTE, encoding='utf-8') as fh:
            self.fonte = fh.read()

    def test_o_teto_sai_do_modelo(self):
        """Somando `Pmpp` dos PVSystem e `kW` dos Generator."""
        self.assertIn('teto_gd', self.fonte)
        self.assertIn('dss.PVsystems.Pmpp()', self.fonte)
        self.assertIn('dss.Generators.kW()', self.fonte)

    def test_o_passo_impossivel_e_reprovado(self):
        self.assertIn('if teto_gd > 0 and gd > teto_gd:', self.fonte)
        pos = self.fonte.index('if teto_gd > 0 and gd > teto_gd:')
        trecho = self.fonte[pos:pos + 260]
        self.assertIn('falhos.append(k)', trecho,
                      'o passo tem de entrar nos falhos, e nao so ser contado')
        self.assertIn('continue', trecho,
                      'a energia do passo espurio nao pode entrar na soma')

    def test_o_guarda_conta_o_que_fez(self):
        """Guarda silencioso vira número que ninguém sabe de onde veio."""
        self.assertIn("serie['passos_gd_impossivel'] = gd_impossivel",
                      self.fonte)
        self.assertIn("'passos_gd_impossivel'", self.fonte)

    def test_o_teto_tem_folga_e_nao_e_exato(self):
        """Comparação exata reprovaria passo bom por arredondamento."""
        self.assertIn('teto_gd *= 1.05', self.fonte)


class TestAGeracaoFirmeEntraNoBalanco(unittest.TestCase):
    """Achado 34: somar só `PVSystem` deixaria 601 unidades fora."""

    def setUp(self):
        with open(FONTE, encoding='utf-8') as fh:
            self.fonte = fh.read()

    def test_a_serie_diaria_soma_os_dois_tipos(self):
        self.assertIn("((dss.PVsystems, 'PVSystem.'),", self.fonte)
        self.assertIn("(dss.Generators, 'Generator.'))", self.fonte)


if __name__ == '__main__':
    unittest.main()
