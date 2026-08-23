# -*- coding: utf-8 -*-
"""A perda do modelo contra uma ancora de FORA da BDGD.

Ate aqui o projeto validava a perda contra o `PERD_A4` da CTMT — que sai do
MESMO arquivo que o modelo le. Isso e autoconsistencia: um conversor que
lesse a BDGD errado dos dois lados passaria. O criterio 11 do PLANO_V1 estava
em 0% por isso, e era o unico zerado que nao dependia de terceiros.

A REFERENCIA. ANEEL SGT/STR, "Perdas de Energia Eletrica na Distribuicao
2025/2024": 14,0% de perda total sobre a energia injetada em 2024, sendo
7,4% (44,6 TWh) tecnica e 6,6% (40,2 TWh) nao tecnica. A safra bate com a
das sete bases — BDGD V11, 2024-12-31.

O TESTE E DE UM LADO SO, E ISSO E O PONTO. Os 7,4% cobrem a distribuicao
INTEIRA: alta, media, baixa e transformadores. O nosso modelo com
`--bt agregado` nao tem a rede de BT, entao ele TEM de ficar abaixo. Acima e
impossivel e vira reprovacao; abaixo e esperado e NAO vira aprovacao, porque
cravar um piso exigiria a decomposicao por segmento que o relatorio nao
publica.

MEDIDO NA V18: Roraima 9,83% e CPFL 8,75% REPROVAM — modelam mais perda em
media tensao do que o Brasil inteiro perde em toda a distribuicao.

O QUE ESTES TESTES TRANCAM

1. O SENTIDO DO TESTE. Inverter o lado transformaria "modelo bom" em
   "modelo reprovado" para as cinco bases que estao certas.

2. A FONTE VIAJA JUNTO. Numero de referencia sem citacao no arquivo e
   numero que ninguem consegue conferir daqui a um ano.

3. SEM O CSV, O RELATORIO DIZ QUE ESTA SEM. Cair calado na media nacional
   faria a comparacao parecer mais forte do que e.

4. O CODIGO DO AGENTE MANDA, quando existe. O nome muda com incorporacao;
   o codigo ANEEL da `BASE.DIST` nao.
"""
import ast
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import referencia as ref                    # noqa: E402


class OSentidoDoTeste(unittest.TestCase):

    def test_acima_do_sistema_inteiro_reprova(self):
        """Roraima na V18: 9,83% em MT contra 7,4% da distribuicao inteira."""
        c = ref.comparar(9.83, tabela={})
        self.assertTrue(c['reprova'])
        self.assertAlmostEqual(c['razao'], 1.328, places=3)

    def test_a_cpfl_da_v18_tambem_reprova(self):
        self.assertTrue(ref.comparar(8.75, tabela={})['reprova'])

    def test_abaixo_nao_reprova_e_tambem_nao_aprova(self):
        """Sem a decomposicao por segmento do Modulo 7 nao ha piso."""
        c = ref.comparar(0.88, tabela={})
        self.assertFalse(c['reprova'])
        self.assertNotIn('aprova', str(c).lower())

    def test_o_limite_e_exatamente_74(self):
        self.assertFalse(ref.comparar(7.4, tabela={})['reprova'])
        self.assertTrue(ref.comparar(7.41, tabela={})['reprova'])

    def test_sem_perda_agregada_nao_quebra_nem_reprova(self):
        c = ref.comparar(None, tabela={})
        self.assertFalse(c['reprova'])
        self.assertIsNone(c['razao'])


