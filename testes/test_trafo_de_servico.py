# -*- coding: utf-8 -*-
"""O trafo de servico do regulador no caminho da potencia — achado 81.

Na CPFL Santa Cruz a entrada de cada banco regulador fica atras de uma UNTRMT
de 11,4 kV para 11,4 kV com 2,5 a 12,5 kVA. Modelada como transformador, ela
estrangula a rede a jusante: 1.637 barras de MT a 0,02 pu na ITS. As seis
subestacoes TENSAO_IMPLAUSIVEL da CPFL_SANTA69 na V39 sao esta forma.

Relacao 1:1 entre dois niveis de MT, poucos kVA, e secundario que CONTINUA a
rede de MT (entrada de regulador, chave, trecho) viram ligacao direta. O
trafo de distribuicao com TEN_LIN_SE de MT por erro de cadastro, e carga de BT
no secundario, continua trafo.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)
import fixture                                             # noqa: E402


def _converte(variante, tmp):
    gdb = fixture.gerar(os.path.join(tmp, 'g.gdb'), variante=variante)
    saida = os.path.join(tmp, 'M')
    p = subprocess.run([sys.executable, '-u',
                        os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                        '--saida', saida], cwd=RAIZ, capture_output=True,
                       text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-1500:]
    return os.path.join(saida, 'SE1'), p.stdout


def _le(*partes):
    with io.open(os.path.join(*partes), encoding='utf-8') as fh:
        return fh.read()


class NaVariante(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ts81_')
        cls.se, cls.log = _converte('trafo_de_servico', cls.tmp)
        cls.trafos = _le(cls.se, 'Trafos.dss')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_vira_ligacao_e_nao_trafo(self):
        self.assertIn('New Line.TR11_TS ', self.trafos)
        self.assertNotIn('New Transformer.TS ', self.trafos)

    def test_o_regulador_nao_fica_pendurado(self):
        r = json.loads(_le(self.se, 'resumo.json'))
        self.assertEqual(r.get('reguladores_pendurados'), 0)

    def test_fica_dito(self):
        self.assertIn('ACHADO 81', self.trafos)
        self.assertIn('ACHADO 81', self.log)


class NaMinima(unittest.TestCase):
    """O TR2 da minima declara TEN_LIN_SE 7,96 kV (MT) e tem carga de BT no
    secundario: e trafo com cadastro errado, e nao trafo de servico."""

    def test_trafo_de_distribuicao_continua_trafo(self):
        tmp = tempfile.mkdtemp(prefix='ts81m_')
        try:
            se, _ = _converte(None, tmp)
            t = _le(se, 'Trafos.dss')
            self.assertIn('New Transformer.TR2 ', t)
            self.assertNotIn('TR11_', t)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
