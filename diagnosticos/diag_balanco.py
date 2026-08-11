# -*- coding: utf-8 -*-
"""Violar o limite rigido pode ser DUAS coisas muito diferentes.

  (a) o modelo produz perda tecnica alta demais       -> defeito nosso
  (b) a perda total MEDIDA e degenerada naquele
      alimentador (nula ou negativa, ou seja, energia
      faturada >= injetada)                            -> defeito do cadastro

Se a total medida for ~0, qualquer perda tecnica positiva "viola", e isso nao
diz nada sobre o modelo. Este corte separa os dois.
"""
import json
import os
import statistics

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
BASES = [('Enel SP', 'MODELOS_V9'), ('Light', 'MODELOS_LT'),
         ('Equatorial', 'MODELOS_EQPA'), ('CPFL', 'MODELOS_CPFL'),
         ('Enel CE', 'MODELOS_ENCE')]

print(f'{"base":12s} {"alim":>6s} {"viola":>12s} '
      f'{"total<=0":>10s} {"total<2%":>10s} {"VIOLA REAL":>12s}')
print('-' * 68)
resumo = []
for rot, pasta in BASES:
    try:
        d = json.load(open(os.path.join(P, pasta, 'validacao_balanco.json'),
                           encoding='utf-8'))
    except Exception:
        continue
    n = len(d)
    viola = [x for x in d if x['viola_limite']]
    # medida degenerada: faturado >= injetado, ou perda total implausivelmente
    # baixa para rede de distribuicao real
    neg = [x for x in d if x['pct_total_medido'] <= 0]
    baixo = [x for x in d if 0 < x['pct_total_medido'] < 2.0]
    # violacao que NAO se explica por medida degenerada
    real = [x for x in viola if x['pct_total_medido'] >= 2.0]
    print(f'{rot:12s} {n:6,} {len(viola):5,} ({100*len(viola)/n:4.1f}%) '
          f'{len(neg):10,} {len(baixo):10,} '
          f'{len(real):5,} ({100*len(real)/n:4.1f}%)')
    resumo.append((rot, pasta, d, viola, real, neg, baixo))

print('\n\nDETALHE POR BASE')
for rot, pasta, d, viola, real, neg, baixo in resumo:
    tot = [x['pct_total_medido'] for x in d]
    nt = [x['pct_nao_tecnica_implicita'] for x in d]
    print(f'\n=== {rot} ({len(d):,} alimentadores)')
    print(f'   perda TOTAL medida:  mediana {statistics.median(tot):6.2f}%   '
          f'p10 {sorted(tot)[len(tot)//10]:7.2f}%   '
          f'p90 {sorted(tot)[9*len(tot)//10]:6.2f}%')
    print(f'   nao tecnica implicita: mediana {statistics.median(nt):6.2f}%')
    print(f'   alimentadores com faturado >= injetado: {len(neg):,} '
          f'({100*len(neg)/len(d):.1f}%)  <- impossivel de medir, e cadastro')
    if real:
        pior = sorted(real, key=lambda z: z['pct_tecnica_modelo']
                      - z['pct_total_medido'], reverse=True)[:5]
        print(f'   violacoes REAIS ({len(real)}), as 5 piores:')
        for x in pior:
            print(f'      {x["sub"]:10s} {x["ctmt"][:18]:18s} '
                  f'modelo {x["pct_tecnica_modelo"]:7.2f}%  '
                  f'medida {x["pct_total_medido"]:6.2f}%  '
                  f'{x["GWh_injetado"]:7.2f} GWh  {x["ucs"]:6,} UCs')
    else:
        print('   violacoes REAIS: nenhuma')
