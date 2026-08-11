# -*- coding: utf-8 -*-
"""
CAMADA DE ALTA TENSAO (subtransmissao) — gerada uma unica vez, compartilhada.

    SSDAT     -> Line          trechos de subtransmissao (88 kV)
    UNSEAT    -> Line(Switch)  chaves e disjuntores de AT, com o estado real
    UNTRAT    -> Transformer   trafos de potencia AT -> MT (com EQTRAT)
    UCAT_tab  -> Load          consumidores atendidos em AT
    UGAT_tab  -> Generator     geracao conectada em AT
    UNCRAT    -> Capacitor     bancos de AT
    (derivado)-> Line(Switch)  os VAOS: barra de MT da SE -> cabeceira

Por que a AT nao pode ser por subestacao: a rede de 88 kV LIGA as subestacoes
entre si. Recorta-la por SE cortaria justamente os trechos que interessam.
Ela e gerada uma vez em _AT/ e referenciada por todos os modelos.

--------------------------------------------------------------------------
O VAO — a peca que faltava
--------------------------------------------------------------------------
A BDGD nao modela o arranjo interno da subestacao. Verificado na DABR: os
seis PAC_INI dos alimentadores estao na malha de MT, mas o PAC_2 dos dois
trafos de AT nao se conecta a nenhum deles — nao ha barramento, nem vao,
nem disjuntor de saida entre o trafo e o alimentador. O elo existe apenas
de forma logica, em CTMT.UNI_TR_AT e CTMT.BARR.

Era isso que obrigava a versao anterior a criar uma fonte infinita por
alimentador. Aqui o elo logico vira eletrico: cada barra de MT declarada em
BAR (ou em UNTRAT.BARR_2) vira um no de verdade, o secundario do trafo
chega nela, e de la sai um vao por alimentador ate o seu PAC_INI. Com isso
os alimentadores da mesma subestacao passam a dividir o mesmo trafo e a
mesma barra — que e como a rede realmente opera.
"""
import collections
import math

from .leitor import num, txt, no as _no
from . import tensoes

FASES = {'A': '1', 'B': '2', 'C': '3'}

# Reatancia de dispersao dos trafos de potencia. A BDGD traz PER_TOT e
# PER_FER (perdas), mas nao a impedancia. Valores tipicos de trafo de
# subestacao AT/MT, por faixa de potencia (NBR 5356 / pratica de projeto).
XHL_POR_MVA = [(10, 7.0), (25, 9.0), (50, 10.5), (1e9, 12.5)]

# Impedancia do vao (barra de MT -> cabeceira). E um disjuntor de saida mais
# alguns metros de barramento: praticamente um curto, mas nao zero.
R_VAO = 1e-4

# Nivel de curto-circuito equivalente quando nao ha dado da transmissora.
MVASC_PADRAO = 2500.0

CAB_VAOS = """! ==========================================================
! VAOS DE SAIDA — barra de MT da SE -> cabeceira do alimentador
! Derivado de CTMT.BARR e CTMT.UNI_TR_AT: a BDGD nao modela o
! arranjo interno da subestacao, so o vinculo logico.
! Cada vao e o disjuntor de saida do alimentador.
! ==========================================================
"""


def _fases(s, padrao='ABC'):
    f = [FASES[c] for c in txt(s, padrao).upper() if c in FASES]
    return f or ['1', '2', '3']


def _xhl(mva):
    for lim, x in XHL_POR_MVA:
        if mva <= lim:
            return x
    return 12.5


def _pot_mva(v):
    """UNTRAT.POT_NOM vem em MVA (20.0 = 20 MVA). Alguns registros aparecem
    em kVA; acima de 1.000 o valor so pode ser kVA."""
    p = num(v, 0.0)
    if p <= 0:
        return 0.0
    return p / 1000.0 if p > 1000 else p


