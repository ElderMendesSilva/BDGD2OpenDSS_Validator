# -*- coding: utf-8 -*-
"""O `perfil_violacao.py` roda no cluster, sobre `.gdb` que esta so la. Estes
testes trancam a parte que NAO depende da BDGD: a selecao dos suspeitos e a
conta de enriquecimento, que e o numero que decide se um condutor explica a
violacao ou so e comum na rede."""
import csv
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'diagnosticos'))

import perfil_violacao as pv        # noqa: E402


def _csv(tmp, base, linhas):
    caminho = os.path.join(tmp, f'{base}_violacoes.csv')
    with open(caminho, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['base', 'sub', 'ctmt', 'motivo',
                                           'se_veredicto'])
        w.writeheader()
        w.writerows(linhas)
    return tmp


def _linha(ctmt, motivo='perda modelada absurda: 90.0%', veredicto='OK'):
    return {'base': 'B', 'sub': 'S1', 'ctmt': ctmt, 'motivo': motivo,
            'se_veredicto': veredicto}


class EscolhaDosSuspeitos(unittest.TestCase):

    def test_modelo_quebrado_nao_entra_na_comparacao(self):
        """Numero de SE quebrada poluiria o perfil — e sintoma de outro
        defeito, ja detectado."""
        tmp = _csv(tempfile.mkdtemp(), 'B', [
            _linha('BOM'),
            _linha('QUEBRADO', veredicto='POTENCIA_NAN[C-API]')])
        alvo, fora = pv.suspeitos_do_csv(tmp, 'B')
        self.assertEqual(alvo, {'BOM'})
        self.assertEqual(fora, 1)

    def test_filtra_por_motivo(self):
        tmp = _csv(tempfile.mkdtemp(), 'B', [
            _linha('ABSURDA', motivo='perda modelada absurda: 90.0%'),
            _linha('LIMITE', motivo='no limite: modelo 1.10x o total medido')])
        alvo, _ = pv.suspeitos_do_csv(tmp, 'B', motivo='perda modelada absurda')
        self.assertEqual(alvo, {'ABSURDA'})

    def test_ctmt_normalizado(self):
        tmp = _csv(tempfile.mkdtemp(), 'B', [_linha(' abc ')])
        alvo, _ = pv.suspeitos_do_csv(tmp, 'B')
        self.assertEqual(alvo, {'ABC'})

    def test_base_sem_csv_falha_dizendo_o_caminho(self):
        with self.assertRaises(SystemExit):
            pv.suspeitos_do_csv(tempfile.mkdtemp(), 'NAO_EXISTE')


class Enriquecimento(unittest.TestCase):
    """O numero que separa 'e maioria' de 'concentra'."""

    def _at(self, cnd):
        return {'cnd': cnd, 'r1': {}, 'cnom': {}}

    def test_condutor_igualmente_comum_nao_enriquece(self):
        at = self._at({'A': {'593': 10.0}, 'B': {'593': 10.0}})
        e = pv.enriquecimento({'A'}, {'B'}, at)
        self.assertEqual(e[0]['condutor'], '593')
        self.assertEqual(e[0]['enriquecimento'], 1.0)

    def test_condutor_concentrado_nos_suspeitos_enriquece(self):
        at = self._at({'A': {'593': 9.0, 'X': 1.0},
                       'B': {'593': 1.0, 'X': 9.0}})
        e = pv.enriquecimento({'A'}, {'B'}, at)
        por_cond = {x['condutor']: x for x in e}
        self.assertEqual(por_cond['593']['enriquecimento'], 9.0)
        self.assertLess(por_cond['X']['enriquecimento'], 1.0)

    def test_condutor_com_km_irrelevante_sai_da_lista(self):
        """Um condutor com 10 cm de rede daria enriquecimento enorme e nao
        significa nada."""
        at = self._at({'A': {'593': 100.0, 'RARO': 0.01},
                       'B': {'593': 100.0}})
        e = pv.enriquecimento({'A'}, {'B'}, at, minimo_km=1.0)
        self.assertNotIn('RARO', [x['condutor'] for x in e])

    def test_condutor_ausente_do_resto_nao_divide_por_zero(self):
        at = self._at({'A': {'SO_NOS_MAUS': 10.0}, 'B': {'593': 10.0}})
        e = pv.enriquecimento({'A'}, {'B'}, at)
        self.assertIsNone(e[0]['enriquecimento'])


if __name__ == '__main__':
    unittest.main()
