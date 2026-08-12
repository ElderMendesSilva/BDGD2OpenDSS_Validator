# -*- coding: utf-8 -*-
"""
INTERFACE COM A TRANSMISSAO — e as fontes do modelo.

--------------------------------------------------------------------------
O que a BDGD entrega de AT, medido nesta base
--------------------------------------------------------------------------
A malha de 88 kV da BDGD NAO e conexa. Montando o grafo de SSDAT mais as
chaves fechadas de UNSEAT dao 32.220 nos em 844 componentes separadas — a
maior com 740 nos, 2,3% do total. Delas:

    230  tem cabeceira declarada (CTAT.PAC_INI)
    213  tem transformador de potencia
    154  tem transformador mas NENHUMA cabeceira
    460  sao ilhas puras: nem cabeceira, nem trafo

As 16 ETTs da ISA (TANH, TBAN, TNOR...) nao possuem uma unica barra na
tabela BAR e quase nenhuma chave em UNSEAT. Ou seja: os trechos de 88 kV
que ligam uma subestacao a outra, e a transmissao aos pontos de conexao,
nao estao nesta exportacao.

Conclusao pratica: NAO da para montar uma subtransmissao conexa so com a
BDGD. Da para montar o patio de AT de cada subestacao e energiza-lo — que
e o que este modulo faz, dizendo em relatorio exatamente quantas
subestacoes receberam ponto de injecao real e quantas receberam
equivalente.

--------------------------------------------------------------------------
Para que servem os arquivos da ISA Energia
--------------------------------------------------------------------------
Eles nao fecham a malha (nao trazem LINHAS de transmissao, so
transformadores e subestacoes), mas resolvem dois problemas concretos:

1. As subestacoes da transmissora que alimentam alimentadores da Enel.
   Cinco SUBs aparecem em CTMT sem nenhum trafo em UNTRAT — TBAN, TCTR,
   TEMG, TMRE e SSJO —, somando 69 alimentadores que hoje ficam orfaos.
   Quatro delas sao ETTs da ISA, e a planilha diz qual e o transformador:
   Bandeirantes 345/34,5 kV, Centro 230/20 kV, Miguel Reale 345/20 kV.
   Com isso esses alimentadores passam a ter um trafo de verdade.

2. O nivel de curto nos pontos de injecao. Em vez de um MVAsc inventado,
   a potencia instalada declarada em cada ETT da uma estimativa defensavel
   (ver `mvasc_estimado`).

O que os arquivos NAO permitem: representar a rede de 345/440 kV em si.
Sem as linhas de transmissao e suas impedancias, qualquer topologia acima
do ponto de conexao seria invencao. O modelo para no ponto de conexao, com
equivalente de curto — que e a pratica normal em estudo de distribuicao.
"""
import collections
import os

from .leitor import num, txt
from . import tensoes

# nom_subestacao na planilha de trafos -> COD_ID da SUB na BDGD.
# Feito a mao a partir das duas planilhas; os nomes nao batem sozinhos
# ('B. SANTISTA' x 'ETT BAIXADA SANTISTA', 'RAM REBERT F' x 'ETT RAMON
# REBERTE FILHO'), entao um de-para explicito e mais seguro que heuristica.
ISA_PARA_SUB = {
    'ANHANGUERA': 'TANH',
    'B. SANTISTA': 'TBSA',
    'BANDEIRANTES': 'TBAN',
    'CENTRO-CTR': 'TCTR',
    'EMBU-GUACU': 'TEMG',
    'JANDIRA': 'TJAD',
    'LESTE': 'TLES',
    'M. FORNASARO': 'TMFO',
    'MIGUEL REALE': 'TMRE',
    'NORDESTE': 'TNOD',
    'NORTE': 'TNOR',
    'PIRATININGA': 'TPIR',
    'PIRATININGA 2': 'TPI2',
    'PIRITUBA': 'TPRI',
    'RAM REBERT F': 'TRRF',
    'SUL': 'TSUL',
}

# Nivel de curto quando nao ha nada em que se basear. 2.500 MVA em 88 kV
# equivale a ~16 kA, ordem de grandeza de um ponto de conexao urbano.
MVASC_PADRAO = 2500.0

