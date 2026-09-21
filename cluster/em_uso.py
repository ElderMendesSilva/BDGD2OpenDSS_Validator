# -*- coding: utf-8 -*-
"""Quantos nucleos e GB os NOSSOS jobs ja tomam, lendo `qstat -f` pela entrada.

    qstat -f $(qstat -u $USER | awk 'NR>5{print $1}') | python cluster/em_uso.py
    -> "48 144"   (nucleos, GB)

POR QUE EXISTE. O `submeter_todas.sh` contava com `qstat -u $USER -f`, e neste
PBS o `-u` faz o `-f` ser ignorado: sai a tabela curta, sem nenhum
`Resource_List.ncpus`, e a soma dava ZERO em toda rodada. Descoberto em
21/09/2026, com o censo de lacos (16 nucleos) e uma prova da SP (32 nucleos)
rodando: o plano da V37 dizia "0 comprometidos" e pedia 160 de 160.

QUAIS ESTADOS CONTAM: R (rodando), Q (na fila) e W (esperando a hora da
rampa). H NAO conta: na submissao em ondas, H e a proxima base de uma
corrente, que so comeca quando a anterior termina — soma-la contaria a mesma
corrente varias vezes. E a memoria conta junto, porque o orcamento tem dois
tetos e o de GB e o que estoura em silencio.
"""
import re
import sys

CONTAM = {'R', 'Q', 'W'}
_UNIDADE = {'b': 1 / 1024 ** 3, 'kb': 1 / 1024 ** 2, 'mb': 1 / 1024, 'gb': 1.0,
            'tb': 1024.0}


def _gb(valor):
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*([kmgt]?b)\s*$', valor or '', re.I)
    if not m:
        return 0.0
    return float(m.group(1)) * _UNIDADE[m.group(2).lower()]


def somar(texto):
    """`(nucleos, gb)` dos jobs em R, Q ou W no texto do `qstat -f`."""
    nucleos, gb = 0, 0.0
    job = None

    def fecha(j):
        nonlocal nucleos, gb
        if j and j.get('estado') in CONTAM:
            nucleos += j.get('ncpus', 0)
            gb += j.get('gb', 0.0)

    for linha in texto.splitlines():
        if linha.startswith('Job Id:'):
            fecha(job)
            job = {}
            continue
        if job is None or '=' not in linha:
            continue
        chave, valor = (x.strip() for x in linha.split('=', 1))
        if chave == 'job_state':
            job['estado'] = valor
        elif chave == 'Resource_List.ncpus':
            job['ncpus'] = int(valor) if valor.isdigit() else 0
        elif chave == 'Resource_List.mem':
            job['gb'] = _gb(valor)
    fecha(job)
    return nucleos, int(round(gb))


if __name__ == '__main__':
    n, g = somar(sys.stdin.read())
    print(n, g)
