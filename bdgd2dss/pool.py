# -*- coding: utf-8 -*-
"""Encerrar um ProcessPoolExecutor sem esperar para sempre.

POR QUE EXISTE. Sair de um `with ProcessPoolExecutor(...)` e
`shutdown(wait=True)`: esperar cada processo trabalhador morrer, sem prazo.
Quando o trabalhador nao morre, a etapa inteira fica pendurada DEPOIS de ja ter
feito todo o trabalho.

Medido na V16 da Cemig-D. O `verifica` processou as 413 subestacoes -- os
indices [1/413] a [413/413] estao todos no log -- e foi morto pelo limite de
6 h sem escrever nada. E a prova de que os trabalhadores e que travam veio
depois: os OITO processos criados as 04:37:09 continuavam vivos as 14:30, seis
horas depois de o pai ter sido morto.

O suspeito e o motor COM, que o `verifica` roda junto com o `capi`: servidor
COM que nao solta segura o processo do trabalhador vivo.

Duas defesas, e as duas sao necessarias:

  1. gravar o resultado ANTES de sair do `with` -- feito em cada etapa, e
     coberto por `testes/test_grava_antes_de_esperar.py`;
  2. nao esperar para sempre -- e este modulo.

O que este modulo NAO faz: nao tenta consertar o motivo de o trabalhador nao
morrer. O trabalho ja terminou e o resultado ja esta em disco; o processo que
sobra nao tem mais nada a entregar, e mata-lo nao perde nada.
"""
import time

PRAZO = 20.0             # segundos de espera educada antes de forcar


def encerrar(ex, prazo=PRAZO, log=None):
    """Fecha o pool `ex`, matando quem nao sair sozinho dentro de `prazo`.

    Devolve quantos trabalhadores precisaram ser mortos. Nunca levanta: uma
    falha aqui nao pode derrubar uma etapa que ja produziu o resultado.
    """
    def _diz(m):
        if log:
            log(m)

    # A LISTA VEM ANTES DO SHUTDOWN, e a ordem aqui nao e estilo.
    # `ProcessPoolExecutor.shutdown` faz `self._processes = None` no fim.
    # Pegar a lista depois devolvia None, e o `.values()` explodia com
    # `AttributeError: 'NoneType' object has no attribute 'values'` —
    # derrubando a etapa INTEIRA no exato ponto em que este modulo existe
    # para nao derrubar nada. Pego pelo canario de Roraima em 23/08/2026,
    # com `ligacao` e `ampacidade` falhando depois de terem feito o trabalho.
    #
    # `getattr(..., {}) or {}` porque o atributo pode estar AUSENTE (outro
    # executor) ou PRESENTE E None (o nosso, depois de um shutdown anterior).
    procs = list((getattr(ex, '_processes', None) or {}).values())

    try:
        ex.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass

    if not procs:
        return 0

    fim = time.time() + prazo
    while time.time() < fim and any(p.is_alive() for p in procs):
        time.sleep(0.2)

    mortos = 0
    for p in procs:
        if not p.is_alive():
            continue
        try:
            p.terminate()
            p.join(2)
            if p.is_alive():
                p.kill()
                p.join(2)
            mortos += 1
        except Exception:
            pass

    if mortos:
        _diz(f'{mortos} trabalhador(es) nao encerraram em {prazo:.0f}s e '
             f'foram mortos — o resultado ja estava em disco. Ver '
             f'bdgd2dss/pool.py')
    return mortos
