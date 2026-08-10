# -*- coding: utf-8 -*-
"""
FECHAMENTO DA MALHA DE 88 kV.

O problema
----------
A BDGD nao modela o barramento interno das subestacoes. Medido nesta base:
a malha de AT (SSDAT + UNSEAT fechadas) tem 32.220 nos em 844 componentes
desconexas, e 656 dos 729 circuitos sao cada um a sua propria ilha. Os
circuitos que chegam e que saem de uma mesma subestacao nunca se encontram.

A solucao
---------
Criar a barra de AT de cada subestacao como no de verdade e ligar a ela todo
trecho de rede que pertenca aquela subestacao. Duas fontes de vinculo, nesta
ordem de confianca:

  1. DADO — UNSEAT.SUB e UNTRAT.SUB declaram a subestacao de cada chave e de
     cada transformador de AT. Sao 2.482 chaves e 437 trafos com o campo
     preenchido, e todas as 342 subestacoes citadas existem na tabela SUB.
     Sozinho, isto leva de 844 para 405 componentes.

  2. NOME — CTAT.NOME identifica as pontas do circuito por mnemonico
     ("LTA ANH-MUT 1" = Anhanguera-Mutinga). O de-para mnemonico->subestacao
     esta em dados/de_para_mnemonicos.csv. Usado apenas nas componentes que
     o item 1 nao alcanca.

Por que nao so pelo nome: tentamos resolver o mnemonico por topologia e o
metodo produziu respostas confiantes e erradas (MUT caindo em Anhanguera,
CTR em Augusta), porque os circuitos sao ilhas curtas e a intersecao
acabava pegando a subestacao da OUTRA ponta. O dado de UNSEAT nao tem essa
fragilidade.
"""
import collections
import csv
import os
import re

from .leitor import txt

# impedancia do trecho barra <-> rede. E o vao de entrada da subestacao.
R_BARRA = 1e-4

PAD_CIRC = re.compile(r'^(LTA|LTS|LIG|LI|RAE|RAS|LDA|LDS|RAC)\s+([A-Z0-9]+)-([A-Z0-9]+)')


def _no(nome):
    s = txt(nome).strip()
    if not s:
        return ''
    return ''.join(c if (c.isalnum() or c in '_-') else '_' for c in s).lower()


def barra_de(sub):
    """Nome do no da barra de AT de uma subestacao."""
    return 'barra_at_' + _no(sub)


def carregar_depara(caminho):
    """{mnemonico: cod_sub}. Aceita vazio; o fechamento so perde alcance."""
    if not caminho or not os.path.exists(caminho):
        return {}
    d = {}
    with open(caminho, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh, delimiter=';'):
            m = (r.get('MNEMONICO') or '').strip().upper()
            s = (r.get('COD_SUB') or '').strip()
            if m and s:
                d[m] = s
    return d


