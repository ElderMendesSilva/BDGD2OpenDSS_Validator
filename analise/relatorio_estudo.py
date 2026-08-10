# -*- coding: utf-8 -*-
"""
RELATORIO EM PDF DO ESTUDO DE CRITICIDADE
=========================================

    python analise/relatorio_estudo.py               abre o painel e pergunta
    python analise/relatorio_estudo.py --dados dados\\resultados --saida dados\\resultados

Le o `criticidade_geral.json` que o criticidade.py produz e monta o
ESTUDO_CRITICIDADE_ENEL_SP.pdf: resumo executivo, metodologia, as cinco
subestacoes da hipotese inicial, ranking de subestacoes, os 60 alimentadores
mais carregados, os 25 mais instaveis pelo indice composto, ressalvas e
recomendacoes.
"""
import argparse, json, os, math, collections, datetime, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                 # a raiz do projeto, onde esta o interativo.py
sys.path.insert(0, RAIZ)

RESULTADOS = os.path.join(RAIZ, 'dados', 'resultados')
PDF = 'ESTUDO_CRITICIDADE_ENEL_SP.pdf'


def _painel():
    import interativo
    v = interativo.formulario('relatorio_estudo', 'Relatório do estudo de criticidade', [
        {'chave': 'dados', 'tipo': 'pasta', 'rotulo': 'Resultados do estudo',
         'padrao': RESULTADOS,
         'dica': 'a pasta com o criticidade_geral.json — rode antes o criticidade.py'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Pasta de saída',
         'padrao': RESULTADOS, 'dica': f'recebe o {PDF}'},
    ], ajuda='Monta o relatório em PDF a partir do estudo já calculado. '
             'Não recalcula nada: se os números mudaram, rode antes o '
             'criticidade.py.')
    if not v:
        raise SystemExit(0)
    sys.argv += ['--dados', v['dados'], '--saida', v['saida']]


if len(sys.argv) == 1:
    _painel()
_ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
_ap.add_argument('--dados', default=RESULTADOS,
                 help='pasta com o criticidade_geral.json')
_ap.add_argument('--saida', default=RESULTADOS, help='pasta que recebe o PDF')
_a = _ap.parse_args()

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

O = _a.dados
os.makedirs(_a.saida, exist_ok=True)
DEST = os.path.join(_a.saida, PDF)
if not os.path.exists(f'{O}/criticidade_geral.json'):
    raise SystemExit(f'falta {O}/criticidade_geral.json\n'
                     f'  gere com: python analise/criticidade.py')
R = json.load(open(f'{O}/criticidade_geral.json', encoding='utf-8'))
OK = [x for x in R if x['confiavel']]
SUS = [x for x in R if not x['confiavel']]
POS = {x['ctmt']: i + 1 for i, x in enumerate(OK)}

AZ = colors.HexColor('#1F3864'); VM = colors.HexColor('#C00000')
LA = colors.HexColor('#ED7D31'); VD = colors.HexColor('#2E7D32'); CZ = colors.HexColor('#F2F2F2')
ss = getSampleStyleSheet()
H1 = ParagraphStyle('H1', parent=ss['Heading1'], fontSize=13.5, textColor=AZ, spaceBefore=9, spaceAfter=5)
H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=10.5, textColor=AZ, spaceBefore=7, spaceAfter=3)
P = ParagraphStyle('P', parent=ss['Normal'], fontSize=8.8, leading=12, alignment=TA_JUSTIFY, spaceAfter=4)
PS = ParagraphStyle('PS', parent=P, fontSize=7.8, leading=10)
TIT = ParagraphStyle('TIT', parent=ss['Title'], fontSize=18, textColor=AZ, spaceAfter=2)
SUB = ParagraphStyle('SUB', parent=ss['Normal'], fontSize=10.5, alignment=TA_CENTER,
                     textColor=colors.HexColor('#555555'), spaceAfter=12)
CEL = ParagraphStyle('CEL', parent=ss['Normal'], fontSize=6.8, leading=8.3)
CELB = ParagraphStyle('CELB', parent=CEL, fontName='Helvetica-Bold')