# ====================================================================== leitura
def carregar(bdgd):
    """Le de uma vez tudo que descreve a AT. Sao tabelas pequenas —
    462 trafos, 29.519 trechos, 2.622 chaves, 988 barras."""
    d = {}
    d['bar'] = bdgd.ler('BAR', ['COD_ID', 'SUB', 'TEN_NOM', 'PAC', 'TIP_INST'])
    d['untrat'] = bdgd.ler('UNTRAT', ['COD_ID', 'SUB', 'BARR_1', 'BARR_2',
                                      'PAC_1', 'PAC_2', 'POT_NOM', 'FAS_CON_P',
                                      'FAS_CON_S', 'SIT_ATIV'])
    d['ssdat'] = bdgd.ler('SSDAT', ['COD_ID', 'PAC_1', 'PAC_2', 'CTAT',
                                    'FAS_CON', 'TIP_CND', 'COMP'])
    d['unseat'] = bdgd.ler('UNSEAT', ['COD_ID', 'PAC_1', 'PAC_2', 'FAS_CON',
                                      'P_N_OPE', 'SUB', 'SIT_ATIV'])
    d['ctat'] = bdgd.ler('CTAT', ['COD_ID', 'NOME', 'TEN_NOM', 'PAC_INI'])
    try:
        e = bdgd.ler('EQTRAT', ['UNI_TR_AT', 'TEN_PRI', 'TEN_SEC', 'LIG',
                                'PER_FER', 'PER_TOT'])
        d['eqtrat'] = {txt(e['UNI_TR_AT'][i]): {
            'ten_pri': txt(e['TEN_PRI'][i]), 'ten_sec': txt(e['TEN_SEC'][i]),
            'lig': txt(e['LIG'][i]), 'per_fer': num(e['PER_FER'][i], 0.3),
            'per_tot': num(e['PER_TOT'][i], 0.8)} for i in range(len(e['UNI_TR_AT']))}
    except Exception:
        d['eqtrat'] = {}
    return d


def barras_mt(dados):
    """{codigo da barra -> {sub, ten}} apenas das barras de MT das SEs."""
    b = dados['bar']
    out = {}
    for i in range(len(b['COD_ID'])):
        if txt(b['TIP_INST'][i]) != 'SE_MT':
            continue
        out[txt(b['COD_ID'][i])] = {'sub': txt(b['SUB'][i]),
                                    'ten': txt(b['TEN_NOM'][i])}
    return out


