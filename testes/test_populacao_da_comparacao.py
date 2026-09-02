# -*- coding: utf-8 -*-
"""De quantos alimentadores a comparacao de perdas fala, e de quantos ela cala.

A V18 publicou "27 de 1.467" para a CPFL. A CPFL tem 1.636 alimentadores no
modelo: 169 nunca entraram na conta, e nenhum arquivo dizia isso. Quem le
"27 de 1.467" entende "de todos", e nao e.

MEDIDO NA V18, as sete bases:

    base    no modelo   comparados   fora   sem decl   sem energia   ambos
    RR             89           63     26         17             2       7
    ENCE          728          685     43          1             2      40
    EQPA          688          612     76         16            37      23
    LT          1.647        1.488    159         17            59      83
    CPFL        1.636        1.467    169         19            64      86
    CMIG        2.397        1.783    614         44           233     337
    SP          1.806        1.535    271         40             3     228

    total       8.991        7.633  1.358        154           400     804

Sao 15,1% do pais fora da conta. A Cemig-D perde 25,6% dela mesma.

O QUE ESTES TESTES TRANCAM

1. OS TRES BALDES SAO SEPARADOS, e nao um `fora` so. Sem PERD_* na CTMT nao
   ha contra o que comparar e a culpa nao e do modelo. DECLARADO e sem
   energia no modelo e rede morta — falha nossa, e o unico balde que o
   projeto pode diminuir sozinho.

2. A CONTA TEM DE FECHAR. `comparados + fora == no_modelo`. Um quarto
   caminho de descarte que ninguem contasse voltaria a esconder o problema
   exatamente como antes.

3. O AVISO DISPARA quando ha declarado-e-morto, e some quando nao ha.

4. NADA QUEBRA SEM A POPULACAO. `linhas()` continua funcionando para quem
   nao passa `pop`.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import concordancia as cc                  # noqa: E402


def par(m, d, kwh_m=1000.0, kwh_d=365000.0):
    return (m, d, kwh_m, kwh_d)


class OsTresBaldes(unittest.TestCase):

    def test_a_cpfl_da_v18_sai_com_os_numeros_medidos(self):
        p = cc.populacao(1636, 1467, 19, 64, 86)
        self.assertEqual(p['fora'], 169)
        self.assertTrue(p['fecha'])
        self.assertAlmostEqual(p['cobertura_pct'], 89.67, places=2)

    def test_o_balde_que_e_falha_nossa_sai_isolado(self):
        """Dos tres, so o `sem_energia` o projeto pode diminuir sozinho."""
        p = cc.populacao(2397, 1783, 44, 233, 337)
        self.assertEqual(p['sem_energia_no_modelo'], 233)
        self.assertAlmostEqual(p['declarado_e_morto_pct'], 9.72, places=2)

    def test_a_conta_tem_de_fechar(self):
        self.assertTrue(cc.populacao(100, 90, 4, 3, 3)['fecha'])
        self.assertFalse(cc.populacao(100, 90, 1, 1, 1)['fecha'],
                         'sobrou alimentador saindo por um caminho nao contado '
                         'e o dicionario nao acusou')

    def test_base_vazia_nao_divide_por_zero(self):
        p = cc.populacao(0, 0, 0, 0, 0)
        self.assertIsNone(p['cobertura_pct'])
        self.assertIsNone(p['declarado_e_morto_pct'])


class ORodape(unittest.TestCase):

    def setUp(self):
        self.pares = [par(2.0, 2.0) for _ in range(50)]

    def test_publica_a_cobertura_e_avisa_do_declarado_morto(self):
        t = '\n'.join(cc.linhas(self.pares,
                                pop=cc.populacao(1636, 1467, 19, 64, 86)))
        self.assertIn('1,467 de 1,636', t)
        self.assertIn('89.7%', t)
        self.assertIn('64 alimentador(es)', t)
        self.assertIn('ATENCAO', t)

    def test_sem_declarado_morto_nao_ha_aviso(self):
        t = '\n'.join(cc.linhas(self.pares,
                                pop=cc.populacao(100, 90, 10, 0, 0)))
        self.assertIn('populacao:', t)
        self.assertNotIn('ATENCAO', t)

    def test_baldes_que_nao_fecham_viram_aviso(self):
        t = '\n'.join(cc.linhas(self.pares,
                                pop=cc.populacao(100, 90, 1, 0, 1)))
        self.assertIn('nao fecham', t)

    def test_sem_populacao_o_rodape_sai_como_antes(self):
        """Chamador antigo nao pode quebrar."""
        t = '\n'.join(cc.linhas(self.pares))
        self.assertIn('razao por corte', t)
        self.assertNotIn('populacao:', t)


class QuemUsa(unittest.TestCase):
    """Exige o USO, e nao a palavra — a licao do `test_valida_perdas`."""

    def setUp(self):
        with open(os.path.join(RAIZ, 'etapas', 'valida_perdas.py'), encoding='utf-8') as fh:
            self.arvore = ast.parse(fh.read().lstrip('\ufeff'))
            fh.seek(0)

    def test_valida_perdas_chama_populacao(self):
        chamadas = {n.func.attr for n in ast.walk(self.arvore)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'concordancia'}
        self.assertIn('populacao', chamadas)

    def test_o_json_leva_a_populacao_e_a_lista_nomeada(self):
        fonte = open(os.path.join(RAIZ, 'etapas', 'valida_perdas.py'),
                     encoding='utf-8').read()
        self.assertIn("'populacao': pop", fonte)
        self.assertIn("'declarados_e_mortos': declarados_e_mortos", fonte,
                      'contar sem nomear nao deixa ninguem ir olhar')

    def test_a_lista_nao_tem_teto_silencioso(self):
        """Cortar em top-N faria 5.000 problemas parecerem 20."""
        fonte = open(os.path.join(RAIZ, 'etapas', 'valida_perdas.py'),
                     encoding='utf-8').read()
        i = fonte.index("'declarados_e_mortos'")
        self.assertNotIn('[:', fonte[i:i + 120],
                         'a lista saiu truncada sem dizer que truncou')


if __name__ == '__main__':
    unittest.main()
