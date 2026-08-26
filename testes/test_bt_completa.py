# -*- coding: utf-8 -*-
"""`COD_ID` da UCBT_tab nao e unico, e o OpenDSS aborta quando descobre.

Medido na Cemig-D em 25/08/2026, subestacao 1726782, com `--bt completo`:

    DSSException: (#266) Duplicate new element definition:
                  "Load.UC_e6446f51...._3". Element being redefined.

O modelo nao chegava a resolver. O erro nao e do OpenDSS — e a BDGD trazendo
duas linhas com o mesmo codigo de unidade consumidora.

A saida NAO e descartar a segunda: perderia energia declarada em silencio, e o
modelo entregaria menos do que a base diz. Cada ocorrencia ganha sufixo, TODAS
entram, e a contagem sai no cabecalho para o defeito de dado ficar visivel.
"""
import io
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import cargas                          # noqa: E402


class _LeitorFalso:
    """Devolve exatamente as colunas pedidas, como o `ler_filtrado` de verdade."""

    def __init__(self, linhas):
        self.linhas = linhas

    def ler_filtrado(self, layer, chave, valores, colunas=None, **kw):
        return {c: [l.get(c) for l in self.linhas] for c in colunas}


def _uc(cod, pac='b1', fas='A', ene=730.0):
    return {'COD_ID': cod, 'PAC': pac, 'UNI_TR_MT': 'TR1', 'CTMT': 'C1',
            'FAS_CON': fas, 'TIP_CC': 'RES-Tipo02', 'ENE_01': ene}


class CodIdRepetidoNaoColide(unittest.TestCase):

    def _gera(self, linhas):
        d = tempfile.mkdtemp()
        alvo = os.path.join(d, 'CargasBT.dss')
        r = cargas.gerar_bt_completa(
            _LeitorFalso(linhas), ['C1'],
            {'TR1': {'kv_fn': 0.127, 'nos': ['1']}},
            alvo, mes=1, curvas_validas={'RES-Tipo02'})
        return r, io.open(alvo, encoding='utf-8').read()

    def test_dois_cod_id_iguais_geram_nomes_diferentes(self):
        r, txt = self._gera([_uc('MESMO'), _uc('MESMO')])
        self.assertIn('New Load.UC_MESMO_1 ', txt)
        self.assertIn('New Load.UC_MESMO_1__2 ', txt)
        self.assertEqual(r['cod_id_repetido'], 1)

    def test_nenhuma_carga_e_descartada(self):
        """Perder energia declarada em silencio seria pior que o erro."""
        r, txt = self._gera([_uc('X'), _uc('X'), _uc('X')])
        self.assertEqual(txt.count('New Load.'), 3)
        self.assertEqual(r['n_cargas_bt'], 3)

    def test_o_defeito_de_dado_fica_declarado_no_arquivo(self):
        _, txt = self._gera([_uc('X'), _uc('X')])
        self.assertIn('COD_ID repetido', txt)
        self.assertIn('Nenhuma foi descartada', txt)

    def test_sem_repeticao_o_nome_nao_muda(self):
        """O caso normal nao pode ganhar sufixo: renomearia todo modelo antigo."""
        r, txt = self._gera([_uc('A'), _uc('B')])
        self.assertIn('New Load.UC_A_1 ', txt)
        self.assertIn('New Load.UC_B_1 ', txt)
        self.assertNotIn('__2', txt)
        self.assertEqual(r['cod_id_repetido'], 0)

    def test_o_sufixo_e_deterministico(self):
        """Duas geracoes do mesmo .gdb tem de sair byte a byte iguais."""
        linhas = [_uc('X'), _uc('Y'), _uc('X'), _uc('X')]
        self.assertEqual(self._gera(linhas)[1], self._gera(linhas)[1])

    def test_fases_diferentes_do_mesmo_cod_id_nao_sao_repeticao(self):
        """`UC_<cod>_1` e `UC_<cod>_2` ja sao distintos: e a mesma UC bifasica."""
        r, txt = self._gera([_uc('BI', fas='AB')])
        self.assertIn('New Load.UC_BI_1 ', txt)
        self.assertIn('New Load.UC_BI_2 ', txt)
        self.assertEqual(r['cod_id_repetido'], 0)


if __name__ == '__main__':
    unittest.main()
