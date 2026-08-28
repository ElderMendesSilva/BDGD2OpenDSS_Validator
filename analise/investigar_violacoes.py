# -*- coding: utf-8 -*-
"""
INVESTIGAR VIOLACOES — separar defeito de topologia do resto (PLANO.md #2)

    python analise/investigar_violacoes.py resultados/v22

Le todos os `*_violacoes.csv` e `*.json` de uma pasta `resultados/<sufixo>/` e
responde tres perguntas sem abrir nenhum modelo:

1. Onde o problema se concentra? (violacoes e GWh por base)
2. Um sinal de topologia da SE (chave ilhada, regulador pendurado, trafo com
   PAC invertido, nao convergencia) explica a violacao, ou o defeito esta no
   alimentador/condutor, fora do que este resultado carrega? Compara a taxa
   DENTRO das violacoes contra a taxa de fundo em TODAS as SEs da rodada — um
   sinal so importa se aparecer mais nas violacoes do que no resto.
3. Quais casos sao sintoma de modelo ja marcado quebrado pela verificacao, e
   por isso nao competem por hora de analise com defeito real de cadastro?

Sai `investigacao.json` na propria pasta de entrada, e imprime o resumo.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

FLAGS_SE = ['chaves_ilhadas', 'reguladores_pendurados', 'trafos_pac_invertido']


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _le_violacoes(pasta):
    linhas = []
    for f in sorted(glob.glob(os.path.join(pasta, '*_violacoes.csv'))):
        with open(f, encoding='utf-8') as fh:
            linhas.extend(csv.DictReader(fh))
    return linhas


def _le_subestacoes(pasta):
    """`(base, se) -> registro de SE`, para todas as bases da rodada — nao so
    as que tem violacao. E o universo contra o qual medir taxa de fundo."""
    indice = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.json'))):
        base = os.path.splitext(os.path.basename(f))[0]
        if base in ('_indice', 'investigacao'):
            continue
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        for se in d.get('subestacoes') or []:
            indice[(base, str(se.get('se')))] = se
    return indice


def taxa_de_fundo(subestacoes):
    """% de todas as SEs da rodada com cada sinal — a base de comparacao."""
    n = len(subestacoes) or 1
    fundo = {'nao_convergiu': sum(1 for se in subestacoes.values()
                                  if not se.get('convergiu')) / n}
    for flag in FLAGS_SE:
        fundo[flag] = sum(1 for se in subestacoes.values()
                          if (se.get(flag) or 0) > 0) / n
    return fundo


def classificar(violacoes, subestacoes):
    """Separa 'ja explicado por modelo quebrado' de 'sinal de topologia
    elevado' de 'sem sinal — cadastro/condutor do alimentador'."""
    modelo_quebrado, com_sinal, sem_sinal = [], [], []
    for v in violacoes:
        if (v.get('se_veredicto') or 'OK') not in ('OK', ''):
            modelo_quebrado.append(v)
            continue
        se = subestacoes.get((v['base'], v['sub']))
        sinais = []
        if se:
            if not se.get('convergiu'):
                sinais.append('nao_convergiu')
            for flag in FLAGS_SE:
                if (se.get(flag) or 0) > 0:
                    sinais.append(flag)
        v = dict(v, _sinais_se=sinais)
        (com_sinal if sinais else sem_sinal).append(v)
    return modelo_quebrado, com_sinal, sem_sinal


def concentracao_por_base(violacoes):
    gwh = defaultdict(float)
    for v in violacoes:
        gwh[v['base']] += _num(v.get('GWh_injetado')) or 0.0
    tot = sum(gwh.values()) or 1.0
    ranking = sorted(gwh.items(), key=lambda kv: -kv[1])
    acumulado, saida = 0.0, []
    for base, g in ranking:
        acumulado += g
        saida.append({'base': base, 'GWh': round(g, 1),
                      'pct_acumulado': round(100 * acumulado / tot, 1)})
    return saida


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('pasta', help='resultados/<sufixo>, ja publicado')
    a = ap.parse_args(argv)

    violacoes = _le_violacoes(a.pasta)
    subestacoes = _le_subestacoes(a.pasta)
    fundo = taxa_de_fundo(subestacoes)
    modelo_quebrado, com_sinal, sem_sinal = classificar(violacoes, subestacoes)

    motivos = Counter(re.sub(r'[\d.]+%?x?', '#', v['motivo']) for v in violacoes)

    resultado = {
        'total_violacoes': len(violacoes),
        'por_motivo': dict(motivos),
        'concentracao_por_base': concentracao_por_base(violacoes),
        'taxa_de_fundo_pct': {k: round(100 * v, 1) for k, v in fundo.items()},
        'modelo_quebrado': {
            'linhas': len(modelo_quebrado),
            'bases': sorted(set(v['base'] for v in modelo_quebrado)),
        },
        'com_sinal_de_topologia': {
            'linhas': len(com_sinal),
            'nota': 'sinal presente NAO prova causa — comparar com a taxa de '
                    'fundo antes de agir; ver taxa_de_fundo_pct',
        },
        'sem_sinal_de_topologia': {
            'linhas': len(sem_sinal),
            'nota': 'candidato a defeito de alimentador/condutor — precisa do '
                    '.gdb, que nao esta em resultados/',
        },
    }

    with open(os.path.join(a.pasta, 'investigacao.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)

    print(f"{len(violacoes)} violacoes em {len(set(v['base'] for v in violacoes))} bases")
    print(f"  modelo ja marcado quebrado: {len(modelo_quebrado)}")
    print(f"  com sinal de topologia na SE: {len(com_sinal)}")
    print(f"  sem sinal (candidato a cadastro/condutor): {len(sem_sinal)}")
    print('taxa de fundo (toda SE da rodada) vs dentro das violacoes:')
    n_com = len(com_sinal) + len(sem_sinal) or 1
    for flag in ['nao_convergiu'] + FLAGS_SE:
        dentro = sum(1 for v in com_sinal if flag in v['_sinais_se'])
        print(f"  {flag:22s} fundo={fundo[flag]*100:5.1f}%  "
             f"violacoes={100*dentro/n_com:5.1f}%")
    print('concentracao por base (top 5):')
    for linha in resultado['concentracao_por_base'][:5]:
        print(f"  {linha['base']:20s} {linha['GWh']:10.1f} GWh  "
             f"acumulado {linha['pct_acumulado']:.0f}%")


if __name__ == '__main__':
    main()
