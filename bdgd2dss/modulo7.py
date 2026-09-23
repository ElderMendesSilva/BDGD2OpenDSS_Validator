# -*- coding: utf-8 -*-
"""Perdas em ramais de ligacao e medidores, pelas regras do Modulo 7 do PRODIST.

POR QUE EXISTE. A referencia externa (`dados/perdas_aneel.csv`) e a perda
tecnica regulatoria que a ANEEL calcula com o ProgGeoPerdas — BDGD no OpenDSS
— e soma alta, media e baixa tensao, transformadores, RAMAIS e MEDIDORES. O
modelo nacional roda com a BT agregada e nao tem nem ramal nem medidor. Este
modulo completa esses dois segmentos, para que a comparacao seja do mesmo
recorte. Ver o achado 66.

A FONTE E O TEXTO DO MODULO 7 (Anexo VII da REN 956/2021, DOU de 15/12/2021,
pp. 196-202), e nao memoria:

- MEDIDOR: "Para os medidores, sao computadas as perdas nas bobinas de tensao
  localizadas nas unidades consumidoras do grupo B." PM = K x PC x 1e-6 MW, com
  PC = 1 W por circuito de tensao no eletromecanico e 0,5 W no eletronico, e
  K = 3 (3 fases e 4 fios), 2 (2 fases e 3 fios, ou 1 fase e 3 fios), 1 (1 fase
  e 2 fios). A energia e PM x o periodo.
- RAMAL: entra no fluxo de potencia do SDBT como condutor. Sem cadastro, "o
  comprimento regulatorio de 15 metros"; "o comprimento maximo admissivel para
  o ramal de ligacao e de 30 metros".

O RAMAL NAO PRECISA DE FLUXO DE POTENCIA AQUI. Cada ramal alimenta so as
unidades penduradas nele, entao a corrente dele e a soma das delas, e a perda
e R x I^2 nos condutores que conduzem — o que o fluxo daria, a menos da queda
de tensao, que num ramal de 15 m e de fracao de ponto percentual.

O QUE AINDA E PREMISSA, dito:

- `EQME.TIPMED`: 1 = eletromecanico e 2 = eletronico e INFERIDO — o manual da
  BDGD nao esta ao alcance, e na FORCEL83 o codigo 2 tem instalacao mediana em
  2020 contra 2014 do 1. Por isso o medidor sai com tres numeros: o provavel,
  o teto (todos a 1 W) e o piso (todos a 0,5 W).
- K para as ligacoes que o Modulo 7 nao cita: 3 fases SEM neutro (ABC) conta 2
  circuitos de tensao, como o medidor trifasico a 3 fios; 2 fases sem neutro
  (AB) conta 1, uma tensao so.
- Fator de potencia 0,92, o mesmo que o Modulo 7 fixa para transformadores.
- Tipo de dia pelo calendario (seg-sex, sabado, domingo), sem feriados.
"""
import calendar
import collections
import math

import numpy as np

from .leitor import num, txt
from . import tensoes

PC_W = {'eletromecanico': 1.0, 'eletronico': 0.5}
# INFERIDO, a confirmar no manual da BDGD — ver o cabecalho.
TIPMED_PROVAVEL = {'1': 'eletromecanico', '2': 'eletronico'}
RAMAL_SEM_CADASTRO_M = 15.0
RAMAL_MAXIMO_M = 30.0
FP = 0.92
# Um ramal nao conduz, em regime, o dobro da ampacidade do proprio condutor.
# Acima disso a corrente e da ENERGIA declarada e nao da rede: unidade de BT
# com energia implausivel, que o quadrado da corrente amplifica. Ver
# `perda_ramais`.
FATOR_AMPACIDADE = 2.0
PASSOS = 96                       # CRVCRG: 96 pontos de 15 min
DT_H = 24.0 / PASSOS
DIAS = ('DU', 'SA', 'DO')


def k_medidor(fas_con):
    """Circuitos de tensao do medidor, pela ligacao da unidade."""
    f = txt(fas_con).upper()
    fases = sum(1 for c in 'ABC' if c in f)
    neutro = 'N' in f
    if fases >= 3:
        return 3 if neutro else 2
    if fases == 2:
        return 2 if neutro else 1
    return 1


