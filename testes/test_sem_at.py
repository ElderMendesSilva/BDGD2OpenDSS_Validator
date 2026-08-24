# -*- coding: utf-8 -*-
"""Achado 52: sem a camada de AT, cada alimentador precisa da propria fonte.

Os VAOS — as linhas que ligam a barra da subestacao a cabeceira de cada
alimentador — nascem dentro do `gerar_at`, porque a ligacao barra-a-cabeceira
pertence ao patio da subestacao. Com `--sem-at` o `gerar_at` nao roda,
`vaos_lig` fica vazio, e o `converter` caia no ultimo recurso: UMA fonte, na
cabeceira do PRIMEIRO alimentador da lista. Os demais ficavam sem fonte.

MEDIDO em Roraima, base inteira:

                          com AT      --sem-at antes   --sem-at depois
    carga morta             2,9%            84,7%             2,8%
    entrada           167.736 kW        25.757 kW       173.297 kW
    fontes na 5003346          2                1                8

Nao e a alta tensao que falta ao modelo isolado — e a ligacao INTERNA do
patio, que mora no mesmo arquivo. Sem barramento modelado, o honesto e
alimentar cada alimentador na propria cabeceira.

POR QUE ISSO IMPORTA ALEM DO `--sem-at`: o mesmo ultimo recurso atende
qualquer subestacao que fique sem vao — e ele ja tinha mordido antes, na CPFL,
quando TODAS as barras eram derivadas e a fonte foi parar dentro de um
alimentador (achado 47). La a correcao foi um degrau acima, no `origem`; aqui
e o degrau final.

O QUE ESTES TESTES TRANCAM

1. UMA FONTE POR CABECEIRA, e nao uma so. E o defeito inteiro.

2. A TENSAO E A DO ALIMENTADOR. Cada cabeceira pode estar num nivel
   diferente — o achado 49 mostrou 510 alimentadores cuja tensao discorda do
   cabecalho. Usar a `kv_se` da subestacao para todos repetiria o erro que a
   barra derivada existe para evitar.

3. CABECEIRA REPETIDA NAO VIRA FONTE DUPLICADA. Dois alimentadores podem
   declarar o mesmo PAC_INI; duas Vsource na mesma barra e curto entre
   fontes.

4. O CAMINHO NORMAL NAO MUDA. Conferido byte a byte em Roraima: 416
   arquivos, ZERO diferentes.
"""
import ast
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)


def _fallback():
    """O trecho do `converter` que decide a fonte quando nao ha vao."""
    with open(os.path.join(RAIZ, 'converter.py'), encoding='utf-8') as fh:
        fonte = fh.read().lstrip('﻿')
    i = fonte.index('SEM VAO NENHUM')
    return fonte[i:i + 1400]


class UmaFontePorCabeceira(unittest.TestCase):

    def test_percorre_todos_os_ctmts(self):
        t = _fallback()
        self.assertIn('for c in ctmts:', t,
                      'voltou a usar so o primeiro alimentador')
        self.assertNotIn('ctmt_info[ctmts[0]]', t,
                         'ctmts[0] e exatamente o defeito do achado 52')

    def test_usa_a_tensao_do_alimentador(self):
        """Achado 49: 510 alimentadores discordam do cabecalho da subestacao."""
        t = _fallback()
        self.assertIn("ctmt_info[c].get('kv')", t,
                      'a cabeceira tem de ser energizada na tensao DELA')

    def test_cabeceira_repetida_nao_duplica_fonte(self):
        """Duas Vsource na mesma barra e curto entre fontes."""
        t = _fallback()
        self.assertIn('setdefault', t,
                      'sem setdefault, dois alimentadores com o mesmo PAC_INI '
                      'geram duas fontes na mesma barra')

    def test_pac_ini_vazio_nao_vira_barra_fantasma(self):
        t = _fallback()
        self.assertIn('if b_:', t,
                      'PAC_INI em branco viraria uma barra vazia, e o achado '
                      'de sempre: todos os alimentadores sem PAC ligados a '
                      'uma mesma barra que nao se conecta a fonte alguma')


class OQueNaoPodeMudar(unittest.TestCase):

    def test_o_ultimo_recurso_continua_sendo_o_ultimo(self):
        """Ele so vale quando NAO ha vao — nem direto, nem por origem.

        Se subisse na ordem, passaria a alimentar por cabeceira subestacao que
        tem barramento, e ai o modelo deixaria de ter barra: era o achado 47.
        """
        with open(os.path.join(RAIZ, 'converter.py'), encoding='utf-8') as fh:
            fonte = fh.read().lstrip('﻿')
        i_derivada = fonte.index("not vaos_lig[c].get('derivada')")
        i_origem = fonte.index("v.get('origem')")
        i_ultimo = fonte.index('SEM VAO NENHUM')
        self.assertLess(i_derivada, i_origem,
                        'o vao direto tem de ser tentado antes da origem')
        self.assertLess(i_origem, i_ultimo,
                        'a origem da barra derivada tem de vir antes da '
                        'cabeceira — senao volta o achado 47')

    def test_a_flag_continua_existindo(self):
        with open(os.path.join(RAIZ, 'converter.py'), encoding='utf-8') as fh:
            arvore = ast.parse(fh.read().lstrip('﻿'))
        nomes = {c.args[0].value for c in ast.walk(arvore)
                 if isinstance(c, ast.Call)
                 and getattr(c.func, 'attr', '') == 'add_argument'
                 and c.args and isinstance(c.args[0], ast.Constant)}
        self.assertIn('--sem-at', nomes)


if __name__ == '__main__':
    unittest.main()
