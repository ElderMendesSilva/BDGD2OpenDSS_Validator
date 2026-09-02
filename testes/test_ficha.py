# -*- coding: utf-8 -*-
"""A ficha do circuito e as métricas do dia.

O que estes testes travam é a coisa que já quebrou de verdade: a ficha some em
SILÊNCIO. Quem a chama engole a exceção para não derrubar o relatório de uma
subestação quebrada, então um nome de atributo errado não aparece como erro —
aparece como uma página em branco que ninguém nota.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import ficha, laudo                          # noqa: E402


class MotorFalso(object):
    """Um dublê com a forma da DSS C-API: tudo é chamada, não propriedade."""

    class _Col(object):
        def __init__(self, n, campo=None, valores=()):
            self._n = n
            self._campo = campo
            self._valores = list(valores)
            self._i = 0

        # __len__ é o que torna uma coleção VAZIA falsa — e foi por isso que
        # `getattr(...) or getattr(...)` apagou os reguladores da ficha.
        def __len__(self):
            return self._n

        def Count(self):
            return self._n

        def First(self):
            self._i = 1
            return 1 if self._valores else 0

        def Next(self):
            self._i += 1
            return self._i if self._i <= len(self._valores) else 0

    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestFichaDoCircuito(unittest.TestCase):

    def _motor(self, nregs=0):
        col = MotorFalso._Col
        circuito = MotorFalso(
            Name=lambda: 'ckt',
            AllNodeNames=lambda: ['a.1', 'a.2', 'b.1'],
            AllBusNames=lambda: ['a', 'b'],
            NumCktElements=lambda: 5,
            TotalPower=lambda: [-1000.0, -400.0],
            Losses=lambda: [30000.0, 1000.0],
            LineLosses=lambda: [20.0, 5.0],
            AllBusMagPu=lambda: [1.0, 0.98, 0.0],
            SetActiveBus=lambda b: 0,
        )
        return MotorFalso(
            Circuit=circuito,
            Solution=MotorFalso(Converged=lambda: True, Iterations=lambda: 4),
            Bus=MotorFalso(kVBase=lambda: 7.97, Distance=lambda: 3.0,
                           puVmagAngle=lambda: [0.98, 0.0]),
            Lines=col(2), Transformers=col(3), Loads=col(4),
            Capacitors=col(0), PVsystems=col(0), Meters=col(1),
            Generators=col(0), RegControls=col(nregs),
        )

    def test_conta_o_que_o_motor_montou(self):
        f = ficha.ficha_do_circuito(self._motor())
        self.assertEqual(f['n_barras'], 2)
        self.assertEqual(f['n_nos'], 3)
        self.assertEqual(f['n_trafos'], 3)

    def test_colecao_vazia_vale_zero_e_nao_ausente(self):
        """Zero reguladores é um FATO sobre a rede; `None` é a ficha quebrada.

        A distinção não é cosmética: a ficha omite o campo ausente, então um
        `None` aqui faria a linha sumir da tabela e ninguém saberia se a rede
        não tem regulador ou se a leitura falhou.
        """
        f = ficha.ficha_do_circuito(self._motor(nregs=0))
        self.assertEqual(f['n_regcontrols'], 0)
        self.assertIsNotNone(f['n_regcontrols'])

    def test_o_sinal_da_potencia_da_fonte_e_invertido(self):
        # `TotalPower` vem negativo quando a rede CONSOME; a ficha publica o
        # valor entregue, positivo, que é como se fala de uma subestação.
        f = ficha.ficha_do_circuito(self._motor())
        self.assertAlmostEqual(f['fonte_kW'], 1000.0)
        self.assertGreater(f['fp_fonte'], 0.9)

    def test_perda_dos_trafos_e_o_que_sobra_das_linhas(self):
        f = ficha.ficha_do_circuito(self._motor())
        self.assertAlmostEqual(f['perdas_kW'], 30.0)
        self.assertAlmostEqual(f['perdas_trafos_kW'], 10.0)

    def test_no_em_zero_nao_entra_na_estatistica_de_tensao(self):
        """0,00 pu não é tensão baixa: é nó desligado da fonte.

        Deixá-lo no cálculo faria a mediana e o mínimo descreverem uma rede que
        não existe.
        """
        f = ficha.ficha_do_circuito(self._motor())
        self.assertEqual(f['n_nos_zerados'], 1)
        self.assertAlmostEqual(f['V_min'], 0.98)

    def test_motor_mudo_nao_levanta(self):
        vazio = MotorFalso(Circuit=MotorFalso(), Solution=MotorFalso(),
                           Bus=MotorFalso())
        f = ficha.ficha_do_circuito(vazio)
        self.assertEqual(f['n_barras'], 0)


class TestFichaDoDia(unittest.TestCase):

    def _serie(self, fonte, gd=None, perdas=None):
        return {'fonte_kw': fonte, 'gd_kw': gd or [], 'perdas_kw': perdas or []}

    def test_fator_de_carga_e_media_sobre_pico(self):
        d = ficha.ficha_do_dia(self._serie([100, 200] * 48), passos=96)
        self.assertAlmostEqual(d['fator_de_carga'], 0.75)
        self.assertEqual(d['pico_kW'], 200)

    def test_passo_falho_nao_desalinha_o_relogio(self):
        """Passo que não converge vale `None` e não zero.

        Zerar o passo puxaria o vale para baixo e o fator de carga junto, e o
        relatório reportaria uma rede que descarrega às três da manhã por um
        motivo que é numérico, não elétrico.
        """
        s = [100] * 96
        s[10] = None
        d = ficha.ficha_do_dia(self._serie(s))
        self.assertEqual(d['passos_falhos'], 1)
        self.assertEqual(d['vale_kW'], 100)

    def test_coincidencia_zero_quando_a_gd_dorme_no_pico(self):
        """O caso que justifica os 96 passos: sol ao meio-dia, pico à noite."""
        fonte = [50] * 96
        fonte[88] = 500                       # pico às 22h
        gd = [0] * 96
        gd[48] = 300                          # sol ao meio-dia
        d = ficha.ficha_do_dia(self._serie(fonte, gd))
        self.assertEqual(d['hora_pico'], 22.0)
        self.assertEqual(d['coincidencia_gd'], 0.0)

    def test_horas_de_fluxo_reverso(self):
        fonte = [100] * 96
        fonte[40:48] = [-10] * 8
        d = ficha.ficha_do_dia(self._serie(fonte))
        self.assertAlmostEqual(d['horas_reverso'], 2.0)

    def test_razao_pico_vale_da_perda(self):
        d = ficha.ficha_do_dia(self._serie([100] * 96,
                                           perdas=[10] * 48 + [40] * 48))
        self.assertAlmostEqual(d['razao_perda_pico_vale'], 4.0)

    def test_serie_vazia_nao_levanta(self):
        self.assertEqual(ficha.ficha_do_dia({})['passos_validos'], 0)


class TestLeituraEscrita(unittest.TestCase):

    def test_acusa_o_fator_de_carga_implausivel(self):
        """Fator de carga alto é sintoma de curva única, e o texto tem de dizê-lo.

        É a leitura que nenhum campo isolado dá: só se vê olhando média, pico e
        vale ao mesmo tempo.
        """
        texto = ' '.join(
            p for _, p in laudo.leitura_da_ficha({}, {'passos_validos': 96,
                                                      'fator_de_carga': 0.97,
                                                      'pico_kW': 10}))
        self.assertIn('mesma curva de carga', texto)

    def test_ficha_vazia_nao_inventa_secao(self):
        self.assertEqual(laudo.leitura_da_ficha({}, {}), [])

    def test_a_hora_sai_como_hora(self):
        self.assertEqual(laudo._hora(22.25), '22h15')
        self.assertEqual(ficha._hora(22.25), '22h15')

    def test_linhas_da_ficha_omite_o_que_nao_foi_medido(self):
        rotulos = [r for _, r, _ in ficha.linhas_da_ficha({'n_barras': 10})]
        self.assertIn('barras', rotulos)
        self.assertNotIn('transformadores', rotulos)


if __name__ == '__main__':
    unittest.main()
