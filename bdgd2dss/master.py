# -*- coding: utf-8 -*-
"""
Os MASTERs. Dois produtos, a partir dos mesmos arquivos de rede:

  MASTER-GERAL.dss    a concessao inteira — transmissao, AT, MT e BT.
                      E o modelo "rede como um todo".

  <SE>/MASTER-<SE>.dss  uma subestacao isolada, com equivalente na barra
                      de MT. Continua existindo porque estudo de
                      alimentador (NSGA-II, criticidade) nao precisa
                      carregar 155 subestacoes para rodar um caso.

O que mudou em relacao a versao anterior
----------------------------------------
Antes cada ALIMENTADOR ganhava um transformador proprio ligado a um
SOURCEBUS infinito. Eram 1.806 fontes ideais numa rede de 155 subestacoes.
Consequencias: os alimentadores da mesma subestacao nao dividiam trafo nem
barra, a impedancia de subtransmissao nao existia, e a tensao na cabeceira
era 1,0 pu por construcao — o que esconde justamente a queda que o estudo
quer medir.

Agora a fonte esta no patio de AT, o transformador de potencia e o real da
UNTRAT/EQTRAT, e os alimentadores da subestacao dividem a barra de MT
atraves dos seus vaos. No modo por subestacao a fonte fica na barra de MT
com o equivalente de curto do patio — sem trafo ideal por alimentador.

Cada arquivo de rede e neutro: so declara elementos, nunca fonte nem
Solve. Assim o mesmo arquivo serve aos dois MASTERs.
"""
import os

from . import tensoes
from . import escrita

CAB_GERAL = """clear
set defaultbasefrequency=60

! ==========================================================================
!  ENEL SP — MODELO COMPLETO DA CONCESSAO
!  gerado de {gdb}
!  por bdgd2dss
! ==========================================================================
!
!  ABRANGENCIA
!    subestacoes ......... {n_se}
!    alimentadores ....... {n_ctmt}
!    trafos de potencia .. {n_trat}   (AT -> MT, reais da UNTRAT/EQTRAT)
!    trechos de AT ....... {n_lat:,}  ({km_at:,.1f} km de subtransmissao)
!    chaves de AT ........ {n_chat:,}
!    vaos de saida ....... {n_vao:,}  (barra de MT -> cabeceira)
!
!  COMO ESTE MODELO E ALIMENTADO
!    A malha de 88 kV da BDGD nao e conexa: sao {n_comp} componentes
!    separadas, e as subestacoes da transmissora nao possuem barra nesta
!    exportacao. Cada patio de AT com transformador recebe portanto a sua
!    propria fonte:
!        {n_fonte_real} em cabeceira de circuito de AT declarada (CTAT.PAC_INI)
!        {n_fonte_eq} como equivalente no primario do transformador
!    O nivel de curto vem da potencia instalada declarada pela ISA Energia
!    onde a subestacao e uma ETT conhecida; nas demais usa-se o padrao
!    documentado em bdgd2dss/transmissao.py.
!
!  ORDEM DE MONTAGEM
!    1. fontes — o New Circuit tem de vir antes de qualquer elemento
!    2. LineCodes e curvas (comuns a todos os niveis)
!    3. subtransmissao: linhas, chaves, transformadores de potencia
!    4. subestacoes da transmissora (as que nao tem trafo proprio)
!    5. vaos de saida — e aqui que a AT encontra a MT
!    6. uma subestacao por vez: MT, transformadores, cargas, GD
!    7. estado das chaves normalmente abertas
!
!  LIMITES DECLARADOS — leia antes de publicar resultado
!    R0/X0 sao premissa (3,0 e 3,5 vezes os de sequencia positiva), nao
!      dado: a SEGCON so traz R1 e X1. Resultado de DESEQUILIBRIO nao tem
!      validade neste modelo.
!    Xhl dos trafos de potencia e adotado por faixa de potencia; a BDGD
!      traz perdas, nao impedancia.
!    A carga de BT esta agregada no secundario de cada trafo de
!      distribuicao. Correto para carregamento de MT; NAO serve para tensao
!      de atendimento ao consumidor (use --bt completo para isso).
!    Fator de potencia 0,92 assumido, nao medido.
!    Harmonicos fora de alcance: a BDGD nao traz espectro.
! ==========================================================================

"""

MEDICAO = """
! ------------------------------------------------------------------ medicao
! EnergyMeter na entrada de cada alimentador (no vao de saida). E o que
! permite apurar perdas, energia e sobrecarga POR ALIMENTADOR — o Monitor
! sozinho registra grandeza, nao acumula perdas.
!   Show Meters          resumo por alimentador
!   Show Losses          perdas por elemento
!   Export Meters        planilha com kWh, perdas e violacoes
{medidores}
! Monitores de potencia nos transformadores de potencia (AT -> MT).
{mon_trafo}
! Monitores de corrente nos troncos de subtransmissao.
{mon_linha}
"""

