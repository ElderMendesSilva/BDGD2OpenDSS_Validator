# -*- coding: utf-8 -*-
"""As bases sao descobertas na pasta, e nao listadas no codigo.

Ate 21/08/2026 o `regerar_v10` tinha sete tuplas com o nome exato de cada
`.gdb`. Rodar a Coelba exigia editar Python; rodar as 53 do pais exigia
escrever 53 linhas a mao — e errar uma delas as 3 da manha, depois que o job
ja tinha esperado a noite na fila.

O QUE NAO PODE SE PERDER NA TROCA, e e o que estes testes trancam:

1. A SIGLA CURTA DAS SETE. Trocar `RR` por `RORAIMA` renomearia
   `MODELOS_RR_V18` e quebraria a comparacao com todas as rodadas anteriores —
   e comparar geracoes e o unico jeito que o projeto tem de saber se uma
   mudanca melhorou ou piorou.

2. A ORDEM. O canario vem primeiro de proposito: Roraima converte em 1,9 min,
   entao codigo quebrado aparece em dois minutos e nao depois de 148 min de
   Cemig-D.

3. BASE NOVA NAO PODE QUEBRAR NADA. Ela entra com sigla derivada do nome e do
   codigo do agente, e vai para o fim, ordenada por tamanho — que e o melhor
   palpite de custo que existe sem ter rodado.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
import regerar_v10 as rg                                 # noqa: E402


def _gdb(base, nome, tamanho=1000):
    """Uma .gdb de mentira: pasta com um arquivo dentro, como a de verdade."""
    d = os.path.join(base, nome)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'a00000001.gdbtable'), 'wb') as fh:
        fh.write(b'x' * tamanho)
    return d


class ASiglaDasConhecidas(unittest.TestCase):
    """Sem isso, a proxima rodada nao compara com nenhuma anterior."""

    def test_as_sete_mantem_a_sigla_e_os_minutos(self):
        esperado = {
            'Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb': ('RR', 1.9),
            'Enel_CE_39_2024-12-31_V11_20250822-1151.gdb': ('ENCE', 21.6),
            'Equatorial_PA_371_2024-12-31_V11_20250911-0946.gdb': ('EQPA', 40.1),
            'Enel_SP_390_2024-12-31_V11_20250702-2009.gdb': ('SP', 48.2),
            'Light_382_2024-12-31_V11_20250925-1811.gdb': ('LT', 52.9),
            'CPFL_Paulista_63_2024-12-31_V11_20250731-1036.gdb': ('CPFL', 85.3),
            'Cemig-D_4950_2024-12-31_V11_20250929-1522.gdb': ('CMIG', 148.4),
        }
        for arq, alvo in esperado.items():
            self.assertEqual(rg._sigla(os.path.join('qualquer', 'pasta', arq)),
                             alvo, arq)

    def test_a_sigla_nao_depende_da_pasta(self):
        a = rg._sigla('/tmp/Light_382_2024-12-31_V11_20250925-1811.gdb')
        b = rg._sigla(r'D:\outro\Light_382_2024-12-31_V11_20250925-1811.gdb')
        self.assertEqual(a, b)

    def test_a_safra_nova_da_mesma_base_mantem_a_sigla(self):
        """Criterio 12: a safra seguinte tem outro carimbo no nome."""
        self.assertEqual(
            rg._sigla('Light_382_2025-12-31_V12_20261001-0900.gdb'),
            ('LT', 52.9))


class ABaseNova(unittest.TestCase):

    def test_ganha_sigla_do_nome_e_do_codigo_do_agente(self):
        """O codigo do agente e o unico identificador estavel: o nome muda com
        incorporacao e o carimbo muda a cada safra."""
        tag, minutos = rg._sigla('Coelba_5161_2024-12-31_V11_20250801-1000.gdb')
        self.assertEqual(tag, 'COELBA5161')
        self.assertIsNone(minutos, 'base nunca rodada nao tem tempo medido')

    def test_nome_fora_do_padrao_nao_quebra(self):
        tag, minutos = rg._sigla('qualquer_coisa.gdb')
        self.assertTrue(tag)
        self.assertIsNone(minutos)


class ADescoberta(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='bases_')

    def test_acha_o_que_esta_na_pasta(self):
        _gdb(self.dir, 'Light_382_2024-12-31_V11_20250925-1811.gdb')
        _gdb(self.dir, 'Coelba_5161_2024-12-31_V11_20250801-1000.gdb')
        tags = [t for t, _, _ in rg.descobrir(self.dir)]
        self.assertIn('LT', tags)
        self.assertIn('COELBA5161', tags)

    def test_o_canario_vem_primeiro(self):
        _gdb(self.dir, 'Cemig-D_4950_2024-12-31_V11_20250929-1522.gdb')
        _gdb(self.dir, 'Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb')
        tags = [t for t, _, _ in rg.descobrir(self.dir)]
        self.assertEqual(tags[0], 'RR',
                         'a menor base tem de vir primeiro: codigo quebrado '
                         'aparece em 2 min e nao depois de 148')

    def test_as_novas_vao_depois_das_conhecidas(self):
        _gdb(self.dir, 'Coelba_5161_2024-12-31_V11_20250801-1000.gdb')
        _gdb(self.dir, 'Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb')
        tags = [t for t, _, _ in rg.descobrir(self.dir)]
        self.assertLess(tags.index('RR'), tags.index('COELBA5161'))

    def test_as_novas_saem_da_menor_para_a_maior(self):
        _gdb(self.dir, 'Grande_9001_2024-12-31_V11_20250801-1000.gdb', 9000)
        _gdb(self.dir, 'Pequena_9002_2024-12-31_V11_20250801-1000.gdb', 10)
        tags = [t for t, _, _ in rg.descobrir(self.dir)]
        self.assertLess(tags.index('PEQUENA9002'), tags.index('GRANDE9001'))

    def test_pasta_vazia_devolve_lista_vazia_e_nao_quebra(self):
        self.assertEqual(rg.descobrir(self.dir), [])


class OQueNaoPodeVoltar(unittest.TestCase):

    def test_nao_ha_lista_de_gdb_no_codigo(self):
        """Uma tupla com nome de arquivo aqui e o defeito voltando."""
        with open(os.path.join(RAIZ, 'regerar_v10.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertNotIn("_2024-12-31_V11_2025", fonte.replace(
            "'Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'", ''),
            'voltou nome de .gdb para dentro do codigo')


if __name__ == '__main__':
    unittest.main()
