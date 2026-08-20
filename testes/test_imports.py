# -*- coding: utf-8 -*-
"""Modulo do projeto usado sem ter sido importado.

Escrito depois de custar uma rodada. O `energia.py` chamava
`plataforma.prepara_processos()` sem importar `plataforma`: o arquivo compila,
a suite inteira passa, o `--help` responde — e a etapa morre com `NameError` no
segundo em que e disparada de verdade. Na V15 isso derrubou o `energia` de
quatro bases seguidas antes de alguem ver.

Por que a suite nao pegou: o caminho paralelo do `energia` nunca era executado
nos testes, e uma linha que nunca roda nao acusa nome que nao existe. Ler o
codigo pega, e custa milissegundos.

O teste e proposital estreito. Nao tenta ser um analisador: olha so os modulos
DESTE projeto usados como `modulo.coisa`, que sao os que a gente importa a mao
e esquece.
"""
import ast
import glob
import os
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# os modulos do projeto que se usam por nome qualificado
NOSSOS = {'plataforma', 'pausa', 'lote', 'escrita', 'ligacao', 'ampacidade',
          'diagnostico', 'tensoes', 'linhas', 'chaves', 'cargas', 'master',
          'linecodes', 'complementos', 'coordenadas', 'transformadores',
          'subtransmissao', 'transmissao', 'malha_at', 'clima', 'interativo',
          'cobertura'}


def _importados(arvore):
    nomes = set()
    for n in ast.walk(arvore):
        if isinstance(n, ast.ImportFrom):
            nomes |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.Import):
            nomes |= {(a.asname or a.name).split('.')[0] for a in n.names}
    return nomes


def _definidos(arvore):
    nomes = set()
    for n in ast.walk(arvore):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            nomes.add(n.id)
        elif isinstance(n, ast.arg):
            nomes.add(n.arg)
    return nomes


class TodoModuloUsadoEstaImportado(unittest.TestCase):

    def _arquivos(self):
        for cam in sorted(glob.glob(os.path.join(RAIZ, '*.py'))
                          + glob.glob(os.path.join(RAIZ, 'bdgd2dss', '*.py'))):
            yield cam

    def test_nenhum_modulo_do_projeto_e_usado_sem_import(self):
        faltando = {}
        for cam in self._arquivos():
            with open(cam, encoding='utf-8') as fh:
                texto = fh.read().lstrip('﻿')
            try:
                arvore = ast.parse(texto)
            except SyntaxError as e:            # pragma: no cover
                self.fail(f'{os.path.basename(cam)} nao compila: {e}')
            tem = _importados(arvore) | _definidos(arvore)
            usados = {n.value.id for n in ast.walk(arvore)
                      if isinstance(n, ast.Attribute)
                      and isinstance(n.value, ast.Name)}
            falta = sorted((usados & NOSSOS) - tem)
            if falta:
                faltando[os.path.relpath(cam, RAIZ)] = falta
        self.assertEqual(faltando, {},
                         'modulo do projeto usado sem import: compila, passa '
                         'na suite, e morre com NameError na primeira '
                         'execucao de verdade')


if __name__ == '__main__':
    unittest.main()