RODAPE_GERAL = """
! ------------------------------------------------------------------ solucao
Set Voltagebases=[{bases}]
CalcVoltagebases

Set maxcontroliter=200
Set maxiterations=100
Set controlmode=static
Set tolerance=0.0001

! estado das chaves normalmente abertas, fixado depois da montagem
{aberturas}
! solucao inicial, recalculo das bases e solucao definitiva
Set mode=snap
Solve
CalcVoltagebases
Solve

! --------------------------------------------------- coordenadas geograficas
! DEPOIS do Solve de proposito: a lista de barras do OpenDSS so existe apos a
! montagem, e um Buscoords emitido antes nao encontra barra alguma para casar.
! Extraidas da geometria da BDGD (SIRGAS 2000). Habilitam:
!   Plot Circuit Power max=2000 dots=n labels=n C1=Blue
!   Plot Circuit Voltage
!   Plot profile phases=all
{buscoords}

! ------------------------------------------------------------------ conferencia
! Descomente para o regime diario de 24 h em passos de 15 min:
!   Set mode=daily
!   Set stepsize=15m
!   Set number=96
!   Solve
!
! Depois de resolver:
!   Show Convergence          quem nao convergiu
!   Show Isolated             o que ficou sem fonte
!   Show Voltages LN Nodes    tensoes por no
!   Show Overloads            elementos acima da nominal
!   Show Losses               perdas por elemento
"""

CAB_SE = """clear
set defaultbasefrequency=60

! ==========================================================================
!  {se} — subestacao isolada
!  {n_alim} alimentadores | {n_barras:,} barras de MT
! ==========================================================================
!  Modelo para estudo de alimentador. A fonte esta na barra de MT, com o
!  equivalente de curto do patio de AT desta subestacao — os alimentadores
!  dividem a mesma barra, como na operacao real.
!
!  Para a rede completa, com a subtransmissao e as demais subestacoes,
!  use ../MASTER-GERAL.dss.
! ==========================================================================

New Circuit.{se} basekV={kv_mt} pu={pu:.4f} phases=3 bus1={barra} Angle=0
~ MVAsc3={mvasc:g} MVAsc1={mvasc1:g}
"""

RODAPE_SE = """
{medicao}
Set Voltagebases=[{bases}]
CalcVoltagebases

Set maxcontroliter=200
Set maxiterations=100
Set controlmode=static

redirect _CHAVES_ABERTAS.dss

! Premissa de modelagem, e nao conversao — achado 34. Vazio quando a base nao
! tem trecho conduzindo acima da propria ampacidade. Apagar esta linha devolve
! o modelo ao que a BDGD declara.
redirect _AMPACIDADE.dss

! Premissa de modelagem que INVENTA um elo — achado 33, forma B. Vazio ate
! alguem rodar `ligacao.py`. Apagar esta linha devolve o modelo a topologia
! que a BDGD declara.
redirect _LIGACAO.dss

Set mode=snap
Solve
CalcVoltagebases
Solve

! coordenadas — depois do Solve, quando a lista de barras ja existe
{buscoords}
"""


def rede_se(se, arquivos, caminho):
    """REDE-<SE>.dss: so os elementos da subestacao, sem fonte e sem Solve.

    E o que permite o mesmo material servir ao modelo isolado e ao geral.
    LineCodes e curvas ficam de fora de proposito: sao globais e seriam
    redeclarados 155 vezes no MASTER-GERAL."""
    comuns = {'LineCodes.dss', 'Curvas.dss', '_XYCURVES.dss'}
    out = [f'! Elementos de {se}. Sem fonte e sem Solve — o MASTER cuida disso.']
    for a in arquivos:
        if os.path.basename(a) in comuns:
            continue
        out.append(f'redirect {a}')
    open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out) + '\n')
    return [a for a in arquivos if os.path.basename(a) not in comuns]