# Fracao da potencia instalada que vira potencia de curto no secundario.
# Um trafo de 400 MVA com 12% de impedancia da ~3.300 MVA de curto; o
# fator 8 e conservador e esta documentado para poder ser contestado.
FATOR_CURTO = 8.0


# ==================================================================== leitura
def ler_isa(pasta_excel, log=None):
    """Le as duas planilhas da ISA. Devolve {} se nao existirem — o
    conversor segue com equivalentes."""
    if not pasta_excel or not os.path.isdir(pasta_excel):
        return {}
    try:
        import openpyxl
    except Exception:
        if log:
            log('    AVISO: openpyxl ausente — dados da ISA ignorados.')
        return {}

    fn = None
    for cand in os.listdir(pasta_excel):
        if cand.lower().startswith('trafosenelsp') and cand.lower().endswith('.xlsx'):
            fn = os.path.join(pasta_excel, cand)
            break
    if not fn:
        return {}

    try:
        wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
        ws = wb.active
        linhas = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as e:
        if log:
            log(f'    AVISO: falha ao ler {os.path.basename(fn)}: {e}')
        return {}
    if not linhas:
        return {}

    hdr = [str(c).strip() if c is not None else '' for c in linhas[0]]
    ix = {h: i for i, h in enumerate(hdr)}
    need = ('nom_subestacao', 'val_tensaoprimario_kv', 'val_tensaosecundario_kv',
            'val_potencianominal_mva', 'dat_desativacao')
    if any(k not in ix for k in need):
        if log:
            log('    AVISO: planilha da ISA com colunas inesperadas — ignorada.')
        return {}

    por_sub = collections.defaultdict(list)
    for r in linhas[1:]:
        if not r or r[ix['nom_subestacao']] is None:
            continue
        if r[ix['dat_desativacao']] is not None:
            continue                                   # trafo desativado
        nome = str(r[ix['nom_subestacao']]).strip()
        sub = ISA_PARA_SUB.get(nome)
        if not sub:
            continue
        kv1 = num(r[ix['val_tensaoprimario_kv']])
        kv2 = num(r[ix['val_tensaosecundario_kv']])
        mva = num(r[ix['val_potencianominal_mva']])
        if kv1 <= 0 or kv2 <= 0 or mva <= 0:
            continue
        por_sub[sub].append({'kv1': kv1, 'kv2': kv2, 'mva': mva, 'nome': nome})
    if log:
        log(f'    ISA: {sum(len(v) for v in por_sub.values())} transformadores '
            f'ativos em {len(por_sub)} subestacoes de transmissao')
    return dict(por_sub)


def mvasc_estimado(isa, sub, kv_alvo=None):
    """Potencia de curto no ponto de conexao, a partir da potencia
    instalada declarada pela ISA. Cai no padrao quando nao ha dado."""
    lst = isa.get(sub) or []
    if kv_alvo:
        f = [x for x in lst if abs(x['kv2'] - kv_alvo) < 0.6]
        lst = f or lst
    if not lst:
        return MVASC_PADRAO, False
    return round(sum(x['mva'] for x in lst) * FATOR_CURTO, 1), True


