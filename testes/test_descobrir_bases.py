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
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
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
        """Uma tupla com nome de arquivo aqui e o defeito voltando.

        Ate 23/08/2026 este teste tinha UMA excecao: o nome completo da .gdb
        da Enel SP, que mora fora da pasta nesta maquina e era resgatada pelo
        nome. A excecao caiu quando `BDGD2DSS_BASES` passou a aceitar VARIAS
        pastas — quem tem base em mais de um lugar diz onde, e nenhum nome de
        arquivo precisa existir no codigo.

        Sem excecao nenhuma, de proposito: o carimbo de exportacao muda a cada
        safra, entao nome de arquivo escrito aqui deixa de funcionar sozinho e
        em silencio no ano que vem.
        """
        with open(os.path.join(RAIZ, 'regerar_v10.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertNotIn('_2024-12-31_V11_2025', fonte,
                         'voltou nome de .gdb para dentro do codigo')

    def test_a_pasta_das_bases_e_uma_lista(self):
        """Base em mais de um lugar e o caso normal, e nao a excecao."""
        self.assertIsInstance(rg.PASTAS_BDGD, list)
        self.assertTrue(rg.PASTAS_BDGD)

    def test_a_variavel_de_ambiente_aceita_varias_pastas(self):
        import importlib
        sep = os.pathsep
        antes = os.environ.get('BDGD2DSS_BASES')
        try:
            os.environ['BDGD2DSS_BASES'] = f'/um{sep}/dois{sep}/tres'
            importlib.reload(rg)
            self.assertEqual(rg.PASTAS_BDGD, ['/um', '/dois', '/tres'])
        finally:
            if antes is None:
                os.environ.pop('BDGD2DSS_BASES', None)
            else:
                os.environ['BDGD2DSS_BASES'] = antes
            importlib.reload(rg)

    def test_pasta_inexistente_na_lista_nao_quebra(self):
        """Cada maquina tem as suas; a que nao existe e ignorada."""
        import importlib
        antes = os.environ.get('BDGD2DSS_BASES')
        try:
            vazia = tempfile.mkdtemp(prefix='sem_bases_')
            os.environ['BDGD2DSS_BASES'] = os.pathsep.join(
                ['/nao_existe_de_jeito_nenhum', vazia])
            importlib.reload(rg)
            self.assertEqual(rg.descobrir(), [])
        finally:
            if antes is None:
                os.environ.pop('BDGD2DSS_BASES', None)
            else:
                os.environ['BDGD2DSS_BASES'] = antes
            importlib.reload(rg)


class DuasSafrasNaMesmaPastaSaoDESAMBIGUADAS(unittest.TestCase):
    """`Sulgipe_46_2024-12-31` e `Sulgipe_46_2025-12-31` viram a MESMA tag.

    E isso e CORRETO: `_sigla` ignora data, versao e carimbo de proposito, e e
    o que permite comparar SULGIPE46 entre safras. O efeito colateral e que as
    duas gravariam em `MODELOS_SULGIPE46_<sufixo>` — a rodada misturaria 2024
    e 2025 sem erro nenhum.

    ATE 02/09/2026 ISTO ERA RECUSADO, e a rodada travava. Defensavel em lote,
    errado quando a pessoa aponta uma `.gdb` especifica e a irma dela por acaso
    mora na mesma pasta: transferia ao usuario um trabalho que o codigo sabe
    fazer.

    Agora a tag ganha a safra SO nas bases que colidem. `MODELOS_RR_2025_V27`
    diz de que safra saiu, e a base que nao colide mantem a tag de sempre —
    que e o que preserva a comparacao com todas as rodadas anteriores.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_as_duas_safras_ganham_a_data_na_tag(self):
        _gdb(self.dir, 'Sulgipe_46_2024-12-31_V11_a.gdb')
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_b.gdb')
        tags = sorted(t for t, _, _ in rg.descobrir(self.dir))
        self.assertEqual(tags, ['SULGIPE46_2024', 'SULGIPE46_2025'])

    def test_quem_NAO_colide_mantem_a_tag_de_sempre(self):
        """O contraste que da sentido a tudo: desambiguar a base errada
        quebraria a comparacao com as rodadas anteriores."""
        _gdb(self.dir, 'Sulgipe_46_2024-12-31_V11_a.gdb')
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_b.gdb')
        _gdb(self.dir, 'Cedrap_5381_2025-12-31_V11_c.gdb')
        tags = sorted(t for t, _, _ in rg.descobrir(self.dir))
        self.assertIn('CEDRAP5381', tags, 'a base unica nao pode mudar de nome')

    def test_base_CONHECIDA_tambem_e_desambiguada(self):
        """A Cemig cai no APELIDO e nao no ramo das novas — outro caminho, que
        uma correcao posta so num dos dois deixaria passar."""
        _gdb(self.dir, 'Cemig-D_4950_2024-12-31_V11_a.gdb')
        _gdb(self.dir, 'Cemig-D_4950_2025-12-31_V11_b.gdb')
        tags = sorted(t for t, _, _ in rg.descobrir(self.dir))
        self.assertEqual(tags, ['CMIG_2024', 'CMIG_2025'])

    def test_as_pastas_de_modelo_ficam_DIFERENTES(self):
        """O ponto todo: sem isso as duas gravariam uma por cima da outra."""
        _gdb(self.dir, 'Sulgipe_46_2024-12-31_V11_a.gdb')
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_b.gdb')
        pastas = {rg.saida_de(t) for t, _, _ in rg.descobrir(self.dir)}
        self.assertEqual(len(pastas), 2, 'as duas safras colidiriam no disco')

    def test_MESMA_safra_duas_vezes_ainda_e_recusado(self):
        """Duas republicacoes do mesmo periodo nao tem como ser separadas sem
        inventar criterio — e inventar seria escolher por acaso qual das duas
        vira o modelo."""
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_20260830-1351.gdb')
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_20260901-0900.gdb')
        with self.assertRaises(rg.SafrasMisturadas):
            rg.descobrir(self.dir)

    def test_uma_safra_so_continua_passando(self):
        _gdb(self.dir, 'Sulgipe_46_2025-12-31_V11_b.gdb')
        _gdb(self.dir, 'Cedrap_5381_2025-12-31_V11_c.gdb')
        tags = sorted(t for t, _, _ in rg.descobrir(self.dir))
        self.assertEqual(tags, ['CEDRAP5381', 'SULGIPE46'])


if __name__ == '__main__':
    unittest.main()
