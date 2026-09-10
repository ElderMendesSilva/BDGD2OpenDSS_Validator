# -*- coding: utf-8 -*-
"""A retomada tem de gritar, e cada entrada tem de dizer de qual commit veio.

O QUE CUSTOU. Em 09/09/2026, medindo a MOG02 no cluster depois de corrigir o
achado 63, o `energia.py` reaproveitou a medida antiga com uma linha discreta —
"1 subestacoes ja medidas — retomando". Li o `tail` sem vê-la, comparei
**72,265%** (modelo velho) com **14,58%** (modelo novo) e concluí que as duas
máquinas discordavam, chegando a escrever que a garantia de determinismo do
CHANGELOG estava quebrada. Com `--refazer`, as duas davam 333.740,7 kWh.

O erro não foi do cache — retomar é sempre melhor do que recomeçar, e uma
queda no meio da noite não pode custar a noite inteira. O erro foi de o cache
não dizer **de quando** era.

Duas coisas mudaram, e este teste trava as duas:

1. o aviso ocupa quatro linhas, nomeia os commits envolvidos e diz que número
   comparado entre gerações não mede mudança de código;
2. cada `resumo.json` e cada item do `energia_dia.json` leva o commit que o
   gerou, e o `_procedencia.json` da rodada passa a listar os commits REAIS da
   pasta — antes ele carimbava tudo com o de quem rodou por último, mentindo
   sobre as subestações antigas.
"""
import io
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss import carimbo                               # noqa: E402


class TestOAviso(unittest.TestCase):

    def setUp(self):
        self._real = carimbo._LEMBRADO
        carimbo._LEMBRADO = 'aaaaaaaaaabbbb'

    def tearDown(self):
        carimbo._LEMBRADO = self._real

    def test_sem_retomada_nao_ha_aviso(self):
        """Rodada limpa não pode ganhar ruído — ruído constante deixa de ser
        lido, que é como a linha antiga morreu."""
        self.assertEqual(carimbo.aviso([], 0), [])

    def test_retomada_do_mesmo_commit_diz_que_e_comparavel(self):
        linhas = carimbo.aviso([{'commit': 'aaaaaaaaaa'}], 1)
        texto = '\n'.join(linhas)
        self.assertIn('RETOMADA', texto)
        self.assertIn('comparavel', texto)
        self.assertNotIn('MISTURADO', texto)

    def test_commit_diferente_e_denunciado_com_os_dois_nomes(self):
        """O caso da MOG02: medida de um código, rodada de outro."""
        texto = '\n'.join(carimbo.aviso(
            [{'commit': '8105ea247c'}, {'commit': 'aaaaaaaaaa'}], 2))
        self.assertIn('MISTURADO', texto)
        self.assertIn('8105ea247c', texto)
        self.assertIn('aaaaaaaaaa', texto)
        self.assertIn('--refazer', texto)

    def test_entrada_sem_carimbo_conta_como_desconhecida(self):
        """Modelo gerado antes deste mecanismo não tem commit — e não pode
        passar por 'do mesmo código'."""
        texto = '\n'.join(carimbo.aviso([{'passos_ok': 96}], 1))
        self.assertIn('MISTURADO', texto)
        self.assertIn('desconhecido', texto)

    def test_o_aviso_diz_quantas_NAO_foram_recalculadas(self):
        texto = '\n'.join(carimbo.aviso([{'commit': 'aaaaaaaaaa'}] * 7, 7))
        self.assertIn('7', texto)
        self.assertIn('NAO foram recalculadas', texto)


class TestAMistura(unittest.TestCase):

    def test_conta_por_commit_do_maior_para_o_menor(self):
        self.assertEqual(
            carimbo.mistura([{'commit': 'a'}, {'commit': 'b'},
                             {'commit': 'a'}]),
            [('a', 2), ('b', 1)])

    def test_pasta_de_uma_geracao_so_da_um_item(self):
        self.assertEqual(len(carimbo.mistura([{'commit': 'a'}] * 5)), 1)

    def test_sem_entradas_nao_quebra(self):
        self.assertEqual(carimbo.mistura([]), [])
        self.assertEqual(carimbo.mistura(None), [])


