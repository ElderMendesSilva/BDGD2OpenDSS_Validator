# -*- coding: utf-8 -*-
"""Opcao que so existe na linha de comando nao existe para quem usa o painel.

O `menu.py` e a porta de entrada do projeto, e a regra e que TUDO que se faz
por comando se faca por ele. Sem este teste a regra dura ate alguem acrescentar
uma flag e esquecer do formulario — e ninguem percebe, porque nada quebra.

Como funciona: para cada executavel, le as opcoes que o proprio `--help`
declara e confere se cada uma aparece na interface que a dispara. Nao prova
que o widget esta certo; prova que a opcao NAO FOI ESQUECIDA, que e o modo de
falha real.
"""
import os
import re
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# executavel -> onde mora a interface que o dispara
ALVOS = {
    'converter.py': 'app.py',            # tem janela propria
    'ligacao.py': None,                  # formulario no proprio script
    'ampacidade.py': None,
    'verifica.py': None,
    'energia.py': None,
    'validador.py': None,
    'valida_perdas.py': None,
    'valida_balanco.py': None,
    'regerar_v10.py': None,
}


def _opcoes(script):
    h = subprocess.run([sys.executable, os.path.join(RAIZ, script), '--help'],
                       capture_output=True, text=True, timeout=120).stdout
    return sorted(set(re.findall(r'--[a-z][a-z0-9-]+', h)) - {'--help'})


class OPainelCobreALinhaDeComando(unittest.TestCase):

    def test_toda_opcao_tem_caminho_pela_interface(self):
        faltando = {}
        for script, ui in ALVOS.items():
            fonte = open(os.path.join(RAIZ, ui or script),
                         encoding='utf-8').read()
            f = [o for o in _opcoes(script) if o not in fonte]
            if f:
                faltando[script] = f
        self.assertEqual(faltando, {},
                         'opcao sem caminho pelo painel — acrescente ao '
                         'formulario do proprio script, ou ao app.py no caso '
                         'do conversor')

    def test_todo_executavel_esta_no_menu(self):
        """Ferramenta que nao esta no menu so existe para quem sabe o nome do
        arquivo."""
        menu = open(os.path.join(RAIZ, 'menu.py'), encoding='utf-8').read()
        fora = [s for s in ALVOS if s not in menu and s != 'converter.py']
        self.assertEqual(fora, [], 'executavel fora do menu.py')

    def test_o_menu_aponta_para_arquivos_que_existem(self):
        menu = open(os.path.join(RAIZ, 'menu.py'), encoding='utf-8').read()
        for nome in re.findall(r"'(\w+\.py)'", menu):
            self.assertTrue(os.path.exists(os.path.join(RAIZ, nome)),
                            f'{nome} esta no menu e nao existe')


if __name__ == '__main__':
    unittest.main()
