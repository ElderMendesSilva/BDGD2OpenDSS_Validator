# -*- coding: utf-8 -*-
"""
RELATORIO DE CRITICIDADE DAS SUBESTACOES GERADAS

Consolida os resumo.json de cada subestacao produzida pelo conversor, cruza com
o estudo analitico por alimentador (criticidade_geral.json, quando disponivel) e
produz:

    RELATORIO_SUBESTACOES.pdf   relatorio completo com graficos
    ranking_subestacoes.csv     lista da mais critica a menos critica

Uso:
    python analise/relatorio_subestacoes.py [pasta_MODELOS] [--saida PASTA]
"""
import os, sys, json, glob, math, argparse, collections, csv, datetime

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, Image)

AZ = colors.HexColor('#1F3864'); VM = colors.HexColor('#C00000')
LA = colors.HexColor('#ED7D31'); VD = colors.HexColor('#2E7D32')
CZ = colors.HexColor('#F2F2F2')
HEX_AZ, HEX_VM, HEX_LA, HEX_VD = '#1F3864', '#C00000', '#ED7D31', '#2E7D32'


def br(v, d=1):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return '—'
    return f'{v:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


# ---------------------------------------------------------------- coleta
def coletar(pasta, criticidade_json=None):
    """Le os resumo.json e monta um registro por subestacao."""
    ses = []
    for f in sorted(glob.glob(os.path.join(pasta, '*', 'resumo.json'))):
        try:
            ses.append(json.load(open(f, encoding='utf-8')))
        except Exception:
            pass
    if not ses:
        raise SystemExit(f'Nenhum resumo.json encontrado em {pasta}')

    # estudo analitico por alimentador, se existir
    por_se = collections.defaultdict(list)
    if criticidade_json and os.path.exists(criticidade_json):
        for x in json.load(open(criticidade_json, encoding='utf-8')):
            if x.get('confiavel'):
                por_se[x.get('sub')].append(x)

    reg = []
    for s in ses:
        kw = s.get('kW_BT', 0) + s.get('kW_MT', 0)
        km = s.get('km_MT', 0) or 0.01
        alim = s.get('alimentadores', 0) or 1
        a = por_se.get(s['SE'], [])
        carr = [x['carreg_pct'] for x in a] if a else []
        reg.append({
            'SE': s['SE'],
            'alimentadores': s.get('alimentadores', 0),
            'com_fonte': s.get('com_cabeceira', 0),
            'kW': kw, 'MW': kw / 1000.0,
            'kW_BT': s.get('kW_BT', 0), 'kW_MT': s.get('kW_MT', 0),
            'km': km, 'barras': s.get('barras', 0),
            'linhas': s.get('linhas', 0), 'trafos': s.get('trafos', 0),
            'chaves': s.get('chaves', 0), 'chaves_abertas': s.get('chaves_abertas', 0),
            'capacitores': s.get('capacitores', 0), 'reguladores': s.get('reguladores', 0),
            'GD': s.get('GD', 0), 'cargas': s.get('n_cargas', 0),
            # --- indicadores derivados
            # densidade so faz sentido com rede minimamente extensa; abaixo de
            # 5 km o denominador e pequeno demais e o valor explode
            'densidade_kW_km': kw / km if km >= 5 else None,
            'km_suspeito': km < 5,
            'kW_por_alim': kw / alim,
            'kW_por_trafo': kw / max(s.get('trafos', 1), 1),
            'km_por_alim': km / alim,
            'pct_MT': 100 * s.get('kW_MT', 0) / kw if kw else 0,
            # --- do estudo analitico
            'carreg_max': max(carr) if carr else None,
            'carreg_med': sum(carr) / len(carr) if carr else None,
            'n_acima_100': sum(1 for c in carr if c > 100) if carr else 0,
            'n_acima_80': sum(1 for c in carr if 80 < c <= 100) if carr else 0,
            'tem_analise': bool(carr),
        })
    return reg


