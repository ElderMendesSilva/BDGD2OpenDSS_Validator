# -*- coding: utf-8 -*-
"""
Elementos complementares, cada funcao gerando um arquivo:

  CRVCRG  -> New LoadShape     (curvas por tipo de dia: DU, SA, DO)
  UNCRMT  -> New Capacitor     (bancos de capacitores de MT)
  UNREMT  -> New Transformer + New RegControl   (reguladores de tensao)
  UGBT/UGMT -> New PVSystem    (geracao distribuida)
  (fixo)  -> New XYCurve       (eficiencia do inversor e derating P x T)
"""
import math
from .leitor import num, txt, no

FASES = {'A': '1', 'B': '2', 'C': '3'}
HORAS = 730.0                       # horas no mes, igual ao usado em cargas.py

# ------------------------------------------------------------------ curvas de 96 pontos
# Tudo em 96 pontos de 15 min cobrindo as 24 h, na mesma malha da CRVCRG.
#
# A versao anterior da irradiancia estava DESLOCADA: 24 valores em passo de
# 15 min cobrem 6 h, nao 12. O sol ficava todo entre 6:00 e 12:00 e a tarde
# inteira zerada — e o pico de carga das 18:00 pegava a rede sem geracao
# nenhuma, o que derrubava a simulacao diaria no passo 72.
NASCER, POR = 6.0, 18.0             # horario solar medio de Sao Paulo (~23,5 S)


def _perfil_solar():
    """Irradiancia normalizada, seno sobre a janela de sol. E o modelo simples
    de ceu claro: proporcional a altura do sol, zero fora da janela."""
    v = []
    for k in range(96):
        h = k * 0.25
        if NASCER < h < POR:
            v.append(round(math.sin(math.pi * (h - NASCER) / (POR - NASCER)), 4))
        else:
            v.append(0.0)
    return v


def _perfil_temperatura(irr):
    """Temperatura de CELULA, nao ambiente — e o que a curva P-T do modulo
    espera. Ambiente em senoide entre 18 C (madrugada) e 28 C (15:00), mais o
    aquecimento por irradiancia pelo modelo NOCT:

        T_cel = T_amb + (NOCT - 20) / 800 * G     com NOCT = 45 C, G em W/m2

    Antes isto era 25 C constante nas 96 posicoes, o que anulava a curva
    MyPvsT: o modulo nunca derateava, e o meio-dia saia ~14% otimista.
    """
    v = []
    for k in range(96):
        h = k * 0.25
        amb = 23.0 - 5.0 * math.cos(math.pi * (h - 3.0) / 12.0)
        v.append(round(amb + (45.0 - 20.0) / 800.0 * (irr[k] * 1000.0), 2))
    return v


