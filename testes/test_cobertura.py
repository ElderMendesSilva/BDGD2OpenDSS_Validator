# -*- coding: utf-8 -*-
"""Carga energizada em kW, e nao so em contagem.

A ferramenta reportava "carga energizada" contando cargas, o que trata uma
padaria e uma fabrica como um. Medido nas 119 subestacoes da Equatorial PA da
V16, sobre exatamente o mesmo modelo: 81,1% por contagem e 66,5% em kW, porque
a carga que fica no escuro e 1,77x maior que a media. A diferenca nao e
detalhe — e a diferenca entre uma base que parece boa e uma que deixa um terco
da potencia fora.

O que estes testes trancam:

1. as duas medidas discordam quando a carga morta e maior que a media, e a de
   kW e a menor. Um agregador que devolvesse o mesmo numero nos dois casos
   estaria apagando o achado;
2. base antiga, sem `kW_nominal`, devolve None e nao zero. Nao medir nao e
   medir zero, e um zero aqui viraria "0% energizada" numa tabela;
3. subestacao com erro nao entra na conta.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import cobertura                          # noqa: E402


def se(cargas, mortas, kw_nom, kw_morto, **extra):
    d = {'se': 'X', 'cargas': cargas, 'mortas_depois': mortas,
         'kW_nominal': kw_nom, 'kW_morto': kw_morto}
    d.update(extra)
    return d


class AsDuasMedidas(unittest.TestCase):

    def test_carga_morta_grande_faz_o_kW_cair_mais_que_a_contagem(self):
        """A EQPA da V16, com os numeros dela: 18,9% das cargas, 33,5% do kW."""
        c = cobertura.energizada([se(389688, 73634, 1134000.0, 380000.0)])
        self.assertEqual(c['cont_pct'], 81.1)
        self.assertEqual(c['kW_pct'], 66.5)
        self.assertLess(c['kW_pct'], c['cont_pct'],
                        'carga morta acima da media tem de derrubar o kW '
                        'mais do que a contagem')

    def test_carga_morta_do_tamanho_medio_da_as_duas_iguais(self):
        c = cobertura.energizada([se(1000, 100, 1000.0, 100.0)])
        self.assertEqual(c['cont_pct'], 90.0)
        self.assertEqual(c['kW_pct'], 90.0)

    def test_carga_morta_pequena_faz_o_kW_cair_menos(self):
        """O sentido contrario tambem tem de aparecer, e nao ser mascarado."""
        c = cobertura.energizada([se(1000, 300, 1000.0, 50.0)])
        self.assertEqual(c['cont_pct'], 70.0)
        self.assertEqual(c['kW_pct'], 95.0)
        self.assertGreater(c['kW_pct'], c['cont_pct'])

    def test_soma_varias_subestacoes(self):
        c = cobertura.energizada([se(600, 100, 800.0, 300.0),
                                  se(400, 100, 200.0, 100.0)])
        self.assertEqual(c['cargas'], 1000)
        self.assertEqual(c['mortas'], 200)
        self.assertEqual(c['cont_pct'], 80.0)
        self.assertEqual(c['kW_pct'], 60.0)      # 600 de 1000 kW
        self.assertEqual(c['MW_nominal'], 1.0)


class OQueNaoFoiMedido(unittest.TestCase):

    def test_base_sem_kW_devolve_None_e_nao_zero(self):
        """Modelo gerado antes desta medida existir.

        Zero aqui viraria "0% energizada" numa tabela, que e pior do que nao
        ter numero: um leitor acredita.
        """
        c = cobertura.energizada([{'se': 'X', 'cargas': 100,
                                   'mortas_depois': 10}])
        self.assertIsNone(c['kW_pct'])
        self.assertIsNone(c['MW_nominal'])
        self.assertEqual(c['cont_pct'], 90.0)

    def test_sem_subestacao_nenhuma_nao_quebra(self):
        c = cobertura.energizada([])
        self.assertIsNone(c['cont_pct'])
        self.assertIsNone(c['kW_pct'])

    def test_a_linha_avisa_quando_falta_o_kW(self):
        l = cobertura.linha(cobertura.energizada(
            [{'se': 'X', 'cargas': 100, 'mortas_depois': 10}]))
        self.assertIn('sem kW nesta base', l)

    def test_a_linha_traz_as_duas_e_o_kW_na_frente(self):
        l = cobertura.linha(cobertura.energizada([se(1000, 189, 1000.0,
                                                     384.0)]))
        self.assertLess(l.index('em kW'), l.index('em contagem'),
                        'a medida de kW e a que vale, e vem primeiro')
        self.assertIn('61.6', l)
        self.assertIn('81.1', l)

    def test_linha_vazia_quando_nao_ha_o_que_dizer(self):
        self.assertEqual(cobertura.linha(cobertura.energizada([])), '')


class QuemUsa(unittest.TestCase):
    """Os dois chamadores tem de usar o MESMO agregador.

    Duas contas para o mesmo numero divergem na primeira mudanca, e ai o
    rodape do `ligacao` e a tabela do `regerar` passam a discordar sem que
    ninguem saiba qual esta certo.
    """

    def test_ligacao_e_regerar_chamam_o_modulo(self):
        for script in ('ligacao.py', 'regerar_v10.py'):
            with open(os.path.join(RAIZ, script), encoding='utf-8') as fh:
                fonte = fh.read()
            self.assertIn('cobertura.energizada(', fonte,
                          f'{script} nao usa o agregador comum')

    def test_ligacao_grava_o_kW_por_subestacao(self):
        """Sem `kW_nominal` no JSON, o agregador nao tem o que somar."""
        with open(os.path.join(RAIZ, 'ligacao.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        for campo in ("'kW_nominal'", "'kW_morto'"):
            self.assertIn(campo, fonte, f'ligacao.py nao grava {campo}')


if __name__ == '__main__':
    unittest.main()
