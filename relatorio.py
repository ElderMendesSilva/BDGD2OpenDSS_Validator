# -*- coding: utf-8 -*-
"""RELATORIO VISUAL — dez figuras por subestacao, dez da concessao.

    python relatorio.py MODELOS_LT_V26                  a concessao inteira
    python relatorio.py MODELOS_LT_V26 --se AGV DBAR    so estas subestacoes
    python relatorio.py MODELOS_LT_V26 --so-geral       so o painel da base

Sai em `<pasta>/RELATORIO/`: um PNG por subestacao e um `_GERAL.png`.

POR QUE ISTO EXISTE. As figuras estavam espalhadas por cinco executaveis, uma
ou duas em cada, com estilos diferentes — `energia.py`, `validador.py`,
`verifica.py`, `valida_perdas.py` e `valida_balanco.py`. Ver uma subestacao
exigia rodar cinco programas e juntar os PNG a mao, e ninguem fazia isso.

NAO RESOLVE CIRCUITO NENHUM POR PADRAO. Le o que as etapas ja mediram —
`validacao.json`, `energia_dia.json`, `resumo.json` — e desenha. Roda em
segundos no laptop, sem cluster. Com `--abrir-modelo` ele compila a subestacao
para extrair perfil de tensao, carregamento e coordenadas, que sao as tres
figuras que exigem o modelo vivo; ai custa alguns segundos por subestacao.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss import graficos                            # noqa: E402



# ===========================================================================
#  O CATALOGO — que figuras existem, e com que nome se pedem
# ===========================================================================
#
# CADA FIGURA TEM UMA CHAVE CURTA, e e por ela que se escolhe o que plotar:
#
#     python relatorio.py MODELOS_LT_V26 --plots perfil tensao gd_fluxo
#     python relatorio.py MODELOS_LT_V26 --plots-lista
#
# Sem `--plots`, saem todas. A ordem do catalogo e a ordem na pagina, e ela
# nao e alfabetica de proposito: primeiro o estado da rede (tensao), depois a
# operacao ao longo do dia, depois a geracao distribuida, e por fim os
# numeros. E a ordem em que a pergunta costuma ser feita.

PLOTS_SE = [
    ('perfil',      'Perfil de tensao contra distancia da fonte'),
    ('tensao',      'Histograma de tensao nas barras de MT'),
    ('mapa',        'A rede no espaco, colorida por tensao'),
    ('dia',         'Curva do dia: fonte, GD e perdas'),
    ('perdas_dia',  'Perda em % ao longo do dia'),
    ('gd_fluxo',    'Geracao no dia, com o fluxo reverso destacado'),
    ('gd_cobre',    'Quanto da carga a GD cobre, passo a passo'),
    ('liquido',     'Carregamento liquido na cabeceira (o MINIMO importa)'),
    ('condutor',    'Carregamento dos condutores, em % da ampacidade'),
    ('composicao',  'Onde a perda acontece: linhas contra transformadores'),
    ('resumo',      'Painel de numeros da subestacao'),
    ('energia',     'Energia do dia e anomalias'),
]

PLOTS_GERAL = [
    ('veredictos',  'Quantas subestacoes passam, e por que as outras nao'),
    ('perdas_hist', 'Distribuicao da perda entre subestacoes'),
    ('perdas_rank', 'As piores perdas'),
    ('dia',         'Curva do dia somada na concessao'),
    ('gd_fluxo',    'Geracao no dia, agregada'),
    ('gd_cobre',    'Cobertura da carga pela GD, agregada'),
    ('tensao_hist', 'Tensao minima por subestacao'),
    ('km_rank',     'As maiores redes'),
    ('perda_km',    'Perda contra tamanho'),
    ('composicao',  'Linhas contra transformadores, na concessao'),
    ('resumo',      'A concessao em numeros'),
    ('energia',     'Energia do dia'),
]


def _escolhidos(pedidos, catalogo):
    """As chaves pedidas que EXISTEM neste catalogo, na ordem dele.

    Filtra em silencio o que nao e deste catalogo: `perfil` so existe na
    subestacao e `veredictos` so na concessao, e pedir os dois na mesma
    execucao e legitimo. Nome que nao existe em catalogo NENHUM e recusado no
    `main`, onde da para ver os dois de uma vez.
    """
    validas = [k for k, _ in catalogo]
    if not pedidos:
        return validas
    return [k for k in validas if k in set(pedidos)]


def _le(caminho):
    try:
        with open(caminho, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def _por_se(dados, chave='modelo'):
    """Lista ou dicionario, indexado pelo nome da subestacao."""
    if isinstance(dados, dict):
        return dados
    if isinstance(dados, list):
        return {str(x.get(chave) or x.get('se')): x for x in dados
                if isinstance(x, dict)}
    return {}


def _figura(linhas, colunas, titulo):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(linhas, colunas,
                             figsize=(colunas * 5.2, linhas * 3.4))
    fig.suptitle(titulo, fontsize=13, x=0.02, ha='left', weight='bold')
    return fig, [a for linha in axes for a in
                 (linha if hasattr(linha, '__len__') else [linha])]


# ---------------------------------------------------------------- subestacao

def _do_modelo(pasta, se):
    """Perfil de tensao, carregamento e coordenadas — exige compilar.

    Devolve (distancias, pus, carregamentos, xs, ys, cores). Tudo vazio quando
    o modelo nao abre: relatorio de subestacao quebrada tem de sair assim
    mesmo, com as figuras dizendo que nao ha dado.
    """
    vazio = ([], [], [], [], [], [])
    try:
        import opendssdirect as dss
    except Exception:
        return vazio
    # O OpenDSS FAZ `chdir` AO COMPILAR, para a pasta do arquivo. Todo caminho
    # relativo depois disso passa a resolver a partir da subestacao — foi
    # assim que o relatorio comecou a gravar no lugar errado, sem erro nenhum:
    # `os.path.isdir('MODELOS_X/SE1')` dava False porque o processo ja estava
    # DENTRO de `MODELOS_X/SE1`.
    voltar = os.getcwd()
    d = os.path.join(pasta, se)
    master = os.path.join(d, 'MASTER-%s.dss' % se)
    if not os.path.exists(master):
        return vazio
    try:
        dss.Text.Command('compile "%s"' % os.path.abspath(master))
        dss.Text.Command('solve')
    except Exception:
        os.chdir(voltar)
        return vazio

    dist, pus = [], []
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        if dss.Bus.kVBase() <= 1:
            continue
        v = [p for p in dss.Bus.puVmagAngle()[0::2] if 0.001 < p < 3]
        if not v:
            continue
        pus.append(min(v))
        dist.append(dss.Bus.Distance())

    carga = []
    i = dss.Lines.First()
    while i:
        try:
            nom = dss.Lines.NormAmps()
            dss.Circuit.SetActiveElement('Line.' + dss.Lines.Name())
            c = dss.CktElement.CurrentsMagAng()[0::2]
            if nom and c:
                carga.append(100.0 * max(c[:3]) / nom)
        except Exception:
            pass
        i = dss.Lines.Next()

    xs, ys, cor = [], [], []
    coords = os.path.join(d, 'BusCoords.dat')
    if os.path.exists(coords):
        pu_de = {}
        for b in dss.Circuit.AllBusNames():
            dss.Circuit.SetActiveBus(b)
            v = [p for p in dss.Bus.puVmagAngle()[0::2] if 0.001 < p < 3]
            if v:
                pu_de[b.lower()] = min(v)
        with open(coords, encoding='utf-8', errors='ignore') as fh:
            for L in fh:
                p = L.split(',')
                if len(p) >= 3:
                    try:
                        xs.append(float(p[1]))
                        ys.append(float(p[2]))
                        cor.append(pu_de.get(p[0].strip().lower()))
                    except ValueError:
                        pass
    os.chdir(voltar)
    return dist, pus, carga, xs, ys, cor


def uma_subestacao(pasta, se, val, ene, ger, destino, abrir=True,
                   plots=None, pdf=True):
    """As dez figuras de uma subestacao."""
    import matplotlib.pyplot as plt
    v = val.get(se) or {}
    e = ene.get(se) or {}
    g = ger.get(se) or {}
    serie = e.get('serie') or {}
    fonte = serie.get('fonte_kw') or []
    gd = serie.get('gd_kw') or []
    perdas = serie.get('perdas_kw') or []

    dist, pus, carga, xs, ys, cor = (_do_modelo(pasta, se) if abrir
                                     else ([], [], [], [], [], []))

    # CADA CHAVE DO CATALOGO VIRA UMA FUNCAO SEM ARGUMENTO, e so as pedidas
    # sao desenhadas. Assim acrescentar uma figura e escrever uma linha aqui e
    # outra no catalogo — e nao mexer no layout, que se ajusta ao numero.
    desenha = {
        'perfil': lambda a: graficos.perfil_de_tensao(a, dist, pus),
        'tensao': lambda a: graficos.histograma_de_tensao(a, pus),
        'mapa': lambda a: graficos.mapa(a, xs, ys, cor, 'Rede (cor = tensao)'),
        'dia': lambda a: graficos.curva_do_dia(a, fonte, gd, perdas),
        'perdas_dia': lambda a: graficos.perdas_do_dia(a, fonte, perdas),
        'gd_fluxo': lambda a: graficos.geracao_no_dia(a, fonte, gd),
        'gd_cobre': lambda a: graficos.cobertura_da_gd(a, fonte, gd),
        'liquido': lambda a: graficos.carregamento_liquido(a, fonte),
        'condutor': lambda a: graficos.carregamento(a, carga),
        'composicao': lambda a: graficos.composicao_da_perda(
            a, v.get('perdas_linhas_kW'), v.get('perdas_trafos_kW')),
        'resumo': lambda a: graficos.texto(a, _resumo_se(v, e, g), 'Resumo'),
        'energia': lambda a: graficos.texto(a, _energia_se(e, g),
                                            'Energia do dia e anomalias'),
    }
    chaves = _escolhidos(plots, PLOTS_SE)

    # UMA FIGURA POR ARQUIVO, numa pasta `RELATORIO/` dentro da subestacao.
    # O painelao de doze quadros servia para ter tudo de relance, mas nao serve
    # para USAR: quem quer o perfil de tensao numa apresentacao teria de
    # recortar da imagem grande, e cada quadro sai pequeno demais para ser lido
    # sozinho. Em arquivos separados cada figura tem a pagina inteira.
    # `destino` JA E a pasta de relatorio; so a pasta da subestacao ganha uma
    # subpasta. Sem esta distincao sai `RELATORIO/RELATORIO/`.
    dse = os.path.join(pasta, se)
    dest_se = os.path.join(dse, 'RELATORIO') if os.path.isdir(dse) else destino
    os.makedirs(dest_se, exist_ok=True)
    import matplotlib.pyplot as _plt
    for chave in chaves:
        f1, a1 = _plt.subplots(figsize=(9, 5.5))
        try:
            desenha[chave](a1)
        except Exception as erro:                            # noqa: BLE001
            graficos._vazio(a1, 'falhou: %s' % erro)
        f1.suptitle('%s — %s' % (se, dict(PLOTS_SE).get(chave, chave)),
                    fontsize=11, x=0.02, ha='left')
        f1.tight_layout(rect=[0, 0, 1, 0.95])
        f1.savefig(os.path.join(dest_se, '%s.png' % chave), dpi=120)
        _plt.close(f1)

    # O painelao continua saindo: e o que se olha primeiro, e o que entra no
    # PDF. As figuras soltas sao para usar.
    linhas = max(1, (len(chaves) + 2) // 3)
    fig, ax = _figura(linhas, 3, '%s — subestacao %s'
                      % (os.path.basename(pasta), se))
    for k, chave in enumerate(chaves):
        desenha[chave](ax[k])
    for sobra in ax[len(chaves):]:
        sobra.axis('off')

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    # A FIGURA MORA COM O MODELO. Quem abre a pasta de uma subestacao para
    # olhar o `.dss` acha o retrato dela do lado, sem precisar saber que existe
    # uma pasta de relatorio em outro lugar.
    base = os.path.join(dest_se, '_PAINEL')
    # OS DOIS FORMATOS, e nao um. O PNG abre com dois cliques e serve para
    # olhar; o PDF e vetorial, imprime sem borrar e e o que se manda por
    # e-mail ou anexa a um relatorio maior.
    alvo = base + '.png'
    fig.savefig(alvo, dpi=110)
    plt.close(fig)
    # O PDF E DOCUMENTO, e nao a figura salva noutro formato: texto, tabela e
    # as figuras dentro. E o que se anexa a um e-mail e o que alguem le sem
    # ter o projeto aberto do lado.
    if pdf:
        try:
            pdf_da_subestacao(base + '.pdf', pasta, se, v, e, g, alvo)
        except Exception as erro:                            # noqa: BLE001
            print('   PDF de %s falhou: %s' % (se, erro), flush=True)
    return alvo


def _resumo_geral(ses, cont, ger, kms, perdas, val, num):
    ok = cont.get('OK', 0)
    return [
        'subestacoes    %d' % len(ses),
        'com veredicto OK %d (%.1f%%)' % (ok, 100.0 * ok / len(ses) if ses else 0),
        'alimentadores  %d' % sum(int(num(ger, x, 'alimentadores') or 0)
                                  for x in ses),
        'trafos         %s' % _fmt(sum(int(num(ger, x, 'trafos') or 0)
                                       for x in ses)),
        'km de MT       %s' % _fmt(sum(v for v, _ in kms)),
        'cargas s/tensao %s' % _fmt(sum(int(num(val, x, 'cargas_sem_tensao') or 0)
                                        for x in ses)),
        'perda mediana  %.2f%%' % (sorted(v for v, _ in perdas)[len(perdas) // 2]
                                   if perdas else 0),
    ]


def _energia_geral(ses, ene, num):
    return [
        'kWh injetado   %s' % _fmt(sum(num(ene, x, 'kWh_injetado') or 0
                                       for x in ses)),
        'kWh perdas     %s' % _fmt(sum(num(ene, x, 'kWh_perdas') or 0
                                       for x in ses)),
        'kWh da GD      %s' % _fmt(sum(num(ene, x, 'kWh_gd') or 0 for x in ses)),
        '',
        'A SERIE DE 96 PASSOS e o que permite',
        'o modo daily, e o modo daily e o que',
        'torna a GD analisavel: fluxo reverso,',
        'nao-coincidencia com o pico e o',
        'carregamento MINIMO so aparecem nela.',
    ]


def _resumo_se(v, e, g):
    return [
        'veredicto      %s' % (v.get('veredicto') or '—'),
        'converge       %s em %s iteracoes' % (v.get('converge'),
                                               v.get('iteracoes')),
        'alimentadores  %s' % (g.get('alimentadores') or '—'),
        'trafos         %s' % (g.get('trafos') or '—'),
        'km de MT       %s' % (g.get('km_MT') or '—'),
        'linhas         %s' % (v.get('n_linhas') or '—'),
        'cargas         %s' % (v.get('n_cargas') or '—'),
        'sem tensao     %s' % (v.get('cargas_sem_tensao') or 0),
        'perda do dia   %s%%' % (e.get('perdas_pct') or '—'),
        'V_MT min/med   %s / %s' % (v.get('V_MT_min'), v.get('V_MT_mediana')),
    ]


def _energia_se(e, g):
    return [
        'kWh injetado   %s' % _fmt(e.get('kWh_injetado')),
        'kWh perdas     %s' % _fmt(e.get('kWh_perdas')),
        'kWh da GD      %s' % _fmt(e.get('kWh_gd')),
        'pico da GD     %s kW' % _fmt(e.get('pico_gd_kW')),
        'passos ok      %s de %s' % (e.get('passos_ok'), e.get('passos')),
        '',
        'reg. pendurado %s' % (g.get('reguladores_pendurados') or 0),
        'chave ilhada   %s' % (g.get('chaves_ilhadas') or 0),
        'PAC invertido  %s' % (g.get('trafos_pac_invertido') or 0),
    ]


def _fmt(x):
    if x is None:
        return '—'
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return str(x)


# ----------------------------------------------------------------- concessao

def a_concessao(pasta, val, ene, ger, ver, destino, plots=None):
    """As dez figuras da base inteira."""
    import collections
    import matplotlib.pyplot as plt

    ses = sorted(set(val) | set(ver) | set(ger))
    ses = [s for s in ses if str(s).strip().upper() not in ('AT', '_AT')]
    cont = collections.Counter(
        str((ver.get(s) or {}).get('veredicto') or '—').split('[')[0]
        for s in ses)

    def num(d, s, k):
        x = (d.get(s) or {}).get(k)
        try:
            f = float(x)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    perdas = [(num(ene, s, 'perdas_pct'), s) for s in ses]
    perdas = [(v, s) for v, s in perdas if v is not None]
    vmin = [(num(val, s, 'V_MT_min'), s) for s in ses]
    vmin = [(v, s) for v, s in vmin if v is not None]
    kms = [(num(ger, s, 'km_MT'), s) for s in ses]
    kms = [(v, s) for v, s in kms if v is not None]

    # a serie somada da concessao
    passos = 0
    for s in ses:
        sr = ((ene.get(s) or {}).get('serie') or {}).get('fonte_kw') or []
        passos = max(passos, len(sr))
    soma_f = [0.0] * passos
    soma_g = [0.0] * passos
    soma_p = [0.0] * passos
    for s in ses:
        sr = (ene.get(s) or {}).get('serie') or {}
        for alvo, chave in ((soma_f, 'fonte_kw'), (soma_g, 'gd_kw'),
                            (soma_p, 'perdas_kw')):
            v = sr.get(chave) or []
            for i in range(min(len(v), passos)):
                alvo[i] += v[i] or 0.0

    desenha = {
        'veredictos': lambda a: graficos.veredictos(a, cont),
        'perdas_hist': lambda a: graficos.histograma(
            a, [v for v, _ in perdas], 'Perda por subestacao',
            '% da injecao', corte=10.0),
        'perdas_rank': lambda a: graficos.ranking(
            a, [x for _, x in perdas], [v for v, _ in perdas],
            'Maiores perdas', '% da injecao', limite=10.0),
        'dia': lambda a: graficos.curva_do_dia(a, soma_f, soma_g, soma_p),
        'gd_fluxo': lambda a: graficos.geracao_no_dia(a, soma_f, soma_g),
        'gd_cobre': lambda a: graficos.cobertura_da_gd(a, soma_f, soma_g),
        'tensao_hist': lambda a: graficos.histograma(
            a, [v for v, _ in vmin], 'Tensao minima por subestacao', 'pu',
            corte=0.93),
        'km_rank': lambda a: graficos.ranking(
            a, [x for _, x in kms], [v for v, _ in kms], 'Maiores redes',
            'km de MT'),
        'perda_km': lambda a: graficos.dispersao(
            a, [num(ger, x, 'km_MT') or 0 for x in ses],
            [num(ene, x, 'perdas_pct') or 0 for x in ses],
            'Perda contra tamanho', 'km de MT', '% de perda'),
        'composicao': lambda a: graficos.composicao_da_perda(
            a, sum(num(val, x, 'perdas_linhas_kW') or 0 for x in ses),
            sum(num(val, x, 'perdas_trafos_kW') or 0 for x in ses)),
        'resumo': lambda a: graficos.texto(
            a, _resumo_geral(ses, cont, ger, kms, perdas, val, num),
            'Concessao em numeros'),
        'energia': lambda a: graficos.texto(
            a, _energia_geral(ses, ene, num), 'Energia do dia'),
    }
    chaves = _escolhidos(plots, PLOTS_GERAL)
    linhas = max(1, (len(chaves) + 2) // 3)
    fig, ax = _figura(linhas, 3, '%s — concessao (%d subestacoes)'
                      % (os.path.basename(pasta), len(ses)))
    for k, chave in enumerate(chaves):
        desenha[chave](ax[k])
    for sobra in ax[len(chaves):]:
        sobra.axis('off')

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    alvo = os.path.join(destino, '_GERAL.png')
    fig.savefig(alvo, dpi=110)
    fig.savefig(os.path.join(destino, '_GERAL.pdf'))
    plt.close(fig)
    return alvo


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pasta', help='pasta MODELOS_* da rodada')
    ap.add_argument('--se', nargs='*', default=None,
                    help='apenas estas subestacoes')
    ap.add_argument('--so-geral', action='store_true',
                    help='so o painel da concessao')
    ap.add_argument('--sem-modelo', action='store_true',
                    help='nao compila: pula perfil, carregamento e mapa')
    ap.add_argument('--plots', nargs='*', default=None, metavar='CHAVE',
                    help='quais figuras desenhar. Sem isto, TODAS — o caminho '
                         'normal e so passar a pasta. Ver --plots-lista')
    ap.add_argument('--plots-lista', action='store_true',
                    help='mostra as figuras disponiveis e sai')
    ap.add_argument('--sem-pdf', action='store_true',
                    help='so as figuras, sem o relatorio escrito')
    ap.add_argument('--saida', default=None)
    a = ap.parse_args(argv)

    if a.plots:
        # A RECUSA E CONTRA OS DOIS CATALOGOS JUNTOS. Chave desconhecida nao
        # pode passar em silencio: quem digitou `tensoes` receberia um painel
        # a menos e nenhum aviso.
        todas = {k for k, _ in PLOTS_SE} | {k for k, _ in PLOTS_GERAL}
        ruins = [x for x in a.plots if x not in todas]
        if ruins:
            print('plot desconhecido: %s' % ', '.join(ruins), file=sys.stderr)
            print('use --plots-lista para ver os nomes', file=sys.stderr)
            return 2

    if a.plots_lista:
        print('figuras da SUBESTACAO:')
        for k, d in PLOTS_SE:
            print('  %-13s %s' % (k, d))
        print('\nfiguras da CONCESSAO:')
        for k, d in PLOTS_GERAL:
            print('  %-13s %s' % (k, d))
        print('\nsem --plots, saem todas.')
        return 0

    if not os.path.isdir(a.pasta):
        print('pasta nao encontrada: %s' % a.pasta, file=sys.stderr)
        return 1
    destino = a.saida or os.path.join(a.pasta, 'RELATORIO')
    os.makedirs(destino, exist_ok=True)

    val = _por_se(_le(os.path.join(a.pasta, 'validacao.json')) or [])
    # CADA ARQUIVO USA UMA CHAVE: `validacao` diz `modelo`, `verificacao`
    # diz `se` e `resumo_geral` diz `SE`. Ler todos com a mesma chave deixava
    # o veredicto vazio no relatorio, sem erro nenhum.
    ver = _por_se(_le(os.path.join(a.pasta, 'verificacao.json')) or [], 'se')
    ene = _por_se(_le(os.path.join(a.pasta, 'energia_dia.json')) or [], 'se')
    ger = _por_se(_le(os.path.join(a.pasta, 'resumo_geral.json')) or [], 'SE')

    if not (val or ver or ene):
        print('nenhum resultado em %s — rode o ciclo antes' % a.pasta,
              file=sys.stderr)
        return 1

    feitos = []
    feitos.append(a_concessao(a.pasta, val, ene, ger, ver, destino,
                              a.plots))
    print('concessao -> %s' % feitos[-1], flush=True)

    if not a.so_geral:
        alvo = a.se or sorted(s for s in (set(val) | set(ver))
                              if str(s).strip().upper() not in ('AT', '_AT'))
        for k, se in enumerate(alvo, 1):
            try:
                p = uma_subestacao(a.pasta, se, val, ene, ger, destino,
                                   abrir=not a.sem_modelo,
                                   plots=a.plots, pdf=not a.sem_pdf)
                feitos.append(p)
                print('[%d/%d] %s' % (k, len(alvo), p), flush=True)
            except Exception as e:                          # noqa: BLE001
                print('[%d/%d] %s: FALHOU (%s)' % (k, len(alvo), se, e),
                      flush=True)

    print('\n%d figuras em %s' % (len(feitos), destino))
    # Gerar nada nao e gerar: relatorio vazio que sai 0 vira "sucesso".
    return 0 if len(feitos) > 1 or a.so_geral else 1


# ===========================================================================
#  O RELATORIO ESCRITO
# ===========================================================================
#
# O PDF NAO E A FIGURA SALVA EM PDF. E um documento com texto, tabela e as
# figuras dentro — o que se anexa a um e-mail ou a um relatorio maior, e o que
# alguem le sem ter o projeto aberto do lado.
#
# A ESTRUTURA E FIXA de proposito. Relatorio que muda de forma a cada rodada
# nao se compara com o anterior, e comparar duas rodadas e metade do trabalho
# deste projeto.

def _p(texto, estilo):
    from reportlab.platypus import Paragraph
    return Paragraph(texto, estilo)


def pdf_da_subestacao(caminho, pasta, se, v, e, g, figura):
    """Um documento por subestacao: o que e, o que deu, e a figura."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Spacer, Table,
                                    TableStyle, Image)

    est = getSampleStyleSheet()
    titulo = ParagraphStyle('t', parent=est['Title'], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle('s', parent=est['Normal'], fontSize=9,
                         textColor=colors.HexColor('#666'), spaceAfter=10)
    h2 = ParagraphStyle('h', parent=est['Heading2'], fontSize=11, spaceBefore=8)
    corpo = ParagraphStyle('c', parent=est['Normal'], fontSize=9, leading=13)

    doc = SimpleDocTemplate(caminho, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title='Subestacao %s' % se)
    ver = str(v.get('veredicto') or '—')
    pecas = [
        _p('Subestação %s' % se, titulo),
        _p('%s &nbsp;·&nbsp; gerado por BDGD → OpenDSS v%s'
           % (os.path.basename(pasta), _versao()), sub),
        _p('Veredicto', h2),
        _p(_frase_do_veredicto(ver, v), corpo),
        Spacer(1, 4 * mm),
        _p('A rede', h2),
    ]
    linhas = [
        ['alimentadores', g.get('alimentadores'), 'transformadores',
         g.get('trafos')],
        ['km de MT', g.get('km_MT'), 'trechos', v.get('n_linhas')],
        ['cargas', v.get('n_cargas'), 'cargas sem tensão',
         v.get('cargas_sem_tensao')],
        ['tensão mínima (pu)', v.get('V_MT_min'), 'tensão mediana (pu)',
         v.get('V_MT_mediana')],
        ['perda do dia (%)', e.get('perdas_pct'), 'perda nos trafos (%)',
         v.get('perdas_trafos_pct')],
        ['kWh injetado', _fmt(e.get('kWh_injetado')), 'kWh de perdas',
         _fmt(e.get('kWh_perdas'))],
        ['kWh da GD', _fmt(e.get('kWh_gd')), 'pico da GD (kW)',
         _fmt(e.get('pico_gd_kW'))],
    ]
    t = Table([[str(c) if c is not None else '—' for c in L] for L in linhas],
              colWidths=[42 * mm, 30 * mm, 42 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.HexColor('#ddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    pecas.append(t)

    anom = _anomalias(g, v)
    if anom:
        pecas += [_p('O que merece olhar', h2), _p(anom, corpo)]

    if figura and os.path.exists(figura):
        pecas += [Spacer(1, 6 * mm), _p('Figuras', h2),
                  Image(figura, width=170 * mm,
                        height=170 * mm * _proporcao(figura))]
    doc.build(pecas)
    return caminho


def _versao():
    try:
        from bdgd2dss import __version__
        return __version__
    except Exception:                                        # noqa: BLE001
        return '?'


def _proporcao(png):
    """Altura por largura da figura, para nao deformar no PDF."""
    try:
        from PIL import Image as _I
        with _I.open(png) as im:
            return im.height / float(im.width)
    except Exception:                                        # noqa: BLE001
        return 0.72


def _frase_do_veredicto(ver, v):
    """O veredicto em uma frase, e o que ele significa.

    Codigo cru num relatorio obriga o leitor a procurar o significado em outro
    lugar — e ninguem procura.
    """
    mapa = {
        'OK': 'A subestação compila, converge, não tem barra com NaN e as '
              'tensões ficam na faixa esperada.',
        'NAO_COMPILA': 'O modelo não compila no OpenDSS. Nada abaixo foi '
                       'medido nesta subestação.',
        'NAO_CONVERGE': 'O fluxo de potência não converge. Os números de '
                        'perda e tensão não devem ser usados.',
        'POTENCIA_NAN': 'A solução tem potência NaN — há barra sem referência '
                        'de tensão ou elemento com impedância nula.',
        'TENSAO_IMPLAUSIVEL': 'A tensão mediana da média tensão está muito '
                              'abaixo do esperado. Isso costuma ser rede '
                              'longa demais, condutor incoerente ou regulador '
                              'atuando contra um laço.',
    }
    base = mapa.get(ver.split('[')[0], 'Veredicto não reconhecido.')
    return '<b>%s</b> — %s' % (ver, base)


def _anomalias(g, v):
    """Só o que estiver diferente de zero. Lista de zeros não informa nada."""
    itens = []
    for chave, texto in (
            ('reguladores_pendurados', 'regulador com um PAC fora da rede'),
            ('chaves_ilhadas', 'chave que não toca a rede em ponta nenhuma'),
            ('trafos_pac_invertido', 'transformador com o PAC invertido')):
        n = g.get(chave) or 0
        if n:
            itens.append('%d %s' % (n, texto))
    n = v.get('cargas_sem_tensao') or 0
    if n:
        itens.append('%d carga(s) sem tensão' % n)
    return '; '.join(itens) + '.' if itens else ''



if __name__ == '__main__':
    sys.exit(main())
