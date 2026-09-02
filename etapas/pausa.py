# -*- coding: utf-8 -*-
"""PAUSAR e RETOMAR um ciclo em andamento, sem perder o que ja foi feito.

    python pausa.py              abre o formulario, como os demais
    python pausa.py --pausar     pausa
    python pausa.py --retomar    retoma
    python pausa.py --estado     so diz como esta, sem mexer
    python pausa.py --motivo X   alterna e grava o motivo

Serve para quando a maquina e necessaria para outra coisa. As tarefas que ja
estao em andamento terminam — a granularidade e uma subestacao — e nenhuma
nova comeca enquanto a pausa durar. Retomar e imediato.

NAO E CANCELAR. Nada e descartado, nenhum arquivo fica pela metade, e o tempo
parado nao entra na conta de desempenho do `regerar`. Se a maquina for
desligada durante a pausa, o ciclo retoma de onde estava na proxima vez, que e
o mesmo comportamento de sempre.
"""
import argparse
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
# A RAIZ E O PAI, desde a mudanca de 02/09/2026: estes executaveis
# sairam da raiz para `etapas/`, e `AQUI` deixou de ser onde mora o
# pacote `bdgd2dss`.
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import pausa                             # noqa: E402


def estado():
    if not pausa.pausado():
        return 'rodando'
    try:
        with open(pausa.ARQUIVO, encoding='utf-8') as fh:
            corpo = [l.strip() for l in fh if l.strip()]
        return f'PAUSADO desde {corpo[-1]}' if corpo else 'PAUSADO'
    except OSError:
        return 'PAUSADO'


def _painel():
    from bdgd2dss import interativo
    ligado = pausa.pausado()
    v = interativo.formulario('pausa', 'Pausar o ciclo', [
        {'chave': 'acao', 'tipo': 'opcao', 'rotulo': 'O que fazer',
         'padrao': 'retomar' if ligado else 'pausar',
         'valores': ['pausar', 'retomar', 'estado']},
        {'chave': 'motivo', 'tipo': 'texto', 'rotulo': 'Motivo', 'padrao': '',
         'dica': 'opcional; fica gravado no arquivo, para quem vier depois '
                 'saber por que estava parado'},
    ], ajuda=f'Agora: {estado()}.\n\nPausar nao cancela nada. As subestações '
             f'em andamento terminam, nenhuma nova começa, e retomar continua '
             f'de onde parou. O tempo parado não entra na conta de desempenho.')
    if not v:
        return False
    sys.argv += ['--' + v['acao']]
    if v['motivo']:
        sys.argv += ['--motivo', v['motivo']]
    return True


def main():
    # Sem argumento nenhum abre o formulario, como todo executavel do projeto —
    # e assim que o `Validator.py` dispara. Quem esta no terminal usa as opcoes, que
    # sao mais rapidas do que abrir janela para uma decisao de uma palavra.
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--pausar', action='store_true', help='pausa o ciclo')
    ap.add_argument('--retomar', action='store_true', help='retoma o ciclo')
    ap.add_argument('--estado', action='store_true',
                    help='so informa como esta, sem mexer')
    ap.add_argument('--motivo', default='', metavar='TEXTO',
                    help='fica gravado no arquivo de pausa')
    a = ap.parse_args()

    if a.estado:
        print(estado())
        return
    # Sem dizer qual das duas, alterna: quem digita este comando quer o
    # contrario do que esta acontecendo agora.
    if a.pausar or (not a.retomar and not pausa.pausado()):
        pausa.pedir(a.motivo)
        print(f'PAUSADO em {time.strftime("%H:%M:%S")}.')
        print('As subestações em andamento terminam; nenhuma nova começa.')
        print('Para retomar:  python pausa.py --retomar')
    elif pausa.retomar():
        print(f'Retomado em {time.strftime("%H:%M:%S")}.')
    else:
        print('Não estava pausado.')


if __name__ == '__main__':
    main()
