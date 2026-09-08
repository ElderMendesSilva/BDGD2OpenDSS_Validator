# -*- coding: utf-8 -*-
"""A geração cuja energia não cabe na própria potência — achado 32.

O conversor dimensiona a GD pela ENERGIA declarada, e a razão está no
docstring de `complementos.geracao`: `POT_INST` replica o `CAR_INST` do
consumidor, errando por até 540x. O achado 32 mostrou o outro lado da moeda —
o maior "gerador distribuído" do país declara `POT_INST` de 109,4 kW com
`ENE_01` de 25,4 GWh no mês, **317 mil vezes** o que a potência comporta.

O teste aqui é FÍSICO e não escolhe entre os dois campos: nenhum gerador
entrega, no mês, mais do que a própria potência instalada vezes 730 h. Quando
`ENE_XX` passa disso, os dois campos da mesma linha se contradizem e não há
tamanho confiável a usar.

O que estes testes protegem é o **contrato da premissa**: o arquivo é sempre
escrito (o MASTER o redireciona sem condição, e `Redirect` de arquivo ausente
aborta a compilação inteira), a unidade continua declarada no `GD.dss`, e o
desligamento mora fora dele — apagar o redirect devolve o modelo à declaração
crua da BDGD.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import complementos                          # noqa: E402


MT = 'bmt1'


class _Leitor:
    def __init__(self, ugmt):
        self.ugmt = ugmt

    def ler_filtrado(self, camada, chave, valores, campos):
        if camada != 'UGMT_tab':
            raise KeyError(camada)
        return self.ugmt


def _ugmt(pot_inst, ene, cod='G1'):
    a = lambda *v: np.array(v, dtype=object)               # noqa: E731
    return {'COD_ID': a(cod), 'PAC': a(MT), 'CTMT': a('F1'),
            'POT_INST': np.array([pot_inst]), 'FAS_CON': a('ABC'),
            'CEG_GD': a(''), 'ENE_01': np.array([ene])}


def _gera(pot_inst, ene):
    tmp = tempfile.mkdtemp()
    gd = os.path.join(tmp, 'GD.dss')
    impl = os.path.join(tmp, '_GD_IMPLAUSIVEL.dss')
    r = complementos.geracao(_Leitor(_ugmt(pot_inst, ene)), ['F1'], {}, gd,
                             barras={MT}, caminho_implausivel=impl)
    return (r, open(gd, encoding='utf-8').read(),
            open(impl, encoding='utf-8').read())


class TestOTeste(unittest.TestCase):

    def test_energia_acima_da_potencia_vezes_730_e_implausivel(self):
        """O caso real: 109,4 kW declarados com 25,4 GWh no mês."""
        r, _, impl = _gera(109.4375, 25_372_031.85)
        self.assertEqual(r[7], 1, 'devia contar uma unidade implausivel')
        self.assertIn('enabled=no', impl)

    def test_fator_de_capacidade_plausivel_passa(self):
        """20% de fator de capacidade é uma usina solar comum."""
        r, _, impl = _gera(1000.0, 1000.0 * 730 * 0.20)
        self.assertEqual(r[7], 0)
        self.assertNotIn('enabled=no', impl)

    def test_o_limite_e_exatamente_100_por_cento(self):
        """Fator de capacidade de 100% é o teto físico, e ainda passa."""
        self.assertEqual(_gera(1000.0, 1000.0 * 730)[0][7], 0)
        self.assertEqual(_gera(1000.0, 1000.0 * 730 * 1.01)[0][7], 1)

    def test_sem_pot_inst_nao_da_para_testar(self):
        """`POT_INST` zero não é contradição: é ausência de referência."""
        self.assertEqual(_gera(0.0, 25_372_031.85)[0][7], 0)


class TestContratoDaPremissa(unittest.TestCase):

    def test_o_arquivo_e_sempre_escrito_mesmo_vazio(self):
        """O MASTER redireciona sem condição; ausente aborta a compilação."""
        _, _, impl = _gera(1000.0, 1000.0 * 730 * 0.20)
        self.assertIn('achado 32', impl)
        self.assertIn('0 unidade(s) desligada(s)', impl)

    def test_a_unidade_continua_declarada_no_gd(self):
        """A premissa desliga do lado de fora — o GD.dss segue sendo a BDGD."""
        _, gd, impl = _gera(109.4375, 25_372_031.85)
        self.assertIn('New PVSystem.GD_G1', gd)
        self.assertIn('Edit PVSystem.GD_G1 enabled=no', impl)

    def test_o_arquivo_diz_como_reverter(self):
        _, _, impl = _gera(109.4375, 25_372_031.85)
        self.assertIn('APAGAR O REDIRECT', impl)

    def test_o_arquivo_mostra_os_dois_numeros_que_se_contradizem(self):
        """Quem abrir o arquivo tem de ver por que a unidade caiu."""
        _, _, impl = _gera(109.4375, 25_372_031.85)
        self.assertIn('POT_INST=109.4', impl)
        self.assertIn('25,372,031.9', impl)

    def test_conta_os_kw_desligados(self):
        r, _, _ = _gera(109.4375, 25_372_031.85)
        self.assertGreater(r[8], 0, 'kW desligados tem de ser contado')


class TestMaster(unittest.TestCase):

    def test_o_master_redireciona_o_arquivo(self):
        """Sem o redirect a premissa não faz efeito nenhum."""
        from bdgd2dss import master
        fonte = open(master.__file__, encoding='utf-8').read()
        self.assertIn('redirect _GD_IMPLAUSIVEL.dss', fonte)


if __name__ == '__main__':
    unittest.main()
