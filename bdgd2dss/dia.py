# -*- coding: utf-8 -*-
"""Quando uma subestacao do `energia_dia.json` conta como medida.

POR QUE UM MODULO PARA UMA LINHA. A regra "dia parcial nao e o dia" morava so
no `validador.py` (achados 29 e 64). O `valida_perdas.py` e o
`valida_balanco.py` liam o mesmo arquivo e somavam TODAS as subestacoes — as
de 80 passos em 96, e ate uma cujos 96 passos tinham perda maior que a energia
que entrava (achado 67). Tres leitores, uma regra, aplicada em um so.

Regra que precisa ser lembrada em cada lugar e regra que um deles esquece.
Aqui ela tem um nome, e os tres chamam o nome.
"""


def completo(x):
    """Se a subestacao fechou os passos que pediu.

    Um passo sai da conta quando nao converge, quando devolve mais geracao do
    que existe (achado 64) ou quando dissipa mais do que entra (achado 67).
    Com passos faltando, a energia e a perda cobrem uma fracao desconhecida do
    dia — e a razao entre elas, que e o que se publica, deixa de ser do dia.
    """
    if not x:
        return False
    passos = x.get('passos') or 0
    return passos > 0 and (x.get('passos_ok') or 0) >= passos


def medidas(modelo):
    """So as subestacoes que contam, e quantas ficaram de fora."""
    dentro = [x for x in (modelo or []) if completo(x)]
    return dentro, len(modelo or []) - len(dentro)
