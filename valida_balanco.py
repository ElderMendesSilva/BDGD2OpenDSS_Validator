# -*- coding: utf-8 -*-
"""
VALIDACAO POR BALANCO DE ENERGIA — modelo contra o que a BDGD MEDIU
==================================================================

    python valida_balanco.py                          abre o painel e pergunta
    python valida_balanco.py MODELOS_V9 <caminho.gdb>

POR QUE ESTE E O CRITERIO, E NAO O `PERD_*`
-------------------------------------------
A BDGD carrega dois tipos de campo, e a diferenca entre eles decide o que
serve para validar:

  MEDICAO   CTMT.ENE_XX          energia injetada na cabeceira do alimentador
            UCBT/UCMT ENE_XX     energia faturada nas unidades consumidoras

  MODELO    CTMT.PERD_*          perda tecnica que a distribuidora CALCULA por
                                 fluxo de potencia, conforme o Modulo 7

Cruzar o nosso resultado com o `PERD_*` compara dois modelos. Cruzar com a
medicao valida. E ha motivo concreto para nao confiar no `PERD_*` como
referencia: medido em duas bases, o vies TROCA DE SINAL — Enel SP 1,88x,
Light 0,19x — e a Light declara perda MAIOR (5,17% contra 4,39%) tendo 2,5x
menos resistencia por km de rede e metade da carga. Os campos de parametro e
os campos de perda da mesma base se contradizem.

O CRITERIO, EM TRES NIVEIS
--------------------------
Por alimentador, tudo em percentual da energia injetada — razoes sao
adimensionais e nao dependem de o modelo rodar um dia e a declaracao ser
anual:

  1. LIMITE RIGIDO   perda tecnica do modelo <= perda total medida.
                     A perda total e (injetada - faturada) e engloba a
                     tecnica. Se o modelo passa dela, esta definitivamente
                     errado — nao ha leitura alternativa. E o unico teste
                     aqui que pode REPROVAR sozinho.

  2. RESIDUO         nao tecnica implicita = total medida - tecnica do modelo.
                     Tem de ser >= 0 (e o mesmo teste do nivel 1, visto por
                     alimentador) e cair numa faixa defensavel.

  3. COBERTURA       quanto da perda total o modelo explica. Nao ha valor
                     "certo": alimentador com muita perda comercial explica
                     pouco, e isso e caracteristica da rede, nao defeito.

O nivel 2 tem um subproduto util: estima a PERDA NAO TECNICA por alimentador
a partir de dado publico. Se o padrao que sair reproduzir o que se sabe de
cada concessao sem ter sido ajustado para isso, e evidencia forte a favor do
modelo.
"""
import argparse
import collections
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402

MESES = [f'ENE_{i:02d}' for i in range(1, 13)]


def energia_medida(gdb, log=print):
    """Por alimentador: (injetada na cabeceira, faturada nas UCs), em kWh/ano.

    A injetada sai da CTMT. A faturada exige varrer UCBT_tab e UCMT_tab, que
    na Enel SP sao 8,26 milhoes de registros — em fatias, como o conversor.
    """
    b = BDGD(gdb, verbose=False)
    c = b.ler('CTMT', ['COD_ID', 'SUB'] + MESES)
    inj, sub = {}, {}
    for i in range(len(c['COD_ID'])):
        cod = txt(c['COD_ID'][i]).strip().upper()
        inj[cod] = sum(num(c[m][i]) for m in MESES)
        sub[cod] = txt(c['SUB'][i]).strip()
    log(f'  CTMT: {len(inj):,} alimentadores, '
        f'{sum(inj.values())/1e6:,.0f} GWh injetados no ano')

    # Agregacao VETORIZADA. Um laco Python sobre 8,26 milhoes de UCs x 12
    # colunas seriam ~99 milhoes de operacoes interpretadas; com np.unique +
    # np.bincount a fatia inteira e somada de uma vez. O `cargas.py` ja usa a
    # mesma estrategia para a mesma tabela.
    import numpy as np
    fat = collections.defaultdict(float)
    n_uc = collections.Counter()
    for tab in ('UCBT_tab', 'UCMT_tab'):
        try:
            lidos = 0
            for col, lido, total in b.ler_em_fatias(tab, ['CTMT'] + MESES):
                cods = col['CTMT'].astype(str)
                ene = np.zeros(len(cods))
                for m in MESES:
                    ene += np.nan_to_num(col[m].astype(float))
                unicos, inv = np.unique(np.char.upper(np.char.strip(cods)),
                                        return_inverse=True)
                soma = np.bincount(inv, weights=ene, minlength=len(unicos))
                cont = np.bincount(inv, minlength=len(unicos))
                for k, u in enumerate(unicos):
                    if u:
                        fat[u] += float(soma[k])
                        n_uc[u] += int(cont[k])
                lidos = lido
                log(f'    {tab}: {lido:,}/{total:,}')
            log(f'  {tab}: {lidos:,} unidades consumidoras')
        except Exception as e:
            log(f'  {tab}: ERRO — {str(e)[:120]}')
    return inj, dict(fat), sub, dict(n_uc)


