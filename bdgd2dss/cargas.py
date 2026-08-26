# -*- coding: utf-8 -*-
"""
UCBT_tab -> New Load (agregada por transformador)
UCMT_tab -> New Load (individual, no PAC do consumidor)

A energia mensal (ENE_01..12) dividida por 730 h da a demanda media; a curva
de carga (LoadShape) faz o resto, pois vem normalizada pela propria media.

As cargas de BT sao agregadas por transformador e divididas entre as pernas
existentes do secundario. Modelar cada uma das 8,26 milhoes de UCs
individualmente multiplicaria o modelo por ~40 sem mudar o carregamento do
alimentador, que e o objetivo.

Model=8 (ZIPV) com o mesmo vetor usado pela distribuidora:
    50% impedancia constante + 50% potencia constante em P,
    100% impedancia constante em Q.

O CUTOFF TEM DE SER ZERO
------------------------
O ultimo termo do vetor ZIPV e a tensao abaixo da qual o OpenDSS deixa de
aplicar o polinomio. Qualquer valor maior que zero quebra o modelo no motor
oficial da EPRI.

Primeiro achado: com o valor usual de 0,5 pu, toda barra que se estabiliza
perto de 0,5 entra em ciclo-limite — a carga desliga, a tensao sobe, a carga
religa, a tensao cai, e o fluxo nunca converge. Eram 25 das 155 subestacoes;
na DVMA, exatamente DOIS nos oscilando entre 0,4623 e 0,4653 pu bastavam para
estourar as 100 iteracoes. Baixar para 0,25 resolveu no DSS C-API.

Segundo achado, mais grave: no OpenDSS v11.0.0.1 (COM da EPRI, que e o motor
que o usuario abre e que a analise_com usa), o ramo abaixo do cutoff devolve
NaN em vez de zerar a injecao. Como sempre ha barras colapsadas — na DALP o
minimo e 0,071 pu — o NaN aparece, contamina a fatoracao e derruba a rede
inteira. Medido na DALP, variando um termo por vez:

    cutoff 0,25 / 0,50 / 0,80        49.821 nos NaN, nao converge em 100 it
    cutoff 0,00                           0 nos NaN, converge em 5 it
    Z puro, P puro, I puro (cutoff 0,25)  49.821 nos NaN

Os coeficientes nao importam; so o cutoff. E o DSS C-API resolvia o mesmo
arquivo com 36 NaN contidos numa ilha, o que escondeu o defeito do validador.

Com cutoff zero o polinomio vale em toda a faixa. A parcela de impedancia
constante (50% de P e 100% de Q) domina em tensao baixa e limita a corrente,
que era a funcao do cutoff.
"""
import collections
from .leitor import num, txt, no, pertence as leitor_pertence
from . import escrita

HORAS = 730.0
FASES = {'A': '1', 'B': '2', 'C': '3'}
ZIPV = '(0.5,0,0.5,1,0,0,0)'      # cutoff ZERO — ver o cabecalho: >0 da NaN no v11


def _agrega_bt(bdgd, ctmts, mes):
    """Soma a energia das UCs por (transformador). Uma varredura na tabela."""
    cols = ['CTMT', 'UNI_TR_MT', 'TIP_CC', f'ENE_{mes:02d}']
    acc = collections.defaultdict(lambda: {'ene': 0.0, 'cur': collections.Counter(), 'n': 0})
    alvo = set(ctmts)
    import numpy as np
    for col, lido, total in bdgd.ler_em_fatias('UCBT_tab', cols):
        # `pertence` em vez de `np.isin` cru: os dois lados podem ter largura
        # de string diferente entre fatias, e ai o numpy levanta UFuncNoLoop.
        mask = leitor_pertence(col['CTMT'], alvo)
        idx = np.nonzero(mask)[0]
        if len(idx):
            ene = np.nan_to_num(col[f'ENE_{mes:02d}'][idx].astype(float))
            for j, i in enumerate(idx):
                d = acc[txt(col['UNI_TR_MT'][i])]
                d['ene'] += ene[j]; d['n'] += 1
                d['cur'][txt(col['TIP_CC'][i])] += 1
        bdgd.log(f'    UCBT: {lido:,}/{total:,}')
    return acc


