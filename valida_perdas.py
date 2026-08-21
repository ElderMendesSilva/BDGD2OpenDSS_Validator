# -*- coding: utf-8 -*-
"""
VALIDACAO DAS PERDAS: MODELO x PERD_* DECLARADO NA BDGD
=======================================================

    python valida_perdas.py                          abre o painel e pergunta
    python valida_perdas.py MODELOS_V8 <caminho.gdb>

Compara, alimentador a alimentador, a perda tecnica que o modelo calcula
contra a que a distribuidora declara na CTMT.

O QUE E, E O QUE NAO E
----------------------
Isto NAO e validacao contra medicao. O Modulo 7 do PRODIST manda a
distribuidora calcular a perda tecnica por fluxo de potencia na propria rede,
entao PERD_* e SAIDA DE MODELO. Comparar o nosso com o dela e um CRUZAMENTO
ENTRE DOIS MODELOS — e a melhor referencia que existe dentro da BDGD, e tem
de ser nomeada assim.

A grandeza medida disponivel e outra: CTMT.ENE_XX e a energia injetada na
cabeceira e a soma das UCs e a faturada. A diferenca entre as duas e a perda
TOTAL, tecnica mais nao tecnica — conferido na DABR: 13.625,6 contra
10.821,5 MWh, 20,58%. O modelo so produz a parcela tecnica, entao o residuo
nao deve ser cobrado dele.

BASES COMPARAVEIS
-----------------
PERD_* e energia ANUAL; o modelo entrega um DIA. A comparacao e entre RAZOES
(perda / energia injetada), que sao adimensionais e independem do periodo —
desde que o dia simulado represente o mes, que e a hipotese declarada.

O mes do modelo tem de ser o mesmo do clima e da carga (--mes do conversor).
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402
from bdgd2dss import escrita
from bdgd2dss import concordancia

# As parcelas eletricas da CTMT. PERD_MED (medicao) e PERD_A3a
# (subtransmissao) ficam de fora — a primeira nao e eletrica, a segunda esta
# acima do recorte do modelo por subestacao.
PARCELAS = ['PERD_A4', 'PERD_B', 'PERD_A4_B']

# ---------------------------------------------------------------------------
# QUAL COMPOSICAO COBRAR DO MODELO — a correcao de metodo do achado 9
# ---------------------------------------------------------------------------
# O modelo rodado com `--bt agregado` tem a rede de MT E os transformadores
# de distribuicao (UNTRMT/EQTRMT viram Transformer), com a carga de BT
# agregada no secundario. O que ele NAO tem e a rede de baixa tensao.
#
# Somar as tres parcelas cobra dele uma perda que ele estruturalmente nao
# gera. Mas cobrar so `PERD_A4` erra para o outro lado, porque descarta a
# perda dos transformadores, que ele gera.
#
# O que cada campo significa exatamente na BDGD nao esta resolvido aqui — a
# norma define o resultado, nao o procedimento, e o nome `PERD_A4_B` admite
# mais de uma leitura. Por isso a composicao e PARAMETRO e o programa MEDE
# qual delas concorda melhor, em vez de arbitrar.
#
# Concordancia nao e prova de identidade semantica. E evidencia, e fica
# reportada como tal.
CANDIDATAS = [['PERD_A4'],
              ['PERD_A4', 'PERD_A4_B'],
              ['PERD_A4', 'PERD_B', 'PERD_A4_B']]

# Medido em 11/08/2026 nas seis bases, amostra comum por base, criterio de
# concordancia = fracao dentro de +-30%:
#
#     base            PERD_A4    +PERD_A4_B    as tres
#     Light             15,6%        12,8%       5,2%
#     Equatorial PA     22,2%         2,8%       0,8%
#     CPFL              39,5%         2,8%       1,0%
#     Enel CE           37,0%        55,2%      27,6%
#     Enel SP            0,8%        10,1%      18,0%
#
# `PERD_A4` sozinho e o melhor em tres das quatro bases sadias; o Enel CE
# prefere `+PERD_A4_B`. E a soma das tres — a que este programa usava — e a
# PIOR em todas, exceto na Enel SP.
#
# O detalhe que importa: a Enel SP e a base com o defeito do condutor 593,
# que infla a perda do modelo. Denominador maior disfarca modelo inflado.
# A composicao antiga era, sem que ninguem tivesse escolhido assim, a que
# fazia a base defeituosa parecer menos ruim.
#
# Nao ha unanimidade e a concordancia e fraca mesmo no melhor caso (39,5%).
# A conclusao honesta nao e "achamos a composicao certa": e que o cruzamento
# com o `PERD_*` e fraco em qualquer composicao — que foi exatamente o motivo
# de o projeto ter migrado para o balanco por energia MEDIDA.
PARCELAS_POR_BT = {'agregado': ['PERD_A4'],
                   'completo': ['PERD_A4', 'PERD_B', 'PERD_A4_B']}


def parcelas_do_modelo(raiz, log=print):
    """Le o `relatorio_rede.json` e escolhe a composicao pelo modo de BT.

    Nao e adivinhacao: o modo esta gravado no manifesto que o conversor
    escreveu junto do modelo. Sem manifesto, mantem o comportamento antigo.
    """
    cam = os.path.join(raiz, 'relatorio_rede.json')
    if not os.path.exists(cam):
        return list(PARCELAS), 'sem relatorio_rede.json — mantendo as tres'
    try:
        with open(cam, encoding='utf-8') as fh:
            bt = (json.load(fh) or {}).get('bt')
    except Exception as e:
        return list(PARCELAS), f'relatorio_rede.json ilegivel ({e}) — as tres'
    p = PARCELAS_POR_BT.get(bt)
    if not p:
        return list(PARCELAS), f'modo de BT "{bt}" desconhecido — as tres'
    return list(p), f'modelo gerado com --bt {bt}'

# Segmentacao por porte, em kWh anuais declarados. Nao e cosmetica: e nela
# que a discordancia aparece com forma — o declarado fica praticamente plano
# de ponta a ponta e o do modelo cresce com o alimentador.
FAIXAS = [(0, 5e6, 'ate 5 GWh'), (5e6, 15e6, '5 a 15 GWh'),
          (15e6, 40e6, '15 a 40 GWh'), (40e6, 9e15, 'acima de 40 GWh')]

# Alimentador com perda declarada de 0,00% ou 0,01% nao existe em campo — e
# casa vazia no cadastro. Deixados na amostra, produzem razoes de ate
# 105.874x (TBAN ban0306) e destroem qualquer estatistica. O mesmo vale para
# o outro extremo: acima de 40% a declaracao nao e critica.
MIN_DECL, MAX_DECL = 0.5, 40.0


def declarado(gdb, parcelas=None):
    """CTMT -> (energia anual, perda declarada) por alimentador, em kWh.

    `parcelas` escolhe quais colunas `PERD_*` somar; o padrao continua sendo
    as tres. Cada alimentador leva tambem `por_parcela` com os campos
    separados, para que o chamador recomponha sem reler a base — e leitura
    da CTMT de uma concessao nao e barata.
    """
    parcelas = list(parcelas or PARCELAS)
    todas = sorted(set(PARCELAS) | set(parcelas))
    b = BDGD(gdb, verbose=False)
    cols = ['COD_ID', 'SUB'] + [f'ENE_{i:02d}' for i in range(1, 13)] + todas
    c = b.ler('CTMT', cols)
    saida = {}
    for i in range(len(c['COD_ID'])):
        cod = txt(c['COD_ID'][i]).strip().upper()
        ene = sum(num(c[f'ENE_{k:02d}'][i]) for k in range(1, 13))
        sep = {k: num(c[k][i]) for k in todas}
        per = sum(sep[k] for k in parcelas)
        saida[cod] = {'sub': txt(c['SUB'][i]).strip(), 'ene_ano': ene,
                      'perda_ano': per, 'por_parcela': sep,
                      'parcelas': parcelas,
                      'pct': (100 * per / ene) if ene > 0 else None}
    return saida


def comparar_composicoes(pares, decl, candidatas=None):
    """Qual composicao de `PERD_*` concorda melhor com o modelo?

    Devolve `(linhas, descartados)`.

    A AMOSTRA E COMUM AS TRES, e isso nao e detalhe. Duas armadilhas, as
    duas encontradas medindo:

    1. Descartando por composicao — pulando so quem declara zero naquela
       combinacao — a Equatorial PA comparava 508 alimentadores numa linha e
       608 na outra: 100 alimentadores declaram PERD_B e nao declaram
       PERD_A4, e entravam apenas onde a soma os incluia.

    2. O filtro de declaracao degenerada (MIN_DECL a MAX_DECL) tambem muda a
       amostra quando aplicado a composicao ESCOLHIDA: rodando com
       `--parcelas PERD_A4`, a Enel SP caia de 1.491 para 963 alimentadores,
       porque muitos declaram menos de 0,5% em A4 sozinho. A tabela ficava
       comparando a composicao consigo mesma.

    A ancora e fixa: o filtro de plausibilidade e aplicado sobre a soma das
    tres (`PARCELAS`), a composicao mais inclusiva, e nao sobre a que esta
    sendo avaliada. Assim as linhas nao se movem com a escolha.
    """
    cand = [list(c) for c in (candidatas or CANDIDATAS)]
    amostra, descartados = [], 0
    for _, cod, m, _, _, _ in pares:
        d = decl.get(cod.upper())
        if not d or not d['ene_ano']:
            descartados += 1
            continue
        pcts = [100.0 * sum(d['por_parcela'].get(k, 0.0) for k in c)
                / d['ene_ano'] for c in cand]
        ancora = 100.0 * sum(d['por_parcela'].get(k, 0.0) for k in PARCELAS) \
            / d['ene_ano']
        if min(pcts) <= 0 or not (MIN_DECL <= ancora <= MAX_DECL):
            descartados += 1
            continue
        amostra.append((m, pcts))

    saida = []
    for i, parc in enumerate(cand):
        if not amostra:
            break
        raz = sorted(m / p[i] for m, p in amostra)
        saida.append({
            'parcelas': parc, 'n': len(raz),
            'razao_mediana': statistics.median(raz),
            'pct_dentro_30': 100.0 * sum(1 for x in raz
                                         if 0.7 <= x <= 1.3) / len(raz)})
    return saida, descartados


def grafico(pares, raiz, faixas, parcelas=None):
    """As tres figuras que sustentam a conclusao do cruzamento.

    Dispersao: onde cada alimentador cai em relacao a linha 1:1, que e o
    acordo perfeito. Histograma da razao: o quanto o conjunto desloca.
    Barras por porte: a discordancia ESTRUTURAL — o declarado e plano com o
    tamanho do alimentador e o do modelo cresce com ele.
    """
    import interativo
    plt = interativo.pyplot()

    m = [x[2] for x in pares]
    d = [x[3] for x in pares]
    r = sorted(x[2] / x[3] for x in pares if x[3])

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(16, 5.2), dpi=110)

    a1.scatter(d, m, s=6, alpha=.25, color='#2166ac', edgecolors='none')
    lim = [0.3, max(max(m), max(d)) * 1.05]
    a1.plot(lim, lim, color='#e31a1c', lw=1.2, ls='--', label='acordo perfeito')
    a1.plot(lim, [1.3 * x for x in lim], color='#999', lw=.8, ls=':',
            label='±30% (critério)')
    a1.plot(lim, [0.7 * x for x in lim], color='#999', lw=.8, ls=':')
    a1.set_xscale('log'); a1.set_yscale('log')
    a1.set_xlim(lim); a1.set_ylim(lim)
    a1.set_title('Modelo × declarado', loc='left', fontsize=12, weight='bold')
    a1.set_xlabel('perdas declaradas na CTMT (%)')
    a1.set_ylabel('perdas do modelo (%)')
    a1.legend(fontsize=8); a1.grid(alpha=.25, lw=.4, which='both')

    a2.hist([min(x, 8) for x in r], bins=60, color='#4292c6',
            edgecolor='white', lw=.4)
    a2.axvline(1, color='#1a7f37', lw=1.4, label='1,0× — acordo')
    a2.axvline(r[len(r) // 2], color='#e31a1c', lw=1.4, ls='--',
               label=f'mediana {r[len(r)//2]:.2f}×')
    a2.set_title(f'Razão modelo/declarado — {len(r):,} alimentadores',
                 loc='left', fontsize=12, weight='bold')
    a2.set_xlabel('razão (recortada em 8×)')
    a2.set_ylabel('alimentadores')
    a2.legend(fontsize=8); a2.grid(alpha=.25, lw=.4)

    rot, mm, dd = [], [], []
    for a0, a1_, lab in faixas:
        g = [(x[2], x[3]) for x in pares if a0 <= x[5] < a1_]
        if g:
            rot.append(lab)
            mm.append(statistics.median([y[0] for y in g]))
            dd.append(statistics.median([y[1] for y in g]))
    x = range(len(rot))
    a3.bar([i - .2 for i in x], mm, width=.4, color='#2166ac', label='modelo')
    a3.bar([i + .2 for i in x], dd, width=.4, color='#fd8d3c', label='declarado')
    a3.set_xticks(list(x)); a3.set_xticklabels(rot, fontsize=8, rotation=15)
    a3.set_title('Por porte do alimentador', loc='left', fontsize=12, weight='bold')
    a3.set_ylabel('perdas medianas (%)')
    a3.legend(fontsize=8); a3.grid(alpha=.25, axis='y', lw=.4)

    fig.suptitle(f'{os.path.basename(raiz)} — cruzamento com '
                 f'{" + ".join(parcelas or PARCELAS)} da CTMT',
                 fontsize=10, color='#555', x=.01, ha='left')
    fig.tight_layout()
    interativo.mostra(plt, os.path.join(raiz, 'validacao_perdas.png'))


def _painel():
    import interativo
    v = interativo.formulario('valida_perdas', 'Validação das perdas', [
        {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'precisa ter o energia_dia.json — rode antes o energia.py'},
        {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
         'padrao': interativo.bdgd_recente(),
         'dica': 'o File Geodatabase é uma PASTA terminada em .gdb'},
    ], ajuda='Compara, alimentador a alimentador, a perda que o modelo calcula '
             'contra a que a distribuidora declara na CTMT. É cruzamento entre '
             'dois modelos, não validação contra medição.')
    if not v:
        return False
    sys.argv += [v['raiz'], v['gdb'], '--grafico']
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('raiz', nargs='?', default='MODELOS_V8')
    ap.add_argument('gdb', nargs='?',
                    default='../Enel_SP_390_2024-12-31_V11_20250702-2009.gdb')
    ap.add_argument('--grafico', action='store_true',
                    help='mostra dispersao, razao e segmentacao por porte')
    ap.add_argument('--parcelas', nargs='+', default=None, metavar='PERD_X',
                    help='quais colunas PERD_* somar (padrao: as tres). O '
                         'modelo com --bt agregado nao produz perda de rede '
                         'de BT — ver CANDIDATAS no cabecalho')
    a = ap.parse_args()

    raiz = os.path.abspath(a.raiz)
    arq = os.path.join(raiz, 'energia_dia.json')
    if not os.path.exists(arq):
        raise SystemExit(f'rode antes:  python energia.py {a.raiz}')
    modelo = json.load(open(arq, encoding='utf-8'))
    if a.parcelas:
        parc, motivo = list(a.parcelas), 'escolhido em --parcelas'
    else:
        parc, motivo = parcelas_do_modelo(raiz)
    print('lendo as perdas declaradas na CTMT...', flush=True)
    decl = declarado(a.gdb, parc)
    print(f'  {len(decl):,} alimentadores com declaracao')
    print(f'  cobrando do modelo: {" + ".join(parc)}  ({motivo})\n', flush=True)

    # `pares` e a amostra da comparacao principal, filtrada pela declaracao
    # da composicao EM USO. `todos` nao leva esse filtro: e ela que vai para
    # a tabela de composicoes, que precisa de amostra independente da escolha
    # sendo avaliada (o filtro de plausibilidade dela e ancorado nas tres).
    pares, todos = [], []
    sem_decl = degenerado = 0
    for se in modelo:
        for cod, v in (se.get('alimentadores') or {}).items():
            # o OpenDSS devolve o nome do medidor em minusculas
            d = decl.get(cod.upper())
            if not d or not d['pct'] or v['perdas_pct'] is None:
                sem_decl += 1
                continue
            reg = (se['se'], cod, v['perdas_pct'], d['pct'],
                   v['kWh'], d['ene_ano'])
            todos.append(reg)
            if not (MIN_DECL <= d['pct'] <= MAX_DECL):
                degenerado += 1
                continue
            pares.append(reg)

    if not pares:
        raise SystemExit('nenhum alimentador casou entre modelo e CTMT')

    raz = [m / d for _, _, m, d, _, _ in pares if d > 0]
    print(f'{len(pares):,} alimentadores comparados '
          f'({sem_decl:,} sem par ou sem declaracao)\n')
    print(f'{"perdas % do modelo":>22s}: mediana '
          f'{statistics.median([m for _, _, m, _, _, _ in pares]):6.2f}%')
    print(f'{"perdas % declarado":>22s}: mediana '
          f'{statistics.median([d for _, _, _, d, _, _ in pares]):6.2f}%')
    print()
    r = sorted(raz)
    print(f'razao modelo/declarado: mediana {statistics.median(r):5.2f}x  '
          f'p10 {r[len(r)//10]:5.2f}x  p90 {r[9*len(r)//10]:5.2f}x')
    for lim in (1.5, 2.0, 3.0):
        print(f'   acima de {lim:.1f}x: {sum(1 for x in r if x > lim):5,} '
              f'({100*sum(1 for x in r if x > lim)/len(r):5.1f}%)')
    print(f'   abaixo de 0,67x: {sum(1 for x in r if x < 0.67):5,} '
          f'({100*sum(1 for x in r if x < 0.67)/len(r):5.1f}%)')

    # AS TRES MEDIDAS, sobre `todos` — a amostra SEM o corte de
    # plausibilidade. O numero acima depende da escolha do corte tanto
    # quanto do modelo (a Light vai de 1,38x a 0,26x e atravessa o 1,0),
    # e o corte so peneirava a DECLARACAO: modelo com 11.224% de perda
    # passava direto. Ver `bdgd2dss/concordancia.py`.
    quatro = [(m, d, k, e) for _, _, m, d, k, e in todos]
    print()
    for _l in concordancia.linhas(quatro):
        print(_l)

    pares.sort(key=lambda x: -(x[2] / x[3]) if x[3] else 0)
    print(f'\n{"SE":6s} {"alimentador":22s} {"modelo":>8s} {"declarado":>10s} {"razao":>7s}')
    for se, cod, m, d, _, _ in pares[:10]:
        print(f'{se:6s} {cod[:22]:22s} {m:7.2f}% {d:9.2f}% {m/d:7.2f}x')

    # A correcao de metodo do achado 9, medida em vez de arbitrada.
    comp, fora = comparar_composicoes(todos, decl)
    print(f'\nqual composicao de PERD_* concorda melhor com este modelo '
          f'({fora:,} fora da amostra comum):')
    print(f'   {"parcelas":>34s} {"n":>6s} {"razao":>8s} {"dentro de +-30%":>16s}')
    for c in comp:
        marca = '  <- em uso' if c['parcelas'] == parc else ''
        print(f'   {" + ".join(c["parcelas"]):>34s} {c["n"]:6,} '
              f'{c["razao_mediana"]:7.2f}x {c["pct_dentro_30"]:15.1f}%{marca}')
    print('   concordancia nao e prova de identidade: e evidencia sobre o que')
    print('   o modelo reproduz, dado que ele tem MT e trafos, e nao rede BT.')

    print()
    print('por porte do alimentador (energia anual declarada):')
    print(f'   {"faixa":>18s} {"n":>6s} {"modelo":>8s} {"declarado":>10s} {"razao":>7s}')
    for a0, a1, rot in FAIXAS:
        g = [(m, d) for _, _, m, d, _, ea in pares if a0 <= ea < a1]
        if not g:
            continue
        print(f'   {rot:>18s} {len(g):6,} '
              f'{statistics.median([m for m, _ in g]):7.2f}% '
              f'{statistics.median([d for _, d in g]):9.2f}% '
              f'{statistics.median([m/d for m, d in g if d]):6.2f}x')

    # `parcelas` vai em cada registro de proposito: sem ela o arquivo nao diz
    # contra o QUE a razao foi calculada, e duas rodadas com composicoes
    # diferentes ficariam indistinguiveis no disco.
    json.dump({'parcelas': parc,
               'sensibilidade': concordancia.sensibilidade(quatro),
               'agregado': concordancia.agregado(quatro),
               'modelo_implausivel': concordancia.implausivel(quatro),
               'alimentadores': [
                   {'se': s, 'ctmt': c, 'modelo_pct': m,
                    'declarado_pct': d,
                    'razao': (m / d) if d else None, 'parcelas': parc}
                   for s, c, m, d, _, _ in pares]},
              open(os.path.join(raiz, 'validacao_perdas.json'), 'w',
                   encoding='utf-8', newline=escrita.FIM_DE_LINHA), indent=1, ensure_ascii=False)
    print(f'\ndetalhe em {os.path.join(raiz, "validacao_perdas.json")}')
    if a.grafico:
        grafico(pares, raiz, FAIXAS, parc)


if __name__ == '__main__':
    main()
