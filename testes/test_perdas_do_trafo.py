# -*- coding: utf-8 -*-
"""Achado 53: o trafo de distribuicao nao tinha ferro, e o cobre vinha errado.

SAO DOIS DEFEITOS NO MESMO LUGAR, e um mascarava o outro.

1. SEM PERDA A VAZIO. O caminho de ALTA tensao sempre escreveu
   `%noloadloss` a partir de `PER_FER`; o de distribuicao nunca escreveu
   nada, e `%noloadloss` do OpenDSS e ZERO por omissao. Todo transformador
   de distribuicao das sete bases — 2,3 milhoes deles — estava sem ferro.

   Perda de ferro e CONSTANTE, 24 h por dia. Medido, o que faltava em % da
   carga viva de cada base:

       Cemig-D 3,60%   CPFL    1,79%   Enel SP 1,48%
       RR      2,55%   Light   1,52%   Enel CE 1,45%
       EQPA    2,41%

   Isso e da ordem de TUDO o que o modelo perdia: a Equatorial PA modelava
   1,09% e deixava 2,41% de fora.

2. O `EQTRMT.R` NAO E CONFIAVEL, e erra com SINAL DIFERENTE por base.
   Comparado com a placa — `(PER_TOT - PER_FER) / (kVA x 10)`:

       base   R mediana  valores distintos  carga real   R/real
       RR         4,150         15            2,100%      1,98
       ENCE       2,960          6            1,950%      1,52
       EQPA       1,000          2            1,900%      0,53
       SP         1,330         37            1,536%      0,87
       LT         1,320         22            1,218%      1,08
       CPFL       1,317         38            1,733%      0,76
       CMIG       1,800         41            2,100%      0,86

   DOIS valores distintos em 227 mil transformadores da Equatorial PA;
   quinze em Roraima. Ali o campo e marcador de posicao — e o desvio explica
   os dois extremos que sobravam contra a ancora da ANEEL: Roraima DOBRA o
   cobre e modelava mais perda em MT do que o pais inteiro perde em toda a
   distribuicao; a EQPA CORTA PELA METADE e modelava um setimo.

O QUE ESTES TESTES TRANCAM

1. A UNIDADE. `PER_FER` e `PER_TOT` estao em WATTS e o OpenDSS quer PERCENTO
   da nominal: `% = W / (kVA x 10)`. Errar isto e um fator de 10 na perda de
   2,3 milhoes de transformadores.

2. `POT_NOM` E CODIGO, e nao valor. Ele indexa a TPOTAPRT — 75 kVA e o
   codigo '16'. Tratar '16' como 16 kVA daria ferro 4,7x maior.

3. COBRE = TOTAL MENOS FERRO. `PER_TOT` inclui o ferro; usa-lo inteiro como
   perda em carga conta o ferro duas vezes.

4. A PLACA MANDA, O `R` E RESERVA — e sem placa o comportamento antigo fica
   intacto, inclusive o achado 26 (metade em cada enrolamento).

5. PLACA ABSURDA NAO SUBSTITUI NADA. Cadastro com ferro de 50% da nominal e
   erro de digitacao, e promove-lo a modelo seria trocar um defeito por um
   pior.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import transformadores as tr                # noqa: E402

# codigos da TPOTAPRT: '16' = 75 kVA, '20' = 112,5 kVA, '2' = 5 kVA
C75, C112, C5 = '16', '20', '2'


class AUnidadeEWatt(unittest.TestCase):

    def test_a_conta_e_watt_sobre_kva_vezes_dez(self):
        """295 W num trafo de 75 kVA sao 0,393% da nominal."""
        ferro, cobre = tr._placa(C75, 295, 1395)
        self.assertAlmostEqual(ferro, 0.3933, places=4)
        self.assertAlmostEqual(cobre, 1.4667, places=4)

    def test_o_cobre_e_o_total_menos_o_ferro(self):
        """PER_TOT inclui o ferro; usa-lo inteiro conta duas vezes."""
        ferro, cobre = tr._placa(C112, 390, 1890)
        self.assertAlmostEqual(ferro + cobre, 1890 / (112.5 * 10.0), places=3)
        self.assertAlmostEqual(cobre, (1890 - 390) / (112.5 * 10.0), places=4)

    def test_pot_nom_e_CODIGO_e_nao_valor(self):
        """'16' e o codigo de 75 kVA. Trata-lo como 16 kVA daria 4,7x mais."""
        ferro, _ = tr._placa(C75, 295, 1395)
        errado = 295 / (16 * 10.0)
        self.assertNotAlmostEqual(ferro, errado, places=2)
        self.assertAlmostEqual(ferro, 295 / (75 * 10.0), places=4)

    def test_um_trafo_pequeno_tambem_fecha(self):
        """5 kVA com 35 W e 140 W: 0,700% e 2,100%, conferido na BDGD de RR."""
        ferro, cobre = tr._placa(C5, 35, 140)
        self.assertAlmostEqual(ferro, 0.700, places=3)
        self.assertAlmostEqual(cobre, 2.100, places=3)


class QuandoAPlacaNaoServe(unittest.TestCase):

    def test_campo_vazio_devolve_None(self):
        self.assertIsNone(tr._placa(C75, 0, 0))
        self.assertIsNone(tr._placa(C75, None, None))

    def test_codigo_de_potencia_desconhecido_devolve_None(self):
        self.assertIsNone(tr._placa('nao_existe', 295, 1395))

    def test_total_menor_que_ferro_devolve_None(self):
        """Cadastro invertido nao vira cobre negativo."""
        self.assertIsNone(tr._placa(C75, 1395, 295))

    def test_placa_absurda_nao_substitui(self):
        """Ferro de 50% da nominal e erro de digitacao, nao transformador."""
        self.assertIsNone(tr._placa(C75, 37500, 40000))


class OQueSaiNoArquivo(unittest.TestCase):

    def _texto(self, r=4.15, per_fer=0.0, per_tot=0.0, pot_nom='0'):
        """Duble proprio, e nao importado do `test_transformadores`.

        Teste que depende de ajudante privado de outro arquivo de teste
        quebra quando aquele arquivo muda por motivo alheio — e foi o que
        aconteceu na primeira versao desta classe.
        """
        import numpy as np
        import tempfile

        a = lambda *v: np.array(v, dtype=object)        # noqa: E731

        class Leitor:
            def ler_filtrado(self, camada, chave, valores, colunas=None, **kw):
                return {'COD_ID': a('TX'), 'PAC_1': a('BMT'), 'PAC_2': a('BBT'),
                        'CTMT': a('F1'), 'POT_NOM': np.array([75.0]),
                        'TEN_LIN_SE': np.array([0.24]),
                        'FAS_CON_P': a('ABC'), 'FAS_CON_S': a('ABCN')}

            def ler(self, camada, colunas=None, **kw):
                return {'UNI_TR_MT': a('TX'), 'R': np.array([r]),
                        'XHL': np.array([3.2]), 'POT_NOM': a(pot_nom),
                        'PER_FER': np.array([per_fer]),
                        'PER_TOT': np.array([per_tot])}

        tmp = tempfile.mkdtemp()
        cam = os.path.join(tmp, 'Trafos.dss')
        tr.gerar(Leitor(), ['F1'], cam, os.path.join(tmp, 'Aterr.dss'),
                 kv_mt=13.8)
        with open(cam, encoding='utf-8') as fh:
            return fh.read()

    def test_com_placa_o_ferro_sai_e_o_cobre_vem_dela(self):
        t = self._texto(r=4.15, per_fer=295, per_tot=1395, pot_nom=C75)
        self.assertIn('%noloadloss=0.3933', t)
        # cobre 1,4667 dividido em dois enrolamentos = 0,733 cada (achado 26)
        pcts = [float(l.split('%R=')[1].split()[0])
                for l in t.splitlines() if '%R=' in l]
        self.assertEqual(len(pcts), 2)
        for p in pcts:
            self.assertAlmostEqual(p, 1.4667 / 2, places=2)
        self.assertNotIn('%R=2.075', t,
                         'o R=4,15 nao pode mais mandar quando ha placa')

    def test_sem_placa_o_comportamento_antigo_fica_intacto(self):
        """Achado 26 continua valendo onde a placa nao existe."""
        t = self._texto(r=4.15)
        pcts = [float(l.split('%R=')[1].split()[0])
                for l in t.splitlines() if '%R=' in l]
        self.assertEqual(pcts, [2.075, 2.075], 'metade de 4,15 em cada')
        self.assertIn('%noloadloss=0.0000', t,
                      'sem placa o ferro e zero, e isso tem de aparecer '
                      'escrito em vez de simplesmente faltar')

    def test_o_arquivo_diz_quantos_usaram_a_placa(self):
        """Quem auditar precisa saber se aquela subestacao teve placa."""
        t = self._texto(r=4.15, per_fer=295, per_tot=1395, pot_nom=C75)
        self.assertIn('com as perdas da PLACA', t)
        self.assertIn('1 de 1 transformadores', t)


if __name__ == '__main__':
    unittest.main()
