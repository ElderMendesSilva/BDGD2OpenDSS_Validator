# -*- coding: utf-8 -*-
"""A iluminacao publica e carga, e estava ficando de fora.

A tabela PIP da BDGD tem `ENE_01..12` como qualquer consumidor, e `UNI_TR_MT`
dizendo em que transformador ela pendura. Medida a energia do mes 01 nas sete
bases, ela vale:

    Enel CE 4,80% | Equatorial PA 4,04% | CPFL 2,96% | Cemig-D 2,73%
    Light 2,46%   | Roraima 1,29%       | Enel SP 1,24%

Sao 5,8 milhoes de pontos somados, e nenhum deles estava no modelo.

DUAS DECISOES QUE ESTES TESTES TRANCAM

1. CARGA SEPARADA, E NAO SOMADA A BT. O `TIP_CC` da PIP e `IP-Tipo1` em 100%
   dos 439.142 registros da Enel CE, e a curva de iluminacao e quase nula de
   dia e cheia de noite. Somar a energia dela na agregacao da BT faria a
   iluminacao seguir o perfil residencial — o contrario do que ela e.

2. `agregado_pip` NO FIM DA ASSINATURA. A primeira versao pos o parametro no
   MEIO de `cargas.gerar`, e o `converter` chama essa funcao com argumentos
   POSICIONAIS: `kv_por_ctmt` passou a entrar no lugar do PIP e `a.kv_mt` no
   lugar do `kv_por_ctmt`. Os 400 testes da suite passaram assim, porque
   nenhum exercitava esse caminho, e o defeito so apareceu ao converter uma
   subestacao de verdade. E a mesma familia do `test_imports`.
"""
import ast
import collections
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
from bdgd2dss import cargas                             # noqa: E402


class ACargaVaiSeparadaDaBT(unittest.TestCase):
    """Sem isso a iluminacao publica acende junto com o chuveiro."""

    def test_a_carga_de_IP_tem_prefixo_e_curva_propria(self):
        fonte = open(os.path.join(RAIZ, 'bdgd2dss', 'cargas.py'),
                     encoding='utf-8').read()
        self.assertIn('New Load.IP_', fonte,
                      'a carga de iluminacao publica nao e emitida')
        self.assertIn("'IP-Tipo1'", fonte,
                      'a curva padrao da iluminacao nao aparece')

    def test_a_agregacao_da_BT_nao_absorve_a_PIP(self):
        """`_agrega_bt` tem de continuar lendo SO a UCBT_tab."""
        arvore = ast.parse(open(os.path.join(RAIZ, 'bdgd2dss', 'cargas.py'),
                                encoding='utf-8').read())
        f = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == '_agrega_bt'][0]
        tabelas = {x.value for x in ast.walk(f)
                   if isinstance(x, ast.Constant) and isinstance(x.value, str)
                   and x.value.endswith('_tab') or
                   (isinstance(x, ast.Constant) and x.value == 'PIP')}
        self.assertNotIn('PIP', tabelas,
                         '_agrega_bt leu a PIP: a energia da iluminacao vai '
                         'seguir a curva residencial')


class ASsinaturaNaoPodeQuebrarOChamador(unittest.TestCase):
    """O defeito que quase foi enviado, e que a suite inteira nao pegou."""

    def test_agregado_pip_e_o_ultimo_parametro(self):
        arvore = ast.parse(open(os.path.join(RAIZ, 'bdgd2dss', 'cargas.py'),
                                encoding='utf-8').read())
        f = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == 'gerar'][0]
        nomes = [a.arg for a in f.args.args]
        self.assertEqual(
            nomes[-1], 'agregado_pip',
            'parametro novo no MEIO da assinatura desloca os posicionais de '
            'quem chama, em silencio')

    def test_o_conversor_passa_o_pip_por_palavra_chave(self):
        arvore = ast.parse(open(os.path.join(RAIZ, 'etapas', 'converter.py'),
                                encoding='utf-8').read())
        chamadas = [n for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'gerar'
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'cargas']
        self.assertTrue(chamadas, 'nao achei a chamada a cargas.gerar')
        for c in chamadas:
            chaves = {k.arg for k in c.keywords}
            self.assertIn('agregado_pip', chaves,
                          'cargas.gerar chamada sem agregado_pip por palavra-'
                          'chave: a iluminacao publica some ou entra no '
                          'parametro errado')


class ACargaEhPreAgregada(unittest.TestCase):
    """Custo. Sem pre-agregar, cada subestacao varre a tabela inteira."""

    def test_o_conversor_agrega_a_pip_uma_vez_so(self):
        fonte = open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8').read()
        self.assertIn('cargas._agrega_pip(', fonte,
                      'o conversor nao pre-agrega a PIP: 2,4 milhoes de '
                      'registros seriam varridos uma vez por subestacao')
        self.assertIn("C.get('agregado_ip')", fonte,
                      'a agregacao nao chega ao trabalhador pelo contexto')

    def test_o_cache_aceita_a_forma_antiga(self):
        """Cache gravado antes da PIP e so o dicionario da BT."""
        fonte = open(os.path.join(RAIZ, 'etapas', 'converter.py'), encoding='utf-8').read()
        self.assertIn('isinstance(_g, tuple)', fonte,
                      'o cache antigo, que e um dict, vai quebrar a leitura')


class OQueAcontecerSemPIP(unittest.TestCase):

    def test_base_sem_a_tabela_nao_quebra(self):
        """Nem toda BDGD tem PIP; a ausencia devolve vazio, nao excecao."""
        class SemPIP:
            def ler_em_fatias(self, *a, **k):
                raise RuntimeError('camada inexistente')

            def log(self, *a):
                pass

        r = cargas._agrega_pip(SemPIP(), ['X'], 1)
        self.assertEqual(len(r), 0)
        self.assertIsInstance(r, collections.defaultdict)


if __name__ == '__main__':
    unittest.main()
