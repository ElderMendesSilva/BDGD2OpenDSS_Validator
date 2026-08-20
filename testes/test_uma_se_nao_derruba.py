# -*- coding: utf-8 -*-
"""Uma subestacao que falha nao pode derrubar a etapa inteira.

Escrito depois de custar uma base. Na V16 a subestacao 1726671 da Cemig-D
estourou o limite de iteracoes de controle — um AVISO do OpenDSS, que o
`opendssdirect` levanta como excecao — e levou junto as outras 412: a etapa
morreu aos 15,4 min, sem `ligacao.json`, e o ciclo seguiu para a proxima etapa
sobre modelos meio ligados.

O custo nao e a subestacao perdida; e a base inteira ter de ser refeita, depois
de 83 min de conversao que estavam certos.

E o caso vai se repetir: quanto mais rede a premissa energiza, mais regulador
entra no laco de controle. A resposta certa e a subestacao ficar de fora COM O
MOTIVO ESCRITO, e nao a rodada parar.

O teste le a arvore: toda funcao que roda UMA subestacao tem de ter um
`except` que devolve registro de erro, em vez de deixar a excecao subir ate o
`f_.result()` do pool.
"""
import ast
import os
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# executavel -> funcao que processa uma subestacao
TRABALHADORES = {
    'ligacao.py': 'uma',
    'ampacidade.py': 'uma',
    'verifica.py': '_uma',
    'energia.py': '_um_processo',
    'validador.py': '_uma',
}


def _funcao(caminho, nome):
    with open(caminho, encoding='utf-8') as fh:
        arvore = ast.parse(fh.read().lstrip('﻿'))
    for n in arvore.body:
        if isinstance(n, ast.FunctionDef) and n.name == nome:
            return n
    return None


class NenhumaFalhaDeUmaSEDerrubaAEtapa(unittest.TestCase):

    def test_todo_trabalhador_captura_e_devolve_o_erro(self):
        sem_rede = []
        for script, nome in TRABALHADORES.items():
            f = _funcao(os.path.join(RAIZ, script), nome)
            self.assertIsNotNone(f, f'{script}: {nome} sumiu')
            captura = [h for n in ast.walk(f)
                       if isinstance(n, ast.Try) for h in n.handlers]
            # `except Exception` (ou nu) em algum ponto, e com retorno dentro
            largo = [h for h in captura
                     if h.type is None
                     or (isinstance(h.type, ast.Name)
                         and h.type.id in ('Exception', 'BaseException'))]
            devolve = any(isinstance(x, ast.Return)
                          for h in largo for x in ast.walk(h))
            if not (largo and devolve):
                sem_rede.append(f'{script}:{nome}')
        self.assertEqual(sem_rede, [],
                         'trabalhador sem rede de seguranca: a excecao sobe '
                         'ate o pool e mata a etapa inteira, e com ela o '
                         'trabalho das outras subestacoes')

    def test_a_falha_e_devolvida_junto_com_a_subestacao(self):
        """Erro sem o nome da SE nao serve: ninguem sabe o que refazer.

        A forma varia de propria de cada etapa — o `ligacao` devolve
        `{'se', 'erro'}`, o `energia` devolve a tripla `(se, r, erro)` — entao
        o que se exige e o par, e nao um formato.
        """
        for script, nome in TRABALHADORES.items():
            f = _funcao(os.path.join(RAIZ, script), nome)
            fonte = ast.unparse(f)
            self.assertIn('erro', fonte,
                          f'{script}: a falha nao e devolvida')
            self.assertTrue('se' in fonte or 'modelo' in fonte,
                            f'{script}: a falha nao diz de que subestacao e')


if __name__ == '__main__':
    unittest.main()
