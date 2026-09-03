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
from bdgd2dss import laudo                               # noqa: E402
from bdgd2dss import ficha                               # noqa: E402
from bdgd2dss import anomalias                           # noqa: E402
from bdgd2dss import veredicto                           # noqa: E402



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
    ('duracao',     'Curva de duracao da carga'),
    ('perda_carga', 'Perda contra carga: o ferro aparece no intercepto'),
    ('gd_fluxo',    'Geracao no dia, com o fluxo reverso destacado'),
    ('gd_cobre',    'Quanto da carga a GD cobre, passo a passo'),
    ('liquido',     'Carregamento liquido na cabeceira (o MINIMO importa)'),
    ('condutor',    'Carregamento dos condutores, em % da ampacidade'),
    ('mapa_carga',  'A rede no espaco, colorida por carregamento'),
    ('perdas_alim', 'Perda por alimentador, maiores primeiro'),
    ('tensao_alim', 'Faixa de tensao por alimentador'),
    ('duracao_v',   'Curva de duracao da tensao'),
    ('trechos',     'Comprimento dos trechos de MT'),
    ('reativo',     'Ativa, reativa e fator de potencia no dia'),
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

    Devolve (distancias, pus, carregamentos, xs, ys, cores, ficha). Tudo vazio
    quando o modelo nao abre: relatorio de subestacao quebrada tem de sair
    assim mesmo, com as figuras dizendo que nao ha dado.
    """
    vazio = ([], [], [], [], [], [], {}, [], {})
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
    # VOLTA AQUI, e nao no fim. Tudo abaixo usa a API do OpenDSS, que nao
    # depende do diretorio — menos a leitura do `BusCoords.dat`, que e um
    # arquivo comum. Restaurar so no fim fazia `os.path.exists(coords)` dar
    # False com o arquivo ali, e o mapa saia "sem coordenadas".
    os.chdir(voltar)

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
        with open(coords, encoding='utf-8', errors='ignore') as fh:  # noqa
            for L in fh:
                p = L.split(',')
                if len(p) >= 3:
                    try:
                        xs.append(float(p[1]))
                        ys.append(float(p[2]))
                        cor.append(pu_de.get(p[0].strip().lower()))
                    except ValueError:
                        pass

    # ------------------------------------------------------ o que e por trecho
    # Numa passagem so pelas linhas: comprimento, carregamento e os dois pontos
    # do segmento. Percorrer `dss.Lines` tres vezes custaria tres vezes, e numa
    # concessao de 450 subestacoes isso e tempo de maquina jogado fora.
    kms, segs = [], []
    xy = {}
    if os.path.exists(coords):
        with open(coords, encoding='utf-8', errors='ignore') as fh:
            for L in fh:
                q = L.split(',')
                if len(q) >= 3:
                    try:
                        xy[q[0].strip().lower()] = (float(q[1]), float(q[2]))
                    except ValueError:
                        pass
    fator_u = {0: 0.0, 1: 1.609344, 2: 0.0003048, 3: 1.0, 4: 0.001,
               5: 0.0000254, 6: 0.0000833, 7: 0.001}
    i = dss.Lines.First()
    while i:
        try:
            nome = dss.Lines.Name()
            u = dss.Lines.Units()
            kms.append((dss.Lines.Length() or 0.0)
                       * fator_u.get(int(u) if u is not None else 3, 0.0))
            b1 = dss.Lines.Bus1().split('.')[0].lower()
            b2 = dss.Lines.Bus2().split('.')[0].lower()
            nom = dss.Lines.NormAmps()
            dss.Circuit.SetActiveElement('Line.' + nome)
            c = dss.CktElement.CurrentsMagAng()[0::2]
            pct = (100.0 * max(c[:3]) / nom) if (nom and c) else None
            if b1 in xy and b2 in xy and pct is not None:
                segs.append((xy[b1][0], xy[b1][1], xy[b2][0], xy[b2][1], pct))
        except Exception:                                    # noqa: BLE001
            pass
        i = dss.Lines.Next()

    # ------------------------------------------------- a tensao por alimentador
    # A zona de cada EnergyMeter E o alimentador: e assim que o proprio modelo
    # define a fronteira, e nao por prefixo de nome — que ja mudou de forma
    # entre distribuidoras e nao serve de chave.
    pu_de = {}
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        if dss.Bus.kVBase() <= 1:
            continue
        vv = [p for p in dss.Bus.puVmagAngle()[0::2] if 0.001 < p < 3]
        if vv:
            pu_de[b.lower()] = min(vv)
    por_alim = {}
    try:
        j = dss.Meters.First()
        while j:
            nome = dss.Meters.Name()
            alim = nome[3:] if nome.lower().startswith('em_') else nome
            vs = []
            for br in (dss.Meters.AllBranchesInZone() or []):
                dss.Circuit.SetActiveElement(br)
                for bb in (dss.CktElement.BusNames() or []):
                    p = pu_de.get(bb.split('.')[0].lower())
                    if p is not None:
                        vs.append(p)
            if vs:
                por_alim[alim] = vs
            dss.Meters.Name(nome)
            j = dss.Meters.Next()
    except Exception:                                        # noqa: BLE001
        por_alim = {}

    # A FICHA. Sai do mesmo circuito ja resolvido — abrir o modelo de novo so
    # para conta-lo seria pagar a compilacao duas vezes, e numa concessao de
    # 450 subestacoes isso e meia hora de maquina por nada.
    try:
        ficha_ = ficha.ficha_do_circuito(dss)
    except Exception:                                        # noqa: BLE001
        ficha_ = {}
    # O DIAGNOSTICO, no mesmo circuito aberto. E aqui que "ha um ponto em
    # 1,551 pu" vira "o Transformer.1019552488 declara 22 kV nesta barra".
    anom = anomalias.do_modelo(dss)
    return (dist, pus, carga, xs, ys, cor, ficha_, anom,
            {'kms': kms, 'segs': segs, 'por_alim': por_alim})



def _fonte(tamanho):
    """Uma fonte com acentos, ou a embutida se nao houver jeito."""
    try:
        import matplotlib
        from PIL import ImageFont
        return ImageFont.truetype(
            os.path.join(matplotlib.get_data_path(), 'fonts', 'ttf',
                         'DejaVuSans.ttf'), tamanho)
    except Exception:                                        # noqa: BLE001
        try:
            from PIL import ImageFont
            return ImageFont.load_default()
        except Exception:                                    # noqa: BLE001
            return None


def _monta_painel(pngs, destino, titulo, colunas=3, largura=1100, margem=26):
    """O painelao, COLADO a partir das figuras ja salvas.

    Antes ele redesenhava as vinte figuras em eixos pequenos, e nao funcionava:
    cada figura foi desenhada para uma pagina inteira — titulo com 48 pontos de
    afastamento, faixa de numeros acima do eixo, caixas de anotacao
    dimensionadas em pontos e nao em fracao. Num eixo de um nono da area, nada
    disso encolhe junto: o titulo invade o grafico de cima, a legenda cobre a
    curva, e o que estava a direita e cortado. O painel saia ilegivel enquanto
    as figuras soltas estavam certas.

    Colar resolve na origem, porque o painel passa a ser exatamente o que as
    figuras sao, so que menor — e nunca mais pode divergir delas. Custa tambem
    menos: nao ha segunda renderizacao de vinte graficos.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:                                        # noqa: BLE001
        return None                       # sem Pillow nao ha painel, e tudo bem
    fotos = [p for p in pngs if os.path.exists(p)]
    if not fotos:
        return None

    cel = (largura - margem * (colunas + 1)) // colunas
    escaladas = []
    for p in fotos:
        try:
            im = Image.open(p).convert('RGB')
        except Exception:                                    # noqa: BLE001
            continue
        alt = max(1, int(im.height * cel / im.width))
        escaladas.append(im.resize((cel, alt), Image.LANCZOS))
    if not escaladas:
        return None

    # ALTURA POR FILEIRA, e nao uma altura unica: o mapa e quadrado e a curva
    # do dia e larga. Forcar todas ao mesmo tamanho distorceria umas e sobraria
    # branco nas outras.
    linhas = (len(escaladas) + colunas - 1) // colunas
    alturas = [max(im.height for im in escaladas[i * colunas:(i + 1) * colunas])
               for i in range(linhas)]
    topo = 52
    total = topo + sum(alturas) + margem * (linhas + 1)
    folha = Image.new('RGB', (largura, total), 'white')
    d = ImageDraw.Draw(folha)
    # A FONTE EMBUTIDA DO PILLOW E BITMAP E SO TEM ASCII: «subestação» saia
    # «subesta▯▯▯o» e o travessao virava um quadrado. A DejaVuSans vem com o
    # matplotlib, que ja e dependencia obrigatoria para desenhar as figuras —
    # entao usa-la nao acrescenta nada ao `requirements.txt`.
    d.text((margem, 16), titulo, fill=(38, 50, 56), font=_fonte(17))
    d.line([(margem, topo - 8), (largura - margem, topo - 8)],
           fill=(207, 216, 220), width=1)

    y = topo
    for i in range(linhas):
        x = margem
        for im in escaladas[i * colunas:(i + 1) * colunas]:
            folha.paste(im, (x, y))
            x += cel + margem
        y += alturas[i] + margem
    folha.save(destino)
    return destino