def gerar_se(se, caminho, barra_mt, kv_mt, n_alim, n_barras, mvasc,
             arquivos_comuns, niveis, buscoords='', bloco_medicao='', pu=1.0,
             barras_extra=(), bt=None):
    """MASTER de uma subestacao, com uma fonte por BARRA de MT.

    `pu` vem de CTMT.TEN_OPE: a barra de MT nao opera no nominal. Com pu=1,0
    a mediana da concessao caia para 0,921 e cinco subestacoes nao convergiam.

    `barras_extra` sao as demais barras de MT da subestacao, cada uma com a
    sua tensao. Uma subestacao pode operar em MAIS DE UM NIVEL: a TBAN tem 9
    alimentadores em 20 kV e 29 em 34,5 kV. Com uma fonte so, os 29 da outra
    barra ficavam sem tensao — eram 2.238 cargas mortas.
    """
    out = [CAB_SE.format(se=se, n_alim=n_alim, n_barras=n_barras,
                         kv_mt=f'{kv_mt:g}', barra=barra_mt, pu=pu,
                         mvasc=mvasc, mvasc1=mvasc * 0.8)]
    for j, (b_, kv_, pu_) in enumerate(barras_extra, 1):
        out.append(f'! segunda barra de MT desta subestacao, em {kv_:g} kV')
        out.append(f'New Vsource.FONTE{j}_{se} bus1={b_} basekV={kv_:g} '
                   f'pu={pu_:.4f} phases=3 Angle=0 '
                   f'MVAsc3={mvasc:g} MVAsc1={mvasc*0.8:g}')
    for a in arquivos_comuns:
        out.append(f'redirect {a}')
    out.append(f'redirect REDE-{se}.dss')
    bases = ' '.join(f'{x:g}' for x in tensoes.bases(*niveis, bt=bt))
    out.append(RODAPE_SE.format(bases=bases, buscoords=buscoords,
                               medicao=bloco_medicao))
    open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out))


CAB_AT = """clear
set defaultbasefrequency=60

! ==========================================================================
!  MASTER-AT — subtransmissao com as subestacoes como carga equivalente
! ==========================================================================
!  {n_se} subestacoes | {mw:,.0f} MW agregados
!
!  POR QUE ESTE MODELO EXISTE
!  --------------------------
!  O MASTER-GERAL junta tudo num arquivo so: 2,39 milhoes de elementos na
!  Enel SP, que nao cabem em 15,8 GB de RAM. Este aqui e a metade de cima da
!  decomposicao: a rede de AT inteira, com cada subestacao representada pela
!  demanda que ela de fato tem.
!
!  Sao ~19.500 elementos, menos de 1% do modelo monolitico, e por isso cabe
!  em qualquer maquina e continua cabendo em qualquer distribuidora — o porte
!  dele escala com a subtransmissao, nao com a concessao.
!
!  O QUE ELE MEDE, E QUE HOJE E SUPOSTO
!  ------------------------------------
!  A tensao na barra de MT de cada subestacao. Nos modelos por subestacao ela
!  e DECLARADA (CTMT.TEN_OPE, que na Enel SP e 1,09 em 1.586 dos 1.806
!  alimentadores) e nao calculada. Aqui ela sai do fluxo, com a impedancia da
!  malha de 88 kV e o carregamento dos transformadores de potencia.
!
!  A CARGA EQUIVALENTE E UMA PREMISSA, e esta declarada
!  ---------------------------------------------------
!  Cada subestacao vira uma carga de potencia constante na sua barra de MT.
!  Isso e exato para rede radial abaixo do transformador — que e o caso — a
!  menos do acoplamento: a demanda real depende da tensao, e a tensao depende
!  da demanda. O laco do `decompor.py` resolve isso iterando.
! ==========================================================================
"""

RODAPE_AT = """
Set Voltagebases=[{bases}]
CalcVoltagebases

Set maxcontroliter=200
Set maxiterations=100
Set controlmode=static

Set mode=snap
Solve
CalcVoltagebases
Solve
{buscoords}
"""


def gerar_at(caminho, arquivos_at, ses, niveis, buscoords='', bt=None,
             fator=1.0, arquivos_globais=()):
    """MASTER-AT.dss — a rede de alta tensao com as subestacoes agregadas.

    `ses` e uma lista de dicionarios com `SE`, `barra_mt`, `kv_mt` e a
    demanda (`kW_BT` + `kW_MT`). Cada uma vira uma carga trifasica de
    potencia constante na barra de MT.

    `fator` multiplica a demanda — e o que o laco de decomposicao usa para
    reinjetar a carga medida no modelo por subestacao depois de resolver.

    MODELO 1 (potencia constante) e deliberado. Com modelo de impedancia
    constante a carga cairia junto com a tensao e o resultado seria
    otimista justamente no caso que interessa medir, que e o da subestacao
    mal alimentada.
    """
    linhas, mw = [], 0.0
    for s in ses:
        barra = (s.get('barra_mt') or '').strip()
        kv = float(s.get('kv_mt') or 0)
        kw = (float(s.get('kW_BT') or 0) + float(s.get('kW_MT') or 0)) * fator
        if not barra or kv <= 0 or kw <= 0:
            continue
        mw += kw / 1000.0
        # pf 0,92: o mesmo das cargas de MT e BT, para o reativo da
        # subtransmissao nao sair de premissa diferente da do resto
        linhas.append(f'New Load.SE_{s["SE"]} Bus1={barra}.1.2.3 Phases=3 '
                      f'Conn=wye Model=1 kV={kv:.4f} kW={kw:.3f} pf=0.92 '
                      f'Vminpu=0.5 Vmaxpu=1.5')

    out = [CAB_AT.format(n_se=len(linhas), mw=mw)]
    # A ORDEM E OBRIGATORIA, e ja custou uma depuracao antes:
    #   1. `Fontes.dss`, porque e nele que nasce o `New Circuit` — sem
    #      circuito, o OpenDSS recusa qualquer definicao com o erro #265;
    #   2. os globais, porque os condutores de AT saem da mesma SEGCON da MT
    #      e sem os LineCodes o `Linhas_AT.dss` recusa na primeira linha;
    #   3. o resto da camada de AT.
    fontes = [a for a in arquivos_at if 'fontes' in os.path.basename(a).lower()]
    resto = [a for a in arquivos_at if a not in fontes]
    for a in fontes + list(arquivos_globais) + resto:
        out.append(f'redirect {a}')
    out.append('\n! ---------------------- subestacoes como carga equivalente')
    out += linhas
    bases = ' '.join(f'{x:g}' for x in tensoes.bases(*niveis, bt=bt))
    out.append(RODAPE_AT.format(bases=bases, buscoords=buscoords))
    open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out))
    return len(linhas), round(mw, 1)