# ================================================================== trafos AT
def trafos(dados, caminho, kv_at_padrao=88.0, kv_mt_padrao=13.8, log=None,
           subs_alvo=None, tap_por_sub=None, nos_malha=None,
           barra_de_sub=None):
    """UNTRAT + EQTRAT -> Transformer. O secundario vai para a BARRA de MT,
    nao para o PAC_2 solto — e a barra que os alimentadores enxergam.

    ONDE O PRIMARIO SE LIGA — achado 7, corrigido no passo 5
    -------------------------------------------------------
    O primario saia de `UNTRAT.PAC_1`, decifrado por engenharia reversa na
    Enel SP. Medido nas sete bases, a cobertura dessa chave e:

        Enel SP  99,5%   |   Roraima, Light, Equatorial PA, CPFL,
                             Enel CE e Cemig-D:  0,0% em TODAS

    Nao e "funciona menos bem nas outras": nao funciona em nenhuma. E a
    camada de AT saia com 0 trechos, 0 fontes e 0 km, com SSDAT impecavel do
    lado.

    A candidata que o achado 7 registrava — `BARR_1` -> `BAR.COD_ID` — casa
    de 86% a 100% em todas, mas nao resolve: o `BAR.PAC` correspondente
    tambem nao esta na SSDAT fora da Enel SP (0,0%). Ela identifica a barra
    e nao chega a rede. **A medicao refutou a correcao proposta**, e por isso
    o teste de aceitacao foi escrito pelo RESULTADO e nao pelo mecanismo.

    O que generaliza e a ancora por SUBESTACAO: `UNTRAT.SUB` aparece em
    `UNSEAT.SUB` de 75,9% (Roraima) a 100%, mediana 98,2%. E o `malha_at` ja
    cria uma barra de AT por subestacao e a liga aos trechos que a
    reivindicam. Entao: PAC_1 quando ele existe na malha, a barra da
    subestacao quando nao.

    `nos_malha` sao os nos da rede de AT (SSDAT + UNSEAT fechadas) e
    `barra_de_sub` e a funcao que nomeia a barra de AT de cada subestacao.
    Sem os dois, o comportamento e o antigo.

    `subs_alvo` restringe aos trafos das subestacoes que estao sendo geradas.
    Sem esse filtro, gerar duas subestacoes traria os 437 trafos da concessao
    com o secundario em aberto — o modelo ate resolve, mas com tensao e
    reativo sem sentido fisico (trafo a vazio no fim de linha longa).

    `tap_por_sub` e o CTMT.TEN_OPE da subestacao: o comutador sob carga
    sustentando a barra de MT acima do nominal, como a distribuidora opera.
    Sem isso a concessao inteira ficava ~9% deslocada para baixo.
    """
    u = dados['untrat']
    eq = dados['eqtrat']
    n = len(u['COD_ID'])
    tap_por_sub = tap_por_sub or {}
    out = ['! ==========================================================',
           '! TRANSFORMADORES DE POTENCIA — UNTRAT + EQTRAT',
           '! Primario: PAC_1 (malha de 88 kV, vinda de SSDAT).',
           '! Secundario: a BARRA de MT (BARR_2), compartilhada pelos',
           '! alimentadores da subestacao.',
           '! Xhl NAO vem da BDGD — adotado por faixa de potencia (ver',
           '! XHL_POR_MVA). %loadloss = PER_TOT - PER_FER, %noloadloss =',
           '! PER_FER, ambos da BDGD.',
           '! O tap do secundario reproduz CTMT.TEN_OPE.',
           '! ==========================================================']
    barra_do_trafo = {}          # COD_ID do trafo -> no da barra de MT
    kv_da_barra = {}             # no da barra de MT -> kV
    pac_at = {}                  # COD_ID do trafo -> PAC de 88 kV
    por_sub = collections.defaultdict(list)
    mva_por_sub = collections.Counter()
    ativos = 0
    por_barra_sub = 0
    for i in range(n):
        cod = txt(u['COD_ID'][i])
        if txt(u['SIT_ATIV'][i]) not in ('AT', ''):
            continue                                   # desativado (DS)
        sub = txt(u['SUB'][i]).strip()
        if subs_alvo is not None and sub not in subs_alvo:
            continue
        no_at = _no(u['PAC_1'][i])
        # Ancora de reserva: a barra de AT da subestacao. Ver o cabecalho —
        # o PAC_1 casa com a SSDAT so na Enel SP.
        #
        # A reserva so entra se `barra_de_sub` devolver algo: o chamador
        # recusa a barra das subestacoes que a malha nao vai ligar a rede.
        # Nesses casos vale o PAC_1 original, que fica ilhado — mas ilhado
        # tambem era o comportamento antigo, e trocar por uma barra que
        # ninguem cria seria pior, nao melhor.
        if nos_malha is not None and barra_de_sub and sub and no_at not in nos_malha:
            alt = barra_de_sub(sub)
            if alt:
                no_at = alt
                por_barra_sub += 1
        if not no_at:
            continue
        # o no do secundario e a barra declarada; se faltar, cai no PAC_2
        no_mt = _no(u['BARR_2'][i]) or _no(u['PAC_2'][i])
        if not no_mt:
            continue
        e = eq.get(cod, {})
        kv1 = tensoes.kv(e.get('ten_pri'), kv_at_padrao, log, 'EQTRAT.TEN_PRI')
        kv2 = tensoes.kv(e.get('ten_sec'), kv_mt_padrao, log, 'EQTRAT.TEN_SEC')
        mva = _pot_mva(u['POT_NOM'][i]) or 20.0
        per_tot = e.get('per_tot', 0.8)
        per_fer = e.get('per_fer', 0.3)
        carga = max(0.05, per_tot - per_fer)
        lig = e.get('lig', '2')
        conn1 = 'delta' if lig in ('2', '5', '7', '9', '12') else 'wye'
        conn2 = 'delta' if lig in ('7', '9', '10', '11', '12') else 'wye'
        nd1 = '.1.2.3' if conn1 == 'delta' else '.1.2.3.0'
        nd2 = '.1.2.3' if conn2 == 'delta' else '.1.2.3.0'
        tap = tap_por_sub.get(sub, 1.0)
        out.append(f'New Transformer.AT_{cod} phases=3 windings=2 Xhl={_xhl(mva):.2f}\n'
                   f'~ %loadloss={carga:.3f} %noloadloss={per_fer:.3f}\n'
                   f'~ wdg=1 bus={no_at}{nd1} conn={conn1} kV={kv1:.4f} kVA={mva*1000:.0f}\n'
                   f'~ wdg=2 bus={no_mt}{nd2} conn={conn2} kV={kv2:.4f} '
                   f'kVA={mva*1000:.0f} tap={tap:.4f}')
        barra_do_trafo[cod] = no_mt
        kv_da_barra[no_mt] = kv2
        pac_at[cod] = no_at
        por_sub[sub].append(cod)
        mva_por_sub[sub] += mva
        ativos += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if log and por_barra_sub:
        log(f'  {por_barra_sub} de {ativos} trafos ancorados pela barra de AT '
            f'da subestacao (PAC_1 fora da malha) — achado 7')
    return {'n': ativos, 'barra_do_trafo': barra_do_trafo,
            'kv_da_barra': kv_da_barra, 'pac_at': pac_at,
            'por_sub': dict(por_sub), 'mva_por_sub': dict(mva_por_sub),
            'ancorados_por_barra_sub': por_barra_sub}


