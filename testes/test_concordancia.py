# -*- coding: utf-8 -*-
"""Tres medidas de concordancia, e o que cada uma tem de pegar.

O projeto publicava UM numero: a mediana de `modelo/declarado` sobre a amostra
que sobra depois de descartar declaracao abaixo de 0,5%. Medido na V17, esse
numero se move com o corte tanto quanto com o modelo — a Light vai de 1,38x a
0,26x, atravessando o 1,0, e a Cemig-D nao sai de 0,45x.

E o filtro era assimetrico: peneirava a DECLARACAO implausivel e deixava passar
MODELO implausivel. Oito alimentadores da CPFL com perda modelada de ate
11.224% carregavam 86,4% da perda da base inteira, e a mediana nao os via.

Estes testes trancam as tres:
  1. a sensibilidade tem de MOSTRAR o movimento, e nao suaviza-lo;
  2. o agregado nao pode depender de corte, e nao pode ser dominado por
     denominador pequeno;
  3. o aviso de modelo implausivel tem de disparar, e dizer que fatia da perda
     esta em cima do defeito.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import concordancia as cc                 # noqa: E402


def par(m, d, kwh_m=1000.0, kwh_d=365000.0):
    return (m, d, kwh_m, kwh_d)


class ASensibilidade(unittest.TestCase):

    def test_o_corte_muda_a_razao_e_isso_tem_de_aparecer(self):
        """O caso da Light: metade declara abaixo de 0,5%."""
        baixos = [par(1.0, 0.2) for _ in range(50)]     # razao 5,0
        altos = [par(1.0, 2.0) for _ in range(50)]      # razao 0,5
        s = {x['corte']: x['razao'] for x in cc.sensibilidade(baixos + altos)}
        self.assertEqual(s[0.0], 2.75)     # mediana dos dois grupos
        self.assertEqual(s[0.5], 0.5)      # so os altos sobram
        self.assertNotEqual(s[0.0], s[0.5],
                            'a sensibilidade existe para MOSTRAR a diferenca')

    def test_amostra_robusta_nao_se_move(self):
        """O caso da Cemig-D: 0,45x em todo corte."""
        p = [par(1.0, 2.0) for _ in range(50)]
        r = {x['razao'] for x in cc.sensibilidade(p)}
        self.assertEqual(r, {0.5})

    def test_o_n_de_cada_corte_vem_junto(self):
        p = [par(1.0, 0.2)] * 30 + [par(1.0, 2.0)] * 70
        s = {x['corte']: x['n'] for x in cc.sensibilidade(p)}
        self.assertEqual(s[0.0], 100)
        self.assertEqual(s[0.5], 70)

    def test_sem_par_nenhum_devolve_None_e_nao_quebra(self):
        s = cc.sensibilidade([])
        self.assertTrue(all(x['razao'] is None and x['n'] == 0 for x in s))


class OAgregado(unittest.TestCase):

    def test_nao_e_dominado_por_denominador_pequeno(self):
        """Um alimentador minusculo que declara quase zero domina a mediana
        de razoes e nao pode dominar o agregado."""
        grandes = [par(2.0, 2.0, kwh_m=1e6, kwh_d=3.65e8) for _ in range(10)]
        anao = [par(2.0, 0.001, kwh_m=1.0, kwh_d=365.0)]
        self.assertAlmostEqual(cc.agregado(grandes + anao)['razao'],
                               1.0, places=2)

    def test_le_a_perda_dos_dois_lados_em_percentual(self):
        a = cc.agregado([par(4.0, 2.0, kwh_m=1000.0, kwh_d=1000.0)])
        self.assertAlmostEqual(a['pct_modelo'], 4.0)
        self.assertAlmostEqual(a['pct_declarado'], 2.0)
        self.assertAlmostEqual(a['razao'], 2.0)

    def test_vazio_devolve_None(self):
        self.assertIsNone(cc.agregado([])['razao'])


class OModeloImplausivel(unittest.TestCase):
    """O que o filtro antigo nao olhava."""

    def test_dispara_e_diz_a_fatia_da_perda(self):
        """O caso da CPFL: poucos alimentadores, quase toda a perda."""
        sadios = [par(2.0, 2.0, kwh_m=1000.0) for _ in range(99)]
        quebrado = [par(11224.0, 3.79, kwh_m=1000.0)]
        i = cc.implausivel(sadios + quebrado)
        self.assertEqual(i['n'], 1)
        self.assertEqual(i['de'], 100)
        self.assertEqual(i['pior_pct'], 11224.0)
        self.assertGreater(i['fatia_da_perda_pct'], 90.0)

    def test_base_limpa_nao_dispara(self):
        """A Equatorial PA: zero alimentadores acima do teto."""
        i = cc.implausivel([par(m, 2.0) for m in (0.5, 1.0, 5.0, 16.0)])
        self.assertEqual(i['n'], 0)
        self.assertEqual(i['pior_pct'], 16.0)

    def test_o_teto_e_configuravel_e_nao_e_magico(self):
        p = [par(25.0, 2.0)]
        self.assertEqual(cc.implausivel(p, teto=20.0)['n'], 1)
        self.assertEqual(cc.implausivel(p, teto=30.0)['n'], 0)


class ORodape(unittest.TestCase):

    def test_traz_as_tres_e_avisa_do_modelo_quebrado(self):
        p = [par(2.0, 2.0) for _ in range(99)] + [par(11224.0, 3.79)]
        t = '\n'.join(cc.linhas(p))
        self.assertIn('razao por corte', t)
        self.assertIn('AGREGADA', t)
        self.assertIn('ATENCAO', t)
        self.assertIn('11,224%', t)

    def test_base_limpa_nao_traz_o_aviso(self):
        p = [par(2.0, 2.0) for _ in range(50)]
        t = '\n'.join(cc.linhas(p))
        self.assertNotIn('ATENCAO', t)


class QuemUsa(unittest.TestCase):

    def test_valida_perdas_publica_as_tres(self):
        """Exige o USO, e nao a palavra.

        A primeira versao deste teste procurava a string `concordancia` no
        arquivo — e passou antes de o modulo estar ligado, porque a palavra ja
        aparecia em tres comentarios desde 2026. Teste que passa sem o codigo
        existir e pior que teste nenhum: ele da tranquilidade falsa.
        """
        import ast
        with open(os.path.join(RAIZ, 'valida_perdas.py'), encoding='utf-8') as fh:
            arvore = ast.parse(fh.read().lstrip('﻿'))
        importado = any(
            isinstance(n, ast.ImportFrom)
            and any(a.name == 'concordancia' for a in n.names)
            for n in ast.walk(arvore))
        self.assertTrue(importado,
                        'valida_perdas nao importa bdgd2dss.concordancia')
        chamadas = {n.func.attr for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'concordancia'}
        self.assertTrue(
            chamadas & {'linhas', 'sensibilidade', 'agregado', 'implausivel'},
            'valida_perdas importa o modulo e nao chama nada dele — '
            'continua publicando um numero so')


if __name__ == '__main__':
    unittest.main()
