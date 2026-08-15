# -*- coding: utf-8 -*-
"""Substituicao de resistencia por ampacidade insuficiente — achado 34.

O QUE ISTO E, E O QUE NAO E
---------------------------
Isto NAO e conversao. E MODELAGEM, e a premissa tem de aparecer no texto de
quem usar o modelo.

A BDGD declara, na SSDMT, qual condutor esta em cada trecho. O conversor
reproduz essa declaracao fielmente. O problema medido no achado 34 e que em
duas das sete bases essa declaracao poe um fio fino no tronco:

    CND_593_3F   r1=8,232 ohm/km   31 A    2.990 km   13,5% da Enel SP
    CND_1000182  r1=29,142 ohm/km  25 A   10.803 km   10,8% da Enel CE

Um condutor de 31 A num trecho que conduz 1.370 A nao e um condutor de 31 A.
Ou o cadastro erra o condutor, ou erra o trecho; de qualquer forma, o R1
declarado nao descreve o que esta no poste. Medido na Enel SP: 16,1% da
quilometragem carrega 73,6% da resistencia ponderada, e trocar o R1 desses
trechos leva a DALV de 11,85% para 3,05% de perda.

A REGRA, E POR QUE ELA E ESTREITA
---------------------------------
Substitui-se APENAS quando a corrente calculada excede a ampacidade declarada.
Nao se mexe em condutor que opera dentro do que declara, por mais estranho que
o par R1 x CNOM pareca — para isso ja existe o auto-ajuste do `linecodes`,
que trata incoerencia INTERNA ao registro. Aqui o criterio e o USO.

Escolhido o trecho, o substituto e o condutor MAIS FINO DO PROPRIO CATALOGO DA
BASE que cobre a corrente medida. Nao e uma tabela externa, nem um valor
inventado: e um condutor que aquela distribuidora declara possuir.

Troca-se R1 e R0. NAO se troca X1 e X0: a reatancia de uma linha aerea vem
sobretudo do espacamento entre fases, que nao muda quando o cabo engrossa, ao
passo que a resistencia vem da secao, que muda. Trocar so o que a secao
governa e a alteracao minima que resolve o defeito medido.

Nunca se AUMENTA a resistencia. Se o candidato for mais resistivo que o
original, nao ha troca — elevar impedancia nao corrige nada e introduz erro
novo.

O QUE SAI DISSO
---------------
Uma lista de substituicoes, cada uma com o trecho, o condutor de origem, o de
destino, a corrente medida e a ampacidade que ela excedeu. Substituicao
silenciosa seria pior que o defeito: quem le o modelo tem de conseguir contar
o que foi trocado e desfazer.
"""
import collections

MARGEM = 1.0            # quantas vezes a ampacidade a corrente precisa exceder


def catalogo_de(linecodes):
    """Ordena o catalogo por ampacidade. `linecodes` e um dicionario

        nome -> {'cnom': float, 'r1': float, 'x1': float, 'nfases': int}

    Devolve a lista ordenada por `cnom` crescente, que e como a escolha
    caminha. Condutor sem ampacidade declarada fica de fora: sem ela nao ha
    como dizer que ele cobre corrente alguma.
    """
    v = [dict(d, nome=n) for n, d in linecodes.items()
         if (d.get('cnom') or 0) > 0 and (d.get('r1') or 0) > 0]
    return sorted(v, key=lambda d: d['cnom'])


def substituto(corrente, atual, catalogo, margem=MARGEM):
    """O condutor mais fino do catalogo que cobre `corrente`.

    `atual` e o dicionario do condutor declarado. Devolve None quando nao ha
    troca a fazer — e sao quatro os casos, todos legitimos:

      1. a corrente esta dentro da ampacidade declarada (o caso comum);
      2. o condutor declarado nao tem ampacidade (nada a comparar);
      3. nenhum condutor do catalogo cobre a corrente (rede alem do que a
         distribuidora declara possuir — vira alerta, nao troca);
      4. o candidato e MAIS resistivo que o declarado.

    A restricao de fases nao entra aqui de proposito: o catalogo passado ja
    deve estar filtrado pelo numero de fases do trecho, se isso importar para
    quem chama.
    """
    amps = (atual or {}).get('cnom') or 0.0
    if amps <= 0 or corrente <= margem * amps:
        return None
    for c in catalogo:
        if c['cnom'] >= corrente:
            if c['r1'] >= (atual.get('r1') or 0.0):
                return None
            return c
    return None


