# -*- coding: utf-8 -*-
"""Sair do `with ProcessPoolExecutor` e esperar sem prazo. Nao pode.

`testes/test_grava_antes_de_esperar.py` ja garante a PRIMEIRA defesa: o
resultado vai para o disco ANTES de sair do `with`. Isso salva o resultado.

Nao salva o RELOGIO. Sair do `with` chama `shutdown(wait=True)`, que espera
cada trabalhador morrer, sem prazo. Medido na V16 da Cemig-D: o `verifica`
processou as 413 subestacoes — os indices [1/413] a [413/413] estao todos no
log — e foi morto pelo limite de 6 h antes de escrever. Os OITO trabalhadores
criados as 04:37:09 continuavam vivos as 14:30, seis horas depois de o pai ter
sido morto. O suspeito e o motor COM, que nao solta.

`bdgd2dss/pool.py` estava escrito desde 21/08 e NINGUEM O CHAMAVA. Ficou
assim ate 23/08, quando a V19 ia rodar a noite inteira sem ninguem olhando.

O QUE ESTES TESTES TRANCAM

1. AS QUATRO ETAPAS CHAMAM. `verifica`, `ampacidade`, `validador` e
   `ligacao` usam pool; se uma esquecer, e justamente ela que vai travar as
   3 da manha.

2. A CHAMADA E DENTRO DO `with`. Fora dele ja e tarde: a espera sem prazo
   acontece na saida do bloco.

3. `encerrar` NUNCA LEVANTA. Uma falha ao matar trabalhador nao pode
   derrubar uma etapa que ja produziu o resultado.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import pool                                  # noqa: E402

ETAPAS = ('verifica.py', 'ampacidade.py', 'validador.py', 'ligacao.py')


def _with_do_pool(arvore):
    """Os blocos `with ProcessPoolExecutor(...) as ex:` do arquivo."""
    achados = []
    for n in ast.walk(arvore):
        if not isinstance(n, ast.With):
            continue
        for item in n.items:
            c = item.context_expr
            if (isinstance(c, ast.Call)
                    and getattr(c.func, 'attr', '') == 'ProcessPoolExecutor'):
                achados.append(n)
    return achados


class AsQuatroEtapasEncerramOPool(unittest.TestCase):

    def _arvore(self, f):
        with open(os.path.join(RAIZ, f), encoding='utf-8') as fh:
            return ast.parse(fh.read().lstrip('﻿'))

    def test_toda_etapa_com_pool_chama_encerrar(self):
        for f in ETAPAS:
            with self.subTest(etapa=f):
                arv = self._arvore(f)
                blocos = _with_do_pool(arv)
                self.assertTrue(blocos, f'{f}: nao achei o bloco do pool')
                chamou = any(
                    isinstance(x, ast.Call)
                    and getattr(x.func, 'attr', '') == 'encerrar'
                    and getattr(x.func.value, 'id', '') == 'pool'
                    for b in blocos for x in ast.walk(b))
                self.assertTrue(
                    chamou,
                    f'{f} sai do `with` sem prazo. E esta etapa que vai '
                    f'travar as 3 da manha com o resultado ja pronto.')

    def test_a_chamada_e_DENTRO_do_with(self):
        """Fora do bloco ja e tarde: a espera acontece na saida dele."""
        for f in ETAPAS:
            with self.subTest(etapa=f):
                arv = self._arvore(f)
                dentro = {id(x) for b in _with_do_pool(arv)
                          for x in ast.walk(b)}
                fora = [x for x in ast.walk(arv)
                        if isinstance(x, ast.Call)
                        and getattr(x.func, 'attr', '') == 'encerrar'
                        and getattr(x.func.value, 'id', '') == 'pool'
                        and id(x) not in dentro]
                self.assertEqual(fora, [],
                                 f'{f}: `pool.encerrar` fora do `with`')

    def test_o_modulo_e_importado(self):
        for f in ETAPAS:
            with self.subTest(etapa=f):
                fonte = open(os.path.join(RAIZ, f), encoding='utf-8').read()
                self.assertIn('pool', fonte.split('def ')[0],
                              f'{f} nao importa bdgd2dss.pool')


class EncerrarNuncaLevanta(unittest.TestCase):
    """Falhar ao matar trabalhador nao pode derrubar etapa ja concluida."""

    def test_pool_sem_processos_devolve_zero(self):
        class Vazio:
            _processes = {}

            def shutdown(self, **k):
                pass
        self.assertEqual(pool.encerrar(Vazio()), 0)

    def test_shutdown_que_explode_nao_propaga(self):
        class Explode:
            _processes = {}

            def shutdown(self, **k):
                raise RuntimeError('boom')
        self.assertEqual(pool.encerrar(Explode()), 0)

    def test_trabalhador_que_nao_morre_e_contado(self):
        class Zumbi:
            def __init__(self):
                self.matou = False

            def is_alive(self):
                return not self.matou

            def terminate(self):
                self.matou = True

            def join(self, t=None):
                pass

            def kill(self):
                self.matou = True

        z = Zumbi()

        class Ex:
            _processes = {1: z}

            def shutdown(self, **k):
                pass

        avisos = []
        self.assertEqual(pool.encerrar(Ex(), prazo=0.1, log=avisos.append), 1)
        self.assertTrue(z.matou)
        self.assertTrue(avisos, 'matar trabalhador em silencio esconde o '
                                'defeito que motivou este modulo')

    def test_shutdown_que_zera__processes_nao_derruba(self):
        """O defeito que o canario pegou, e que os testes nao pegavam.

        `ProcessPoolExecutor.shutdown` faz `self._processes = None` no fim.
        A primeira versao lia a lista DEPOIS do shutdown e recebia None; o
        `.values()` explodia e derrubava a etapa inteira — no exato ponto em
        que este modulo existe para nao derrubar nada. Medido em 23/08/2026:
        `ligacao` e `ampacidade` de Roraima falharam DEPOIS de ter feito o
        trabalho todo.

        Os testes de mentira passavam porque o `shutdown` deles nao mexia em
        `_processes`. Dublê que nao imita o defeito nao protege de nada.
        """
        class Zumbi:
            def is_alive(self):
                return False

        class ComoOCPython:
            def __init__(self):
                self._processes = {1: Zumbi()}

            def shutdown(self, **k):
                self._processes = None      # e o que o CPython faz

        self.assertEqual(pool.encerrar(ComoOCPython(), prazo=0.1), 0)

    def test_executor_sem__processes_nao_derruba(self):
        """Outro executor qualquer pode nem ter o atributo."""
        class Estranho:
            def shutdown(self, **k):
                pass
        self.assertEqual(pool.encerrar(Estranho()), 0)

    def test_trabalhador_que_morre_sozinho_nao_e_contado(self):
        class Saudavel:
            def is_alive(self):
                return False

        class Ex:
            _processes = {1: Saudavel()}

            def shutdown(self, **k):
                pass

        avisos = []
        self.assertEqual(pool.encerrar(Ex(), prazo=0.1, log=avisos.append), 0)
        self.assertEqual(avisos, [], 'sem zumbi nao ha nada a avisar')


if __name__ == '__main__':
    unittest.main()
