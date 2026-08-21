# -*- coding: utf-8 -*-
"""Quanto o modelo concorda com o declarado — por tres medidas, nao por uma.

POR QUE EXISTE. O projeto vinha publicando UM numero por base: a mediana de
`modelo/declarado` por alimentador, sobre a amostra que sobra depois de
descartar declaracao implausivel. Medido, esse numero depende da escolha do
corte tanto quanto do modelo:

    base             corte 0%   0,25%   0,5%    1%     2%
    Light               1,38x   0,97x   0,74x  0,53x  0,26x
    Equatorial PA       0,74x   0,66x   0,54x  0,40x  0,14x
    Roraima             3,53x   2,90x   2,63x  2,35x  1,48x
    Cemig-D             0,45x   0,45x   0,45x  0,45x  0,45x

A Light atravessa o 1,0 por causa do corte. A Cemig-D nao se move. Um numero
so, sem dizer de que corte ele saiu, esconde a diferenca entre esses dois
casos — e sao casos opostos.

O corte tem razao de existir: alimentador que declara 0,00% produz razao de
105.874x e destroi a estatistica. O problema nao e filtrar, e publicar o
resultado como se nao houvesse filtro.

AS TRES MEDIDAS, E O QUE CADA UMA PEGA

  `sensibilidade`  a mediana em varios cortes. Diz se o numero e robusto ou
                   se e artefato da escolha.

  `agregado`       soma a perda e a energia dos dois lados e compara as
                   fracoes. Nao usa corte nenhum e nao sofre com denominador
                   pequeno. Em percentual, e nao em GWh: o modelo roda um dia
                   util e a declaracao e anual, e a razao entre fracoes nao
                   carrega esse fator.

  `implausivel`    o que o filtro antigo NAO olhava. Ele so peneirava a
                   DECLARACAO; modelo com 11.224% de perda passava direto e
                   entrava na mediana como uma razao qualquer.

E o `implausivel` e o que explica a divergencia entre as outras duas. Medido
na V17:

    base        mediana   agregado   alim. com perda > 20%   fatia da perda
    CPFL          0,88x     5,96x         8 de 1.548             86,4%
    Roraima       2,63x     4,62x         8 de 80                60,7%
    Cemig-D       0,45x     0,85x         6 de 1.831             23,4%
    Equatorial    0,55x     0,41x         0 de 628                0,0%

Oito alimentadores da CPFL, meio por cento da base, carregam 86,4% da perda
que o modelo dela produz. A mediana nao os ve; o agregado e feito deles.
"""

CORTES = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)

# Acima disto a perda do MODELO nao e resultado, e defeito. Alimentador de
# distribuicao nao perde um quinto do que recebe: o pior caso fisico plausivel
# fica bem abaixo, e o que se ve acima disso na V17 sao 11.224%, 2.072% e 390%,
# que sao modelo quebrado — quase sempre alimentador na tensao errada.
TETO_MODELO = 20.0


def _mediana(v):
    s = sorted(v)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def sensibilidade(pares, cortes=CORTES, teto_decl=40.0):
    """A mediana de `modelo/declarado` em cada corte de declaracao.

    `pares` sao tuplas `(pct_modelo, pct_declarado, kwh_modelo, kwh_declarado)`.
    Devolve lista de `{'corte', 'razao', 'n'}`, na ordem de `cortes`.
    """
    out = []
    for c in cortes:
        r = [m / d for m, d, _, _ in pares if d and c <= d <= teto_decl]
        out.append({'corte': c, 'razao': _mediana(r), 'n': len(r)})
    return out


def agregado(pares):
    """Perda total dos dois lados, em percentual da energia de cada lado.

    Sem corte: e a medida que nao depende de escolha nenhuma.
    """
    pm = em = pd = ed = 0.0
    for m, d, kwh_m, kwh_d in pares:
        pm += m / 100.0 * kwh_m
        em += kwh_m
        pd += d / 100.0 * kwh_d
        ed += kwh_d
    a = 100.0 * pm / em if em else None
    b = 100.0 * pd / ed if ed else None
    return {'pct_modelo': a, 'pct_declarado': b,
            'razao': (a / b) if (a and b) else None, 'n': len(pares)}


def implausivel(pares, teto=TETO_MODELO):
    """Alimentadores cuja perda MODELADA nao e fisicamente possivel.

    Devolve quantos sao, que fatia da perda modelada eles carregam, e o pior.
    Fatia alta e o aviso de que o agregado esta sendo feito por defeito, e nao
    por rede.
    """
    tot = alto = 0.0
    n = 0
    pior = None
    for m, _, kwh, _ in pares:
        e = m / 100.0 * kwh
        tot += e
        if pior is None or m > pior:
            pior = m
        if m > teto:
            n += 1
            alto += e
    return {'n': n, 'de': len(pares), 'teto': teto, 'pior_pct': pior,
            'fatia_da_perda_pct': (100.0 * alto / tot) if tot else None}


def linhas(pares, cortes=CORTES):
    """As tres medidas em texto, para o rodape de quem chama."""
    s = sensibilidade(pares, cortes)
    a = agregado(pares)
    i = implausivel(pares)
    out = ['razao por corte de declaracao:']
    out.append('   ' + '  '.join(
        f'{x["corte"]:.2f}%: ' + (f'{x["razao"]:.2f}x' if x['razao'] else '—')
        + f' (n={x["n"]})' for x in s))
    if a['razao']:
        out.append(f'razao AGREGADA (sem corte): {a["razao"]:.2f}x  '
                   f'— modelo {a["pct_modelo"]:.2f}% contra declarado '
                   f'{a["pct_declarado"]:.2f}%')
    if i['n']:
        out.append(f'ATENCAO: {i["n"]} de {i["de"]} alimentadores com perda '
                   f'MODELADA acima de {i["teto"]:.0f}% — pior {i["pior_pct"]:,.0f}% '
                   f'— e eles carregam {i["fatia_da_perda_pct"]:.1f}% da perda '
                   f'do modelo. Modelo quebrado, quase sempre tensao errada.')
    return out