def decidir(trechos, linecodes, margem=MARGEM):
    """Percorre os trechos resolvidos e decide as substituicoes.

    `trechos` e uma lista de dicionarios, um por trecho de linha:

        {'linha': str, 'linecode': str, 'km': float, 'corrente': float}

    Devolve (substituicoes, resumo). Cada substituicao:

        {'linha', 'de', 'para', 'corrente', 'amps_de', 'amps_para',
         'r1_de', 'r1_para', 'km'}

    O resumo traz o que precisa ser dito no cabecalho do arquivo gerado e no
    relatorio: quantos trechos, quantos km, e os casos sem candidato.
    """
    cat = catalogo_de(linecodes)
    subs = []
    sem_candidato = collections.Counter()
    km_total = km_trocado = 0.0
    for t in trechos:
        km = float(t.get('km') or 0.0)
        km_total += km
        lc = str(t.get('linecode') or '').strip()
        atual = linecodes.get(lc) or linecodes.get(lc.lower())
        if not atual:
            continue
        i = float(t.get('corrente') or 0.0)
        # o catalogo util e o das mesmas fases: trocar um monofasico por um
        # trifasico mudaria a matriz, nao so a resistencia
        nf = atual.get('nfases')
        cat_nf = [c for c in cat if c.get('nfases') == nf] if nf else cat
        c = substituto(i, atual, cat_nf, margem)
        if c is None:
            amps = atual.get('cnom') or 0.0
            if amps > 0 and i > margem * amps:
                sem_candidato[lc] += 1
            continue
        subs.append({'linha': t.get('linha'), 'de': lc, 'para': c['nome'],
                     'corrente': round(i, 1),
                     'amps_de': atual.get('cnom'), 'amps_para': c['cnom'],
                     'r1_de': atual.get('r1'), 'r1_para': c['r1'],
                     # o X e o do ORIGINAL: a reatancia vem do espacamento
                     'x1': atual.get('x1') or 0.0, 'nfases': nf or 3,
                     'codigo': f'{lc}_AJ{int(round(c["cnom"]))}',
                     'km': round(km, 4)})
        km_trocado += km
    resumo = {'trechos': len(trechos), 'trocados': len(subs),
              'km_total': round(km_total, 2), 'km_trocado': round(km_trocado, 2),
              'pct_km': (round(100.0 * km_trocado / km_total, 2)
                         if km_total else 0.0),
              'sem_candidato': dict(sem_candidato),
              'margem': margem,
              'por_condutor': dict(collections.Counter(s['de'] for s in subs))}
    return subs, resumo


CABECALHO = """! ==========================================================================
!  SUBSTITUICAO DE RESISTENCIA POR AMPACIDADE INSUFICIENTE — achado 34
! ==========================================================================
!  ISTO E MODELAGEM, NAO CONVERSAO. A BDGD declara estes condutores nestes
!  trechos; o modelo os substitui porque a corrente calculada excede a
!  ampacidade declarada em mais de {margem:g}x, e um condutor de 31 A que
!  conduz 1.370 A nao e um condutor de 31 A.
!
!  Trocam-se R1 e R0. X1 e X0 ficam: a reatancia vem do espacamento entre
!  fases, que nao muda quando o cabo engrossa.
!
!  {trocados} trechos trocados de {trechos} ({km_trocado:,.1f} km de
!  {km_total:,.1f}, {pct_km:g}% da rede).
!  Substituto: o condutor MAIS FINO DO CATALOGO DESTA BASE que cobre a
!  corrente medida — nao um valor de tabela externa.
!
!  Para rodar SEM esta premissa, apague o `redirect _AMPACIDADE.dss` do
!  MASTER. O modelo continua valido; a perda e que muda.
! ==========================================================================
"""


def escrever(caminho, subs, resumo):
    """Escreve o `_AMPACIDADE.dss`: LineCodes derivados e a reatribuicao.

    DUAS ARMADILHAS DO OPENDSS, as duas medidas na pratica.

    A primeira: editar o LineCode NAO alcanca as linhas ja criadas — o OpenDSS
    copia a impedancia para dentro da Line no momento em que ela nasce. A
    primeira medicao deste achado deu diferenca zero por isso.

    A segunda, e mais traicoeira: `Edit Line.X r1=...` tambem nao serve. A
    Line desta base e declarada em METROS (`Units=m`), entao o `r1` lancado
    direto nela e lido como ohm/METRO. Escrever 0,636 vira 636 ohm/km, e a
    perda da DALV saltou de 11,53% para 37,81% — na direcao contraria, e por
    mil vezes. O executor pegou porque resolve de novo e confere.

    A saida que funciona e um LineCode DERIVADO, que carrega a propria
    unidade, seguido da reatribuicao. De brinde o arquivo fica legivel: da
    para ver o condutor novo e a que trecho ele foi.
    """
    out = [CABECALHO.format(**resumo)]
    vistos = {}
    for s in subs:
        vistos.setdefault(s['codigo'], s)
    if vistos:
        out.append('! --- condutores derivados: R do substituto, X do '
                   'original ---')
    for cod, s in sorted(vistos.items()):
        r1 = s['r1_para']
        x1 = s['x1']
        out.append(f"New LineCode.{cod} nphases={s['nfases']} basefreq=60 "
                   f"units=km r1={r1:.5f} x1={x1:.5f} r0={3*r1:.5f} "
                   f"x0={3.5*x1:.5f} normamps={s['amps_para']:g}"
                   f"   ! {s['de']} ({s['amps_de']:g} A, r1={s['r1_de']:.3f})"
                   f" -> {s['para']} ({s['amps_para']:g} A)")
    if vistos:
        out.append('\n! --- reatribuicao, trecho a trecho ---')
    for s in subs:
        out.append(f"Edit Line.{s['linha']} linecode={s['codigo']}"
                   f"   ! I={s['corrente']:g} A > {s['amps_de']:g} A")
    if not subs:
        out.append('! nenhum trecho excede a ampacidade declarada nesta '
                   'subestacao.')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return len(subs)