def _extra_do_modelo(pus, carga, fonte, gd):
    """O QUE SO O MODELO ABERTO SABE, e que o laudo e o veredicto precisam.

    Sao as tres medidas que respondem se a rede e boa: quantas barras fora da
    faixa, quantos condutores acima da ampacidade, e em quantos passos o fluxo
    se inverte. Ficava embutido no bloco do PDF, e por isso o veredicto
    impresso no terminal nao as via.
    """
    extra = {}
    if pus:
        fora = sum(1 for x in pus
                   if x < graficos.V_ADEQUADA[0] or x > graficos.V_ADEQUADA[1])
        extra['pct_fora_faixa'] = 100.0 * fora / len(pus)
    if carga:
        extra['pct_sobrecarga'] = (100.0 * sum(1 for x in carga if x > 100)
                                   / len(carga))
    if gd and any(gd):
        total = [(f or 0) + (x or 0) for f, x in zip(fonte, gd)]
        extra['passos_reversos'] = sum(1 for x, t in zip(gd, total) if x > t)
    return extra


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

    dist, pus, carga, xs, ys, cor, fic, anom, mais = (
        _do_modelo(pasta, se) if abrir
        else ([], [], [], [], [], [], {}, [], {}))
    fdia = ficha.ficha_do_dia(serie)
    anom = list(anom) + anomalias.do_dia(fdia)

    # CADA CHAVE DO CATALOGO VIRA UMA FUNCAO SEM ARGUMENTO, e so as pedidas
    # sao desenhadas. Assim acrescentar uma figura e escrever uma linha aqui e
    # outra no catalogo — e nao mexer no layout, que se ajusta ao numero.
    desenha = {
        'perfil': lambda a: graficos.perfil_de_tensao(a, dist, pus),
        'tensao': lambda a: graficos.histograma_de_tensao(a, pus),
        'mapa': lambda a: graficos.mapa(a, xs, ys, cor, 'Rede (cor = tensao)'),
        'dia': lambda a: graficos.curva_do_dia(a, fonte, gd, perdas),
        'perdas_dia': lambda a: graficos.perdas_do_dia(a, fonte, perdas),
        'duracao': lambda a: graficos.duracao_de_carga(a, fonte),
        'perda_carga': lambda a: graficos.perda_contra_carga(a, fonte, perdas),
        'gd_fluxo': lambda a: graficos.geracao_no_dia(a, fonte, gd),
        'gd_cobre': lambda a: graficos.cobertura_da_gd(a, fonte, gd),
        'liquido': lambda a: graficos.carregamento_liquido(a, fonte),
        'condutor': lambda a: graficos.carregamento(a, carga),
        'mapa_carga': lambda a: graficos.mapa_de_carregamento(
            a, (mais or {}).get('segs')),
        'perdas_alim': lambda a: graficos.perdas_por_alimentador(
            a, e.get('alimentadores')),
        'tensao_alim': lambda a: graficos.tensao_por_alimentador(
            a, (mais or {}).get('por_alim')),
        'duracao_v': lambda a: graficos.duracao_de_tensao(a, pus),
        'trechos': lambda a: graficos.comprimento_dos_trechos(
            a, (mais or {}).get('kms')),
        'reativo': lambda a: graficos.reativo_no_dia(
            a, fonte, serie.get('fonte_kvar')),
        'composicao': lambda a: graficos.composicao_da_perda(
            a, v.get('perdas_linhas_kW'), v.get('perdas_trafos_kW')),
        'resumo': lambda a: graficos.texto(
            a, _resumo_se(v, e, g, fic, fdia,
                          _extra_do_modelo(pus, carga, fonte, gd), anom),
            'Resumo'),
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
        # SEM `suptitle`: cada figura ja escreve o proprio titulo no eixo, e
        # o de cima repetia a mesma frase com outras palavras. O nome da
        # subestacao vai no rodape, que e onde nao disputa espaco com o dado.
        f1.text(0.01, 0.01, '%s · %s' % (se, chave), fontsize=7,
                color=graficos.COR_CLARA)
        f1.tight_layout(rect=[0, 0.02, 1, 1])
        # `bbox_inches='tight'` porque a faixa de numeros e o titulo ficam
        # ACIMA do eixo: com o enquadramento fixo o titulo saia cortado da
        # figura solta — no PDF ele nao faltava, porque ali o titulo e um
        # cabecalho de secao, e por isso o corte passou despercebido.
        f1.savefig(os.path.join(dest_se, '%s.png' % chave), dpi=120,
                   bbox_inches='tight')
        _plt.close(f1)

    # A FIGURA MORA COM O MODELO. Quem abre a pasta de uma subestacao para
    # olhar o `.dss` acha o retrato dela do lado, sem precisar saber que existe
    # uma pasta de relatorio em outro lugar.
    base = os.path.join(dest_se, '_PAINEL')
    alvo = base + '.png'
    _monta_painel([os.path.join(dest_se, '%s.png' % c) for c in chaves],
                  alvo, '%s — subestação %s' % (os.path.basename(pasta), se))
    # O VEREDICTO NO TERMINAL. Quem roda o ciclo inteiro ve o selo de cada
    # subestacao passando, e nao precisa abrir 450 PDFs para descobrir que
    # duas reprovaram.
    try:
        classe = veredicto.completo(v, e, g, fic, fdia,
                                    _extra_do_modelo(pus, carga, fonte, gd),
                                    anom)[0]
        print('      veredicto: %s' % classe, flush=True)
    except Exception:                                        # noqa: BLE001
        pass
    # O PDF E DOCUMENTO, e nao a figura salva noutro formato: texto, tabela e
    # as figuras dentro. E o que se anexa a um e-mail e o que alguem le sem
    # ter o projeto aberto do lado.
    if pdf:
        # O QUE SO O MODELO ABERTO SABE. Sem isto o laudo diria "nao medido"
        # em tres secoes — e elas sao justamente as que respondem se a rede e
        # boa: quantas barras fora da faixa, quantos condutores acima da
        # ampacidade, e em quantos passos o fluxo se inverte.
        extra = _extra_do_modelo(pus, carga, fonte, gd)
        extra['dia'] = fdia
        try:
            pdf_da_subestacao(base + '.pdf', pasta, se, v, e, g, alvo, extra,
                              fic, fdia, anom)
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


def _resumo_se(v, e, g, fic=None, fdia=None, extra=None, anom=None):
    # O VEREDICTO SAI DO MODULO QUE O CALCULA, e nao de um campo que ninguem
    # escreve: `v['veredicto']` nunca existiu — o `validador.py` grava
    # `compila`, `converge`, `resolve` e `causa` —, e por isso este painel
    # imprimia «veredicto —» em toda subestacao desde sempre.
    try:
        selo = veredicto.completo(v, e, g, fic or {}, fdia or {},
                                  extra or {}, anom)[0]
    except Exception:                                        # noqa: BLE001
        selo = '—'
    return [
        'veredicto      %s' % selo,
        'causa          %s' % (v.get('causa') or '—'),
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

def a_concessao(pasta, val, ene, ger, ver, destino, plots=None,
                pdf=True):
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
            a, [v for v, _ in perdas], 'Perda por subestação',
            '% da injeção', corte=10.0),
        'perdas_rank': lambda a: graficos.ranking(
            a, [x for _, x in perdas], [v for v, _ in perdas],
            'Maiores perdas', '% da injeção', limite=10.0),
        'dia': lambda a: graficos.curva_do_dia(a, soma_f, soma_g, soma_p),
        'gd_fluxo': lambda a: graficos.geracao_no_dia(a, soma_f, soma_g),
        'gd_cobre': lambda a: graficos.cobertura_da_gd(a, soma_f, soma_g),
        'tensao_hist': lambda a: graficos.histograma(
            a, [v for v, _ in vmin], 'Tensão mínima por subestação', 'pu',
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
            'A concessão em números'),
        'energia': lambda a: graficos.texto(
            a, _energia_geral(ses, ene, num), 'Energia do dia'),
    }
    chaves = _escolhidos(plots, PLOTS_GERAL)

    # A CONCESSAO GANHA O MESMO TRATAMENTO DA SUBESTACAO: uma figura por
    # arquivo, e nao so o painelao. Ate agora so a subestacao tinha sido
    # adaptada, e o `_GERAL` continuava sendo a versao antiga — quem quisesse
    # o ranking de perdas numa apresentacao teria de recortar da imagem grande.
    os.makedirs(destino, exist_ok=True)
    import matplotlib.pyplot as _plt
    for chave in chaves:
        f1, a1 = _plt.subplots(figsize=(9, 5.5))
        try:
            desenha[chave](a1)
        except Exception as erro:                            # noqa: BLE001
            graficos._vazio(a1, 'falhou: %s' % erro)
        f1.text(0.01, 0.01, 'concessao · %s' % chave, fontsize=7,
                color=graficos.COR_CLARA)
        f1.tight_layout(rect=[0, 0.02, 1, 1])
        f1.savefig(os.path.join(destino, '%s.png' % chave), dpi=120)
        _plt.close(f1)

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
    plt.close(fig)
    # E O PDF DA CONCESSAO tambem vira laudo, com a mesma estrutura do da
    # subestacao: o julgamento primeiro, e cada figura com a leitura dela.
    if pdf:
        agregado = {
            'ses': len(ses), 'ok': cont.get('OK', 0),
            'cargas_sem_tensao': sum(int(num(val, x, 'cargas_sem_tensao') or 0)
                                     for x in ses),
            'perda_mediana': (sorted(v for v, _ in perdas)[len(perdas) // 2]
                              if perdas else None),
            'perdas_linhas_kW': sum(num(val, x, 'perdas_linhas_kW') or 0
                                    for x in ses),
            'perdas_trafos_kW': sum(num(val, x, 'perdas_trafos_kW') or 0
                                    for x in ses),
        }
        try:
            pdf_da_concessao(os.path.join(destino, '_GERAL.pdf'), pasta,
                             agregado, destino, chaves)
        except Exception as erro:                            # noqa: BLE001
            print('   PDF da concessao falhou: %s' % erro, flush=True)
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
                              a.plots, pdf=not a.sem_pdf))
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


