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


def _dec(x, casas=2):
    """Numero com VIRGULA decimal, que e como se escreve em portugues."""
    try:
        return (('%%.%df' % casas) % float(x)).replace('.', ',')
    except (TypeError, ValueError):
        return '—'


def _mil(x):
    """Número com ponto de milhar, à brasileira."""
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return '—'


# ------------------------------------------------------------------ tipografia
#
# UMA ESCALA SO, e nao um numero solto em cada chamada. As figuras entram no
# PDF com 150 mm de largura enquanto sao desenhadas com 9 polegadas (229 mm):
# tudo encolhe para dois tercos no papel, e o rotulo de 7 pt que parecia bom na
# tela vira 4,6 pt impresso — ilegivel. Mexer aqui mexe em todas as figuras de
# uma vez, que e o unico jeito de manter o relatorio consistente.
ESCALA_FONTE = 1.45


def _fs(base):
    """O tamanho de fonte, ja na escala do relatorio."""
    return round(base * ESCALA_FONTE, 1)


def _vazio(ax, motivo):
    """Diz por que nao ha figura, em vez de deixar o eixo em branco."""
    ax.text(0.5, 0.5, motivo, ha='center', va='center', fontsize=_fs(9),
            color=COR_NEUTRA, wrap=True, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ('top', 'right', 'bottom', 'left'):
        ax.spines[lado].set_visible(False)
    return ax


def _acaba(ax, titulo, x=None, y=None, pad=None):
    # `pad` afasta o titulo do eixo, para caber uma faixa de numeros embaixo
    # dele. Passe-o AQUI: `ax.get_title()` devolve o titulo CENTRAL, e como
    # este projeto usa `loc='left'`, reescrever o titulo depois com o que
    # `get_title()` devolve apaga o titulo com uma string vazia — o que
    # aconteceu, e a figura saiu sem titulo nenhum.
    ax.set_title(titulo, fontsize=_fs(10), loc='left',
                 **({'pad': pad} if pad else {}))
    if x:
        ax.set_xlabel(x, fontsize=_fs(8))
    if y:
        ax.set_ylabel(y, fontsize=_fs(8))
    ax.tick_params(labelsize=_fs(7))
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

def _percentil(v, q):
    """O percentil `q` (0 a 1) de uma lista ja ORDENADA, sem numpy."""
    if not v:
        return None
    k = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
    return v[k]


def _faixa_util(valores, referencia=None, cobertura=0.998, folga=0.06,
                alcance=float('inf')):
    """O intervalo do eixo que mostra O DADO, e nao o vazio em volta dele.

    UM ponto perdido em 1,55 pu estica o eixo ate la e espreme os outros dez
    mil numa tira de um centimetro no rodape — a figura fica tecnicamente
    correta e analiticamente inutil, que foi exatamente o que aconteceu com o
    perfil da 5003305.

    A regra: o eixo cobre 99,8% dos pontos, e SEMPRE inclui as linhas de
    referencia (a faixa do PRODIST), porque e contra elas que se julga. O que
    sobrar fora vira contagem anotada na figura, e nao escala desperdicada —
    saber que existem tres barras acima de 1,4 pu e a informacao util; ver o
    espaco vazio ate la nao e.

    `alcance` limita ate onde vale a pena esticar o eixo para alcancar uma
    referencia, em multiplos da largura do dado. Com tudo carregando abaixo de
    40% da ampacidade, arrastar o eixo ate a linha de 100% gasta seis decimos
    da figura para desenhar nada — ali `alcance=1` deixa a linha de fora e a
    figura anota que ela nao cabe. Ja na tensao a faixa do PRODIST fica logo ao
    lado do dado e e o criterio de julgamento, entao ela entra sempre.

    Devolve (baixo, alto, n_abaixo, n_acima).
    """
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None, None, 0, 0
    lo = _percentil(v, (1.0 - cobertura) / 2.0)
    hi = _percentil(v, 1.0 - (1.0 - cobertura) / 2.0)
    if referencia:
        limite = (hi - lo) * alcance if alcance != float('inf') else None
        for r in referencia:
            if limite is not None and not (lo - limite <= r <= hi + limite):
                continue
            lo, hi = min(lo, r), max(hi, r)
    if hi <= lo:
        lo, hi = lo - 0.05, hi + 0.05
    m = (hi - lo) * folga
    lo, hi = lo - m, hi + m
    return lo, hi, sum(1 for x in v if x < lo), sum(1 for x in v if x > hi)


def _avisa_cortados(ax, n_abaixo, n_alto, unidade='', vertical=True):
    """A contagem do que ficou fora do eixo, escrita na propria figura.

    Sem isto o corte de escala vira mentira: quem olha ve uma nuvem inteira
    dentro da faixa e nao fica sabendo que ha pontos alem do quadro.
    """
    partes = []
    if n_abaixo:
        partes.append('%d abaixo do eixo' % n_abaixo)
    if n_alto:
        partes.append('%d acima do eixo' % n_alto)
    if not partes:
        return
    ax.text(0.99, 0.97 if vertical else 0.03, ' · '.join(partes) + unidade,
            transform=ax.transAxes, ha='right',
            va='top' if vertical else 'bottom',
            fontsize=_fs(7.5), color=COR_RUIM,
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec=COR_RUIM,
                      lw=0.6, alpha=0.9))


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
    ax.axhspan(V_ADEQUADA[0], V_ADEQUADA[1], color=COR_OK, alpha=0.07, lw=0)
    for y, txt in ((V_ADEQUADA[0], 'limite inferior do PRODIST  %s pu'),
                   (V_ADEQUADA[1], 'limite superior do PRODIST  %s pu')):
        ax.axhline(y, color=COR_RUIM, lw=0.8, ls='--')
        ax.text(0.005, y, txt % _dec(y), transform=ax.get_yaxis_transform(),
                fontsize=_fs(7), color=COR_RUIM, va='bottom', ha='left')

    # A ESCALA SEGUE O DADO, e nao o ponto perdido. Ver `_faixa_util`.
    lo, hi, n_b, n_a = _faixa_util(pus, referencia=V_ADEQUADA)
    ax.set_ylim(lo, hi)
    _avisa_cortados(ax, n_b, n_a)

    # A TENDENCIA, tracada sobre a nuvem. E ela que separa queda ohmica (desce
    # continuamente) de ilhamento (patamar) e de regulador (degrau), e a olho
    # nu numa nuvem de dez mil pontos essa distincao nao se faz.
    ordem = sorted(zip(distancias, pus))
    n = len(ordem)
    if n >= 20:
        faixas = 24
        px, py = [], []
        for k in range(faixas):
            pedaco = ordem[k * n // faixas:(k + 1) * n // faixas]
            if pedaco:
                px.append(sum(d for d, _ in pedaco) / len(pedaco))
                py.append(sum(p for _, p in pedaco) / len(pedaco))
        if len(px) > 2:
            ax.plot(px, py, color='#263238', lw=1.8, alpha=0.9)
            # ROTULO NA PROPRIA LINHA, e nao numa legenda. Com a fonte no
            # tamanho legivel a caixa da legenda ocupava um quinto da figura e
            # cobria o limite inferior do PRODIST; encostada na curva ela
            # identifica a linha sem disputar espaco com o dado.
            # No ALTO, acompanhando o inicio da curva: ali o eixo esta vazio
            # em rede sadia (a nuvem fica embaixo) e a seta liga o rotulo a
            # linha sem que ele encoste em nada.
            ax.annotate('tensão média por faixa de distância',
                        xy=(px[1], py[1]), xytext=(0.13, 0.80),
                        textcoords='axes fraction',
                        fontsize=_fs(7), color='#263238', ha='left',
                        arrowprops=dict(arrowstyle='->', color='#263238',
                                        lw=0.9, alpha=0.8),
                        bbox=dict(boxstyle='round,pad=0.3', fc='white',
                                  ec='#cfd8dc', lw=0.6, alpha=0.9))

    # OS NUMEROS NA PROPRIA FIGURA. Antes era preciso ir a tabela para saber a
    # tensao minima; agora a figura responde sozinha o que ela mesma levanta.
    vmin, vmax = min(pus), max(pus)
    dmax = max(distancias)
    fora = sum(1 for p in pus if p < V_ADEQUADA[0] or p > V_ADEQUADA[1])
    resumo = ('%s barras  ·  mín %s pu  ·  máx %s pu  ·  queda %s pu\n'
              '%s km até a barra mais distante  ·  %s fora da faixa (%s%%)'
              % (_mil(len(pus)), _dec(vmin, 3), _dec(vmax, 3),
                 _dec(vmax - vmin, 3), _dec(dmax, 1), _mil(fora),
                 _dec(100.0 * fora / len(pus), 1)))
    # A CAIXA SAI DE DENTRO DO GRAFICO. Dentro dela disputava espaco com a
    # nuvem, com o rotulo do limite inferior e com a linha de tendencia, e nao
    # havia canto livre em toda figura: rede boa enche o meio, rede ruim enche
    # embaixo. Abaixo do titulo o espaco e sempre nosso, e o numero e lido
    # ANTES da figura, que e a ordem certa.
    ax.text(0.0, 1.01, resumo, transform=ax.transAxes, ha='left',
            va='bottom', fontsize=_fs(7.5), color=COR_NEUTRA, linespacing=1.6)
    # a barra de menor tensao, marcada onde ela esta
    i_pior = min(range(len(pus)), key=lambda k: pus[k])
    if lo <= pus[i_pior] <= hi:
        ax.annotate('mínimo %s pu' % _dec(vmin, 3),
                    xy=(distancias[i_pior], pus[i_pior]),
                    xytext=(8, 14), textcoords='offset points', fontsize=_fs(7.5),
                    color=COR_RUIM,
                    arrowprops=dict(arrowstyle='->', color=COR_RUIM, lw=0.8))
    return _acaba(ax, 'Perfil de tensão contra distância da fonte',
                  'distância elétrica da fonte (km)', 'tensão (pu)', pad=48)


def histograma_de_tensao(ax, pus):
    """Quanto da rede esta fora da faixa adequada, e para que lado."""
    if not pus:
        return _vazio(ax, 'sem barras de MT com tensao')
    # Mesma regra do perfil: a escala segue o dado. Um punhado de barras em
    # 1,5 pu fazia o histograma inteiro virar uma barra unica encostada na
    # esquerda, e nao se enxergava mais NADA da distribuicao que importa.
    lo, hi, n_b, n_a = _faixa_util(pus, referencia=V_ADEQUADA)
    dentro = [p for p in pus if lo <= p <= hi]
    ax.hist(dentro or pus, bins=48, range=(lo, hi), color=COR_NEUTRA,
            alpha=0.85)
    ax.axvspan(V_ADEQUADA[0], V_ADEQUADA[1], color=COR_OK, alpha=0.07, lw=0)
    for x in V_ADEQUADA:
        ax.axvline(x, color=COR_RUIM, lw=0.9, ls='--')
        ax.text(x, 0.98, ' %s pu' % _dec(x), transform=ax.get_xaxis_transform(),
                fontsize=_fs(7), color=COR_RUIM, va='top', rotation=90)
    ax.set_xlim(lo, hi)
    _avisa_cortados(ax, n_b, n_a)

    baixo = sum(1 for p in pus if p < V_ADEQUADA[0])
    alto = sum(1 for p in pus if p > V_ADEQUADA[1])
    med = sorted(pus)[len(pus) // 2]
    ax.axvline(med, color='#263238', lw=1.4)
    ax.text(med, 0.55, ' mediana %s pu' % _dec(med, 3), fontsize=_fs(7.5),
            transform=ax.get_xaxis_transform(), color='#263238', rotation=90,
            va='center')
    # PARA QUE LADO a rede sai da faixa, que e a pergunta que o histograma
    # existe para responder: abaixo e queda de tensao, acima e geracao ou
    # regulador alto, e o tratamento e oposto.
    ax.text(0.99, 0.97,
            '%s barras  ·  %s abaixo de %s pu  ·  %s acima de %s pu'
            % (_mil(len(pus)), _mil(baixo), _dec(V_ADEQUADA[0]),
               _mil(alto), _dec(V_ADEQUADA[1])),
            transform=ax.transAxes, ha='right', va='top', fontsize=_fs(7.5),
            color=COR_NEUTRA,
            bbox=dict(boxstyle='round,pad=0.35', fc='white', ec=COR_CLARA,
                      lw=0.6, alpha=0.92))
    fora = baixo + alto
    return _acaba(ax, 'Tensão nas barras de MT — %s de %s fora da faixa (%s%%)'
                  % (_mil(fora), _mil(len(pus)),
                     _dec(100.0 * fora / len(pus), 1)),
                  'tensão (pu)', 'número de barras')


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
    ax.legend(fontsize=_fs(7), frameon=False)
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
    # O teto fixo de 200% a 400% resolvia metade do problema: numa rede em que
    # tudo carrega abaixo de 20%, o histograma ficava espremido no primeiro
    # decimo do eixo. A faixa util resolve os dois lados.
    lo, hi, _n_b, n_a = _faixa_util(pcts, referencia=(0.0, 100.0), folga=0.04,
                                    alcance=1.0)
    lo = max(0.0, lo)
    dentro = [min(max(p, lo), hi) for p in pcts]
    ax.hist(dentro, bins=48, range=(lo, hi), color=COR_NEUTRA, alpha=0.85)
    ax.axvspan(lo, min(100.0, hi), color=COR_OK, alpha=0.06, lw=0)
    if hi >= 100.0:
        ax.axvline(100, color=COR_RUIM, lw=1.1, ls='--')
        ax.text(100, 0.98, ' ampacidade declarada (100%)',
                transform=ax.get_xaxis_transform(), fontsize=_fs(7),
                color=COR_RUIM, va='top', rotation=90)
    else:
        # A LINHA DE 100% NAO CABE, e isso e a boa noticia: dizer por escrito
        # onde ela ficaria informa mais do que desenhar meio grafico vazio ate
        # ela.
        ax.text(0.99, 0.86, 'a linha de 100%% fica fora do eixo — o trecho '
                'mais carregado chega a %s%%' % _dec(max(pcts), 1),
                transform=ax.transAxes, ha='right', va='top', fontsize=_fs(7.5),
                color=COR_OK, style='italic')
    ax.set_xlim(lo, hi)
    _avisa_cortados(ax, 0, n_a)

    acima = sum(1 for p in pcts if p > 100)
    pior = max(pcts)
    med = sorted(pcts)[len(pcts) // 2]
    ax.text(0.99, 0.97,
            '%s trechos  ·  mediana %s%%  ·  pior %s%%\n'
            '%s acima da ampacidade (%s%%)'
            % (_mil(len(pcts)), _dec(med, 1), _dec(pior, 1), _mil(acima),
               _dec(100.0 * acima / len(pcts), 1)),
            transform=ax.transAxes, ha='right', va='top', fontsize=_fs(7.5),
            color=COR_NEUTRA, linespacing=1.5,
            bbox=dict(boxstyle='round,pad=0.35', fc='white', ec=COR_CLARA,
                      lw=0.6, alpha=0.92))
    return _acaba(ax, 'Carregamento dos condutores — %s de %s acima de 100%%'
                  % (_mil(acima), _mil(len(pcts))),
                  '% da ampacidade declarada', 'número de trechos')


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
        ax.text(x + largura * 0.012, k, _rotulo(x), va='center', fontsize=_fs(7),
                color=COR_RUIM if (destacar and x > destacar) else COR_NEUTRA)
    ax.set_xlim(0, largura * 1.16)
    ax.set_yticks(range(len(v)))
    ax.set_yticklabels(n, fontsize=_fs(6))
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
                ha='center', va='center', fontsize=_fs(9), color=cor,
                linespacing=1.5)
    ax.set_yticks([])
    ax.set_ylim(-0.45, 0.45)
    ax.set_title('Onde a perda acontece — %s kW no total' % _mil(tot),
                 fontsize=_fs(10), loc='left')
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
    ax.set_title(titulo, fontsize=_fs(10), loc='left')
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
                ha='center', va='bottom', fontsize=_fs(7), color=cores[k],
                linespacing=1.3)
    ax.set_ylim(0, max(v) * 1.25)
    ax.set_xticks(range(len(v)))
    ax.set_xticklabels(n, fontsize=_fs(6), rotation=20, ha='right')
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
                fontsize=_fs(7), color=COR_OK, ha='left',
                xytext=(4, 0), textcoords='offset points')
    if corte is not None:
        ax.axvline(corte, color=COR_RUIM, lw=1.0, ls='--')
        acima = sum(1 for x in valores if x > corte)
        ax.annotate('%d acima de %g' % (acima, corte),
                    (corte, ax.get_ylim()[1] * 0.78), fontsize=_fs(7),
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
    ax.set_title(titulo, fontsize=_fs(10), loc='left')
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
    ax.set_xticklabels(nomes, fontsize=_fs(6), rotation=60, ha='right')
    ax.legend(fontsize=_fs(7), frameon=False)
    return _acaba(ax, titulo, None, unidade)


def texto(ax, linhas, titulo=None):
    """Um painel de numeros. Nem tudo vira grafico, e forcar barra onde cabe
    uma tabela de seis linhas so gasta tinta."""
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ('top', 'right', 'bottom', 'left'):
        ax.spines[lado].set_visible(False)
    if titulo:
        ax.set_title(titulo, fontsize=_fs(10), loc='left')
    y = 0.92
    for L in linhas[:14]:
        ax.text(0.02, y, L, fontsize=_fs(8), va='top', transform=ax.transAxes,
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
                     fontsize=_fs(10), loc='left')
    else:
        ax.set_title('Geração no dia — sem fluxo reverso', fontsize=_fs(10),
                     loc='left')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(fontsize=_fs(7), frameon=False)
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
                fontsize=_fs(7), color=COR_NEUTRA, va='top')
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
                fontsize=_fs(7), color=COR_RUIM)
    if lo < 0:
        ax.axhline(0, color=COR_RUIM, lw=1.0)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    return _acaba(ax, 'Carregamento líquido na cabeceira — variação de %.0fx'
                  % (hi / lo if lo > 0 else float('inf')), 'hora', 'kW')


