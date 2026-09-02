# -*- coding: utf-8 -*-
"""O diagnóstico das anomalias.

O que estes testes protegem é a regra central do módulo: **medido e causa
provável nunca se misturam**, e nenhuma causa é afirmada sem ter sido
verificada no modelo. Um relatório que erra a explicação e apresenta os dois
como a mesma coisa ensina quem lê a desconfiar também do número.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import anomalias                             # noqa: E402


class Rede(object):
    """Um circuito de mentira com a forma da DSS C-API."""

    def __init__(self, barras, linhas=(), cargas=(), trafos=()):
        self._barras = barras            # nome -> (kVBase, [pu por no])
        self._ativa = None
        self._linhas = list(linhas)      # (nome, normamps, [correntes])
        self._cargas = list(cargas)      # (nome, kv, barra)
        self._trafos = list(trafos)      # (nome, [barras], kv_por_wdg)
        self._elem = None
        self._i = {}
        r = self

        class _Circuit(object):
            def AllBusNames(self):
                return list(r._barras)

            def SetActiveBus(self, b):
                r._ativa = b.split('.')[0]

            def SetActiveElement(self, e):
                r._elem = e
        self.Circuit = _Circuit()

        class _Bus(object):
            def kVBase(self):
                return r._barras.get(r._ativa, (0, []))[0]

            def puVmagAngle(self):
                pus = r._barras.get(r._ativa, (0, []))[1]
                saida = []
                for p in pus:
                    saida += [p, 0.0]
                return saida

            def Coorddefined(self):
                return True
        self.Bus = _Bus()
        self.Lines = _Colecao(r, '_linhas')
        self.Loads = _Colecao(r, '_cargas')
        self.Transformers = _Colecao(r, '_trafos')

        class _Ckt(object):
            def CurrentsMagAng(self):
                for nome, _n, cs in r._linhas:
                    if (r._elem or '').lower() == 'line.' + nome.lower():
                        saida = []
                        for c in cs:
                            saida += [c, 0.0]
                        return saida
                return []

            def BusNames(self):
                for nome, _kv, b in r._cargas:
                    if (r._elem or '').lower() == 'load.' + nome.lower():
                        return [b]
                for nome, bs, _kvs in r._trafos:
                    if (r._elem or '').lower() == 'transformer.' + nome.lower():
                        return list(bs)
                return ['']
        self.CktElement = _Ckt()


class _Colecao(object):
    def __init__(self, rede, campo):
        self._r, self._c, self._i = rede, campo, 0

    def _itens(self):
        return getattr(self._r, self._c)

    def First(self):
        self._i = 1
        return 1 if self._itens() else 0

    def Next(self):
        self._i += 1
        return self._i if self._i <= len(self._itens()) else 0

    def Name(self):
        return self._itens()[self._i - 1][0]

    def NormAmps(self):
        return self._itens()[self._i - 1][1]

    def kV(self):
        it = self._itens()[self._i - 1]
        return it[1] if self._c == '_cargas' else it[2][self._wdg - 1]

    _wdg = 1

    def Wdg(self, n):
        self._wdg = int(n)


class TestTensaoAlta(unittest.TestCase):

    def test_nomeia_o_trafo_que_colocou_a_barra_la(self):
        """O caso real da 5003305: um ponto em 1,551 pu entre 6.731 barras.

        A causa não é sobretensão: é o secundário do transformador declarado em
        22 kV onde o padrão é 0,22 kV. O relatório tem de dizer isso e dar o
        nome do elemento, senão a pessoa não tem o que fazer com a informação.
        """
        r = Rede(barras={'boa': (7.97, [0.98]), 'alta': (7.97, [1.551])},
                 trafos=[('T1', ['origem', 'alta'], [13.8, 22.0])])
        a = anomalias.do_modelo(r)
        alto = [x for x in a if 'acima' in x['titulo']]
        self.assertEqual(len(alto), 1)
        self.assertIn('1,551', alto[0]['medido'])
        self.assertIn('Transformer.T1', ' '.join(alto[0]['elementos']))
        self.assertIn('22,0000 kV', ' '.join(alto[0]['elementos']))

    def test_atribui_ao_cadastro_e_nao_ao_conversor(self):
        """A tese do projeto depende desta frase estar certa."""
        r = Rede(barras={'alta': (7.97, [1.6])},
                 trafos=[('T1', ['x', 'alta'], [13.8, 22.0])])
        causa = anomalias.do_modelo(r)[0]['causa']
        self.assertIn('defeito está no dado', causa)

    def test_tensao_dentro_da_faixa_nao_vira_achado(self):
        r = Rede(barras={'a': (7.97, [1.02]), 'b': (7.97, [0.95])})
        self.assertEqual([x for x in anomalias.do_modelo(r)
                          if 'acima' in x['titulo']], [])


class TestOutrosDoModelo(unittest.TestCase):

    def test_barra_morta_separada_de_barra_com_tensao_baixa(self):
        """Zero pu e 0,5 pu são problemas diferentes, com causas diferentes.

        Somar os dois num número só foi o que produziu o valor de 25,70% que
        este projeto publicou errado (achados 21 e 23).
        """
        r = Rede(barras={'morta': (7.97, [0.0]), 'baixa': (7.97, [0.5]),
                         'ok': (7.97, [0.98])})
        titulos = [x['titulo'] for x in anomalias.do_modelo(r)]
        self.assertTrue(any('não recebem tensão' in t for t in titulos))
        self.assertTrue(any('abaixo de' in t for t in titulos))

    def test_laco_e_distinguido_de_sobrecarga(self):
        """2.500 A num cabo de 145 A não é rede carregada: é corrente de laço."""
        r = Rede(barras={'a': (7.97, [0.98])},
                 linhas=[('L1', 145.0, [2506.0, 2506.0, 2506.0])])
        a = [x for x in anomalias.do_modelo(r) if x['figura'] == 'condutor']
        self.assertEqual(len(a), 1)
        self.assertIn('laço', a[0]['causa'])

    def test_sobrecarga_moderada_atribuida_ao_cadastro(self):
        r = Rede(barras={'a': (7.97, [0.98])},
                 linhas=[('L%d' % k, 100.0, [120.0]) for k in range(10)])
        a = [x for x in anomalias.do_modelo(r) if x['figura'] == 'condutor']
        self.assertNotIn('laço', a[0]['causa'])
        self.assertIn('poste', a[0]['causa'])

    def test_carga_com_tensao_cem_vezes_maior(self):
        r = Rede(barras={'b': (0.127, [0.98])},
                 cargas=[('C1', 12.7017, 'b.1.4')])
        a = [x for x in anomalias.do_modelo(r) if 'Cargas' in x['titulo']]
        self.assertEqual(len(a), 1)
        self.assertIn('Load.C1', ' '.join(a[0]['elementos']))

    def test_fase_neutro_contra_fase_fase_nao_e_anomalia(self):
        """A raiz de três é legítima e não pode virar achado — seria ruído em
        todo modelo do país."""
        r = Rede(barras={'b': (7.97, [0.98])}, cargas=[('C1', 13.8, 'b')])
        self.assertEqual([x for x in anomalias.do_modelo(r)
                          if 'Cargas' in x['titulo']], [])

    def test_modelo_que_explode_nao_derruba_o_relatorio(self):
        class Explode(object):
            def __getattr__(self, _n):
                raise RuntimeError('sem circuito')
        self.assertEqual(anomalias.do_modelo(Explode()), [])


class TestDoDia(unittest.TestCase):

    def test_fator_de_carga_alto_vira_achado_de_curva_unica(self):
        a = anomalias.do_dia({'fator_de_carga': 0.95})
        self.assertIn('mesma curva', a[0]['causa'])

    def test_coincidencia_baixa_cita_as_duas_horas(self):
        a = anomalias.do_dia({'coincidencia_gd': 0.05, 'kWh_gd': 100,
                              'gd_no_pico_kW': 5, 'gd_pico_kW': 100,
                              'hora_gd_pico': 12.0, 'hora_pico': 22.25})
        self.assertIn('12h00', a[0]['causa'])
        self.assertIn('22h15', a[0]['causa'])

    def test_dia_sadio_nao_gera_achado(self):
        self.assertEqual(anomalias.do_dia({'fator_de_carga': 0.55,
                                           'razao_perda_pico_vale': 3.0}), [])

    def test_serie_ausente_nao_levanta(self):
        self.assertEqual(anomalias.do_dia(None), [])


class TestEstrutura(unittest.TestCase):

    def test_medido_e_causa_sao_campos_separados(self):
        """Se algum dia se juntarem, o número passa a carregar o risco da
        interpretação — e é o número que tem de sobreviver a uma explicação
        errada."""
        for a in anomalias.do_dia({'fator_de_carga': 0.95}):
            self.assertTrue(a['medido'] and a['causa'])
            self.assertNotEqual(a['medido'], a['causa'])

    def test_o_grave_vem_antes_do_informativo(self):
        r = Rede(barras=dict([('m%d' % k, (7.97, [0.0])) for k in range(50)]
                             + [('ok', (7.97, [0.98]))]),
                 linhas=[('L1', 100.0, [120.0])])
        g = [x['gravidade'] for x in anomalias.do_modelo(r)]
        self.assertEqual(g, sorted(g, key=lambda x: {'grave': 0, 'atencao': 1,
                                                     'nota': 2}[x]))

    def test_por_figura_agrupa(self):
        d = anomalias.por_figura([{'figura': 'perfil'}, {'figura': 'perfil'},
                                  {'figura': 'dia'}])
        self.assertEqual(len(d['perfil']), 2)


if __name__ == '__main__':
    unittest.main()


class TestExportacao(unittest.TestCase):

    def test_exportar_no_dia_e_achado_grave(self):
        a = anomalias.do_dia({'exporta_no_dia': True, 'kWh_fonte': -3388,
                              'kWh_gd': 11000})
        grave = [x for x in a if x['gravidade'] == anomalias.GRAVE]
        self.assertEqual(len(grave), 1)
        self.assertIn('sem a carga correspondente', grave[0]['causa'])

    def test_a_causa_nao_culpa_o_conversor(self):
        """É declaração, não modelagem — e o texto tem de dizer isso, porque é
        a tese do projeto."""
        a = anomalias.do_dia({'exporta_no_dia': True, 'kWh_fonte': -1,
                              'kWh_gd': 2})
        self.assertIn('não é operação', a[0]['causa'])
