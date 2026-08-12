# -*- coding: utf-8 -*-
"""
SSDMT -> New Line   (rede de media tensao)
SSDBT -> New Line   (rede de baixa tensao, opcional)

Cada trecho vira uma Line com o LineCode do seu condutor. As barras sao os
PAC_1/PAC_2 da BDGD, preservados como estao — e isso que permite casar com
transformadores, chaves e cargas sem nenhuma tabela de-para.
"""
from .leitor import num, txt, no

FASES = {'A': '1', 'B': '2', 'C': '3', 'N': '4'}

# Achado 16. O guarda antigo era `if comp <= 0: comp = 1.0`, e ele olhava a
# ENTRADA. O defeito nasce na SAIDA: `Length={comp:.2f}` escreve `0.00` para
# qualquer valor abaixo de 0,005 m, e com comprimento zero a matriz de
# impedancia fica nula, o OpenDSS nao a inverte e ABORTA a montagem da Y da
# rede inteira — uma linha derruba a subestacao.
#
# Em 24,4 milhoes de trechos das sete bases NAO HA UM SO com COMP <= 0. O que
# ha sao 6 positivos e curtos demais: 5 na Equatorial PA (o menor tem 0,001 m)
# e 1 na Light. O guarda cobria o caso que nunca aparece.
#
# 1 cm e a escolha: esta abaixo de qualquer medicao real de rede (o menor piso
# entre as distribuidoras e 0,10 m, da Cemig-D), acima da resolucao dos dois
# formatos de saida (0.01 em metros, 0.00001 em km), e nao move o km do
# relatorio. Preservar o valor declarado importa mais do que arredonda-lo para
# 1 m: um vao de 1 mm continua sendo um vao curto, e nao um vao de um metro.
COMP_MINIMO = 0.01


def comprimento(v, padrao=1.0):
    """Comprimento em metros que sobrevive aos dois formatos de saida.

    `padrao` vale para campo ausente ou nao numerico — nao para valor pequeno.
    Zero e negativo continuam virando o padrao, porque ali nao ha dado; o que
    muda e o positivo minusculo, que agora e preservado com piso em vez de
    virar zero.
    """
    c = num(v, padrao)
    if c <= 0:
        return padrao
    return max(c, COMP_MINIMO)


def nos(fas_con, incluir_neutro=False):
    """'ABC' -> '.1.2.3' ; 'AN' -> '.1' (neutro fica implicito no terra)."""
    f = [FASES[c] for c in txt(fas_con).upper() if c in 'ABC']
    if not f:
        f = ['1', '2', '3']
    s = '.'.join(f)
    if incluir_neutro and 'N' in txt(fas_con).upper():
        s += '.4'
    return '.' + s


def _linecode(mapa, tip_cnd, nfases):
    d = mapa.get(txt(tip_cnd))
    if d and nfases in d:
        return d[nfases]
    return f'CND_GENERICO_{nfases}F'


def gerar(bdgd, mapa_cnd, ctmts, caminho_saida, camada='SSDMT', col=None):
    """Gera as linhas dos CTMT pedidos. Devolve (n_linhas, km, barras).

    `col` permite reaproveitar uma leitura ja feita — evita varrer a mesma
    camada duas vezes por subestacao.
    """
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON', 'TIP_CND', 'COMP']
    if col is None:
        col = bdgd.ler_filtrado(camada, 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])
    linhas = [f'! ==========================================================',
              f'! LINHAS — geradas de {camada}',
              f'! Barras = PAC_1 / PAC_2 da BDGD (preservados)',
              f'! ==========================================================']
    barras = set()
    km = 0.0
    for i in range(n):
        b1 = no(col['PAC_1'][i])
        b2 = no(col['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        fas = txt(col['FAS_CON'][i])
        nf = max(1, len([c for c in fas.upper() if c in 'ABC']))
        comp = comprimento(col['COMP'][i])
        lc = _linecode(mapa_cnd, col['TIP_CND'][i], nf)
        nd = nos(fas)
        linhas.append(f'New Line.{txt(col["COD_ID"][i])} '
                      f'Bus1={b1}{nd} Bus2={b2}{nd} '
                      f'LineCode={lc} Length={comp:.2f} Units=m')
        barras.add(b1); barras.add(b2)
        km += comp / 1000.0
    open(caminho_saida, 'w', encoding='utf-8').write('\n'.join(linhas) + '\n')
    return len(linhas) - 4, round(km, 2), barras


# fator entre a impedancia do neutro e a da fase. Em cabo multiplexado o
# neutro costuma ter secao igual ou uma bitola abaixo da fase; 1,0 e a
# hipotese conservadora e esta declarada aqui para poder ser contestada.
K_NEUTRO = 1.0


def gerar_bt(bdgd, mapa_cnd, ctmts, caminho_saida, camada='SSDBT', col=None):
    """Rede de BT a QUATRO FIOS: as fases mais o neutro explicito.

    Por que o neutro precisa existir. As cargas de BT ficam entre a fase e o
    no 4 (o neutro do secundario do trafo). Se a rede levar so as fases, o
    no 4 das barras distantes nao existe e a carga fica sem retorno — foi o
    que deixou 29.834 das 30.009 cargas sem tensao no primeiro teste do modo
    completo. Fechar o retorno pela terra (no 0) tambem nao serve: toda a
    corrente passaria pelo reator de aterramento de 0,5 ohm do trafo.

    A SEGCON nao tem LineCode de quatro condutores, entao o neutro sai como
    uma linha monofasica paralela, com a impedancia da fase vezes K_NEUTRO.
    """
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON', 'TIP_CND', 'COMP']
    if col is None:
        col = bdgd.ler_filtrado(camada, 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])
    out = ['! ==========================================================',
           f'! REDE DE BAIXA TENSAO — {camada}',
           '! Quatro fios: fases pelo LineCode da SEGCON, neutro (no 4) como',
           f'! linha monofasica paralela com {K_NEUTRO:g} x a impedancia da fase.',
           '! ==========================================================']
    barras = set()
    km = 0.0
    nl = 0
    for i in range(n):
        b1 = no(col['PAC_1'][i])
        b2 = no(col['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        fas = txt(col['FAS_CON'][i])
        nf = max(1, len([c for c in fas.upper() if c in 'ABC']))
        comp = comprimento(col['COMP'][i])
        d = mapa_cnd.get(txt(col['TIP_CND'][i]))
        lc = _linecode(mapa_cnd, col['TIP_CND'][i], nf)
        nd = nos(fas)
        cod = txt(col['COD_ID'][i])
        out.append(f'New Line.{cod} Bus1={b1}{nd} Bus2={b2}{nd} '
                   f'LineCode={lc} Length={comp:.2f} Units=m')
        r1 = (d or {}).get('r1', 0.4) * K_NEUTRO
        x1 = (d or {}).get('x1', 0.4) * K_NEUTRO
        out.append(f'New Line.N_{cod} phases=1 Bus1={b1}.4 Bus2={b2}.4 '
                   f'units=km r1={r1:.5f} x1={x1:.5f} r0={r1:.5f} x0={x1:.5f} '
                   f'c1=0 c0=0 Length={comp/1000.0:.5f} normamps=200')
        barras.add(b1.lower()); barras.add(b2.lower())
        km += comp / 1000.0
        nl += 2
    open(caminho_saida, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return nl, round(km, 2), barras
