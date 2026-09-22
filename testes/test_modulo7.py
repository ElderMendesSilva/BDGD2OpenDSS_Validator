# -*- coding: utf-8 -*-
"""Ramais e medidores pelo Modulo 7 do PRODIST — `bdgd2dss/modulo7.py`.

A referencia da ANEEL e a perda tecnica regulatoria do ProgGeoPerdas, que
soma ramais e medidores; o modelo com BT agregada nao tem nenhum dos dois.
Os numeros esperados aqui sao feitos a mao a partir do texto do Modulo 7 (REN
956/2021, Anexo VII): 1 W por circuito de tensao no eletromecanico, 0,5 W no
eletronico, K = 3/2/1 pela ligacao; ramal de 15 m sem cadastro, 30 m no
maximo.
"""
import os
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)

import fixture                                             # noqa: E402
from bdgd2dss import leitor, modulo7                       # noqa: E402

H = modulo7.horas_do_ano(2025)


class BDGDFalsa:
    def __init__(self, tabelas):
        self.t = tabelas

    def ler(self, layer, colunas=None, where=None):
        if layer not in self.t:
            raise RuntimeError(f'sem {layer}')
        tab = self.t[layer]
        return {c: tab.get(c, [''] * len(next(iter(tab.values()))))
                for c in (colunas or tab)}


def _curva_plana():
    base = {'COD_ID': [], 'TIP_DIA': []}
    for k in range(1, 97):
        base[f'POT_{k:02d}'] = []
    for dia in ('DU', 'SA', 'DO'):
        base['COD_ID'].append('RES')
        base['TIP_DIA'].append(dia)
        for k in range(1, 97):
            base[f'POT_{k:02d}'].append(1.0)
    return base


def _bdgd_ramal(comp, ucs, fas_ramal='AN'):
    """Um ramal de condutor com 1 ohm/km e as unidades `ucs` [(fas, kW)]."""
    dias = modulo7.dias_por_tipo(2025)
    uc = {'RAMAL': [], 'TIP_CC': [], 'FAS_CON': [], 'TEN_FORN': []}
    for m in range(1, 13):
        uc[f'ENE_{m:02d}'] = []
    for fas, kw in ucs:
        uc['RAMAL'].append('R1')
        uc['TIP_CC'].append('RES')
        uc['FAS_CON'].append(fas)
        uc['TEN_FORN'].append('')
        for m in range(1, 13):
            uc[f'ENE_{m:02d}'].append(kw * 24 * sum(dias[m].values()))
    return BDGDFalsa({
        'RAMLIG': {'COD_ID': ['R1'], 'CTMT': ['F1'], 'TIP_CND': ['C1'],
                   'COMP': [comp], 'FAS_CON': [fas_ramal]},
        'SEGCON': {'COD_ID': ['C1'], 'R1': [1.0]},
        'CRVCRG': _curva_plana(),
        'UCBT_tab': uc,
    })


def _esperado_mono(kw, comp_m, v_fn=127.0):
    """Monofasico com neutro: 2 condutores levam a corrente."""
    i = kw * 1000 / (v_fn * modulo7.FP)
    return 2 * (comp_m / 1000.0) * i ** 2 * H / 1e6          # MWh


