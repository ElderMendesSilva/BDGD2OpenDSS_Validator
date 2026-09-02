# -*- coding: utf-8 -*-
"""Clima pela coordenada da propria base — achado 4.

NENHUM TESTE AQUI TOCA A REDE. A `baixar` recebe a funcao de abertura por
parametro justamente para isso: uma suite que depende de servico externo
falha por motivo que nao e do projeto, e ai as pessoas aprendem a ignorar a
falha — que e o pior desfecho possivel para uma suite.
"""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
from bdgd2dss import clima, complementos          # noqa: E402
from bdgd2dss.leitor import BDGD                  # noqa: E402

GDB = None


def setUpModule():
    global GDB
    GDB = fixture.garantir()


def _resposta(ghi_por_hora, t_por_hora, dias=3):
    """Imita a resposta horaria da NASA POWER para alguns dias."""
    g, t = {}, {}
    for d in range(1, dias + 1):
        for h in range(24):
            k = f'20240{1}{d:02d}{h:02d}'
            g[k] = ghi_por_hora[h]
            t[k] = t_por_hora[h]
    return {'properties': {'parameter': {'ALLSKY_SFC_SW_DWN': g, 'T2M': t}}}


# um dia plausivel: sol das 6h as 18h, pico ao meio-dia
GHI = [0.0] * 6 + [50, 200, 400, 600, 750, 820, 800, 700, 520, 320, 140, 30] \
      + [0.0] * 6
AMB = [20 + 8 * (1 if 10 <= h <= 16 else 0) for h in range(24)]


class Interpolacao(unittest.TestCase):

    def test_24_viram_96(self):
        self.assertEqual(len(clima.para_96(list(range(24)))), 96)

    def test_os_valores_horarios_sao_preservados(self):
        """Cada hora cheia cai exatamente num dos 96 passos."""
        v = clima.para_96(list(range(24)))
        for h in range(24):
            self.assertAlmostEqual(v[h * 4], float(h), places=9)

    def test_interpola_e_nao_repete(self):
        """Repetir o valor da hora nos quatro passos daria uma escada; o que
        se quer e a rampa."""
        v = clima.para_96([0.0, 4.0] + [0.0] * 22)
        self.assertAlmostEqual(v[1], 1.0, places=9)
        self.assertAlmostEqual(v[2], 2.0, places=9)
        self.assertAlmostEqual(v[3], 3.0, places=9)

    def test_fecha_o_dia(self):
        """A interpolacao e circular: o passo entre 23h e 0h existe. Sem
        isso aparecia um degrau a meia-noite na temperatura."""
        v = clima.para_96([10.0] * 23 + [20.0])
        self.assertGreater(v[95], 10.0)
        self.assertLess(v[95], 20.0)

    def test_lista_vazia_nao_quebra(self):
        self.assertEqual(len(clima.para_96([])), 96)


class TemperaturaDeCelula(unittest.TestCase):

    def test_sem_sol_a_celula_e_a_ambiente(self):
        self.assertEqual(clima.celula([0.0], [25.0]), [25.0])

    def test_o_modelo_e_o_mesmo_do_caminho_antigo(self):
        """Os dois caminhos — arquivo local e cache baixado — TEM de dar o
        mesmo numero, senao trocar a fonte muda o resultado por motivo que
        nao e o clima. A formula do `complementos` esta inline; aqui ela e
        conferida contra a constante deste modulo."""
        for g, amb in ((0.5, 25.0), (1.0, 30.0), (0.259, 19.3)):
            esperado = round(amb + (45.0 - 20.0) / 800.0 * (g * 1000.0), 2)
            self.assertEqual(clima.celula([g], [amb]), [esperado])

    def test_a_celula_sobe_com_a_irradiancia(self):
        fria = clima.celula([0.2], [25.0])[0]
        quente = clima.celula([1.0], [25.0])[0]
        self.assertGreater(quente, fria)