# =========================================================== fontes do modelo
def fontes(componentes, info_trafos, ctat_heads, isa, caminho,
           kv_at_padrao=88.0, log=None, barra_por_sub=None):
    """Uma fonte por patio de AT que tenha transformador.

    Preferencia do ponto de injecao, da melhor para a pior:
      1. a barra de uma ETT (subestacao da transmissora) presente no patio —
         e o ponto de conexao de verdade;
      2. a cabeceira do circuito de AT (CTAT.PAC_INI);
      3. o proprio primario do transformador (PAC_1) — equivalente explicito.

    Patios sem transformador nao recebem fonte: nao alimentam nada, seriam
    trechos energizados a toa. Entram no relatorio como ilhas.
    """
    barra_por_sub = barra_por_sub or {}
    # barras das subestacoes da transmissora: onde a energia realmente entra
    barras_ett = {barra_por_sub[s]: s for s in ISA_PARA_SUB.values()
                  if s in barra_por_sub}
    pac_at = info_trafos['pac_at']
    sub_do_trafo = {}
    for sub, lst in info_trafos['por_sub'].items():
        for cod in lst:
            sub_do_trafo[cod] = sub

    out = ['! ==========================================================',
           '! FONTES — uma por patio de AT energizado',
           '! ',
           '! A malha de 88 kV da BDGD nao e conexa (844 componentes), e as',
           '! subestacoes da transmissora nao tem barra nesta exportacao.',
           '! Por isso cada patio de AT com transformador recebe sua propria',
           '! fonte no ponto de conexao. Onde ha cabeceira de circuito de AT',
           '! (CTAT.PAC_INI) ela e usada; senao, injeta-se no primario do',
           '! transformador, o que e um equivalente explicito.',
           '! ',
           '! MVAsc: da potencia instalada declarada pela ISA quando a',
           '! subestacao e uma ETT conhecida; senao o padrao documentado.',
           '! ==========================================================']

    primeira = True
    n_head = n_eq = 0
    detalhe = []
    for comp in componentes:
        trafos_aqui = [cod for cod, p in pac_at.items() if p in comp]
        if not trafos_aqui:
            continue
        ett = sorted(comp & set(barras_ett))
        heads = sorted(comp & ctat_heads)
        sub_ett = None
        if ett:
            barra = ett[0]
            sub_ett = barras_ett[barra]
            origem = f'ponto de conexao real ({sub_ett})'
            n_head += 1
        elif heads:
            barra = heads[0]
            origem = 'cabeceira CTAT'
            n_head += 1
        else:
            barra = pac_at[trafos_aqui[0]]
            origem = 'equivalente no primario do trafo'
            n_eq += 1
        subs = {sub_do_trafo.get(c) for c in trafos_aqui} - {None}
        sub = sub_ett or (sorted(subs)[0] if subs else '')
        mvasc, real = mvasc_estimado(isa, sub, kv_at_padrao)
        nome = f'FONTE_{sub or "SEM_SUB"}_{barra[:12]}'.replace('-', '_')
        cmt = (f'! {sub or "?"}: {len(trafos_aqui)} trafo(s), {origem}, '
               f'MVAsc={mvasc:g} ({"ISA" if real else "padrao"})')
        out.append(cmt)
        if primeira:
            out.append(f'New Circuit.ENEL_SP basekV={kv_at_padrao} pu=1.0 phases=3 '
                       f'bus1={barra} Angle=0 MVAsc3={mvasc:g} MVAsc1={mvasc*0.8:g}')
            primeira = False
        else:
            out.append(f'New Vsource.{nome} bus1={barra} basekV={kv_at_padrao} pu=1.0 '
                       f'phases=3 Angle=0 MVAsc3={mvasc:g} MVAsc1={mvasc*0.8:g}')
        detalhe.append({'sub': sub, 'barra': barra, 'origem': origem,
                        'mvasc': mvasc, 'isa': real, 'trafos': len(trafos_aqui)})
    if primeira:
        # nenhuma componente com trafo: circuito precisa de pelo menos uma fonte
        out.append(f'New Circuit.ENEL_SP basekV={kv_at_padrao} pu=1.0 phases=3 '
                   f'bus1=SOURCEBUS Angle=0 MVAsc3={MVASC_PADRAO:g}')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if log:
        log(f'    fontes de AT: {n_head} em cabeceira real, {n_eq} equivalentes')
    return {'com_cabeceira': n_head, 'equivalentes': n_eq, 'detalhe': detalhe}


