# -*- coding: utf-8 -*-
"""De qual código veio ESTA entrada — o carimbo que a retomada exige.

POR QUE EXISTE. Retomar é sempre melhor do que recomeçar: uma queda no meio da
noite não pode custar a noite inteira. Mas retomar mistura duas gerações de
código na mesma pasta, e até aqui nada registrava isso.

O QUE CUSTOU. Em 09/09/2026, medindo a MOG02 no cluster depois de corrigir o
achado 63, o `energia.py` reaproveitou a medida antiga com uma linha discreta —
"1 subestacoes ja medidas — retomando" — e eu li o `tail` sem vê-la. Comparei
72,265% (modelo velho) com 14,58% (modelo novo) e **concluí que as duas
máquinas discordavam**, chegando a escrever que a garantia de determinismo do
CHANGELOG estava quebrada. Com `--refazer`, as duas davam 333.740,7 kWh. O
erro não foi do cache: foi de o cache não ter dito de quando era.

O `_procedencia.json` da rodada não resolve isto. Ele carimba a PASTA com o
commit de quem rodou por último — e numa retomada esse commit vale para as
subestações novas e mente sobre as antigas.

Aqui o carimbo é POR ENTRADA: cada `resumo.json` e cada item do
`energia_dia.json` leva o commit que o gerou. Depois, `mistura()` diz numa
linha se a pasta tem uma geração ou várias.

O commit vem do git; quando o git não responde — ele existe no nó de acesso e
não no de cálculo, e foi assim que a V21 inteira saiu sem commit —, vale o
`BDGD2DSS_COMMIT` que a submissão passou por `-v`.
"""
import os
import subprocess

_LEMBRADO = None


def commit(curto=True):
    """O commit deste código, ou `''` quando não há como saber.

    Medido uma vez por processo: são dezenas de subestações por rodada, e
    `git rev-parse` em cada uma seria um subprocesso por subestação.
    """
    global _LEMBRADO
    if _LEMBRADO is None:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        valor = ''
        try:
            p = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=raiz,
                               capture_output=True, text=True, timeout=30)
            if p.returncode == 0:
                valor = p.stdout.strip()
        except Exception:                                        # noqa: BLE001
            valor = ''
        if not valor:
            valor = os.environ.get('BDGD2DSS_COMMIT', '').strip()
        _LEMBRADO = valor
    return _LEMBRADO[:10] if (curto and _LEMBRADO) else _LEMBRADO


def marca():
    """O que se grava dentro de cada entrada."""
    return commit() or 'desconhecido'


def mistura(entradas, campo='commit'):
    """Quais commits estão dentro desta pasta, do mais frequente ao menos.

    Devolve `[(commit, quantas)]`. Mais de um item significa que a pasta é
    uma COLCHA: parte veio de um código, parte de outro, e nenhum número
    tirado dela pertence a uma geração só.
    """
    contagem = {}
    for e in entradas or ():
        v = (e or {}).get(campo) or 'desconhecido'
        contagem[v] = contagem.get(v, 0) + 1
    return sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))


def aviso(entradas, quantas_reaproveitadas, o_que='subestacoes', campo='commit'):
    """As linhas que a retomada tem de GRITAR, ou `[]` quando não há retomada.

    Não é decoração. A linha discreta de antes existia e passou despercebida
    num `tail -3`; esta ocupa três linhas e nomeia o risco.
    """
    if not quantas_reaproveitadas:
        return []
    atual = commit() or 'desconhecido'
    quais = mistura(entradas, campo)
    velhos = [(c, n) for c, n in quais if c != atual]
    linhas = ['',
              f'  !! RETOMADA: {quantas_reaproveitadas} {o_que} vieram do '
              f'disco e NAO foram recalculadas.']
    if velhos:
        detalhe = ', '.join(f'{n} de {c}' for c, n in velhos)
        linhas += [
            f'  !! CODIGO MISTURADO: {detalhe}; o resto e de {atual}.',
            '  !! Numero comparado entre geracoes diferentes nao mede mudanca '
            'de codigo.',
            '  !! Para uma medida de uma geracao so, use --refazer.']
    else:
        linhas.append(f'  !! Todas do mesmo commit ({atual}) — comparavel.')
    linhas.append('')
    return linhas
