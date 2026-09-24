# -*- coding: utf-8 -*-
"""O relato do coletor grita pelo que a V39 deixou passar calado — achado 75.

Nove bases sem ancora externa, 84 subestacoes da Elektro sem o dia, 24,7 MW
mortos numa subestacao da Copel: nada disso reprova, e o relato nao disse
nada. Foi achado varrendo a mao. Estes alarmes acham sozinhos.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'etapas'))
import auditoria                                      # noqa: E402


def _relato(indice):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        auditoria._relata(indice)
    return buf.getvalue()


class Relata(unittest.TestCase):

    def test_base_com_rede_e_sem_ancora_aparece(self):
        t = _relato([{'base': 'COSERN', 'sem_ancora': True, 'commit': 'x'}])
        self.assertRegex(t, r'SEM ancora externa\s+1\s+COSERN')

    def test_dia_incompleto_aparece(self):
        t = _relato([{'base': 'ELEKTRO', 'dia_incompleto_pct': 58.0, 'commit': 'x'}])
        self.assertRegex(t, r'dia incompleto.*1\s+ELEKTRO')

    def test_carga_morta_aparece(self):
        t = _relato([{'base': 'COPEL', 'carga_morta_pct': 11.0, 'commit': 'x'}])
        self.assertRegex(t, r'carga morta.*1\s+COPEL')

    def test_nao_compila_aparece(self):
        t = _relato([{'base': 'RJ', 'nao_compila': 1, 'commit': 'x'}])
        self.assertRegex(t, r'nao compila\s+1\s+RJ')

    def test_base_sadia_nao_aparece(self):
        t = _relato([{'base': 'SP', 'sem_ancora': False, 'dia_incompleto_pct': 2.0,
                      'carga_morta_pct': 1.0, 'nao_compila': 0, 'commit': 'x'}])
        self.assertNotIn('SP', t.split('commits distintos')[0])


class ColherBase(unittest.TestCase):

    def test_conta_o_dia_incompleto_e_quem_nao_compila(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'energia_dia.json'), 'w', encoding='utf-8') as fh:
            json.dump([{'se': 'A', 'passos': 96, 'passos_ok': 96},
                       {'se': 'B', 'passos': 96, 'passos_ok': 95}], fh)
        with open(os.path.join(d, 'validacao.json'), 'w', encoding='utf-8') as fh:
            json.dump([{'modelo': 'A', 'compila': True},
                       {'modelo': 'B', 'compila': False}], fh)
        resumo, _ = auditoria.colher_base(d, 'X')
        self.assertEqual(resumo['rollup']['dia_incompleto'], 1)
        self.assertEqual(resumo['rollup']['ses_com_dia'], 2)
        self.assertEqual(resumo['rollup']['nao_compila'], 1)


if __name__ == '__main__':
    unittest.main()
