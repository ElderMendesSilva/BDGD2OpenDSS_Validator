# -*- coding: utf-8 -*-
"""Pausar um ciclo de horas sem perder o que ja foi feito.

O que estes testes trancam nao e "a pausa funciona" — e barato de ver — e sim
as tres coisas que a fariam causar mais dano do que resolve:

1. **Ninguem para no meio de uma subestacao.** A espera fica sempre ANTES do
   trabalho. Um trabalhador que esperasse depois de compilar seguraria o
   circuito inteiro na memoria, e o motivo de pausar costuma ser precisar da
   maquina.
2. **O tempo parado nao conta como tempo de execucao.** Sem isso, pausar tres
   horas faria a etapa "estourar o tempo limite" ao ser retomada — o pior jeito
   possivel de perder trabalho — e os minutos do resumo virariam ficcao,
   quebrando a comparacao de desempenho entre duas geracoes.
3. **O arquivo e achado de qualquer diretorio.** Os trabalhadores fazem
   `os.chdir` para dentro da pasta da subestacao. Um caminho relativo faria a
   pausa ser ignorada exatamente por quem precisa obedece-la.
"""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import pausa                             # noqa: E402

# etapa -> a funcao que roda uma subestacao. Todas tem de esperar antes.
TRABALHADORES = {
    'ligacao.py': 'def uma(pasta, se, min_cargas):',
    'ampacidade.py': 'def uma(pasta, se, margem):',
    'verifica.py': 'def _uma(tarefa):',
    'energia.py': 'def _um_processo(tarefa):',
    'validador.py': 'def _uma(tarefa):',
}


class OArquivoDePausa(unittest.TestCase):

    def tearDown(self):
        pausa.retomar()

    def test_o_caminho_e_absoluto(self):
        """Os trabalhadores fazem chdir. Caminho relativo seria ignorado por
        eles — justamente por quem mais precisa obedecer."""
        self.assertTrue(os.path.isabs(pausa.ARQUIVO))

    def test_e_achado_de_outro_diretorio(self):
        pausa.pedir('teste')
        antes = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            self.assertTrue(pausa.pausado())
        finally:
            os.chdir(antes)

    def test_pedir_e_retomar(self):
        self.assertFalse(pausa.pausado())
        pausa.pedir('teste')
        self.assertTrue(pausa.pausado())
        self.assertTrue(pausa.retomar())
        self.assertFalse(pausa.pausado())

    def test_retomar_duas_vezes_nao_quebra(self):
        pausa.pedir()
        pausa.retomar()
        self.assertFalse(pausa.retomar())

    def test_o_motivo_fica_gravado(self):
        pausa.pedir('vou jogar')
        with open(pausa.ARQUIVO, encoding='utf-8') as fh:
            self.assertIn('vou jogar', fh.read())

    def test_espera_devolve_zero_quando_nao_ha_pausa(self):
        self.assertEqual(pausa.espera(), 0.0)

    def test_espera_segura_ate_o_arquivo_sumir(self):
        pausa.pedir('teste')
        parado = []

        def solta():
            time.sleep(pausa.INTERVALO * 3)
            pausa.retomar()

        threading.Thread(target=solta, daemon=True).start()
        t0 = time.time()
        parado.append(pausa.espera('teste'))
        gasto = time.time() - t0
        self.assertGreater(parado[0], 0)
        self.assertLess(gasto, 30, 'espera nao soltou quando o arquivo sumiu')

    def test_avisa_uma_vez_ao_entrar_e_uma_ao_sair(self):
        pausa.pedir('teste')
        ditos = []
        threading.Timer(pausa.INTERVALO * 2, pausa.retomar).start()
        pausa.espera('etapa', avisa=ditos.append)
        self.assertEqual(len(ditos), 2, ditos)
        self.assertIn('pausado', ditos[0])
        self.assertIn('retomando', ditos[1])


class OndeAEsperaAcontece(unittest.TestCase):
    """A espera fica ANTES do trabalho, em todo caminho que roda uma SE."""

    def _corpo(self, script, assinatura):
        with open(os.path.join(RAIZ, script), encoding='utf-8') as fh:
            linhas = fh.read().split('\n')
        i = next(k for k, l in enumerate(linhas) if l.startswith(assinatura))
        return linhas[i:i + 25]

    def test_todo_trabalhador_espera_antes_de_trabalhar(self):
        for script, assinatura in TRABALHADORES.items():
            corpo = self._corpo(script, assinatura)
            esperas = [k for k, l in enumerate(corpo) if 'pausa.espera()' in l]
            self.assertTrue(esperas, f'{script}: trabalhador nao espera')
            trabalho = [k for k, l in enumerate(corpo)
                        if 'Compile' in l or 'Redirect MASTER' in l
                        or 'valida(' in l or '_capi(' in l or 'dia(' in l]
            if trabalho:
                self.assertLess(esperas[0], min(trabalho),
                                f'{script}: espera depois de montar o '
                                f'circuito — seguraria a memoria toda')

    def test_o_conversor_para_entre_subestacoes(self):
        with open(os.path.join(RAIZ, 'converter.py'), encoding='utf-8') as fh:
            self.assertIn('pausa.espera()', fh.read())

    def test_o_regerar_desconta_a_pausa_do_limite(self):
        """Pausar nao pode fazer a etapa estourar o tempo limite."""
        with open(os.path.join(RAIZ, 'regerar_v10.py'), encoding='utf-8') as fh:
            fonte = fh.read()
        self.assertIn('time.time() - t0 - parado > limite', fonte)
        self.assertIn('m = (time.time() - t0 - parado) / 60.0', fonte,
                      'os minutos do resumo tem de ser de trabalho, nao de '
                      'relogio')


class PelaLinhaDeComando(unittest.TestCase):

    def tearDown(self):
        pausa.retomar()

    def _roda(self, *args):
        return subprocess.run([sys.executable, os.path.join(RAIZ, 'pausa.py'),
                               *args], capture_output=True, text=True,
                              timeout=120)

    def test_pausar_e_retomar(self):
        self._roda('--pausar')
        self.assertTrue(pausa.pausado())
        self._roda('--retomar')
        self.assertFalse(pausa.pausado())

    def test_estado_nao_mexe_em_nada(self):
        r = self._roda('--estado')
        self.assertIn('rodando', r.stdout)
        self.assertFalse(pausa.pausado())

    def test_sem_dizer_qual_alterna(self):
        """Com o ciclo pausado, quem so passa `--motivo` quer retomar.

        Nao se chama sem argumento NENHUM aqui de proposito: isso abre o
        formulario, como em todo executavel do projeto, e travaria a suite.
        """
        self._roda('--pausar')
        self._roda('--motivo', 'voltei')
        self.assertFalse(pausa.pausado(),
                         'rodar de novo com o ciclo pausado deveria retomar')


if __name__ == '__main__':
    unittest.main()