def br(v, d=1):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return '—'
    return f'{v:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def c(t, b=False):
    return Paragraph(str(t), CELB if b else CEL)


def tab(d, larg, cor=AZ):
    t = Table(d, colWidths=larg, repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#BFBFBF')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5), ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
        ('BACKGROUND', (0, 0), (-1, 0), cor), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CZ])]))
    return t


def rod(cv, doc):
    cv.saveState()
    cv.setStrokeColor(AZ); cv.setLineWidth(0.6)
    cv.line(18 * mm, 275 * mm, 192 * mm, 275 * mm)
    cv.setFont('Helvetica-Bold', 7.5); cv.setFillColor(AZ)
    cv.drawString(18 * mm, 277 * mm, 'ENEL SP — Estudo de Criticidade de Alimentadores')
    cv.setFont('Helvetica', 7.5); cv.setFillColor(colors.HexColor('#666666'))
    cv.drawRightString(192 * mm, 277 * mm, 'BDGD 2024-12-31 V11')
    cv.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    cv.drawString(18 * mm, 11 * mm, datetime.date.today().strftime('%d/%m/%Y'))
    cv.drawRightString(192 * mm, 11 * mm, f'Página {doc.page}')
    cv.restoreState()


S = []
S.append(Spacer(1, 10))
S.append(Paragraph('Estudo de criticidade dos alimentadores', TIT))
S.append(Paragraph('Enel Distribuição São Paulo — 1.531 alimentadores, 153 subestações — BDGD 2024-12-31', SUB))

# ---------------------------------------------------------------- 1
S.append(Paragraph('1. Resumo executivo', H1))
n100 = len([x for x in OK if x['carreg_pct'] > 100])
n80 = len([x for x in OK if 80 < x['carreg_pct'] <= 100])
S.append(Paragraph(
    'Foram avaliados <b>' + br(len(OK), 0) + '</b> alimentadores de <b>153 subestações</b>, cobrindo toda a área de '
    'concessão. <b>' + str(n100) + ' circuitos (' + br(100*n100/len(OK),1) + '%) operam acima da capacidade nominal</b> '
    'do condutor de tronco na ponta do mês mais carregado, e outros ' + str(n80) + ' estão na faixa de atenção entre '
    '80% e 100%. A grande maioria — ' + br(len([x for x in OK if x['carreg_pct']<=50]),0) + ' circuitos, '
    + br(100*len([x for x in OK if x['carreg_pct']<=50])/len(OK),0) + '% do total — opera abaixo de 50%.', P))
S.append(Paragraph(
    'Sobre a hipótese que originou o trabalho: das cinco subestações apontadas como sobrecarregadas, '
    '<b>apenas o GNA-111 se confirma</b>, com 106,0% e 21ª posição no ranking. EMB-107 e EMB-106 estão '
    'carregados mas dentro do limite (78,7% e 68,3%). BSI-105 e CAM-013 estão folgados (23,3% e 13,5%), nas '
    'posições 1.147 e 1.352 de 1.531. As subestações realmente críticas da concessão são outras.', P))

d = [[c('Faixa de carregamento', True), c('Alimentadores', True), c('% do total', True), c('Situação', True)]]
FX = [('≥ 131%', lambda x: x >= 131, 'sobrecarga severa'),
      ('121 – 130%', lambda x: 121 <= x < 131, 'sobrecarga'),
      ('111 – 120%', lambda x: 111 <= x < 121, 'sobrecarga'),
      ('101 – 110%', lambda x: 101 <= x < 111, 'acima do nominal'),
      ('81 – 100%', lambda x: 81 <= x < 101, 'atenção'),
      ('51 – 80%', lambda x: 51 <= x < 81, 'normal'),
      ('≤ 50%', lambda x: x < 51, 'folgado')]
for nome, f, sit in FX:
    q = [x for x in OK if f(x['carreg_pct'])]
    d.append([c(nome, True), c(br(len(q), 0)), c(br(100 * len(q) / len(OK), 1) + '%'), c(sit)])