# ============================== subestacoes da transmissora (as 5 orfas)
def trafos_transmissora(orfas, isa, caminho, kv_mt_padrao=13.8, log=None):
    """Constroi o transformador das subestacoes que aparecem em CTMT mas
    nao tem nada em UNTRAT — o caso que voce lembrava da ALCO.

    `orfas` = {SUB: {kv_mt: [lista de alimentadores]}}. Para cada tensao de
    MT procura-se na ISA um trafo cujo secundario bata; achando, ele e
    emitido com os dados reais. Nao achando, emite-se um equivalente
    dimensionado pela quantidade de alimentadores, e isso vai no relatorio.
    """
    out = ['! ==========================================================',
           '! SUBESTACOES DA TRANSMISSORA',
           '! ',
           '! Estas subestacoes alimentam alimentadores da Enel mas nao tem',
           '! transformador em UNTRAT — o ativo e da transmissora, entao nao',
           '! entra na BDGD da distribuidora. O trafo abaixo vem da planilha',
           '! da ISA quando a tensao bate; senao e um equivalente, marcado.',
           '! ==========================================================']
    n_real = n_eq = 0
    barras = {}
    niveis = set()          # tensoes introduzidas por estes trafos (230, 345...)
    # A fonte e UMA POR PATIO, e o patio e (subestacao, nivel de AT). O laco
    # abaixo percorre (subestacao, nivel de MT), entao uma subestacao que
    # alimenta dois niveis de MT a partir do MESMO nivel de AT passa duas vezes
    # pela mesma fonte. Medido na Equatorial PA: SSB e TUR emitiam
    # `Vsource.FONTE_SSB_88kv` e `FONTE_TUR_88kv` duas vezes cada.
    #
    # A linha repetida e IDENTICA — nome, barra, basekV e MVAsc dependem so de
    # (sub, kv1) —, entao nao havia diferenca eletrica. Mas o C-API recusa a
    # redefinicao com o erro #266 e o MASTER-AT inteiro deixa de compilar; o
    # motor COM aceita calado e a segunda apaga a primeira. Nenhum dos dois
    # comportamentos e o que se quer de uma duplicata exata.
    fontes_emitidas = set()
    for sub, por_kv in sorted(orfas.items()):
        lst = isa.get(sub) or []
        for kv_mt, alims in sorted(por_kv.items()):
            cand = [x for x in lst if abs(x['kv2'] - kv_mt) < 0.6]
            barra = f'barra_mt_{sub}_{str(kv_mt).replace(".", "p")}'.lower()
            if cand:
                kv1 = cand[0]['kv1']
                mva = sum(x['mva'] for x in cand)
                fonte = f'ISA: {len(cand)} trafo(s) {kv1:g}/{kv_mt:g} kV'
                n_real += 1
            else:
                kv1 = 88.0
                mva = max(20.0, 10.0 * len(alims))
                fonte = (f'EQUIVALENTE — a ISA nao declara trafo em {kv_mt:g} kV '
                         f'nesta subestacao; {mva:g} MVA dimensionados por '
                         f'{len(alims)} alimentadores')
                n_eq += 1
            mvasc, _ = mvasc_estimado(isa, sub, kv1)
            # A barra de AT tem de ser UMA POR NIVEL DE TENSAO. A TBAN
            # alimenta 9 saidas em 20 kV e 29 em 34,5 kV; com uma barra so,
            # duas Vsource caiam no mesmo no com basekV diferente (88 e 345),
            # o CalcVoltagebases atribuia 88/raiz(3) a barra de 34,5 kV e os
            # 29 alimentadores ficavam sem tensao — foram 2.238 cargas mortas.
            barra_at = f'barra_at_{sub.lower()}_{kv1:g}kv'.replace('.', 'p')
            out.append(f'! {sub} — {len(alims)} alimentadores em {kv_mt:g} kV. {fonte}')
            nome_fonte = f'FONTE_{sub}_{kv1:g}kv'
            if nome_fonte not in fontes_emitidas:
                fontes_emitidas.add(nome_fonte)
                out.append(f'New Vsource.{nome_fonte} bus1={barra_at} '
                           f'basekV={kv1:g} pu=1.0 phases=3 Angle=0 '
                           f'MVAsc3={mvasc:g} MVAsc1={mvasc*0.8:g}')
            else:
                out.append(f'! (a fonte {nome_fonte} ja foi emitida para outro '
                           f'nivel de MT desta subestacao)')
            out.append(f'New Transformer.TT_{sub}_{str(kv_mt).replace(".", "p")} '
                       f'phases=3 windings=2 Xhl=12.0\n'
                       f'~ %loadloss=0.5 %noloadloss=0.15\n'
                       f'~ wdg=1 bus={barra_at}.1.2.3 conn=delta '
                       f'kV={kv1:g} kVA={mva*1000:.0f}\n'
                       f'~ wdg=2 bus={barra}.1.2.3.0 conn=wye '
                       f'kV={kv_mt:g} kVA={mva*1000:.0f}')
            niveis.add(float(kv1)); niveis.add(float(kv_mt))
            for a in alims:
                barras[a] = {'barra': barra, 'kv': kv_mt}
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if log:
        log(f'    subestacoes da transmissora: {n_real} com trafo da ISA, '
            f'{n_eq} com equivalente')
    return barras, {'isa': n_real, 'equivalente': n_eq, 'niveis': sorted(niveis)}