def ancoras(dados, depara=None):
    """no da rede de AT -> {subestacoes que o reivindicam}."""
    anc = collections.defaultdict(set)

    u = dados['unseat']
    for i in range(len(u['COD_ID'])):
        s = txt(u['SUB'][i]).strip()
        if not s or txt(u['SIT_ATIV'][i]) not in ('AT', ''):
            continue
        for k in ('PAC_1', 'PAC_2'):
            n = _no(u[k][i])
            if n:
                anc[n].add(s)

    t = dados['untrat']
    for i in range(len(t['COD_ID'])):
        s = txt(t['SUB'][i]).strip()
        if s and txt(t['SIT_ATIV'][i]) in ('AT', ''):
            n = _no(t['PAC_1'][i])
            if n:
                anc[n].add(s)

    if not depara:
        return anc

    # complemento pelo nome do circuito, so onde o dado nao chega
    ct = dados['ctat']
    nome_ct = {txt(ct['COD_ID'][i]).strip(): txt(ct['NOME'][i]).strip().upper()
               for i in range(len(ct['COD_ID']))}
    pac_ini = {txt(ct['COD_ID'][i]).strip(): _no(ct['PAC_INI'][i])
               for i in range(len(ct['COD_ID']))}
    s = dados['ssdat']
    nos_do_circ = collections.defaultdict(set)
    for i in range(len(s['COD_ID'])):
        c = txt(s['CTAT'][i]).strip()
        for k in ('PAC_1', 'PAC_2'):
            n = _no(s[k][i])
            if n:
                nos_do_circ[c].add(n)

    for c, nos in nos_do_circ.items():
        if any(n in anc for n in nos):
            continue                      # ja ancorada pelo dado
        m = PAD_CIRC.match(nome_ct.get(c, ''))
        if not m:
            continue
        a, b = m.group(2), m.group(3)
        sa, sb = depara.get(a), depara.get(b)
        ini = pac_ini.get(c)
        # a cabeceira do circuito e a ponta da PRIMEIRA sigla do nome
        if sa and ini and ini in nos:
            anc[ini].add(sa)
        if sb:
            # a outra ponta: no mais distante da cabeceira dentro do circuito
            outros = sorted(nos - {ini})
            if outros:
                anc[outros[-1]].add(sb)
    return anc


def gerar(comps, anc, caminho):
    """Emite as barras de AT e os trechos que ligam cada componente a elas.

    Uma ligacao por (subestacao, componente): basta um ponto de contato para
    unir a componente a barra. Ligar todos os nos criaria dezenas de caminhos
    paralelos de impedancia quase nula, sem ganho e com risco numerico.
    """
    out = ['! ==========================================================',
           '! BARRAS DE AT DAS SUBESTACOES — fechamento da malha de 88 kV',
           '! ',
           '! A BDGD nao modela o barramento interno da subestacao: os',
           '! circuitos de AT que chegam e que saem nunca se encontram, e a',
           '! malha fica em 844 ilhas. Aqui cada subestacao ganha a sua barra',
           '! e os trechos que lhe pertencem sao ligados a ela.',
           '! ',
           '! Vinculo vindo de UNSEAT.SUB e UNTRAT.SUB (dado declarado) e,',
           '! onde estes faltam, do nome do circuito em CTAT.NOME via',
           '! dados/de_para_mnemonicos.csv.',
           '! ==========================================================']

    idx = {}
    for k, c in enumerate(comps):
        for n in c:
            idx[n] = k

    # (sub, componente) -> no representativo
    contato = {}
    for n, subs in anc.items():
        k = idx.get(n)
        if k is None:
            continue
        for s in subs:
            contato.setdefault((s, k), n)

    por_sub = collections.defaultdict(list)
    for (s, k), n in contato.items():
        por_sub[s].append((k, n))

    nlig = 0
    for s in sorted(por_sub):
        b = barra_de(s)
        out.append(f'! {s}: {len(por_sub[s])} trecho(s) de AT chegando na barra')
        for j, (k, n) in enumerate(sorted(por_sub[s]), 1):
            out.append(f'New Line.BAT_{_no(s).upper()}_{j} phases=3 '
                       f'Bus1={b}.1.2.3 Bus2={n}.1.2.3 Switch=y '
                       f'r1={R_BARRA} r0={R_BARRA} x1=0 x0=0 c1=0 c0=0')
            nlig += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

    # componentes apos o fechamento (union-find sobre as barras)
    pai = list(range(len(comps)))

    def find(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    for s, lst in por_sub.items():
        base = find(lst[0][0])
        for k, _ in lst[1:]:
            r = find(k)
            if r != base:
                pai[r] = base
                base = find(base)

    grupos = collections.defaultdict(set)
    for k in range(len(comps)):
        grupos[find(k)] |= comps[k]
    return {'barras': len(por_sub), 'ligacoes': nlig,
            'componentes_antes': len(comps),
            'componentes_depois': len(grupos),
            'grupos': list(grupos.values()),
            'barra_por_sub': {s: barra_de(s) for s in por_sub}}