def pdf_da_subestacao(caminho, pasta, se, v, e, g, figura,
                      extra=None, fic=None, fdia=None, anom=None):
    """Um documento por subestacao: o que e, o que deu, e a figura."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Spacer, Table,
                                    TableStyle, Image, PageBreak)

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
    ]

    # A FICHA DO CIRCUITO ABRE O DOCUMENTO. Antes ele comecava pelo veredicto,
    # e o veredicto sozinho nao diz sobre O QUE ele foi dado: 3% de perda numa
    # rede de 40 barras e 3% numa de 40 mil sao resultados diferentes. Os
    # numeros aqui saem da interface do OpenDSS com o circuito ja resolvido —
    # e nao do `.dss` lido como texto —, entao contam o que o motor de fato
    # montou, e nao o que foi escrito.
    pecas += _bloco_do_veredicto(v, e, g, fic or {}, fdia or {}, extra, anom,
                                 'Veredicto', h2, corpo)
    pecas.append(PageBreak())

    if fic or fdia:
        pecas += _bloco_da_ficha(fic or {}, fdia or {}, h2, corpo)
        pecas.append(PageBreak())

    pecas.append(_p('A rede', h2))
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

    # O LAUDO ESCRITO, que e o que faz disto um relatorio e nao uma legenda de
    # figura. As regras estao em `bdgd2dss/laudo.py`, com as faixas de
    # referencia e a origem de cada uma.
    for tit, par in laudo.laudo_da_subestacao(v, e, g, extra):
        pecas += [_p(tit, h2), _p(_negrito(par), corpo)]

    # O DIAGNOSTICO EM PAGINA PROPRIA. O laudo diz que ha uma barra fora da
    # faixa; esta secao diz QUAL barra e qual elemento a colocou la. E a
    # diferenca entre um relatorio que se le e um que se usa.
    diag = _bloco_de_anomalias(anom, h2, corpo,
                               titulo='Diagnóstico das anomalias')
    if diag:
        pecas.append(PageBreak())
        pecas += diag

    # CADA FIGURA COM A SUA ANALISE, e nao um bloco de figuras no fim. O
    # painelao servia para ter tudo de relance; num relatorio, figura sem
    # leitura ao lado obriga quem le a redescobrir sozinho o que ela mostra —
    # e a maior parte das pessoas nao redescobre, so passa a pagina.
    pasta_fig = os.path.join(os.path.dirname(caminho))
    for chave, titulo_fig in PLOTS_SE:
        png = os.path.join(pasta_fig, '%s.png' % chave)
        if not os.path.exists(png):
            continue
        texto = laudo.analise_da_figura(chave, v, e, g, extra)
        achados_daqui = _bloco_de_anomalias(anom, h2, corpo, apenas=chave)
        if not texto and not achados_daqui:
            continue
        # UMA PAGINA POR SECAO. Duas secoes na mesma pagina fazem a figura
        # de baixo brigar por espaco com o texto de cima, e a leitura vira
        # rolagem. Com uma por pagina, cada figura tem a largura toda e o
        # paragrafo fica acima dela, onde e lido antes.
        pecas.append(PageBreak())
        pecas += [
            _p(titulo_fig, h2),
            _p(_negrito(texto), corpo),
            Spacer(1, 5 * mm),
            Image(png, width=168 * mm, height=168 * mm * _proporcao(png)),
        ]
        # O ACHADO FICA COM A FIGURA. Quem esta olhando o ponto solitario no
        # perfil tem a explicacao dele na mesma pagina, e nao vinte paginas
        # atras numa secao geral.
        pecas += achados_daqui
    doc.build(pecas)
    return caminho


def _bloco_do_veredicto(v, e, g, fic, fdia, extra, anom, titulo, h2, corpo):
    """A PRIMEIRA COISA DA PRIMEIRA PAGINA: o julgamento e por que.

    O relatorio abria pela ficha, e a ficha e evidencia. Quem recebe um
    documento quer a conclusao primeiro e a evidencia depois — e sobretudo quer
    saber PARA QUE aquele modelo serve, que e a pergunta que ninguem estava
    respondendo.
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import Spacer, Table, TableStyle

    classe, crits, frase, serve, nao = veredicto.completo(
        v, e, g, fic, fdia, extra, anom)
    cor = colors.HexColor(veredicto.COR.get(classe, '#546e7a'))

    selo = ParagraphStyle('selo', parent=corpo, fontSize=15, leading=19,
                          textColor=colors.white)
    peq = ParagraphStyle('peq', parent=corpo, fontSize=7.4, leading=10,
                         textColor=colors.HexColor('#666'))
    item = ParagraphStyle('it', parent=corpo, fontSize=8.6, leading=12,
                          leftIndent=4 * mm)

    faixa = Table([[_p('<b>%s</b>' % classe, selo)]], colWidths=[164 * mm])
    faixa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    pecas = [_p(titulo, h2), faixa, Spacer(1, 2.5 * mm),
             _p(_negrito(frase), corpo), Spacer(1, 3 * mm)]

    # A TABELA DE CRITERIOS. Valor medido e limite lado a lado: sem o limite
    # visivel, "2,9%" nao diz se passou, e o leitor tem de confiar no selo em
    # vez de conferir.
    simbolo = {veredicto.PASSA: ('passa', '#2e7d32'),
               veredicto.ATENCAO: ('atenção', '#f9a825'),
               veredicto.FALHA: ('REPROVA', '#c62828'),
               veredicto.SEM_DADO: ('sem dado', '#9e9e9e')}
    linhas = [[_p('<b>critério</b>', peq), _p('<b>medido</b>', peq),
               _p('<b>limite</b>', peq), _p('<b>resultado</b>', peq)]]
    estilo = [
        ('FONTSIZE', (0, 0), (-1, -1), 7.6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.HexColor('#e0e0e0')),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#9e9e9e')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for k, x in enumerate(crits, start=1):
        txt, c_res = simbolo.get(x['resultado'], simbolo[veredicto.SEM_DADO])
        linhas.append([
            _p(x['nome'] + (' <font size=6 color="#999">(eliminatório)</font>'
                            if x['eliminatorio'] else ''), peq),
            _p(str(x['valor']), peq), _p(str(x['limite']), peq),
            _p('<b><font color="%s">%s</font></b>' % (c_res, txt), peq)])
        if x['resultado'] in (veredicto.FALHA, veredicto.ATENCAO):
            estilo.append(('BACKGROUND', (0, k), (-1, k),
                           colors.HexColor('#fff8e1'
                                           if x['resultado'] == veredicto.ATENCAO
                                           else '#ffebee')))
    t = Table(linhas, colWidths=[52 * mm, 45 * mm, 42 * mm, 25 * mm])
    t.setStyle(TableStyle(estilo))
    pecas.append(t)

    # PARA QUE SERVE / PARA QUE NAO SERVE — a parte que nao existia.
    pecas += [Spacer(1, 4 * mm), _p('Este modelo serve para', h2)]
    for f in serve:
        pecas.append(_p('• ' + _negrito(f), item))
    pecas += [Spacer(1, 2 * mm), _p('Este modelo NÃO serve para', h2)]
    for f in nao:
        pecas.append(_p('• ' + _negrito(f), item))

    # O criterio que reprovou merece a razao dele por extenso.
    ruins = [x for x in crits if x['resultado'] == veredicto.FALHA]
    if ruins:
        pecas += [Spacer(1, 3 * mm), _p('Por que cada critério reprovou', h2)]
        for x in ruins:
            pecas.append(_p('<b>%s</b> — %s' % (x['nome'], x['porque']), corpo))
    return pecas


def _bloco_da_ficha(fic, fdia, h2, corpo):
    """A ficha do circuito: tres tabelas de duas colunas e a leitura delas.

    Tabela de duas colunas e nao de uma: a ficha tem quase cinquenta linhas, e
    empilhadas numa coluna so elas ocupariam tres paginas de papel quase
    branco. Em duas colunas cabe um bloco por terco de pagina, que e o formato
    em que alguem realmente confere numero.
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import Spacer, Table, TableStyle

    pequeno = ParagraphStyle('fic', parent=corpo, fontSize=8, leading=11)
    pecas = [_p('Ficha do circuito', h2),
             _p('Lido da interface do OpenDSS, com o circuito já resolvido.',
                pequeno)]

    blocos = {}
    ordem = []
    for bloco, rotulo, valor in ficha.linhas_da_ficha(fic, fdia):
        if bloco not in blocos:
            blocos[bloco] = []
            ordem.append(bloco)
        blocos[bloco].append((rotulo, valor))

    for bloco in ordem:
        itens = blocos[bloco]
        meio = (len(itens) + 1) // 2
        esq, dir_ = itens[:meio], itens[meio:]
        linhas = []
        for k in range(meio):
            a = esq[k] if k < len(esq) else ('', '')
            b = dir_[k] if k < len(dir_) else ('', '')
            linhas.append([a[0], a[1], b[0], b[1]])
        t = Table(linhas, colWidths=[46 * mm, 26 * mm, 46 * mm, 26 * mm])
        t.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7.6),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.HexColor('#e8e8e8')),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        pecas += [Spacer(1, 3 * mm), _p('<b>%s</b>' % bloco, pequeno),
                  Spacer(1, 1 * mm), t]

    for tit, par in laudo.leitura_da_ficha(fic, fdia):
        pecas += [_p(tit, h2), _p(_negrito(par), corpo)]
    return pecas


CORES_GRAVIDADE = {
    'grave': ('#c62828', 'requer atenção'),
    'atencao': ('#ef6c00', 'observar'),
    'nota': ('#546e7a', 'informativo'),
}


def _bloco_de_anomalias(anom, h2, corpo, apenas=None, titulo=None):
    """O diagnostico: o que foi medido, a causa provavel, e QUAIS elementos.

    A separacao entre "medido" e "causa provavel" e deliberada e visivel na
    pagina. Um relatorio que mistura as duas coisas ensina quem le a
    desconfiar das duas; separando, o numero continua valendo mesmo quando a
    explicacao estiver errada.
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import Spacer, Table, TableStyle

    itens = [a for a in (anom or [])
             if apenas is None or a.get('figura') == apenas]
    if not itens:
        return []

    rotulo = ParagraphStyle('rot', parent=corpo, fontSize=7.5, leading=10,
                            textColor=colors.HexColor('#777'))
    elem = ParagraphStyle('elem', parent=corpo, fontSize=7.6, leading=10.5,
                          leftIndent=4 * mm, textColor=colors.HexColor('#37474f'))
    pecas = []
    if titulo:
        pecas.append(_p(titulo, h2))
    for a in itens:
        cor, selo = CORES_GRAVIDADE.get(a['gravidade'], CORES_GRAVIDADE['nota'])
        cab = Table([[_p('<b>%s</b>' % a['titulo'], corpo),
                      _p('<font color="%s">%s</font>' % (cor, selo.upper()),
                         rotulo)]],
                    colWidths=[128 * mm, 36 * mm])
        cab.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.HexColor(cor)),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        pecas += [Spacer(1, 3 * mm), cab,
                  _p('O QUE FOI MEDIDO', rotulo),
                  _p(_negrito(a['medido']), corpo),
                  _p('EXPLICAÇÃO PROVÁVEL', rotulo),
                  _p(_negrito(a['causa']), corpo)]
        if a.get('elementos'):
            pecas.append(_p('ONDE OLHAR', rotulo))
            for x in a['elementos']:
                pecas.append(_p('• ' + _negrito(str(x)), elem))
    return pecas