def duracao_de_carga(ax, fonte_kw):
    """A curva de duracao: a carga ordenada do maior para o menor.

    Responde o que a curva do dia nao responde — nao QUANDO a carga e alta,
    mas por QUANTO TEMPO. Pico que dura quinze minutos e questao de protecao;
    o mesmo pico sustentado por seis horas e questao de condutor, e as duas
    curvas do dia podem ter o mesmo maximo.
    """
    v = sorted((x for x in (fonte_kw or []) if x is not None), reverse=True)
    if not v:
        return _vazio(ax, 'sem série diária')
    h = [(i + 1) * 24.0 / len(v) for i in range(len(v))]
    ax.fill_between(h, v, color=COR_NEUTRA, alpha=0.25, lw=0)
    ax.plot(h, v, color=COR_NEUTRA, lw=1.6)
    pico, med = v[0], sum(v) / len(v)
    ax.axhline(med, color=COR_ATENCAO, ls='--', lw=1.2,
               label='média %s kW  (fator de carga %.2f)'
                     % (_mil(med), med / pico if pico else 0))
    # As horas acima de 90% do pico, que e o numero que dimensiona o condutor.
    n90 = sum(1 for x in v if x >= 0.9 * pico)
    if n90:
        t90 = n90 * 24.0 / len(v)
        ax.axvspan(0, t90, color=COR_RUIM, alpha=0.10, lw=0,
                   label='%.1f h acima de 90%% do pico' % t90)
    ax.axhline(pico, color=COR_RUIM, ls=':', lw=1.0)
    ax.annotate('pico %s kW' % _mil(pico), xy=(0.3, pico), fontsize=_fs(8),
                color=COR_RUIM, va='bottom')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(fontsize=_fs(7.5), framealpha=0.9)
    return _acaba(ax, 'Curva de duração da carga',
                  'horas em que a carga é pelo menos o valor do eixo Y', 'kW')


