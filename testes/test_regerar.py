# -*- coding: utf-8 -*-
"""`--so` mescla o resumo, nao o sobrescreve.

Aconteceu na V11, em 13/08/2026: a Cemig-D foi reprocessada sozinha com
`--so CMIG` e o `resumo_v11.json` passou a ter UMA base. As seis da noite
anterior sumiram do arquivo, e a tabela das sete teve de ser remontada na mao
a partir do JSON de dentro de cada modelo.

O resumo e por base. Quem rodou agora vale agora; quem nao rodou continua como
estava.
"""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import regerar_v10 as rg                             # noqa: E402


def _b(tag, **kw):
    return dict(tag=tag, **kw)


class Mesclagem(unittest.TestCase):

    def test_a_base_reprocessada_substitui_a_antiga(self):
        antes = [_b('RR', sadias=20), _b('CMIG', sadias=341)]
        agora = [_b('CMIG', sadias=412)]
        r = {x['tag']: x for x in rg.mesclar(antes, agora)}
        self.assertEqual(r['CMIG']['sadias'], 412)
        self.assertEqual(r['RR']['sadias'], 20, 'a que nao rodou tem de ficar')

    def test_as_outras_seis_nao_somem(self):
        antes = [_b(t) for t in ('RR', 'ENCE', 'EQPA', 'SP', 'LT', 'CPFL')]
        r = rg.mesclar(antes, [_b('CMIG')])
        self.assertEqual(len(r), 7)

    def test_base_nova_entra(self):
        r = rg.mesclar([], [_b('RR')])
        self.assertEqual([x['tag'] for x in r], ['RR'])

    def test_a_ordem_e_a_de_BASES_e_nao_a_de_chegada(self):
        """A tabela impressa no fim tem de sair sempre igual, senao comparar
        duas rodadas vira trabalho de conferencia.

        A ordem esperada vem do APELIDO, e nao de `rg.BASES`: desde que as
        bases sao DESCOBERTAS na pasta, `BASES` depende de quais .gdb
        existem na maquina, e um teste nao pode depender disso. O que se
        exige e que `mesclar` respeite a ordem canonica das conhecidas.
        """
        ordem = [tag for tag, _ in rg.APELIDO.values()]
        r = rg.mesclar([_b('CMIG'), _b('RR')], [_b('SP')])
        saiu = [x['tag'] for x in r]
        self.assertEqual(saiu, sorted(saiu, key=ordem.index))

    def test_tag_desconhecida_vai_para_o_fim_e_nao_quebra(self):
        r = rg.mesclar([_b('XXXX')], [_b('RR')])
        self.assertEqual([x['tag'] for x in r], ['RR', 'XXXX'])


class GravacaoEmDisco(unittest.TestCase):

    def setUp(self):
        self.dest = os.path.join(tempfile.mkdtemp(), 'resumo_v11.json')

    def _ler(self):
        with open(self.dest, encoding='utf-8') as fh:
            return json.load(fh)

    def test_grava_e_depois_mescla(self):
        gravar = rg._gravador(self.dest)
        gravar({'commit': 'aaa'}, [_b('RR', sadias=20), _b('SP', sadias=155)])
        gravar({'commit': 'bbb'}, [_b('CMIG', sadias=412)])
        d = self._ler()
        self.assertEqual({x['tag'] for x in d['bases']}, {'RR', 'SP', 'CMIG'})
        self.assertEqual(d['procedencia']['commit'], 'bbb',
                         'a procedencia e a da rodada corrente')

    def test_arquivo_ilegivel_nao_trava_a_rodada(self):
        """Um JSON truncado por queda de energia nao pode custar a noite."""
        with open(self.dest, 'w', encoding='utf-8') as fh:
            fh.write('{ isto nao e json')
        rg._gravador(self.dest)({'commit': 'a'}, [_b('RR')])
        self.assertEqual([x['tag'] for x in self._ler()['bases']], ['RR'])

    def test_o_arquivo_sai_legivel_em_utf8(self):
        rg._gravador(self.dest)({'commit': 'a'}, [_b('RR', nota='ção')])
        self.assertEqual(self._ler()['bases'][0]['nota'], 'ção')