def _agrega_pip(bdgd, ctmts, mes):
    """Soma a energia da ILUMINACAO PUBLICA por transformador.

    A PIP e carga de verdade e estava ficando de fora. Medida a energia do
    mes 01 nas sete bases, ela vale de 1,24% (Enel SP) a 4,80% (Enel CE)
    de tudo que a distribuidora entrega, com 5,8 milhoes de pontos somados.

    Vai em carga SEPARADA, e nao somada a agregacao da BT, por causa da
    curva: `TIP_CC` da PIP e `IP-Tipo1` em 100% dos registros da Enel CE, e
    a curva de iluminacao e quase nula de dia e cheia de noite. Somada a
    BT, a energia dela seguiria o perfil residencial, que e o contrario.
    A curva ja existe no Curvas.dss: ela vem da CRVCRG como as outras.

    O `UNI_TR_MT` esta preenchido em 439.142 de 439.142 registros da Enel
    CE, entao a juncao pelo transformador nao perde nada.
    """
    cols = ['CTMT', 'UNI_TR_MT', 'TIP_CC', f'ENE_{mes:02d}']
    acc = collections.defaultdict(
        lambda: {'ene': 0.0, 'cur': collections.Counter(), 'n': 0})
    alvo = set(ctmts)
    import numpy as np
    try:
        fatias = list(bdgd.ler_em_fatias('PIP', cols))
    except Exception:
        return acc            # base sem PIP segue sem iluminacao publica
    for col, lido, total in fatias:
        mask = leitor_pertence(col['CTMT'], alvo)
        idx = np.nonzero(mask)[0]
        if len(idx):
            ene = np.nan_to_num(col[f'ENE_{mes:02d}'][idx].astype(float))
            for j, k in enumerate(idx):
                d = acc[txt(col['UNI_TR_MT'][k])]
                d['ene'] += ene[j]; d['n'] += 1
                d['cur'][txt(col['TIP_CC'][k])] += 1
    return acc


# A curva que a Enel SP usa como residencial tipica. Ela NAO e garantia: e o
# palpite historico, e so vale se a propria base a tiver publicado.
PADRAO_HISTORICO = 'RES-Tipo02'


def curva_padrao(curvas_validas, uso=None):
    """A curva de fallback SAI DA BASE, e nao de uma constante.

    O codigo antigo caia em `RES-Tipo02` sempre que o `TIP_CC` da UC nao
    estivesse entre as curvas validas — sem nunca conferir se a propria
    `RES-Tipo02` existia. Nas sete bases do projeto ela existe; em 49 das 97
    do pais, nao.

    O MECANISMO E MAIS FINO DO QUE PARECE, e por isso o defeito sobreviveu a
    dezenove rodadas. Medido em 25/08/2026:

        base          LoadShapes geradas   tem RES-Tipo02   resultado
        Cocel                        59             nao      PASSOU
        Castro-Dis                    1             nao      falhou

    A Cocel tambem nao tem a curva E FUNCIONA, porque as UCs dela acham a
    propria entre as 59 e o fallback nunca e alcancado. A Castro-Dis tem uma
    curva so, entao quase toda UC cai nele. **O fallback so e alcancado quando
    o catalogo da base e pobre — e e exatamente ai que ele proprio falta.**

    Sem curva, o `energia.py` morre com `LoadShape object not found`, o
    `energia_dia.json` sai com `alimentadores: {}` e nada casa na validacao:
    49 bases converteram e nao puderam ser validadas.

    `uso` e a contagem de consumidores por curva NA PROPRIA BASE. A mais usada
    ganha, porque e a que melhor representa quem nao declarou.

    Devolve `None` quando a base nao publicou curva nenhuma — e ai a carga sai
    SEM `Daily`, que e melhor que apontar para uma curva inexistente.
    """
    curvas_validas = curvas_validas or set()
    if uso:
        for nome, _ in uso.most_common():
            if nome in curvas_validas:
                return nome
    if PADRAO_HISTORICO in curvas_validas:
        return PADRAO_HISTORICO
    return sorted(curvas_validas)[0] if curvas_validas else None


def _daily(curva):
    """` Daily=X` ou nada. Base sem curva gera carga plana, e nao erro."""
    return f' Daily={curva}' if curva else ''