def dias_por_tipo(ano):
    """{mes: {'DU': n, 'SA': n, 'DO': n}} pelo calendario."""
    out = {}
    for m in range(1, 13):
        c = collections.Counter()
        for d in range(1, calendar.monthrange(ano, m)[1] + 1):
            w = calendar.weekday(ano, m, d)
            c['DO' if w == 6 else 'SA' if w == 5 else 'DU'] += 1
        out[m] = dict(c)
    return out


def horas_do_ano(ano):
    return (366 if calendar.isleap(ano) else 365) * 24.0


def perda_medidores(bdgd, ano=2025):
    """Perda anual nos medidores do grupo B, por CTMT, em MWh.

    Devolve `{ctmt: {'provavel', 'teto', 'piso', 'n', 'sem_tipo'}}`. A unidade
    sem medidor na EQME entra pelo teto (1 W) no provavel, contada em
    `sem_tipo`.
    """
    uc = bdgd.ler('UCBT_tab', ['COD_ID', 'CTMT', 'FAS_CON'])
    tipo = {}
    try:
        eq = bdgd.ler('EQME', ['UC_UG', 'TIPMED'])
        for u, t in zip(eq['UC_UG'], eq['TIPMED']):
            tipo[txt(u)] = TIPMED_PROVAVEL.get(txt(t))
    except Exception:                                        # noqa: BLE001
        pass
    h = horas_do_ano(ano)
    out = collections.defaultdict(lambda: {'provavel': 0.0, 'teto': 0.0,
                                           'piso': 0.0, 'n': 0, 'sem_tipo': 0})
    for cod, ct, fas in zip(uc['COD_ID'], uc['CTMT'], uc['FAS_CON']):
        k = k_medidor(fas)
        t = tipo.get(txt(cod))
        r = out[txt(ct)]
        r['n'] += 1
        if t is None:
            r['sem_tipo'] += 1
        pc = PC_W.get(t, PC_W['eletromecanico'])
        r['provavel'] += k * pc * h / 1e6
        r['teto'] += k * PC_W['eletromecanico'] * h / 1e6
        r['piso'] += k * PC_W['eletronico'] * h / 1e6
    return dict(out)


def _resistencias(bdgd):
    """{TIP_CND: ohm/km} da SEGCON, com a MESMA correcao do `linecodes`.

    Ler o R1 cru nao serve, e a primeira medida nacional provou: a Copel deu
    372 W medios por ramal contra 0,6 W da FORCEL83, e a CPFL Santa Cruz
    2,5 TWh/ano so em ramal. A causa e a que o achado dos condutores
    incoerentes ja tinha medido — R1 dezenas de vezes acima do previsto para a
    ampacidade do cabo —, e o `linecodes` corrige isso desde entao. A perda do
    ramal vai com o quadrado da corrente mas e LINEAR em R: um R 100x errado e
    uma perda 100x errada.
    """
    from . import linecodes
    s = bdgd.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
    pares = [(num(r), num(c)) for r, c in zip(s['R1'], s['CNOM'])]
    aj = linecodes._ajuste(pares) if linecodes.FATOR_CORRIGE else None
    out = {}
    for cod, r1, cnom in zip(s['COD_ID'], s['R1'], s['CNOM']):
        r1, cnom = num(r1), num(cnom)
        if r1 <= 0:
            continue
        if aj and cnom > 0:
            prev = math.exp(aj[1]) * cnom ** aj[0]
            if r1 > linecodes.FATOR_CORRIGE * prev:
                r1 = prev
        out[txt(cod)] = r1
    return out


def _curvas(bdgd):
    """{(TIP_CC, dia): vetor de 96 com media 1}."""
    col = bdgd.ler('CRVCRG', ['COD_ID', 'TIP_DIA'] +
                   [f'POT_{i:02d}' for i in range(1, PASSOS + 1)])
    out = {}
    for i in range(len(col['COD_ID'])):
        v = np.array([num(col[f'POT_{k:02d}'][i]) for k in range(1, PASSOS + 1)])
        if v.mean() > 0:
            out[(txt(col['COD_ID'][i]), txt(col['TIP_DIA'][i]).upper())] = v / v.mean()
    return out