MESES = ['Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho', 'Julho',
         'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


def _ler_96(caminho):
    """Le 96 valores de um CSV, nos dois formatos que aparecem na pasta.

      NASA POWER:  YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN  com os campos entre
                   aspas e virgula decimal — 2025,1,15,"0,25","0,0"
      lista crua:  um valor por linha

    O decimal e virgula nos dois, entao a leitura tem de passar pelo modulo
    csv: separar por virgula na mao parte o campo "0,25" ao meio.
    """
    import csv as _csv
    import io as _io
    with _io.open(caminho, encoding='utf-8-sig', newline='') as fh:
        linhas = [l for l in _csv.reader(fh) if l and l[0].strip()]
    dados = [l for l in linhas
             if l[0].strip().replace('.', '').replace(',', '').lstrip('-').isdigit()]
    if not dados:
        raise ValueError(f'{caminho}: nenhuma linha de dado')
    v = [float(l[-1].replace(',', '.')) for l in dados]
    if len(v) != 96:
        raise ValueError(f'{caminho}: {len(v)} valores, esperado 96')
    return v


def _achar_mes(pasta, mes):
    """Acha o arquivo do mes ignorando caixa, acento e sufixo.

    A pasta mistura tres convencoes — JANEIRO_INTERPOLADO.csv,
    Janeiro_Irrad.csv, ABRIL.csv — e MARCO vem com cedilha.
    """
    import os as _os
    import unicodedata as _ud
    if not _os.path.isdir(pasta):
        return None

    def _n(s):
        s = _ud.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()
        for suf in ('_INTERPOLADO', '_IRRAD', '.CSV'):
            s = s.replace(suf, '')
        return s.strip()

    alvo = _n(MESES[max(1, min(12, mes)) - 1])
    achados = [f for f in sorted(_os.listdir(pasta)) if _n(f) == alvo]
    if not achados:
        return None
    # prefere o export da NASA (tem data e e o mais recente) ao formato antigo
    for f in achados:
        if 'INTERPOLADO' in f.upper():
            return _os.path.join(pasta, f)
    return _os.path.join(pasta, achados[0])


def carregar_clima(pasta, mes=1, log=None, dist_base=None, dist_clima=None,
                   forcar=False):
    """Irradiancia e temperatura MEDIDAS, se disponiveis.

    ---------------------------------------------------------------------
    O CLIMA TEM DE SER DA REGIAO — achado 4
    ---------------------------------------------------------------------
    Este era o defeito mais silencioso do conversor. O `--clima` aponta para
    a pasta de dados MEDIDOS de Sao Paulo, e ela era aplicada a qualquer
    base sem uma palavra. Roraima, que fica perto do equador, foi convertida
    com `irradiancia media 0.2590 kW/m2, ambiente 19.3 a 26.1 C` — numeros
    identicos aos de Sao Paulo, impressos como se fossem dela.

    Pior que quebrar, porque passa. Um erro que quebra e corrigido; um que
    imprime numero plausivel entra no artigo.

    Agora a pasta declara a que distribuidora pertence (`dist_clima`, o
    codigo ANEEL) e a base declara a sua (`BASE.DIST`). Se nao baterem, o
    conversor RECUSA o dado medido e cai no perfil sintetico, avisando. O
    sintetico e pior — 23% otimista e simetrico — mas ele SE DECLARA
    sintetico, e essa e a diferenca que importa.

    `forcar=True` usa mesmo assim. Existe porque ha casos legitimos (CPFL
    Paulista tambem opera em Sao Paulo), e fica registrado no relatorio.

    ---------------------------------------------------------------------
    Espera a arvore de 04_DADOS_AUXILIARES:

        Irradiancia_Interpolada/<Mes>_Irrad.csv   irradiancia em W/m2
        Temperatura_Interpolado/<Mes>.csv         temperatura ambiente em C

    Devolve (irradiancia em kW/m2, temperatura de celula em C) ou None se o
    mes nao estiver disponivel — nesse caso vale o perfil sintetico, que e
    declaradamente pior: medido em janeiro, o seno de ceu claro tem media
    0,318 contra 0,259 do dado real, 23% otimista, e e simetrico, enquanto o
    real tem 1,37x mais energia de manha que de tarde — a assinatura da
    convecao de verao de Sao Paulo.

    Tres ressalvas conferidas no arquivo de janeiro, nenhuma impeditiva:

      * ruido de borda: irradiancia nao nula com o sol sob o horizonte,
        abaixo de 1 W/m2. Zerada aqui.
      * irradiacao diaria de 6,22 kWh/m2, ~10% acima da faixa tipica de Sao
        Paulo em janeiro (5,0 a 5,8). Pode ser ano especifico, plano
        inclinado ou a interpolacao. O efeito e o pico do gerador sair ~10%
        subestimado, ja que o pmpp vem da energia dividida pela media.
      * defasagem termica de 1 h contra as 2 a 3 h reais, e amplitude diaria
        de 6,8 C contra 8 a 10 C tipicos: a temperatura parece suavizada
        demais. Efeito pequeno no derating.
    """
    import os as _os
    if not pasta:
        return None
    nome = MESES[max(1, min(12, mes)) - 1]
    d_base = str(dist_base or '').strip()
    d_clima = str(dist_clima or '').strip()
    if d_base and d_clima and d_base != d_clima and not forcar:
        if log:
            log(f'  clima: o dado medido e da distribuidora {d_clima} e esta '
                f'base e a {d_base}. RECUSADO — usando o perfil sintetico, '
                f'que ao menos se declara sintetico. Use --clima-forcar se a '
                f'regiao for a mesma.')
        return None
    fi = _achar_mes(_os.path.join(pasta, 'Irradiancia_Interpolada'), mes)
    ft = _achar_mes(_os.path.join(pasta, 'Temperatura_Interpolado'), mes)
    if not (fi and ft):
        if log:
            log(f'  clima: sem arquivo de {nome}; usando o perfil sintetico')
        return None
    try:
        # abaixo de 2 W/m2 e ruido da interpolacao: janeiro traz 0,04 a
        # 0,95 W/m2 as 1:25h, 3:25h e 20:25h, com o sol sob o horizonte
        g = [(x / 1000.0 if x >= 2.0 else 0.0) for x in _ler_96(fi)]
        amb = _ler_96(ft)
    except Exception as e:
        if log:
            log(f'  clima: falha ao ler {nome} ({e}); usando o perfil sintetico')
        return None
    # Mes sem sol nenhum e arquivo vazio, nao noite polar: novembro e dezembro
    # de 2025 vieram com os 96 pontos zerados. Cair no sintetico e melhor que
    # modelar uma concessao inteira sem geracao.
    if max(g) <= 0:
        if log:
            log(f'  clima: irradiancia de {nome} esta toda zerada — arquivo sem '
                f'dado; usando o perfil sintetico')
        return None
    # temperatura de CELULA pelo modelo NOCT, a partir da ambiente medida
    cel = [round(a + (45.0 - 20.0) / 800.0 * (gi * 1000.0), 2)
           for gi, a in zip(g, amb)]
    if log:
        log(f'  clima: {nome} medido — irradiancia media {sum(g)/96:.4f} kW/m2, '
            f'ambiente {min(amb):.1f} a {max(amb):.1f} C')
    return g, cel


IRRAD_DIA = _perfil_solar()
TEMP_DIA = _perfil_temperatura(IRRAD_DIA)


def _fator_pt(t):
    """MyPvsT interpolada: [0, 25, 75, 100] C -> [1.2, 1.0, 0.8, 0.6]."""
    x, y = [0, 25, 75, 100], [1.2, 1.0, 0.8, 0.6]
    if t <= x[0]:
        return y[0]
    for i in range(1, len(x)):
        if t <= x[i]:
            f = (t - x[i - 1]) / (x[i] - x[i - 1])
            return y[i - 1] + f * (y[i] - y[i - 1])
    return y[-1]


# Fator de capacidade EFETIVO da curva: media de irradiancia x derating termico.
# E o divisor que transforma a energia declarada da UG em potencia de pico:
#
#     pmpp = (ENE_mes / 730) / FC_IRRAD
#
# Incluir o derating aqui e o que mantem a invariante que a validacao exige —
# na simulacao diaria a integral bate com a energia da BDGD. Fica de fora a
# curva de eficiencia do inversor (MyEff), que depende do carregamento
# instantaneo e nao tem forma fechada; sao alguns por cento, medidos na
# comparacao final e nao estimados aqui.
def fc_efetivo(irr, cel):
    """Fator de capacidade efetivo de um par de curvas."""
    return sum(g * _fator_pt(t) for g, t in zip(irr, cel)) / len(irr)


FC_IRRAD = fc_efetivo(IRRAD_DIA, TEMP_DIA)      # valor do perfil sintetico

XYCURVES = """! Curvas do inversor e do modulo fotovoltaico.
New XYCurve.MyPvsT npts=4 xarray=[0 25 75 100] yarray=[1.2 1.0 0.8 0.6]
New XYCurve.MyEff  npts=4 xarray=[0.1 0.2 0.4 1.0] yarray=[0.86 0.90 0.93 0.97]
"""


# ------------------------------------------------------------------ curvas
def curvas(bdgd, caminho, tipo_dia='DU', clima=None):
    """LoadShapes normalizadas pela media. A BDGD traz POT_01..POT_96.

    `clima` = (irradiancia, temperatura de celula) de `carregar_clima`. Sem
    ele valem os perfis sinteticos. Devolve (nomes das curvas, irradiancia,
    temperatura) para que a geracao dimensione o pmpp pela MESMA curva que
    vai reger a simulacao diaria — se as duas divergirem, a integral deixa de
    bater com a energia declarada e a validacao contra PERD_* perde o pe.
    """
    col = bdgd.ler('CRVCRG', ['COD_ID', 'TIP_DIA'] + [f'POT_{i:02d}' for i in range(1, 97)])
    out = [f'! LoadShapes — CRVCRG, tipo de dia {tipo_dia}',
           '! Normalizadas pela demanda media de cada curva.']
    nomes = set()
    for i in range(len(col['COD_ID'])):
        if txt(col['TIP_DIA'][i]) != tipo_dia:
            continue
        v = [num(col[f'POT_{k:02d}'][i]) for k in range(1, 97)]
        m = sum(v) / len(v)
        if m <= 0:
            continue
        cod = txt(col['COD_ID'][i])
        nomes.add(cod)
        out.append(f'New LoadShape.{cod} npts=96 interval=0.25 '
                   f'mult=({" ".join(f"{x/m:.4f}" for x in v)})')
    # irradiancia em kW/m2 (1,0 = STC) e temperatura de celula, 96 pontos
    irr, cel = clima if clima else (IRRAD_DIA, TEMP_DIA)
    fonte = ('MEDIDA em Sao Paulo' if clima
             else f'SINTETICA (seno de {NASCER:g}h a {POR:g}h)')
    out.append(f'\n! irradiancia {fonte}, em kW/m2 (1,0 = STC).')
    out.append(f'! fator de capacidade efetivo (irradiancia x derating '
               f'termico) = {fc_efetivo(irr, cel):.4f}')
    out.append(f'New LoadShape.IRRAD_DIA npts=96 interval=0.25 '
               f'mult=({" ".join(f"{x:.4f}" for x in irr)})')
    out.append('\n! temperatura de CELULA, nao ambiente: e o que a curva '
               'MyPvsT espera. Ambiente + aquecimento NOCT por irradiancia.')
    out.append('New TShape.TEMP_DIA npts=96 interval=0.25 '
               f'temp=({" ".join(f"{x:.2f}" for x in cel)})')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return nomes, irr, cel


# ------------------------------------------------------------------ capacitores
def capacitores(bdgd, ctmts, caminho, kv=13.8, kv_por_ctmt=None, barras=None):
    """UNCRMT -> Capacitor. `barras` bloqueia o banco cujo PAC nao existe na
    rede: ele criaria a barra sozinho e a ilha devolveria NaN."""
    kv_por_ctmt = kv_por_ctmt or {}
    try:
        col = bdgd.ler_filtrado('UNCRMT', 'CTMT', ctmts,
                                ['COD_ID', 'PAC_1', 'CTMT', 'POT_NOM', 'FAS_CON'])
    except Exception:
        open(caminho, 'w').write('! UNCRMT indisponivel\n'); return 0
    out = ['! CAPACITORES — gerados de UNCRMT',
           '! Emitidos como banco FIXO. A BDGD nao traz o ajuste do CapControl;',
           '! se houver controle em campo, incluir CapControl aqui.']
    n = fora = 0
    for i in range(len(col['COD_ID'])):
        pac = no(col['PAC_1'][i])
        kvar = num(col['POT_NOM'][i])
        if not pac or kvar <= 0:
            continue
        if barras is not None and pac not in barras:
            fora += 1
            continue
        fs = [FASES[c] for c in txt(col['FAS_CON'][i], 'ABC').upper() if c in FASES] or ['1', '2', '3']
        kvc = kv_por_ctmt.get(txt(col['CTMT'][i]), kv)
        out.append(f'New Capacitor.{txt(col["COD_ID"][i])} Bus1={pac}.{".".join(fs)} '
                   f'Phases={len(fs)} Conn=wye kV={kvc:g} kvar={kvar:.1f}')
        n += 1
    out.insert(3, f'! {fora} bancos descartados por PAC ausente da rede.')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n


# ------------------------------------------------------------------ reguladores
def reguladores(bdgd, ctmts, caminho, kv=13.8, kv_por_ctmt=None,
                vreg=122.0, band=2.0, kva=5000.0, barras=None):
    """UNREMT -> autotrafo + RegControl.

    A exportacao original trazia kVs de linha num enrolamento monofasico,
    kVA irrisorio e vreg/ptratio incoerentes — o que fazia o OpenDSS estourar
    MaxControlIter. Aqui os parametros sao emitidos de forma consistente:
    kV fase-neutro, potencia compativel com o tronco, vreg em volts no
    secundario do TP e ptratio coerente.

    ATENCAO — vreg, band e kVA NAO vem da BDGD. Sao ajustes tipicos, iguais
    para todos os 213 reguladores da concessao. Se a distribuidora fornecer
    a tabela de ajuste de campo, passe os valores reais por aqui: e a
    diferenca entre um regulador que representa a operacao e um que apenas
    nao atrapalha a convergencia.
    """
    kv_por_ctmt = kv_por_ctmt or {}
    try:
        col = bdgd.ler_filtrado('UNREMT', 'CTMT', ctmts,
                                ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON'])
    except Exception:
        open(caminho, 'w').write('! UNREMT indisponivel\n'); return 0
    out = ['! REGULADORES — gerados de UNREMT',
           f'! vreg = {vreg:g} V e band = {band:g} V — AJUSTES TIPICOS, nao de campo.',
           f'! kVA = {kva:g} adotado; a BDGD nao traz a potencia do regulador.',
           '! O ptratio segue a tensao de cada alimentador (TP para 120 V).']
    n = 0
    for i in range(len(col['COD_ID'])):
        b1 = no(col['PAC_1'][i]); b2 = no(col['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        # com as duas pontas fora da rede o regulador vira uma ilha de duas
        # barras, e a ilha devolve NaN
        if barras is not None and b1 not in barras and b2 not in barras:
            continue
        cod = txt(col['COD_ID'][i])
        kv_ct = kv_por_ctmt.get(txt(col['CTMT'][i]), kv)
        kv_fn = kv_ct / math.sqrt(3)
        ptratio = round(kv_fn * 1000 / 120.0, 2)
        for f in [FASES[c] for c in txt(col['FAS_CON'][i], 'ABC').upper() if c in FASES] or ['1']:
            nome = f'REG_{cod}_{f}'
            out.append(f'New Transformer.{nome} phases=1 windings=2 XHL=0.04\n'
                       f'~ buses=[{b1}.{f} {b2}.{f}] conns=[wye wye]\n'
                       f'~ kVs=[{kv_fn:.4f} {kv_fn:.4f}] kVAs=[{kva:g} {kva:g}] %Rs=[0.01 0.01]\n'
                       f'~ maxtap=1.10 mintap=0.90 numtaps=32')
            out.append(f'New RegControl.RC_{nome} transformer={nome} winding=2 '
                       f'vreg={vreg:g} band={band:g} ptratio={ptratio} '
                       f'delay=15 maxtapchange=1')
            n += 1
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n


# ------------------------------------------------------------------ geracao
def geracao(bdgd, ctmts, sec, caminho, kv_mt=13.8, barras=None,
            irradiancia=1.0, fp=1.0, mes=1, fc=None):
    """UGBT_tab e UGMT_tab -> PVSystem.

    A POTENCIA VEM DA ENERGIA, NAO DE POT_INST
    ------------------------------------------
    `POT_INST` das tabelas de geracao NAO e a potencia do gerador: nas seis
    unidades de MT com mais de 1 MW da DPIP, DALV e DPEN ele e EXATAMENTE
    igual ao `CAR_INST` da unidade consumidora correspondente — carga
    instalada, nao potencia instalada de geracao. Uma delas declara
    POT_INST = 15.175 kW com DEM_01 = 228 kW e ENE_01 = 20.343 kWh/mes, o que
    da 27,9 kW medios. Erro de 540x.

    Na concessao inteira: POT_INST soma 1.399 MW (629 na BT, 770 na MT) contra
    30,5 MW de potencia media pela energia. A razao mediana e 21x na BT e 34x
    na MT — muito alem dos ~5x que um fator de capacidade fotovoltaico de 20%
    explicaria.

    Aqui o gerador e dimensionado pela grandeza MEDIDA, como ja se faz com a
    carga:

        pmpp = (ENE_mes / 730) / media(IRRAD_DIA)

    Com isso a simulacao diaria integra exatamente a energia declarada na
    BDGD, e o instantaneo com irradiance=1,0 da a ponta do meio-dia. Os dois
    modos ficam coerentes, que e o que a validacao contra as colunas PERD_*
    da CTMT vai exigir.

    Ressalva honesta: fica provado que POT_INST nao e a potencia do gerador
    nas unidades grandes de MT, e que a razao agregada e incompativel com
    fator de capacidade. NAO fica provado que ele esteja errado nas 33 mil
    unidades de BT — pode haver mistura de significado na base.

    Duas unidades sao descartadas por motivos diferentes:

    * energia nula no mes — sem energia nao ha gerador a modelar, e um
      PVSystem com kVA=0 gera divisao por zero e contamina a solucao com NaN;
    * ponto de conexao ausente da rede — o PVSystem cria a barra sozinho, ela
      fica sem nenhum PDE ligado, e a ilha resultante devolve NaN. Foi o que
      travava a DBSI em 100 iteracoes.

    O PAC da UGBT aponta para um no da rede secundaria (SSDBT/RAMLIG). Com
    `--bt agregado` essa rede nao existe, entao a geracao e realocada para o
    secundario do transformador indicado em UNI_TR_MT — a mesma agregacao ja
    aplicada as cargas de BT. A potencia e dividida entre as pernas
    existentes do secundario, como em `cargas.gerar`.

    IRRADIANCIA — nao e detalhe. No instantaneo, `irradiance` define quanto
    da potencia instalada esta gerando. Com 1,0 a DALP injeta 54.339 kW de
    GD contra 50.217 kW de carga: a subestacao exporta. Como a carga vem da
    energia MENSAL (ENE/730, potencia media), 1,0 representa o meio-dia de
    ceu claro, nao a ponta. Para estudo de carregamento maximo use um valor
    baixo; para estudo de sobretensao por GD, mantenha 1,0. Na simulacao
    diaria a curva IRRAD_DIA cuida disso e este parametro nao vale.
    """
    out = ['! GERACAO DISTRIBUIDA — gerada de UGBT_tab e UGMT_tab',
           '! Unidades com potencia nula sao omitidas (gerariam NaN).']
    n = nulos = realocados = sem_rede = por_ceg = 0
    pend = {}          # barra de BT -> geracao pendente, limitada no 2o passe
    # CEG_GD da UCMT_tab -> PAC da carga. E o unico caminho que funciona para
    # a geracao de MT: dos 319 registros de UGMT_tab da concessao, NENHUM tem
    # PAC presente na SSDMT (0,0%). Pelo CEG_GD, 164 casam com uma unidade
    # consumidora cujo PAC esta na rede — 568 MW que antes eram descartados
    # por "ponto de conexao ausente". Os 155 restantes nao tem par nem PAC
    # valido por nenhum caminho.
    pac_da_uc = {}
    try:
        u = bdgd.ler_filtrado('UCMT_tab', 'CTMT', ctmts, ['CEG_GD', 'PAC'])
        for i in range(len(u['CEG_GD'])):
            g = txt(u['CEG_GD'][i]).strip()
            if g:
                pac_da_uc[g] = no(u['PAC'][i])
    except Exception:
        pass

    ene = f'ENE_{mes:02d}'
    for camada, is_bt in (('UGBT_tab', True), ('UGMT_tab', False)):
        campos = ['COD_ID', 'PAC', 'CTMT', 'POT_INST', 'FAS_CON', 'CEG_GD', ene]
        if is_bt:
            campos.append('UNI_TR_MT')
        try:
            col = bdgd.ler_filtrado(camada, 'CTMT', ctmts, campos)
        except Exception:
            continue
        for i in range(len(col['COD_ID'])):
            # A potencia vem da ENERGIA declarada, nao de POT_INST. Ver o
            # docstring: POT_INST replica o CAR_INST do consumidor.
            pot = num(col[ene][i]) / HORAS / (fc or FC_IRRAD)
            pac = no(col['PAC'][i])
            if not pac:
                continue
            if pot <= 0:
                nulos += 1
                continue
            fs = [FASES[c] for c in txt(col['FAS_CON'][i], 'ABC').upper() if c in FASES] or ['1']
            cod = txt(col['COD_ID'][i])
            if is_bt:
                s = sec.get(pac)
                if s is None and barras is not None and pac not in barras:
                    # `UNI_TR_MT` e o plano B quando o PAC da geracao nao esta
                    # na rede. Se a coluna nao veio, nao ha plano B — e isso e
                    # contado como geracao sem rede, nao como excecao
                    s = (sec.get(txt(col['UNI_TR_MT'][i]))
                         if 'UNI_TR_MT' in col else None)
                    if s is None:
                        sem_rede += 1
                        continue
                    pac = s.get('barra', pac)
                    fs = s['nos'] or ['1']            # pernas reais do secundario
                    realocados += 1
                kv = s['kv_fn'] if s else 0.127
                # segura para o segundo passe, que limita pela capacidade do
                # transformador antes de escrever
                pend.setdefault(pac, {'kva': (s or {}).get('kva', 0.0),
                                      'kv': kv, 'itens': []})
                pend[pac]['itens'].append((cod, pot, fs))
                continue
            if barras is not None and pac not in barras and pac not in sec:
                # o PAC da UGMT nunca esta na rede; o da UC correspondente esta
                alt = pac_da_uc.get(txt(col['CEG_GD'][i]).strip(), '')
                if alt and (alt in barras or alt in sec):
                    pac = alt
                    por_ceg += 1
                else:
                    sem_rede += 1
                    continue
            kv = kv_mt if len(fs) >= 3 else kv_mt / math.sqrt(3)
            out.append(_pv(cod, f'{pac}.{".".join(fs)}', len(fs), kv, pot,
                           irradiancia, fp))
            n += 1
    # --- segundo passe da BT: nenhuma barra gera acima do proprio trafo ---
    # A BDGD declara POT_INST de UGBT que excede a capacidade do transformador
    # que a conecta — na DALP sao 232 das 571 barras com GD, 38.768 kW. Antes
    # essas unidades caiam em barra fantasma e nao faziam efeito (eram o NaN);
    # realocadas para o secundario, passaram a injetar 900 kW num trafo de
    # 100 kVA, jogando a barra a 3 pu. Com a tensao nesse patamar o PVSystem
    # entrega multiplos do Pmpp (medido: 8,75x) e a solucao vira ficcao.
    # O limite e fisico: a geracao a jusante nao passa da capacidade de quem
    # a conecta. O excedente e cortado e contabilizado.
    kw_cortado, barras_limitadas = 0.0, 0
    for bus, d in pend.items():
        total = sum(p for _, p, _ in d['itens'])
        limite = d['kva']
        fator = 1.0
        if limite > 0 and total > limite:
            fator = limite / total
            kw_cortado += total - limite
            barras_limitadas += 1
        for cod, pot, fs in d['itens']:
            pot *= fator
            if pot <= 0:
                continue
            for f in fs:
                out.append(_pv(f'{cod}_{f}', f'{bus}.{f}.4', 1, d['kv'],
                               pot / len(fs), irradiancia, fp))
                n += 1

    out.insert(2, f'! {nulos} unidades descartadas por potencia nula.')
    out.insert(3, f'! {realocados} unidades de BT realocadas para o secundario '
                  f'do transformador (rede secundaria nao modelada).')
    out.insert(4, f'! {sem_rede} unidades descartadas por ponto de conexao '
                  f'ausente da rede.')
    out.insert(5, f'! irradiance={irradiancia:g} — ver o docstring: 1,0 e '
                  f'meio-dia de ceu claro, nao a ponta de carga.')
    out.insert(6, f'! {barras_limitadas} barras tiveram a GD limitada a '
                  f'capacidade do transformador ({kw_cortado:,.0f} kW cortados).')
    out.insert(7, f'! inversores em pf={fp:g} — ver o docstring de _pv: 0,92 e '
                  f'capacidade exigida pelo PRODIST, nao despacho.')
    out.insert(8, f'! {por_ceg} unidades de MT ligadas pelo PAC da carga '
                  f'(casadas por CEG_GD): o PAC da UGMT nao existe na SSDMT.')
    open(caminho, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return (n, nulos, realocados, sem_rede, barras_limitadas,
            round(kw_cortado, 1), por_ceg)


def _pv(cod, bus, nf, kv, pot, irrad=1.0, fp=1.0):
    """Um PVSystem.

    O FATOR DE POTENCIA E UNITARIO POR PADRAO. O valor anterior, 0,92, e a
    CAPACIDADE que o Modulo 3 do PRODIST exige do inversor — nao o despacho.
    Em campo o inversor opera em fator unitario, salvo solicitacao expressa da
    distribuidora para suporte de reativo.

    A diferenca nao e cosmetica: a 0,92 cada MW de geracao injeta 430 kvar, a
    tensao sobe, o inversor injeta mais e a realimentacao estoura o fluxo.
    Medido em MODELOS_V6: DEMB e DJAN divergiam com Vmax de 1e+69 e 1e+52; com
    fator unitario convergem em 37 iteracoes. Para estudar suporte de reativo,
    use --gd-fp.
    """
    return (f'New PVSystem.GD_{cod} phases={nf} '
            f'bus1={bus} conn=wye kv={kv:.4f} pf={fp:g} '
            f'pmpp={pot:.2f} kva={max(pot, 0.1):.2f} irradiance={irrad:g} temperature=25 '
            f'%cutin=20 %cutout=20 effcurve=MyEff P-TCurve=MyPvsT '
            f'Daily=IRRAD_DIA TDaily=TEMP_DIA')


def xycurves(caminho):
    open(caminho, 'w', encoding='utf-8').write(XYCURVES)
