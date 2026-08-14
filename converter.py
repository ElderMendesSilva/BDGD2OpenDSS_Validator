# -*- coding: utf-8 -*-
"""
CONVERSOR BDGD -> OpenDSS
=========================

Recebe uma BDGD (.gdb) e gera a rede da concessao em OpenDSS: subtransmissao,
media e baixa tensao, num modelo unico e tambem em modelos por subestacao.

    python converter.py <caminho.gdb> --saida MODELOS
    python converter.py <caminho.gdb> --saida MODELOS --se DEMB DGNA
    python converter.py <caminho.gdb> --saida MODELOS --fator-carga 1.3
    python converter.py <caminho.gdb> --saida MODELOS --bt completo --se DEMB

O que sai
---------
    MASTER-GERAL.dss      a concessao inteira: AT -> MT -> BT
    _global/              LineCodes e curvas, declarados uma unica vez
    _AT/                  subtransmissao: linhas, chaves, trafos de potencia,
                          fontes e os vaos de saida das subestacoes
    <SE>/MASTER-<SE>.dss  a subestacao isolada, com equivalente na barra de MT
    <SE>/REDE-<SE>.dss    so os elementos da SE — usado pelos dois MASTERs
    relatorio_rede.json   cobertura, fontes, ilhas e o que ficou de fora

Por que existem os dois MASTERs
-------------------------------
O geral e a rede como um todo, para estudo sistemico. O por-subestacao
continua porque carregar 155 subestacoes para otimizar um alimentador e
desperdicio: o NSGA-II e o estudo de criticidade rodam no modelo isolado.
Os dois compartilham os mesmos arquivos de rede, entao nao divergem.
"""
import os, sys, json, time, argparse, collections, gc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss.leitor import BDGD, num, txt
CANCELAR = None   # a interface grafica injeta um threading.Event aqui

from bdgd2dss import (linecodes, linhas, chaves, transformadores, cargas,
                      complementos, master, subtransmissao, transmissao,
                      tensoes, malha_at, coordenadas)


def ja_gerada(pasta, se):
    """Uma SE conta como pronta se tem MASTER e resumo.json — o resumo so e
    escrito no fim, entao sua presenca garante que nao ficou pela metade."""
    return (os.path.exists(os.path.join(pasta, se, f'MASTER-{se}.dss'))
            and os.path.exists(os.path.join(pasta, se, 'resumo.json')))


