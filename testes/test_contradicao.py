# -*- coding: utf-8 -*-
"""O ferro declarado cabe dentro da perda declarada? Tres campos, tres unidades.

O achado 13 e o mais forte do projeto porque NAO depende do nosso modelo: sao
tres campos da mesma BDGD que nao fecham entre si. Mas exatamente por isso ele
nao tem rede de seguranca — nenhum resultado de simulacao denuncia uma conta de
unidade errada aqui. Um fator 1.000 ou um fator 8.760 fora do lugar produz um
numero plausivel e falso.

    PER_FER   WATTS por transformador  -> x 8.760 h = kWh/ano
    ENE_xx    kWh no mes               -> soma dos 12
    PERD_*    kWh no ano               -> ja e anual

Estes testes travam as tres conversoes com numeros escolhidos para dar conta
redonda, e travam tambem o caso que o achado 53 ensinou: ausencia nao e zero.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'diagnosticos'))
import contradicao                                       # noqa: E402


class _BDGDFalsa:
    """EQTRMT com `PER_FER`, CTMT com `ENE_xx` e `PERD_*`.

    Devolve ARRAY do numpy como o leitor real: foi um `or []` sobre array que
    fez o `ferro.py` errar as 97 bases de uma vez, com rc=0.
    """

    def __init__(self, per_fer, ene_mes, perd_a4):
        import numpy as np
        self._eq = {'PER_FER': np.array(per_fer, dtype=object)}
        n = len(ene_mes)
        d = {'COD_ID': np.array(['F%d' % i for i in range(n)], dtype=object),
             'PERD_A4': np.array(perd_a4, dtype=float),
             'PERD_B': np.zeros(n),
             'PERD_A4_B': np.zeros(n)}
        for k in range(1, 13):
            d['ENE_%02d' % k] = np.array(ene_mes, dtype=float)
        self._ct = d

    def ler(self, camada, cols):
        return self._eq if camada == 'EQTRMT' else self._ct


def _mede(per_fer, ene_mes, perd_a4):
    real = contradicao.BDGD
    contradicao.BDGD = lambda *a, **k: _BDGDFalsa(per_fer, ene_mes, perd_a4)
    try:
        return contradicao.contradicao_da_base('/qualquer.gdb')
    finally:
        contradicao.BDGD = real


class AsTresUnidadesFecham(unittest.TestCase):

    def test_watt_de_placa_vira_kWh_no_ano(self):
        """1.000 W ligados o ano inteiro = 8.760 kWh."""
        r = _mede([1000.0], [1.0], [0.0])
        self.assertAlmostEqual(r['ferro_kWh_ano'], 8760.0, places=1)

    def test_a_energia_e_a_soma_dos_DOZE_meses(self):
        """`ENE_01` sozinho seria um doze avos, e o percentual sairia 12x."""
        r = _mede([], [100.0, 100.0], [0.0, 0.0])   # dois alimentadores
        self.assertAlmostEqual(r['energia_kWh_ano'], 2400.0, places=1)

    def test_a_perda_declarada_ja_e_anual(self):
        """`PERD_*` nao se multiplica por 12 — o campo e do ano."""
        r = _mede([], [1000.0], [500.0])
        self.assertAlmostEqual(r['declarado_kWh_ano'], 500.0, places=1)

    def test_os_percentuais_usam_o_MESMO_denominador(self):
        """Ferro e declarado sobre a mesma energia; senao a razao nao diz nada.

        1.000 W de ferro = 8.760 kWh/ano. Energia = 12 x 8.760 = 105.120 kWh.
        Ferro = 8,333%. Declarado 10.512 kWh = 10%.
        """
        r = _mede([1000.0], [8760.0], [10512.0])
        self.assertAlmostEqual(r['ferro_pct'], 8.333, places=2)
        self.assertAlmostEqual(r['declarado_pct'], 10.0, places=2)

    def test_a_razao_acima_de_1_e_a_contradicao(self):
        """O achado em uma linha: ferro que nao cabe na perda declarada."""
        r = _mede([2000.0], [8760.0], [8760.0])
        # ferro 17.520 kWh contra 8.760 declarados
        self.assertAlmostEqual(r['razao_ferro_declarado'], 2.0, places=2)


class OQueNaoPodeVirarNumeroPlausivel(unittest.TestCase):

    def test_trafo_sem_PER_FER_e_contado_e_nao_somado(self):
        """O achado 53 em uma linha: ausencia nao e zero."""
        r = _mede([1000.0, None, 0.0, ''], [1.0], [1.0])
        self.assertEqual(r['trafos'], 4)
        self.assertEqual(r['sem_per_fer'], 3)
        self.assertAlmostEqual(r['ferro_kWh_ano'], 8760.0, places=1)

    def test_energia_zero_nao_divide_por_zero(self):
        r = _mede([1000.0], [0.0], [0.0])
        self.assertIsNone(r['ferro_pct'])
        self.assertIsNone(r['declarado_pct'])

    def test_perda_declarada_zero_nao_vira_razao_infinita(self):
        """Base que declara zero nao e base com contradicao infinita: e base
        sem declaracao utilizavel, e as duas leituras sao diferentes."""
        r = _mede([1000.0], [1000.0], [0.0])
        self.assertIsNone(r['razao_ferro_declarado'])

    def test_base_sem_EQTRMT_nao_derruba(self):
        r = _mede([], [1000.0], [10.0])
        self.assertEqual(r['ferro_kWh_ano'], 0.0)
        self.assertEqual(r['trafos'], 0)


class ContradicaoNaoSeConfundeComDadoQUEBRADO(unittest.TestCase):
    """A primeira execucao publicou 2.639% de ferro e razoes de 213.530x.

    Nao era achado, era denominador degenerado: a CERBRANORT6898 declara 0,2
    GWh no ano para 1.810 transformadores. A conta estava certa e o dado, nao —
    e sem separar as duas coisas o lixo afoga o achado na mesma estatistica.

    Estes testes existem porque os outros nove NAO pegaram isso: eles travam as
    unidades, e o defeito estava na escolha de quem entra na conta.
    """

    def test_ferro_impossivel_sai_da_estatistica(self):
        """Perda a vazio nao chega a um quarto da energia servida."""
        r = _mede([1000000.0], [1.0], [1.0])      # ferro gigante, energia 12
        self.assertFalse(r['plausivel'])
        self.assertIn('energia da CTMT', r['motivo'])

    def test_quem_quase_nao_declara_sai_da_estatistica(self):
        """Razao de 213.530x mede o denominador, nao a contradicao."""
        r = _mede([1000.0], [8760.0], [1.0])      # declara ~0,001%
        self.assertFalse(r['plausivel'])
        self.assertIn('sem perda com que comparar', r['motivo'])

    def test_base_sadia_continua_entrando(self):
        """O contraste: o filtro nao pode comer o caso normal.

        Ferro 8,3% contra 10% declarados e exatamente a ordem de grandeza real
        — a CRELUZD598 da 8,1% contra 2,5%.
        """
        r = _mede([1000.0], [8760.0], [10512.0])
        self.assertTrue(r['plausivel'])
        self.assertIsNone(r['motivo'])

    def test_a_contradicao_REAL_sobrevive_ao_filtro(self):
        """Ferro que excede o declarado, com os dois em faixa plausivel: e o
        achado, e ele nao pode ser descartado junto com o lixo."""
        r = _mede([2000.0], [8760.0], [8760.0])   # 16,7% contra 8,3%
        self.assertTrue(r['plausivel'])
        self.assertGreater(r['razao_ferro_declarado'], 1.0)


if __name__ == '__main__':
    unittest.main()
