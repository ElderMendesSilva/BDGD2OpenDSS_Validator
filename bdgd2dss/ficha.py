# -*- coding: utf-8 -*-
"""A ficha do circuito: o que a interface do OpenDSS sabe dizer sobre a rede.

É a primeira página do relatório, e existe para responder uma pergunta que
nenhuma figura responde: **o que exatamente foi simulado?** Perda de 3% numa
rede de 40 barras e perda de 3% numa de 40 mil são resultados diferentes, e
sem o censo do circuito ao lado o número flutua sem denominador.

Tudo aqui sai da interface — `Circuit`, `Bus`, `Lines`, `Transformers`,
`PVSystems`, `Meters`, `Solution` — e não do `.dss` lido como texto. A
diferença importa: o texto diz o que foi ESCRITO, a interface diz o que o
motor de fato MONTOU. Elemento que o OpenDSS descartou por erro de sintaxe
some da interface e continua no arquivo, e foi assim que uma rodada antiga
reportou transformadores que não existiam na matriz de admitância.

As duas funções são independentes de qual motor está sendo usado: a DSS C-API
e o COM da EPRI expõem os mesmos nomes, com a diferença de que na C-API são
chamadas e no COM são propriedades. `_v()` resolve isso.
"""
import math


def _v(x):
    """O valor, seja ele propriedade (COM) ou chamada (C-API)."""
    try:
        return x() if callable(x) else x
    except Exception:                                        # noqa: BLE001
        return None


def _attr(obj, *nomes):
    """O primeiro dos `nomes` que existir, ja resolvido.

    A DSS C-API e o COM da EPRI nao concordam em todos os nomes — a tensao por
    no e `AllBusMagPu` numa e `AllBusVmagPu` na outra. Sem isto a ficha some
    inteira num dos motores, e some em SILENCIO, porque quem chama engole a
    excecao para nao derrubar o relatorio.
    """
    for n in nomes:
        if hasattr(obj, n):
            return _v(getattr(obj, n))
    return None


