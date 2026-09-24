# -*- coding: utf-8 -*-
"""Chave com o mesmo `COD_ID` de um trecho de MT — achado 77.

`COD_ID` e unico dentro de uma tabela, nao entre tabelas. Na Cosern, 93
codigos da UNSEMT sao tambem codigos da SSDMT; os dois viravam `Line.<cod>`,
o OpenDSS recusava o segundo com #266 ("Duplicate new element definition") e
as subestacoes CCO e MCV sairam NAO_COMPILA na V39.

So a chave que colide muda de nome (`CH_<cod>`): nas bases sem colisao, nada
muda, e o controle e a lista de abertas seguem o nome novo.
"""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import chaves                           # noqa: E402
from test_chaves import _Leitor, _unsemt              # noqa: E402


def _gera(linhas, trechos=None):
    tmp = tempfile.mkdtemp()
    c = os.path.join(tmp, 'Chaves.dss')
    k = os.path.join(tmp, 'Controles.dss')
    n, ab, _ilh, _cr = chaves.gerar(_Leitor(_unsemt(*linhas)), ['F1'], c, k,
                                    trechos=trechos)
    return n, ab, open(c, encoding='utf-8').read(), open(k, encoding='utf-8').read()


class ChaveComCodigoDeTrecho(unittest.TestCase):

    def test_a_chave_que_colide_ganha_prefixo(self):
        _, _, ch, ct = _gera([('1571773', 'b1', 'b2', 'F'), ('9', 'b2', 'b3', 'F')],
                             trechos={'1571773', '42'})
        self.assertIn('New Line.CH_1571773 ', ch)
        self.assertNotIn('New Line.1571773 ', ch)
        self.assertIn('New Line.9 ', ch, 'a que nao colide fica como estava')
        self.assertIn('SwitchedObj=Line.CH_1571773 ', ct)

    def test_a_aberta_sai_com_o_nome_novo(self):
        _, ab, _, _ = _gera([('77', 'b1', 'b2', 'A')], trechos={'77'})
        self.assertEqual(ab, ['CH_77'])

    def test_a_comparacao_ignora_maiusculas(self):
        """O OpenDSS nao distingue `Line.ABC` de `Line.abc`."""
        _, _, ch, _ = _gera([('SEGM_X', 'b1', 'b2', 'F')], trechos={'segm_x'})
        self.assertIn('New Line.CH_SEGM_X ', ch)

    def test_fica_escrito_no_arquivo(self):
        _, _, ch, _ = _gera([('77', 'b1', 'b2', 'F')], trechos={'77'})
        self.assertIn('ACHADO 77', ch)

    def test_sem_trechos_nada_muda(self):
        _, _, ch, _ = _gera([('77', 'b1', 'b2', 'F')])
        self.assertIn('New Line.77 ', ch)
        self.assertNotIn('ACHADO 77', ch)

    def test_o_conversor_passa_os_trechos(self):
        with open(os.path.join(os.path.dirname(AQUI), 'etapas', 'converter.py'),
                  encoding='utf-8') as fh:
            self.assertIn('trechos={c for v in pares_mt.values()', fh.read())


if __name__ == '__main__':
    unittest.main()
