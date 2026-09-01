# -*- coding: utf-8 -*-
"""O ferro declarado cabe dentro da perda declarada? So a `.gdb` responde.

    python diagnosticos/contradicao.py --bases $BDGD2DSS_BASES \
        --saida-json medicoes/contradicao_2025.json

POR QUE ISTO EXISTE SEPARADO DO `ferro.py`. O achado 13 e o mais forte do
projeto justamente porque NAO DEPENDE DO NOSSO MODELO: sao tres campos da mesma
BDGD que nao fecham entre si.

    PER_FER   (EQTRMT)      a perda a vazio na placa dos transformadores
    ENE_01..12(UCBT/UCMT)   a energia faturada das unidades consumidoras
    PERD_*    (CTMT)        a perda tecnica que a distribuidora declara

Se o ferro implicito nas placas ja excede a perda tecnica declarada, sobra
espaco NEGATIVO para linhas, cobre e ramais — contradicao interna do dado.
Medido na safra 2024: 40 de 81 bases.

So que o `ferro.py` le a perda declarada de `resultados/<sufixo>/`, que e saida
de rodada. Isso amarra um achado que nao precisa de modelo a uma conversao de
horas — e impede medi-lo numa safra recem-baixada, que e exatamente quando ele
mais interessa. Aqui os tres campos saem da `.gdb`.

AS UNIDADES, que e onde este tipo de conta erra:

    PER_FER   WATTS por transformador  -> x 8,76 kh/ano = kWh/ano
    ENE_xx    kWh no mes               -> soma dos 12 = kWh/ano
    PERD_*    kWh no ano               -> ja e anual

RESSALVA HERDADA DO ACHADO 13: o denominador e energia FATURADA. Se a real for
maior — furto, medicao incompleta — o ferro percentual cai. Isso relativiza os
casos de razao 1,1x; nao salva os de 3x.

Le `.gdb`, entao roda em no de calculo (regra de 28/08/2026).
"""
import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import escrita                            # noqa: E402
from bdgd2dss.leitor import BDGD, num                    # noqa: E402

HORAS_ANO = 8760.0

# A composicao do `PERD_*` para o modo agregado, medida em `valida_perdas.py`:
# `PERD_A4` sozinho e o que melhor concorda em tres das quatro bases sadias.
# Aqui vale a mesma escolha, para que os dois numeros sejam comparaveis.
PARCELAS = ['PERD_A4']


def contradicao_da_base(caminho, parcelas=None):
    """(ferro kWh/ano, energia kWh/ano, perda declarada kWh/ano) da base."""
    parcelas = list(parcelas or PARCELAS)
    b = BDGD(caminho, verbose=False)

    # --- ferro: a placa dos proprios transformadores
    col = b.ler('EQTRMT', ['PER_FER'])
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
    ferro_kwh = w / 1000.0 * HORAS_ANO          # W -> kW -> kWh/ano

    # --- energia e perda declarada, da CTMT
    todas = sorted(set(PARCELAS) | set(parcelas))
    cols = (['COD_ID'] + [f'ENE_{i:02d}' for i in range(1, 13)] + todas)
    c = b.ler('CTMT', cols)
    ene = perda = 0.0
    for i in range(len(c['COD_ID'])):
        ene += sum(num(c[f'ENE_{k:02d}'][i]) for k in range(1, 13))
        perda += sum(num(c[k][i]) for k in parcelas)

    return {
        'trafos': len(vals),
        'sem_per_fer': sem,
        'ferro_kWh_ano': round(ferro_kwh, 1),
        'energia_kWh_ano': round(ene, 1),
        'declarado_kWh_ano': round(perda, 1),
        'ferro_pct': round(100.0 * ferro_kwh / ene, 3) if ene > 0 else None,
        'declarado_pct': round(100.0 * perda / ene, 3) if ene > 0 else None,
        # A RAZAO E O ACHADO. Acima de 1, o ferro dos proprios transformadores
        # nao cabe dentro da perda que a distribuidora declara.
        'razao_ferro_declarado': (round(ferro_kwh / perda, 3)
                                  if perda > 0 else None),
        'parcelas': parcelas,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', ''))
    ap.add_argument('--so', nargs='*', default=None, help='tags')
    ap.add_argument('--parcelas', nargs='*', default=None,
                    help='quais PERD_* somar (padrao: PERD_A4)')
    ap.add_argument('--saida-json',
                    default=os.path.join('medicoes', 'contradicao.json'))
    a = ap.parse_args(argv)

    import regerar_v10 as rg
    so = set(a.so) if a.so else None
    bases = [(t, c) for t, c, _ in rg.descobrir(a.bases) if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada', file=sys.stderr)
        return 1

    saida, erros = [], 0
    print('%-20s %10s %10s %10s' % ('base', 'ferro %', 'declara %', 'razao'))
    for tag, cam in bases:
        try:
            d = contradicao_da_base(cam, a.parcelas)
        except Exception as e:                          # noqa: BLE001
            print('%-20s ERRO: %s' % (tag, str(e)[:70]), flush=True)
            erros += 1
            continue
        d['base'] = tag
        saida.append(d)
        print('%-20s %9s%% %9s%% %10s'
              % (tag,
                 '—' if d['ferro_pct'] is None else '%.2f' % d['ferro_pct'],
                 '—' if d['declarado_pct'] is None
                 else '%.2f' % d['declarado_pct'],
                 '—' if d['razao_ferro_declarado'] is None
                 else '%.2fx' % d['razao_ferro_declarado']), flush=True)

    piores = [d for d in saida
              if (d['razao_ferro_declarado'] or 0) > 1.0]
    print('\n%d de %d bases em que o FERRO SOZINHO excede a perda declarada'
          % (len(piores), len(saida)))
    for d in sorted(piores, key=lambda x: -x['razao_ferro_declarado'])[:10]:
        print('  %-20s %.2f%% de ferro contra %.2f%% declarados  (%.1fx)'
              % (d['base'], d['ferro_pct'], d['declarado_pct'],
                 d['razao_ferro_declarado']))

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'bases': saida}, fh, ensure_ascii=False, indent=1)
    print('\n%d bases medidas, %d com erro  ->  %s'
          % (len(saida), erros, a.saida_json))
    # Medir nada nao e medir — mesmo defeito que o `ferro.py` ja teve.
    if not saida:
        print('nenhuma base medida: veja os erros acima', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