t = tab(d, [34 * mm, 30 * mm, 28 * mm, 44 * mm])
t.setStyle(TableStyle([('ALIGN', (1, 1), (2, -1), 'RIGHT'),
                       ('TEXTCOLOR', (0, 1), (-1, 4), VM), ('TEXTCOLOR', (0, 5), (-1, 5), LA),
                       ('TEXTCOLOR', (0, 7), (-1, 7), VD)]))
S.append(t)

# ---------------------------------------------------------------- 2
S.append(Paragraph('2. Metodologia', H1))
S.append(Paragraph(
    'A avaliação é analítica, feita diretamente sobre a BDGD, sem simulação de fluxo de potência. Isso '
    'permite cobrir os 1.806 alimentadores da distribuidora — inviável por modelagem elétrica individual — '
    'ao custo de não capturar queda de tensão, desequilíbrio entre fases nem perdas. Para as quatro '
    'subestações modeladas em OpenDSS, os dois métodos foram comparados: no CAM-301 o método analítico deu '
    '152% e a simulação 174%, diferença de 12% — a favor da simulação, que inclui as perdas.', P))
S.append(Paragraph('2.1 Cálculo da demanda de ponta', H2))
S.append(Paragraph(
    'Para cada alimentador, somou-se a energia mensal de todas as unidades consumidoras de baixa tensão '
    '(<i>UCBT_tab</i>, 8,26 milhões de registros) e de média tensão (<i>UCMT_tab</i>, 15.892). Tomou-se o '
    'mês de maior energia, converteu-se em demanda média dividindo por 730 h e aplicou-se o fator de ponta '
    'da curva de carga típica de cada classe (<i>CRVCRG</i>, dia útil). A corrente resulta de '
    'P / (√3 · 13,8 kV · 0,92).', P))
S.append(Paragraph('2.2 Capacidade de referência', H2))
S.append(Paragraph(
    'Adotou-se a <b>capacidade nominal (CNOM)</b> do condutor trifásico de maior seção do alimentador, obtida '
    'do cruzamento entre <i>SSDMT</i> (1,42 milhão de trechos) e <i>SEGCON</i>. Na BDGD, CMAX = 1,2 × CNOM; '
    'usar CMAX reduziria todos os percentuais em 17%. Vale confirmar qual referência a Figura 2 do '
    'Diagnóstico adotou, porque a escolha muda a leitura de forma relevante.', P))
S.append(Paragraph('2.3 Índice de instabilidade', H2))
S.append(Paragraph(
    'Combina quatro dimensões numa escala de 0 (mais estável) a 100 (menos estável). Um circuito a 70% e '
    'crescendo 10% ao ano é menos estável que outro a 85% estagnado — daí a necessidade de um índice '
    'composto, e não apenas do carregamento.', P))
d = [[c('Dimensão', True), c('Peso', True), c('O que mede', True), c('Fonte na BDGD', True)]]
for a, b, e, f in [
    ('Carregamento', '45', 'Corrente de ponta sobre a capacidade nominal do tronco', 'UCBT, UCMT, SSDMT, SEGCON'),
    ('Margem de reserva', '20', 'kW ainda disponíveis antes do limite. Distingue circuito pequeno '
     'folgado de circuito grande no limite', 'derivado'),
    ('Crescimento', '20', 'Tendência da energia ao longo dos 12 meses, em % ao ano', 'ENE_01 a ENE_12'),
    ('Qualidade', '15', 'DIC médio por unidade consumidora (60%) e penetração de geração '
     'distribuída sobre a ponta (40%)', 'DIC_01 a 12, UGBT, UGMT'),
]:
    d.append([c(a, True), c(b), c(e), c(f)])
t = tab(d, [26 * mm, 12 * mm, 78 * mm, 38 * mm])
t.setStyle(TableStyle([('ALIGN', (1, 1), (1, -1), 'CENTER')]))
S.append(t)

S.append(Paragraph('2.4 Controle de qualidade do dado', H2))
S.append(Paragraph(
    f'De 1.580 alimentadores com dados suficientes, <b>{len(SUS)} foram separados por inconsistência</b> na '
    'própria BDGD e não entram no ranking: demanda que implicaria mais de três vezes a capacidade máxima do '
    'condutor, série mensal errática (variação anual acima de ±60%) ou poucas unidades consumidoras com '
    'energia muito alta. O caso extremo é o SND-0104, cuja energia registrada implicaria 705 MW de ponta em '
    '4.804 consumidores. Esses registros merecem auditoria à parte — estão listados na planilha com a '
    'coluna de alerta preenchida.', P))