class TestOCommit(unittest.TestCase):

    def test_e_medido_uma_vez_so(self):
        """São dezenas de subestações por rodada; `git rev-parse` em cada uma
        seria um subprocesso por subestação."""
        fonte = io.open(os.path.join(RAIZ, 'bdgd2dss', 'carimbo.py'),
                        encoding='utf-8').read()
        self.assertIn('_LEMBRADO', fonte)

    def test_cai_para_a_variavel_da_submissao(self):
        """O git responde no nó de acesso e não no de cálculo — foi assim que
        a V21 inteira saiu sem commit nenhum."""
        fonte = io.open(os.path.join(RAIZ, 'bdgd2dss', 'carimbo.py'),
                        encoding='utf-8').read()
        self.assertIn("os.environ.get('BDGD2DSS_COMMIT'", fonte)

    def test_marca_nunca_devolve_vazio(self):
        real = carimbo._LEMBRADO
        try:
            carimbo._LEMBRADO = ''
            self.assertEqual(carimbo.marca(), 'desconhecido')
        finally:
            carimbo._LEMBRADO = real


class TestQuemCarimba(unittest.TestCase):
    """Os três lugares que passaram a gravar o commit."""

    def _fonte(self, *partes):
        return io.open(os.path.join(RAIZ, *partes), encoding='utf-8').read()

    def test_o_converter_carimba_o_resumo_de_cada_subestacao(self):
        fonte = self._fonte('etapas', 'converter.py')
        self.assertIn("'commit': carimbo.marca(),", fonte)

    def test_o_converter_grita_na_retomada(self):
        fonte = self._fonte('etapas', 'converter.py')
        self.assertIn('carimbo.aviso(', fonte)
        self.assertNotIn('ja existem na pasta e serao puladas', fonte,
                         'a linha discreta voltou')

    def test_a_energia_carimba_na_GRAVACAO_e_nao_em_cada_caminho(self):
        """São quatro caminhos que escrevem em `por_se` — sucesso, falha do
        lote, falha do processo e o serial. Carimbar três daria um carimbo
        pior que nenhum: a entrada sem commit passaria por reaproveitada."""
        fonte = self._fonte('etapas', 'energia.py')
        self.assertIn('class _Carimbados(dict):', fonte)
        self.assertIn('def __setitem__', fonte)

    def test_o_que_veio_do_disco_NAO_e_recarimbado(self):
        """Entrada reaproveitada entra pelo construtor, que não passa por
        `__setitem__` — se passasse, o carimbo mentiria."""
        fonte = self._fonte('etapas', 'energia.py')
        self.assertIn("_Carimbados({x['se']: x for x in saida", fonte)

    def test_a_energia_grita_na_retomada(self):
        fonte = self._fonte('etapas', 'energia.py')
        self.assertIn('carimbo.aviso(', fonte)
        self.assertNotIn('subestacoes ja medidas — retomando', fonte)

    def test_a_procedencia_lista_os_commits_REAIS_da_pasta(self):
        fonte = self._fonte('regerar_v10.py')
        self.assertIn('commits=[', fonte)
        self.assertIn('carimbo.mistura(', fonte)
        self.assertIn('_resumos_das_ses(', fonte)


class TestOCarimbadoDeVerdade(unittest.TestCase):
    """O comportamento do dicionário que carimba, exercitado."""

    def test_o_que_entra_agora_ganha_commit(self):
        exec_globals = {'carimbo': carimbo}
        fonte = io.open(os.path.join(RAIZ, 'etapas', 'energia.py'),
                        encoding='utf-8').read()
        i = fonte.index('    class _Carimbados(dict):')
        j = fonte.index('    por_se = _Carimbados(')
        corpo = '\n'.join(l[4:] for l in fonte[i:j].splitlines())
        exec(compile(corpo, 'energia_trecho', 'exec'), exec_globals)
        d = exec_globals['_Carimbados']({'velha': {'se': 'velha'}})
        d['nova'] = {'se': 'nova'}
        self.assertNotIn('commit', d['velha'],
                         'entrada do disco nao pode ser recarimbada')
        self.assertEqual(d['nova']['commit'], carimbo.marca())


if __name__ == '__main__':
    unittest.main()
