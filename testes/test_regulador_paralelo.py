# -*- coding: utf-8 -*-
"""O regulador nao pode ficar em paralelo com o trecho que ele regula.

ACHADO 22. A UNREMT declara o regulador entre `PAC_1` e `PAC_2`, e a SSDMT
declara o TRECHO entre os mesmos dois PACs — o vao onde o equipamento esta
instalado. Emitir os dois liga o mesmo par de barras por dois caminhos, e um
deles tem impedancia quase nula. O tap regulando contra esse curto produz
corrente de laco.

MEDIDO na subestacao AGV da NEOENERGIA385, safra 2025:

    9 de 9 reguladores em paralelo com uma linha
    2.506 A num condutor de 145 A nominais
    tensao mediana de MT em 0,415 pu, com 9,9 MW de perda
    e a perda NAO some ao desligar as 1.282 cargas

    desligando so os 9 reguladores:  1,013 pu e 229 kW

A correcao poe o regulador EM SERIE — ele existe na rede real, entao remover
seria mentir sobre a rede. Cria-se uma barra intermediaria e a linha do par e
reconectada para sair dela.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import complementos                        # noqa: E402


class _BDGDFalsa:
    """UNREMT com um regulador entre dois PACs."""

    def __init__(self, pac1, pac2, cod='R1'):
        import numpy as np
        self._d = {'COD_ID': np.array([cod], dtype=object),
                   'PAC_1': np.array([pac1], dtype=object),
                   'PAC_2': np.array([pac2], dtype=object),
                   'CTMT': np.array(['F1'], dtype=object),
                   'FAS_CON': np.array(['ABC'], dtype=object)}

    def ler_filtrado(self, camada, campo, valores, cols):
        if camada == 'UNREMT':
            return self._d
        raise KeyError(camada)         # sem EQRE, como muitas bases


def _gera(pares):
    """Emite o Reguladores.dss e devolve o texto."""
    d = tempfile.mkdtemp()
    alvo = os.path.join(d, 'Reguladores.dss')
    # `no()` normaliza o PAC para minusculas, e `barras`/`pares` sao
    # comparados DEPOIS dessa normalizacao. Escrever 'pA' aqui faria o
    # regulador ser descartado como pendurado, e o teste passaria a medir
    # outra coisa.
    complementos.reguladores(_BDGDFalsa('pA', 'pB'), ['F1'], alvo,
                             barras={'pa', 'pb'}, pares=pares)
    with open(alvo, encoding='utf-8') as fh:
        return fh.read()


class OReguladorEntraEmSerie(unittest.TestCase):

    def test_sem_linha_no_par_ele_liga_os_dois_PACs(self):
        """O caso simples, que nao pode regredir: sem trecho paralelo, o
        regulador vai de PAC a PAC como sempre foi."""
        t = _gera({})
        self.assertIn('buses=[pa.1 pb.1]', t)
        self.assertNotIn('Edit Line.', t)

    def test_COM_linha_no_par_ele_ganha_barra_intermediaria(self):
        """O caso do achado 22: a linha existe entre os mesmos PACs."""
        t = _gera({('pa', 'pb'): [('L9', 'pa', 'pb')]})
        self.assertNotIn('buses=[pa.1 pb.1]', t,
                         'o regulador nao pode ligar o par direto')
        self.assertIn('buses=[pa.1 pa_regR1.1]', t)

    def test_a_linha_do_par_e_RECONECTADA_a_barra_do_meio(self):
        """Sem isto o regulador ficaria pendurado e a rede, cortada."""
        t = _gera({('pa', 'pb'): [('L9', 'pa', 'pb')]})
        self.assertIn('Edit Line.L9 bus1=pa_regR1', t)

    def test_a_ponta_certa_e_que_move(self):
        """A linha pode estar declarada ao contrario — `pB -> pA`. Reconectar
        sempre `bus1` deixaria o regulador em paralelo de novo, sem erro."""
        t = _gera({('pa', 'pb'): [('L9', 'pb', 'pa')]})
        self.assertIn('Edit Line.L9 bus2=pa_regR1', t)

    def test_as_TRES_fases_usam_a_MESMA_barra_do_meio(self):
        """Uma barra por fase separaria o regulador trifasico em tres redes."""
        t = _gera({('pa', 'pb'): [('L9', 'pa', 'pb')]})
        for f in ('1', '2', '3'):
            self.assertIn('buses=[pa.%s pa_regR1.%s]' % (f, f), t)

    def test_o_arquivo_DECLARA_o_que_foi_feito(self):
        """Mudanca de topologia silenciosa e a pior espécie: quem abrir o
        modelo daqui a um ano precisa achar a explicacao no proprio arquivo."""
        t = _gera({('pa', 'pb'): [('L9', 'pa', 'pb')]})
        self.assertIn('EM PARALELO', t)
        self.assertIn('achado 22', t)

    def test_varias_linhas_no_mesmo_par_sao_todas_reconectadas(self):
        """A AGV tinha duas linhas em cada par. Deixar uma para tras manteria
        o laco intacto."""
        t = _gera({('pa', 'pb'): [('L9', 'pa', 'pb'), ('L8', 'pa', 'pb')]})
        self.assertIn('Edit Line.L9 bus1=pa_regR1', t)
        self.assertIn('Edit Line.L8 bus1=pa_regR1', t)


if __name__ == '__main__':
    unittest.main()
