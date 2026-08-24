# -*- coding: utf-8 -*-
"""Achado 55 — o teto de iteracoes reprovava modelo sadio.

`Set maxiterations=100` estava nos tres rodapes do MASTER. Medido na 5003346
de Roraima com `--bt completo`, 205.122 barras:

    maxiterations   usou   convergiu    perda
         100         100      NAO        7,53%
         500         202      sim        7,98%
        2000         202      sim        7,98%

Com 100 o OpenDSS parava no meio e devolvia um ponto que nao e solucao — e a
perda saia 0,45 ponto percentual ABAIXO da verdadeira, que e o lado que
engana: um modelo que nao convergiu parecia melhor do que o que converge.

Quantas iteracoes ela precisa depende de onde a solucao COMECA: 202 quando
retomada do ponto em que o teto de 100 a abandonou, e 123 quando o MASTER ja
nasce com teto de 500 e resolve de uma vez. Por isso o teste abaixo cobra
folga sobre o MAIOR dos dois, e nao sobre o do dia.

POR QUE 500 E NAO 2000. O teto tambem limita o desperdicio de quem nao
converge nunca. Na V19, 6 subestacoes de 2.390 nao convergiram — todas na
CEMIG, todas paradas exatamente em 100. Elas NAO sao caso de teto: com 2.000
iteracoes a 1726539 continua sem convergir, e a solucao fica identica ate a
quarta casa nas tres tentativas (16.371,6 / 16.371,9 / 16.371,8 kW de
entrada; 553,4 kW de perda; 3,38%). Alguns nos oscilam enquanto o resto ja
convergiu — defeito diferente, que subir o teto nao resolve. Com 500 o
desperdicio delas fica em 5x em vez de 20x.

Quem converge antes nao paga nada por este numero: o teto e limite, nao
quantidade.
"""
import os
import re
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss import master        # noqa: E402

TETO = 500
PRECISA = 202          # o MAIOR dos dois medidos na 5003346 de Roraima
                       # com --bt completo; o outro foi 123


def _rodapes():
    """Os textos de rodape que o master escreve, por nome."""
    return {n: v for n, v in vars(master).items()
            if n.startswith('RODAPE_') and isinstance(v, str)}


class OTetoValeEmTodosOsRodapes(unittest.TestCase):
    """Sao tres — GERAL, SE e AT. Um deles ficar para tras e o defeito
    voltar so em parte do modelo, que e pior do que voltar inteiro: a
    subestacao converge sozinha e a rodada geral nao, ou o contrario."""

    def test_todo_rodape_declara_o_teto(self):
        rod = _rodapes()
        self.assertGreaterEqual(len(rod), 3, 'sumiu rodape')
        for nome, txt in rod.items():
            self.assertIn('maxiterations', txt,
                          f'{nome} nao declara maxiterations')

    def test_nenhum_rodape_ficou_em_100(self):
        for nome, txt in _rodapes().items():
            for v in re.findall(r'maxiterations\s*=\s*(\d+)', txt):
                self.assertNotEqual(int(v), 100,
                                    f'{nome} voltou ao teto que reprovava '
                                    f'modelo sadio')

    def test_o_teto_cobre_o_pior_caso_medido(self):
        """202 iteracoes sao o que a 5003346 precisa. O teto tem de ter
        folga sobre isso, e nao empatar."""
        for nome, txt in _rodapes().items():
            for v in re.findall(r'maxiterations\s*=\s*(\d+)', txt):
                self.assertGreater(int(v), PRECISA,
                                   f'{nome}: teto {v} nao cobre as {PRECISA} '
                                   f'iteracoes medidas em Roraima')

    def test_o_teto_e_o_mesmo_nos_tres(self):
        vistos = set()
        for txt in _rodapes().values():
            vistos.update(int(v) for v in
                          re.findall(r'maxiterations\s*=\s*(\d+)', txt))
        self.assertEqual(vistos, {TETO},
                         'rodapes com tetos diferentes fazem a mesma rede '
                         'convergir num arquivo e nao no outro')


class OTetoNaoSobeSemLimite(unittest.TestCase):
    """A 1726539 da CEMIG nao converge nem com 2.000 iteracoes, e a solucao
    dela e a mesma com 100, 500 e 2.000. Para as seis assim, todo passo acima
    de 500 e tempo jogado fora."""

    def test_nao_passa_de_mil(self):
        for nome, txt in _rodapes().items():
            for v in re.findall(r'maxiterations\s*=\s*(\d+)', txt):
                self.assertLessEqual(int(v), 1000,
                                     f'{nome}: teto {v} gasta 20x em quem '
                                     f'oscila e nao converge nunca')


class OControleContinuaSeparado(unittest.TestCase):
    """`maxcontroliter` conta iteracao de CONTROLE — regulador, capacitor —,
    e nao de fluxo de potencia. Trocar um pelo outro ja seria um achado."""

    def test_maxcontroliter_nao_foi_mexido(self):
        for nome, txt in _rodapes().items():
            if 'maxcontroliter' in txt:
                v = re.search(r'maxcontroliter\s*=\s*(\d+)', txt)
                self.assertEqual(int(v.group(1)), 200,
                                 f'{nome}: maxcontroliter e outra coisa')


if __name__ == '__main__':
    unittest.main()
