# -*- coding: utf-8 -*-
"""Quanto ocupa cada `.gdb` — medido no no de calculo, nunca no de acesso.

O planejador de rodada precisa do tamanho de cada base para dimensionar o job:
`.gdb` maior ganha mais nucleo e mais memoria. Medir e barato em CPU e caro em
I/O de metadado — sao ~20 mil arquivos espalhados por 97 pastas, e cada um pede
um `stat` ao sistema de arquivos.

POR QUE ISTO E UM MODULO, E NAO TRES LINHAS NO SUBMISSOR. A regra de 28/08/2026
diz que o head node do Ubiratan nao processa. Antes, a medicao acontecia dentro
do submissor, que roda justamente la — e a unica protecao era um cache que, se
alguem apagasse ou se chegasse base nova, deixava a varredura voltar em
silencio. Regra que depende de um arquivo sobreviver nao e regra.

Agora a medicao RECUSA rodar fora de um job do gerenciador de fila. Quem estiver
no no de acesso le o cache; se faltar base nela, o processo para e diz como
construi-la. Uma regra que o codigo faz valer nao precisa que ninguem lembre.
"""
import json
import os

from bdgd2dss import escrita

# O cache vive no repositorio, ao lado das demais medicoes. Nao entra no git:
# e resultado de execucao, refeito por um comando registrado.
CACHE = os.path.join('medicoes', 'tamanho_bases.json')


class PrecisaDeNo(RuntimeError):
    """Faltou base no cache e nao ha no de calculo para medir agora."""


def dentro_de_job():
    """Estamos dentro de um job do gerenciador de fila?

    `PBS_ENVIRONMENT` e posta pelo PBS/Torque so no ambiente de execucao do
    job — no no de acesso ela nao existe, mesmo com o `qsub` a mao. `SLURM_JOB_ID`
    fica junto porque custa uma linha e o proximo cluster pode ser outro.
    """
    return any((os.environ.get(v) or '').strip()
               for v in ('PBS_ENVIRONMENT', 'PBS_JOBID', 'SLURM_JOB_ID'))


def medir(caminho):
    """GB ocupados por uma `.gdb`, somando o tamanho de cada arquivo dentro."""
    return sum(os.path.getsize(os.path.join(d, f))
               for d, _, fs in os.walk(caminho) for f in fs) / 2 ** 30


def carregar(cache=CACHE):
    """O cache, ou vazio. Arquivo corrompido vale como vazio, e nao como erro:
    um JSON truncado por queda no meio da escrita nao pode custar a rodada."""
    try:
        with open(cache, encoding='utf-8') as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def gravar(tam, cache=CACHE):
    d = os.path.dirname(cache)
    if d:
        os.makedirs(d, exist_ok=True)
    # `newline=` explicito: o cache e lido nas duas maquinas, e fim de linha
    # do sistema faria o mesmo arquivo diferir entre Linux e Windows.
    with open(cache, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump(tam, fh, indent=1, sort_keys=True)


def tamanhos(caminhos, cache=CACHE, pode_medir=None):
    """`{caminho: gb}` para `caminhos`, medindo so o que faltar no cache.

    `pode_medir` existe para o teste; em producao quem decide e `dentro_de_job`.
    Levanta `PrecisaDeNo` quando falta base e nao se pode medir — de proposito,
    porque a alternativa e varrer o no de acesso, que e o que a regra proibe.

    Devolve `(tam, novas)`: `novas` e quantas foram medidas agora, para o
    chamador dizer ao usuario que a proxima execucao ja sai do cache.
    """
    if pode_medir is None:
        pode_medir = dentro_de_job()
    tam = carregar(cache)
    faltam = [c for c in caminhos if c not in tam]
    if faltam and not pode_medir:
        raise PrecisaDeNo(
            '%d base(s) sem tamanho no cache e este no nao pode medir.\n'
            '   Falta:  %s%s\n'
            '   Meca num no de calculo:\n'
            '       bash cluster/submeter_todas.sh --medir\n'
            '   (o head node nao processa; ver a regra de 28/08/2026)'
            % (len(faltam), ', '.join(os.path.basename(c) for c in faltam[:3]),
               ' ...' if len(faltam) > 3 else ''))
    for c in faltam:
        tam[c] = medir(c)
    if faltam:
        gravar(tam, cache)
    return {c: tam[c] for c in caminhos}, len(faltam)
