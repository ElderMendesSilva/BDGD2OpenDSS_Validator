# -*- coding: utf-8 -*-
"""Validar em paralelo tem de dar exatamente o mesmo arquivo que em serie.

O ganho de tempo so vale se o resultado nao mudar, e "nao mudar" aqui e byte a
byte: `validacao.json` e comparado entre duas geracoes para provar que uma
alteracao no conversor nao mexeu no diagnostico. Se a ordem do arquivo passasse
a depender de quem terminou primeiro, essa comparacao acusaria diferenca a cada
rodada sem nenhum numero ter mudado, e o metodo inteiro perderia o valor.

O teste e montado para PEGAR esse erro, e nao so para passar: o primeiro modelo
da ordem serial e de longe o mais pesado, entao em paralelo ele e o ultimo a
terminar. Se a saida seguisse a conclusao, ele cairia para o fim do arquivo.

Os modelos sao DSS escritos a mao, minusculos, e nao saidas do conversor: o que
se testa aqui e o arranjo do validador, nao a conversao.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))

try:
    import opendssdirect                              # noqa: F401
    TEM_DSS = True
except ImportError:                                   # pragma: no cover
    TEM_DSS = False


def _modelo(destino, nome, trechos):
    """Um alimentador em cadeia: `trechos` linhas, uma carga em cada barra."""
    d = os.path.join(destino, nome)
    os.makedirs(d, exist_ok=True)
    L = ['New Circuit.%s basekv=13.8 pu=1.0 phases=3 bus1=fonte '
         'MVAsc3=100000 MVAsc1=100000' % nome,
         'New Linecode.lc nphases=3 r1=0.5 x1=0.4 units=km normamps=200']
    anterior = 'fonte'
    for i in range(trechos):
        b = 'b%d' % i
        L.append('New Line.l%d bus1=%s bus2=%s linecode=lc length=0.05 '
                 'units=km' % (i, anterior, b))
        L.append('New Load.c%d bus1=%s phases=3 kV=13.8 kW=20 pf=0.95' % (i, b))
        anterior = b
    L += ['Set Voltagebases=[13.8]', 'Calcvoltagebases', 'Solve']
    with open(os.path.join(d, 'MASTER-%s.dss' % nome), 'w',
              encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')


def _roda(pasta, jobs):
    r = subprocess.run([sys.executable, '-u',
                        os.path.join(RAIZ, 'etapas', 'validador.py'), pasta,
                        '--ses', '--jobs', str(jobs)],
                       capture_output=True, text=True, timeout=900)
    arq = os.path.join(pasta, 'validacao.json')
    assert os.path.exists(arq), r.stdout + r.stderr
    with open(arq, 'rb') as fh:
        bruto = fh.read()
    os.remove(arq)
    return bruto, r


@unittest.skipUnless(TEM_DSS, 'opendssdirect nao instalado')
class ParaleloEIgualASerie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix='validador_')
        # A_PESADA vem primeiro na ordem alfabetica — que e a ordem serial — e
        # e a que demora mais. Em paralelo ela termina por ultimo.
        _modelo(cls.dir, 'A_PESADA', 400)
        for nome in ('B_LEVE', 'C_LEVE', 'D_LEVE', 'E_LEVE'):
            _modelo(cls.dir, nome, 3)
        cls.serie, cls.saida_serie = _roda(cls.dir, 1)
        cls.paralelo, _ = _roda(cls.dir, 4)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_o_arquivo_e_identico_byte_a_byte(self):
        self.assertEqual(self.serie, self.paralelo,
                         'validacao.json mudou so por ter rodado em paralelo')

    def test_a_ordem_e_a_da_pasta_e_nao_a_de_quem_terminou(self):
        ordem = [r['modelo'] for r in json.loads(self.paralelo)]
        self.assertEqual(ordem, ['A_PESADA', 'B_LEVE', 'C_LEVE', 'D_LEVE',
                                 'E_LEVE'])

    def test_os_cinco_modelos_foram_validados(self):
        """Trabalhador que morre em silencio sumiria com o modelo, e a unica
        pista seria um arquivo mais curto."""
        self.assertEqual(len(json.loads(self.paralelo)), 5)

    def test_todos_compilam_e_convergem(self):
        for r in json.loads(self.paralelo):
            self.assertTrue(r['compila'], r['modelo'])
            self.assertTrue(r.get('converge'), r['modelo'])

    def test_o_diagnostico_de_cada_modelo_e_o_mesmo_nos_dois_modos(self):
        a = {r['modelo']: r['diagnostico'] for r in json.loads(self.serie)}
        b = {r['modelo']: r['diagnostico'] for r in json.loads(self.paralelo)}
        self.assertEqual(a, b)


class AReferenciaDaBase(unittest.TestCase):
    """O limiar de REDE_EXTENSA sai da base inteira (achado 3).

    Ele e calculado no processo principal, antes do leque, e viaja pronto para
    cada trabalhador. Se cada um calculasse o seu, o limiar dependeria do lote
    e a mesma subestacao seria classificada de um jeito sozinha e de outro no
    meio das demais. Le-se a arvore do `main`, e nao o texto do arquivo, para
    que um comentario citando o nome nao satisfaca o teste.
    """

    @staticmethod
    def _main():
        import ast
        with open(os.path.join(RAIZ, 'etapas', 'validador.py'), encoding='utf-8') as fh:
            arvore = ast.parse(fh.read())
        return next(n for n in arvore.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'main')

    def test_a_referencia_vem_antes_de_abrir_os_processos(self):
        import ast
        m = self._main()
        calc = [n.lineno for n in ast.walk(m)
                if isinstance(n, ast.Call)
                and getattr(n.func, 'attr', None) == 'referencia_de']
        leque = [n.lineno for n in ast.walk(m)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, 'attr', None) == 'ProcessPoolExecutor']
        self.assertTrue(calc and leque)
        self.assertLess(max(calc), min(leque),
                        'a referencia da base tem de ser calculada antes de '
                        'abrir os processos')

    def test_o_trabalhador_recebe_a_referencia_pronta(self):
        import inspect
        import validador
        self.assertEqual(list(inspect.signature(validador._uma).parameters),
                         ['tarefa'])
        # e o que ele desempacota tem de ser (pasta, referencia)
        self.assertIn('pasta, ref = tarefa', inspect.getsource(validador._uma))


if __name__ == '__main__':
    unittest.main()
