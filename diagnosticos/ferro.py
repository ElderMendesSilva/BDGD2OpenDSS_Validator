# -*- coding: utf-8 -*-
"""Quanto da perda modelada é FERRO — a parcela que não depende de carga.

    python diagnosticos/ferro.py --bases $BDGD2DSS_BASES \\
        --resultados resultados/v24 --saida-json medicoes/ferro.json

POR QUE A PERGUNTA. O achado 10 mede um viés: nas 38 bases com declaração
original e plausível, a perda modelada fica 1,42x acima da declarada pela
distribuidora. O viés é real (sobrevive aos filtros dos achados 8 e 9) e não
cresce com o comprimento do alimentador — o que descarta as explicações
geométricas e aponta para uma parcela CONSTANTE.

Perda de ferro é exatamente isso: existe 24 h por dia, com ou sem carga, e
depende do número de transformadores e não de quilômetros. O achado 53 já a
mediu em 1,45% a 3,60% da carga viva das sete bases — na Cemig-D, 3,60%, que é
da ordem de TODA a perda que o modelo dela reporta (4,63%).

A HIPÓTESE A TESTAR: se o ferro responder por ~30% da perda modelada, o viés
está explicado, e a questão deixa de ser erro e passa a ser CONVENÇÃO — o
`PERD_*` da distribuidora provavelmente reporta só a parcela dependente de
carga, e os dois números estariam certos medindo coisas diferentes.

O QUE ISTO NÃO FAZ: não abre modelo nem simula. Soma `PER_FER` da EQTRMT, que é
a placa declarada pela própria distribuidora, e compara com a energia que o
modelo já publicou em `resultados/`. Lê `.gdb`, então roda em nó de cálculo.

`PER_FER` vem em WATTS por transformador na EQTRMT. Multiplicado por 24 h dá a
energia diária de ferro, que é a base de comparação com a perda do dia
simulado.
"""
import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import escrita                            # noqa: E402
from bdgd2dss.leitor import BDGD, num                    # noqa: E402


def ferro_da_base(caminho):
    """(n_trafos, kW de ferro somados) da EQTRMT.

    Trafo sem `PER_FER` entra como zero e é CONTADO à parte: a diferença entre
    "declara zero" e "não declara" muda a leitura, e escondê-la repetiria o
    defeito que o achado 53 corrigiu — perda a vazio ausente que passava por
    perda a vazio nula.
    """
    b = BDGD(caminho, verbose=False)
    col = b.ler('EQTRMT', ['PER_FER', 'POT_NOM'])
    # `x or []` NAO SERVE AQUI: o leitor devolve array do numpy, e testar a
    # verdade de um array com mais de um elemento levanta ValueError. Foi assim
    # que a primeira execucao errou as 97 bases de uma vez, com rc=0.
    vals = col.get('PER_FER')
    if vals is None:
        vals = []
    w = 0.0
    sem = 0
    for v in vals:
        x = num(v)
        if x is None or x <= 0:
            sem += 1
            continue
        w += x
    return len(vals), w / 1000.0, sem


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', ''))
    ap.add_argument('--resultados', required=True)
    ap.add_argument('--so', default='', help='tags separadas por espaco')
    ap.add_argument('--saida-json', default=os.path.join('medicoes',
                                                         'ferro.json'))
    a = ap.parse_args(argv)

    import regerar_v10 as rg
    so = {x for x in a.so.split() if x}
    bases = [(t, c) for t, c, _ in rg.descobrir(a.bases) if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada', file=sys.stderr)
        return 1

    saida, erros = [], 0
    print('%-20s %10s %12s %10s %10s' %
          ('base', 'trafos', 'ferro kW', 'sem PER_FER', 'modelo %'))
    for tag, cam in bases:
        j = os.path.join(a.resultados, tag + '.json')
        try:
            with open(j, encoding='utf-8') as fh:
                r = json.load(fh)
        except OSError:
            continue
        ag = (r.get('perdas') or {}).get('agregado') or {}
        try:
            n, kw, sem = ferro_da_base(cam)
        except Exception as e:                          # noqa: BLE001
            print('%-20s ERRO: %s' % (tag, str(e)[:70]), flush=True)
            erros += 1
            continue
        d = dict(base=tag, trafos_eqtrmt=n, ferro_kW=round(kw, 1),
                 sem_per_fer=sem, pct_modelo=ag.get('pct_modelo'),
                 pct_declarado=ag.get('pct_declarado'),
                 kW_nominal=(r.get('rollup') or {}).get('kW_nominal'))
        saida.append(d)
        print('%-20s %10s %12s %10s %10s'
              % (tag, f'{n:,}', f'{kw:,.0f}', f'{sem:,}',
                 f"{ag.get('pct_modelo') or 0:.2f}"), flush=True)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'bases': saida}, fh, ensure_ascii=False, indent=1)
    print('\n%d bases medidas, %d com erro  ->  %s'          % (len(saida), erros, a.saida_json))
    # FALHAR QUANDO FALHA. A primeira execucao errou as 97 bases e saiu com
    # rc=0, publicando um JSON vazio — o mesmo padrao de falha silenciosa que
    # ja custou duas colheitas neste projeto. Medir nada nao e medir.
    if not saida:
        print('nenhuma base medida: veja os erros acima', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