def perda_contra_carga(ax, fonte_kw, perdas_kw):
    """Perda contra carga, um ponto por passo de 15 min.

    A perda ohmica vai com o QUADRADO da corrente, entao os pontos deveriam
    cair sobre uma parabola que passa perto da origem. O que a nuvem mostra e
    o intercepto: onde a parabola cruza carga zero esta a perda a vazio — o
    ferro dos transformadores, que existe com a rede vazia e nao aparece em
    nenhuma medicao de ponta.
    """
    par = [(f, p) for f, p in zip(fonte_kw or [], perdas_kw or [])
           if f is not None and p is not None and f > 0]
    if len(par) < 5:
        return _vazio(ax, 'sem série diária')
    xs = [a for a, _ in par]
    ys = [b for _, b in par]
    ax.scatter(xs, ys, s=18, color=COR_NEUTRA, alpha=0.65, edgecolors='none')
    # ajuste a*x^2 + c por minimos quadrados em duas incognitas, resolvido a
    # mao para nao arrastar numpy so por isto.
    n = len(par)
    s4 = sum(x ** 4 for x in xs)
    s2 = sum(x ** 2 for x in xs)
    sy = sum(ys)
    sx2y = sum(x * x * y for x, y in par)
    det = s4 * n - s2 * s2
    if det:
        a = (sx2y * n - s2 * sy) / det
        c = (s4 * sy - s2 * sx2y) / det
        lo, hi = min(xs), max(xs)
        gx = [lo + (hi - lo) * k / 60.0 for k in range(61)]
        ax.plot(gx, [a * x * x + c for x in gx], color=COR_RUIM, lw=1.6,
                label='ajuste quadrático')
        if c > 0:
            ax.axhline(c, color=COR_ATENCAO, ls='--', lw=1.2,
                       label='perda a vazio ≈ %s kW (o ferro)' % _mil(c))
        ax.legend(fontsize=_fs(7.5), framealpha=0.9)
    return _acaba(ax, 'A perda segue o quadrado da carga',
                  'potência da fonte (kW)', 'perdas (kW)')


