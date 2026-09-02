# -*- coding: utf-8 -*-
"""Achado 56 — a placa que e de outro transformador.

A guarda do `_placa`, escrita no achado 53, pergunta se o ferro esta entre
0,05% e 2,0% da nominal. Ela e CEGA A ESCALA: 1,50% passa folgado, e 1,50% de
10 kVA sao 150 W — que nao e o ferro de um 10 kVA, e sim o de um 30 kVA.
**Percentual errado continua parecendo percentual**, e por isso guarda em
percentual nunca pega erro de escala.

O QUE FOI MEDIDO NA CEMIG

    classe    ferro    unidades   fases do primario
     10 kVA   150 W     280.574   monofasicas
     30 kVA   150 W      27.729   TRIFASICAS
     15 kVA   195 W     116.115   monofasicas
     45 kVA   195 W      81.843   TRIFASICAS

150 W e o valor certo de um BANCO trifasico de 30 kVA — tres unidades de
10 kVA a 50 W. Ele foi copiado para as unidades individuais. **A hipotese
inversa foi testada e caiu:** eu supus que o codigo desse a potencia por fase
num banco, e entao os 280.574 seriam trifasicos. Sao monofasicos, todos.

A propria Cemig tem o valor certo em 1.507 unidades de 10 kVA com 50 W. O erro
e interno a base.

Sao 396.689 transformadores, 42% do parque, uns 43.000 kW de ferro a mais —
perto de 30% do ferro que a base declara.

A REGRA E UMA CURVA. Tabela por classe cresce a cada distribuidora e nunca
fica pronta, que e a licao do achado 5. `W = 10,4 x kVA^0,77`, ajustada sobre
a mediana das seis bases sadias, com faixa de metade a dobro. Das 56 celulas
(7 bases x 8 classes), as UNICAS tres fora da faixa sao as tres da Cemig.

     kVA   curva    min    max      RR   ENCE   EQPA     SP     LT   CPFL   CMIG
       5      36     18     72      35     35     40     70     30     50     35
      10      61     31    122      50     50     55     70     45     60    150!
      15      84     42    167      65     85     60    110     60    100    195!
      30     143     71    285     150    150    150    170    130    170    150
      45     195     97    390     195    195    170    260    170    220    195
      75     289    144    578     295    295    255    390    255    330    295
   112,5     395    197    790     390    390    335    520    335    440    150!
     150     493    246    985     485    485    420    640    420    540    485
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'etapas'))
from bdgd2dss import transformadores as tr        # noqa: E402

# (base, kVA, watts) das seis sadias — a linha que a faixa NAO pode reprovar.
SADIAS = [
    ('RR', 5, 35), ('RR', 10, 50), ('RR', 15, 65), ('RR', 30, 150),
    ('RR', 45, 195), ('RR', 75, 295), ('RR', 112.5, 390), ('RR', 150, 485),
    ('ENCE', 5, 35), ('ENCE', 10, 50), ('ENCE', 15, 85), ('ENCE', 30, 150),
    ('ENCE', 45, 195), ('ENCE', 75, 295), ('ENCE', 112.5, 390),
    ('ENCE', 150, 485),
    ('EQPA', 5, 40), ('EQPA', 10, 55), ('EQPA', 15, 60), ('EQPA', 30, 150),
    ('EQPA', 45, 170), ('EQPA', 75, 255), ('EQPA', 112.5, 335),
    ('EQPA', 150, 420),
    ('SP', 5, 70), ('SP', 10, 70), ('SP', 15, 110), ('SP', 30, 170),
    ('SP', 45, 260), ('SP', 75, 390), ('SP', 112.5, 520), ('SP', 150, 640),
    ('LT', 5, 30), ('LT', 10, 45), ('LT', 15, 60), ('LT', 30, 130),
    ('LT', 45, 170), ('LT', 75, 255), ('LT', 112.5, 335), ('LT', 150, 420),
    ('CPFL', 5, 50), ('CPFL', 10, 60), ('CPFL', 15, 100), ('CPFL', 30, 170),
    ('CPFL', 45, 220), ('CPFL', 75, 330), ('CPFL', 112.5, 440),
    ('CPFL', 150, 540),
    # da Cemig, as classes que estao certas
    ('CMIG', 5, 35), ('CMIG', 30, 150), ('CMIG', 45, 195), ('CMIG', 75, 295),
    ('CMIG', 150, 485),
]

DOENTES = [('CMIG', 10, 150), ('CMIG', 15, 195), ('CMIG', 112.5, 150)]


class AFaixaSepara(unittest.TestCase):
    """O teste que vale mais que todos: as 53 celulas sadias das sete bases
    passam e as 3 doentes caem. Nao e um exemplo escolhido — e o censo."""

    def test_as_53_celulas_sadias_passam(self):
        for base, kva, w in SADIAS:
            self.assertFalse(tr._ferro_fora_de_escala(kva, w),
                             f'{base} {kva} kVA / {w} W foi reprovado, e e '
                             f'placa legitima')

    def test_as_3_celulas_doentes_caem(self):
        for base, kva, w in DOENTES:
            self.assertTrue(tr._ferro_fora_de_escala(kva, w),
                            f'{base} {kva} kVA / {w} W passou, e e a placa de '
                            f'outro transformador')

    def test_pega_os_DOIS_lados(self):
        """O 112,5 kVA da Cemig erra PARA BAIXO — 150 W onde a curva pede 395
        — e nao obedece ao fator 3 dos outros dois. Uma guarda que so olhasse
        excesso o deixaria passar."""
        self.assertTrue(tr._ferro_fora_de_escala(112.5, 150),
                        'ferro de menos tambem e placa de outro tamanho')
        self.assertTrue(tr._ferro_fora_de_escala(10, 150),
                        'ferro de mais')

    def test_a_folga_da_faixa_e_deliberada(self):
        """O 5 kVA da Enel SP declara 70 W e o da Light 30 W — as duas sao
        defensaveis, e sao 2,3x uma da outra. Faixa apertada viraria diferenca
        de fabricante em defeito. A da Cemig e 2,5x a curva e sobra."""
        self.assertEqual(tr.FERRO_FAIXA, 2.0)
        self.assertFalse(tr._ferro_fora_de_escala(5, 70))
        self.assertFalse(tr._ferro_fora_de_escala(5, 30))


class ACurva(unittest.TestCase):

    def test_cresce_menos_que_a_potencia(self):
        """O nucleo tem um minimo que nao some quando a potencia cai: dobrar o
        kVA nao dobra o ferro. Se o expoente virasse 1, a curva deixaria de
        descrever transformador e o 5 kVA seria reprovado em toda base."""
        self.assertLess(tr.FERRO_B, 1.0)
        self.assertGreater(tr.FERRO_B, 0.5)
        self.assertLess(tr.ferro_esperado(20) / tr.ferro_esperado(10), 2.0)

    def test_bate_com_as_classes_medidas(self):
        for kva, esperado in ((10, 61), (30, 143), (75, 289), (150, 493)):
            self.assertAlmostEqual(tr.ferro_esperado(kva), esperado, delta=3,
                                   msg=f'{kva} kVA')

    def test_campo_vazio_nao_e_fora_de_escala(self):
        """Ausencia de dado nao e defeito de escala — quem trata isso e o
        `_placa`, e confundir os dois faria a contagem de trocadas mentir."""
        for kva, w in ((None, 150), (10, None), (10, 0), (0, 150), (10, -5)):
            self.assertFalse(tr._ferro_fora_de_escala(kva, w), f'{kva}/{w}')


class OPlacaRejeita(unittest.TestCase):
    """`_placa` recebe CODIGO da TPOTAPRT, e nao kVA. '3' e 10 kVA."""

    def test_a_placa_da_cemig_de_10kva_e_recusada(self):
        self.assertIsNone(tr._placa('3', 150, 695))

    def test_a_placa_certa_de_10kva_passa(self):
        p = tr._placa('3', 50, 245)
        self.assertIsNotNone(p)
        self.assertAlmostEqual(p[0], 0.5, places=3)     # 50 W / 100 = 0,50%

    def test_a_guarda_percentual_continua_valendo(self):
        """A do achado 53 nao foi substituida, foi somada: ela pega o campo
        vazio, o zero e o total menor que o ferro."""
        self.assertIsNone(tr._placa('3', 0, 245))
        self.assertIsNone(tr._placa('3', 150, 100))
        self.assertIsNone(tr._placa('codigo-que-nao-existe', 50, 245))


def _eqtrmt(linhas):
    """`linhas` = [(cod, codigo_potencia, per_fer, per_tot)]."""
    a = lambda *v: np.array(v, dtype=object)          # noqa: E731
    return {'UNI_TR_MT': a(*[x[0] for x in linhas]),
            'POT_NOM': a(*[x[1] for x in linhas]),
            'PER_FER': np.array([x[2] for x in linhas], dtype=float),
            'PER_TOT': np.array([x[3] for x in linhas], dtype=float),
            'R': np.array([1.5] * len(linhas)),
            'XHL': np.array([3.0] * len(linhas))}


class ASubstituicaoVemDaPropriaBase(unittest.TestCase):
    """O valor certo esta dentro da base: a Cemig tem 1.507 unidades de 10 kVA
    com 50 W ao lado de 280.574 com os 150 W do banco. A curva serve para
    decidir QUEM esta errado, e nao para dizer o que colocar no lugar."""

    def test_a_placa_sadia_da_classe_substitui_a_doente(self):
        imp, censo = tr.placas_da_base(_eqtrmt([
            ('BOM', '3', 50, 245),          # 10 kVA sadio
            ('MAU', '3', 150, 695),         # 10 kVA com a placa do banco
        ]))
        self.assertEqual(imp['MAU'][2], imp['BOM'][2])
        self.assertAlmostEqual(imp['MAU'][2][0], 0.5, places=3)
        self.assertEqual(censo['placa_trocada'], 1)
        self.assertEqual(censo['sem_substituto'], 0)

    def test_a_maioria_nao_manda_se_estiver_errada(self):
        """280.574 erradas contra 1.507 certas: quem decide e a curva, e nao
        a contagem. Contar votos entregaria a base ao proprio defeito."""
        linhas = [(f'M{i}', '3', 150, 695) for i in range(50)]
        linhas.append(('BOM', '3', 50, 245))
        imp, censo = tr.placas_da_base(_eqtrmt(linhas))
        self.assertEqual(censo['placa_trocada'], 50)
        self.assertAlmostEqual(imp['M0'][2][0], 0.5, places=3)

    def test_classe_sem_placa_sadia_fica_sem_ferro(self):
        """Preferir isso a inventar: o `R` ruim e problema conhecido e
        medido, placa inventada nao."""
        imp, censo = tr.placas_da_base(_eqtrmt([('MAU', '3', 150, 695)]))
        self.assertIsNone(imp['MAU'][2])
        self.assertEqual(censo['sem_substituto'], 1)
        self.assertEqual(censo['placa_trocada'], 0)

    def test_a_classe_e_o_kVA_e_nao_o_codigo(self):
        """Uma classe nao empresta placa para outra: a de 30 kVA sadia nao
        pode consertar a de 10 kVA, senao a substituicao repete o defeito que
        ela existe para desfazer."""
        imp, censo = tr.placas_da_base(_eqtrmt([
            ('T30', '8', 150, 695),         # 30 kVA sadio
            ('T10', '3', 150, 695),         # 10 kVA doente
        ]))
        self.assertIsNotNone(imp['T30'][2])
        self.assertIsNone(imp['T10'][2],
                          'a placa de 30 kVA nao serve ao 10 kVA')

    def test_r_e_xhl_atravessam_intactos(self):
        """A troca e da PLACA. `R` e `Xhl` sao outro campo e outro achado."""
        imp, _ = tr.placas_da_base(_eqtrmt([('X', '3', 150, 695)]))
        self.assertEqual(imp['X'][0], 1.5)
        self.assertEqual(imp['X'][1], 3.0)

    def test_base_toda_sadia_nao_troca_nada(self):
        imp, censo = tr.placas_da_base(_eqtrmt([
            ('A', '3', 50, 245), ('B', '8', 150, 695)]))
        self.assertEqual(censo['placa_trocada'], 0)
        self.assertEqual(censo['com_placa'], 2)
        self.assertEqual(censo['total'], 2)


if __name__ == '__main__':
    unittest.main()