def perda_ramais(bdgd, ano=2025, kv_bt_padrao=0.22, lote=20000):
    """Perda anual nos ramais de ligacao da BT, por CTMT, em MWh.

    Devolve `({ctmt: MWh}, censo)`, com o censo das premissas que pesaram:
    ramais sem comprimento (15 m), acima de 30 m (cortados), sem condutor
    conhecido, e unidades sem ramal.
    """
    try:
        r = bdgd.ler('RAMLIG', ['COD_ID', 'CTMT', 'TIP_CND', 'COMP', 'FAS_CON'])
    except Exception:                                        # noqa: BLE001
        # base sem RAMLIG: nao ha ramal a somar, e isso e dito, nao zerado
        return {}, {'sem_tabela': 'RAMLIG'}
    ohm_km = _resistencias(bdgd)
    s_ = bdgd.ler('SEGCON', ['COD_ID', 'CNOM'])
    ampac = {txt(c): num(a) for c, a in zip(s_['COD_ID'], s_['CNOM']) if num(a) > 0}
    curvas = _curvas(bdgd)
    uc = bdgd.ler('UCBT_tab', ['RAMAL', 'TIP_CC', 'FAS_CON', 'TEN_FORN'] +
                  [f'ENE_{m:02d}' for m in range(1, 13)])
    censo = collections.Counter()

    # O ramal: resistencia do caminho e fases
    ram = {}
    r_med = np.median(list(ohm_km.values())) if ohm_km else 1.0
    for cod, ct, cnd, comp, fas in zip(r['COD_ID'], r['CTMT'], r['TIP_CND'],
                                       r['COMP'], r['FAS_CON']):
        L = num(comp)
        if L <= 0:
            L = RAMAL_SEM_CADASTRO_M
            censo['sem_comprimento'] += 1
        elif L > RAMAL_MAXIMO_M:
            L = RAMAL_MAXIMO_M
            censo['acima_de_30m'] += 1
        rk = ohm_km.get(txt(cnd))
        if rk is None:
            rk = r_med
            censo['condutor_desconhecido'] += 1
        f = txt(fas).upper()
        nf = max(1, sum(1 for c in 'ABC' if c in f))
        ram[txt(cod)] = (txt(ct), rk * L / 1000.0, nf, 'N' in f,
                         ampac.get(txt(cnd), 0.0))
    censo['ramais'] = len(ram)

    # As unidades, agrupadas por ramal: a potencia de cada instante e a SOMA.
    # Monta-se um mes por vez: 12 x ramais x tipos de curva passaria de 2 GB
    # numa base de um milhao de ramais.
    tipos = sorted({t for t, _ in curvas})
    it = {t: i for i, t in enumerate(tipos)}
    idx_ram = {k: i for i, k in enumerate(ram)}
    n_r, n_t = len(ram), max(1, len(tipos))
    n_uc = len(uc['RAMAL'])
    J = np.full(n_uc, -1, dtype=np.int64)
    T = np.zeros(n_uc, dtype=np.int64)
    v_fn = np.full(n_r, kv_bt_padrao * 1000 / math.sqrt(3))
    for i in range(n_uc):
        j = idx_ram.get(txt(uc['RAMAL'][i]))
        if j is None:
            censo['uc_sem_ramal'] += 1
            continue
        J[i] = j
        t = it.get(txt(uc['TIP_CC'][i]))
        if t is None:
            censo['uc_sem_curva'] += 1
            t = 0
        T[i] = t
        kv = tensoes.kv(uc['TEN_FORN'][i], kv_bt_padrao)
        # codigo de BT e tensao de LINHA; abaixo de 0,2 kV e ja fase-neutro
        v_fn[j] = kv * 1000 / math.sqrt(3) if kv >= 0.2 else kv * 1000
    ok = J >= 0

    R = np.array([v[1] for v in ram.values()])
    NF = np.array([v[2] for v in ram.values()])
    # monofasico com neutro: a corrente volta pelo neutro, 2 condutores
    NCOND = NF + np.array([1 if (v[2] == 1 and v[3]) else 0 for v in ram.values()])
    dias = dias_por_tipo(ano)
    AMP = np.array([v[4] for v in ram.values()])
    perda_kwh = np.zeros(n_r)
    i_max = np.zeros(n_r)
    for m in range(12):
        ene = np.array([num(x) for x in uc[f'ENE_{m + 1:02d}']])
        E = np.zeros((n_r, n_t), dtype=np.float64)
        np.add.at(E, (J[ok], T[ok]), ene[ok])                          # kWh
        nd = sum(dias[m + 1].values())
        for d in DIAS:
            if not dias[m + 1].get(d):
                continue
            S = np.stack([curvas.get((t, d), curvas.get((t, 'DU'), np.ones(PASSOS)))
                          for t in tipos]) if tipos else np.ones((1, PASSOS))
            for a in range(0, n_r, lote):
                b = min(n_r, a + lote)
                # W em cada instante: E/(24 h x dias) x curva de media 1
                P = (E[a:b, :] / (24.0 * nd)) @ S * 1000.0
                I = P / (NF[a:b, None] * v_fn[a:b, None] * FP)
                i_max[a:b] = np.maximum(i_max[a:b], I.max(axis=1))
                w = NCOND[a:b, None] * R[a:b, None] * I ** 2
                perda_kwh[a:b] += w.sum(axis=1) * DT_H * dias[m + 1][d] / 1000.0
    # ACHADO 73 — O RAMAL QUE CONDUZ O QUE NENHUM CABO CONDUZ. A primeira
    # medida nacional deu 71,7% da energia injetada em ramal na CPFL Santa
    # Cruz e 56,6% na Copel, com resistencia (0,67 e 0,59 ohm/km), comprimento
    # e unidades por ramal (1,08) normais — e 579 W medios por ramal, contra
    # 0,7 W da mediana do pais. Para isso a corrente media teria de ser ~100 A
    # numa unidade residencial: e a ENERGIA declarada de poucas unidades,
    # implausivel para a BT, que o quadrado da corrente faz dominar a base.
    # O ramal cuja corrente de pico passa de FATOR_AMPACIDADE x a ampacidade
    # do proprio condutor sai da soma e e contado a parte, como o modelo
    # principal faz com o alimentador implausivel.
    implausivel = (AMP > 0) & (i_max > FATOR_AMPACIDADE * AMP)
    censo['ramais_implausiveis'] = int(implausivel.sum())
    censo['mwh_implausivel'] = round(float(perda_kwh[implausivel].sum()) / 1000.0, 1)
    por_ct = collections.defaultdict(float)
    for (ct, *_), p, fora in zip(ram.values(), perda_kwh, implausivel):
        if not fora:
            por_ct[ct] += p / 1000.0                                    # MWh
    perda_kwh = np.where(implausivel, 0.0, perda_kwh)
    # DIAGNOSTICO, porque a primeira medida nacional teve base com 70% da
    # energia injetada em ramal e a causa nao apareceu no censo: a resistencia
    # mediana usada, quantas unidades pendura cada ramal e o watt medio de
    # cada um dizem, juntos, se o absurdo e do dado ou da conta.
    if len(perda_kwh):
        censo['w_medio_por_ramal'] = round(
            float(perda_kwh.sum()) * 1000.0 / len(perda_kwh) / horas_do_ano(ano), 2)
    if ohm_km:
        censo['ohm_km_mediano'] = round(float(np.median(list(ohm_km.values()))), 4)
    if n_r:
        por_ramal = np.bincount(J[ok], minlength=n_r) if n_uc else np.zeros(n_r)
        censo['uc_por_ramal_medio'] = round(float(por_ramal.mean()), 2)
        censo['uc_por_ramal_max'] = int(por_ramal.max()) if n_r else 0
        # R = ohm/km x L/1000  ->  L = R x 1000 / (ohm/km)
        censo['comprimento_medio_m'] = round(
            float(np.mean([v[1] for v in ram.values()])) * 1000.0
            / max(1e-9, float(np.median(list(ohm_km.values())) if ohm_km else 1)), 1)
    return dict(por_ct), dict(censo)
