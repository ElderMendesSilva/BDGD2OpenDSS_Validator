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


def populacao(no_modelo, comparados, sem_declaracao, sem_energia, ambos):
    """De quantos alimentadores a comparacao fala, e de quantos ela cala.

    POR QUE EXISTE. As tres medidas acima publicam `n` e `de` — a CPFL da
    V18 saiu com "27 de 1.467". Mas a CPFL tem 1.636 alimentadores no
    modelo: 169 nunca entraram, e nenhum arquivo dizia isso. Quem le
    "27 de 1.467" entende "de todos", e nao e.

    MEDIDO NA V18, as sete bases:

        base    no modelo   comparados   fora   sem decl   sem energia  ambos
        RR             89           63     26         17             2      7
        ENCE          728          685     43          1             2     40
        EQPA          688          612     76         16            37     23
        LT          1.647        1.488    159         17            59     83
        CPFL        1.636        1.467    169         19            64     86
        CMIG        2.397        1.783    614         44           233    337
        SP          1.806        1.535    271         40             3    228

        total       8.991        7.633  1.358        154           400    804

    Sao 15,1% do pais fora da conta, e a Cemig-D perde 25,6% dela mesma.

    OS TRES BALDES NAO VALEM O MESMO, e por isso saem separados:

      `sem_declaracao`  a CTMT nao traz PERD_*. Nao ha contra o que comparar,
                        e a culpa nao e do modelo. 154 no pais.

      `sem_energia`     ESTE E O QUE INCOMODA. A distribuidora DECLARA a
                        perda do alimentador e o nosso modelo devolve zero
                        energia nele — rede morta que a metrica escondia
                        justamente por estar morta. Sao 400 no pais, 233 so
                        na Cemig-D. Alimentador nesse balde e falha nossa, e
                        tem de aparecer.

      `ambos`           sem declaracao E sem energia. Quase sempre CTMT
                        desativada que sobrou na base. 804 no pais.

    A soma dos tres tem de fechar com `no_modelo - comparados`; se nao
    fechar, alguem drenou alimentador por um quarto caminho sem contar.
    """
    fora = sem_declaracao + sem_energia + ambos
    return {
        'no_modelo': no_modelo,
        'comparados': comparados,
        'fora': fora,
        'sem_declaracao': sem_declaracao,
        'sem_energia_no_modelo': sem_energia,
        'sem_os_dois': ambos,
        'cobertura_pct': (100.0 * comparados / no_modelo) if no_modelo else None,
        # o balde que e falha do modelo, isolado: e o unico dos tres que o
        # projeto pode diminuir por conta propria
        'declarado_e_morto_pct': ((100.0 * sem_energia / no_modelo)
                                  if no_modelo else None),
        'fecha': (comparados + fora) == no_modelo,
    }



def linhas(pares, cortes=CORTES, pop=None):
    """As tres medidas em texto, para o rodape de quem chama.

    `pop` e o que `populacao` devolve. Sem ela o rodape sai como antes,
    e a linha de cobertura simplesmente nao aparece — nenhum chamador
    antigo quebra.
    """
    s = sensibilidade(pares, cortes)
    a = agregado(pares)
    i = implausivel(pares)
    out = []
    if pop:
        out.append(f'populacao: {pop["comparados"]:,} de {pop["no_modelo"]:,} '
                   f'alimentadores comparados ({pop["cobertura_pct"]:.1f}%) — '
                   f'{pop["fora"]:,} fora: {pop["sem_declaracao"]:,} sem PERD_* '
                   f'na CTMT, {pop["sem_energia_no_modelo"]:,} DECLARADOS e sem '
                   f'energia no modelo, {pop["sem_os_dois"]:,} sem os dois')
        if not pop['fecha']:
            out.append('ATENCAO: os baldes nao fecham com o total — ha alimentador '
                       'saindo da conta por um caminho nao contado')
        if pop['sem_energia_no_modelo']:
            out.append(f'ATENCAO: {pop["sem_energia_no_modelo"]:,} alimentador(es) que a '
                       f'distribuidora DECLARA e que o modelo deixa sem energia '
                       f'({pop["declarado_e_morto_pct"]:.1f}% da base). Rede morta '
                       f'nao entra na razao — ela some dela.')
    out.append('razao por corte de declaracao:')
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