class BaixarSemRede(unittest.TestCase):

    def _baixa(self, **kw):
        return clima.baixar(-60.6979, 2.7722,
                            abrir=lambda u: _resposta(GHI, AMB), **kw)

    def test_formato_do_cache(self):
        d = self._baixa()
        self.assertEqual(len(d['irradiancia_kw_m2']), 96)
        self.assertEqual(len(d['celula_c']), 96)
        self.assertEqual(len(d['ambiente_c']), 96)

    def test_converte_w_para_kw(self):
        d = self._baixa()
        self.assertAlmostEqual(max(d['irradiancia_kw_m2']), 0.820, places=3)

    def test_zera_o_ruido_de_borda(self):
        """Irradiancia sob o horizonte, abaixo de 2 W/m2, e ruido de
        interpolacao. O caminho do arquivo local ja zerava; os dois tem de
        aplicar o mesmo criterio."""
        ghi = [1.0] * 6 + GHI[6:]
        d = clima.baixar(0, 0, abrir=lambda u: _resposta(ghi, AMB))
        self.assertEqual(d['irradiancia_kw_m2'][0], 0.0)

    def test_a_procedencia_fica_gravada(self):
        """Um modelo cujo clima nao se sabe de onde veio nao serve para
        artigo nenhum."""
        d = self._baixa()
        for k in ('fonte', 'url', 'lon', 'lat', 'periodo', 'baixado_em'):
            self.assertIn(k, d)
        self.assertIn('NASA POWER', d['fonte'])
        self.assertIn('satelite', d['fonte'])

    def test_resposta_sem_dado_levanta(self):
        """Servico no ar devolvendo vazio e pior que servico fora do ar:
        seguir com lista vazia produziria uma concessao sem geracao."""
        vazio = {'properties': {'parameter': {}}}
        with self.assertRaises(ValueError):
            clima.baixar(0, 0, abrir=lambda u: vazio)

    def test_ausencia_marcada_com_999_nao_entra(self):
        ghi = list(GHI)
        ghi[12] = -999.0
        d = clima.baixar(0, 0, abrir=lambda u: _resposta(ghi, AMB))
        self.assertTrue(all(v >= 0 for v in d['irradiancia_kw_m2']))

    def test_fevereiro_bissexto(self):
        d = self._baixa(mes=2, ano=2024)
        self.assertTrue(d['periodo'].endswith('0229'), d['periodo'])
        d = self._baixa(mes=2, ano=2023)
        self.assertTrue(d['periodo'].endswith('0228'), d['periodo'])


class CacheEmDisco(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = clima.baixar(-46.6464, -23.5685,
                              abrir=lambda u: _resposta(GHI, AMB))

    def test_grava_e_le_de_volta(self):
        p = clima.gravar(self.d, os.path.join(self.tmp, 'c.json'))
        v = clima.carregar(p, log=lambda *a: None)
        self.assertIsNotNone(v)
        irr, cel = v
        self.assertEqual(len(irr), 96)
        self.assertEqual(irr, self.d['irradiancia_kw_m2'])

    def test_o_contrato_e_o_mesmo_do_carregar_clima(self):
        """`complementos.carregar_clima` devolve (irradiancia, celula) com 96
        pontos. O cache tem de devolver exatamente isso, senao o conversor
        precisaria saber de onde veio o clima — e ele nao pode precisar."""
        p = clima.gravar(self.d, os.path.join(self.tmp, 'c.json'))
        irr, cel = clima.carregar(p, log=lambda *a: None)
        self.assertEqual(len(irr), complementos.PASSOS
                         if hasattr(complementos, 'PASSOS') else 96)
        self.assertEqual(len(cel), len(irr))
        self.assertTrue(all(isinstance(x, float) for x in irr))

    def test_cache_ausente_devolve_none(self):
        self.assertIsNone(clima.carregar(os.path.join(self.tmp, 'nao_existe')))

    def test_cache_corrompido_devolve_none_e_nao_levanta(self):
        p = os.path.join(self.tmp, 'ruim.json')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('{isto nao e json')
        self.assertIsNone(clima.carregar(p, log=lambda *a: None))

    def test_cache_sem_sol_e_recusado(self):
        """Novembro e dezembro de 2025 vieram com os 96 pontos zerados no
        arquivo local. Modelar uma concessao inteira sem geracao por causa
        de um arquivo vazio e pior que cair no sintetico."""
        d = dict(self.d, irradiancia_kw_m2=[0.0] * 96)
        p = clima.gravar(d, os.path.join(self.tmp, 'zero.json'))
        self.assertIsNone(clima.carregar(p, log=lambda *a: None))

    def test_caminho_do_cache_separa_por_distribuidora_e_mes(self):
        a = clima.caminho_cache('/r', '370', 1)
        b = clima.caminho_cache('/r', '390', 1)
        c = clima.caminho_cache('/r', '370', 7)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)


class CentroideDaBase(unittest.TestCase):

    def test_base_sem_geometria_devolve_none(self):
        """O fixture e SEM GEOMETRIA de proposito. Sem coordenada nao ha de
        onde tirar o clima, e o modulo tem de dizer isso em vez de chutar
        um ponto."""
        self.assertIsNone(clima.centroide(BDGD(GDB, verbose=False)))


if __name__ == '__main__':
    unittest.main()