def indice_criticidade(reg):
    """Compoe o indice 0-100 e ordena do mais critico ao menos.

    Quatro dimensoes, todas normalizadas por percentil dentro do proprio
    conjunto — assim o indice mede posicao relativa na concessao, nao um
    valor absoluto que dependeria de premissas externas.
    """
    def pct_rank(vals):
        v = np.array([x if x is not None else 0 for x in vals], dtype=float)
        ordem = v.argsort().argsort()
        return 100.0 * ordem / max(len(v) - 1, 1)

    dens = pct_rank([r['densidade_kW_km'] or 0 for r in reg])
    carga = pct_rank([r['kW'] for r in reg])
    cmax = pct_rank([r['carreg_max'] or 0 for r in reg])
    sobre = pct_rank([r['n_acima_100'] for r in reg])

    for i, r in enumerate(reg):
        r['p_densidade'] = dens[i]
        r['p_carga'] = carga[i]
        r['p_carreg'] = cmax[i]
        r['p_sobrecarga'] = sobre[i]
        # pesos: sobrecarga e carregamento pesam mais que porte
        r['indice'] = round(0.35 * sobre[i] + 0.30 * cmax[i]
                            + 0.20 * dens[i] + 0.15 * carga[i], 1)
    reg.sort(key=lambda r: -r['indice'])
    for i, r in enumerate(reg, 1):
        r['posicao'] = i
    return reg


def classe(r):
    if r['indice'] >= 85: return 'critica'
    if r['indice'] >= 65: return 'alta'
    if r['indice'] >= 40: return 'moderada'
    if r['indice'] >= 20: return 'baixa'
    return 'folgada'


CORES = {'critica': HEX_VM, 'alta': HEX_LA, 'moderada': '#C9A227',
         'baixa': '#5B8C5A', 'folgada': HEX_VD}


