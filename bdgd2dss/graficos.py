# -*- coding: utf-8 -*-
"""As figuras do relatorio, num lugar so.

ATE 02/09/2026 ELAS ESTAVAM ESPALHADAS por cinco executaveis — `energia.py`,
`validador.py`, `verifica.py`, `valida_perdas.py` e `valida_balanco.py` —, com
uma ou duas figuras cada, estilos diferentes e nenhum reuso. Quem queria ver a
rede tinha de rodar cinco programas e juntar os PNG a mao.

Aqui cada funcao desenha UMA figura num eixo que recebe pronto. Isso as torna
compostas: o relatorio por subestacao monta dez num PDF, o da concessao monta
outras dez, e qualquer uma pode ser usada sozinha.

DUAS REGRAS QUE VALEM PARA TODAS:

1. FIGURA SEM DADO NAO E FIGURA VAZIA, e sim figura que DIZ que nao ha dado.
   Eixo em branco num relatorio de 20 paginas parece defeito do gerador, e o
   leitor nao sabe se e ausencia de dado ou erro nosso.

2. NENHUMA delas resolve circuito. Recebem dados ja medidos — do
   `validacao.json`, do `energia_dia.json` ou de um modelo ja compilado. Isso
   e o que permite gerar relatorio em segundos, no laptop, sem cluster.
"""
import math

# A paleta e fixa e tem significado: verde é o que está dentro do esperado,
# âmbar o que merece olhar, vermelho o que reprova. Repetir a mesma cor para o
# mesmo significado em vinte figuras é o que faz o relatório ser lido rápido.
COR_OK = '#2e7d32'
COR_ATENCAO = '#f9a825'
COR_RUIM = '#c62828'
COR_NEUTRA = '#546e7a'
COR_CLARA = '#b0bec5'

# Limites regulatorios de tensao em pu (PRODIST, modulo 8, faixa adequada).
V_ADEQUADA = (0.93, 1.05)


