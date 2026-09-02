# -*- coding: utf-8 -*-
"""V26 contra V27 nas 99 bases — o efeito nacional da correcao do regulador.

Produziu o achado 24. Roda LOCALMENTE sobre os `validacao.json` das duas
rodadas: NENHUMA conta no head node do cluster, que e a regra do projeto.

Para reproduzir, do diretorio onde os modelos devem cair:

    ssh teste@10.107.1.23 'cd ~/elder/BDGD2OpenDSS_Validator &&         tar czf - MODELOS_*_V26/validacao.json MODELOS_*_V27/validacao.json'         > v2627.tgz
    tar xzf v2627.tgz
    python <caminho>/analise/v26_x_v27.py

O `tar` para a saida padrao evita gravar arquivo temporario no cluster, e sao
8,3 MB em 198 arquivos — pesa menos que um `git pull`.

Troque os sufixos nos padroes abaixo para comparar outras duas rodadas.
"""
import collections
import glob
import io
import json
import os


def carrega(padrao):
    saida = {}
    for f in glob.glob(padrao):
        base = os.path.basename(os.path.dirname(f))
        base = base.replace('MODELOS_', '').rsplit('_V', 1)[0]
        try:
            saida[base] = json.load(io.open(f, encoding='utf-8'))
        except Exception:                                    # noqa: BLE001
            pass
    return saida


def causa(r):
    return str(r.get('causa') or '?').split('[')[0].strip()


def mediana(v):
    v = sorted(x for x in v if x is not None)
    return v[len(v) // 2] if v else None


v26 = carrega('MODELOS_*_V26/validacao.json')
v27 = carrega('MODELOS_*_V27/validacao.json')
comuns = sorted(set(v26) & set(v27))
print('bases em ambas as rodadas: %d  (V26: %d, V27: %d)'
      % (len(comuns), len(v26), len(v27)))

c26, c27 = collections.Counter(), collections.Counter()
n26 = n27 = 0
mudou = []
for b in comuns:
    a, d = v26[b], v27[b]
    n26 += len(a)
    n27 += len(d)
    for r in a:
        c26[causa(r)] += 1
    for r in d:
        c27[causa(r)] += 1
    ok_a = sum(1 for r in a if causa(r) == 'OK')
    ok_d = sum(1 for r in d if causa(r) == 'OK')
    if ok_d != ok_a:
        mudou.append((ok_d - ok_a, b, len(a), ok_a, ok_d,
                      mediana([r.get('V_MT_mediana') for r in a]),
                      mediana([r.get('V_MT_mediana') for r in d]),
                      mediana([r.get('perdas_pct') for r in a]),
                      mediana([r.get('perdas_pct') for r in d])))

print('subestacoes: V26 %s   V27 %s' % (f'{n26:,}', f'{n27:,}'))
print()
todas = sorted(set(c26) | set(c27), key=lambda k: -(c26[k] + c27[k]))
print('%-24s %8s %8s %9s' % ('causa', 'V26', 'V27', 'delta'))
for k in todas:
    print('%-24s %8d %8d %+9d' % (k, c26[k], c27[k], c27[k] - c26[k]))

print()
print('OK: %d (%.1f%%)  ->  %d (%.1f%%)'
      % (c26['OK'], 100.0 * c26['OK'] / n26, c27['OK'], 100.0 * c27['OK'] / n27))

print()
print('BASES QUE MUDARAM (%d de %d):' % (len(mudou), len(comuns)))
print('%-20s %6s %7s %7s   %-15s %-15s'
      % ('base', 'SEs', 'OK V26', 'OK V27', 'V_MT med', 'perda med'))
for d, b, n, ok_a, ok_d, va, vd_, pa, pd in sorted(mudou, reverse=True):
    print('%-20s %6d %7d %7d   %6s -> %-6s %6s -> %-6s'
          % (b, n, ok_a, ok_d,
             ('%.3f' % va) if va else '-', ('%.3f' % vd_) if vd_ else '-',
             ('%.1f' % pa) if pa else '-', ('%.1f' % pd) if pd else '-'))
