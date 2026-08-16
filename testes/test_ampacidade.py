# -*- coding: utf-8 -*-
"""Substituicao por ampacidade insuficiente — achado 34.

O condutor CND_593 da Enel SP tem 31 A e 8,232 ohm/km, e cobre 2.990 km da
rede — 13,5%. Na base inteira, 16,1% da quilometragem carrega 73,6% da
resistencia ponderada. Um fio de 31 A num tronco que conduz 1.370 A nao e um
fio de 31 A.

Estes testes trancam a REGRA, que e estreita de proposito: so troca quem
excede a propria ampacidade, so troca para baixo, e so para condutor que a
propria base declara possuir.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import ampacidade                       # noqa: E402


def _cat(*itens):
    """Cada item: (nome, cnom, r1). Todos trifasicos."""
    return {n: {'cnom': c, 'r1': r, 'x1': 0.4, 'nfases': 3}
            for n, c, r in itens}


CATALOGO = _cat(('FINO', 31.0, 8.232),      # o 593 da Enel SP
                ('MEDIO', 105.0, 1.660),
                ('GROSSO', 254.0, 0.636),
                ('TRONCO', 600.0, 0.197))


class AEscolha(unittest.TestCase):

    def setUp(self):
        self.cat = ampacidade.catalogo_de(CATALOGO)

    def test_dentro_da_ampacidade_nao_troca(self):
        self.assertIsNone(ampacidade.substituto(
            20.0, CATALOGO['FINO'], self.cat))

    def test_acima_da_ampacidade_pega_o_mais_fino_que_cobre(self):
        c = ampacidade.substituto(200.0, CATALOGO['FINO'], self.cat)
        self.assertEqual(c['nome'], 'GROSSO', 'o de 254 A cobre 200 A; o de '
                                              '600 A seria exagero')

    def test_o_limite_e_exatamente_a_ampacidade(self):
        """31 A num condutor de 31 A esta dentro. 31,1 nao esta."""
        self.assertIsNone(ampacidade.substituto(31.0, CATALOGO['FINO'], self.cat))
        self.assertIsNotNone(ampacidade.substituto(31.1, CATALOGO['FINO'],
                                                   self.cat))

    def test_condutor_sem_ampacidade_nao_e_avaliado(self):
        self.assertIsNone(ampacidade.substituto(
            9999.0, {'cnom': 0, 'r1': 5.0}, self.cat))

    def test_corrente_acima_de_todo_o_catalogo_nao_troca(self):
        """Rede alem do que a distribuidora declara possuir: vira alerta, e
        nao uma troca por um condutor inventado."""
        self.assertIsNone(ampacidade.substituto(5000.0, CATALOGO['FINO'],
                                                self.cat))

    def test_nunca_aumenta_a_resistencia(self):
        """Um condutor grosso sobrecarregado nao vira fino."""
        cat = ampacidade.catalogo_de(_cat(('A', 100.0, 0.10),
                                          ('B', 900.0, 9.99)))
        self.assertIsNone(ampacidade.substituto(500.0, {'cnom': 100.0,
                                                        'r1': 0.10}, cat))

    def test_a_margem_afrouxa_o_criterio(self):
        a = CATALOGO['FINO']
        self.assertIsNotNone(ampacidade.substituto(40.0, a, self.cat))
        self.assertIsNone(ampacidade.substituto(40.0, a, self.cat, margem=2.0))


class ADecisao(unittest.TestCase):

    def _t(self, linha, lc, km, i):
        return {'linha': linha, 'linecode': lc, 'km': km, 'corrente': i}

    def test_troca_so_o_trecho_sobrecarregado(self):
        """O MESMO condutor pode estar certo no ramal e errado no tronco. A
        troca e por trecho, nunca por codigo."""
        subs, r = ampacidade.decidir(
            [self._t('L1', 'FINO', 10.0, 200.0),      # tronco
             self._t('L2', 'FINO', 5.0, 12.0)],       # ramal, dentro
            CATALOGO)
        self.assertEqual([s['linha'] for s in subs], ['L1'])
        self.assertEqual(r['trocados'], 1)
        self.assertAlmostEqual(r['km_trocado'], 10.0)
        self.assertAlmostEqual(r['pct_km'], 66.67, places=1)

    def test_o_resumo_conta_por_condutor(self):
        subs, r = ampacidade.decidir(
            [self._t('L1', 'FINO', 1.0, 200.0),
             self._t('L2', 'FINO', 1.0, 240.0),
             self._t('L3', 'MEDIO', 1.0, 300.0)], CATALOGO)
        self.assertEqual(r['por_condutor'], {'FINO': 2, 'MEDIO': 1})

    def test_sem_candidato_vira_alerta_e_nao_troca(self):
        subs, r = ampacidade.decidir(
            [self._t('L1', 'FINO', 1.0, 5000.0)], CATALOGO)
        self.assertEqual(subs, [])
        self.assertEqual(r['sem_candidato'], {'FINO': 1})

    def test_linecode_desconhecido_e_ignorado_sem_quebrar(self):
        subs, r = ampacidade.decidir(
            [self._t('L1', 'NAO_EXISTE', 1.0, 5000.0)], CATALOGO)
        self.assertEqual((subs, r['trocados']), ([], 0))

    def test_nao_mistura_numero_de_fases(self):
        """Trocar um monofasico por um trifasico mudaria a matriz, nao so a
        resistencia."""
        cat = {'M1': {'cnom': 31.0, 'r1': 8.2, 'x1': 0.4, 'nfases': 1},
               'T3': {'cnom': 600.0, 'r1': 0.2, 'x1': 0.4, 'nfases': 3}}
        subs, _ = ampacidade.decidir(
            [self._t('L1', 'M1', 1.0, 500.0)], cat)
        self.assertEqual(subs, [], 'nao ha monofasico que cubra 500 A')


class OArquivo(unittest.TestCase):

    def setUp(self):
        self.alvo = os.path.join(tempfile.mkdtemp(), '_AMPACIDADE.dss')

    def _gera(self, trechos):
        subs, r = ampacidade.decidir(trechos, CATALOGO)
        ampacidade.escrever(self.alvo, subs, r)
        return open(self.alvo, encoding='utf-8').read()

    def test_reatribui_a_linha_a_um_codigo_derivado(self):
        """Duas armadilhas, as duas medidas na pratica.

        Editar o LineCode nao alcanca linha ja criada: o OpenDSS copia a
        impedancia para dentro da Line quando ela nasce. E editar `r1` direto
        na Line tambem nao serve — a Line e declarada em METROS, entao o r1
        lancado nela vira ohm/metro. Escrever 0,636 virou 636 ohm/km e a perda
        da DALV saltou de 11,53% para 37,81%.

        O que funciona: LineCode derivado, que carrega a propria unidade."""
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0}])
        self.assertIn('New LineCode.FINO_AJ254', t)
        self.assertIn('Edit Line.L1 linecode=FINO_AJ254', t)
        self.assertNotIn('Edit Line.L1 r1=', t)

    def test_o_codigo_derivado_declara_a_unidade(self):
        """Sem `units=km` o OpenDSS adota a unidade do circuito, e o erro
        volta pela outra porta."""
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0}])
        self.assertIn('units=km', t)

    def test_r_vem_do_substituto_e_X_vem_do_original(self):
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0}])
        self.assertIn('r1=0.63600', t)          # do GROSSO
        self.assertIn('r0=1.90800', t)
        self.assertIn('x1=0.40000', t)          # do FINO, inalterado

    def test_um_codigo_derivado_por_par_e_nao_por_trecho(self):
        t = self._gera([{'linha': f'L{i}', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0} for i in range(5)])
        self.assertEqual(t.count('New LineCode.FINO_AJ254'), 1)
        self.assertEqual(t.count('Edit Line.'), 5)

    def test_a_troca_fica_dita_na_propria_linha(self):
        """Substituicao silenciosa e pior que o defeito."""
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0}])
        for esperado in ('FINO', 'GROSSO', '31 A', '254 A', 'I=200 A'):
            self.assertIn(esperado, t)

    def test_o_cabecalho_diz_que_e_modelagem_e_como_desfazer(self):
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 200.0}])
        self.assertIn('MODELAGEM, NAO CONVERSAO', t)
        self.assertIn('_AMPACIDADE.dss', t, 'tem de dizer como desfazer')

    def test_sem_troca_o_arquivo_existe_e_diz_que_nao_houve(self):
        """O MASTER redireciona sempre; arquivo ausente derrubaria a
        compilacao da subestacao inteira."""
        t = self._gera([{'linha': 'L1', 'linecode': 'FINO', 'km': 1.0,
                         'corrente': 5.0}])
        self.assertIn('nenhum trecho excede', t)


if __name__ == '__main__':
    unittest.main()
