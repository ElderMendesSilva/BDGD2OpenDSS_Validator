# -*- coding: utf-8 -*-
"""Coerencia de condutor — o que o auto-ajuste pega e o que ele deixa passar.

Achado 11 de ACHADOS_GENERALIZACAO.md. O condutor 593 da Enel SP (31 A,
8,232 ohm/km) cobre 2.993 km — 13,5% de toda a rede de media tensao — e
responde por 94,7% da quilometragem que opera acima da ampacidade e por
97,4% da perda que acontece ali. Trocar so ele por um condutor plausivel da
propria base resolve 87,8% dos alimentadores fisicamente impossiveis.

E o `linecodes._ajuste` NAO o toca. Este arquivo mede por que, e o motivo
importa mais do que o numero: o ajuste confere R1 contra CNOM *dentro da
SEGCON*, e 31 A com 8,2 ohm/km e um par internamente COERENTE. Um cabo fino
tem mesmo resistencia alta. O que esta errado nao e o par — e o USO, 2.993 km
de rede metropolitana nele. E uso so aparece depois de resolver o fluxo.

Dai a divisao deste arquivo: o que o ajuste faz, ele faz certo (primeira
classe, tudo verde); o que falta e uma verificacao de outra natureza, que
compara a corrente CALCULADA com a ampacidade DECLARADA (ultima classe,
falha esperada ate o passo 5).
"""
import math
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
from bdgd2dss import linecodes                    # noqa: E402
from bdgd2dss.leitor import BDGD                  # noqa: E402

GDB = None

# Calibrado para reproduzir a base real: na SEGCON da Enel SP o ajuste
# prevê ~19 A para uma resistencia de 8,232 ohm/km (registrado no achado 11).
# Com a lei R1 = K/CNOM isso da K = 8,232 x 19 = 156,4.
K = 156.4


def setUpModule():
    global GDB
    GDB = fixture.garantir()


def _populacao(n=80):
    """Uma SEGCON coerente: R1 = K/CNOM, com dispersao de catalogo.

    A dispersao e deterministica de proposito — teste que depende de sorteio
    passa e falha sem que nada tenha mudado. O seno so espalha o produto
    R1 x CNOM o bastante para o corte de percentis 5-95 ter o que cortar.
    """
    pares = []
    for i in range(n):
        cnom = 20.0 + i * 10.0                     # de 20 a 810 A
        pares.append((K / cnom * (1.0 + 0.15 * math.sin(i)), cnom))
    return pares


def _previsto(aj, cnom):
    a, b, _ = aj
    return math.exp(b) * cnom ** a


class AjusteCalibradoNaPropriaBase(unittest.TestCase):
    """O que o `_ajuste` faz — e faz certo."""

    def setUp(self):
        self.aj = linecodes._ajuste(_populacao())
        self.assertIsNotNone(self.aj, 'a populacao sintetica deveria calibrar')

    def test_recupera_a_lei_da_propria_amostra(self):
        """Nada de tabela externa: o expoente sai da SEGCON que esta sendo
        convertida. Com R1 = K/CNOM o expoente correto e -1."""
        a, b, _ = self.aj
        self.assertAlmostEqual(a, -1.0, places=1)
        self.assertAlmostEqual(math.exp(b), K, delta=0.25 * K)

    def test_a_populacao_sintetica_bate_com_a_base_real(self):
        """Confere a propria amostra deste arquivo contra um condutor real.

        O CND_1664 da Enel SP declara 254 A e 0,678 ohm/km — e o condutor
        usado como referencia na analise de sensibilidade do achado 11. Se a
        populacao sintetica prever algo muito diferente disso para 254 A, ela
        deixou de representar uma SEGCON e os testes abaixo nao valem nada.
        """
        self.assertAlmostEqual(_previsto(self.aj, 254.0), 0.678, delta=0.15)

    def test_amostra_pequena_nao_calibra_e_isso_e_declarado(self):
        """Menos de 50 condutores: nao ha ajuste, e portanto NENHUM R1 e
        corrigido. Roraima tem 153 e escapou; uma base menor nao escaparia.

        O que salva e a declaracao: o proprio LineCodes.dss diz que nao houve
        ajuste. Correcao que nao acontece em silencio ainda e defensavel.
        """
        self.assertIsNone(linecodes._ajuste(_populacao()[:40]))

        d = tempfile.mkdtemp()
        arq = os.path.join(d, 'LineCodes.dss')
        _, n, correcoes = linecodes.gerar(BDGD(GDB, verbose=False), arq)
        self.assertEqual(correcoes, [], 'com 4 condutores nada pode ser corrigido')
        self.assertEqual(n, 4)
        with open(arq, encoding='utf-8') as fh:
            texto = fh.read()
        self.assertIn('ajuste indisponivel', texto,
                      'a ausencia de calibracao tem de estar escrita no arquivo')

    def test_condutor_incoerente_e_corrigido(self):
        """O caso 1863 da Enel SP: 8,43 ohm/km declarados para 1.500 A.
        Um cabo de 1.500 A tem resistencia da ordem de 0,04 ohm/km."""
        prev = _previsto(self.aj, 1500.0)
        self.assertGreater(8.43 / prev, linecodes.FATOR_CORRIGE,
                           f'previsto {prev:.4f} ohm/km para 1.500 A')

    def test_so_corrige_para_baixo(self):
        """R1 muito ABAIXO do previsto e quase sempre barramento ou trecho
        ideal declarado de proposito. Eleva-lo inventaria impedancia."""
        prev = _previsto(self.aj, 500.0)
        self.assertLess(0.001, prev)
        self.assertLess(0.001, linecodes.FATOR_CORRIGE * prev,
                        'a condicao do codigo e r1 > fator*prev — nunca o inverso')