def medicao(vaos, trafos_at, linhas_at, max_linhas=200):
    """EnergyMeter por alimentador e monitores nos trafos e troncos de AT.

    O EnergyMeter vai no vao porque e o unico ponto onde toda a energia do
    alimentador passa; medindo ali, `Show Meters` da perdas e carregamento
    alimentador a alimentador sem pos-processamento.
    """
    med = [f'New EnergyMeter.EM_{c} element=Line.VAO_{c} terminal=1' for c in vaos]
    mt = [f'New Monitor.MT_{t} element=Transformer.AT_{t} terminal=1 mode=1 ppolar=no'
          for t in trafos_at]
    # so os troncos: monitorar 29 mil trechos geraria arquivo inutilizavel
    ml = [f'New Monitor.ML_{n} element=Line.AT_{n} terminal=1 mode=0'
          for n in linhas_at[:max_linhas]]
    if len(linhas_at) > max_linhas:
        ml.append(f'! {len(linhas_at)-max_linhas} trechos de AT sem monitor '
                  f'(limite {max_linhas}) — use Export Currents para o restante')
    return MEDICAO.format(medidores='\n'.join(med) or '! sem vaos',
                          mon_trafo='\n'.join(mt) or '! sem trafos de AT',
                          mon_linha='\n'.join(ml) or '! sem linhas de AT')


def gerar_geral(caminho, gdb, ses, arquivos_at, arquivos_globais,
                estat, niveis, aberturas, bloco_medicao='', buscoords='',
                bt=None):
    """MASTER-GERAL.dss — a concessao inteira num modelo so."""
    out = [CAB_GERAL.format(
        gdb=os.path.basename(gdb), n_se=len(ses), n_ctmt=estat.get('n_ctmt', 0),
        n_trat=estat.get('n_trafos_at', 0), n_lat=estat.get('n_linhas_at', 0),
        km_at=estat.get('km_at', 0.0), n_chat=estat.get('n_chaves_at', 0),
        n_vao=estat.get('n_vaos', 0), n_comp=estat.get('n_componentes', 0),
        n_fonte_real=estat.get('fontes_cabeceira', 0),
        n_fonte_eq=estat.get('fontes_equivalente', 0))]

    # o New Circuit vive em Fontes.dss e tem de ser a PRIMEIRA declaracao:
    # o OpenDSS recusa qualquer elemento antes de existir um circuito.
    fontes = [a for a in arquivos_at if os.path.basename(a).startswith('Fontes')]
    resto_at = [a for a in arquivos_at if a not in fontes]

    out.append('! ---------------------------------------- 1. fontes')
    for a in fontes:
        out.append(f'redirect {a}')

    out.append('\n! ---------------------------------------- 2. LineCodes e curvas')
    for a in arquivos_globais:
        out.append(f'redirect {a}')

    out.append('\n! ---------------------------------------- 3 a 5. alta tensao')
    for a in resto_at:
        out.append(f'redirect {a}')

    out.append(f'\n! ---------------------------------------- 6. as {len(ses)} subestacoes')
    for se in ses:
        out.append(f'redirect {se}/REDE-{se}.dss')

    if bloco_medicao:
        out.append(bloco_medicao)

    out.append('\n! ---------------------------------------- 7. chaves abertas')
    ab = '\n'.join(f'redirect {a}' for a in aberturas)
    bases = ' '.join(f'{x:g}' for x in tensoes.bases(*niveis, bt=bt))
    out.append(RODAPE_GERAL.format(bases=bases, aberturas=ab + '\n',
                                   buscoords=buscoords))
    open(caminho, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(out))