# ---------------------------------------------------------------- graficos
def graficos(reg, dest):
    """Gera os PNG e devolve os caminhos."""
    plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#888888',
                         'axes.labelcolor': '#333333', 'text.color': '#333333',
                         'xtick.color': '#555555', 'ytick.color': '#555555'})
    saidas = {}
    dens = np.array([r['densidade_kW_km'] for r in reg if r['densidade_kW_km']])

    # 1) densidade de carga — histograma + curva de densidade (KDE gaussiana)
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
    d = dens[dens > 0]
    ax.hist(d, bins=40, color=HEX_AZ, alpha=0.35, edgecolor='white', linewidth=0.5,
            density=True, label='histograma')
    # KDE simples, sem scipy
    xs = np.linspace(0, np.percentile(d, 99.5), 400)
    h = 1.06 * d.std() * len(d) ** (-1 / 5)          # regra de Silverman
    if h > 0:
        k = np.exp(-0.5 * ((xs[:, None] - d[None, :]) / h) ** 2).sum(axis=1)
        k /= (len(d) * h * np.sqrt(2 * np.pi))
        ax.plot(xs, k, color=HEX_VM, linewidth=1.8, label='densidade estimada')
    ax.axvline(np.median(d), color=HEX_VD, linestyle='--', linewidth=1.2,
               label=f'mediana {np.median(d):.0f} kW/km')
    ax.set_xlabel('Densidade de carga (kW por km de rede de MT)')
    ax.set_ylabel('densidade de probabilidade')
    ax.set_title('Distribuição da densidade de carga entre as subestações', color=HEX_AZ)
    ax.legend(frameon=False, fontsize=7)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    p = os.path.join(dest, '_g1_densidade.png'); fig.savefig(p); plt.close(fig)
    saidas['densidade'] = p

    # 2) dispersão carga x extensão, tamanho = alimentadores, cor = classe
    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=200)
    for cl in ['folgada', 'baixa', 'moderada', 'alta', 'critica']:
        g = [r for r in reg if classe(r) == cl]
        if not g:
            continue
        ax.scatter([r['km'] for r in g], [r['MW'] for r in g],
                   s=[8 + 2.2 * r['alimentadores'] for r in g],
                   c=CORES[cl], alpha=0.72, edgecolors='white', linewidth=0.4, label=cl)
    for r in reg[:8]:
        ax.annotate(r['SE'], (r['km'], r['MW']), fontsize=6.5,
                    xytext=(4, 3), textcoords='offset points', color='#444444')
    # linhas de iso-densidade
    xm = max(r['km'] for r in reg)
    for dd, rot in [(100, '100'), (300, '300'), (600, '600 kW/km')]:
        ax.plot([0, xm], [0, dd * xm / 1000], color='#BBBBBB', linewidth=0.7,
                linestyle=':', zorder=0)
        ax.annotate(rot, (xm * 0.97, dd * xm / 1000 * 0.97), fontsize=6,
                    color='#999999', ha='right')
    ax.set_xlabel('Extensão da rede de MT (km)')
    ax.set_ylabel('Carga de ponta (MW)')
    ax.set_title('Carga × extensão — tamanho do ponto = nº de alimentadores', color=HEX_AZ)
    ax.legend(frameon=False, fontsize=7, title='criticidade', title_fontsize=7)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    p = os.path.join(dest, '_g2_dispersao.png'); fig.savefig(p); plt.close(fig)
    saidas['dispersao'] = p

    # 3) as 25 mais críticas — barras de densidade
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    top = reg[:25][::-1]
    y = np.arange(len(top))
    ax.barh(y, [r['densidade_kW_km'] or 0 for r in top],
            color=[CORES[classe(r)] for r in top], alpha=0.85,
            edgecolor='white', linewidth=0.5)
    ax.set_yticks(y); ax.set_yticklabels([r['SE'] for r in top], fontsize=6.5)
    ax.axvline(np.median(dens), color='#666666', linestyle='--', linewidth=1,
               label=f'mediana geral {np.median(dens):.0f} kW/km')
    for i, r in enumerate(top):
        ax.text((r['densidade_kW_km'] or 0) + max(dens) * 0.01, i,
                f"{r['densidade_kW_km'] or 0:.0f}", va='center', fontsize=6, color='#555555')
    ax.set_xlabel('Densidade de carga (kW/km)')
    ax.set_title('As 25 subestações mais críticas', color=HEX_AZ)
    ax.legend(frameon=False, fontsize=7)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    p = os.path.join(dest, '_g3_top.png'); fig.savefig(p); plt.close(fig)
    saidas['top'] = p

    # 4) composição do índice nas 20 primeiras
    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
    top = reg[:20]
    x = np.arange(len(top))
    comp = [('sobrecarga', 0.35, 'p_sobrecarga', HEX_VM),
            ('carregamento', 0.30, 'p_carreg', HEX_LA),
            ('densidade', 0.20, 'p_densidade', HEX_AZ),
            ('porte', 0.15, 'p_carga', '#7FA6C9')]
    base = np.zeros(len(top))
    for nome, peso, campo, cor in comp:
        v = np.array([r[campo] * peso for r in top])
        ax.bar(x, v, bottom=base, color=cor, label=nome, width=0.72,
               edgecolor='white', linewidth=0.4)
        base += v
    ax.set_xticks(x); ax.set_xticklabels([r['SE'] for r in top], rotation=90, fontsize=6)
    ax.set_ylabel('índice de criticidade')
    ax.set_title('Composição do índice nas 20 mais críticas', color=HEX_AZ)
    ax.legend(frameon=False, fontsize=7, ncol=4)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    p = os.path.join(dest, '_g4_composicao.png'); fig.savefig(p); plt.close(fig)
    saidas['composicao'] = p

    return saidas


