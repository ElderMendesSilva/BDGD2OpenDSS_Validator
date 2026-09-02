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
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
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


class ONomeDaLinhaLevaACamada(unittest.TestCase):
    """`COD_ID` e unico DENTRO da tabela, nao entre tabelas.

    BT1, 29/08/2026: as DEZ bases do experimento sairam `NAO_COMPILA`, da de
    32 m/trafo a de 955. O erro do OpenDSS era `Duplicate new element
    definition: "Line.662"` — a SSDMT, a SSDBT e a RAMLIG numeram cada uma a
    partir do seu proprio espaco, e o mesmo `662` existe nas tres.

    No modo agregado nada de BT e emitido e o choque nao aparece; foi por isso
    que o defeito so surgiu quando o modo completo finalmente rodou no cluster.
    E ele custou o experimento inteiro: o resultado media o nome, nao a
    topologia que a hipotese queria testar.
    """

    def test_a_linha_e_o_neutro_carregam_o_nome_da_camada(self):
        from bdgd2dss import linhas
        col = {'COD_ID': ['662'], 'PAC_1': ['b1'], 'PAC_2': ['b2'],
               'CTMT': ['c'], 'FAS_CON': ['ABC'], 'TIP_CND': ['x'],
               'COMP': [100.0]}
        saida = os.path.join(tempfile.mkdtemp(), 'bt.dss')
        linhas.gerar_bt(None, {}, ['c'], saida, camada='SSDBT', col=col)
        with open(saida, encoding='utf-8') as fh:
            txt = fh.read()
        self.assertIn('New Line.SSDBT_662 ', txt)
        self.assertIn('New Line.N_SSDBT_662 ', txt)
        self.assertNotIn('New Line.662 ', txt)

    def test_camadas_diferentes_nao_colidem_no_mesmo_COD_ID(self):
        """O caso exato que derrubou a BT1."""
        from bdgd2dss import linhas
        col = {'COD_ID': ['662'], 'PAC_1': ['b1'], 'PAC_2': ['b2'],
               'CTMT': ['c'], 'FAS_CON': ['ABC'], 'TIP_CND': ['x'],
               'COMP': [100.0]}
        d = tempfile.mkdtemp()
        nomes = []
        for cam in ('SSDBT', 'RAMLIG'):
            p = os.path.join(d, cam + '.dss')
            linhas.gerar_bt(None, {}, ['c'], p, camada=cam, col=dict(col))
            with open(p, encoding='utf-8') as fh:
                nomes += [l.split()[1] for l in fh if l.startswith('New Line.')]
        self.assertEqual(len(nomes), len(set(nomes)),
                         'mesmo COD_ID em camadas diferentes nao pode gerar '
                         'o mesmo nome de elemento')


if __name__ == '__main__':
    unittest.main()
