# -*- coding: utf-8 -*-
"""`leitor.pertence` — o filtro que derrubou a Cemig-D depois de 4h15.

    ufunc 'minimum' did not contain a loop with signature matching
    types (dtype('<U7'), dtype('<U')) -> None

O `np.isin` cru falha quando os dois lados sao string de largura diferente. A
largura sai do conteudo lido, entao o defeito depende da base e das fatias —
Enel SP, Roraima, Light, Equatorial e CPFL passaram por sorte de conteudo.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bdgd2dss.leitor import pertence              # noqa: E402


class Pertence(unittest.TestCase):

    def test_caso_que_derrubou_a_cemig(self):
        """Coluna <U7 contra alvo de largura diferente."""
        col = np.array(['1726748', '1726750', '1726752'], dtype='<U7')
        alvo = np.array(['1726750'], dtype='<U')      # itemsize 0
        m = pertence(col, alvo)
        self.assertEqual(list(m), [False, True, False])

    def test_alvo_mais_largo_que_a_coluna(self):
        """Truncar para casar seria pior que o erro: casamento errado calado."""
        col = np.array(['ABC', 'ABCDEFGH'], dtype='<U8')
        m = pertence(col, ['ABCDEFGHIJ'])
        self.assertEqual(list(m), [False, False])

    def test_alvo_mais_curto(self):
        col = np.array(['ABCDEFGH', 'AB'], dtype='<U8')
        self.assertEqual(list(pertence(col, ['AB'])), [False, True])

    def test_larguras_iguais_continua_funcionando(self):
        col = np.array(['F1', 'F2', 'F3'])
        self.assertEqual(list(pertence(col, ['F1', 'F3'])), [True, False, True])

    def test_coluna_vazia(self):
        self.assertEqual(len(pertence(np.array([], dtype='<U7'), ['A'])), 0)

    def test_alvo_vazio(self):
        col = np.array(['A', 'B'])
        self.assertEqual(list(pertence(col, [])), [False, False])

    def test_coluna_de_objeto(self):
        """O pyogrio devolve texto como object em algumas versoes."""
        col = np.array(['F1', 'F2'], dtype=object)
        self.assertEqual(list(pertence(col, ['F2'])), [False, True])

    def test_numerico_nao_e_afetado(self):
        col = np.array([1, 2, 3])
        self.assertEqual(list(pertence(col, [2, 3])), [False, True, True])

    def test_muitos_valores(self):
        col = np.array([f'C{i:05d}' for i in range(5000)])
        alvo = [f'C{i:05d}' for i in range(0, 5000, 500)]
        self.assertEqual(int(pertence(col, alvo).sum()), 10)


class ColunaDeObjeto(unittest.TestCase):
    """Segunda volta, 12/08/2026. A primeira correcao nao bastou: a Cemig-D
    caiu com o MESMO erro na subestacao 265 de 413, depois de 5h57.

    A coluna CTMT dela chega como `dtype('O')`, e para objeto o `itemsize` e
    8 — o tamanho do ponteiro, nao o comprimento da string. A versao anterior
    usava esse 8 como largura.
    """

    def test_string_maior_que_oito_nao_e_truncada(self):
        """O caso que o `itemsize` de objeto produzia: com largura 8, os dois
        codigos abaixo viram o MESMO 'ABCDEFGH' e casam os dois. Casamento
        errado em silencio e pior que o erro — a docstring do proprio modulo
        diz isso."""
        col = np.array(['ABCDEFGH_1', 'ABCDEFGH_2'], dtype=object)
        self.assertEqual(list(pertence(col, ['ABCDEFGH_2'])), [False, True])

    def test_objeto_com_codigos_longos_e_curtos_juntos(self):
        col = np.array(['F1', 'ALIMENTADOR_MUITO_LONGO_01', 'F3'],
                       dtype=object)
        self.assertEqual(list(pertence(col, ['ALIMENTADOR_MUITO_LONGO_01'])),
                         [False, True, False])

    def test_objeto_com_none_no_meio(self):
        """Campo nulo da BDGD nao pode derrubar o filtro."""
        col = np.array(['F1', None, 'F2'], dtype=object)
        self.assertEqual(list(pertence(col, ['F2'])), [False, False, True])

    def test_objeto_com_numero_no_meio(self):
        col = np.array(['F1', 7, 'F2'], dtype=object)
        self.assertEqual(list(pertence(col, ['F2'])), [False, False, True])

    def test_o_caso_medido_na_cemig(self):
        """A coluna real: object, itemsize 8, conteudo de 5 caracteres."""
        col = np.array(['ENC13', 'FIO12', 'GHE10', 'FIO13'], dtype=object)
        self.assertEqual(col.dtype.itemsize, 8)
        self.assertEqual(list(pertence(col, ['FIO13', 'FIO12'])),
                         [False, True, False, True])

    def test_alvo_numpy_str_em_coluna_de_objeto(self):
        col = np.array(['F1', 'F2'], dtype=object)
        alvo = np.array(['F2'])                  # numpy.str_, nao str
        self.assertEqual(list(pertence(col, alvo)), [False, True])

    def test_volume_de_objeto_nao_perde_correcao(self):
        col = np.array([f'CTMT_{i:06d}' for i in range(20000)], dtype=object)
        alvo = [f'CTMT_{i:06d}' for i in range(0, 20000, 1000)]
        self.assertEqual(int(pertence(col, alvo).sum()), 20)


if __name__ == '__main__':
    unittest.main()
