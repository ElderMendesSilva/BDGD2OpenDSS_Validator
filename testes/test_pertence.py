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


if __name__ == '__main__':
    unittest.main()
