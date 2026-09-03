# -*- coding: utf-8 -*-
"""Onde mora o MODELO_QUEBRADO — a maior classe de reprovação do projeto.

`MODELO_QUEBRADO` soma 1.250 das 4.078 subestações da safra 2025 (achado 24),
e o rótulo esconde **quatro defeitos diferentes** que o `diagnostico.py`
empilha na mesma gaveta, em ordem de precedência:

    1. não compila           o `.dss` não é aceito pelo motor
    2. não converge          compila e o fluxo não fecha
    3. nós com NaN           converge com potência indefinida — ilha sem fonte
    4. carga sem tensão      UMA carga já basta

Os três primeiros são falhas do modelo; o quarto é um fato sobre o cadastro, e
é quase certo que ele domine a contagem. Tratá-los como um bloco só faz a maior
classe de reprovação parecer intratável, quando provavelmente é uma classe
grande e fácil ao lado de três pequenas e difíceis.

Roda LOCALMENTE sobre os `validacao.json` — ver `v26_x_v27.py` para o comando
que os traz do cluster.

    python analise/quebrados.py [sufixo]        (padrão: V27)
"""
import collections
import glob
import io
import json
import os
import sys


def causa(r):
    return str(r.get('causa') or '?').split('[')[0].strip()


def qual_defeito(r):
    """O motivo REAL, na mesma ordem de precedência do `diagnostico.py`."""
    if not r.get('compila'):
        return 'nao compila'
    if not r.get('converge'):
        return 'nao converge'
    if r.get('nos_nan'):
        return 'nos com NaN'
    if r.get('cargas_sem_tensao'):
        return 'carga sem tensao'
    return 'outro'


def main(sufixo='V27'):
    arquivos = sorted(glob.glob('MODELOS_*_%s/validacao.json' % sufixo))
    if not arquivos:
        print('nenhum MODELOS_*_%s/validacao.json aqui' % sufixo)
        return 2

    motivos = collections.Counter()
    por_base = collections.Counter()
    total = quebrados = 0
    faixas = collections.Counter()
    # quanto de carga se perde, e nao so quantas subestacoes sao marcadas
    cargas_mortas = cargas_totais = 0
    piores = []

    for f in arquivos:
        base = os.path.basename(os.path.dirname(f)).replace('MODELOS_', '')
        base = base.rsplit('_' + sufixo, 1)[0]
        try:
            dados = json.load(io.open(f, encoding='utf-8'))
        except Exception:                                    # noqa: BLE001
            continue
        for r in dados:
            total += 1
            if causa(r) != 'MODELO_QUEBRADO':
                continue
            quebrados += 1
            m = qual_defeito(r)
            motivos[m] += 1
            por_base[base] += 1
            if m == 'carga sem tensao':
                mortas = r.get('cargas_sem_tensao') or 0
                n = r.get('n_cargas') or 0
                cargas_mortas += mortas
                cargas_totais += n
                p = (100.0 * mortas / n) if n else None
                # A FRACAO E QUE DECIDE O TRATAMENTO. Uma carga em dez mil e
                # ramal solto; metade da subestacao e rede que nao fecha.
                if p is None:
                    faixas['sem contagem'] += 1
                elif mortas == 1:
                    faixas['exatamente 1 carga'] += 1
                elif p < 0.1:
                    faixas['menos de 0,1%'] += 1
                elif p < 1:
                    faixas['0,1% a 1%'] += 1
                elif p < 10:
                    faixas['1% a 10%'] += 1
                else:
                    faixas['acima de 10%'] += 1
                piores.append((p or 0, mortas, n, base, r.get('modelo')))

    print('subestacoes: %s   MODELO_QUEBRADO: %s (%.1f%%)'
          % (f'{total:,}', f'{quebrados:,}', 100.0 * quebrados / total))
    print()
    print('POR QUE, na ordem de precedencia do classificador:')
    for m, n in motivos.most_common():
        print('  %-20s %6d  %5.1f%% dos quebrados' % (m, n, 100.0 * n / quebrados))

    if faixas:
        print()
        print('DOS QUE SAO "carga sem tensao", QUANTA carga se perde:')
        ordem = ['exatamente 1 carga', 'menos de 0,1%', '0,1% a 1%',
                 '1% a 10%', 'acima de 10%', 'sem contagem']
        soma = sum(faixas.values())
        for k in ordem:
            if faixas[k]:
                print('  %-20s %6d  %5.1f%%' % (k, faixas[k],
                                                100.0 * faixas[k] / soma))
        if cargas_totais:
            print('  --')
            print('  cargas sem tensao: %s de %s (%.3f%%) nessas subestacoes'
                  % (f'{cargas_mortas:,}', f'{cargas_totais:,}',
                     100.0 * cargas_mortas / cargas_totais))

    print()
    print('AS 12 BASES QUE MAIS CONCENTRAM:')
    for b, n in por_base.most_common(12):
        print('  %-24s %5d' % (b, n))

    print()
    print('AS 10 PIORES SUBESTACOES (fracao de carga sem tensao):')
    for p, mortas, n, base, modelo in sorted(piores, reverse=True)[:10]:
        print('  %-22s %-14s %6.1f%%  (%s de %s cargas)'
              % (base, str(modelo)[:14], p, f'{mortas:,}', f'{n:,}'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'V27'))