def perdas_por_alimentador(ax, alimentadores, quantos=15):
    """Ranking de perda por alimentador, em % e em kWh.

    A perda agregada da subestacao ESCONDE QUEM DOMINA: e comum um punhado de
    alimentadores responder pela maior parte da perda, e trabalhar sobre a
    media da subestacao seria tratar o sintoma errado. O eixo mostra o
    percentual, que compara; o rotulo traz o kWh, que dimensiona.
    """
    itens = [(d.get('perdas_pct'), n, d.get('kWh_perdas') or 0)
             for n, d in (alimentadores or {}).items()
             if d.get('perdas_pct') is not None and (d.get('kWh') or 0) > 0]
    if not itens:
        return _vazio(ax, 'sem energia por alimentador')
    itens.sort(reverse=True)
    itens = itens[:quantos]
    nomes = [n for _p, n, _k in itens][::-1]
    pcts = [p for p, _n, _k in itens][::-1]
    kwh = [k for _p, _n, k in itens][::-1]
    cores = [COR_RUIM if p > 10 else (COR_ATENCAO if p > 8 else COR_NEUTRA)
             for p in pcts]
    ax.barh(range(len(pcts)), pcts, color=cores, height=0.72)
    ax.set_yticks(range(len(nomes)))
    ax.set_yticklabels(nomes, fontsize=_fs(6.5))
    largura = max(pcts) or 1
    for k, (p, e) in enumerate(zip(pcts, kwh)):
        ax.text(p + largura * 0.015, k, '%s%%   (%s kWh)' % (_dec(p, 2), _mil(e)),
                va='center', fontsize=_fs(6.5), color=COR_NEUTRA)
    ax.set_xlim(0, largura * 1.34)
    if largura > 10:
        ax.axvline(10, color=COR_RUIM, lw=0.9, ls='--')
    ax.text(0.0, 1.01, '%d alimentadores mostrados  ·  somam %s kWh de perda'
            % (len(itens), _mil(sum(kwh))), transform=ax.transAxes,
            fontsize=_fs(7.5), color=COR_NEUTRA, va='bottom')
    return _acaba(ax, 'Perda por alimentador (maiores primeiro)',
                  '% da energia que entra no alimentador', None, pad=26)


