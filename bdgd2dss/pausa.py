# -*- coding: utf-8 -*-
"""PAUSAR o ciclo sem perder o que ja foi feito.

Um ciclo das sete bases leva horas, e a maquina e a mesma que o dono usa. Sem
uma pausa, as opcoes eram ruins as duas: aguentar a lentidao ou matar a rodada
e comecar de novo.

COMO FUNCIONA. Um arquivo vazio na raiz do projeto, `PAUSA`. Enquanto ele
existir, quem for comecar uma tarefa nova espera. Quem ja estava no meio de uma
termina — a granularidade e uma subestacao, que e de segundos a poucos minutos.
Apagar o arquivo retoma na hora.

POR QUE UM ARQUIVO, e nao um sinal ou uma porta: os passos rodam em processos
separados (cada etapa e um subprocesso do `regerar`, e dentro dela cada
subestacao e um processo do pool). Um arquivo e a unica coisa que todos eles
enxergam sem combinar nada, e que continua valendo se algum deles morrer.

ONDE A ESPERA ACONTECE. Sempre ANTES de comecar o trabalho, nunca no meio:

  * no `regerar`, entre etapas e entre bases;
  * em cada trabalhador dos pools, antes de compilar o modelo;
  * no `converter`, entre subestacoes.

Isso importa por memoria: um trabalhador que espera ANTES de compilar segura
alguns MB. Se esperasse depois, seguraria o circuito inteiro — e o motivo de
pausar costuma ser justamente precisar da maquina.

O TEMPO PARADO NAO CONTA COMO TEMPO DE EXECUCAO. O `regerar` desconta a pausa
do limite de cada etapa; sem isso, pausar tres horas faria a etapa "estourar o
tempo limite" ao ser retomada, que e o pior jeito possivel de perder trabalho.
Os minutos gravados no resumo tambem sao os de trabalho, e nao os de relogio —
senao a comparacao de desempenho entre duas geracoes viraria ficcao.
"""
import os
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO = os.path.join(RAIZ, 'PAUSA')

# de quanto em quanto tempo se olha o arquivo. Meio segundo e imperceptivel
# para quem retoma e irrisorio para quem espera horas.
INTERVALO = 0.5


def pausado():
    """Verdadeiro enquanto o arquivo de pausa existir."""
    return os.path.exists(ARQUIVO)


def pedir(motivo=''):
    """Cria o arquivo. Devolve o caminho, para quem quiser mostrar."""
    with open(ARQUIVO, 'w', encoding='utf-8') as fh:
        fh.write(f'{motivo or "pausado"}\n{time.strftime("%d/%m %H:%M:%S")}\n')
    return ARQUIVO


def retomar():
    """Apaga o arquivo. Silencioso se ja nao existia."""
    try:
        os.remove(ARQUIVO)
        return True
    except OSError:
        return False


def espera(rotulo='', avisa=None):
    """Segura aqui enquanto o arquivo existir. Devolve os segundos parados.

    `avisa(texto)` e chamado uma vez ao entrar e uma vez ao sair — so quando
    houve pausa de verdade. Nao imprime nada por conta propria porque isto roda
    dentro de trabalhadores em paralelo, onde dezenas de mensagens iguais so
    atrapalhariam; quem chama decide se vale falar.
    """
    if not pausado():
        return 0.0
    t0 = time.time()
    if avisa:
        avisa(f'pausado{" em " + rotulo if rotulo else ""} — apague '
              f'{ARQUIVO} para retomar')
    while pausado():
        time.sleep(INTERVALO)
    parado = time.time() - t0
    if avisa:
        avisa(f'retomando apos {parado/60:.1f} min parado')
    return parado
