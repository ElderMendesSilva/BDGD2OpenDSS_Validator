# -*- coding: utf-8 -*-
"""Trava o que o `investigar_violacoes.py` promete: comparar contra a taxa de
FUNDO, e nao contra zero. Um sinal que aparece em toda SE da rodada nao pode
sair como se explicasse a violacao so por estar presente."""
import csv
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'analise'))

import investigar_violacoes as iv     # noqa: E402


def _pasta_com(tmp, violacoes_por_base, ses_por_base):
    for base, linhas in violacoes_por_base.items():
        with open(os.path.join(tmp, f'{base}_violacoes.csv'), 'w',
                  newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
    for base, ses in ses_por_base.items():
        with open(os.path.join(tmp, f'{base}.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({'subestacoes': ses}, fh)
    return tmp


def _linha(base='B', sub='S1', motivo='perda modelada absurda: 50.0%',
          se_veredicto='OK', gwh=10.0):
    return {'base': base, 'sub': sub, 'ctmt': 'C1', 'motivo': motivo,
            'GWh_injetado': str(gwh), 'se_veredicto': se_veredicto}


def _se(nome, **flags):
    d = {'se': nome, 'convergiu': True, 'chaves_ilhadas': 0,
         'reguladores_pendurados': 0, 'trafos_pac_invertido': 0}
    d.update(flags)
    return d


class Classificacao(unittest.TestCase):

    def test_modelo_quebrado_nao_conta_como_sem_sinal(self):
        v = [_linha(se_veredicto='POTENCIA_NAN[C-API]')]
        quebrado, com, sem = iv.classificar(v, {})
        self.assertEqual(len(quebrado), 1)
        self.assertEqual(len(com) + len(sem), 0)

    def test_sinal_so_conta_se_a_se_tiver_o_flag(self):
        v = [_linha(sub='S1')]
        subs = {('B', 'S1'): _se('S1', chaves_ilhadas=3)}
        quebrado, com, sem = iv.classificar(v, subs)
        self.assertEqual(len(com), 1)
        self.assertIn('chaves_ilhadas', com[0]['_sinais_se'])

    def test_sem_registro_de_se_vai_para_sem_sinal(self):
        v = [_linha(sub='FORA_DO_INDICE')]
        quebrado, com, sem = iv.classificar(v, {})
        self.assertEqual(len(sem), 1)

    def test_taxa_de_fundo_usa_TODAS_as_se_da_rodada(self):
        """O ponto do script: um flag em 80% das violacoes nao diz nada se
        tambem esta em 80% de toda a rodada."""
        subs = {('B', str(i)): _se(str(i), chaves_ilhadas=1) for i in range(8)}
        subs.update({('B', str(i)): _se(str(i)) for i in range(8, 10)})
        fundo = iv.taxa_de_fundo(subs)
        self.assertAlmostEqual(fundo['chaves_ilhadas'], 0.8)


class ArquivoDeSaida(unittest.TestCase):

    def test_grava_investigacao_json_e_nao_derruba(self):
        tmp = tempfile.mkdtemp()
        _pasta_com(
            tmp,
            {'B': [_linha(motivo='perda modelada absurda: 90.0%')]},
            {'B': [_se('S1', chaves_ilhadas=1)]})
        iv.main([tmp])
        saida = json.load(open(os.path.join(tmp, 'investigacao.json'),
                               encoding='utf-8'))
        self.assertEqual(saida['total_violacoes'], 1)
        self.assertIn('taxa_de_fundo_pct', saida)


if __name__ == '__main__':
    unittest.main()