class OCondutor593(unittest.TestCase):
    """Por que o condutor que reprovou a Enel SP passa pelo auto-ajuste."""

    def setUp(self):
        self.aj = linecodes._ajuste(_populacao())
        self.r1, self.cnom = 8.232, 31.0

    def test_o_par_r1_cnom_e_coerente(self):
        """A verificacao que existe hoje aprova o 593, e com razao: 31 A pede
        mesmo resistencia dessa ordem. Nao ha nada a corrigir no registro."""
        prev = _previsto(self.aj, self.cnom)
        self.assertLess(self.r1, linecodes.FATOR_CORRIGE * prev,
                        f'previsto {prev:.3f} ohm/km para {self.cnom:.0f} A')

    def test_baixar_o_limiar_nao_resolveria(self):
        """A tentacao obvia depois do achado 11 e mexer no FATOR_CORRIGE.
        Este teste mede por que nao adianta: o 593 fica a ~1,6x do previsto,
        contra o limiar de 7,4x. Para pega-lo seria preciso descer abaixo de
        1,6x — dentro da dispersao normal de catalogo, varrendo junto os
        condutores legitimos. O 593 nao e um outlier de resistencia."""
        razao = self.r1 / _previsto(self.aj, self.cnom)
        self.assertGreater(razao, 1.0, 'esta acima do previsto, so que pouco')
        self.assertLess(razao, 2.0)
        self.assertLess(razao, linecodes.FATOR_CORRIGE / 3.0,
                        'a folga ate o limiar e de mais de 3x')

    def test_o_ajuste_nao_enxerga_quilometragem(self):
        """O ponto do achado 11. `_ajuste` recebe pares (R1, CNOM) e mais
        nada: o mesmo condutor cobrindo 1 km ou 3.000 km produz exatamente o
        mesmo veredito. A informacao que denunciaria o 593 nao chega ate aqui.
        """
        base = _populacao()
        v1 = _previsto(linecodes._ajuste(base + [(self.r1, self.cnom)]), self.cnom)
        v2 = _previsto(linecodes._ajuste(base + [(self.r1, self.cnom)] * 40),
                       self.cnom)
        self.assertNotAlmostEqual(v1, v2, places=6,
                                  msg='repetir o registro muda o ajuste...')
        # ...mas o veredito nao muda, porque o que pesa e quantas VEZES o
        # condutor aparece na SEGCON, nao quantos km de rede ele cobre.
        for prev in (v1, v2):
            self.assertLess(self.r1, linecodes.FATOR_CORRIGE * prev)

    def test_coerencia_entre_ampacidade_e_corrente(self):
        """O item que o achado 11 acrescentou ao passo 5 do PLANO.md.

        A verificacao que faltava e de outra natureza: compara a corrente
        CALCULADA pelo fluxo com a ampacidade DECLARADA, por condutor, e
        reporta ENRIQUECIMENTO — a fatia da sobrecarga dividida pela fatia da
        rede. Foi essa razao, 4,64x, que denunciou o 593.

        O caso abaixo e um recorte do que foi medido: 867,1 km de CND_593
        operando a 45 A com 31 A declarados, contra 2.230 km de CND_1664 a
        90 A com 254 A declarados. Toda a sobrecarga esta no primeiro, que e
        27,998% da rede — enriquecimento 1/0,27998 = 3,572x.
        """
        r = linecodes.coerencia_de_uso([
            {'linecode': 'CND_593_3F', 'km': 867.1, 'corrente': 45.0,
             'amps': 31.0},
            {'linecode': 'CND_1664_3F', 'km': 2230.0, 'corrente': 90.0,
             'amps': 254.0},
        ])
        self.assertAlmostEqual(r['CND_593_3F']['pct_da_sobrecarga'], 100.0, 1)
        self.assertAlmostEqual(r['CND_593_3F']['enriquecimento'], 3.572, 2)
        self.assertAlmostEqual(r['CND_1664_3F']['pct_da_sobrecarga'], 0.0, 1)
        self.assertAlmostEqual(r['CND_593_3F']['pct_do_proprio_km'], 100.0, 1)


