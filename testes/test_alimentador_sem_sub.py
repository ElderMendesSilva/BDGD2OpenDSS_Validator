# -*- coding: utf-8 -*-
"""Base sem subestação não é conversão vazia, é conversão falha — achado 65.

O conversor gera **por subestação**: agrupa os alimentadores por `CTMT.SUB` e
percorre os grupos. Alimentador com `SUB` vazio não entra em grupo nenhum e
saía da rodada sem uma linha de log.

Medido na V34: em **17 das 99 bases** — cooperativas e permissionárias, que
compram energia num ponto de conexão e não têm subestação própria — *todos* os
alimentadores são assim. São **113 alimentadores e 180.615 UCs** (a DCELT87
sozinha tem 43.000). A base inteira virava um `MASTER-AT.dss` sem carga, o
`energia.py` dizia "nenhum MASTER", e o `validador.py` fechava com **"1 de 1
modelos sem ressalva"**. Contadas como convertidas, portanto.

O conversor não inventa a subestação que a base não tem. O que ele passa a
fazer é recusar-se a calar: conta os órfãos no log, grava o número no
`relatorio_rede.json`, e sai com código 2 quando havia alimentadores e nada
foi gerado — para que o ciclo pare antes de validar o vazio.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CAMINHO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'etapas', 'converter.py')


class TestOGuarda(unittest.TestCase):
    """Só o fonte: o efeito exige uma `.gdb` com CTMT.SUB vazio, que é
    exatamente a fixture que ainda não existe (item 1 do plano)."""

    def setUp(self):
        self.fonte = io.open(CAMINHO, encoding='utf-8').read()

    def test_os_orfaos_sao_contados(self):
        self.assertRegex(
            self.fonte,
            r"else:\s*\n\s*orfaos\.append\(cod\)",
            'o alimentador sem SUB voltou a ser descartado em silencio')

    def test_o_log_diz_quantos_ficaram_de_fora(self):
        self.assertIn('ACHADO 65:', self.fonte)
        self.assertIn('sem CTMT.SUB', self.fonte)

    def test_o_relatorio_grava_o_numero(self):
        self.assertIn("'alimentadores_sem_sub': len(orfaos),", self.fonte,
                      'o relatorio_rede.json precisa registrar os orfaos')

    def test_sai_com_erro_quando_nada_foi_gerado(self):
        self.assertRegex(
            self.fonte,
            r"if not resumo and not prontas and ctmt_info:(?:.|\n)*?sys\.exit\(2\)",
            'a base sem subestacao alguma tem de falhar, nao seguir o ciclo')

    def test_a_falha_vem_depois_da_retomada(self):
        """Retomada legítima tem `prontas` cheio e `resumo` vazio — não pode
        cair aqui."""
        self.assertIn('not prontas', self.fonte)

    def test_base_realmente_vazia_nao_falha(self):
        """`.gdb` sem alimentador nenhum não é o caso do achado 65."""
        self.assertIn('and ctmt_info:', self.fonte)


if __name__ == '__main__':
    unittest.main()