def cruzar(modelo, inj, fat, sub, n_uc):
    """Junta o modelo com a medicao, alimentador a alimentador."""
    tec = {}
    for se in modelo:
        for cod, v in (se.get('alimentadores') or {}).items():
            if v.get('perdas_pct') is not None:
                tec[cod.strip().upper()] = v['perdas_pct']

    linhas, sem_par = [], 0
    for cod, pct_tec in tec.items():
        e_inj, e_fat = inj.get(cod), fat.get(cod)
        if not e_inj or e_fat is None or e_inj <= 0:
            sem_par += 1
            continue
        pct_total = 100.0 * (e_inj - e_fat) / e_inj
        linhas.append({
            'ctmt': cod, 'sub': sub.get(cod, ''),
            'GWh_injetado': round(e_inj / 1e6, 4),
            'GWh_faturado': round(e_fat / 1e6, 4),
            'ucs': n_uc.get(cod, 0),
            'pct_total_medido': round(pct_total, 3),
            'pct_tecnica_modelo': round(pct_tec, 3),
            'pct_nao_tecnica_implicita': round(pct_total - pct_tec, 3),
            'cobertura': (round(100 * pct_tec / pct_total, 1)
                          if pct_total > 0 else None),
            'viola_limite': bool(pct_tec > pct_total),
        })
    return linhas, sem_par


def grafico(linhas, raiz):
    import interativo
    plt = interativo.pyplot()
    tot = [x['pct_total_medido'] for x in linhas]
    tec = [x['pct_tecnica_modelo'] for x in linhas]
    res = [x['pct_nao_tecnica_implicita'] for x in linhas]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=110)
    a1.scatter(tot, tec, s=7, alpha=.25, color='#2166ac', edgecolors='none')
    lim = [0, min(60, max(max(tot), max(tec)) * 1.05)]
    a1.plot(lim, lim, color='#e31a1c', lw=1.4, ls='--',
            label='limite: técnica = total medida')
    a1.fill_between(lim, lim, [lim[1]] * 2, color='#e31a1c', alpha=.07)
    a1.set_xlim(lim); a1.set_ylim(lim)
    a1.set_title('Técnica do modelo × perda total medida', loc='left',
                 fontsize=12, weight='bold')
    a1.set_xlabel('perda total medida (%)  —  injetada menos faturada')
    a1.set_ylabel('perda técnica do modelo (%)')
    a1.legend(fontsize=8); a1.grid(alpha=.25, lw=.4)
    viol = sum(1 for x in linhas if x['viola_limite'])
    a1.text(.98, .04, f'acima da linha = impossível\n{viol:,} de {len(linhas):,} '
            f'({100*viol/max(len(linhas),1):.1f}%)', transform=a1.transAxes,
            ha='right', fontsize=8, color='#b3261e')

    a2.hist([min(max(x, -20), 60) for x in res], bins=60, color='#41ab5d',
            edgecolor='white', lw=.4)
    a2.axvline(0, color='#e31a1c', lw=1.4,
               label='zero — abaixo disso é impossível')
    med = statistics.median(res)
    a2.axvline(med, color='#333', lw=1.2, ls='--', label=f'mediana {med:.1f}%')
    a2.set_title('Perda não técnica implícita', loc='left', fontsize=12,
                 weight='bold')
    a2.set_xlabel('total medida − técnica do modelo (%)')
    a2.set_ylabel('alimentadores')
    a2.legend(fontsize=8); a2.grid(alpha=.25, lw=.4)

    fig.suptitle(f'{os.path.basename(raiz)} — validação contra energia MEDIDA '
                 f'(CTMT.ENE_XX e energia faturada das UCs)',
                 fontsize=10, color='#555', x=.01, ha='left')
    fig.tight_layout()
    interativo.mostra(plt, os.path.join(raiz, 'validacao_balanco.png'))


