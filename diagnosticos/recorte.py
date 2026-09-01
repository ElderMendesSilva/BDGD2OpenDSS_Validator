# -*- coding: utf-8 -*-
"""O recorte por subestação parte a rede? Mede na BDGD, sem simular.

    python diagnosticos/recorte.py --bases $BDGD2DSS_BASES \\
        --so LT CEREJ5352 --saida-json medicoes/recorte.json

POR QUE A PERGUNTA. O achado 12 mostrou que a fragmentação é característica POR
DISTRIBUIDORA — 40 de 76 bases com mediana ZERO de ramos isolados por km, e a
Light com 45,8. O conversor é o mesmo para as 97, então o gatilho está no dado
ou na interação dele com uma premissa nossa.

A PREMISSA SUSPEITA é o recorte. O `converter.py` monta um modelo POR
SUBESTAÇÃO e filtra a SSDMT pelos CTMTs daquela SE
(`ler_filtrado('SSDMT', 'CTMT', ctmts, ...)`). Um trecho cujo CTMT pertence a
outra subestação fica de fora — e se ele era o caminho de ligação, o que estava
depois dele vira ramo isolado.

O TESTE, e ele não precisa de OpenDSS: um PAC (ponto de conexão) tocado por
trechos de DUAS subestações diferentes é um ponto de corte. Ali o recorte
separa o que a rede declara junto. Contá-los por base diz se o mecanismo
explica a diferença entre a Light e uma base limpa.

O QUE ESTE NÚMERO NÃO É: prova de defeito. Rede de distribuição tem pontos de
transferência entre subestações por projeto, normalmente com chave aberta. O
que interessa é a MAGNITUDE comparada entre bases — dezenas é operação normal,
dezenas de milhares é outra coisa.
"""
import argparse
import collections
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import escrita                            # noqa: E402
from bdgd2dss.leitor import BDGD, txt                    # noqa: E402


def cortes_da_base(caminho):
    """Quantos PACs a divisão por subestação separa.

    Devolve o dicionário do resultado. `pacs_multi_se` é a medida principal:
    pontos de conexão tocados por trechos de mais de uma subestação.
    """
    b = BDGD(caminho, verbose=False)

    # CTMT -> SUB, que é o mapa que define o recorte
    c = b.ler('CTMT', ['COD_ID', 'SUB'])
    de_ctmt = {}
    for i in range(len(c['COD_ID'])):
        de_ctmt[txt(c['COD_ID'][i])] = txt(c['SUB'][i])

    m = b.ler('SSDMT', ['PAC_1', 'PAC_2', 'CTMT'])
    por_pac = collections.defaultdict(set)
    sem_ctmt = 0
    n = len(m['CTMT'])
    for i in range(n):
        se = de_ctmt.get(txt(m['CTMT'][i]))
        if not se:
            sem_ctmt += 1
            continue
        for campo in ('PAC_1', 'PAC_2'):
            p = txt(m[campo][i])
            if p:
                por_pac[p].add(se)

    multi = sum(1 for v in por_pac.values() if len(v) > 1)
    return {
        'trechos_mt': n,
        'trechos_sem_ctmt_conhecido': sem_ctmt,
        'pacs': len(por_pac),
        'pacs_multi_se': multi,
        'pct_pacs_multi_se': round(100.0 * multi / max(1, len(por_pac)), 3),
        'subestacoes_no_ctmt': len(set(de_ctmt.values())),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', ''))
    ap.add_argument('--so', nargs='*', default=None, help='tags')
    ap.add_argument('--saida-json', default=os.path.join('medicoes',
                                                         'recorte.json'))
    a = ap.parse_args(argv)

    import regerar_v10 as rg
    so = set(a.so) if a.so else None
    bases = [(t, c) for t, c, _ in rg.descobrir(a.bases) if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada', file=sys.stderr)
        return 1

    saida, erros = [], 0
    print('%-20s %10s %10s %12s %9s' %
          ('base', 'trechos', 'PACs', 'PACs multi-SE', '%'))
    for tag, cam in bases:
        try:
            d = cortes_da_base(cam)
        except Exception as e:                          # noqa: BLE001
            print('%-20s ERRO: %s' % (tag, str(e)[:70]), flush=True)
            erros += 1
            continue
        d['base'] = tag
        saida.append(d)
        print('%-20s %10s %10s %12s %8.3f%%'
              % (tag, f"{d['trechos_mt']:,}", f"{d['pacs']:,}",
                 f"{d['pacs_multi_se']:,}", d['pct_pacs_multi_se']),
              flush=True)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'bases': saida}, fh, ensure_ascii=False, indent=1)
    print('\n%d bases medidas, %d com erro  ->  %s'
          % (len(saida), erros, a.saida_json))
    # Medir nada nao e medir — ver `diagnosticos/ferro.py`, mesmo defeito.
    if not saida:
        print('nenhuma base medida: veja os erros acima', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
