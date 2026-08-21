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


if __name__ == '__main__':
    unittest.main()