class TestMedidor(unittest.TestCase):

    def test_k_pelo_texto_do_modulo_7(self):
        self.assertEqual(modulo7.k_medidor('ABCN'), 3)      # 3 fases, 4 fios
        self.assertEqual(modulo7.k_medidor('ABN'), 2)       # 2 fases, 3 fios
        self.assertEqual(modulo7.k_medidor('AN'), 1)        # 1 fase, 2 fios

    def test_k_das_ligacoes_que_o_texto_nao_cita(self):
        self.assertEqual(modulo7.k_medidor('ABC'), 2)       # 3 fios, 2 elementos
        self.assertEqual(modulo7.k_medidor('AB'), 1)        # uma tensao so

    def test_perda_do_medidor(self):
        b = BDGDFalsa({
            'UCBT_tab': {'COD_ID': ['U1', 'U2', 'U3'], 'CTMT': ['F1'] * 3,
                         'FAS_CON': ['ABCN', 'AN', 'ABN']},
            'EQME': {'UC_UG': ['U1', 'U2'], 'TIPMED': ['1', '2']}})
        r = modulo7.perda_medidores(b)['F1']
        # U1: 3 x 1 W; U2: 1 x 0,5 W; U3 sem EQME, entra a 1 W: 2 x 1 W
        self.assertAlmostEqual(r['provavel'], (3 + 0.5 + 2) * H / 1e6)
        self.assertAlmostEqual(r['teto'], (3 + 1 + 2) * H / 1e6)
        self.assertAlmostEqual(r['piso'], (3 + 1 + 2) * 0.5 * H / 1e6)
        self.assertEqual(r['sem_tipo'], 1)

    def test_calendario_de_2025(self):
        d = modulo7.dias_por_tipo(2025)
        self.assertEqual(sum(sum(v.values()) for v in d.values()), 365)
        # janeiro de 2025 comeca numa quarta: 23 uteis, 4 sabados, 4 domingos
        self.assertEqual(d[1], {'DU': 23, 'SA': 4, 'DO': 4})


class TestRamal(unittest.TestCase):

    def test_ramal_mono_bate_com_a_conta(self):
        ram, censo = modulo7.perda_ramais(_bdgd_ramal(20, [('AN', 1.27)]),
                                          kv_bt_padrao=0.127)
        self.assertAlmostEqual(ram['F1'], _esperado_mono(1.27, 20), places=6)
        self.assertEqual(censo['ramais'], 1)

    def test_sem_comprimento_vale_15_m(self):
        ram, censo = modulo7.perda_ramais(_bdgd_ramal(0, [('AN', 1.27)]),
                                          kv_bt_padrao=0.127)
        self.assertAlmostEqual(ram['F1'], _esperado_mono(1.27, 15), places=6)
        self.assertEqual(censo['sem_comprimento'], 1)

    def test_acima_de_30_m_e_cortado(self):
        ram, censo = modulo7.perda_ramais(_bdgd_ramal(80, [('AN', 1.27)]),
                                          kv_bt_padrao=0.127)
        self.assertAlmostEqual(ram['F1'], _esperado_mono(1.27, 30), places=6)
        self.assertEqual(censo['acima_de_30m'], 1)

    def test_duas_unidades_no_mesmo_ramal_somam_a_corrente(self):
        """A perda e do QUADRADO da soma: duas unidades de 1,27 kW no mesmo
        ramal perdem 4x o que uma perde, e nao 2x."""
        um, _ = modulo7.perda_ramais(_bdgd_ramal(20, [('AN', 1.27)]), kv_bt_padrao=0.127)
        dois, _ = modulo7.perda_ramais(_bdgd_ramal(20, [('AN', 1.27), ('AN', 1.27)]),
                                       kv_bt_padrao=0.127)
        self.assertAlmostEqual(dois['F1'] / um['F1'], 4.0, places=6)

    def test_base_sem_ramlig_diz_que_nao_tem(self):
        ram, censo = modulo7.perda_ramais(BDGDFalsa({}))
        self.assertEqual(ram, {})
        self.assertEqual(censo, {'sem_tabela': 'RAMLIG'})


class TestNaMinima(unittest.TestCase):

    def test_a_etapa_roda_sobre_a_gdb(self):
        gdb = fixture.garantir()
        p = subprocess.run([sys.executable, os.path.join(RAIZ, 'etapas', 'modulo7.py'), gdb],
                           cwd=RAIZ, capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        # 4 unidades de BT, sem FAS_CON nem EQME: 4 x 1 W o ano inteiro
        b = leitor.BDGD(gdb, verbose=False)
        med = modulo7.perda_medidores(b)
        self.assertAlmostEqual(sum(v['provavel'] for v in med.values()), 4 * H / 1e6)


if __name__ == '__main__':
    unittest.main()
