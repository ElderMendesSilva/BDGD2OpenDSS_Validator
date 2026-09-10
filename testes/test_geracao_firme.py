# -*- coding: utf-8 -*-
"""Usina firme não se dimensiona pelo fator solar — achado 63.

O conversor dimensionava TODA geração por `ENE / 730 / 0,286`, e 0,286 é o
fator de capacidade da **curva solar**. A conta está certa para solar e só
para ela: `pmpp × 0,286 × 730 = ENE`, e a integral do dia fecha.

Para uma PCH que roda a 76% de fator de capacidade, dividir pelo fator solar
infla a usina. Medido na NEOENERGIA385/MOG02: 7,3 MW de placa viravam
**19,5 MW** no modelo, injetando com curva de irradiância — pico ao meio-dia
e **zero à noite**, quando uma PCH roda continuamente.

Censo nacional (99 bases, razão entre o emitido e a placa, mediana): PCH
1,74x, UHE 1,53x, CGH 1,31x — e UFV 0,28x, a solar de verdade encolhendo.

**A correção não é trocar energia por placa.** O invariante é que a integral
do dia bata com a energia declarada, e por isso o divisor tem de casar com a
curva anexada: curva solar divide pelo fator dela, curva plana não divide por
nada. É isso que estes testes travam.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import complementos as c                      # noqa: E402

MT = 'bmt1'
ENE = 4_069_870.7          # a energia da PCH da MOG02, kWh/mes


class _Leitor:
    def __init__(self, ugmt):
        self.ugmt = ugmt

    def ler_filtrado(self, camada, chave, valores, campos):
        if camada != 'UGMT_tab':
            raise KeyError(camada)
        return self.ugmt


def _gera(ceg, ene=ENE, pot_inst=7274.2):
    a = lambda *v: np.array(v, dtype=object)                # noqa: E731
    ugmt = {'COD_ID': a('G1'), 'PAC': a(MT), 'CTMT': a('F1'),
            'POT_INST': np.array([pot_inst]), 'FAS_CON': a('ABC'),
            'CEG_GD': a(ceg), 'ENE_01': np.array([ene])}
    d = tempfile.mkdtemp()
    gd = os.path.join(d, 'GD.dss')
    r = c.geracao(_Leitor(ugmt), ['F1'], {}, gd, barras={MT},
                  caminho_implausivel=os.path.join(d, '_GD_IMPLAUSIVEL.dss'))
    with open(gd, encoding='utf-8') as fh:
        return r, fh.read()


class TestTecnologia(unittest.TestCase):

    def test_ceg_generico_nao_declara_tecnologia(self):
        """`GD.SP.001.904.722` são 3,09 milhões de unidades sem tecnologia."""
        self.assertEqual(c.tecnologia('GD.SP.001.904.722'), '')

    def test_ceg_completo_declara(self):
        self.assertEqual(c.tecnologia('PCH.PH.SP.001479-6'), 'PCH')
        self.assertEqual(c.tecnologia('UTE.AI.GO.028113-1'), 'UTE')
        self.assertEqual(c.tecnologia('UFV.RS.SP.072965-5'), 'UFV')

    def test_vazio_e_lixo_nao_quebram(self):
        for v in (None, '', '   ', 'XX', 12):
            self.assertEqual(c.tecnologia(v), '')


class TestUsinaFirme(unittest.TestCase):
    """O caso da MOG02, com o CEG real dela."""

    CEG = 'PCH.PH.SP.001479-6'

    def test_sai_como_generator_e_nao_como_pvsystem(self):
        _, txt = _gera(self.CEG)
        self.assertIn('New Generator.GD_G1', txt)
        self.assertNotIn('New PVSystem.GD_G1', txt)

    def test_a_potencia_e_a_media_do_mes_sem_divisor_solar(self):
        """`ENE/730`, e não `ENE/730/0,286`."""
        _, txt = _gera(self.CEG)
        esperado = ENE / c.HORAS                       # 5.575 kW
        self.assertIn(f'kW={esperado:.2f}', txt)
        inflado = ENE / c.HORAS / c.FC_IRRAD           # 19.495 kW, o defeito
        self.assertNotIn(f'{inflado:.2f}', txt)

    def test_a_curva_e_plana_e_nao_a_de_irradiancia(self):
        """PCH roda de noite; curva solar zera a geração no pico de carga."""
        _, txt = _gera(self.CEG)
        self.assertIn('Daily=GERACAO_FIRME', txt)
        self.assertNotIn('IRRAD_DIA', txt)

    def test_a_integral_do_dia_bate_com_a_energia_declarada(self):
        """O invariante que justifica a correção inteira.

        A tolerância é a do próprio arquivo: `kW` sai com duas casas, então
        0,005 kW × 730 h = 3,65 kWh de arredondamento sobre 4 GWh.
        """
        _, txt = _gera(self.CEG)
        import re
        kw = float(re.search(r'kW=([0-9.]+)', txt).group(1))
        self.assertAlmostEqual(kw * c.HORAS, ENE, delta=0.005 * c.HORAS)

    def test_e_contada_no_retorno(self):
        r, _ = _gera(self.CEG)
        self.assertEqual(r[9], 1, 'usina firme tem de ser contada')
        self.assertAlmostEqual(r[10], ENE / c.HORAS, delta=1.0)


class TestSolarNaoMuda(unittest.TestCase):
    """A massa de micro-GD segue exatamente como estava."""

    def test_ceg_generico_continua_pvsystem_com_curva_solar(self):
        _, txt = _gera('GD.SP.001.904.722')
        self.assertIn('New PVSystem.GD_G1', txt)
        self.assertIn('Daily=IRRAD_DIA', txt)
        self.assertNotIn('New Generator', txt)

    def test_ufv_declarada_tambem_continua_solar(self):
        """`UFV` é solar: a conta antiga está certa para ela."""
        _, txt = _gera('UFV.RS.SP.072965-5')
        self.assertIn('New PVSystem.GD_G1', txt)
        self.assertNotIn('New Generator', txt)

    def test_a_potencia_da_solar_continua_dividida_pelo_fator(self):
        _, txt = _gera('GD.SP.001.904.722')
        self.assertIn(f'pmpp={ENE / c.HORAS / c.FC_IRRAD:.2f}', txt)


class TestCurva(unittest.TestCase):

    def test_a_curva_plana_e_escrita_com_96_pontos_de_valor_1(self):
        """Sem a curva no arquivo, o `Daily=GERACAO_FIRME` aponta para o nada
        e o OpenDSS aceita em silêncio, gerando com perfil default."""
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'Curvas.dss')

        class _SemCurvas:
            """CRVCRG existente e vazia — a curva firme não depende dela."""

            def ler(self, camada, campos):
                return {campo: np.array([]) for campo in campos}

        c.curvas(_SemCurvas(), p)
        with open(p, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertIn('New LoadShape.GERACAO_FIRME npts=96', txt)
        linha = [l for l in txt.splitlines() if 'GERACAO_FIRME' in l][0]
        self.assertEqual(linha.count('1.0'), 96, 'a curva tem de ser plana')


class TestContabilidade(unittest.TestCase):
    """Se o validador só somasse PVSystem, a GD firme sumiria em silêncio."""

    def test_o_validador_soma_os_dois_tipos(self):
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(raiz, 'etapas', 'validador.py'),
                  encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn('dss.Generators', fonte,
                      'P_gd_kW voltaria a subcontar a geracao firme')

    def test_a_sonda_do_achado_26_desliga_os_dois(self):
        """Desligar só os PVSystem mediria `sem GD` com a PCH injetando."""
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(raiz, 'etapas', 'validador.py'),
                  encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn("for _classe in ('pvsystem', 'generator')", fonte)



class TestEstabilidadeNumerica(unittest.TestCase):
    """A banda de tensão do `Generator` é o que estabiliza a iteração.

    A primeira versão punha `Vminpu=0.5 Vmaxpu=1.5` para a usina "não se
    desligar por subtensão do modelo". O raciocínio estava errado: fora da
    banda o OpenDSS troca o gerador para impedância constante, e é essa troca
    que amortece a iteração. Medido na MOG02, com a mesma usina de 5.575 kW:
    com 0,5/1,5 a solução explode para 10⁷⁸ pu; com o padrão, converge.
    """

    def test_nao_alarga_a_banda_de_tensao(self):
        _, txt = _gera('PCH.PH.SP.001479-6')
        self.assertNotIn('Vminpu', txt,
                         'alargar a banda faz a solucao divergir')
        self.assertNotIn('Vmaxpu', txt)

    def test_nao_usa_model_3(self):
        """`model=3` regula tensão injetando reativo SEM limite — é suporte
        de reativo inventado, e esconde a sobretensão que a usina causa."""
        _, txt = _gera('PCH.PH.SP.001479-6')
        self.assertIn('model=1', txt)
        self.assertNotIn('model=3', txt)


if __name__ == '__main__':
    unittest.main()
