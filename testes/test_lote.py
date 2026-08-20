# -*- coding: utf-8 -*-
"""Ordem de despacho: a maior subestacao primeiro.

Medido nas 119 subestacoes da EQPA, com 8 trabalhadores e a maquina livre: a
ordem alfabetica leva 181 s e a maior-primeiro leva 154 s — 13,5%, com o
arquivo de saida identico byte a byte nos dois. A regra so vale se duas coisas
continuarem verdadeiras, e sao elas que estes testes trancam:

1. a ordem de DESPACHO muda;
2. a ordem da SAIDA nao muda.

A segunda e a que importa de verdade. Toda etapa paralela reimpoe a ordem
original no arquivo que grava, e e isso que permite comparar duas geracoes byte
a byte. Se alguem simplificar trocando `ses` por `fila` na linha da saida, o
resultado continua correto e a comparacao entre geracoes morre em silencio.
"""
import ast
import os
import re
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import lote                              # noqa: E402

# etapa -> nome da lista ORIGINAL, a que define a ordem do arquivo
#
# Exige-se a PROPRIEDADE, e nao o texto da linha. A versao anterior guardava a
# linha inteira, e quebrou quando a montagem da saida foi para dentro de um
# `grava()` — a ordem continuava certa e o teste reprovava. Teste que casa
# token e um obstaculo a refatoracao; o que precisa ficar trancado e de QUE
# lista a saida itera.
ETAPAS = {
    'ligacao.py': 'ses',
    'ampacidade.py': 'ses',
    'verifica.py': 'itens',
    'validador.py': 'pastas',
}


def _arvore(base, tamanhos):
    """Uma pasta por subestacao, cada uma com um MASTER do tamanho pedido."""
    for nome, n in tamanhos.items():
        d = os.path.join(base, nome)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f'MASTER-{nome}.dss'), 'w',
                  encoding='utf-8') as fh:
            fh.write('!' + 'x' * n)
    return base


class AOrdemDeDespacho(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='lote_')
        self.tam = {'AAA': 10, 'BBB': 5000, 'CCC': 300, 'DDD': 90000}
        _arvore(self.dir, self.tam)
        self.pasta = lambda s: os.path.join(self.dir, s)

    def test_a_maior_vem_primeiro(self):
        ses = sorted(self.tam)                        # alfabetica, como hoje
        self.assertEqual(lote.maior_primeiro(ses, self.pasta),
                         ['DDD', 'BBB', 'CCC', 'AAA'])

    def test_nao_perde_nem_duplica_tarefa(self):
        ses = sorted(self.tam)
        self.assertCountEqual(lote.maior_primeiro(ses, self.pasta), ses)

    def test_serve_para_item_que_nao_e_so_o_nome(self):
        """`verifica` e `energia` carregam tuplas, nao o nome solto."""
        itens = [(s, os.path.join(self.dir, s, f'MASTER-{s}.dss'))
                 for s in sorted(self.tam)]
        fila = lote.maior_primeiro(itens, lambda t: os.path.dirname(t[1]))
        self.assertEqual([s for s, _ in fila], ['DDD', 'BBB', 'CCC', 'AAA'])

    def test_pasta_ausente_vai_para_o_fim_e_nao_quebra(self):
        ses = sorted(self.tam) + ['SUMIU']
        self.assertEqual(lote.maior_primeiro(ses, self.pasta)[-1], 'SUMIU')

    def test_empate_e_resolvido_sempre_do_mesmo_jeito(self):
        """Duas rodadas da mesma pasta despacham igual — logs comparaveis."""
        _arvore(self.dir, {'EEE': 300, 'FFF': 300})
        ses = sorted(list(self.tam) + ['EEE', 'FFF'])
        a = lote.maior_primeiro(ses, self.pasta)
        b = lote.maior_primeiro(list(reversed(ses)), self.pasta)
        self.assertEqual(a, b)

    def test_lista_vazia(self):
        self.assertEqual(lote.maior_primeiro([], self.pasta), [])


class AOrdemDaSaida(unittest.TestCase):
    """A fila e para despachar. A saida continua na ordem original."""

    def test_nenhuma_etapa_grava_na_ordem_da_fila(self):
        """A lista gravada itera a colecao original, nunca a `fila`.

        Le a arvore: procura a compreensao que indexa o dicionario de
        resultados (`por_se[...]`, `por_pasta[...]`) e confere sobre o que ela
        itera. E a propriedade que permite comparar duas geracoes byte a byte.
        """
        for script, original in ETAPAS.items():
            with open(os.path.join(RAIZ, script), encoding='utf-8') as fh:
                fonte = fh.read()
            self.assertIn('lote.maior_primeiro', fonte,
                          f'{script} nao despacha a maior primeiro')
            arvore = ast.parse(fonte.lstrip('﻿'))
            fontes = []
            for n in ast.walk(arvore):
                if not isinstance(n, ast.ListComp):
                    continue
                if not (isinstance(n.elt, ast.Subscript)
                        and isinstance(n.elt.value, ast.Name)
                        and n.elt.value.id.startswith('por_')):
                    continue
                for g in n.generators:
                    it = g.iter
                    fontes.append(it.id if isinstance(it, ast.Name)
                                  else ast.dump(it))
            self.assertTrue(
                fontes,
                f'{script}: nao achei a compreensao que monta a saida — o '
                f'teste perdeu o alvo, e nao o codigo a propriedade')
            self.assertEqual(
                set(fontes), {original},
                f'{script}: a saida deixou de iterar `{original}` — a ordem '
                f'passa a depender de quem terminou primeiro e a comparacao '
                f'entre geracoes morre em silencio')

    def test_a_fila_so_aparece_dentro_do_bloco_paralelo(self):
        """`fila` alimentando qualquer coisa fora do `submit` e o erro que
        este teste existe para pegar."""
        for script in list(ETAPAS) + ['energia.py']:
            with open(os.path.join(RAIZ, script), encoding='utf-8') as fh:
                fonte = fh.read()
            usos = re.findall(r'^.*\bfila\b.*$', fonte, re.M)
            for u in usos:
                self.assertTrue(
                    'maior_primeiro' in u or 'submit' in u or 'for ' in u
                    or u.strip().startswith(('#', 'itens,', 'pendentes,',
                                             'ses,', 'pastas,')),
                    f'{script}: uso inesperado da fila -> {u.strip()}')

    def test_energia_mantem_a_ordem_pela_lista_original(self):
        with open(os.path.join(RAIZ, 'energia.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn('ordem = [se for se, _ in itens]', fonte)


if __name__ == '__main__':
    unittest.main()