# ---------------------------------------------------------------- pdf
def montar_pdf(reg, g, dest_pdf, pasta_modelos):
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle('H1', parent=ss['Heading1'], fontSize=13, textColor=AZ,
                        spaceBefore=9, spaceAfter=5)
    H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=10.5, textColor=AZ,
                        spaceBefore=7, spaceAfter=3)
    P = ParagraphStyle('P', parent=ss['Normal'], fontSize=8.7, leading=11.8,
                       alignment=TA_JUSTIFY, spaceAfter=4)
    PS = ParagraphStyle('PS', parent=P, fontSize=7.6, leading=9.8)
    TIT = ParagraphStyle('TIT', parent=ss['Title'], fontSize=17.5, textColor=AZ, spaceAfter=2)
    SUB = ParagraphStyle('SUB', parent=ss['Normal'], fontSize=10, alignment=TA_CENTER,
                         textColor=colors.HexColor('#555555'), spaceAfter=12)
    CEL = ParagraphStyle('CEL', parent=ss['Normal'], fontSize=6.3, leading=7.6)
    CELB = ParagraphStyle('CELB', parent=CEL, fontName='Helvetica-Bold')

    def c(t, b=False):
        return Paragraph(str(t), CELB if b else CEL)

    def tab(d, larg, cor=AZ):
        t = Table(d, colWidths=larg, repeatRows=1)
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#C4C4C4')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.4), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
            ('BACKGROUND', (0, 0), (-1, 0), cor), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CZ])]))
        return t

    def rod(cv, doc):
        cv.saveState()
        cv.setStrokeColor(AZ); cv.setLineWidth(0.6)
        cv.line(15 * mm, 283 * mm, 195 * mm, 283 * mm)
        cv.setFont('Helvetica-Bold', 7.2); cv.setFillColor(AZ)
        cv.drawString(15 * mm, 285 * mm, 'ENEL SP — Criticidade das Subestações')
        cv.setFont('Helvetica', 7.2); cv.setFillColor(colors.HexColor('#666666'))
        cv.drawRightString(195 * mm, 285 * mm, 'Modelos OpenDSS gerados da BDGD 2024-12-31')
        cv.line(15 * mm, 12 * mm, 195 * mm, 12 * mm)
        cv.drawString(15 * mm, 8 * mm, datetime.date.today().strftime('%d/%m/%Y'))
        cv.drawRightString(195 * mm, 8 * mm, f'Página {doc.page}')
        cv.restoreState()

    dens = np.array([r['densidade_kW_km'] for r in reg if r['densidade_kW_km']])
    tot_mw = sum(r['MW'] for r in reg)
    tot_km = sum(r['km'] for r in reg)
    tot_al = sum(r['alimentadores'] for r in reg)
    com_an = [r for r in reg if r['tem_analise']]
    n100 = sum(r['n_acima_100'] for r in reg)

    S = []
    S.append(Spacer(1, 8))
    S.append(Paragraph('Criticidade das subestações', TIT))
    S.append(Paragraph(f'{len(reg)} subestações · {br(tot_al,0)} alimentadores · '
                       f'{br(tot_mw,0)} MW · {br(tot_km,0)} km de rede de MT', SUB))

    # ---------------------------------------------------- 1
    S.append(Paragraph('1. Resumo', H1))
    S.append(Paragraph(
        f'Este relatório consolida as <b>{len(reg)} subestações</b> efetivamente geradas pelo conversor, '
        f'somando <b>{br(tot_mw, 0)} MW</b> de demanda de ponta distribuídos em <b>{br(tot_al,0)}</b> '
        f'alimentadores e <b>{br(tot_km, 0)} km</b> de rede de média tensão. '
        f'A densidade de carga mediana é de <b>{br(np.median(dens), 0)} kW/km</b>, com o quartil superior '
        f'acima de {br(np.percentile(dens, 75), 0)} kW/km e casos extremos passando de '
        f'{br(np.percentile(dens, 99), 0)} kW/km.', P))
    S.append(Paragraph(
        'A densidade de carga é o indicador que melhor separa subestações urbanas densas de rurais '
        'extensas: duas subestações com a mesma carga total exigem intervenções muito diferentes se uma '
        'concentra tudo em 20 km e a outra espalha por 400 km. Por isso ela entra no índice de '
        'criticidade com peso próprio, ao lado do carregamento dos alimentadores.', P))

    d = [[c('Indicador', True), c('Total', True), c('Mediana', True),
          c('Percentil 75', True), c('Máximo', True)]]
    for rot, campo, dec in [('Carga de ponta (MW)', 'MW', 1),
                            ('Extensão de MT (km)', 'km', 1),
                            ('Densidade (kW/km)', 'densidade_kW_km', 0),
                            ('Alimentadores', 'alimentadores', 0),
                            ('Transformadores', 'trafos', 0),
                            ('Carga por alimentador (kW)', 'kW_por_alim', 0)]:
        v = np.array([r[campo] for r in reg if r[campo] is not None], dtype=float)
        if not len(v):
            continue
        soma = v.sum() if campo in ('MW', 'km', 'alimentadores', 'trafos') else None
        d.append([c(rot, True), c(br(soma, dec) if soma is not None else '—'),
                  c(br(np.median(v), dec)), c(br(np.percentile(v, 75), dec)),
                  c(br(v.max(), dec))])
    t = tab(d, [46 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([('ALIGN', (1, 1), (-1, -1), 'RIGHT')]))
    S.append(t)

    # ---------------------------------------------------- 2 grafico densidade
    S.append(Paragraph('2. Densidade de carga', H1))
    S.append(Image(g['densidade'], width=176 * mm, height=83 * mm))
    S.append(Paragraph(
        'A distribuição é fortemente assimétrica à direita: a maioria das subestações se concentra numa '
        'faixa estreita de baixa densidade, e uma cauda longa reúne os casos urbanos densos. '
        'Essa assimetria é o motivo de o índice usar posição percentílica e não valor absoluto — '
        'a média seria puxada pelos extremos e não representaria o conjunto.', PS))

    faixas = [('até 100 kW/km', lambda x: x <= 100, 'rural / periurbana'),
              ('100 – 250', lambda x: 100 < x <= 250, 'suburbana'),
              ('250 – 500', lambda x: 250 < x <= 500, 'urbana'),
              ('500 – 1.000', lambda x: 500 < x <= 1000, 'urbana densa'),
              ('acima de 1.000', lambda x: x > 1000, 'núcleo denso')]
    d = [[c('Faixa de densidade', True), c('Subestações', True), c('%', True),
          c('MW somados', True), c('Perfil típico', True)]]
    for rot, f, perfil in faixas:
        q = [r for r in reg if r['densidade_kW_km'] and f(r['densidade_kW_km'])]
        d.append([c(rot, True), c(br(len(q), 0)), c(br(100 * len(q) / len(reg), 1) + '%'),
                  c(br(sum(x['MW'] for x in q), 0)), c(perfil)])
    t = tab(d, [32 * mm, 26 * mm, 20 * mm, 28 * mm, 40 * mm])
    t.setStyle(TableStyle([('ALIGN', (1, 1), (3, -1), 'RIGHT')]))
    S.append(t)

    S.append(PageBreak())
    # ---------------------------------------------------- 3 dispersao
    S.append(Paragraph('3. Carga contra extensão', H1))
    S.append(Image(g['dispersao'], width=176 * mm, height=98 * mm))
    S.append(Paragraph(
        'Cada ponto é uma subestação; o tamanho indica quantos alimentadores ela tem e a cor, a classe de '
        'criticidade. As linhas pontilhadas são iso-densidades. Subestações acima da linha de 600 kW/km '
        'concentram muita carga em pouca rede — são as que respondem pior a crescimento de demanda, porque '
        'não há folga geográfica para redistribuir. As que ficam à direita e embaixo têm rede extensa e '
        'carga diluída: o problema delas tende a ser queda de tensão, não ampacidade.', PS))

    # ---------------------------------------------------- 4 top
    S.append(Paragraph('4. As mais críticas', H1))
    S.append(Image(g['top'], width=176 * mm, height=113 * mm))

    S.append(PageBreak())
    S.append(Paragraph('5. Como o índice é composto', H1))
    S.append(Image(g['composicao'], width=176 * mm, height=88 * mm))
    d = [[c('Dimensão', True), c('Peso', True), c('O que mede', True)]]
    for a_, b_, e_ in [
        ('Sobrecarga', '35%', 'quantos alimentadores da subestação passam de 100% da capacidade nominal'),
        ('Carregamento', '30%', 'o carregamento do alimentador mais carregado da subestação'),
        ('Densidade', '20%', 'kW de ponta por km de rede de MT — concentração de carga'),
        ('Porte', '15%', 'carga total, que dimensiona o impacto de uma contingência'),
    ]:
        d.append([c(a_, True), c(b_), c(e_)])
    t = tab(d, [30 * mm, 16 * mm, 130 * mm])
    t.setStyle(TableStyle([('ALIGN', (1, 1), (1, -1), 'CENTER')]))
    S.append(t)
    S.append(Paragraph(
        'Cada dimensão é convertida em posição percentílica dentro do próprio conjunto de subestações. '
        'O índice resultante vai de 0 a 100 e mede <b>posição relativa na concessão</b>, não um valor '
        'absoluto — o que evita depender de premissas externas como a referência de capacidade nominal, '
        'que ainda está em aberto.', PS))

    # ---------------------------------------------------- 6 lista completa
    S.append(PageBreak())
    S.append(Paragraph('6. Lista completa — da mais crítica à menos crítica', H1))
    S.append(Paragraph(
        f'As {len(reg)} subestações ordenadas pelo índice. "Alim. > 100%" é a contagem de alimentadores '
        'acima da capacidade nominal segundo o estudo analítico sobre a BDGD; onde aparece travessão, a '
        'subestação não tinha dado suficiente para o cálculo por alimentador.', P))
    cab = ['#', 'SE', 'Índice', 'Classe', 'MW', 'km', 'Densid.\nkW/km', 'Alim.',
           'Alim.\n>100%', 'Carreg.\nmáx', 'Trafos', 'Barras', 'GD', 'MT %']
    larg = [7, 15, 13, 17, 14, 15, 17, 11, 13, 16, 14, 16, 10, 12]
    d = [[c(x, True) for x in cab]]
    for r in reg:
        cl = classe(r)
        d.append([c(str(r['posicao'])), c(r['SE'], True), c(br(r['indice']), True), c(cl),
                  c(br(r['MW'], 1)), c(br(r['km'], 0)), c(br(r['densidade_kW_km'], 0)),
                  c(str(r['alimentadores'])),
                  c(str(r['n_acima_100']) if r['tem_analise'] else '—'),
                  c(br(r['carreg_max'], 0) + '%' if r['carreg_max'] else '—'),
                  c(br(r['trafos'], 0)), c(br(r['barras'], 0)), c(str(r['GD'])),
                  c(br(r['pct_MT'], 0))])
    t = tab(d, [x * mm for x in larg])
    sty = [('ALIGN', (2, 1), (-1, -1), 'RIGHT'), ('ALIGN', (3, 1), (3, -1), 'LEFT')]
    for i, r in enumerate(reg, 1):
        cl = classe(r)
        if cl == 'critica':
            sty.append(('TEXTCOLOR', (0, i), (-1, i), VM))
        elif cl == 'alta':
            sty.append(('TEXTCOLOR', (0, i), (-1, i), LA))
        elif cl == 'folgada':
            sty.append(('TEXTCOLOR', (0, i), (-1, i), VD))
    t.setStyle(TableStyle(sty))
    S.append(t)

    # ---------------------------------------------------- 7 ressalvas
    S.append(PageBreak())
    S.append(Paragraph('7. Leitura e ressalvas', H1))
    d = [[c('Ponto', True), c('Detalhe', True)]]
    sem_an = [r for r in reg if not r['tem_analise']]
    for a_, b_ in [
        ('Origem dos dados',
         f'Os totais de carga, extensão, transformadores e barras vêm dos modelos OpenDSS gerados '
         f'(arquivo resumo.json de cada subestação). O carregamento por alimentador vem do estudo '
         f'analítico sobre a BDGD. {len(com_an)} das {len(reg)} subestações têm os dois; '
         f'{len(sem_an)} têm apenas os dados do modelo.'),
        ('Ainda não é simulação',
         'O carregamento aqui é analítico — demanda de ponta sobre ampacidade do tronco. Não inclui '
         'perdas nem queda de tensão. Na comparação feita no CAM-301, o método analítico subestimou em '
         'cerca de 12% frente ao fluxo de potência. Rodar o OpenDSS nos modelos gerados é o passo que '
         'fecha esse ponto.'),
        ('Referência de capacidade',
         'Adotou-se a capacidade nominal (CNOM) do condutor. Se a referência operativa da distribuidora '
         'for outra — corrente do disjuntor de saída, por exemplo — todos os percentuais mudam na mesma '
         'proporção, mas a ordem do ranking se mantém.'),
        ('Mês e tipo de dia',
         'Os modelos foram gerados para o mês e o tipo de dia escolhidos na conversão. Trocar de mês '
         'muda a carga e pode reordenar as subestações de perfil sazonal.'),
        ('Sequência zero',
         'Os LineCodes usam R0 e X0 derivados de R1/X1 por razões típicas, porque a BDGD não traz '
         'sequência zero. Isso não afeta o carregamento, mas invalida qualquer análise de desequilíbrio.'),
    ]:
        d.append([c(a_, True), c(b_)])
    S.append(tab(d, [38 * mm, 138 * mm]))

    S.append(Paragraph('8. Próximos passos sugeridos', H1))
    for i, t_ in enumerate([
        'Rodar <i>validador.py</i> sobre a pasta inteira e separar as subestações que não convergem antes '
        'de qualquer conclusão operativa.',
        'Simular no OpenDSS as 20 primeiras deste ranking, em regime diário de 96 passos, para obter '
        'carregamento com perdas e queda de tensão.',
        'Cruzar as subestações de alta densidade com as chaves normalmente abertas — são as candidatas '
        'naturais a remanejamento de carga entre alimentadores vizinhos.',
        'Para o NSGA-II, usar as subestações das classes crítica e alta como casos com restrição de '
        'ampacidade ativa; as folgadas servem como destino de transferência.',
    ]):
        S.append(Paragraph(f'{i + 1}. {t_}',
                           ParagraphStyle('L', parent=P, leftIndent=10, spaceAfter=4)))

    doc = SimpleDocTemplate(dest_pdf, pagesize=A4, leftMargin=13 * mm, rightMargin=13 * mm,
                            topMargin=20 * mm, bottomMargin=17 * mm,
                            title='Criticidade das subestações — Enel SP')
    doc.build(S, onFirstPage=rod, onLaterPages=rod)


def salvar_csv(reg, caminho):
    with open(caminho, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['Posicao', 'Subestacao', 'Indice_criticidade', 'Classe',
                    'MW_ponta', 'km_MT', 'Densidade_kW_km', 'Alimentadores',
                    'Alim_acima_100pct', 'Alim_80_100pct', 'Carreg_max_pct',
                    'Carreg_medio_pct', 'kW_BT', 'kW_MT', 'pct_MT',
                    'kW_por_alimentador', 'km_por_alimentador', 'Transformadores',
                    'Barras', 'Linhas', 'Chaves', 'Chaves_abertas', 'Capacitores',
                    'Reguladores', 'GD', 'Cargas',
                    'p_sobrecarga', 'p_carregamento', 'p_densidade', 'p_porte'])
        v = lambda z, d=1: ('' if z is None else f'{z:.{d}f}'.replace('.', ','))
        for r in reg:
            w.writerow([r['posicao'], r['SE'], v(r['indice']), classe(r),
                        v(r['MW']), v(r['km']), v(r['densidade_kW_km'], 0),
                        r['alimentadores'],
                        r['n_acima_100'] if r['tem_analise'] else '',
                        r['n_acima_80'] if r['tem_analise'] else '',
                        v(r['carreg_max']), v(r['carreg_med']),
                        v(r['kW_BT'], 0), v(r['kW_MT'], 0), v(r['pct_MT']),
                        v(r['kW_por_alim'], 0), v(r['km_por_alim'], 2),
                        r['trafos'], r['barras'], r['linhas'], r['chaves'],
                        r['chaves_abertas'], r['capacitores'], r['reguladores'],
                        r['GD'], r['cargas'],
                        v(r['p_sobrecarga']), v(r['p_carreg']),
                        v(r['p_densidade']), v(r['p_carga'])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('modelos', nargs='?', default='MODELOS/Modelos')
    ap.add_argument('--saida', default='.')
    ap.add_argument('--criticidade', default='dados/resultados/criticidade_geral.json')
    a = ap.parse_args()

    reg = coletar(a.modelos, a.criticidade)
    reg = indice_criticidade(reg)
    os.makedirs(a.saida, exist_ok=True)
    g = graficos(reg, a.saida)
    pdf = os.path.join(a.saida, 'RELATORIO_SUBESTACOES.pdf')
    montar_pdf(reg, g, pdf, a.modelos)
    csvp = os.path.join(a.saida, 'ranking_subestacoes.csv')
    salvar_csv(reg, csvp)
    for p in g.values():
        pass  # os PNG ficam como anexos reutilizaveis
    print(f'{len(reg)} subestacoes')
    print('PDF:', pdf)
    print('CSV:', csvp)
    print(f'mais critica: {reg[0]["SE"]} (indice {reg[0]["indice"]}, '
          f'{reg[0]["densidade_kW_km"]:.0f} kW/km)')
    print(f'menos critica: {reg[-1]["SE"]} (indice {reg[-1]["indice"]})')


if __name__ == '__main__':
    main()
