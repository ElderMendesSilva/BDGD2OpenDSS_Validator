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
import os
import re
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import lote                              # noqa: E402

# etapa -> (linha que monta a fila, linha que monta a saida)
ETAPAS = {
    'ligacao.py': 'saida = [por_se[s_] for s_ in ses if s_ in por_se]',
    'ampacidade.py': 'saida = [por_se[s_] for s_ in ses if s_ in por_se]',
    'verifica.py': 'saida = [por_se[se] for se, _ in itens if se in por_se]',
    'validador.py': 'out = [por_pasta[p] for p in pastas if p in por_pasta]',
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
        for script, linha_saida in ETAPAS.items():
            with open(os.path.join(RAIZ, script), encoding='utf-8') as fh:
                fonte = fh.read()
            self.assertIn('lote.maior_primeiro', fonte,
                          f'{script} nao despacha a maior primeiro')
            self.assertIn(linha_saida, fonte,
                          f'{script}: a saida deixou de sair na ordem '
                          f'original — a comparacao entre geracoes perde o '
                          f'valor')

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