class BaseNovaNaoDerrubaARodada(unittest.TestCase):
    """As 90 bases novas do pais morreram no minuto 1, todas pelo mesmo motivo.

    25/08/2026, cluster Ubiratan: `TypeError: unsupported operand type(s) for
    +: 'int' and 'NoneType'` na soma da previsao. O `descobrir` devolve `None`
    para base fora do `APELIDO` — de proposito, porque inventar tempo seria
    pior — e o `main` nao tratava. Funcionalidade pela metade, invisivel
    enquanto so as sete conhecidas rodavam.
    """

    def test_so_conhecidas(self):
        self.assertEqual(rg.previsao([('RR', '/x', 1.9), ('SP', '/y', 48.2)]),
                         (50.1, 0))

    def test_so_novas_nao_explode(self):
        p, sem = rg.previsao([('CERFOX504', '/x', None),
                              ('COCEL82', '/y', None)])
        self.assertEqual((p, sem), (0, 2))

    def test_misturado_soma_o_que_da(self):
        """Previsao parcial vale mais que nenhuma, e muito mais que travar."""
        p, sem = rg.previsao([('RR', '/x', 1.9), ('CERFOX504', '/y', None),
                              ('SP', '/z', 48.2)])
        self.assertAlmostEqual(p, 50.1)
        self.assertEqual(sem, 1)

    def test_lista_vazia(self):
        self.assertEqual(rg.previsao([]), (0, 0))


class OModoDaBtEntraNoSufixo(unittest.TestCase):
    """Modelo agregado e modelo completo nao podem disputar a mesma pasta.

    Na Roraima, a mesma subestacao deu 1.852 cargas no agregado e 28.390 no
    completo. Sao modelos diferentes, com outra perda e outra tensao. Sem marca
    no sufixo, o segundo grava por cima do primeiro em silencio — o mesmo
    defeito que o `uma_base.pbs` teve com o sufixo caindo em V18.
    """

    def test_agregado_nao_ganha_marca(self):
        """O padrao historico nao pode mudar: renomearia rodada ja existente."""
        self.assertEqual(rg.sufixo_com_bt('V20', 'agregado'), 'V20')

    def test_completo_e_nenhum_ganham(self):
        self.assertEqual(rg.sufixo_com_bt('V20', 'completo'), 'V20_btcompleto')
        self.assertEqual(rg.sufixo_com_bt('V20', 'nenhum'), 'V20_btnenhum')

    def test_os_tres_modos_nunca_colidem(self):
        s = {rg.sufixo_com_bt('V1_cluster', m)
             for m in ('agregado', 'completo', 'nenhum')}
        self.assertEqual(len(s), 3, 'cada modo tem de ter pasta propria')


class ProcedenciaNaoMenteQuandoNaoSabe(unittest.TestCase):
    """Git que nao responde nao pode virar atestado de arvore limpa.

    Job 34039 no Ubiratan, 25/08/2026: a linha saiu `codigo: (sem git) limpo`.
    O `git` existe no no de acesso e nao no de execucao, e a versao anterior
    devolvia string vazia tanto para "falhou" quanto para "arvore limpa" —
    `git status --porcelain` nao imprime nada quando esta tudo commitado. As
    duas viravam `sujo=False`, e o modelo se declarava reproduzivel sozinho.

    `sujo` agora tem tres valores, e o terceiro e o que faltava:
    True (suja), False (conferida e limpa), None (nao deu para conferir).
    """

    def _com_git(self, fake):
        import subprocess
        real = subprocess.run
        subprocess.run = fake
        try:
            return rg.procedencia()
        finally:
            subprocess.run = real

    def test_git_ausente_nao_afirma_arvore_limpa(self):
        def explode(*a, **k):
            raise FileNotFoundError('git')
        p = self._com_git(explode)
        self.assertIsNone(p['sujo'],
                          'sem git, `sujo` e None — nunca False')
        self.assertFalse(p['git_respondeu'])

    def test_git_que_falha_tambem_nao_afirma(self):
        """Nao basta o binario existir: `rc != 0` tambem e nao-resposta."""
        class R:
            returncode, stdout, stderr = 128, '', 'not a git repository'
        p = self._com_git(lambda *a, **k: R())
        self.assertIsNone(p['sujo'])
        self.assertFalse(p['git_respondeu'])

    def test_arvore_limpa_de_verdade_continua_False(self):
        """O caso legitimo nao pode ter virado None junto."""
        class R:
            returncode, stdout, stderr = 0, '', ''
        p = self._com_git(lambda *a, **k: R())
        self.assertIs(p['sujo'], False,
                      'git respondeu e nao ha pendencia: limpo de verdade')
        self.assertTrue(p['git_respondeu'])

    def test_arvore_suja_continua_True(self):
        class R:
            returncode, stdout, stderr = 0, ' M regerar_v10.py', ''
        p = self._com_git(lambda *a, **k: R())
        self.assertIs(p['sujo'], True)


if __name__ == '__main__':
    unittest.main()