class AFonteViajaJunto(unittest.TestCase):

    def test_o_numero_traz_a_citacao(self):
        f = ref.ANEEL_2024['fonte']
        self.assertIn('ANEEL', f)
        self.assertIn('2025/2024', f)
        self.assertIn('Figura', f)

    def test_o_rodape_imprime_a_fonte(self):
        t = '\n'.join(ref.linhas(ref.comparar(9.83, tabela={})))
        self.assertIn('ANEEL', t)
        self.assertIn('Figura 3', t)

    def test_as_parcelas_fecham_com_o_total(self):
        """14,0% = 7,4% tecnica + 6,6% nao tecnica, como o relatorio diz."""
        a = ref.ANEEL_2024
        self.assertAlmostEqual(a['tecnica_pct'] + a['nao_tecnica_pct'],
                               a['total_pct'], places=6)

    def test_a_safra_da_referencia_bate_com_a_das_bases(self):
        self.assertEqual(ref.ANEEL_2024['ano'], 2024,
                         'as sete bases sao V11 de 2024-12-31')


class SemODadoPorDistribuidora(unittest.TestCase):

    def test_csv_ausente_devolve_vazio_e_nao_quebra(self):
        self.assertEqual(ref.por_distribuidora('nao_existe_isto.csv'), {})

    def test_o_relatorio_avisa_que_caiu_na_media_nacional(self):
        t = '\n'.join(ref.linhas(ref.comparar(4.39, tabela={})))
        self.assertIn('MEDIA NACIONAL', t)
        self.assertIn('perdas_aneel.csv', t,
                      'nao diz como sair da media nacional')

    def test_com_o_csv_a_referencia_e_a_da_distribuidora(self):
        d = tempfile.mkdtemp()
        cam = os.path.join(d, 'perdas_aneel.csv')
        with open(cam, 'w', encoding='utf-8', newline='') as fh:
            fh.write('agente,pct\n370,11.2\n63,6,8\n')
        t = ref.por_distribuidora(cam)
        self.assertEqual(t['370'], 11.2)
        c = ref.comparar(9.83, agente='370', tabela=t)
        self.assertFalse(c['reprova'],
                         '9,83% esta abaixo dos 11,2% de Roraima: com o dado '
                         'da propria distribuidora o veredito muda')
        self.assertTrue(c['de_agente'])

    def test_agente_fora_do_csv_cai_na_media_e_avisa(self):
        c = ref.comparar(9.83, agente='999', tabela={'370': 11.2})
        self.assertFalse(c['de_agente'])
        self.assertEqual(c['referencia_pct'], ref.TETO)

    def test_a_virgula_decimal_do_csv_brasileiro_e_lida(self):
        d = tempfile.mkdtemp()
        cam = os.path.join(d, 'p.csv')
        with open(cam, 'w', encoding='utf-8', newline='') as fh:
            fh.write('agente;pct\n')
        with open(cam, 'a', encoding='utf-8', newline='') as fh:
            fh.write('')
        cam2 = os.path.join(d, 'q.csv')
        with open(cam2, 'w', encoding='utf-8', newline='') as fh:
            fh.write('agente,pct\n370,"9,4"\n')
        self.assertEqual(ref.por_distribuidora(cam2)['370'], 9.4)


class QuemUsa(unittest.TestCase):
    """Exige o USO, e nao a palavra."""

    def setUp(self):
        with open(os.path.join(RAIZ, 'valida_perdas.py'), encoding='utf-8') as fh:
            self.fonte = fh.read().lstrip('\ufeff')
        self.arvore = ast.parse(self.fonte)

    def test_valida_perdas_chama_a_comparacao(self):
        chamadas = {n.func.attr for n in ast.walk(self.arvore)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'referencia'}
        self.assertIn('comparar', chamadas)
        self.assertIn('linhas', chamadas)

    def test_o_json_leva_a_comparacao_externa(self):
        self.assertIn("'referencia_externa': ext", self.fonte)

    def test_a_comparacao_usa_o_agregado_e_nao_a_mediana(self):
        """A mediana de razoes nao e uma perda: nao da para comparar com %."""
        i = self.fonte.index('referencia.comparar(')
        self.assertIn('pct_modelo', self.fonte[i:i + 120])


if __name__ == '__main__':
    unittest.main()