S.append(PageBreak())
# ---------------------------------------------------------------- 3
S.append(Paragraph('3. As cinco subestações da hipótese inicial', H1))
S.append(Paragraph(
    'Comparação entre o que a Figura 2 do Diagnóstico 2022 apontava e o que a BDGD de dezembro de 2024 '
    'mostra. A posição é no ranking de carregamento entre os 1.531 alimentadores consistentes.', P))
d = [[c('Circuito', True), c('Faixa Fig. 2 (2022)', True), c('Carreg. 2024', True), c('Posição', True),
      c('kW ponta', True), c('I ponta (A)', True), c('I nom (A)', True), c('Índice', True), c('Veredito', True)]]
for cod, fx in [('GNA0111', '111–120%'), ('EMB0107', '121–130%'), ('EMB0106', '121–130%'),
                ('BSI0105', '111–120%'), ('CAM0013', '121–130%')]:
    x = next((y for y in OK if y['ctmt'] == cod), None)
    if not x:
        continue
    v = 'confirmado' if x['carreg_pct'] > 100 else ('atenção' if x['carreg_pct'] > 60 else 'não confirmado')
    d.append([c(cod, True), c(fx), c(br(x['carreg_pct']) + '%', True), c(f"{POS[cod]}º"),
              c(br(x['kW_ponta'], 0)), c(br(x['I_ponta_A'])), c(br(x['Inom_A'], 0)),
              c(br(x['indice'])), c(v, True)])
t = tab(d, [20 * mm, 24 * mm, 20 * mm, 16 * mm, 20 * mm, 20 * mm, 18 * mm, 14 * mm, 22 * mm])
t.setStyle(TableStyle([('ALIGN', (2, 1), (7, -1), 'RIGHT'),
                       ('TEXTCOLOR', (8, 1), (8, 1), VM), ('TEXTCOLOR', (8, 2), (8, 3), LA),
                       ('TEXTCOLOR', (8, 4), (8, 5), VD)]))
S.append(t)
S.append(Paragraph(
    'O <b>GNA-111</b> é o único que se confirma: 106% de carregamento, 16.776 kW de ponta contra uma '
    'capacidade de 864 A. Os dois circuitos da SE Embu (EMB-106 e EMB-107) estão em faixa de atenção. '
    'Os outros dois não se sustentam — o CAM-013 opera a 13,5%, na posição 1.352 de 1.531. '
    'Duas explicações possíveis, não excludentes: a rede foi reforçada entre 2022 e 2024, ou a Figura 2 '
    'usa uma referência de capacidade diferente da ampacidade do condutor.', P))

# ---------------------------------------------------------------- 4
S.append(Paragraph('4. Ranking de subestações', H1))
se = collections.defaultdict(lambda: {'n': 0, 'car': [], 'kw': 0.0, 'crit': 0, 'idx': []})
for x in OK:
    s = se[x['sub']]; s['n'] += 1; s['car'].append(x['carreg_pct']); s['kw'] += x['kW_ponta']
    s['idx'].append(x['indice'])
    if x['carreg_pct'] > 100:
        s['crit'] += 1
ordem = sorted(se.items(), key=lambda kv: -max(kv[1]['car']))
S.append(Paragraph(
    'As 20 subestações com o alimentador mais carregado. "Circuitos > 100%" é a contagem de alimentadores '
    'em sobrecarga dentro da subestação.', P))
d = [[c('#', True), c('SE', True), c('Alim.', True), c('Maior carreg.', True), c('Carreg. médio', True),
      c('Circuitos > 100%', True), c('MW de ponta', True), c('Índice médio', True)]]
for i, (s, v) in enumerate(ordem[:20], 1):
    d.append([c(str(i)), c(str(s), True), c(str(v['n'])), c(br(max(v['car'])) + '%', True),
              c(br(sum(v['car']) / len(v['car'])) + '%'), c(str(v['crit'])),
              c(br(v['kw'] / 1000)), c(br(sum(v['idx']) / len(v['idx'])))])
