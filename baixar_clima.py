# -*- coding: utf-8 -*-
"""Baixa o clima de cada base a partir dos centroides medidos no no.

    python baixar_clima.py                       # so mostra o que falta
    python baixar_clima.py --rodar
    python baixar_clima.py --rodar --mes 1 --so CMIG SP

SEGUNDO PASSO DE DOIS. O primeiro (`cluster/centroides.py`) roda no cluster,
onde estao as `.gdb`, e publica `medicoes/centroides.json`. Este roda numa
maquina com internet e transforma coordenada em cache de clima.

A separacao nao e capricho: a coordenada so existe na `.gdb` e o no de calculo
nao alcanca a NASA POWER. Juntar os dois passos exigiria internet no no ou as
`.gdb` na maquina de casa, e nenhuma das duas e verdade.

POR QUE ISTO IMPORTA — achado 4. Irradiancia e temperatura comandam o derating
do painel. Sem cache, o conversor cai no perfil SINTETICO, que e honesto (ele
se declara em `clima_fonte`) mas ~23% otimista e simetrico. Enquanto for assim,
nenhuma conclusao sobre geracao distribuida se sustenta.

NAO REBAIXA VERDADE POR ENGANO: base que ja tem cache e PULADA, e so
`--refazer` sobrescreve. E uma falha de rede numa base nao derruba as outras —
a proxima execucao pega o que faltou, porque o que existe e pulado.
"""
import argparse
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from bdgd2dss import clima                             # noqa: E402

CENTROIDES = os.path.join('medicoes', 'centroides.json')

# A NASA POWER e gratuita e sem chave, e por isso mesmo se pede licenca: uma
# pausa entre consultas evita parecer varredura automatizada. 97 bases a 2s
# custam tres minutos, o que nao e problema para algo que se faz uma vez.
PAUSA = 2.0


def pendentes(centroides, mes, raiz, refazer=False, so=None):
    """(tag, dist, lon, lat) das bases que ainda precisam de download."""
    fila, sem_coord, prontas = [], [], []
    for tag, d in sorted(centroides.items()):
        if so and tag not in so:
            continue
        if d.get('erro') or d.get('lat') is None:
            sem_coord.append((tag, d.get('erro') or 'sem coordenada'))
            continue
        dest = clima.caminho_cache(raiz, d['dist'], mes)
        if os.path.exists(dest) and not refazer:
            prontas.append(tag)
            continue
        fila.append((tag, d['dist'], d['lon'], d['lat']))
    return fila, prontas, sem_coord


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--centroides', default=CENTROIDES)
    ap.add_argument('--mes', type=int, default=1)
    ap.add_argument('--ano', type=int, default=2024)
    ap.add_argument('--so', nargs='*', default=None, help='tags')
    ap.add_argument('--refazer', action='store_true',
                    help='rebaixa mesmo quem ja tem cache')
    ap.add_argument('--rodar', action='store_true',
                    help='sem isto, apenas mostra o que seria baixado')
    ap.add_argument('--pausa', type=float, default=PAUSA)
    a = ap.parse_args(argv)

    if not os.path.exists(a.centroides):
        print('nao achei %s\n'
              '   ele sai do no, onde estao as .gdb:\n'
              '       bash cluster/submeter_centroides.sh --rodar'
              % a.centroides, file=sys.stderr)
        return 1
    with open(a.centroides, encoding='utf-8') as fh:
        cen = json.load(fh).get('bases') or {}

    fila, prontas, sem = pendentes(cen, a.mes, RAIZ, a.refazer,
                                   set(a.so) if a.so else None)
    print('mes %02d/%d  |  %d ja em cache  |  %d a baixar  |  %d sem coordenada'
          % (a.mes, a.ano, len(prontas), len(fila), len(sem)))
    for tag, m in sem:
        print('  sem coordenada: %-22s %s' % (tag, m))
    if not a.rodar:
        print('\nnada baixado. Para baixar:  python baixar_clima.py --rodar')
        return 0

    ok = falhou = 0
    for i, (tag, dist, lon, lat) in enumerate(fila, 1):
        dest = clima.caminho_cache(RAIZ, dist, a.mes)
        try:
            d = clima.baixar(lon, lat, a.mes, a.ano)
            clima.gravar(d, dest)
            print('  %3d/%d %-22s dist %-8s %.2f kWh/m2/dia  %.1f a %.1f C'
                  % (i, len(fila), tag, dist, d['kwh_m2_dia'],
                     min(d['ambiente_c']), max(d['ambiente_c'])), flush=True)
            ok += 1
        except Exception as e:                         # noqa: BLE001
            # Falha de rede numa base nao pode custar as outras 96. Quem falhou
            # nao tem cache, e a proxima execucao a pega — as prontas sao
            # puladas, entao repetir o comando e barato e seguro.
            print('  %3d/%d %-22s FALHOU: %s'
                  % (i, len(fila), tag, str(e)[:70]), flush=True)
            falhou += 1
        if a.pausa and i < len(fila):
            time.sleep(a.pausa)

    print('\n%d baixadas, %d falharam. Repita o comando para tentar de novo '
          'so as que faltam.' % (ok, falhou))
    print('O cache vai para o git (`dados/` e versionado) — commite e o no o le.')
    return 0 if not falhou else 1


if __name__ == '__main__':
    sys.exit(main())
