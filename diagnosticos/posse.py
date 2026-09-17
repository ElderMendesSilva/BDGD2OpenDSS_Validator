# -*- coding: utf-8 -*-
"""De quem sao os transformadores que o modelo conta como rede.

    python diagnosticos/posse.py --bases $BDGD2DSS_BASES \\
        --saida-json medicoes/posse.json

POR QUE A PERGUNTA. A referencia externa por distribuidora (achado 66) pos a
FORCEL83 entre as que perdem mais do que a ANEEL declara — 1,34x mesmo so nas
subestacoes que o classificador acha sadias. Decomposta localmente em
17/09/2026, a perda dela tinha um dono inesperado:

    posse   trafos      kVA   PER_FER   com UC de BT
    PD         660   27.685    157 kW            646
    O           95   23.298     71 kW             43

46% da capacidade instalada nao e da distribuidora (`UNTRMT.POS = 'O'`), e o
modelo soma o ferro desses transformadores — 71 kW, 24 horas por dia — como
perda da rede. A perda regulatoria cobre os transformadores DA DISTRIBUIDORA;
o de um cliente atendido em media tensao fica depois da medicao dele. Tirando
so esse ferro, a Forcel vai de 5,09% para ~4,44% (razao 1,17).

Uma base nao faz lei. Este censo mede, nas 99, quanto da capacidade e do
ferro esta em transformador que nao e da distribuidora.

O QUE ISTO NAO FAZ: nao abre modelo nem simula. Le `UNTRMT` (posse, potencia,
ferro) e `UCBT_tab` (quais transformadores tem cliente de BT). Le `.gdb`,
entao roda em no de calculo.
"""
import argparse
import collections
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import escrita                            # noqa: E402
from bdgd2dss.leitor import BDGD, num, txt              # noqa: E402

# A distribuidora declara o proprio transformador como `PD`. O resto — `O` na
# Forcel — e o que se quer medir; os valores sao contados como vem, sem
# supor o significado de cada codigo.
PROPRIO = 'PD'


def posse_da_base(caminho):
    """Por codigo de `POS`: trafos, kVA, kW de ferro e quantos tem UC de BT."""
    b = BDGD(caminho, verbose=False)
    u = b.ler('UNTRMT', ['COD_ID', 'POT_NOM'])
    # POS e PER_FER lidos UM A UM: base que nao declara um deles ainda mede o
    # outro, e a ausencia vira contagem, nao excecao que derruba a base.
    # O leitor devolve coluna VAZIA para campo ausente, e nao erro — por isso
    # o tamanho e conferido, alem da excecao.
    n = len(u['COD_ID'])
    for campo in ('POS', 'PER_FER'):
        try:
            col = b.ler('UNTRMT', [campo]).get(campo)
        except Exception:                                # noqa: BLE001
            col = None
        u[campo] = col if col is not None and len(col) == n else None
    sem_pos = u['POS'] is None
    com_bt = set()
    try:
        for col, _, _ in b.ler_em_fatias('UCBT_tab', ['UNI_TR_MT']):
            com_bt.update(str(x).strip() for x in col['UNI_TR_MT'])
    except Exception:                                    # noqa: BLE001
        pass
    fer = u.get('PER_FER')
    por = collections.defaultdict(lambda: {'trafos': 0, 'kva': 0.0,
                                           'ferro_kw': 0.0, 'com_uc_bt': 0})
    for i in range(len(u['COD_ID'])):
        p = '(sem POS)' if sem_pos else (txt(u['POS'][i]).strip() or '(vazio)')
        d = por[p]
        d['trafos'] += 1
        d['kva'] += num(u['POT_NOM'][i], 0) or 0
        if fer is not None:
            d['ferro_kw'] += (num(fer[i], 0) or 0) / 1000.0
        d['com_uc_bt'] += txt(u['COD_ID'][i]).strip() in com_bt
    return {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv)
                for kk, vv in v.items()} for k, v in por.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', ''))
    ap.add_argument('--so', default='', help='tags separadas por espaco')
    ap.add_argument('--saida-json', default=os.path.join('medicoes',
                                                         'posse.json'))
    a = ap.parse_args(argv)

    import regerar_v10 as rg
    so = {x for x in a.so.split() if x}
    bases = [(t, c) for t, c, _ in rg.descobrir(a.bases) if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada', file=sys.stderr)
        return 1

    saida, erros = [], 0
    print('%-20s %8s %8s %10s %10s %9s' % ('base', 'trafos', 'nao PD',
                                            'kVA nao PD', '% do kVA',
                                            'ferro %'))
    for tag, cam in bases:
        try:
            por = posse_da_base(cam)
        except Exception as e:                           # noqa: BLE001
            print('%-20s ERRO: %s' % (tag, str(e)[:70]), flush=True)
            erros += 1
            continue
        tot = {k: sum(v[k] for v in por.values())
               for k in ('trafos', 'kva', 'ferro_kw')}
        fora = {k: sum(v[k] for p, v in por.items() if p != PROPRIO)
                for k in ('trafos', 'kva', 'ferro_kw')}
        d = dict(base=tag, gdb=os.path.basename(cam), por_posse=por,
                 trafos=tot['trafos'], kva=round(tot['kva'], 1),
                 ferro_kw=round(tot['ferro_kw'], 1),
                 trafos_nao_pd=fora['trafos'],
                 kva_nao_pd=round(fora['kva'], 1),
                 ferro_kw_nao_pd=round(fora['ferro_kw'], 1))
        saida.append(d)
        pk = 100 * fora['kva'] / tot['kva'] if tot['kva'] else 0
        pf = 100 * fora['ferro_kw'] / tot['ferro_kw'] if tot['ferro_kw'] else 0
        print('%-20s %8s %8s %10s %9.1f%% %8.1f%%'
              % (tag, f"{tot['trafos']:,}", f"{fora['trafos']:,}",
                 f"{fora['kva']:,.0f}", pk, pf), flush=True)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'bases': saida}, fh, ensure_ascii=False, indent=1)
    print('\n%d bases medidas, %d com erro  ->  %s'
          % (len(saida), erros, a.saida_json))
    # medir nada nao e medir — ver diagnosticos/ferro.py
    if not saida:
        print('nenhuma base medida: veja os erros acima', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