t = tab(d, [8 * mm, 18 * mm, 16 * mm, 24 * mm, 24 * mm, 28 * mm, 24 * mm, 22 * mm])
t.setStyle(TableStyle([('ALIGN', (2, 1), (-1, -1), 'RIGHT')]))
S.append(t)

S.append(PageBreak())
# ---------------------------------------------------------------- 5
S.append(Paragraph('5. Lista de sobrecarga — do mais crítico ao mais estável', H1))
S.append(Paragraph(
    'Os 60 alimentadores mais carregados. A lista completa dos 1.580, ordenada e com todas as colunas, '
    'está em <b>ranking_alimentadores.csv</b>.', P))
d = [[c('#', True), c('CTMT', True), c('SE', True), c('Carreg.', True), c('kW ponta', True),
      c('I (A)', True), c('I nom', True), c('Reserva kW', True), c('Cresc. %/ano', True),
      c('UCs', True), c('DIC h', True), c('GD %', True), c('Índice', True)]]
for i, x in enumerate(OK[:60], 1):
    d.append([c(str(i)), c(x['ctmt'], True), c(str(x['sub'])[:5]), c(br(x['carreg_pct']) + '%', True),
              c(br(x['kW_ponta'], 0)), c(br(x['I_ponta_A'], 0)), c(br(x['Inom_A'], 0)),
              c(br(x['reserva_kW'], 0)), c(br(x['cresc_pct_ano'])), c(br(x['n_uc'], 0)),
              c(br(x['dic_medio_h'])), c(br(x['gd_pct'])), c(br(x['indice']))])
t = tab(d, [7 * mm, 18 * mm, 13 * mm, 16 * mm, 18 * mm, 13 * mm, 13 * mm, 18 * mm, 17 * mm,
            15 * mm, 12 * mm, 11 * mm, 13 * mm])
sty = [('ALIGN', (3, 1), (-1, -1), 'RIGHT')]
for i, x in enumerate(OK[:60], 1):
    if x['carreg_pct'] > 100:
        sty.append(('TEXTCOLOR', (0, i), (-1, i), VM))
    elif x['carreg_pct'] > 80:
        sty.append(('TEXTCOLOR', (0, i), (-1, i), LA))
t.setStyle(TableStyle(sty))
S.append(t)

S.append(PageBreak())
# ---------------------------------------------------------------- 6
S.append(Paragraph('6. Os mais instáveis pelo índice composto', H1))
S.append(Paragraph(
    'Ordenação pelo índice, que pondera carregamento, reserva, crescimento e qualidade. Circuitos que '
    'aparecem aqui e não no ranking de carregamento são os que preocupam pela <b>trajetória</b>, não pelo '
    'estado atual — tipicamente carga média com crescimento acelerado.', P))
inst = sorted(OK, key=lambda x: -x['indice'])[:25]
d = [[c('#', True), c('CTMT', True), c('SE', True), c('Índice', True), c('Carreg.', True),
      c('Cresc. %/ano', True), c('Reserva kW', True), c('DIC h', True), c('GD %', True),
      c('Componente dominante', True)]]
for i, x in enumerate(inst, 1):
    comp = max([('carregamento', x['i_carreg']), ('reserva', x['i_reserva']),
                ('crescimento', x['i_cresc']), ('qualidade', x['i_qualidade'])], key=lambda t_: t_[1])
    d.append([c(str(i)), c(x['ctmt'], True), c(str(x['sub'])[:5]), c(br(x['indice']), True),
              c(br(x['carreg_pct']) + '%'), c(br(x['cresc_pct_ano'])), c(br(x['reserva_kW'], 0)),
              c(br(x['dic_medio_h'])), c(br(x['gd_pct'])), c(f'{comp[0]} ({br(comp[1])})')])
t = tab(d, [8 * mm, 20 * mm, 14 * mm, 16 * mm, 18 * mm, 20 * mm, 20 * mm, 14 * mm, 13 * mm, 31 * mm])
t.setStyle(TableStyle([('ALIGN', (3, 1), (8, -1), 'RIGHT')]))
S.append(t)