def gerar(bdgd, ctmts, sec, caminho_saida, mes=1, curvas_validas=None,
          fator=1.0, agregado_bt=None, kv_por_ctmt=None, kv_mt_padrao=13.8,
          barras=None, agregado_pip=None):
    """Escreve as cargas. `fator` permite escalar a demanda (util para o
    NSGA-II, ao gerar cenarios de estresse de ampacidade).

    `kv_por_ctmt` da a tensao de cada alimentador. Antes a MT era fixada em
    13,8 kV para toda a concessao, o que estava errado nos 122 alimentadores
    que operam em 20 kV (codigo 59) ou 34,5 kV (codigo 72).

    `barras` bloqueia a carga de MT cujo PAC nao existe na rede: ela criaria a
    barra sozinha e a ilha sem fonte devolve NaN."""
    curvas_validas = curvas_validas or set()
    kv_por_ctmt = kv_por_ctmt or {}
    bt = agregado_bt if agregado_bt is not None else _agrega_bt(bdgd, ctmts, mes)

    out = ['! ==========================================================',
           f'! CARGAS — mes {mes:02d}',
           '! BT: UCBT_tab agregada por transformador (kW = ENE/730 h)',
           '! MT: UCMT_tab individual no PAC do consumidor',
           '! IP: PIP agregada por transformador, com curva propria',
           f'! fator de escala aplicado: {fator:g}',
           '! ==========================================================']
    tot_bt = tot_mt = 0.0
    n = fora = 0
    # A curva de recurso sai da PROPRIA BASE: soma o uso declarado por todos os
    # transformadores e pega a mais frequente que exista de verdade. O
    # contador ja esta em memoria — nao custa leitura nenhuma.
    uso = collections.Counter()
    for d in bt.values():
        uso.update(d['cur'] or {})
    recurso = curva_padrao(curvas_validas, uso)
    for cod, d in bt.items():
        s = sec.get(cod)
        if not s:
            continue
        kw = d['ene'] / HORAS * fator
        if kw <= 0.001:
            continue
        curva = d['cur'].most_common(1)[0][0] if d['cur'] else None
        if curva not in curvas_validas:
            curva = recurso
        pernas = s['nos'] or ['1']
        # a barra e a do secundario do trafo, nao o codigo do trafo
        bus = s.get('barra', cod)
        kwf = kw / len(pernas)
        for f in pernas:
            out.append(f'New Load.BT_{cod}_{f} Bus1={bus}.{f}.4 Phases=1 Model=8 '
                       f'zipv={ZIPV} kv={s["kv_fn"]:.4f} pf=0.92 kW={kwf:.6f}{_daily(curva)}')
            n += 1
        tot_bt += kw

    # --- media tensao
    cols = ['CTMT', 'PAC', 'FAS_CON', 'TIP_CC', f'ENE_{mes:02d}']
    col = bdgd.ler_filtrado('UCMT_tab', 'CTMT', ctmts, cols)
    # ILUMINACAO PUBLICA: carga propria, curva propria. Ver `_agrega_pip`.
    ip = agregado_pip if agregado_pip is not None else _agrega_pip(
        bdgd, ctmts, mes)
    tot_ip = 0.0
    n_ip = 0
    if ip:
        out.append('')
        out.append('! --- iluminacao publica (PIP), agregada por trafo ---')
    for cod, d in ip.items():
        s = sec.get(cod)
        if not s:
            continue
        kw = d['ene'] / HORAS * fator
        if kw <= 0.001:
            continue
        curva = d['cur'].most_common(1)[0][0] if d['cur'] else 'IP-Tipo1'
        if curva not in curvas_validas:
            curva = recurso
        pernas = s['nos'] or ['1']
        bus = s.get('barra', cod)
        kwf = kw / len(pernas)
        for f in pernas:
            out.append(f'New Load.IP_{cod}_{f} Bus1={bus}.{f}.4 Phases=1 '
                       f'Model=8 zipv={ZIPV} kv={s["kv_fn"]:.4f} pf=0.92 '
                       f'kW={kwf:.6f}{_daily(curva)}')
            n_ip += 1
        tot_ip += kw

    out.append('\n! --- cargas de media tensao (UCMT_tab) ---')
    # `MT-Tipo02` era a constante daqui, e cai no mesmo defeito da BT: e nome
    # da Enel SP e nao ha garantia de que a base o publique. O recurso sai do
    # uso real dos consumidores de MT desta base.
    uso_mt = collections.Counter(txt(v) for v in col['TIP_CC'])
    recurso_mt = curva_padrao(curvas_validas, uso_mt)
    for i in range(len(col['CTMT'])):
        kw = num(col[f'ENE_{mes:02d}'][i]) / HORAS * fator
        if kw <= 0.001:
            continue
        pac = no(col['PAC'][i])
        if not pac:
            continue
        if barras is not None and pac not in barras and pac not in sec:
            fora += 1
            continue
        fs = [FASES[c] for c in txt(col['FAS_CON'][i], 'ABC').upper() if c in FASES] or ['1', '2', '3']
        curva = txt(col['TIP_CC'][i])
        if curva not in curvas_validas:
            curva = recurso_mt
        kv_ct = kv_por_ctmt.get(txt(col['CTMT'][i]), kv_mt_padrao)
        kv = kv_ct if len(fs) >= 3 else kv_ct / (3 ** 0.5)
        out.append(f'New Load.MT_{pac}_{i} Bus1={pac}.{".".join(fs)} Phases={len(fs)} '
                   f'Conn=wye Model=8 zipv={ZIPV} kv={kv:.4f} pf=0.92 '
                   f'kW={kw:.4f}{_daily(curva)}')
        tot_mt += kw
        n += 1

    out.insert(5, f'! {fora} cargas de MT descartadas por PAC ausente da rede.')
    open(caminho_saida, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    return {'n_cargas': n, 'kW_BT': round(tot_bt, 1), 'kW_MT': round(tot_mt, 1),
            'mt_fora_da_rede': fora}


def gerar_bt_completa(bdgd, ctmts, sec, caminho_saida, mes=1,
                      curvas_validas=None, fator=1.0):
    """Cada UC de BT no seu proprio PAC, em vez de agregada no trafo.

    Quando usar: so quando o estudo for de TENSAO DE ATENDIMENTO. O
    equivalente agregado nao ve a queda no secundario e no ramal, que e
    exatamente onde a violacao do Modulo 8 costuma aparecer.

    Quando NAO usar: carregamento de alimentador, criticidade, NSGA-II. Aqui
    o agregado da o mesmo resultado num modelo ~40 vezes menor, porque a BT
    e curta e radial e a MT nao distingue as duas representacoes.

    Custo: sao 8,26 milhoes de UCs na concessao. Por subestacao e viavel;
    para as 155 de uma vez, nao.
    """
    curvas_validas = curvas_validas or set()
    cols = ['COD_ID', 'PAC', 'UNI_TR_MT', 'CTMT', 'FAS_CON', 'TIP_CC',
            f'ENE_{mes:02d}']
    col = bdgd.ler_filtrado('UCBT_tab', 'CTMT', ctmts, cols)
    out = ['! ==========================================================',
           f'! CARGAS DE BT INDIVIDUAIS — mes {mes:02d}',
           '! Uma Load por unidade consumidora, no PAC real (nao agregada).',
           '! Exige a rede de BT montada (LinhasBT.dss) para fazer sentido.',
           '! ==========================================================']
    n = 0
    tot = 0.0
    sem_rede = 0
    # `COD_ID` DA UCBT_tab NAO E UNICO, e o OpenDSS ABORTA quando descobre:
    #
    #     DSSException: (#266) Duplicate new element definition:
    #                   "Load.UC_e6446f51...._3". Element being redefined.
    #
    # Medido na Cemig-D em 25/08/2026, subestacao 1726782: o `--bt completo`
    # nao chegava a resolver. O erro nao e do OpenDSS — e a BDGD trazendo duas
    # linhas com o mesmo codigo de unidade consumidora.
    #
    # A saida NAO e descartar a segunda: isso perderia energia declarada, em
    # silencio, e o modelo passaria a entregar menos do que a base diz. Cada
    # ocorrencia ganha sufixo e TODAS entram; a contagem sai no cabecalho do
    # arquivo para o defeito de dado ficar visivel em vez de remendado.
    #
    # O sufixo e deterministico porque a ordem de leitura e: o mesmo `.gdb`
    # gera o mesmo arquivo byte a byte, que e requisito do projeto.
    vistos = collections.Counter()
    repetidos = 0
    # Mesmo recurso da agregada: a curva mais usada que EXISTE nesta base.
    recurso = curva_padrao(curvas_validas,
                           collections.Counter(txt(v) for v in col['TIP_CC']))
    for i in range(len(col['COD_ID'])):
        kw = num(col[f'ENE_{mes:02d}'][i]) / HORAS * fator
        if kw <= 0.001:
            continue
        pac = no(col['PAC'][i])
        if not pac:
            continue
        s = sec.get(txt(col['UNI_TR_MT'][i]))
        if not s:
            sem_rede += 1
            continue
        fs = [FASES[c] for c in txt(col['FAS_CON'][i], 'A').upper() if c in FASES] or ['1']
        curva = txt(col['TIP_CC'][i])
        if curva not in curvas_validas:
            curva = recurso
        kwf = kw / len(fs)
        for f in fs:
            nome = f'UC_{txt(col["COD_ID"][i])}_{f}'
            vistos[nome] += 1
            if vistos[nome] > 1:
                nome = f'{nome}__{vistos[nome]}'
                repetidos += 1
            out.append(f'New Load.{nome} '
                       f'Bus1={pac}.{f}.4 Phases=1 Model=8 zipv={ZIPV} '
                       f'kv={s["kv_fn"]:.4f} pf=0.92 kW={kwf:.6f}{_daily(curva)}')
            n += 1
        tot += kw
    if sem_rede:
        out.insert(4, f'! {sem_rede} UCs sem transformador conhecido — omitidas.')
    if repetidos:
        out.insert(4, f'! {repetidos} cargas com COD_ID repetido na UCBT_tab: '
                      f'sufixo __N para nao colidir. Nenhuma foi descartada.')
    open(caminho_saida, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    return {'n_cargas_bt': n, 'kW_BT': round(tot, 1), 'sem_trafo': sem_rede,
            'cod_id_repetido': repetidos}
