# -*- coding: utf-8 -*-
"""ORDEM DE DESPACHO das subestacoes nas etapas paralelas.

As etapas que rodam em paralelo submetiam na ordem em que as pastas aparecem,
que e a alfabetica. As subestacoes sao MUITO desiguais — na EQPA a maior custa
4.208 vezes a menor — e com tarefas assim a alfabetica desperdiça: se uma
grande cai perto do fim da fila, os outros trabalhadores terminam e ficam
parados esperando so por ela.

Despachar a maior primeiro e a regra classica para isso (LPT).

MEDIDO DE PONTA A PONTA, o `validador` sobre as 119 subestacoes da EQPA, com 8
trabalhadores, a maquina livre e as ordens alternadas para nao premiar o cache:

| ordem | 1a | 2a |
|---|---|---|
| maior primeiro | **154 s** | **159 s** |
| alfabetica | 181 s | 181 s |

**13,5%**, e os quatro `validacao.json` com o mesmo MD5.

A SIMULACAO PROMETIA 27,4%, E ERA OTIMISTA. Ela usava o custo de COMPILAR como
proxy do custo da tarefa, e a tarefa real e compilar mais as verificacoes — que
sao bem mais parecidas entre subestacoes do que a compilacao. Menos
desigualdade, menos ganho. Fica registrado porque a diferenca entre o simulado
e o medido e a informacao, nao o erro: 13,5% de graca continua valendo, e o
numero honesto e o do relogio.

NAO E PRECISO MEDIR O CUSTO PARA ORDENAR. Os bytes da pasta em disco sao proxy
suficiente: correlacao de 0,938 com o tempo de compilacao, e a simulacao com o
proxy da EXATAMENTE o mesmo tempo que a simulacao com o custo real, nos tres
numeros de trabalhadores. Um `stat` por arquivo e barato perto de compilar o
modelo.

ISTO NAO MUDA NENHUM NUMERO. Muda so a ordem em que as tarefas entram na fila.
Toda etapa paralela ja reimpoe a ordem original na saida — justamente para que
o arquivo gerado nao dependa de quem terminou primeiro — e por isso a ordem de
despacho ja era livre. Estava sendo desperdiçada.
"""
import os


def tamanho(caminho):
    """Bytes de uma pasta de modelo. Pasta ausente ou ilegivel vale zero.

    Zero e o valor certo para o caso ruim: manda a pasta duvidosa para o fim
    da fila, onde ela custa menos se de fato estiver quebrada.
    """
    try:
        return sum(os.path.getsize(os.path.join(d, f))
                   for d, _, fs in os.walk(caminho) for f in fs)
    except OSError:
        return 0


def maior_primeiro(itens, pasta_de):
    """Copia de `itens` ordenada da maior subestacao para a menor.

    `pasta_de(item)` devolve o caminho da pasta daquele item — os chamadores
    guardam a subestacao de formas diferentes (nome solto, par com o MASTER,
    tripla com os passos), e nenhum precisa mudar por causa disto.

    O desempate e pelo caminho, e nao pela ordem de entrada: assim duas
    rodadas da mesma pasta despacham na mesma ordem, o que mantem os logs
    comparaveis entre uma execucao e outra.
    """
    marcado = [(-tamanho(pasta_de(x)), pasta_de(x), i, x)
               for i, x in enumerate(itens)]
    marcado.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[3] for t in marcado]
