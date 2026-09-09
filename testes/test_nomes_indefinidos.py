# -*- coding: utf-8 -*-
"""Nenhuma chamada a nome que não existe em escopo nenhum — o erro da V33.

A V33 caiu em **35 das 99 bases** com `NameError: name 'log' is not defined`.
A linha estava dentro de `_uma_se`, onde `log` não existe — ele é do escopo do
`main` —, e só era **alcançada** quando a base tinha uma unidade de GD
implausível. As 64 bases sem nenhuma passaram, e o teste de fumaça na `.gdb`
mínima também, por não ter nenhuma.

É o formato de erro mais caro do projeto: não aparece no caminho comum,
aparece só no caminho que importa. Python não acusa nome indefinido até
executar a linha, e uma rodada nacional custa horas de cluster.

Este teste varre o pacote inteiro pela árvore sintática. Não substitui um
linter; cobre a classe de erro que já custou uma rodada.
"""
import glob
import os
import sys
import textwrap
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import nomes                                  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestOProjeto(unittest.TestCase):

    def test_nenhuma_chamada_a_nome_indefinido(self):
        alvos = sorted(
            glob.glob(os.path.join(RAIZ, 'bdgd2dss', '*.py'))
            + glob.glob(os.path.join(RAIZ, 'etapas', '*.py'))
            + glob.glob(os.path.join(RAIZ, '*.py')))
        self.assertGreater(len(alvos), 40, 'a varredura nao achou o projeto')
        achados = nomes.indefinidos(alvos)
        detalhe = '\n'.join(
            f'  {os.path.relpath(a, RAIZ)}:{ln}  {fn}() chama `{nome}`'
            for a, ln, fn, nome in achados)
        self.assertEqual(achados, [], f'nome indefinido:\n{detalhe}')


class TestOVerificador(unittest.TestCase):
    """Verificador que não acusa nada pode estar apenas quebrado."""

    def _checa(self, fonte):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'alvo.py')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(textwrap.dedent(fonte))
        return nomes.indefinidos([p])

    def test_pega_o_erro_exato_da_v33(self):
        achados = self._checa('''
            def main():
                def log(m):
                    print(m)
                log('ok')

            def _uma_se(C, se, k):
                if C:
                    log('ACHADO 32')
            ''')
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0][2:], ('_uma_se', 'log'))

    def test_o_escopo_de_fechamento_conta(self):
        """`pool.py` chama `log` dentro de `_diz`, e `log` é argumento de
        `encerrar`. Acusar isso tornaria o verificador inútil."""
        self.assertEqual(self._checa('''
            def encerrar(ex, log=None):
                def _diz(m):
                    if log:
                        log(m)
                _diz('oi')
            '''), [])

    def test_funcao_do_topo_vale_em_qualquer_lugar(self):
        self.assertEqual(self._checa('''
            def ajuda():
                return 1

            def usa():
                return ajuda()
            '''), [])

    def test_import_dentro_de_try_vale(self):
        """Import opcional em `try/except ImportError` é comum no projeto."""
        self.assertEqual(self._checa('''
            try:
                from json import dumps
            except ImportError:
                dumps = None

            def usa(x):
                return dumps(x)
            '''), [])

    def test_embutido_do_python_nao_e_indefinido(self):
        self.assertEqual(self._checa('''
            def usa(x):
                return len(sorted(x))
            '''), [])

    def test_funcao_aninhada_em_if_e_alcancada(self):
        """A varredura tem de atravessar `if`/`try`/`for` para achar a função."""
        achados = self._checa('''
            import os

            if os.name:
                def dentro_do_if():
                    inexistente_de_proposito()
            ''')
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0][3], 'inexistente_de_proposito')


if __name__ == '__main__':
    unittest.main()