def tensao_por_alimentador(ax, por_alim):
    """A faixa de tensao de cada alimentador: minimo, mediana e maximo.

    O histograma da subestacao mistura tudo; aqui se ve QUAL alimentador puxa
    a cauda. Uma subestacao com 8% das barras fora da faixa pode ter oito
    alimentadores levemente baixos ou UM inteiro afundado, e o tratamento e
    completamente diferente.
    """
    itens = [(min(v), sorted(v)[len(v) // 2], max(v), n)
             for n, v in (por_alim or {}).items() if v]
    if not itens:
        return _vazio(ax, 'sem tensão por alimentador')
    itens.sort()
    # A ESCALA SAI DAS MEDIANAS, e nao dos extremos. Com catorze alimentadores
    # nao ha percentil que apare um valor unico, e bastou UM alimentador com
    # uma barra em 1,55 pu para o eixo ir ate la e comprimir os catorze numa
    # coluna de meio centimetro. O extremo que nao couber vira seta e contagem.
    base = [x for it in itens for x in (it[0], it[1])]
    lo, hi, _nb, _na = _faixa_util(base, referencia=V_ADEQUADA, folga=0.05)
    estourados = 0
    for k, (lo_, med, hi_, _nome) in enumerate(itens):
        # a cor vem do pior lado, e nao so do minimo: alimentador com barra
        # muito ALTA e tao anomalo quanto um com barra muito baixa.
        pior = lo_ if (V_ADEQUADA[0] - lo_) >= (hi_ - V_ADEQUADA[1]) else hi_
        ax.plot([max(lo_, lo), min(hi_, hi)], [k, k], color=_cor_da_tensao(pior),
                lw=2.6, alpha=0.8, solid_capstyle='round')
        if lo <= med <= hi:
            ax.plot([med], [k], marker='|', color='#263238', ms=9, mew=1.6)
        if hi_ > hi:
            estourados += 1
            ax.annotate('%s pu' % _dec(hi_, 3), xy=(hi, k), xytext=(-6, 0),
                        textcoords='offset points', fontsize=_fs(6),
                        color=COR_RUIM, va='center', ha='right',
                        arrowprops=dict(arrowstyle='->', color=COR_RUIM,
                                        lw=1.0))
    ax.set_yticks(range(len(itens)))
    ax.set_yticklabels([x[3] for x in itens], fontsize=_fs(6.5))
    ax.axvspan(V_ADEQUADA[0], V_ADEQUADA[1], color=COR_OK, alpha=0.08, lw=0)
    for x in V_ADEQUADA:
        ax.axvline(x, color=COR_RUIM, lw=0.9, ls='--')
    ax.set_xlim(lo, hi)
    _avisa_cortados(ax, 0, estourados)
    fora = sum(1 for x in itens if x[0] < V_ADEQUADA[0] or x[2] > V_ADEQUADA[1])
    ax.text(0.0, 1.01, '%d alimentadores  ·  %d com pelo menos um ponto fora da '
            'faixa  ·  o traço é mín–máx, o risco é a mediana'
            % (len(itens), fora), transform=ax.transAxes, fontsize=_fs(7.5),
            color=COR_NEUTRA, va='bottom')
    return _acaba(ax, 'Faixa de tensão por alimentador', 'tensão (pu)', None,
                  pad=26)


def duracao_de_tensao(ax, pus):
    """Curva de duracao da TENSAO: quanto da rede esta acima de cada nivel.

    Responde o que o histograma nao responde de relance — nao quantas barras ha
    em cada faixa, mas quanto da rede esta abaixo de um limite qualquer que se
    queira escolher. Ler "10% da rede abaixo de 0,95 pu" e imediato aqui e
    exige somar barras no histograma.
    """
    v = sorted((x for x in (pus or []) if x is not None), reverse=True)
    if not v:
        return _vazio(ax, 'sem barras de MT com tensão')
    fr = [100.0 * (i + 1) / len(v) for i in range(len(v))]
    lo, hi, nb, na = _faixa_util(v, referencia=V_ADEQUADA)
    ax.plot(fr, v, color=COR_NEUTRA, lw=2.0)
    ax.fill_between(fr, v, lo, color=COR_NEUTRA, alpha=0.13, lw=0)
    ax.axhspan(V_ADEQUADA[0], V_ADEQUADA[1], color=COR_OK, alpha=0.08, lw=0)
    for y in V_ADEQUADA:
        ax.axhline(y, color=COR_RUIM, lw=0.9, ls='--')
    ax.set_ylim(lo, hi)
    _avisa_cortados(ax, nb, na)
    marcas = []
    for corte in (0.95, V_ADEQUADA[0]):
        abaixo = sum(1 for x in v if x < corte)
        if abaixo:
            p = 100.0 * abaixo / len(v)
            ax.plot([100 - p, 100 - p], [lo, corte], color=COR_ATENCAO, lw=1.0,
                    ls=':')
            marcas.append('%s%% abaixo de %s pu' % (_dec(p, 1), _dec(corte, 2)))
    ax.set_xlim(0, 100)
    ax.text(0.0, 1.01, '%s barras  ·  %s'
            % (_mil(len(v)), '  ·  '.join(marcas) or 'nenhuma abaixo de 0,95 pu'),
            transform=ax.transAxes, fontsize=_fs(7.5), color=COR_NEUTRA,
            va='bottom')
    return _acaba(ax, 'Curva de duração da tensão',
                  '% das barras com tensão pelo menos igual ao eixo Y',
                  'tensão (pu)', pad=26)


def comprimento_dos_trechos(ax, kms):
    """Distribuicao do comprimento de trecho — o denominador de tudo.

    Rede feita de milhares de trechos de dez metros e rede feita de centenas de
    trechos de um quilometro respondem de forma diferente a mesma perda. E
    trecho de comprimento ZERO e defeito de cadastro que so aparece aqui: ele
    nao move o total de quilometros o bastante para chamar atencao em lugar
    nenhum.
    """
    v = [x for x in (kms or []) if x is not None and x >= 0]
    if not v:
        return _vazio(ax, 'sem comprimento de trecho')
    m = [x * 1000.0 for x in v]
    lo, hi, _nb, na = _faixa_util(m, folga=0.02)
    lo = max(0.0, lo)
    ax.hist([min(max(x, lo), hi) for x in m], bins=48, range=(lo, hi),
            color=COR_NEUTRA, alpha=0.85)
    _avisa_cortados(ax, 0, na)
    zeros = sum(1 for x in m if x <= 0.01)
    med = sorted(m)[len(m) // 2]
    ax.axvline(med, color='#263238', lw=1.4)
    ax.text(med, 0.6, ' mediana %s m' % _dec(med, 1), rotation=90,
            transform=ax.get_xaxis_transform(), fontsize=_fs(7),
            color='#263238', va='center')
    resumo = ('%s trechos  ·  mediana %s m  ·  maior %s m  ·  total %s km'
              % (_mil(len(m)), _dec(med, 1), _mil(max(m)), _dec(sum(v), 1)))
    if zeros:
        resumo += ('\n%s trechos com comprimento ZERO — cadastro incompleto'
                   % _mil(zeros))
    ax.text(0.0, 1.01, resumo, transform=ax.transAxes, fontsize=_fs(7.5),
            color=COR_RUIM if zeros else COR_NEUTRA, va='bottom',
            linespacing=1.6)
    return _acaba(ax, 'Comprimento dos trechos de média tensão',
                  'comprimento do trecho (m)', 'número de trechos',
                  pad=42 if zeros else 26)


def reativo_no_dia(ax, fonte_kw, fonte_kvar):
    """Ativa, reativa e fator de potencia na cabeceira, ao longo do dia.

    O fator de potencia NAO e constante: ele cai no vale, quando o reativo dos
    transformadores pesa sobre uma ativa pequena. Abaixo de 0,92 a distribuidora
    e cobrada por excedente de reativo, e um numero unico de ponta esconde
    exatamente as horas em que isso acontece.
    """
    q = list(fonte_kvar or [])
    if not fonte_kw or not any(x is not None for x in q):
        return _vazio(ax, 'a série não traz o reativo — refaça a etapa de energia')
    n = len(fonte_kw)
    h = [i * 24.0 / n for i in range(n)]
    ax.plot(h, fonte_kw, color=COR_NEUTRA, lw=2.0, label='ativa (kW)')
    ax.plot(h, q, color='#7b1fa2', lw=1.6, ls='--', label='reativa (kvar)')
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(fontsize=_fs(7), loc='upper left', frameon=False)

    b = ax.twinx()
    fp = []
    for p, x in zip(fonte_kw, q):
        if p is None or x is None:
            fp.append(None)
            continue
        s = (p * p + x * x) ** 0.5
        fp.append(abs(p) / s if s else None)
    b.plot(h, fp, color=COR_ATENCAO, lw=1.8)
    b.axhline(0.92, color=COR_RUIM, lw=1.0, ls=':')
    # O EIXO DO FP TAMBEM SEGUE O DADO. Fixo em 0 a 1,06 ele espremia toda a
    # variacao — que numa subestacao real cabe entre 0,87 e 0,93 — em cinco por
    # cento da altura, e a curva virava uma reta colada no teto. Aqui o
    # intervalo interessante e estreito por natureza, e e nele que se decide se
    # ha excedente de reativo.
    bons = [x for x in fp if x is not None]
    if bons:
        pmin, pmax = min(bons), max(bons)
        alvo_lo = min(pmin, 0.92) - 0.02
        alvo_hi = max(pmax, 0.92) + 0.02
        b.set_ylim(max(0.0, alvo_lo), min(1.02, alvo_hi))
    else:
        b.set_ylim(0, 1.06)
    b.set_ylabel('fator de potência', fontsize=_fs(8), color=COR_ATENCAO)
    b.tick_params(labelsize=_fs(7), colors=COR_ATENCAO)
    # FP SO TEM SENTIDO ONDE HA POTENCIA ATIVA. Quando P cruza o zero — e na
    # Roraima ha subestacoes que exportam metade do dia — o fator de potencia
    # despenca para 0,000 sem que nada de fisico tenha acontecido: e a divisao
    # de um numero pequeno por outro. Reportar esse minimo como "o fator de
    # potencia da subestacao" seria descrever um artefato aritmetico.
    pico = max((abs(x) for x in fonte_kw if x is not None), default=0)
    validos = [x for x, p in zip(fp, fonte_kw)
               if x is not None and p is not None and abs(p) > 0.05 * pico]
    if validos:
        abaixo = sum(1 for x in validos if x < 0.92) * 24.0 / n
        ax.text(0.0, 1.01, 'fator de potência entre %s e %s  ·  %s h abaixo de '
                '0,92 (limite de excedente de reativo)'
                % (_dec(min(validos), 3), _dec(max(validos), 3), _dec(abaixo, 2)),
                transform=ax.transAxes, fontsize=_fs(7.5), color=COR_NEUTRA,
                va='bottom')
    return _acaba(ax, 'Ativa, reativa e fator de potência na cabeceira',
                  'hora', 'potência', pad=26)


def mapa_de_carregamento(ax, segmentos):
    """A rede desenhada, com a COR indicando carregamento do condutor.

    O mapa de tensao mostra onde a rede esta fraca; este mostra por onde a
    corrente passa. Sao perguntas diferentes e costumam ter respostas
    diferentes — tronco muito carregado tem tensao boa, porque esta perto da
    fonte.
    """
    segs = [s for s in (segmentos or []) if s and s[4] is not None]
    if not segs:
        return _vazio(ax, 'sem coordenadas de trecho')
    faixas = [(0, 30, COR_OK, 'até 30%'), (30, 60, '#9ccc65', '30 a 60%'),
              (60, 100, COR_ATENCAO, '60 a 100%'),
              (100, float('inf'), COR_RUIM, 'acima de 100%')]
    for lo, hi, cor, rot in faixas:
        xs, ys, n = [], [], 0
        for x1, y1, x2, y2, pct in segs:
            if lo <= pct < hi:
                xs += [x1, x2, None]
                ys += [y1, y2, None]
                n += 1
        if n:
            ax.plot(xs, ys, color=cor, lw=1.3 if hi <= 60 else 2.0, alpha=0.85,
                    label='%s (%s trechos)' % (rot, _mil(n)))
    ax.set_aspect('equal', adjustable='datalim')
    ax.legend(fontsize=_fs(6.5), loc='best', framealpha=0.85)
    ax.set_xticks([])
    ax.set_yticks([])
    acima = sum(1 for s in segs if s[4] > 100)
    ax.text(0.0, 1.01, '%s trechos desenhados  ·  %s acima da ampacidade'
            % (_mil(len(segs)), _mil(acima)), transform=ax.transAxes,
            fontsize=_fs(7.5), color=COR_RUIM if acima else COR_NEUTRA,
            va='bottom')
    return _acaba(ax, 'A rede no espaço, colorida por carregamento', None, None,
                  pad=26)