def _num(x):
    try:
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def ficha_do_circuito(dss):
    """O censo do circuito resolvido. Devolve um dicionário achatado.

    NUNCA LEVANTA, e isso é requisito e não conveniência: quem chama engole a
    exceção para não derrubar o relatório de uma subestação quebrada, então um
    nome de atributo errado não apareceria como erro — apareceria como uma
    página em branco que ninguém nota. Por isso TODO acesso passa por `_attr`,
    inclusive os que existem nos dois motores hoje. Campo que o motor não sabe
    responder vem `None`, e a ficha escreve um travessão.
    """
    c = dss.Circuit
    f = {}

    f['nome'] = _attr(c, 'Name')
    sol = dss.Solution
    f['convergiu'] = bool(_attr(sol, 'Converged'))
    f['iteracoes'] = _attr(sol, 'Iterations')
    f['iteracoes_controle'] = _attr(sol, 'ControlIterations')
    f['modo'] = _attr(sol, 'ModeID', 'Mode')

    # ------------------------------------------------------------- o tamanho
    nos = _attr(c, 'AllNodeNames') or []
    barras = _attr(c, 'AllBusNames') or []
    f['n_barras'] = len(barras)
    f['n_nos'] = len(nos)
    f['n_elementos'] = _attr(c, 'NumCktElements')

    for atributo, chave in (('Lines', 'n_linhas'),
                            ('Transformers', 'n_trafos'),
                            ('Loads', 'n_cargas'),
                            ('Capacitors', 'n_capacitores'),
                            ('PVsystems', 'n_pv'),
                            ('RegControls', 'n_regcontrols'),
                            ('Meters', 'n_medidores'),
                            ('Generators', 'n_geradores')):
        # NAO usar `A or B` aqui: estas colecoes definem `__len__`, entao uma
        # colecao VAZIA e falsa e o `or` cairia no nome alternativo, que nao
        # existe — e o campo viraria `None` em vez de zero. Foi assim que os
        # reguladores sumiram da ficha da Roraima, que tem zero deles.
        obj = getattr(dss, atributo, None)
        if obj is None:
            obj = getattr(dss, atributo.lower(), None)
        f[chave] = _v(getattr(obj, 'Count', None)) if obj is not None else None

    # ------------------------------------------------- potência e perda (kW)
    tp = _attr(c, 'TotalPower') or [None, None]
    f['fonte_kW'] = -_num(tp[0]) if _num(tp[0]) is not None else None
    f['fonte_kvar'] = -_num(tp[1]) if len(tp) > 1 and _num(tp[1]) is not None else None
    if f['fonte_kW'] and f['fonte_kvar'] is not None:
        s = math.hypot(f['fonte_kW'], f['fonte_kvar'])
        f['fp_fonte'] = abs(f['fonte_kW']) / s if s else None
    else:
        f['fp_fonte'] = None

    perdas = _attr(c, 'Losses') or [None, None]
    f['perdas_kW'] = (_num(perdas[0]) / 1000.0
                      if _num(perdas[0]) is not None else None)
    lin = _attr(c, 'LineLosses') or [None]
    f['perdas_linhas_kW'] = _num(lin[0])
    if f['perdas_kW'] is not None and f['perdas_linhas_kW'] is not None:
        f['perdas_trafos_kW'] = f['perdas_kW'] - f['perdas_linhas_kW']
    else:
        f['perdas_trafos_kW'] = None
    if f['perdas_kW'] is not None and f['fonte_kW']:
        f['perdas_pct'] = 100.0 * f['perdas_kW'] / f['fonte_kW']
    else:
        f['perdas_pct'] = None

    # ---------------------------------------------------------------- tensão
    # `AllBusVmagPu` é por NÓ e mistura os níveis de tensão. Separar MT de BT
    # é o que evita o erro clássico de reportar "tensão mínima 0,00 pu" que na
    # verdade é o neutro de um secundário.
    pus = [p for p in (_attr(c, 'AllBusMagPu', 'AllBusVmagPu') or []) if _num(p) is not None]
    f['n_nos_zerados'] = sum(1 for p in pus if p <= 1e-6)
    f['pct_nos_zerados'] = (100.0 * f['n_nos_zerados'] / len(pus)) if pus else None
    vivos = sorted(p for p in pus if p > 1e-6)
    if vivos:
        f['V_min'] = vivos[0]
        f['V_max'] = vivos[-1]
        f['V_mediana'] = vivos[len(vivos) // 2]
        fa = sum(1 for p in vivos if p < 0.93 or p > 1.05)
        f['pct_fora_faixa'] = 100.0 * fa / len(vivos)
    else:
        f['V_min'] = f['V_max'] = f['V_mediana'] = f['pct_fora_faixa'] = None

    # a barra pior, que é o que alguém vai querer abrir depois
    pior, pior_pu, dmax = None, None, 0.0
    kvs = set()
    try:
        for b in barras:
            _v(getattr(c, 'SetActiveBus', lambda _b: None)(b))
            kvb = _num(_attr(dss.Bus, 'kVBase'))
            if kvb:
                kvs.add(round(kvb * math.sqrt(3), 1))
            d = _num(_attr(dss.Bus, 'Distance')) or 0.0
            dmax = max(dmax, d)
            if kvb is None or kvb <= 1:
                continue
            vv = [p for p in (_attr(dss.Bus, 'puVmagAngle') or [])[0::2]
                  if 0.001 < (p or 0) < 3]
            if vv and (pior_pu is None or min(vv) < pior_pu):
                pior_pu, pior = min(vv), b
    except Exception:                                        # noqa: BLE001
        pass
    f['barra_pior'] = pior
    f['barra_pior_pu'] = pior_pu
    f['distancia_max_km'] = dmax or None
    f['niveis_kV'] = sorted(kvs, reverse=True)[:6]

    # ------------------------------------------------------------ instalados
    f['kW_pv_instalado'] = _soma(dss, 'PVsystems', 'Pmpp')
    f['kvar_capacitores'] = _soma(dss, 'Capacitors', 'kvar')
    f['kW_carga_instalada'] = _soma(dss, 'Loads', 'kW')
    f['km_linhas'] = _km(dss)
    return f


def _soma(dss, colecao, campo):
    obj = getattr(dss, colecao, None)
    if obj is None:
        return None
    try:
        total, i = 0.0, _v(obj.First)
        while i:
            x = _num(_v(getattr(obj, campo)))
            if x:
                total += x
            i = _v(obj.Next)
        return total
    except Exception:                                        # noqa: BLE001
        return None


def _km(dss):
    """Quilômetros de linha, convertendo a unidade de cada trecho.

    O OpenDSS guarda `Length` na unidade declarada no próprio trecho, e a BDGD
    mistura metros e quilômetros na mesma subestação. Somar sem converter dá
    número mil vezes errado — já deu.
    """
    fator = {0: 0.0, 1: 1.609344, 2: 0.0003048, 3: 1.0, 4: 0.001,
             5: 0.0000254, 6: 0.0000833, 7: 0.001}
    try:
        L = dss.Lines
        total, i = 0.0, _v(L.First)
        while i:
            comp = _num(_v(L.Length)) or 0.0
            u = _v(L.Units)
            total += comp * fator.get(int(u) if u is not None else 3, 0.0)
            i = _v(L.Next)
        return total or None
    except Exception:                                        # noqa: BLE001
        return None


# ===========================================================================
#  O QUE OS 96 PASSOS PERMITEM MEDIR
# ===========================================================================
#
# Um instantâneo de ponta responde "cabe?". A série de 15 minutos responde
# "cabe QUANDO, e por quanto tempo?" — e são perguntas diferentes desde que
# existe geração distribuída, porque o pior caso da GD não é o pico de carga:
# é o vale de carga com sol a pino, um instante que nenhum estudo de ponta
# visita.

def ficha_do_dia(serie, passos=96):
    """As métricas derivadas da série de 96 passos.

    `serie` é o `energia_dia.json`: listas `fonte_kw`, `gd_kw`, `perdas_kw`,
    com `None` nos passos que não convergiram.
    """
    f = {}
    fonte = [x for x in (serie.get('fonte_kw') or [])]
    gd = [x for x in (serie.get('gd_kw') or [])]
    perdas = [x for x in (serie.get('perdas_kw') or [])]
    h = 24.0 / passos if passos else 0.25

    val = [x for x in fonte if x is not None]
    f['passos_validos'] = len(val)
    f['passos_falhos'] = sum(1 for x in fonte if x is None)
    if not val:
        return f

    pico, vale = max(val), min(val)
    f['pico_kW'] = pico
    f['vale_kW'] = vale
    f['media_kW'] = sum(val) / len(val)
    # Fator de carga: média sobre pico. Abaixo de 0,4 é rede residencial pura;
    # acima de 0,7 há carga industrial ou o modelo aplicou a mesma curva a
    # todo mundo — e a segunda hipótese é a que mais aparece aqui.
    f['fator_de_carga'] = (f['media_kW'] / pico) if pico else None
    i_pico = max(range(len(fonte)),
                 key=lambda k: (fonte[k] is not None, fonte[k] or -1e18))
    f['hora_pico'] = i_pico * h
    i_vale = min((k for k in range(len(fonte)) if fonte[k] is not None),
                 key=lambda k: fonte[k])
    f['hora_vale'] = i_vale * h

    # Rampa: a maior variação entre dois passos consecutivos. É o que dimensiona
    # reserva e o que a regulação de tensão tem de acompanhar.
    rampas = [abs(fonte[k] - fonte[k - 1]) for k in range(1, len(fonte))
              if fonte[k] is not None and fonte[k - 1] is not None]
    f['rampa_max_kW'] = max(rampas) if rampas else None

    # Curva de duração: quantas horas a carga fica acima de 90% do pico. Pico
    # que dura 15 minutos é um problema de proteção; pico que dura 6 horas é um
    # problema de condutor.
    f['horas_acima_90pct'] = sum(1 for x in val if x >= 0.9 * pico) * h
    f['horas_reverso'] = sum(1 for x in val if x < 0) * h

    pv = [x for x in perdas if x is not None]
    if pv:
        f['perda_pico_kW'] = max(pv)
        f['perda_vale_kW'] = min(pv)
        # A perda no vale é quase toda ferro: existe com a rede vazia. A razão
        # entre ela e a do pico separa a parcela fixa da que depende da carga,
        # e é essa separação que a perda declarada pela distribuidora costuma
        # não fazer (achado 13).
        f['razao_perda_pico_vale'] = (max(pv) / min(pv)) if min(pv) else None
        f['kWh_perdas'] = sum(pv) * h

    f['kWh_fonte'] = sum(val) * h
    gv = [x for x in gd if x is not None]
    if gv and any(gv):
        f['kWh_gd'] = sum(gv) * h
        f['gd_pico_kW'] = max(gv)
        f['hora_gd_pico'] = gv.index(max(gv)) * h
        # Coincidência: quanto da GD está disponível NA HORA DO PICO da carga.
        # É o número que decide se a geração alivia a rede ou só desloca
        # energia no tempo, e em rede solar com pico noturno ele é próximo de
        # zero por construção.
        no_pico = gd[i_pico] if i_pico < len(gd) else None
        f['gd_no_pico_kW'] = no_pico
        f['coincidencia_gd'] = ((no_pico / max(gv)) if (no_pico is not None
                                                       and max(gv)) else None)
        carga = [(fo or 0) + (g or 0) for fo, g in zip(fonte, gd)]
        f['passos_reversos'] = sum(1 for g, t in zip(gv, carga) if g > t)
        # PENETRACAO CONTRA O CONSUMO, e nao contra a energia injetada. A
        # formula antiga dividia pela soma (fonte + GD), que e o denominador
        # certo so enquanto a fonte e positiva. Em cinco subestacoes da Roraima
        # a fonte fica NEGATIVA no balanco do dia — a GD declarada supera a
        # carga declarada —, o denominador encolhe e a penetracao saia 533%,
        # que nao quer dizer nada.
        consumo = f['kWh_fonte'] + f['kWh_gd'] - (f.get('kWh_perdas') or 0)
        f['kWh_consumo'] = consumo
        f['exporta_no_dia'] = f['kWh_fonte'] < 0
        f['penetracao_gd_pct'] = (100.0 * f['kWh_gd'] / consumo
                                  if consumo > 0 else None)
    return f


# ===========================================================================
#  A FICHA IMPRESSA
# ===========================================================================

def _hora(h):
    """22,25 nao e hora nenhuma: e 22h15. A ficha e lida por quem opera rede."""
    try:
        h = float(h)
        return '%dh%02d' % (int(h), round((h - int(h)) * 60))
    except (TypeError, ValueError):
        return '—'


def _f(x, casas=2, mil=False):
    if casas == 'h':
        return _hora(x)
    if x is None:
        return '—'
    if isinstance(x, bool):
        return 'sim' if x else 'NÃO'
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return ', '.join(_f(i, 1) for i in x) or '—'
    try:
        if mil:
            return f'{x:,.0f}'.replace(',', '.')
        return (('%%.%df' % casas) % x).replace('.', ',')
    except (TypeError, ValueError):
        return str(x)


# (rótulo, chave, casas, usar separador de milhar)
LINHAS_CIRCUITO = [
    ('barras', 'n_barras', 0, True),
    ('nós', 'n_nos', 0, True),
    ('elementos', 'n_elementos', 0, True),
    ('trechos de linha', 'n_linhas', 0, True),
    ('extensão (km)', 'km_linhas', 1, False),
    ('transformadores', 'n_trafos', 0, True),
    ('cargas', 'n_cargas', 0, True),
    ('carga instalada (kW)', 'kW_carga_instalada', 0, True),
    ('geradores fotovoltaicos', 'n_pv', 0, True),
    ('potência FV instalada (kW)', 'kW_pv_instalado', 0, True),
    ('capacitores (kvar)', 'kvar_capacitores', 0, True),
    ('reguladores de tensão', 'n_regcontrols', 0, True),
    ('medidores de energia', 'n_medidores', 0, True),
    ('níveis de tensão (kV)', 'niveis_kV', 1, False),
    ('maior distância à fonte (km)', 'distancia_max_km', 2, False),
]

LINHAS_OPERACAO = [
    ('convergiu', 'convergiu', 0, False),
    ('iterações', 'iteracoes', 0, False),
    ('iterações de controle', 'iteracoes_controle', 0, False),
    ('potência da fonte (kW)', 'fonte_kW', 0, True),
    ('reativo da fonte (kvar)', 'fonte_kvar', 0, True),
    ('fator de potência na fonte', 'fp_fonte', 3, False),
    ('perdas totais (kW)', 'perdas_kW', 1, False),
    ('perdas (%)', 'perdas_pct', 2, False),
    ('perdas nas linhas (kW)', 'perdas_linhas_kW', 1, False),
    ('perdas nos trafos (kW)', 'perdas_trafos_kW', 1, False),
    ('tensão mínima (pu)', 'V_min', 4, False),
    ('tensão mediana (pu)', 'V_mediana', 4, False),
    ('tensão máxima (pu)', 'V_max', 4, False),
    ('nós fora da faixa (%)', 'pct_fora_faixa', 2, False),
    ('nós com tensão zero', 'n_nos_zerados', 0, True),
    ('nós com tensão zero (%)', 'pct_nos_zerados', 2, False),
    ('barra de menor tensão', 'barra_pior', 0, False),
]

LINHAS_DIA = [
    ('passos que convergiram', 'passos_validos', 0, False),
    ('passos que falharam', 'passos_falhos', 0, False),
    ('demanda de pico (kW)', 'pico_kW', 0, True),
    ('hora do pico', 'hora_pico', 'h', False),
    ('demanda de vale (kW)', 'vale_kW', 0, True),
    ('hora do vale', 'hora_vale', 'h', False),
    ('demanda média (kW)', 'media_kW', 0, True),
    ('fator de carga', 'fator_de_carga', 3, False),
    ('maior rampa em 15 min (kW)', 'rampa_max_kW', 0, True),
    ('horas acima de 90% do pico', 'horas_acima_90pct', 2, False),
    ('horas com fluxo reverso', 'horas_reverso', 2, False),
    ('energia da fonte (kWh)', 'kWh_fonte', 0, True),
    ('energia perdida (kWh)', 'kWh_perdas', 0, True),
    ('perda no pico (kW)', 'perda_pico_kW', 1, False),
    ('perda no vale (kW)', 'perda_vale_kW', 1, False),
    ('razão perda pico/vale', 'razao_perda_pico_vale', 2, False),
    ('energia gerada pela GD (kWh)', 'kWh_gd', 0, True),
    ('energia consumida (kWh)', 'kWh_consumo', 0, True),
    ('penetração da GD (%)', 'penetracao_gd_pct', 2, False),
    ('pico da GD (kW)', 'gd_pico_kW', 0, True),
    ('hora do pico da GD', 'hora_gd_pico', 'h', False),
    ('GD disponível no pico de carga (kW)', 'gd_no_pico_kW', 0, True),
    ('coincidência GD × pico', 'coincidencia_gd', 3, False),
]


def linhas_da_ficha(circuito, dia=None):
    """A ficha como lista de (bloco, rótulo, valor formatado).

    Só entra o que foi medido: linha com valor ausente é ruído numa tabela que
    existe para ser lida de relance.
    """
    saida = []
    for bloco, tabela, dados in (('O circuito', LINHAS_CIRCUITO, circuito),
                                 ('O ponto de operação', LINHAS_OPERACAO, circuito),
                                 ('O dia em 96 passos', LINHAS_DIA, dia or {})):
        for rotulo, chave, casas, mil in tabela:
            if chave not in (dados or {}):
                continue
            valor = dados.get(chave)
            if valor is None or valor == [] or valor == '':
                continue
            saida.append((bloco, rotulo, _f(valor, casas, mil)))
    return saida


def imprimir(circuito, dia=None, escreve=print):
    """A ficha no terminal, em três blocos."""
    atual = None
    for bloco, rotulo, valor in linhas_da_ficha(circuito, dia):
        if bloco != atual:
            atual = bloco
            escreve('')
            escreve('  ' + bloco.upper())
            escreve('  ' + '-' * 56)
        escreve('    %-38s %s' % (rotulo, valor))