def _negrito(txt):
    """`**assim**` vira `<b>assim</b>`.

    O laudo e escrito em texto simples para poder ser lido no terminal e no
    log; o reportlab so entende marcacao propria.
    """
    partes = txt.split('**')
    saida = []
    for k, pedaco in enumerate(partes):
        saida.append('<b>%s</b>' % pedaco if k % 2 else pedaco)
    return ''.join(saida)


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


def pdf_da_concessao(caminho, pasta, agregado, pasta_fig, chaves):
    """O laudo da concessão: o julgamento, os números e cada figura lida.

    Mesma estrutura do da subestação, de propósito. Relatório que muda de forma
    conforme o nível de agregação obriga quem lê a reaprender o documento a
    cada página.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Spacer, Table,
                                    TableStyle, Image, PageBreak)

    est = getSampleStyleSheet()
    titulo = ParagraphStyle('t', parent=est['Title'], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle('s', parent=est['Normal'], fontSize=9,
                         textColor=colors.HexColor('#666'), spaceAfter=10)
    h2 = ParagraphStyle('h', parent=est['Heading2'], fontSize=11, spaceBefore=8)
    corpo = ParagraphStyle('c', parent=est['Normal'], fontSize=9, leading=13)

    doc = SimpleDocTemplate(caminho, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title='Concessao %s' % os.path.basename(pasta))
    # O QUE ESTE RELATORIO COBRE, dito no cabecalho. Sem isto o titulo
    # «Concessao — MODELOS_X» nao diz se o numero e a soma das subestacoes de
    # distribuicao, o modelo da subtransmissao ou o MASTER-GERAL resolvido como
    # um circuito so — e sao tres coisas com valores diferentes. O `AT` e
    # excluido do agregado desde sempre (ver `ses` acima); o que faltava era
    # AVISAR.
    n_ses = agregado.get('ses') or 0
    pecas = [
        _p('Concessão — %s' % os.path.basename(pasta), titulo),
        _p('soma das <b>%d subestações de distribuição</b>, cada uma resolvida '
           'no seu próprio modelo &nbsp;·&nbsp; gerado por BDGD → OpenDSS v%s'
           % (n_ses, _versao()), sub),
        _p('O que este agregado NÃO é', h2),
        _p(_negrito(
            'Não é a subtransmissão: o modelo de alta tensão é o '
            '`MASTER-AT.dss` e tem relatório próprio, e a pseudo-subestação '
            '`AT` fica **fora** desta soma. E não é o `MASTER-GERAL.dss` '
            'resolvido como um circuito único — ali existem fluxos ENTRE '
            'subestações que uma soma de modelos independentes não pode '
            'representar, e os dois números não têm por que coincidir. O que '
            'está aqui é a soma de %d fluxos de potência independentes.'
            % n_ses), corpo),
    ]
    for tit, par in laudo.laudo_da_concessao(agregado):
        pecas += [_p(tit, h2), _p(_negrito(par), corpo)]

    # os números, na mesma tabela de duas colunas do relatório da subestação
    linhas = [
        ['subestações', agregado.get('ses'), 'com veredicto OK',
         agregado.get('ok')],
        ['cargas sem tensão', _fmt(agregado.get('cargas_sem_tensao')),
         'perda mediana (%)', _fmt2(agregado.get('perda_mediana'))],
        ['perda nas linhas (kW)', _fmt(agregado.get('perdas_linhas_kW')),
         'perda nos trafos (kW)', _fmt(agregado.get('perdas_trafos_kW'))],
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
    pecas += [Spacer(1, 4 * mm), t]

    nomes = dict(PLOTS_GERAL)
    for chave in chaves:
        png = os.path.join(pasta_fig, '%s.png' % chave)
        if not os.path.exists(png):
            continue
        texto = laudo.analise_da_concessao(chave, agregado)
        if not texto:
            continue
        pecas.append(PageBreak())
        pecas += [
            _p(nomes.get(chave, chave), h2),
            _p(_negrito(texto), corpo),
            Spacer(1, 5 * mm),
            Image(png, width=168 * mm, height=168 * mm * _proporcao(png)),
        ]
        # AQUI NAO HA ACHADO POR FIGURA. O diagnostico do `anomalias.py` e por
        # SUBESTACAO — ele nomeia o transformador, a barra, o trecho —, e nada
        # disso tem equivalente no agregado da concessao. A linha
        # `pecas += achados_daqui` chegou a existir neste laco por acidente:
        # uma substituicao de texto casou nos DOIS lacos, que eram identicos, e
        # a contagem nao foi travada. O PDF da concessao passou a morrer com
        # `name 'achados_daqui' is not defined` — e morria em SILENCIO, porque
        # a excecao e impressa e engolida. Quem pegou foi o teste de ponta a
        # ponta da camada de apresentacao.
    doc.build(pecas)
    return caminho


def _fmt2(x):
    try:
        return '%.2f' % float(x)
    except (TypeError, ValueError):
        return '—'


if __name__ == '__main__':
    sys.exit(main())