def _painel():
    import interativo
    v = interativo.formulario('valida_balanco', 'Validação por balanço de energia', [
        {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'precisa do energia_dia.json — rode antes o energia.py'},
        {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
         'padrao': interativo.bdgd_recente(),
         'dica': 'de onde saem a energia injetada e a faturada'},
    ], ajuda='Compara a perda técnica do modelo com a perda TOTAL medida pela '
             'BDGD (energia injetada na cabeceira menos energia faturada). '
             'Diferente do valida_perdas.py, que cruza com a perda declarada '
             '— esta usa medição, não saída de modelo.')
    if not v:
        return False
    sys.argv += [v['raiz'], v['gdb'], '--grafico']
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('raiz', nargs='?', default='MODELOS_V9')
    ap.add_argument('gdb', nargs='?')
    ap.add_argument('--grafico', action='store_true')
    a = ap.parse_args()
    if not a.gdb:
        raise SystemExit('informe o caminho da .gdb')

    raiz = os.path.abspath(a.raiz)
    arq = os.path.join(raiz, 'energia_dia.json')
    if not os.path.exists(arq):
        raise SystemExit(f'rode antes:  python energia.py {a.raiz}')
    modelo = json.load(open(arq, encoding='utf-8'))

    print('lendo a energia MEDIDA na BDGD (injetada e faturada)...', flush=True)
    inj, fat, sub, n_uc = energia_medida(a.gdb)
    linhas, sem_par = cruzar(modelo, inj, fat, sub, n_uc)
    if not linhas:
        raise SystemExit('nenhum alimentador casou entre modelo e BDGD')

    viol = [x for x in linhas if x['viola_limite']]
    tot = [x['pct_total_medido'] for x in linhas]
    tec = [x['pct_tecnica_modelo'] for x in linhas]
    res = [x['pct_nao_tecnica_implicita'] for x in linhas]
    cob = [x['cobertura'] for x in linhas if x['cobertura'] is not None]

    print(f'\n{len(linhas):,} alimentadores cruzados ({sem_par:,} sem par)\n')
    print('NIVEL 1 — LIMITE RIGIDO (tecnica do modelo <= total medida)')
    print(f'   violam: {len(viol):,} de {len(linhas):,} '
          f'({100*len(viol)/len(linhas):.2f}%)')
    print(f'   {"APROVA" if not viol else "REPROVA"}: '
          f'{"nenhum alimentador tem perda tecnica maior que a total medida" if not viol else "ha modelo fisicamente impossivel"}')
    print('\nNIVEL 2 — RESIDUO (perda nao tecnica implicita)')
    print(f'   mediana {statistics.median(res):6.2f}%   '
          f'p10 {sorted(res)[len(res)//10]:6.2f}%   '
          f'p90 {sorted(res)[9*len(res)//10]:6.2f}%')
    print('\nNIVEL 3 — COBERTURA (quanto da perda total o modelo explica)')
    print(f'   mediana {statistics.median(cob):6.1f}%')
    print(f'\n   perda total medida: mediana {statistics.median(tot):6.2f}%')
    print(f'   tecnica do modelo:  mediana {statistics.median(tec):6.2f}%')

    if viol:
        print(f'\nos 10 piores (tecnica acima da total medida):')
        for x in sorted(viol, key=lambda z: z['pct_tecnica_modelo']
                        - z['pct_total_medido'], reverse=True)[:10]:
            print(f'   {x["sub"]:10s} {x["ctmt"][:20]:20s} '
                  f'modelo {x["pct_tecnica_modelo"]:7.2f}%  '
                  f'total medida {x["pct_total_medido"]:7.2f}%')

    dest = os.path.join(raiz, 'validacao_balanco.json')
    json.dump(linhas, open(dest, 'w', encoding='utf-8'), indent=1,
              ensure_ascii=False)
    print(f'\ndetalhe em {dest}')
    if a.grafico:
        grafico(linhas, raiz)


if __name__ == '__main__':
    main()
