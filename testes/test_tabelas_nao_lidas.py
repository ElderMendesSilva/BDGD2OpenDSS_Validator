# -*- coding: utf-8 -*-
"""Criterio 7: as tabelas que sobraram, DECLARADAS a cada rodada.

O criterio pede "resolvidas OU declaradas". Declaracao que mora so num `.md`
envelhece: a safra seguinte muda os numeros e o documento continua dizendo os
antigos. Aqui ela sai no `relatorio_rede.json`, com os numeros DAQUELA base.

O QUE FOI MEDIDO NAS SETE, em 24/08/2026:

    EQSE      3.026.708   nas sete
    UNSEBT      158.656   so SP, LT, CMIG e CPFL — zero nas outras tres
    UNCRBT            0   ZERO nas sete
    UNREBT      ausente   a camada nao existe em base nenhuma

E POR QUE A EQSE FICA DE FORA, que era a duvida real: o `COR_NOM` dela e
IDENTICO ao da UNSEMT em 23.962 de 23.962 casos em Roraima, com zero
diferencas e zero exclusivos — a ampacidade que ela traz o conversor ja tem.
O proprio dela e `ELO_FSV` e `MEI_ISO`, protecao e patrimonio, fora do fluxo
de potencia.

O QUE ESTES TESTES TRANCAM

1. A DECLARACAO SAI NO ARQUIVO, e nao so no log. Log se perde; o
   `relatorio_rede.json` fica junto do modelo que alguem vai auditar.

2. CADA TABELA TEM MOTIVO. Listar nome sem dizer por que nao ajuda ninguem —
   e a diferenca entre declarar e apenas omitir com estilo.

3. CAMADA AUSENTE NAO E ZERO. `None` (a camada nao existe) e 0 (existe e esta
   vazia) sao fatos diferentes sobre a BDGD, e o censo preserva os dois.

4. CENSO NUNCA DERRUBA CONVERSAO. Isto e relatorio; relatorio que quebra o
   que ele deveria descrever nao serve para nada.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import tabelas                               # noqa: E402


class BDGDdeMentira:
    def __init__(self, contagens):
        self.c = contagens

    def n_registros(self, tab):
        if tab not in self.c:
            raise RuntimeError(f'camada {tab} nao existe')
        return self.c[tab]


class OCensoDiz(unittest.TestCase):

    def test_conta_cada_tabela_nao_lida(self):
        r = tabelas.censo(BDGDdeMentira({'EQSE': 24541, 'UNSEBT': 0,
                                         'UNCRBT': 0}))
        self.assertEqual(r['EQSE']['registros'], 24541)
        self.assertEqual(r['UNSEBT']['registros'], 0)

    def test_camada_ausente_e_None_e_nao_zero(self):
        """Existir vazia e nao existir sao fatos diferentes sobre a BDGD."""
        r = tabelas.censo(BDGDdeMentira({'UNCRBT': 0}))
        self.assertEqual(r['UNCRBT']['registros'], 0)
        self.assertIsNone(r['UNREBT']['registros'],
                          'camada inexistente tem de sair como None')

    def test_toda_tabela_traz_o_motivo(self):
        r = tabelas.censo(BDGDdeMentira({}))
        for tab, d in r.items():
            with self.subTest(tabela=tab):
                self.assertTrue(d['motivo'].strip(),
                                f'{tab} listada sem dizer por que ficou fora')
                self.assertGreater(len(d['motivo']), 30,
                                   f'{tab}: motivo curto demais para explicar')

    def test_a_eqse_diz_que_o_cor_nom_ja_e_lido(self):
        """O motivo dela e o unico que precisa de medicao, e a medicao esta
        la: 23.962 de 23.962 iguais ao da UNSEMT."""
        m = tabelas.NAO_LIDAS['EQSE']
        self.assertIn('COR_NOM', m)
        self.assertIn('23.962', m)


class CensoNuncaDerruba(unittest.TestCase):

    def test_bdgd_que_explode_nao_propaga(self):
        class Explode:
            def n_registros(self, tab):
                raise RuntimeError('disco caiu')
        r = tabelas.censo(Explode())
        self.assertEqual(len(r), len(tabelas.NAO_LIDAS))
        self.assertTrue(all(d['registros'] is None for d in r.values()))

    def test_sem_o_metodo_tambem_nao_quebra(self):
        class Nada:
            pass
        self.assertTrue(tabelas.censo(Nada()))


class QuemUsa(unittest.TestCase):

    def test_o_conversor_publica_no_relatorio(self):
        with open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8') as fh:
            fonte = fh.read().lstrip('﻿')
        self.assertIn("'tabelas_nao_lidas'", fonte,
                      'a declaracao nao chega ao relatorio_rede.json')
        arvore = ast.parse(fonte)
        chamou = any(isinstance(n, ast.Call)
                     and getattr(n.func, 'attr', '') == 'censo'
                     and getattr(getattr(n.func, 'value', None), 'id', '')
                     == 'tabelas'
                     for n in ast.walk(arvore))
        self.assertTrue(chamou, 'converter importa tabelas e nao chama censo')


if __name__ == '__main__':
    unittest.main()
