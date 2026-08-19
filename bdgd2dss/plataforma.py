# -*- coding: utf-8 -*-
"""ONDE ESTAMOS RODANDO: no computador de trabalho ou num no de cluster.

    BDGD2DSS_MODO=cluster python regerar_v10.py --sufixo V15
    python regerar_v10.py --sufixo V15 --modo cluster

Dois modos, e a diferenca entre eles e uma so: **de quem e a maquina**.

`pessoal`   a maquina e do dono, que quer continuar usando ela. Deixa nucleos
            de folga, abre formulario quando falta argumento, desenha figura,
            e usa o motor COM da EPRI quando ele existe.

`cluster`   a maquina e do trabalho. Usa todos os nucleos, nunca abre janela
            (nao ha tela), desenha em arquivo e nao na tela, e nao conta com
            nada que so exista no Windows.

O padrao e decidido sozinho e acerta na maior parte das vezes: sem tela e sem
terminal interativo, e cluster. `BDGD2DSS_MODO` ou `--modo` mandam mais que a
deteccao — num no com tela, ou num desktop Linux emprestado, quem sabe e quem
digita.

O QUE O MODO NAO MUDA
---------------------
Nenhum numero. Nem a ordem das contas, nem os arquivos gerados, nem a
quantidade de passos do dia. O modo decide **quanta maquina usar e como falar
com o usuario** — nunca o que e calculado. Um modelo gerado no cluster tem de
sair byte a byte igual ao gerado no laptop, e ha teste para isso.
"""
import os
import sys

CLUSTER = 'cluster'
PESSOAL = 'pessoal'

# quantos nucleos deixar livres no modo pessoal, para a maquina continuar
# utilizavel enquanto o ciclo roda. Dois e o que sobrou de usar a maquina
# durante as rodadas: com zero de folga o computador engasga, com quatro
# desperdica.
FOLGA_PESSOAL = 2

# teto do modo pessoal. Medido: numa maquina so o ganho satura perto de 8
# porque todos os processos disputam o mesmo disco para carregar o modelo.
# No cluster o teto nao se aplica — cada no tem o seu disco e a sua memoria.
TETO_PESSOAL = 8

_forcado = None


def _detecta():
    """Cluster quando nao ha com quem falar: sem tela e sem terminal.

    Nao se pergunta se o sistema e Linux. Ha Linux de mesa e ha Windows sem
    tela, e o que importa nao e o sistema — e se existe alguem na frente.
    """
    if os.environ.get('SLURM_JOB_ID') or os.environ.get('PBS_JOBID'):
        return CLUSTER                      # gerenciador de fila: e no
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        return CLUSTER                      # Linux sem servidor grafico
    return PESSOAL


def modo():
    """O modo em vigor. `--modo` > BDGD2DSS_MODO > deteccao."""
    if _forcado:
        return _forcado
    v = (os.environ.get('BDGD2DSS_MODO') or '').strip().lower()
    return v if v in (CLUSTER, PESSOAL) else _detecta()


def fixar(valor):
    """Fixa o modo para este processo. Usado por quem le `--modo`.

    Grava tambem no ambiente para que os processos filhos herdem: o `regerar`
    dispara cada etapa como processo novo, e um cluster que virasse pessoal na
    segunda etapa seria pior do que nao ter modo nenhum.
    """
    global _forcado
    v = (valor or '').strip().lower()
    if v in (CLUSTER, PESSOAL):
        _forcado = v
        os.environ['BDGD2DSS_MODO'] = v
    return modo()


def no_cluster():
    return modo() == CLUSTER


def nucleos():
    """Quantos processos usar por padrao."""
    n = os.cpu_count() or 4
    if no_cluster():
        return max(1, n)
    return max(1, min(TETO_PESSOAL, n - FOLGA_PESSOAL))


def tem_tela():
    """Se da para abrir formulario. No cluster, nunca."""
    if no_cluster():
        return False
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        return False
    try:
        import tkinter                                  # noqa: F401
        return True
    except Exception:
        return False


def tem_com():
    """O motor COM da EPRI, que so existe registrado no Windows.

    O `verifica` compara os dois motores; fora do Windows ele roda so o
    `opendssdirect` e DIZ que rodou so um, em vez de fingir que comparou.
    """
    if sys.platform != 'win32':
        return False
    try:
        import win32com.client                          # noqa: F401
        return True
    except Exception:
        return False


def pyplot():
    """Matplotlib pronto para o modo em vigor.

    No cluster o backend e `Agg`, que desenha em arquivo sem servidor grafico.
    Sem isso a importacao do pyplot derruba o processo num no headless — e
    derrubaria no fim de uma etapa longa, depois de todo o trabalho feito.
    """
    import matplotlib
    if not tem_tela():
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return plt


def prepara_processos():
    """Iguala o comportamento de `multiprocessing` entre os sistemas.

    No Windows o unico metodo e `spawn`: o filho comeca zerado e importa o
    modulo do trabalhador. No Linux o padrao e `fork`, e o filho nasce com uma
    COPIA do processo pai — inclusive da DLL do OpenDSS ja carregada, com
    circuito e solucao dentro. Isso e exatamente o estado compartilhado que os
    processos separados existem para evitar.

    Forcar `spawn` custa alguns milissegundos por trabalhador e garante que o
    cluster faca a mesma conta que o laptop.
    """
    import multiprocessing as mp
    try:
        if mp.get_start_method(allow_none=True) != 'spawn':
            mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass                                # ja iniciado; nada a fazer
    return mp.get_start_method()


def resumo():
    """Uma linha para o cabecalho dos logs."""
    return (f'modo={modo()} | nucleos={nucleos()} de {os.cpu_count()} | '
            f'tela={"sim" if tem_tela() else "nao"} | '
            f'COM={"sim" if tem_com() else "nao"} | {sys.platform}')