# ---------------------------------------------------------------- 7
S.append(Paragraph('7. Leitura dos resultados', H1))
d = [[c('Constatação', True), c('Evidência', True), c('Implicação', True)]]
for a, b, e in [
    ('A concessão não está globalmente sobrecarregada',
     f'{n100} de {len(OK):,} circuitos acima de 100%; 71% abaixo de 50%.'.replace(',', '.'),
     'A criticidade é pontual e concentrada. Investimento deve ser direcionado, não difuso.'),
    ('A criticidade concentra-se em poucas subestações',
     'TCTR tem 4 circuitos acima de 100% e 139 MW de ponta; DTMR tem 2 em 7 circuitos, com carregamento '
     'médio de 78%.',
     'Priorizar estudo de reforço por subestação, não por alimentador isolado.'),
    ('A hipótese inicial se confirma só parcialmente',
     'Dos 5 circuitos apontados, 1 acima de 100%, 2 em atenção e 2 folgados.',
     'Revisar o critério que gerou a lista original — provavelmente denominador diferente.'),
    ('Há circuitos estáveis hoje e críticos amanhã',
     'TMR-0109 está a 130,9% com crescimento de 38,8% ao ano; SAC-0103 a 117,2% crescendo 23,6%.',
     'O índice composto identifica esses casos antes que virem restrição operativa.'),
    ('A base tem registros inconsistentes',
     f'{len(SUS)} alimentadores com energia incompatível com a rede física.',
     'Auditar a origem desses registros antes de usá-los em planejamento.'),
]:
    d.append([c(a, True), c(b), c(e)])
S.append(tab(d, [44 * mm, 64 * mm, 66 * mm]))

S.append(Paragraph('8. Ressalvas', H1))
for t_ in [
    '<b>Método analítico, não simulação.</b> Não captura queda de tensão, desequilíbrio entre fases nem '
    'perdas. A comparação com o OpenDSS no CAM-301 sugere que o método <b>subestima</b> em cerca de 12%.',
    '<b>Tensão de 13,8 kV assumida</b> para todos os alimentadores. 92% da base tem o mesmo código de '
    'tensão nominal dos circuitos verificados, mas os 8% restantes podem estar em outro nível.',
    '<b>Capacidade nominal do condutor</b> como referência. Se a Figura 2 usa a corrente do disjuntor de '
    'saída ou um limite operativo, os percentuais não são diretamente comparáveis.',
    '<b>Fator de ponta das curvas típicas da BDGD</b>, não medição real. A coincidência entre classes '
    'dentro do mesmo alimentador não é modelada — o que tende a <b>superestimar</b> a ponta.',
    '<b>Base de dezembro de 2024</b> contra uma figura de 2022. Reforços executados no período explicam '
    'parte das diferenças.',
]:
    S.append(Paragraph('• ' + t_, ParagraphStyle('L', parent=P, leftIndent=10, spaceAfter=4)))

S.append(Paragraph('9. Recomendações', H1))
for i, t_ in enumerate([
    'Confirmar a referência de capacidade usada na Figura 2. É a verificação mais barata e pode reconciliar '
    'boa parte da divergência sem tocar em modelo.',
    f'Auditar os {len(SUS)} registros inconsistentes da BDGD — são erros de base que contaminam qualquer '
    'estudo de planejamento.',
    'Modelar em OpenDSS as 10 subestações do topo do ranking, para obter queda de tensão e perdas. '
    'O processo já está automatizado e documentado.',
    'Acompanhar os circuitos com índice alto por crescimento (TMR-0109, SAC-0103), que hoje não são os mais '
    'carregados mas têm a pior trajetória.',
    'Repetir a análise mês a mês, e não só no mês de maior energia, para capturar sazonalidade.',
]):
    S.append(Paragraph(f'{i + 1}. {t_}', ParagraphStyle('L', parent=P, leftIndent=10, spaceAfter=4)))

doc = SimpleDocTemplate(DEST, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                        topMargin=22 * mm, bottomMargin=20 * mm,
                        title='Estudo de criticidade — Enel SP')
doc.build(S, onFirstPage=rod, onLaterPages=rod)
print('OK', DEST, os.path.getsize(DEST))