# =================================================================== linhas AT
def linhas(dados, mapa_cnd, caminho, log=None, nos_alvo=None):
    """SSDAT -> Line. Os condutores de AT estao todos na SEGCON (69 de 69
    tipos), entao os mesmos LineCodes da MT servem.

    `nos_alvo` limita aos patios que alimentam as subestacoes geradas."""
    s = dados['ssdat']
    out = ['! ==========================================================',
           '! LINHAS DE SUBTRANSMISSAO — SSDAT',
           '! LineCodes da SEGCON, os mesmos usados na MT.',
           '! ==========================================================']
    barras = set()
    nomes = []
    km = 0.0
    n = 0
    for i in range(len(s['COD_ID'])):
        b1 = _no(s['PAC_1'][i])
        b2 = _no(s['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        if nos_alvo is not None and b1 not in nos_alvo:
            continue
        fs = _fases(s['FAS_CON'][i], 'ABC')
        comp = num(s['COMP'][i], 1.0) or 1.0
        d = mapa_cnd.get(txt(s['TIP_CND'][i]))
        lc = d[len(fs)] if (d and len(fs) in d) else f'CND_GENERICO_{len(fs)}F'
        nd = '.' + '.'.join(fs)
        cod = txt(s['COD_ID'][i])
        out.append(f'New Line.AT_{cod} Bus1={b1}{nd} Bus2={b2}{nd} '
                   f'LineCode={lc} Length={comp:.2f} Units=m')
        barras.add(b1); barras.add(b2)
        nomes.append(cod)
        km += comp / 1000.0
        n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n, round(km, 2), barras, nomes


# =================================================================== chaves AT
def chaves(dados, caminho, caminho_abertas, nos_alvo=None):
    """UNSEAT -> Line com Switch=Y. P_N_OPE: 'A' = normalmente aberta."""
    s = dados['unseat']
    out = ['! ==========================================================',
           '! CHAVES E DISJUNTORES DE AT — UNSEAT',
           '! P_N_OPE = A -> normalmente aberta (comando Open no fim)',
           '! ==========================================================']
    abertas = []
    n = 0
    for i in range(len(s['COD_ID'])):
        b1 = _no(s['PAC_1'][i])
        b2 = _no(s['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        if txt(s['SIT_ATIV'][i]) not in ('AT', ''):
            continue
        if nos_alvo is not None and b1 not in nos_alvo:
            continue
        cod = txt(s['COD_ID'][i])
        fs = _fases(s['FAS_CON'][i])
        nd = '.' + '.'.join(fs)
        nome = f'ATSW_{cod}'
        out.append(f'New Line.{nome} phases={len(fs)} '
                   f'Bus1={b1}{nd} Bus2={b2}{nd} Switch=y '
                   f'r1=1e-4 r0=1e-4 x1=0 x0=0 c1=0 c0=0')
        if txt(s['P_N_OPE'][i]).upper().startswith('A'):
            abertas.append(nome)
        n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    ab = ['! Chaves de AT normalmente abertas — estado fixado apos a montagem.']
    ab += [f'Open Line.{x} 1' for x in abertas]
    open(caminho_abertas, 'w', encoding='utf-8').write('\n'.join(ab) + '\n')
    return n, abertas


# ============================================================== conectividade
def componentes(dados):
    """Componentes conexas da malha de AT, com as chaves abertas removidas.

    Devolve (lista de conjuntos de nos, conjunto das cabeceiras de CTAT).
    E sobre isso que as fontes sao distribuidas: cada patio energizado
    precisa de exatamente um ponto de injecao.
    """
    adj = collections.defaultdict(set)
    s = dados['ssdat']
    for i in range(len(s['COD_ID'])):
        a, b = _no(s['PAC_1'][i]), _no(s['PAC_2'][i])
        if a and b and a != b:
            adj[a].add(b); adj[b].add(a)
    u = dados['unseat']
    for i in range(len(u['COD_ID'])):
        if txt(u['P_N_OPE'][i]).upper().startswith('A'):
            continue                                   # normalmente aberta
        if txt(u['SIT_ATIV'][i]) not in ('AT', ''):
            continue
        a, b = _no(u['PAC_1'][i]), _no(u['PAC_2'][i])
        if a and b and a != b:
            adj[a].add(b); adj[b].add(a)

    vis, comps = set(), []
    for x in list(adj):
        if x in vis:
            continue
        pilha, c = [x], set()
        while pilha:
            y = pilha.pop()
            if y in c:
                continue
            c.add(y); vis.add(y)
            pilha.extend(adj[y] - c)
        comps.append(c)
    comps.sort(key=len, reverse=True)

    ct = dados['ctat']
    heads = {_no(ct['PAC_INI'][i]) for i in range(len(ct['COD_ID']))
             if _no(ct['PAC_INI'][i])}
    return comps, heads


# ====================================================================== vaos
def vaos(ctmt_info, info_trafos, barras, kv_mt_padrao=13.8, log=None):
    """Liga a barra de MT da subestacao a cabeceira de cada alimentador.

    Ordem de preferencia para achar a barra do alimentador:
      1. CTMT.BARR, quando essa barra e secundario de algum trafo;
      2. a barra do trafo apontado por CTMT.UNI_TR_AT;
      3. CTMT.BARR mesmo sem trafo (subestacao de transmissora);
      4. nada: o alimentador fica sem vao e e reportado.

    Os vaos saem POR SUBESTACAO, nao numa pasta comum: eles pertencem ao
    patio da SE. Guardados em _AT/ o modelo isolado nao os enxergava e a
    subestacao inteira ficava desligada da propria fonte.

    UMA BARRA POR NIVEL DE TENSAO
    -----------------------------
    Sete subestacoes tem alimentadores em tensoes diferentes, e a BDGD poe
    todos no mesmo CTMT.BARR. Adotar a tensao da barra para todos energizava
    alimentador de 13,8 kV a 34,5 kV. Medido na DALP: 1.484 dos 1.491
    transformadores ficavam com o primario fora da tensao da barra, e os
    secundarios subiam a 1,9 pu.

    Aqui a tensao do ALIMENTADOR (CTMT.TEN_NOM) prevalece. Quando ela difere
    da barra, o alimentador vai para uma barra derivada, ligada a barra
    original por um transformador de barra — que e o que existe em campo e a
    BDGD nao declara. A potencia sai rateada da capacidade de AT da SE.
    """
    bt = info_trafos['barra_do_trafo']
    kvb = info_trafos['kv_da_barra']
    mva_sub = info_trafos.get('mva_por_sub') or {}
    barras_de_trafo = set(bt.values())
    por_se = collections.defaultdict(list)
    ligados = {}
    sem_vao = []
    derivadas = {}                  # (sub, barra_orig, kv) -> barra derivada
    alim_por_sub = collections.Counter()
    alim_por_grupo = collections.Counter()

    for cod, c in ctmt_info.items():
        barr = _no(c['barr'])
        tr = c['uni_tr_at']
        alvo = None
        if barr and barr in barras_de_trafo:
            alvo = barr
        elif tr and tr in bt:
            alvo = bt[tr]
        elif barr:
            alvo = barr
        pac = _no(c['pac_ini'])
        if not alvo or not pac or pac == alvo:
            sem_vao.append(cod)
            continue

        sub = c['sub']
        alim_por_sub[sub] += 1
        kv_alim = c.get('kv') or tensoes.kv(c['ten_nom'], kv_mt_padrao, log,
                                            'CTMT.TEN_NOM')
        kv_barra = kvb.get(alvo)
        kv = kv_barra or kv_alim
        derivada = False
        if kv_barra and kv_alim and abs(kv_barra - kv_alim) > 0.1:
            chave = (sub, alvo, round(kv_alim, 4))
            if chave not in derivadas:
                derivadas[chave] = f'{alvo}_{kv_alim:g}kv'.replace('.', 'p')
            alvo = derivadas[chave]
            kv = kv_alim
            derivada = True
            alim_por_grupo[chave] += 1

        por_se[sub].append(
            f'New Line.VAO_{cod} phases=3 Bus1={alvo}.1.2.3 Bus2={pac}.1.2.3 '
            f'Switch=y r1={R_VAO} r0={R_VAO} x1=0 x0=0 c1=0 c0=0')
        por_se[sub].append(
            f'New Monitor.M_{cod} element=Line.VAO_{cod} terminal=1 '
            f'mode=1 ppolar=no')
        # `derivada` avisa o converter para NAO por Vsource nessa barra: ela
        # e alimentada pelo transformador de barra, nao por fonte propria
        ligados[cod] = {'barra': alvo, 'kv': kv, 'derivada': derivada}
        barras.add(alvo)

    # transformadores de barra das derivadas, um por nivel de tensao
    for (sub, orig, kv_alim), nova in sorted(derivadas.items()):
        kv_orig = kvb.get(orig) or kv_mt_padrao
        fatia = alim_por_grupo[(sub, orig, kv_alim)] / max(alim_por_sub[sub], 1)
        mva = max(10.0, (mva_sub.get(sub) or 40.0) * fatia)
        # O nome sai da barra DERIVADA, que ja e unica por chave. Nomear por
        # (subestacao, tensao) colidia quando a mesma subestacao tinha duas
        # barras de origem distintas precisando do mesmo nivel derivado —
        # saiam dois `Transformer.TRB_5003585_34p5` e o OpenDSS recusava o
        # arquivo inteiro: "(#266) Duplicate new element definition".
        # Nunca disparou na Enel SP; bloqueou 1 das 20 subestacoes de
        # Roraima. Bug de nascenca, exposto pela segunda base.
        nome = 'TRB_' + nova
        por_se[sub].insert(0, (
            f'! Transformador de barra: a BDGD poe alimentadores de '
            f'{kv_alim:g} kV no mesmo CTMT.BARR da barra de {kv_orig:g} kV.\n'
            f'! Em campo ha um transformador entre as duas barras; a BDGD nao '
            f'o declara. Potencia rateada da capacidade de AT da SE.\n'
            f'New Transformer.{nome} phases=3 windings=2 Xhl={_xhl(mva):.2f}\n'
            f'~ wdg=1 bus={orig}.1.2.3 conn=delta kV={kv_orig:.4f} '
            f'kVA={mva*1000:.0f}\n'
            f'~ wdg=2 bus={nova}.1.2.3.0 conn=wye kV={kv_alim:.4f} '
            f'kVA={mva*1000:.0f}'))
        barras.add(nova)
        if log:
            log(f'  {sub}: barra derivada de {kv_alim:g} kV para '
                f'{alim_por_grupo[(sub, orig, kv_alim)]} alimentadores '
                f'({mva:.0f} MVA)')
    return ligados, sem_vao, dict(por_se)


def escrever_vaos(caminho, linhas_dss):
    open(caminho, 'w', encoding='utf-8').write(CAB_VAOS + '\n'.join(linhas_dss) + '\n')


# ============================================================ cargas e geracao
def cargas(bdgd, caminho, mes=1, kv_at_padrao=88.0, fator=1.0, log=None,
           nos_alvo=None):
    """UCAT_tab -> Load. Sao 186 consumidores atendidos direto em 88 kV;
    ignora-los subestima a carga da subtransmissao."""
    try:
        c = bdgd.ler('UCAT_tab', ['COD_ID', 'PAC', 'CTAT', 'FAS_CON', 'TEN_FORN',
                                  f'ENE_P_{mes:02d}', f'ENE_F_{mes:02d}',
                                  f'DEM_P_{mes:02d}'])
    except Exception:
        open(caminho, 'w').write('! UCAT_tab indisponivel\n')
        return 0, 0.0
    out = ['! CARGAS DE ALTA TENSAO — UCAT_tab',
           '! kW = (ENE_P + ENE_F) / 730 h, como na MT e na BT.']
    n = 0
    tot = 0.0
    for i in range(len(c['COD_ID'])):
        pac = _no(c['PAC'][i])
        if not pac:
            continue
        if nos_alvo is not None and pac not in nos_alvo:
            continue
        kw = (num(c[f'ENE_P_{mes:02d}'][i]) +
              num(c[f'ENE_F_{mes:02d}'][i])) / 730.0 * fator
        if kw <= 0.001:
            continue
        fs = _fases(c['FAS_CON'][i])
        kv = tensoes.kv(c['TEN_FORN'][i], kv_at_padrao, log, 'UCAT.TEN_FORN')
        if len(fs) < 3:
            kv /= math.sqrt(3)
        out.append(f'New Load.AT_{txt(c["COD_ID"][i])} Bus1={pac}.{".".join(fs)} '
                   f'Phases={len(fs)} Conn=wye Model=1 kV={kv:.4f} pf=0.92 '
                   f'kW={kw:.4f}')
        tot += kw
        n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n, round(tot, 1)


def geracao(bdgd, caminho, kv_at_padrao=88.0, log=None, nos_alvo=None):
    """UGAT_tab -> Generator. Sao 3 unidades; entram como maquina, nao como
    PVSystem, porque em 88 kV nao se trata de geracao distribuida solar."""
    try:
        g = bdgd.ler('UGAT_tab', ['COD_ID', 'PAC', 'POT_INST', 'FAS_CON', 'TEN_CON'])
    except Exception:
        open(caminho, 'w').write('! UGAT_tab indisponivel\n')
        return 0
    out = ['! GERACAO EM ALTA TENSAO — UGAT_tab']
    n = 0
    for i in range(len(g['COD_ID'])):
        pac = _no(g['PAC'][i])
        pot = num(g['POT_INST'][i])
        if not pac or pot <= 0:
            continue
        if nos_alvo is not None and pac not in nos_alvo:
            continue
        fs = _fases(g['FAS_CON'][i])
        kv = tensoes.kv(g['TEN_CON'][i], kv_at_padrao, log, 'UGAT.TEN_CON')
        out.append(f'New Generator.GAT_{txt(g["COD_ID"][i])} phases={len(fs)} '
                   f'bus1={pac}.{".".join(fs)} kV={kv:.4f} kW={pot:.2f} '
                   f'pf=0.95 model=1 Vminpu=0.9 Vmaxpu=1.1')
        n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n


def capacitores(bdgd, caminho, kv_at_padrao=88.0, log=None, nos_alvo=None):
    """UNCRAT -> Capacitor (24 bancos)."""
    try:
        c = bdgd.ler('UNCRAT', ['COD_ID', 'PAC_1', 'POT_NOM', 'FAS_CON', 'SIT_ATIV'])
    except Exception:
        open(caminho, 'w').write('! UNCRAT indisponivel\n')
        return 0
    out = ['! CAPACITORES DE AT — UNCRAT (banco fixo; a BDGD nao traz o controle)']
    n = 0
    for i in range(len(c['COD_ID'])):
        pac = _no(c['PAC_1'][i])
        kvar = num(c['POT_NOM'][i])
        if not pac or kvar <= 0:
            continue
        if txt(c['SIT_ATIV'][i]) not in ('AT', ''):
            continue
        if nos_alvo is not None and pac not in nos_alvo:
            continue
        fs = _fases(c['FAS_CON'][i])
        out.append(f'New Capacitor.CAT_{txt(c["COD_ID"][i])} '
                   f'Bus1={pac}.{".".join(fs)} Phases={len(fs)} '
                   f'Conn=wye kV={kv_at_padrao:.4f} kvar={kvar:.1f}')
        n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n
