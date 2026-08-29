# -*- coding: utf-8 -*-
"""O clima tem de ser da regiao da base — achado 4.

O conversor aplicava o clima medido de Sao Paulo em qualquer base. Roraima, no
equador, saiu com "19,3 a 26,1 C" numa regiao cuja MINIMA e 25,1 C. Temperatura
de celula comanda o derating do painel: a geracao saia fria demais, logo
eficiente demais. Pior que quebrar, porque passa.

Hoje o conversor recusa clima de outra distribuidora e cai no sintetico, que se
declara. Mas so UMA das 97 bases tem cache — as outras 96 rodam no sintetico, e
enquanto for assim nenhuma conclusao sobre GD se sustenta.

Aqui se testa a fila do download: quem ja tem cache e pulado, quem nao tem
coordenada e relatado e nao chutado, e uma falha nao leva as outras junto.
"""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import baixar_clima as bc                              # noqa: E402
from bdgd2dss import clima                             # noqa: E402


class AFilaDoDownload(unittest.TestCase):

    def setUp(self):
        self.raiz = tempfile.mkdtemp()

    def _cache(self, dist, mes=1):
        p = clima.caminho_cache(self.raiz, dist, mes)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('{}')
        return p

    def test_quem_tem_cache_e_pulado(self):
        """Rebaixar o que ja existe gasta rede e arrisca sobrescrever."""
        self._cache('390')
        cen = {'SP': {'dist': '390', 'lon': -46.6, 'lat': -23.5},
               'RR': {'dist': '370', 'lon': -60.7, 'lat': 2.7}}
        fila, prontas, sem = bc.pendentes(cen, 1, self.raiz)
        self.assertEqual([f[0] for f in fila], ['RR'])
        self.assertEqual(prontas, ['SP'])

    def test_refazer_ignora_o_cache(self):
        self._cache('390')
        cen = {'SP': {'dist': '390', 'lon': -46.6, 'lat': -23.5}}
        fila, _, _ = bc.pendentes(cen, 1, self.raiz, refazer=True)
        self.assertEqual([f[0] for f in fila], ['SP'])

    def test_base_sem_coordenada_e_relatada_e_nao_chutada(self):
        """Sem geometria nao ha de onde tirar clima. Inventar uma coordenada
        seria repetir o achado 4 com outra roupa."""
        cen = {'XX': {'dist': '1', 'erro': 'sem geometria utilizavel'}}
        fila, prontas, sem = bc.pendentes(cen, 1, self.raiz)
        self.assertEqual(fila, [])
        self.assertEqual(sem, [('XX', 'sem geometria utilizavel')])

    def test_lat_ausente_conta_como_sem_coordenada(self):
        cen = {'XX': {'dist': '1', 'lon': -46.6}}
        fila, _, sem = bc.pendentes(cen, 1, self.raiz)
        self.assertEqual((fila, len(sem)), ([], 1))

    def test_o_mes_faz_parte_da_identidade_do_cache(self):
        """Janeiro em cache nao dispensa julho: o clima e do MES."""
        self._cache('390', mes=1)
        cen = {'SP': {'dist': '390', 'lon': -46.6, 'lat': -23.5}}
        self.assertEqual(bc.pendentes(cen, 1, self.raiz)[0], [])
        self.assertEqual([f[0] for f in bc.pendentes(cen, 7, self.raiz)[0]],
                         ['SP'])

    def test_so_filtra_por_tag(self):
        cen = {'SP': {'dist': '390', 'lon': -46.6, 'lat': -23.5},
               'RR': {'dist': '370', 'lon': -60.7, 'lat': 2.7}}
        fila, _, _ = bc.pendentes(cen, 1, self.raiz, so={'RR'})
        self.assertEqual([f[0] for f in fila], ['RR'])

    def test_duas_bases_da_mesma_distribuidora_compartilham_o_cache(self):
        """O cache e por DIST, nao por tag: e assim que o conversor o procura.
        Duas `.gdb` da mesma concessionaria nao pedem dois downloads."""
        cen = {'A': {'dist': '390', 'lon': -46.6, 'lat': -23.5},
               'B': {'dist': '390', 'lon': -46.7, 'lat': -23.6}}
        fila, _, _ = bc.pendentes(cen, 1, self.raiz)
        self.assertEqual(len(fila), 2, 'ambas entram na fila...')
        self._cache('390')
        self.assertEqual(bc.pendentes(cen, 1, self.raiz)[0], [],
                         '...e uma so as atende')


if __name__ == '__main__':
    unittest.main()