def _rotulo(x):
    """O valor da barra, na escala certa: 4,2 e 4,2%; 1.850 vira 1.850."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return ''
    # DUAS CASAS ATE 1.000. A regra anterior arredondava a partir de 10, e
    # `16,29%` virava `16` — perdendo justamente a precisao que distingue as
    # tres piores subestacoes entre si.
    if abs(f) >= 1000:
        return _mil(f)
    return ('%.2f' % f).replace('.', ',')


def _mil(x):
    """Número com ponto de milhar, à brasileira."""
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return '—'


def _vazio(ax, motivo):
    """Diz por que nao ha figura, em vez de deixar o eixo em branco."""
    ax.text(0.5, 0.5, motivo, ha='center', va='center', fontsize=9,
            color=COR_NEUTRA, wrap=True, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ('top', 'right', 'bottom', 'left'):
        ax.spines[lado].set_visible(False)
    return ax


def _acaba(ax, titulo, x=None, y=None):
    ax.set_title(titulo, fontsize=10, loc='left')
    if x:
        ax.set_xlabel(x, fontsize=8)
    if y:
        ax.set_ylabel(y, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25, linewidth=0.5)
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    return ax


def _cor_da_tensao(pu):
    if pu is None:
        return COR_CLARA
    if pu < V_ADEQUADA[0] or pu > V_ADEQUADA[1]:
        return COR_RUIM
    if pu < 0.95:
        return COR_ATENCAO
    return COR_OK


# ===========================================================================
#  POR SUBESTACAO
# ===========================================================================

def perfil_de_tensao(ax, distancias, pus):
    """Tensao contra distancia eletrica da fonte — a figura mais informativa
    de um alimentador.

    A queda ao longo do tronco aparece como uma nuvem descendente; um degrau
    vertical e regulador ou transformador; um patamar horizontal e rede sem
    corrente. E onde o achado 22 saltaria aos olhos: a AGV desenhava a nuvem
    inteira abaixo de 0,5 pu.
    """
    if not distancias or not pus:
        return _vazio(ax, 'sem barras de MT com tensao')
    cores = [_cor_da_tensao(p) for p in pus]
    ax.scatter(distancias, pus, s=3, c=cores, alpha=0.55, linewidths=0)
    ax.axhline(V_ADEQUADA[0], color=COR_RUIM, lw=0.8, ls='--')
    ax.axhline(V_ADEQUADA[1], color=COR_RUIM, lw=0.8, ls='--')
    ax.axhspan(V_ADEQUADA[0], V_ADEQUADA[1], color=COR_OK, alpha=0.06)
    return _acaba(ax, 'Perfil de tensão', 'distância elétrica da fonte (km)', 'pu')


def histograma_de_tensao(ax, pus):
    """Quanto da rede esta fora da faixa adequada, e para que lado."""
    if not pus:
        return _vazio(ax, 'sem barras de MT com tensao')
    ax.hist(pus, bins=40, color=COR_NEUTRA, alpha=0.8)
    ax.axvline(V_ADEQUADA[0], color=COR_RUIM, lw=0.9, ls='--')
    ax.axvline(V_ADEQUADA[1], color=COR_RUIM, lw=0.9, ls='--')
    fora = sum(1 for p in pus if p < V_ADEQUADA[0] or p > V_ADEQUADA[1])
    ax.set_title('Tensão nas barras de MT — %d de %d fora da faixa (%.1f%%)'
                 % (fora, len(pus), 100.0 * fora / len(pus)),
                 fontsize=10, loc='left')
    return _acaba(ax, ax.get_title(), 'pu', 'barras')


def curva_do_dia(ax, fonte_kw, gd_kw=None, perdas_kw=None):
    """As 24 h em passos de 15 min: o que entra, o que a GD injeta e o que se
    perde. E a unica figura que mostra a rede em OPERACAO, e nao num instante.
    """
    if not fonte_kw:
        return _vazio(ax, 'sem serie diaria (rode o energia.py)')
    h = [i * 24.0 / len(fonte_kw) for i in range(len(fonte_kw))]
    ax.plot(h, fonte_kw, color=COR_NEUTRA, lw=1.4, label='fonte')
    if gd_kw and any(gd_kw):
        ax.plot(h, gd_kw, color=COR_OK, lw=1.2, label='geracao distribuida')
    if perdas_kw and any(perdas_kw):
        ax.plot(h, perdas_kw, color=COR_RUIM, lw=1.0, label='perdas')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(fontsize=7, frameon=False)
    return _acaba(ax, 'Curva do dia', 'hora', 'kW')


def perdas_do_dia(ax, fonte_kw, perdas_kw):
    """A perda em % ao longo do dia. Ela NAO e constante, e o valor unico que
    o relatorio publica e a integral — ver a curva evita ler o pico como media.
    """
    if not fonte_kw or not perdas_kw:
        return _vazio(ax, 'sem serie diaria')
    h = [i * 24.0 / len(fonte_kw) for i in range(len(fonte_kw))]
    pct = [100.0 * p / f if f else 0.0 for p, f in zip(perdas_kw, fonte_kw)]
    ax.plot(h, pct, color=COR_RUIM, lw=1.3)
    ax.fill_between(h, pct, color=COR_RUIM, alpha=0.12)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    return _acaba(ax, 'Perda ao longo do dia', 'hora', '% da injeção')


def carregamento(ax, pcts):
    """Corrente sobre ampacidade, por trecho. Acima de 100% o condutor conduz
    mais do que a placa dele — e o que o achado 34 corrige, e o que denunciou o
    laco do regulador na AGV: 2.506 A num cabo de 145 A, 1.700%.
    """
    if not pcts:
        return _vazio(ax, 'sem dados de carregamento')
    teto = max(200.0, min(400.0, max(pcts) if pcts else 200.0))
    dados = [min(p, teto) for p in pcts]
    ax.hist(dados, bins=40, color=COR_NEUTRA, alpha=0.85)
    ax.axvline(100, color=COR_RUIM, lw=1.0, ls='--')
    acima = sum(1 for p in pcts if p > 100)
    return _acaba(ax, 'Carregamento dos condutores — %d acima de 100%%' % acima,
                  '% da ampacidade declarada', 'trechos')


def por_alimentador(ax, nomes, valores, titulo, unidade, destacar=None):
    """Barras horizontais por alimentador, do maior para o menor.

    Serve para perda, km, trafos e tensao minima — quatro figuras com um
    desenho so, porque a comparacao entre alimentadores e sempre a mesma
    pergunta: qual deles domina?
    """
    if not nomes or not valores:
        return _vazio(ax, 'sem alimentadores')
    par = sorted(zip(valores, nomes), reverse=True)[:15]
    v = [x[0] for x in par]
    n = [x[1] for x in par]
    cores = [COR_RUIM if (destacar and x > destacar) else COR_NEUTRA for x in v]
    ax.barh(range(len(v)), v, color=cores, height=0.7)
    # O NUMERO NO FIM DA BARRA. Sem ele o leitor compara comprimentos e nao
    # sabe a grandeza — "a maior e o dobro da segunda" nao diz se sao 4% ou
    # 40%. Com o valor escrito, ranking e magnitude cabem na mesma figura.
    largura = max(v) if v else 1
    for k, x in enumerate(v):
        ax.text(x + largura * 0.012, k, _rotulo(x), va='center', fontsize=7,
                color=COR_RUIM if (destacar and x > destacar) else COR_NEUTRA)
    ax.set_xlim(0, largura * 1.16)
    ax.set_yticks(range(len(v)))
    ax.set_yticklabels(n, fontsize=6)
    ax.invert_yaxis()
    if destacar:
        ax.axvline(destacar, color=COR_RUIM, lw=0.8, ls='--')
    return _acaba(ax, titulo, unidade, None)


def composicao_da_perda(ax, linhas_kw, trafos_kw):
    """Onde a perda acontece. O achado 13 vive nesta figura: nas 38 bases
    filtradas, 78% da perda modelada esta nos transformadores, e as linhas dao
    0,87% — o que muda completamente a leitura da comparacao com o declarado.
    """
    if linhas_kw is None or trafos_kw is None:
        return _vazio(ax, 'sem separacao de perdas')
    tot = (linhas_kw or 0) + (trafos_kw or 0)
    if tot <= 0:
        return _vazio(ax, 'perda total nula ou negativa')
    ax.barh([0], [linhas_kw], color=COR_NEUTRA, height=0.45)
    ax.barh([0], [trafos_kw], left=[linhas_kw], color=COR_ATENCAO, height=0.45)
    # O VALOR VAI DENTRO DA BARRA. Barra empilhada sem numero obriga o leitor a
    # medir o comprimento contra o eixo, e ninguem faz isso — le "mais ou menos
    # metade" e segue. Com o kW e o percentual escritos, a figura responde
    # sozinha.
    for x0, larg, rot, cor in ((0, linhas_kw, 'linhas', 'white'),
                               (linhas_kw, trafos_kw, 'transformadores',
                                '#3e2723')):
        if larg <= 0:
            continue
        ax.text(x0 + larg / 2.0, 0,
                '%s\n%s kW\n%.0f%%' % (rot, _mil(larg),
                                          100.0 * larg / tot),
                ha='center', va='center', fontsize=9, color=cor,
                linespacing=1.5)
    ax.set_yticks([])
    ax.set_ylim(-0.45, 0.45)
    ax.set_title('Onde a perda acontece — %s kW no total' % _mil(tot),
                 fontsize=10, loc='left')
    return _acaba(ax, ax.get_title(), 'kW', None)


def mapa(ax, xs, ys, valores=None, titulo='Rede'):
    """A rede no espaco, colorida pelo que interessa.

    Nao e enfeite: rede partida, alimentador que atravessa a concessao e
    coordenada trocada aparecem aqui em um segundo e em nenhuma tabela.
    """
    if not xs or not ys:
        return _vazio(ax, 'sem coordenadas (BusCoords)')
    if valores:
        cores = [_cor_da_tensao(v) for v in valores]
    else:
        cores = COR_NEUTRA
    # `datalim` deixava a rede num canto com metade da figura em branco:
    # ele estica os LIMITES para casar com a proporcao do eixo. `box` faz o
    # contrario — ajusta a caixa ao dado, e a rede ocupa a pagina.
    ax.scatter(xs, ys, s=2.0, c=cores, alpha=0.7, linewidths=0)
    ax.set_aspect('equal', adjustable='box')
    ax.margins(0.02)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(titulo, fontsize=10, loc='left')
    for lado in ('top', 'right', 'bottom', 'left'):
        ax.spines[lado].set_visible(False)
    return ax


# ===========================================================================
#  DA CONCESSAO (MASTER GERAL)
# ===========================================================================

def veredictos(ax, contagem):
    """Quantas subestacoes passam, e por que as outras nao passam."""
    if not contagem:
        return _vazio(ax, 'sem veredictos')
    ordem = sorted(contagem.items(), key=lambda kv: -kv[1])
    n = [k for k, _ in ordem]
    v = [x for _, x in ordem]
    cores = [COR_OK if k == 'OK' else COR_RUIM for k in n]
    ax.bar(range(len(v)), v, color=cores)
    for k, x in enumerate(v):
        ax.text(k, x, ' %d\n %.1f%%' % (x, 100.0 * x / sum(v)),
                ha='center', va='bottom', fontsize=7, color=cores[k],
                linespacing=1.3)
    ax.set_ylim(0, max(v) * 1.25)
    ax.set_xticks(range(len(v)))
    ax.set_xticklabels(n, fontsize=6, rotation=20, ha='right')
    tot = sum(v)
    ok = contagem.get('OK', 0)
    return _acaba(ax, 'Veredictos — %d de %d aprovadas (%.1f%%)'
                  % (ok, tot, 100.0 * ok / tot if tot else 0), None,
                  'subestacoes')


def ranking(ax, nomes, valores, titulo, unidade, limite=None):
    """As 15 piores de uma metrica. O agregado esconde quem domina; esta
    figura existe para mostrar que quase sempre poucas bases respondem por
    quase tudo — como a NEOENERGIA385, com 68 das 139 subestacoes fora do OK.
    """
    return por_alimentador(ax, nomes, valores, titulo, unidade, limite)


def dispersao(ax, xs, ys, titulo, xlabel, ylabel, diagonal=False):
    """Duas medidas, uma contra a outra. Com `diagonal`, a reta y=x — que e
    onde os pontos cairiam se as duas concordassem.
    """
    if not xs or not ys:
        return _vazio(ax, 'sem pares para comparar')
    ax.scatter(xs, ys, s=12, color=COR_NEUTRA, alpha=0.6, linewidths=0)
    if diagonal:
        lo = min(min(xs), min(ys))
        hi = max(max(xs), max(ys))
        ax.plot([lo, hi], [lo, hi], color=COR_RUIM, lw=0.9, ls='--')
    return _acaba(ax, titulo, xlabel, ylabel)


def histograma(ax, valores, titulo, xlabel, corte=None):
    """Distribuicao de uma metrica pela concessao."""
    if not valores:
        return _vazio(ax, 'sem valores')
    import statistics as _st
    ax.hist(valores, bins=30, color=COR_NEUTRA, alpha=0.85)
    # MEDIANA E CORTE ANOTADOS COM O NUMERO. Linha tracejada sem rotulo obriga
    # a olhar o eixo e adivinhar onde ela cai.
    med = _st.median(valores)
    ax.axvline(med, color=COR_OK, lw=1.2)
    ax.annotate('mediana %.2f' % med, (med, ax.get_ylim()[1] * 0.92),
                fontsize=7, color=COR_OK, ha='left',
                xytext=(4, 0), textcoords='offset points')
    if corte is not None:
        ax.axvline(corte, color=COR_RUIM, lw=1.0, ls='--')
        acima = sum(1 for x in valores if x > corte)
        ax.annotate('%d acima de %g' % (acima, corte),
                    (corte, ax.get_ylim()[1] * 0.78), fontsize=7,
                    color=COR_RUIM, ha='left', xytext=(4, 0),
                    textcoords='offset points')
    return _acaba(ax, '%s — %d subestações' % (titulo, len(valores)),
                  xlabel, 'subestações')


def pizza(ax, rotulos, valores, titulo):
    """Composicao. Usada com parcimonia: so quando as partes somam um todo
    que o leitor precisa ver inteiro."""
    if not valores or sum(valores) <= 0:
        return _vazio(ax, 'sem composicao')
    cores = [COR_OK, COR_ATENCAO, COR_RUIM, COR_NEUTRA, COR_CLARA]
    ax.pie(valores, labels=rotulos, autopct='%1.0f%%', textprops={'fontsize': 7},
           colors=cores[:len(valores)], wedgeprops={'linewidth': 0.5,
                                                    'edgecolor': 'white'})
    ax.set_title(titulo, fontsize=10, loc='left')
    return ax


def barras_empilhadas(ax, nomes, series, rotulos, titulo, unidade):
    """Varias parcelas por item — perda de linha e de trafo por subestacao,
    por exemplo."""
    if not nomes or not series:
        return _vazio(ax, 'sem series')
    cores = [COR_NEUTRA, COR_ATENCAO, COR_RUIM, COR_CLARA]
    base = [0.0] * len(nomes)
    for k, serie in enumerate(series):
        ax.bar(range(len(nomes)), serie, bottom=base,
               color=cores[k % len(cores)], label=rotulos[k])
        base = [b + (s or 0) for b, s in zip(base, serie)]
    ax.set_xticks(range(len(nomes)))
    ax.set_xticklabels(nomes, fontsize=6, rotation=60, ha='right')
    ax.legend(fontsize=7, frameon=False)
    return _acaba(ax, titulo, None, unidade)


def texto(ax, linhas, titulo=None):
    """Um painel de numeros. Nem tudo vira grafico, e forcar barra onde cabe
    uma tabela de seis linhas so gasta tinta."""
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ('top', 'right', 'bottom', 'left'):
        ax.spines[lado].set_visible(False)
    if titulo:
        ax.set_title(titulo, fontsize=10, loc='left')
    y = 0.92
    for L in linhas[:14]:
        ax.text(0.02, y, L, fontsize=8, va='top', transform=ax.transAxes,
                family='monospace')
        y -= 0.075
    return ax


# ===========================================================================
#  GERACAO DISTRIBUIDA — o que a serie de 96 passos torna possivel
# ===========================================================================
#
# A serie e o insumo mais valioso do modelo, e nao um subproduto: e ela que
# permite o modo `daily` do OpenDSS, e o modo daily e o que torna a GD
# analisavel. Num instantaneo, geracao distribuida e so uma carga negativa; nas
# 24 h em passos de 15 min, ela vira o que de fato e — uma injecao que segue o
# sol, some a noite e nao acompanha o pico de carga.
#
# Nenhuma pergunta que importa sobre GD se responde sem a serie:
#
#   * a que hora a injecao supera o consumo, invertendo o fluxo;
#   * quanto da carga do dia foi atendida localmente;
#   * se o pico de geracao coincide com o pico de carga (quase nunca coincide);
#   * qual o carregamento MINIMO do alimentador, que e quando a sobretensao
#     por GD aparece.

def geracao_no_dia(ax, fonte_kw, gd_kw):
    """A GD contra a carga, hora a hora, com o fluxo reverso destacado.

    FLUXO REVERSO e o resultado que so o modo daily entrega: quando a injecao
    local supera o consumo, a corrente inverte e o alimentador passa a exportar
    para a subestacao. E ali que aparecem sobretensao, atuacao indevida de
    regulador e o limite real de hospedagem — nenhum deles visivel num
    instantaneo de ponta.
    """
    if not gd_kw or not any(gd_kw):
        return _vazio(ax, 'sem geracao distribuida nesta rede')
    h = [i * 24.0 / len(gd_kw) for i in range(len(gd_kw))]
    carga = [(f or 0) + (g or 0) for f, g in zip(fonte_kw or [0] * len(gd_kw),
                                                 gd_kw)]
    ax.plot(h, carga, color=COR_NEUTRA, lw=1.3, label='carga total')
    ax.plot(h, gd_kw, color=COR_OK, lw=1.4, label='geracao distribuida')
    reverso = [i for i, (g, c) in enumerate(zip(gd_kw, carga)) if g > c]
    if reverso:
        ax.fill_between(h, 0, max(carga) if carga else 1,
                        where=[i in set(reverso) for i in range(len(h))],
                        color=COR_RUIM, alpha=0.10)
        ax.set_title('Geração no dia — FLUXO REVERSO em %d passos (%.1f h)'
                     % (len(reverso), len(reverso) * 0.25),
                     fontsize=10, loc='left')
    else:
        ax.set_title('Geração no dia — sem fluxo reverso', fontsize=10,
                     loc='left')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(fontsize=7, frameon=False)
    return _acaba(ax, ax.get_title(), 'hora', 'kW')


def cobertura_da_gd(ax, fonte_kw, gd_kw):
    """Que fracao da carga a GD cobre, passo a passo.

    O numero do dia inteiro esconde o essencial: a GD pode cobrir 60% ao meio-
    dia e 0% no pico das 19 h. E essa NAO-COINCIDENCIA que define se ela alivia
    a rede ou apenas desloca energia.
    """
    if not gd_kw or not any(gd_kw):
        return _vazio(ax, 'sem geracao distribuida nesta rede')
    h = [i * 24.0 / len(gd_kw) for i in range(len(gd_kw))]
    carga = [(f or 0) + (g or 0) for f, g in zip(fonte_kw or [0] * len(gd_kw),
                                                 gd_kw)]
    pct = [100.0 * g / c if c > 0 else 0.0 for g, c in zip(gd_kw, carga)]
    ax.fill_between(h, pct, color=COR_OK, alpha=0.30)
    ax.plot(h, pct, color=COR_OK, lw=1.2)
    ax.axhline(100, color=COR_RUIM, lw=0.9, ls='--')
    # a hora do pico de carga, que quase nunca e a do pico de geracao
    if carga:
        i_pico = max(range(len(carga)), key=lambda k: carga[k])
        ax.axvline(h[i_pico], color=COR_NEUTRA, lw=0.9, ls=':')
        ax.text(h[i_pico], max(pct) * 0.95 if pct else 1,
                ' pico de carga: a GD cobre %.0f%%' % pct[i_pico],
                fontsize=7, color=COR_NEUTRA, va='top')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    return _acaba(ax, 'Cobertura da carga pela GD', 'hora', '% da carga')


def carregamento_liquido(ax, fonte_kw):
    """O que a subestacao ve: carga menos geracao, ao longo do dia.

    O MINIMO desta curva importa tanto quanto o maximo. Carregamento minimo e
    quando a rede esta mais descarregada e a tensao mais alta — a condicao
    critica de sobretensao por GD, e a que o estudo de ponta nunca ve.
    """
    if not fonte_kw:
        return _vazio(ax, 'sem serie diaria')
    h = [i * 24.0 / len(fonte_kw) for i in range(len(fonte_kw))]
    ax.plot(h, fonte_kw, color=COR_NEUTRA, lw=1.4)
    ax.fill_between(h, fonte_kw, color=COR_NEUTRA, alpha=0.12)
    lo = min(fonte_kw)
    hi = max(fonte_kw)
    i_lo = fonte_kw.index(lo)
    ax.scatter([h[i_lo]], [lo], s=28, color=COR_RUIM, zorder=5)
    ax.annotate('mínimo de %s kW às %.1f h' % (_mil(lo), h[i_lo]),
                (h[i_lo], lo), textcoords='offset points', xytext=(6, 8),
                fontsize=7, color=COR_RUIM)
    if lo < 0:
        ax.axhline(0, color=COR_RUIM, lw=1.0)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    return _acaba(ax, 'Carregamento líquido na cabeceira — variação de %.0fx'
                  % (hi / lo if lo > 0 else float('inf')), 'hora', 'kW')