def memoria_gb():
    """Memoria do processo, em GB. Devolve 0 se nao der para medir."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 ** 3)
    except Exception:
        pass
    try:  # Linux, sem dependencia externa
        with open('/proc/self/statm') as fh:
            return int(fh.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / (1024 ** 3)
    except Exception:
        return 0.0


def ler_ctmt(bdgd, kv_mt_padrao, log):
    """Cadastro dos alimentadores: subestacao, trafo de AT que o alimenta,
    barra de saida, cabeceira e tensao.

    PAC_INI e a cabeceira DECLARADA pela BDGD. A versao anterior descobria a
    cabeceira por topologia, escolhendo a barra de maior ampacidade da maior
    componente conexa — um chute que erra sempre que a rede esta fragmentada.
    Conferido na DABR: os seis PAC_INI estao todos na malha de MT do proprio
    alimentador."""
    col = bdgd.ler('CTMT', ['COD_ID', 'SUB', 'NOME', 'UNI_TR_AT', 'PAC_INI',
                            'BARR', 'TEN_NOM', 'TEN_OPE'])
    info = {}
    for i in range(len(col['COD_ID'])):
        # strip obrigatorio: a BDGD preenche campo ausente com espaco, e um
        # ' ' que passa como valido vira barra fantasma la na frente.
        cod = txt(col['COD_ID'][i]).strip()
        info[cod] = {
            'sub': txt(col['SUB'][i]).strip(),
            'nome': txt(col['NOME'][i]).strip(),
            'uni_tr_at': txt(col['UNI_TR_AT'][i]).strip(),
            'pac_ini': txt(col['PAC_INI'][i]).strip(),
            'barr': txt(col['BARR'][i]).strip(),
            'ten_nom': txt(col['TEN_NOM'][i]).strip(),
            'kv': tensoes.kv(col['TEN_NOM'][i], kv_mt_padrao, log, 'CTMT.TEN_NOM'),
            # TEN_OPE e a tensao de OPERACAO da barra de MT, em pu do nominal.
            # A Enel opera 1,09 pu em 1.586 dos 1.806 alimentadores, justamente
            # para compensar a queda ao longo do tronco. Ignorar esse campo
            # deslocava a concessao inteira ~9% para baixo: a mediana das SEs
            # ficava em 0,921 pu e cinco subestacoes nem convergiam.
            'ten_ope': min(1.15, max(0.9, num(col['TEN_OPE'][i], 1.0) or 1.0)),
        }
    return info


def gerar_at(bdgd, a, ctmt_info, mapa_cnd, log, subs_alvo=None):
    """Monta a camada de alta tensao, uma vez, em _AT/.

    Tudo que sai daqui e restrito as subestacoes pedidas. Gerar a AT inteira
    junto de poucas subestacoes produziria centenas de transformadores com o
    secundario em aberto no fim de linhas longas — o modelo resolve, mas com
    Ferranti e reativo que nao existem na rede real."""
    d = os.path.join(a.saida, '_AT')
    os.makedirs(d, exist_ok=True)
    log('Alta tensao (subtransmissao)...')
    dados = subtransmissao.carregar(bdgd)

    comps, heads = subtransmissao.componentes(dados)
    log(f'  malha de AT: {len(comps)} componentes conexas, '
        f'{len(heads)} cabeceiras de circuito')

    # tape do trafo AT/MT = tensao de operacao declarada da barra de MT.
    # Usa-se a mediana dos alimentadores da subestacao, porque TEN_OPE e por
    # alimentador mas a barra e uma so.
    import statistics as _st
    _por_sub = collections.defaultdict(list)
    for _c in ctmt_info.values():
        if _c['sub']:
            _por_sub[_c['sub']].append(_c['ten_ope'])
    tap_por_sub = {k: round(_st.median(v), 4) for k, v in _por_sub.items()}
    # Os nos da malha precisam existir ANTES dos trafos: e contra eles que o
    # `trafos` decide se o PAC_1 serve de ancora ou se cai na barra de AT da
    # subestacao (achado 7). `componentes` ja rodou acima.
    # --- fechamento da malha: cada subestacao ganha a sua barra de AT
    # Precisa vir ANTES dos trafos. A ancora de reserva do achado 7 usa a
    # barra de AT da subestacao, e so vale usa-la para as subestacoes que o
    # `malha_at` de fato vai ligar a rede: apontar o primario para uma barra
    # que ninguem cria deixa o trafo ilhado, que e o defeito de partida.
    depara = malha_at.carregar_depara(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'dados', 'de_para_mnemonicos.csv'))
    anc = malha_at.ancoras(dados, depara)
    if subs_alvo is not None:                 # so as subestacoes do recorte
        anc = {n: (s & subs_alvo) for n, s in anc.items()}
        anc = {n: s for n, s in anc.items() if s}
    log(f'  de-para: {len(depara)} mnemonicos | ancoras: {len(anc):,} nos')

    nos_malha = set().union(*comps) if comps else set()
    com_barra = {s for n, ss in anc.items() if n in nos_malha for s in ss}

    def _barra_se_ligada(sub):
        """So devolve a barra de AT se ela vai existir e estar conectada."""
        return malha_at.barra_de(sub) if sub in com_barra else ''

    info_tr = subtransmissao.trafos(dados, os.path.join(d, 'Trafos_AT.dss'),
                                    a.kv_at, a.kv_mt, log, subs_alvo,
                                    tap_por_sub, nos_malha, _barra_se_ligada)
    log(f'  {info_tr["n"]} transformadores de potencia')

    # patios de interesse: os que tem trafo alvo ou equipamento de SE alvo
    alvo_pac = set(info_tr['pac_at'].values())
    comps = [c for c in comps if (c & alvo_pac) or any(n in anc for n in c)]
    nos_alvo = set().union(*comps) if comps else set()

    malha = malha_at.gerar(comps, anc, os.path.join(d, 'Barras_AT.dss'))
    log(f'  malha de AT: {malha["barras"]} barras, {malha["ligacoes"]} ligacoes '
        f'-> {malha["componentes_antes"]} ilhas viraram {malha["componentes_depois"]}')
    grupos = malha['grupos']
    nos_alvo |= set(malha['barra_por_sub'].values())
    log(f'  {len(grupos)} patios de AT energizados, {len(nos_alvo):,} nos')

    n_lat, km_at, barras_at, nomes_lat = subtransmissao.linhas(
        dados, mapa_cnd, os.path.join(d, 'Linhas_AT.dss'), log, nos_alvo)
    log(f'  {n_lat:,} trechos de AT ({km_at:,.1f} km)')

    n_chat, abertas_at = subtransmissao.chaves(
        dados, os.path.join(d, 'Chaves_AT.dss'),
        os.path.join(d, '_CHAVES_ABERTAS_AT.dss'), nos_alvo)
    log(f'  {n_chat:,} chaves de AT ({len(abertas_at)} normalmente abertas)')

    isa = transmissao.ler_isa(a.excel, log)

    # Subestacoes que aparecem em CTMT mas nao tem transformador em UNTRAT.
    # A comparacao usa a UNTRAT INTEIRA, nao os trafos ja filtrados: senao
    # toda subestacao fora do recorte pareceria orfa.
    u = dados['untrat']
    com_trafo = {txt(u['SUB'][i]) for i in range(len(u['COD_ID']))
                 if txt(u['SIT_ATIV'][i]) in ('AT', '') and txt(u['SUB'][i])}
    orfas = collections.defaultdict(lambda: collections.defaultdict(list))
    for cod, c in ctmt_info.items():
        if subs_alvo is not None and c['sub'] not in subs_alvo:
            continue
        if c['sub'] and c['sub'] not in com_trafo:
            orfas[c['sub']][c['kv']].append(cod)
    barras_orfas, est_orfas = ({}, {'isa': 0, 'equivalente': 0, 'niveis': []})
    if orfas:
        log(f'  {len(orfas)} subestacoes sem trafo proprio '
            f'({sum(len(v) for d2 in orfas.values() for v in d2.values())} alimentadores)')
        barras_orfas, est_orfas = transmissao.trafos_transmissora(
            {k: dict(v) for k, v in orfas.items()}, isa,
            os.path.join(d, 'Trafos_Transmissora.dss'), a.kv_mt, log)

    est_fontes = transmissao.fontes(grupos, info_tr, heads, isa,
                                    os.path.join(d, 'Fontes.dss'), a.kv_at, log,
                                    malha['barra_por_sub'])

    # vaos: barra de MT -> cabeceira de cada alimentador (so os do recorte)
    ctmt_alvo = {k: v for k, v in ctmt_info.items()
                 if subs_alvo is None or v['sub'] in subs_alvo}
    ligados, sem_vao, vaos_por_se = subtransmissao.vaos(
        ctmt_alvo, info_tr, barras_at, a.kv_mt, log)
    # alimentadores das subestacoes da transmissora ganham vao pela barra dela
    for cod, bb in barras_orfas.items():
        if cod in ligados:
            continue
        pac = subtransmissao._no(ctmt_info[cod]['pac_ini'])
        if not pac:
            continue
        se_cod = ctmt_info[cod]['sub']
        vaos_por_se.setdefault(se_cod, []).append(
            f'New Line.VAO_{cod} phases=3 Bus1={bb["barra"]}.1.2.3 '
            f'Bus2={pac}.1.2.3 Switch=y r1={subtransmissao.R_VAO} '
            f'r0={subtransmissao.R_VAO} x1=0 x0=0 c1=0 c0=0')
        vaos_por_se[se_cod].append(
            f'New Monitor.M_{cod} element=Line.VAO_{cod} terminal=1 '
            f'mode=1 ppolar=no')
        ligados[cod] = {'barra': bb['barra'], 'kv': bb['kv']}
        if cod in sem_vao:
            sem_vao.remove(cod)
    log(f'  {len(ligados):,} vaos de saida ({len(sem_vao)} alimentadores sem vao)')

    # coordenadas geograficas da AT; a barra de cada SE vai no centroide
    # do seu proprio patio, que e onde ela fisicamente esta.
    co_at = coordenadas.coletar(bdgd, 'SSDAT')
    co_at = {k: v for k, v in co_at.items() if k in nos_alvo}
    extras = {}
    for sb, barra in malha['barra_por_sub'].items():
        nos_sb = [n for n, ss_ in anc.items() if sb in ss_]
        c = coordenadas.centroide(co_at, nos_sb)
        if c:
            extras[barra] = c
    n_co = coordenadas.escrever(co_at, os.path.join(d, 'BusCoords_AT.dat'), extras)
    log(f'  {n_co:,} barras de AT com coordenada')

    n_uc_at, kw_at = subtransmissao.cargas(
        bdgd, os.path.join(d, 'Cargas_AT.dss'), a.mes, a.kv_at, a.fator_carga,
        log, nos_alvo)
    n_gd_at = subtransmissao.geracao(bdgd, os.path.join(d, 'GD_AT.dss'), a.kv_at,
                                     log, nos_alvo)
    n_cap_at = subtransmissao.capacitores(
        bdgd, os.path.join(d, 'Capacitores_AT.dss'), a.kv_at, log, nos_alvo)
    log(f'  {n_uc_at} cargas de AT ({kw_at:,.0f} kW), {n_gd_at} geradores, '
        f'{n_cap_at} capacitores')

    # Vaos.dss NAO entra aqui: ele e escrito dentro de cada subestacao, para
    # que o modelo isolado tambem enxergue a ligacao com a sua barra de MT.
    arquivos = [f'_AT/{x}' for x in
                ('Fontes.dss', 'Linhas_AT.dss', 'Chaves_AT.dss', 'Barras_AT.dss',
                 'Trafos_AT.dss')]
    if orfas:
        arquivos.append('_AT/Trafos_Transmissora.dss')
    arquivos += [f'_AT/{x}' for x in
                 ('Cargas_AT.dss', 'GD_AT.dss', 'Capacitores_AT.dss')]
    arquivos = [x for x in arquivos if os.path.exists(os.path.join(a.saida, x))]

    # MVAsc que cada subestacao vera no MASTER isolado: a fonte fica na barra
    # de MT, entao o equivalente precisa embutir trafo e rede de montante.
    # Vem da capacidade instalada — 8 x MVA, ver transmissao.FATOR_CURTO.
    mvasc_por_se = {}
    for s, mva in info_tr['mva_por_sub'].items():
        mvasc_por_se[s] = round(mva * transmissao.FATOR_CURTO, 1)
    for s in orfas:                       # subestacoes da transmissora
        mvasc_por_se[s] = transmissao.mvasc_estimado(isa, s)[0]

    est = {'n_trafos_at': info_tr['n'], 'n_linhas_at': n_lat, 'km_at': km_at,
           'vaos_por_se': vaos_por_se, 'mvasc_por_se': mvasc_por_se,
           'coords_at': n_co, 'trafos_at_nomes': sorted(info_tr['pac_at']),
           'tap_por_se': tap_por_sub,
           'linhas_at_nomes': nomes_lat,
           'malha_barras': malha['barras'], 'malha_ligacoes': malha['ligacoes'],
           'malha_ilhas_antes': malha['componentes_antes'],
           'malha_ilhas_depois': malha['componentes_depois'],
           'n_chaves_at': n_chat, 'n_componentes': len(grupos),
           'n_vaos': len(ligados), 'sem_vao': sem_vao,
           'fontes_cabeceira': est_fontes['com_cabeceira'],
           'fontes_equivalente': est_fontes['equivalentes'],
           'orfas': {k: {str(kv): len(v) for kv, v in d2.items()}
                     for k, d2 in orfas.items()},
           'orfas_resolvidas_isa': est_orfas['isa'],
           'orfas_equivalente': est_orfas['equivalente'],
           'niveis_transmissora': est_orfas.get('niveis', []),
           'cargas_at': n_uc_at, 'kW_AT': kw_at, 'gd_at': n_gd_at,
           'capacitores_at': n_cap_at}
    return arquivos, est, info_tr, ligados, est_fontes


def main():
    # Sem argumento nenhum, abrir a interface e mais util do que imprimir o
    # usage: a conversao tem 20 opcoes e ninguem as decora. O app.py preenche
    # sys.argv e chama esta mesma funcao, entao nao ha recursao — quando ele
    # chama, ja ha argumento.
    if len(sys.argv) == 1:
        try:
            import app
        except Exception:
            pass
        else:
            app.App().mainloop()
            return

    ap = argparse.ArgumentParser(description='Converte BDGD em modelos OpenDSS.')
    ap.add_argument('gdb')
    ap.add_argument('--saida', default='MODELOS')
    ap.add_argument('--se', nargs='*', help='subestacoes a gerar (padrao: todas)')
    ap.add_argument('--mes', type=int, default=1)
    ap.add_argument('--dia', default='DU', choices=['DU', 'SA', 'DO'])
    ap.add_argument('--fator-carga', type=float, default=1.0)
    ap.add_argument('--kv-mt', type=float, default=13.8,
                    help='tensao de MT quando o codigo TEN_NOM e desconhecido')
    ap.add_argument('--kv-at', type=float, default=88.0)
    ap.add_argument('--bt', default='agregado', choices=['agregado', 'completo', 'nenhum'],
                    help='agregado: carga somada no secundario do trafo (padrao, '
                         'correto para estudo de MT). completo: rede de BT e uma '
                         'carga por UC — so para estudo de tensao de atendimento')
    ap.add_argument('--excel', default=None,
                    help='pasta com as planilhas da transmissora (ISA). Sem ela '
                         'as subestacoes de transmissao usam equivalente')
    ap.add_argument('--sem-at', action='store_true',
                    help='nao gerar a camada de alta tensao nem o MASTER-GERAL')
    ap.add_argument('--reg-vreg', type=float, default=122.0,
                    help='tensao de referencia dos reguladores, em V no TP')
    ap.add_argument('--lote', type=int, default=10,
                    help='subestacoes por varredura de camada da BDGD. Maior '
                         'reduz o numero de varreduras e usa mais memoria; '
                         '1 volta ao comportamento antigo (uma varredura por '
                         'subestacao). O limite de 900 itens da clausula IN '
                         'do GDAL cabe ~80 subestacoes.')
    ap.add_argument('--clima',
                    default=os.path.join('D:', os.sep, 'Elder', 'Elder',
                                         'ENEL', '04_DADOS_AUXILIARES'),
                    help='pasta com Irradiancia_Interpolada/ e Temperatura_Interpolado/ '
                         '(96 pontos por mes, dado medido de Sao Paulo). Sem ela, '
                         'usa um perfil solar sintetico, 23%% otimista e simetrico.')
    ap.add_argument('--clima-dist', default='390',
                    help='codigo ANEEL da distribuidora a que o dado de '
                         '--clima pertence. Padrao 390 (Enel SP), que e a '
                         'origem da pasta 04_DADOS_AUXILIARES. Se nao bater '
                         'com o BASE.DIST da base, o conversor RECUSA o dado '
                         'medido e cai no perfil sintetico.')
    ap.add_argument('--clima-forcar', action='store_true',
                    help='usa o clima medido mesmo sendo de outra '
                         'distribuidora. Legitimo quando a regiao e a mesma '
                         '(CPFL Paulista tambem opera em Sao Paulo). Fica '
                         'registrado no relatorio_rede.json.')
    ap.add_argument('--gd-fp', type=float, default=1.0,
                    help='fator de potencia dos inversores da GD. Padrao 1,0, '
                         'que e como operam em campo. 0,92 e a capacidade '
                         'exigida pelo PRODIST Modulo 3 — usar so para estudo '
                         'de suporte de reativo.')
    ap.add_argument('--irradiancia', type=float, default=1.0,
                    help='irradiancia dos PVSystem no instantaneo (0 a 1). '
                         '1,0 = meio-dia de ceu claro; para estudo de ponta de '
                         'carga use um valor baixo. Nao afeta o modo diario.')
    ap.add_argument('--reg-band', type=float, default=2.0)
    ap.add_argument('--reg-kva', type=float, default=5000.0)
    ap.add_argument('--cache', default='_cache_ucbt.pkl',
                    help='arquivo de cache da agregacao da UCBT (reuso entre execucoes)')
    ap.add_argument('--refazer', action='store_true',
                    help='regera as subestacoes ja existentes (padrao: pula e continua)')
    ap.add_argument('--memoria-max', type=float, default=0,
                    help='limite de memoria em GB. Ao ultrapassar, o conversor para '
                         'de forma limpa e informa onde retomar. 0 = sem limite')
    a = ap.parse_args()

    t0 = time.time()
    b = BDGD(a.gdb)
    log = b.log
    os.makedirs(a.saida, exist_ok=True)

    # se a pasta das planilhas nao foi dada, procura ao lado da .gdb
    if a.excel is None:
        cand = os.path.join(os.path.dirname(os.path.abspath(a.gdb)), '..', 'Excel')
        a.excel = os.path.abspath(cand) if os.path.isdir(cand) else None

    ctmt_info = ler_ctmt(b, a.kv_mt, log)
    kv_por_ctmt = {k: v['kv'] for k, v in ctmt_info.items()}
    ses = collections.defaultdict(list)
    for cod, c in ctmt_info.items():
        if c['sub']:
            ses[c['sub']].append(cod)
    ses = dict(ses)
    alvo = a.se or sorted(ses)

    prontas = [s for s in alvo if ja_gerada(a.saida, s)]
    if prontas and not a.refazer:
        alvo = [s for s in alvo if s not in prontas]
        print(f'{len(prontas)} subestacoes ja existem na pasta e serao puladas '
              f'(use --refazer para regerar).', flush=True)
    print(f'BDGD com {len(ses)} subestacoes e {len(ctmt_info)} alimentadores; '
          f'gerando {len(alvo)}.', flush=True)

    # --- itens globais
    print('LineCodes (SEGCON)...', flush=True)
    tmp = os.path.join(a.saida, '_global')
    os.makedirs(tmp, exist_ok=True)
    mapa_cnd, n_lc, corr_cnd = linecodes.gerar(b, os.path.join(tmp, 'LineCodes.dss'))
    print(f'  {n_lc} condutores', flush=True)
    if corr_cnd:
        km_c = sum(1 for _ in corr_cnd)
        print(f'  {km_c} com R1 incoerente com a ampacidade — resistencia '
              f'substituida pelo ajuste da propria base (ver LineCodes.dss)', flush=True)
    # --- quem e esta base, segundo ela propria
    # `BASE.DIST` e o codigo ANEEL da distribuidora, e esta em todas as sete
    # bases conferidas. E dado, nao inferencia pelo nome do arquivo.
    dist_base = ''
    try:
        _bs = b.ler('BASE', ['DIST'])
        dist_base = txt(_bs['DIST'][0]).strip()
    except Exception:
        pass
    log(f'  distribuidora declarada na BASE: {dist_base or "(ausente)"}')

    # --- tensoes de BT vindas do censo DESTA base (achado 5)
    bt_da_base = tensoes.censo_bt(b, log)

    clima = complementos.carregar_clima(a.clima, a.mes, log, dist_base,
                                        a.clima_dist, a.clima_forcar)
    clima_fonte = ('medido_forcado' if (clima and a.clima_forcar
                                        and dist_base != str(a.clima_dist))
                   else 'medido' if clima else 'sintetico')
    nomes_curva, _irr, _cel = complementos.curvas(
        b, os.path.join(tmp, 'Curvas.dss'), a.dia, clima)
    fc_gd = complementos.fc_efetivo(_irr, _cel)
    print(f'  fator de capacidade da curva solar: {fc_gd:.4f} '
          f'(pmpp = {1/fc_gd:.2f}x a potencia media)', flush=True)
    complementos.xycurves(os.path.join(tmp, '_XYCURVES.dss'))
    print(f'  {len(nomes_curva)} curvas de carga ({a.dia})', flush=True)
    globais = [f'_global/{x}' for x in ('LineCodes.dss', 'Curvas.dss', '_XYCURVES.dss')]

    # --- alta tensao (uma vez, compartilhada pelas subestacoes geradas)
    # inclui as ja prontas: elas continuam no MASTER-GERAL, entao os seus
    # patios de AT precisam existir mesmo numa execucao de retomada.
    subs_alvo = set(alvo) | set(prontas)
    arq_at, est_at, info_tr, vaos_lig, est_fontes = ([], {}, None, {}, {})
    if not a.sem_at:
        arq_at, est_at, info_tr, vaos_lig, est_fontes = gerar_at(
            b, a, ctmt_info, mapa_cnd, log, subs_alvo)

    # --- agregacao da carga de BT: UMA varredura para todas as SEs
    agregado = None
    if a.bt == 'agregado':
        todos_ctmt = [c for s in alvo for c in ses.get(s, [])]
        print(f'Agregando carga de BT de {len(todos_ctmt)} alimentadores '
              f'({b.n_registros("UCBT_tab"):,} UCs)...', flush=True)
        import pickle
        cache = os.path.join(a.saida, f'{a.cache}.mes{a.mes:02d}')
        if os.path.exists(cache):
            agregado = pickle.load(open(cache, 'rb'))
            print(f'  cache reaproveitado: {len(agregado):,} transformadores', flush=True)
        else:
            agregado = cargas._agrega_bt(b, todos_ctmt, a.mes)
            pickle.dump(dict(agregado), open(cache, 'wb'))
            print(f'  {len(agregado):,} transformadores com carga (cache salvo)', flush=True)

    resumo = []
    # Subestacoes processadas em lote. O WHERE do GDAL nao tem indice, entao
    # cada leitura filtrada varre a camada inteira: trazer 49 linhas do SSDMT
    # custa os mesmos 13 s de trazer 6.927. Um lote de 10 subestacoes custa
    # 19 s onde 10 leituras separadas custam 135. Sem isto, ~45 dos ~75 min da
    # rodada eram revarredura de tabela.
    feitas = []
    for k, se in enumerate(alvo, 1):
        if CANCELAR is not None and CANCELAR.is_set():
            print('Cancelado pelo usuario.', flush=True)
            break
        if (k - 1) % a.lote == 0:
            grupo = alvo[k - 1:k - 1 + a.lote]
            b.abrir_lote([c for s in grupo for c in ses.get(s, [])])
        ctmts = ses.get(se, [])
        if not ctmts:
            continue
        d = os.path.join(a.saida, se)
        os.makedirs(d, exist_ok=True)
        print(f'[{k}/{len(alvo)}] {se} — {len(ctmts)} alimentadores', flush=True)

        for f in ('Curvas.dss', '_XYCURVES.dss'):
            open(os.path.join(d, f), 'w', encoding='utf-8').write(
                open(os.path.join(tmp, f), encoding='utf-8').read())
        # LineCodes fica para o fim do bloco: so os que esta SE referencia.

        col_mt = b.ler_filtrado('SSDMT', 'CTMT', ctmts,
                                ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON',
                                 'TIP_CND', 'COMP'])
        n_ln, km, barras = linhas.gerar(b, mapa_cnd, ctmts, os.path.join(d, 'Linhas.dss'),
                                        'SSDMT', col=col_mt)
        # `barras` vem da rede de MT acima: chave cujos dois PACs estao fora
        # dela cria ilha flutuante, e o NaN dela contamina a perda da
        # subestacao inteira (achado 28)
        n_ch, abertas, ch_ilhadas = chaves.gerar(
            b, ctmts, os.path.join(d, 'Chaves.dss'),
            os.path.join(d, 'Controles.dss'), barras=barras)
        n_tr, sec = transformadores.gerar(b, ctmts, os.path.join(d, 'Trafos.dss'),
                                          os.path.join(d, '_ATERRAMENTO.dss'),
                                          a.kv_mt, kv_por_ctmt)
        # Conjunto de pontos de conexao que a rede realmente tem. Um shunt
        # (carga, banco, PVSystem) num PAC ausente daqui cria a barra sozinho,
        # a ilha fica sem fonte e a solucao devolve NaN — foi o que travava a
        # DBSI em 100 iteracoes.
        barras_rede = set(barras) | set(sec)
        barras_bt = set()          # so o --bt completo a preenche

        n_cp = complementos.capacitores(b, ctmts, os.path.join(d, 'Capacitores.dss'),
                                        a.kv_mt, kv_por_ctmt, barras=barras_rede)
        n_rg = complementos.reguladores(b, ctmts, os.path.join(d, 'Reguladores.dss'),
                                        a.kv_mt, kv_por_ctmt,
                                        a.reg_vreg, a.reg_band, a.reg_kva,
                                        barras=barras_rede)
        if a.bt == 'completo':
            info = cargas.gerar(b, ctmts, sec, os.path.join(d, 'Cargas.dss'), a.mes,
                                nomes_curva, a.fator_carga,
                                agregado_bt=collections.defaultdict(
                                    lambda: {'ene': 0.0, 'cur': collections.Counter(), 'n': 0}),
                                kv_por_ctmt=kv_por_ctmt, kv_mt_padrao=a.kv_mt,
                                barras=barras_rede)
            ibt = cargas.gerar_bt_completa(b, ctmts, sec,
                                           os.path.join(d, 'CargasBT.dss'), a.mes,
                                           nomes_curva, a.fator_carga)
            info['n_cargas'] += ibt['n_cargas_bt']
            info['kW_BT'] = ibt['kW_BT']
            # A cadeia real e trafo -> SSDBT -> RAMLIG -> UC. Sem o ramal de
            # ligacao, 97% das unidades consumidoras ficam soltas: o PAC da
            # UCBT e a ponta do RAMLIG, nao um no da rede secundaria.
            n_bt, km_bt, bb_bt = linhas.gerar_bt(b, mapa_cnd, ctmts,
                                                 os.path.join(d, 'LinhasBT.dss'), 'SSDBT')
            n_rm, km_rm, bb_rm = linhas.gerar_bt(b, mapa_cnd, ctmts,
                                                 os.path.join(d, 'Ramais.dss'), 'RAMLIG')
            info['linhas_BT'] = n_bt + n_rm
            info['km_BT'] = round(km_bt + km_rm, 2)
            # guardadas em separado: a GD de BT precisa saber o que e barra DE
            # BT, e nao apenas o que e barra (achado 30)
            barras_bt = set(bb_bt) | set(bb_rm)
            barras_rede |= barras_bt
        else:
            info = cargas.gerar(b, ctmts, sec, os.path.join(d, 'Cargas.dss'), a.mes,
                                nomes_curva, a.fator_carga, agregado,
                                kv_por_ctmt, a.kv_mt, barras=barras_rede)

        # a GD vem depois da rede de BT: com --bt completo o PAC da UGBT so
        # existe depois que SSDBT e RAMLIG foram escritos
        (n_gd, gd_nulos, gd_realoc, gd_fora, gd_lim, gd_kw_cortado,
         gd_por_ceg) = complementos.geracao(
            b, ctmts, sec, os.path.join(d, 'GD.dss'), a.kv_mt,
            barras=barras_rede, barras_bt=barras_bt,
            irradiancia=a.irradiancia, fp=a.gd_fp,
            mes=a.mes, fc=fc_gd)

        # vaos desta subestacao: ligam a barra de MT as cabeceiras
        vaos_se = (est_at.get('vaos_por_se') or {}).get(se, [])
        if vaos_se:
            subtransmissao.escrever_vaos(os.path.join(d, 'Vaos.dss'), vaos_se)

        # LineCodes: so os referenciados por esta subestacao. O arquivo global
        # tem 10.500 definicoes e cada SE usa mediana de 152 — copia-lo
        # inteiro gerava 215 MB de conteudo identico nas 155 pastas.
        n_lc_se = linecodes.escrever_usados(os.path.join(tmp, 'LineCodes.dss'),
                                            os.path.join(d, 'LineCodes.dss'), d)

        # --- arquivos da subestacao, na ordem de montagem
        arqs = ['_XYCURVES.dss', 'LineCodes.dss', 'Curvas.dss', 'Linhas.dss']
        if a.bt == 'completo':
            arqs += ['LinhasBT.dss', 'Ramais.dss']
        arqs += ['Chaves.dss', 'Controles.dss', 'Trafos.dss', '_ATERRAMENTO.dss',
                 'Reguladores.dss', 'Capacitores.dss', 'Vaos.dss', 'Cargas.dss']
        if a.bt == 'completo':
            arqs.append('CargasBT.dss')
        arqs.append('GD.dss')
        arqs = [x for x in arqs if os.path.exists(os.path.join(d, x))]

        ab = ['! Chaves normalmente abertas — estado fixado apos a montagem.']
        ab += [f'Open Line.{n} 1' for n in abertas]
        open(os.path.join(d, '_CHAVES_ABERTAS.dss'), 'w',
             encoding='utf-8').write('\n'.join(ab) + '\n')

        # coordenadas geograficas desta subestacao
        co = coordenadas.coletar(b, 'SSDMT', ctmts)
        if a.bt == 'completo':
            coordenadas.coletar(b, 'SSDBT', ctmts, co)
            coordenadas.coletar(b, 'RAMLIG', ctmts, co)
        n_co_se = coordenadas.escrever(co, os.path.join(d, 'BusCoords.dat'))

        master.rede_se(se, arqs, os.path.join(d, f'REDE-{se}.dss'))

        # MASTER isolado: fonte na barra de MT desta subestacao
        kvs = {ctmt_info[c]['kv'] for c in ctmts}
        kv_se = max(kvs) if kvs else a.kv_mt
        # Uma fonte por BARRA de MT: a subestacao pode ter mais de um nivel
        # de tensao (a TBAN tem 20 kV e 34,5 kV em barras distintas).
        # Barra derivada (alimentador cuja tensao difere da barra da SE) fica
        # de fora: quem a energiza e o transformador de barra escrito no
        # Vaos.dss, nao uma fonte propria. Duas fontes na mesma barra com
        # tensoes diferentes foi o que matou 2.238 cargas da TBAN.
        # A TENSAO DE CABECEIRA TEM DE SER A MESMA NOS DOIS MODELOS.
        #
        # No modelo GERAL quem sustenta a barra de MT e o transformador de AT,
        # com `tap` = mediana de CTMT.TEN_OPE dos alimentadores da subestacao.
        # No modelo ISOLADO nao ha esse transformador: a fonte o substitui, e
        # portanto tem de reproduzir o mesmo pu.
        #
        # Nao reproduzia. O pu saia daqui por dois caminhos diferentes — o
        # `setdefault` abaixo, que faz vencer o PRIMEIRO alimentador da
        # iteracao, e o `1.0` embutido no ramo de fallback. Medido: 5 das 150
        # subestacoes com trafo de AT ficavam com pu diferente do tap, e a
        # diferenca era sempre 0,09 pu — que e exatamente a distancia entre
        # operar a 1,09 e operar a 1,00.
        #
        # A DALP e uma delas, e foi por isso que uma equipe externa relatou
        # subtensao generalizada nela: abriram o modelo isolado, que dizia
        # 1,00, enquanto o geral dizia 1,09. Nove pontos percentuais de
        # tensao de cabeceira separando dois arquivos da mesma subestacao.
        tap_se = (est_at.get('tap_por_se') or {}).get(se)
        barras_se = {}
        for c in ctmts:
            if c in vaos_lig and not vaos_lig[c].get('derivada'):
                b_ = vaos_lig[c]['barra']
                barras_se.setdefault(b_, (vaos_lig[c]['kv'],
                                          tap_se or ctmt_info[c]['ten_ope']))
        if not barras_se:
            barras_se = {subtransmissao._no(ctmt_info[ctmts[0]]['pac_ini']):
                         (kv_se, tap_se or 1.0)}
        itens = sorted(barras_se.items(), key=lambda x: -x[1][0])
        barra_se, (kv_se, pu_se) = itens[0]
        extras = [(b_, kv_, pu_) for b_, (kv_, pu_) in itens[1:]]
        mvasc = (est_at.get('mvasc_por_se') or {}).get(se) or transmissao.MVASC_PADRAO
        master.gerar_se(se, os.path.join(d, f'MASTER-{se}.dss'), barra_se, kv_se,
                        len(ctmts), len(barras), mvasc,
                        ['LineCodes.dss', 'Curvas.dss', '_XYCURVES.dss'],
                        list(kvs) + [a.kv_at],
                        pu=pu_se, barras_extra=extras, bt=bt_da_base,
                        buscoords='Buscoords BusCoords.dat',
                        bloco_medicao=master.medicao(
                            [c for c in ctmts if c in vaos_lig], [], []))

        r = {'SE': se, 'alimentadores': len(ctmts),
             'com_vao': sum(1 for c in ctmts if c in vaos_lig),
             'kv_mt': kv_se, 'barra_mt': barra_se,
             'barras_mt': len(barras_se),
             'linhas': n_ln, 'km_MT': km, 'barras': len(barras), 'chaves': n_ch,
             'chaves_abertas': len(abertas),
             'chaves_ilhadas': len(ch_ilhadas), 'trafos': n_tr,
             'capacitores': n_cp,
             'reguladores': n_rg, 'GD': n_gd, 'GD_nulos': gd_nulos,
             'GD_realocada': gd_realoc, 'GD_fora_da_rede': gd_fora,
             'GD_barras_limitadas': gd_lim, 'GD_kW_cortado': gd_kw_cortado,
             'GD_MT_por_CEG_GD': gd_por_ceg,
             'mes': a.mes, 'dia': a.dia, 'fator_carga': a.fator_carga,
             'bt': a.bt, 'coords': n_co_se,
             # capacidade instalada de AT: o classificador de causa usa isso
             # para separar "rede carregada" de "modelo com defeito"
             'mva_at': round((info_tr or {}).get('mva_por_sub', {}).get(se, 0), 1)
             if info_tr else 0,
             **info}
        json.dump(r, open(os.path.join(d, 'resumo.json'), 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False)
        resumo.append(r)
        feitas.append(se)

        del col_mt, sec, barras
        gc.collect()
        mem = memoria_gb()
        if a.memoria_max and mem > a.memoria_max:
            print(f'\nMemoria em {mem:.2f} GB, acima do limite de {a.memoria_max:.2f} GB. '
                  f'Parando de forma limpa.', flush=True)
            print(f'As {len(resumo)} subestacoes concluidas estao salvas. '
                  f'Rode o mesmo comando de novo — ele retoma da proxima.', flush=True)
            break
        # `n_ln` e so a MT. Com `--bt completo` o modelo ganha LinhasBT e
        # Ramais — medido na 5003525 de Roraima, 6.277 -> 24.267 linhas —, e
        # imprimir so a MT fazia os dois modos parecerem identicos no log.
        _lbt = info.get('linhas_BT') or 0
        print(f'   {n_ln:,} linhas MT'
              f'{f" + {_lbt:,} BT" if _lbt else ""} | {n_tr:,} trafos | '
              f'{info["n_cargas"]:,} cargas | '
              f'{info["kW_BT"]+info["kW_MT"]:,.0f} kW', flush=True)

    b.fechar_lote()

    # --- MASTER geral, com tudo que existe na pasta
    if not a.sem_at:
        todas = sorted(s for s in ses
                       if os.path.exists(os.path.join(a.saida, s, f'REDE-{s}.dss')))
        est_at['n_ctmt'] = sum(len(ses[s]) for s in todas)
        # as bases precisam cobrir TODO nivel presente no modelo. Faltando
        # um, o CalcVoltagebases escolhe o mais proximo e a tensao em pu sai
        # errada por um fator inteiro — 34,5 kV lido como 13,8 da 2,5 pu.
        niveis = {ctmt_info[c]['kv'] for s in todas for c in ses[s]}
        niveis |= {a.kv_at, 138.0}
        if info_tr:
            niveis |= set(info_tr['kv_da_barra'].values())
        niveis |= set(est_at.get('niveis_transmissora') or [])
        niveis = sorted(niveis)
        aberturas = ['_AT/_CHAVES_ABERTAS_AT.dss']
        aberturas += [f'{s}/_CHAVES_ABERTAS.dss' for s in todas]
        aberturas = [x for x in aberturas if os.path.exists(os.path.join(a.saida, x))]
        vaos_todos = [c for s_ in todas for c in ses[s_]
                      if c in (vaos_lig or {})]
        bloco = master.medicao(vaos_todos, est_at.get('trafos_at_nomes') or [],
                               sorted(est_at.get('linhas_at_nomes') or []))
        bc = ['Buscoords _AT/BusCoords_AT.dat']
        bc += [f'Buscoords {s_}/BusCoords.dat' for s_ in todas
               if os.path.exists(os.path.join(a.saida, s_, 'BusCoords.dat'))]
        master.gerar_geral(os.path.join(a.saida, 'MASTER-GERAL.dss'), a.gdb,
                           todas, arq_at, globais, est_at, niveis, aberturas,
                           bloco_medicao=bloco, buscoords=os.linesep.join(bc),
                           bt=bt_da_base)
        print(f'\nMASTER-GERAL.dss escrito com {len(todas)} subestacoes.', flush=True)

        # --- MASTER-AT: a metade de cima da decomposicao (achado 13)
        # O MASTER-GERAL da Enel SP tem 2,39 milhoes de elementos e nao cabe
        # em 15,8 GB. Este tem ~19.500 — menos de 1% — porque as subestacoes
        # entram como carga equivalente na barra de MT, em vez de com a rede
        # inteira delas. E o unico modelo que CALCULA a tensao de cabeceira,
        # que nos modelos por subestacao e declarada.
        #
        # Le os resumo.json do disco, e nao a lista `resumo` da memoria, para
        # incluir tambem as subestacoes que ja estavam prontas de uma execucao
        # anterior — do contrario uma conversao retomada geraria um MASTER-AT
        # com metade da concessao e ninguem notaria.
        ses_at = []
        for s_ in todas:
            fr = os.path.join(a.saida, s_, 'resumo.json')
            if not os.path.exists(fr):
                continue
            try:
                with open(fr, encoding='utf-8') as fh:
                    ses_at.append(json.load(fh))
            except Exception:
                pass
        n_se_at, mw_at = master.gerar_at(
            os.path.join(a.saida, 'MASTER-AT.dss'), arq_at, ses_at, niveis,
            buscoords='Buscoords _AT/BusCoords_AT.dat', bt=bt_da_base,
            arquivos_globais=globais)
        print(f'MASTER-AT.dss escrito: {n_se_at} subestacoes como carga '
              f'equivalente, {mw_at:,.0f} MW.', flush=True)

    rel = {'gdb': os.path.basename(a.gdb),
           'dist': dist_base,
           'clima_fonte': clima_fonte,
           'clima_dist': str(a.clima_dist),
           'tensoes_bt_da_base': bt_da_base,
           'subestacoes_na_bdgd': len(ses),
           'subestacoes_geradas': len(resumo) + len(prontas),
           'alimentadores': len(ctmt_info),
           'bt': a.bt, 'mes': a.mes, 'dia': a.dia,
           'fator_carga': a.fator_carga,
           'codigos_tensao_desconhecidos': tensoes.desconhecidos(),
           'condutores_r1_corrigido': corr_cnd,
           'alta_tensao': est_at,
           'subestacoes': resumo}
    json.dump(rel, open(os.path.join(a.saida, 'relatorio_rede.json'), 'w',
                        encoding='utf-8'), indent=1, ensure_ascii=False)
    json.dump(resumo, open(os.path.join(a.saida, 'resumo_geral.json'), 'w',
                           encoding='utf-8'), indent=1, ensure_ascii=False)

    if tensoes.desconhecidos():
        print(f'\nCodigos de tensao sem valor definido: '
              f'{", ".join(tensoes.desconhecidos())} — usaram o padrao. '
              f'Preencha em bdgd2dss/tensoes.py se souber os valores.', flush=True)
    print(f'\nFIM — {len(resumo)} subestacoes em {(time.time()-t0)/60:.1f} min', flush=True)


if __name__ == '__main__':
    main()