class CoerenciaDeUso(unittest.TestCase):
    """A verificacao nova, nos casos em que ela pode enganar."""

    def test_rede_sem_sobrecarga_nao_produz_enriquecimento(self):
        """O controle da Enel CE: 0,0% da quilometragem acima da ampacidade.
        Enriquecimento tem de vir None, nao 1,0 — devolver 1,0 fingiria uma
        medida que nao houve, e o alerta dispararia numa base sadia."""
        r = linecodes.coerencia_de_uso([
            {'linecode': 'A', 'km': 100.0, 'corrente': 10.0, 'amps': 254.0},
            {'linecode': 'B', 'km': 50.0, 'corrente': 20.0, 'amps': 100.0},
        ])
        self.assertEqual(r['A']['pct_do_proprio_km'], 0.0)
        self.assertIsNone(r['A']['enriquecimento'])
        self.assertIsNone(linecodes.concentracao(r))

    def test_enriquecimento_1_quando_a_sobrecarga_acompanha_a_rede(self):
        """Se todo condutor sobrecarrega na mesma proporcao em que ocupa a
        rede, ninguem se destaca — e o alerta nao pode disparar."""
        r = linecodes.coerencia_de_uso([
            {'linecode': 'A', 'km': 80.0, 'corrente': 300.0, 'amps': 100.0},
            {'linecode': 'B', 'km': 20.0, 'corrente': 300.0, 'amps': 100.0},
        ])
        for k in ('A', 'B'):
            self.assertAlmostEqual(r[k]['enriquecimento'], 1.0, places=6)

    def test_condutor_extenso_e_sadio_nao_e_acusado(self):
        """Armadilha obvia: o condutor com mais km nao pode ser apontado so
        por ser o maior. Aqui A tem 90% da rede e nenhuma sobrecarga."""
        r = linecodes.coerencia_de_uso([
            {'linecode': 'A', 'km': 900.0, 'corrente': 50.0, 'amps': 254.0},
            {'linecode': 'B', 'km': 100.0, 'corrente': 50.0, 'amps': 31.0},
        ])
        self.assertEqual(r['A']['pct_da_sobrecarga'], 0.0)
        pior, enr, pct = linecodes.concentracao(r)
        self.assertEqual(pior, 'B')
        self.assertAlmostEqual(enr, 10.0, places=6)
        self.assertAlmostEqual(pct, 100.0, places=6)

    def test_a_perda_em_sobrecarga_e_atribuida_ao_condutor_certo(self):
        """97,4% da perda em trecho sobrecarregado da Enel SP estava no 593.
        A conta tem de somar sobre os trechos em sobrecarga, nao sobre todos
        os trechos do condutor."""
        r = linecodes.coerencia_de_uso([
            {'linecode': 'A', 'km': 10.0, 'corrente': 50.0, 'amps': 31.0,
             'perda_kw': 900.0},
            {'linecode': 'A', 'km': 10.0, 'corrente': 5.0, 'amps': 31.0,
             'perda_kw': 100.0},
            {'linecode': 'B', 'km': 10.0, 'corrente': 50.0, 'amps': 31.0,
             'perda_kw': 100.0},
        ])
        self.assertAlmostEqual(r['A']['perda_kw'], 1000.0)
        self.assertAlmostEqual(r['A']['perda_kw_sobrecarga'], 900.0)
        self.assertAlmostEqual(r['A']['pct_da_perda_em_sobrecarga'], 90.0, 6)
        self.assertAlmostEqual(r['A']['pct_do_proprio_km'], 50.0, 6)

    def test_ampacidade_ausente_nao_vira_sobrecarga(self):
        """Trecho sem CNOM declarado tem amps 0. Comparar corrente > 0
        acusaria a rede inteira."""
        r = linecodes.coerencia_de_uso([
            {'linecode': 'A', 'km': 10.0, 'corrente': 50.0, 'amps': 0.0},
        ])
        self.assertEqual(r['A']['km_sobrecarga'], 0.0)

    def test_margem_desloca_o_limiar(self):
        """`margem=2.0` mede a sobrecarga SEVERA, que foi a que separou os
        458 alimentadores dos demais por fator 8 (7,0% contra 0,9%)."""
        t = [{'linecode': 'A', 'km': 10.0, 'corrente': 50.0, 'amps': 31.0}]
        self.assertEqual(linecodes.coerencia_de_uso(t)['A']['km_sobrecarga'],
                         10.0)
        self.assertEqual(
            linecodes.coerencia_de_uso(t, margem=2.0)['A']['km_sobrecarga'],
            0.0)


if __name__ == '__main__':
    unittest.main()
