# -*- coding: utf-8 -*-
"""
CORRETOR DOS MODELOS BDGD -> OpenDSS
===================================
Le os modelos originais da pasta Criticidades e grava uma versao corrigida em
<Criticidades>/_CORRIGIDO/<SE>_<CEN>/, sem alterar os arquivos originais.

Correcoes aplicadas
-------------------
C1  Gera um transformador equivalente de subestacao (EQ-TR) para cada alimentador
    que esteja sem fonte, conectado a barra do arranjo de saida da subestacao.
C2  Converte os transformadores de distribuicao monofasicos para 3 enrolamentos
    com derivacao central, colocando o neutro no no 4 (que as cargas ja usam).
C3  Coloca o neutro dos transformadores trifasicos de BT no no 4.
C4  Corrige a tensao nominal das cargas e PV de BT para a do enrolamento que os alimenta.
C5  Corrige transformadores do DCAM com primario 3,8 kV para 13,8 kV.
C6  Cria as XYCurve MyEff e MyPvsT ausentes.
C7  Cria arquivos-stub para os redirects sem arquivo (reguladores DBSI/DCAM, PV-MT DBSI).
C8  Remove monitores que apontam para elementos inexistentes.
C9  Amplia Set Voltagebases com os niveis de baixa tensao.
C10 Eleva MaxControlIter e retira Solve/Show do MASTER.
C11 Fixa o estado das chaves normalmente abertas.
C12 Corrige tensao, potencia e ajuste dos reguladores de tensao.
C13 Desabilita PVSystem com potencia nula (gera NaN na solucao).
C14 Converte a curva de irradiancia de W/m2 para pu (divide por 1000).

Uso:  python3 corrigir_modelos.py [SE ...]
"""
import os, re, sys, math, json, shutil, collections

BASE = '/sessions/relaxed-sweet-turing/mnt/Criticidades'
DEST = os.environ.get('DEST_CORRIGIDO', os.path.join(BASE, '_CORRIGIDO'))
SES = ['DBSI', 'DCAM', 'DEMB', 'DGNA']
CENARIOS = ['DU', 'SA', 'DO']
# raiz do nome das barras do arranjo da subestacao
RAIZ = {'DBSI': '2b58bee', 'DCAM': '2b58caf', 'DEMB': '2b58b2c', 'DGNA': '2b58dfe'}
VBASES = 'Set Voltagebases=[88 13.8 0.44 0.38 0.24 0.22 0.208 0.127 0.11]'
XY = ('! Curvas do inversor e do modulo fotovoltaico.\n'
      '! Valores informados pela area tecnica (nao sao estimativa do corretor).\n'
      '! Faltavam no pacote original e impediam a compilacao dos arquivos de PV.\n'
      'New XYCurve.MyPvsT npts=4 xarray=[0 25 75 100] yarray=[1.2 1.0 0.8 0.6]\n'
      'New XYCurve.MyEff  npts=4 xarray=[0.1 0.2 0.4 1.0] yarray=[0.86 0.90 0.93 0.97]\n')


# ----------------------------------------------------------------- utilitarios
def logical(path):
    """Le um .dss juntando as linhas de continuacao (~) e removendo comentarios."""
    out = []
    for raw in open(path, encoding='latin-1', errors='replace'):
        s = raw.split('!')[0].strip()
        if not s:
            continue
        if s.startswith('~'):
            if out:
                out[-1] += ' ' + s[1:].strip()
        else:
            out.append(s)
    return out


def base(b):
    return b.split('.')[0].lower()


def nodes(b):
    return b.split('.')[1:]


def fnum(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


# ------------------------------------------------------- C1: zonas e cabeceiras
def mapear_zonas(d, se):
    """Devolve (zonas, cabecalhos, eq_existentes). Zona = alimentador delimitado
    pelas chaves normalmente abertas."""
    # linecodes -> ampacidade
    amp_lc = {}
    for ln in logical(os.path.join(d, 'LineCodes.dss')):
        m = re.match(r'New\s+Linecode\.(\S+)', ln, re.I)
        if m:
            a = re.search(r'normamps\s*=\s*([\d\.]+)', ln, re.I)
            amp_lc[m.group(1).lower()] = fnum(a.group(1)) if a else 0.0
    # chaves normalmente abertas
    abertas = set()
    f = os.path.join(d, f'CHAVES-CONTROLE-MT-{se}.dss')
    if os.path.exists(f):
        for ln in logical(f):
            if re.search(r'State\s*=\s*open', ln, re.I):
                m = re.search(r'SwitchedObj\s*=\s*Line\.(\S+)', ln, re.I)
                if m:
                    abertas.add(m.group(1).lower())
    adj = collections.defaultdict(list)
    for arq in [f'LINHAS-MT-{se}.dss', f'CHAVES-MT-{se}.dss']:
        p = os.path.join(d, arq)
        if not os.path.exists(p):
            continue
        for ln in logical(p):
            nm = re.match(r'New\s+Line\.(\S+)', ln, re.I)
            if not nm or nm.group(1).lower() in abertas:
                continue
            m1 = re.search(r'Bus1\s*=\s*([\w\-\.]+)', ln, re.I)
            m2 = re.search(r'Bus2\s*=\s*([\w\-\.]+)', ln, re.I)
            if not (m1 and m2):
                continue
            lc = re.search(r'LineCode\s*=\s*(\S+)', ln, re.I)
            a = amp_lc.get(lc.group(1).lower(), 0.0) if lc else 400.0
            ph = len([x for x in nodes(m1.group(1)) if x != '0'])
            adj[base(m1.group(1))].append((base(m2.group(1)), a, ph, m1.group(1)))
            adj[base(m2.group(1))].append((base(m1.group(1)), a, ph, m2.group(1)))
    # EQ-TR ja existentes
    eq = {}
    for ln in logical(os.path.join(d, f'MASTER-{se}.dss')):
        if re.search(r'wdg\s*=\s*2', ln, re.I) and 'eq-tr' in ln.lower():
            pass
    txt = open(os.path.join(d, f'MASTER-{se}.dss'), encoding='latin-1').read()
    for m in re.finditer(r'New\s+Transformer\.(\S*EQ-TR\d+)(.*?)(?=New\s+Transformer|redirect|$)',
                         txt, re.I | re.S):
        b2 = re.findall(r'wdg=2\s+bus=([\w\-\.]+)', m.group(2), re.I)
        if b2:
            eq[base(b2[0])] = m.group(1)
    # componentes conexas
    vistos = set()
    zonas = []
    for x in list(adj):
        if x in vistos:
            continue
        pilha, comp = [x], set()
        while pilha:
            y = pilha.pop()
            if y in comp:
                continue
            comp.add(y); vistos.add(y)
            pilha.extend(z for z, _, _, _ in adj[y] if z not in comp)
        zonas.append(comp)
    zonas.sort(key=len, reverse=True)

    pse = re.compile(rf'{RAIZ[se]}[abm]$')
    pct = re.compile(r'_([a-z]{3}\d{4})$')
    info = []
    for c in zonas:
        tem = [b for b in c if b in eq]
        ct = sorted({pct.search(b).group(1) for b in c if pct.search(b)})
        cand = [b for b in c if pse.search(b)]
        # cabeceira: barra do arranjo da SE com maior ampacidade incidente;
        # empate resolvido pela barra de maior grau
        cab = None
        if cand:
            cab = max(cand, key=lambda b: (max((a for _, a, _, _ in adj[b]), default=0), len(adj[b])))
        elif c:
            cab = max(c, key=lambda b: (max((a for _, a, _, _ in adj[b]), default=0), len(adj[b])))
        # numero de fases e especificacao de nos da cabeceira
        nph, spec = 3, None
        if cab:
            viz = adj[cab]
            nph = max((p for _, _, p, _ in viz), default=3)
            spec = max(viz, key=lambda t: t[2])[3] if viz else f'{cab}.1.2.3'
        info.append({'barras': len(c), 'ctmt': ct, 'eq': tem, 'cabeceira': cab,
                     'fases': nph, 'spec': spec, 'zona': c})
    return info, eq


# ---------------------------------------------------------------- C2/C3/C4/C5
def corrigir_trafos_e_cargas(dst, se, log):
    """Reescreve TRAFOS-MT e os arquivos de carga/PV de BT."""
    # 1) descobre os nos que cargas e PV usam em cada barra de BT
    usados = collections.defaultdict(set)
    arqs_bt = [f for f in os.listdir(dst)
               if f.startswith('EQUIVALENTE-UCBT-') or f.startswith('PV-BT-')]
    for f in arqs_bt:
        for ln in logical(os.path.join(dst, f)):
            m = re.search(r'Bus1\s*=\s*([\w\-\.]+)', ln, re.I)
            if m:
                usados[base(m.group(1))].update(nodes(m.group(1)))

    # 1b) quantos transformadores compartilham cada barra secundaria (bancos trifasicos de BT)
    banco = collections.Counter()
    ordem = collections.defaultdict(list)
    for ln in logical(os.path.join(dst, f'TRAFOS-MT-{se}.dss')):
        if not ln.lower().startswith('new transformer'):
            continue
        bs = re.findall(r'bus\s*=\s*([\w\-\.]+)', ln, re.I)
        if len(bs) > 1:
            banco[base(bs[1])] += 1
            ordem[base(bs[1])].append(re.match(r'New\s+Transformer\.(\S+)', ln, re.I).group(1))

    # 2) reescreve os transformadores
    tp = os.path.join(dst, f'TRAFOS-MT-{se}.dss')
    novo, sec = [], {}
    for ln in logical(tp):
        if not ln.lower().startswith('new transformer'):
            novo.append(ln); continue
        nome = re.match(r'New\s+Transformer\.(\S+)', ln, re.I).group(1)
        # C5 - primario 3,8 kV
        if re.search(r'wdg=1[^~]*?Kv=3\.8\b', ln, re.I):
            ln = re.sub(r'(wdg=1\s+bus=\S+\s+conn=\w+\s+Kv=)3\.8\b', r'\g<1>13.8', ln, flags=re.I)
            log['C5_primario_3,8kV_para_13,8kV'] += 1
        buses = re.findall(r'bus\s*=\s*([\w\-\.]+)', ln, re.I)
        kvs = re.findall(r'\bKv\s*=\s*([\d\.]+)', ln, re.I)
        kvas = re.findall(r'\bKva\s*=\s*([\d\.]+)', ln, re.I)
        conns = re.findall(r'\bconn\s*=\s*(\w+)', ln, re.I)
        taps = re.findall(r'\btap\s*=\s*([\d\.]+)', ln, re.I)
        if len(buses) < 2 or len(kvs) < 2:
            novo.append(ln); continue
        b2, kv2 = buses[1], fnum(kvs[1])
        bb = base(b2)
        n2 = [n for n in nodes(b2) if n != '0']
        nu = usados.get(bb, set())
        # reconstroi o secundario quando as cargas usam o no 4 OU quando ha mais de
        # uma unidade na mesma barra (banco): sem isso as unidades ficam em paralelo
        # entre fases diferentes da MT atraves dos secundarios.
        # Todo secundario de BT e reconstruido, tenha ou nao carga hoje: se a carga
        # for adicionada depois (ex.: extracao da BDGD), o no 4 ja existe.
        precisa4 = True

        if not precisa4:
            novo.append(ln)
            sec[bb] = {'kv_carga': kv2 if len(n2) < 3 else round(kv2 / math.sqrt(3), 4),
                       'nos': nodes(b2), 'trifasico': len(n2) >= 3}
            continue

        kva = kvas[1] if len(kvas) > 1 else (kvas[0] if kvas else '100')
        tap = taps[-1] if taps else '1.0'
        xhl = re.search(r'Xhl\s*=\s*([\d\.]+)', ln, re.I)
        xhl = xhl.group(1) if xhl else '2.0'
        c1 = conns[0] if conns else 'wye'
        kv1 = kvs[0]
        b1 = buses[0]

        if len(n2) >= 3:
            # C3 - trifasico: neutro passa do no 0 para o no 4
            novo_b2 = f'{bb}.1.2.3.4'
            ln = (f'New Transformer.{nome} phases=3 windings=2 Xhl={xhl}\n'
                  f'~ wdg=1 bus={b1} conn={c1} Kv={kv1} Kva={kva} tap={tap}\n'
                  f'~ wdg=2 bus={novo_b2} conn=wye Kv={kv2} Kva={kva} tap={tap}')
            sec[bb] = {'kv_carga': round(kv2 / math.sqrt(3), 4), 'nos': ['1', '2', '3', '4'],
                       'trifasico': True, 'aterrado': True}
            log['C3_trafo_3F_neutro_para_no_4'] += 1
        elif banco[bb] > 1:
            # C2b - banco de monofasicos na mesma barra: cada unidade alimenta uma fase,
            # com neutro comum no no 4 (nao podem ser postos em paralelo entre si)
            k = str(ordem[bb].index(nome) % 3 + 1)
            ln = (f'New Transformer.{nome} phases=1 windings=2 Xhl={xhl}\n'
                  f'~ wdg=1 bus={b1} conn={c1} Kv={kv1} Kva={kva} tap={tap}\n'
                  f'~ wdg=2 bus={bb}.{k}.4 conn=wye Kv={kv2} Kva={kva} tap={tap}')
            ant = sec.get(bb, {}).get('nos', ['4'])
            sec[bb] = {'kv_carga': kv2,
                       'nos': sorted(set(ant) | {k, '4'}),
                       'trifasico': False, 'aterrado': True}
            log['C2b_banco_BT_uma_fase_por_unidade'] += 1
        else:
            # C2 - monofasico isolado: 2 enrolamentos -> 3 enrolamentos com derivacao central
            ln = (f'New Transformer.{nome} phases=1 windings=3 Xhl={xhl} Xht={xhl} Xlt={float(xhl)/2:.4f}\n'
                  f'~ wdg=1 bus={b1} conn={c1} Kv={kv1} Kva={kva} tap={tap}\n'
                  f'~ wdg=2 bus={bb}.1.4 conn=wye Kv={kv2} Kva={kva} tap={tap}\n'
                  f'~ wdg=3 bus={bb}.4.2 conn=wye Kv={kv2} Kva={kva} tap={tap}')
            sec[bb] = {'kv_carga': kv2, 'nos': ['1', '2', '4'], 'trifasico': False,
                       'aterrado': True}
            log['C2_trafo_1F_para_derivacao_central'] += 1
        novo.append(ln)
    # aterramento do neutro (no 4) dos secundarios reconstruidos
    ater = [f'! Aterramento do neutro dos secundarios de BT (no 4) - {se}']
    for bb, s in sec.items():
        if s.get('aterrado'):
            ater.append(f'New Reactor.NEUTRO_{bb} phases=1 bus1={bb}.4 bus2={bb}.0 R=0.5 X=0')
            log['C2_aterramento_de_neutro_criado'] += 1
    open(os.path.join(dst, '_ATERRAMENTO.dss'), 'w', encoding='latin-1').write('\n'.join(ater) + '\n')
    open(tp, 'w', encoding='latin-1').write('\n'.join(novo) + '\nredirect _ATERRAMENTO.dss\n')

    # 3) C4 - ajusta nos e tensao nominal das cargas e PV de BT ao enrolamento real
    for f in arqs_bt:
        p = os.path.join(dst, f)
        out = []
        for ln in logical(p):
            m = re.search(r'Bus1\s*=\s*([\w\-\.]+)', ln, re.I)
            if not m or not ln.lower().startswith('new'):
                out.append(ln); continue
            b = m.group(1); s = sec.get(base(b))
            if not s:
                log['C4_elemento_BT_sem_trafo'] += 1
                out.append(ln); continue
            disp = [n for n in s['nos'] if n not in ('0', '4')]   # pernas vivas do enrolamento
            ns = [n for n in nodes(b) if n not in ('0', '4')]     # fases pedidas pelo elemento
            # o no 0 (terra) so e terminal valido se o enrolamento realmente o oferece
            falta = [n for n in nodes(b) if n not in s['nos']]
            if falta and not s.get('aterrado'):
                # enrolamento nao convertido: liga o elemento nos proprios terminais dele
                b_novo = base(b) + '.' + '.'.join(s['nos'])
                ln = re.sub(r'(Bus1\s*=\s*)[\w\-\.]+', lambda mm: mm.group(1) + b_novo,
                            ln, count=1, flags=re.I)
                ln = re.sub(r'(\bPhases\s*=\s*)\d+', r'\g<1>1', ln, flags=re.I)
                log['C4_nos_de_elemento_BT_remapeados'] += 1
                falta = []
            if falta:
                # remapeia para os nos realmente energizados, preservando a ordem das fases
                novos = []
                for i, n in enumerate(ns):
                    novos.append(n if n in s['nos'] else disp[i % len(disp)])
                # elimina repeticoes mantendo a ordem
                vistos, limpo = set(), []
                for n in novos:
                    if n not in vistos:
                        vistos.add(n); limpo.append(n)
                if '4' not in limpo:
                    limpo.append('4')
                b_novo = base(b) + '.' + '.'.join(limpo)
                ln = re.sub(r'(Bus1\s*=\s*)[\w\-\.]+', lambda mm: mm.group(1) + b_novo,
                            ln, count=1, flags=re.I)
                nf = len([n for n in limpo if n != '4'])
                ln = re.sub(r'(\bPhases\s*=\s*)\d+', lambda mm: mm.group(1) + str(max(nf, 1)),
                            ln, flags=re.I)
                log['C4_nos_de_elemento_BT_remapeados'] += 1
            mkv = re.search(r'\bkv\s*=\s*([\d\.]+)', ln, re.I)
            if mkv and abs(fnum(mkv.group(1)) - s['kv_carga']) > 1e-6:
                ln = re.sub(r'(\bkv\s*=\s*)[\d\.]+',
                            lambda mm: mm.group(1) + f"{s['kv_carga']:.4f}", ln, count=1, flags=re.I)
                log['C4_kV_de_elemento_BT_corrigido'] += 1
            out.append(ln)
        open(p, 'w', encoding='latin-1').write('\n'.join(out) + '\n')
    return sec


# ------------------------------------------------- C14: curva de irradiancia em pu
def corrigir_irradiancia(dst, se, log):
    """A LoadShape de irradiancia e exportada em W/m2 (pico ~870), mas o PVSystem a
    usa como multiplicador em pu da irradiancia nominal. Sem normalizar, cada PV
    injeta centenas de vezes a potencia nominal e o fluxo diario diverge.
    Converte-se para pu dividindo por 1000 W/m2 (condicao padrao de ensaio)."""
    for f in sorted(os.listdir(dst)):
        if not f.upper().startswith('TEMP_IRR_'):
            continue
        p = os.path.join(dst, f)
        txt = open(p, encoding='latin-1', errors='replace').read()

        def norm(m):
            vals = [fnum(x) for x in m.group(2).split()]
            if not vals or max(vals) <= 1.5:      # ja esta em pu
                return m.group(0)
            novos = ' '.join(f'{v / 1000.0:.6f}' for v in vals)
            log['C14_curva_de_irradiancia_convertida_para_pu'] += 1
            return f'{m.group(1)}[ {novos} ]'

        txt = re.sub(r'(New\s+Loadshape\.PVIrrad\S*[^\[]*?mult\s*=\s*)\[([^\]]*)\]',
                     norm, txt, flags=re.I | re.S)
        open(p, 'w', encoding='latin-1').write(txt)


# --------------------------------------------------------- C13: PV com kVA nulo
def corrigir_pv_nulos(dst, se, log):
    """PVSystem com pmpp=0 ou kva=0 gera divisao por zero na montagem da matriz e
    contamina toda a solucao com NaN. Sao desabilitados, nao removidos."""
    for arq in [f'PV-MT-{se}.dss', f'PV-BT-{se}.dss']:
        p = os.path.join(dst, arq)
        if not os.path.exists(p):
            continue
        out = []
        for ln in logical(p):
            if ln.lower().startswith('new') and 'pvsystem' in ln.lower():
                pm = re.search(r'pmpp\s*=\s*([\d\.]+)', ln, re.I)
                kva = re.search(r'\bkva\s*=\s*([\d\.]+)', ln, re.I)
                if (pm and fnum(pm.group(1)) <= 0) or (kva and fnum(kva.group(1)) <= 0):
                    ln = ('! DESABILITADO pelo corretor: pmpp/kva nulo gera NaN na solucao\n'
                          '! ' + ln)
                    log['C13_PV_com_potencia_nula_desabilitado'] += 1
            out.append(ln)
        open(p, 'w', encoding='latin-1').write('\n'.join(out) + '\n')


# ------------------------------------------------------------ C12: reguladores
def corrigir_reguladores(dst, se, log):
    """Os reguladores sao exportados com tensao de enrolamento fase-fase, potencia
    irrisoria (36 kVA) e vreg/ptratio incoerentes, o que impede a convergencia."""
    p = os.path.join(dst, f'REGULADORES-MT-{se}.dss')
    if not os.path.exists(p):
        return
    out = []
    for ln in logical(p):
        low = ln.lower()
        if low.startswith('new transformer') and 'reg_' in low:
            nf = re.search(r'phases\s*=\s*(\d)', ln, re.I)
            nf = int(nf.group(1)) if nf else 1
            kv = 13.8 / math.sqrt(3) if nf == 1 else 13.8
            ln = re.sub(r'kVs\s*=\s*\[[^\]]*\]', f'kVs=[{kv:.4f} {kv:.4f}]', ln, flags=re.I)
            ln = re.sub(r'kVAs\s*=\s*\[[^\]]*\]', 'kVAs=[5000 5000]', ln, flags=re.I)
            log['C12_regulador_kV_e_kVA_corrigidos'] += 1
        elif low.startswith('new regcontrol'):
            # TP de 13,8/sqrt(3) kV para 120 V -> ptratio = 66,4 ; alvo 122 V (1,017 pu)
            ln = re.sub(r'vreg\s*=\s*[\d\.]+', 'vreg=122', ln, flags=re.I)
            ln = re.sub(r'ptratio\s*=\s*[\d\.]+', 'ptratio=66.4', ln, flags=re.I)
            ln = re.sub(r'band\s*=\s*[\d\.]+', 'band=2', ln, flags=re.I)
            log['C12_RegControl_vreg_e_ptratio_corrigidos'] += 1
        out.append(ln)
    open(p, 'w', encoding='latin-1').write('\n'.join(out) + '\n')


# ------------------------------------------------------------------ C1 + master
def corrigir_master(dst, se, zonas, eq, log):
    mp = os.path.join(dst, f'MASTER-{se}.dss')
    txt = open(mp, encoding='latin-1').read()

    # C7 - stubs
    arquivos = {f.lower() for f in os.listdir(dst)}
    for r in re.findall(r'(?im)^\s*redirect\s+(\S+)', txt):
        if r.lower() not in arquivos:
            open(os.path.join(dst, r), 'w').write(
                f'! STUB gerado pelo corretor - "{r}" nao existe no pacote original.\n'
                f'! Solicitar o arquivo a quem gera a exportacao BDGD.\n')
            log[f'C7_stub_{r}'] += 1

    # C6 - XYCurves
    open(os.path.join(dst, '_XYCURVES.dss'), 'w').write(XY)
    txt = txt.replace('redirect LineCodes.dss', 'redirect _XYCURVES.dss\nredirect LineCodes.dss')
    log['C6_XYCurve_MyEff_MyPvsT'] += 2

    # C1 - EQ-TR para as zonas sem fonte
    novos, criados = [], []
    n = max([int(x) for t in eq.values() for x in re.findall(r'EQ-TR(\d+)', t.upper())] or [0])
    for z in zonas:
        if z['eq'] or not z['cabeceira']:
            continue
        if z['barras'] < 5:          # fragmentos residuais, nao sao alimentadores
            log['C1_zona_residual_ignorada'] += 1
            continue
        n += 1
        rot = (z['ctmt'][0].upper() if z['ctmt'] else f'Z{n}')
        nome = f'{se}-EQ-TR{n}'
        nos = '.1.2.3' if z['fases'] >= 3 else ('.' + '.'.join(nodes(z['spec'])) if z['spec'] else '.1')
        ph = 3 if z['fases'] >= 3 else z['fases']
        novos.append(
            f'! alimentador {rot} - {z["barras"]} barras - fonte criada pelo corretor\n'
            f'New Transformer.{nome} Phase={ph} Windings=2 Xhl=0.5\n'
            f'~ wdg=1 bus=SOURCEBUS.1.2.3 conn=delta Kv=88 Kva=20000 %R=0.61 tap=1.03\n'
            f'~ wdg=2 bus={z["cabeceira"]}{nos} conn=wye Kv=13.8 Kva=20000 %R=0.61 tap=1.03\n')
        criados.append({'EQ_TR': nome, 'alimentador': rot, 'barra': z['cabeceira'],
                        'barras_zona': z['barras'], 'fases': ph})
        log['C1_EQ_TR_criado'] += 1
    if novos:
        alvo = 'redirect _XYCURVES.dss'
        txt = txt.replace(alvo, '\n'.join(novos) + '\n' + alvo, 1)

    # C8 - monitores orfaos
    existe = set()
    for f in os.listdir(dst):
        if f.lower().endswith('.dss'):
            for m in re.finditer(r'(?im)^\s*new\s+"?([a-z]+)\.([^"\s]+)',
                                 open(os.path.join(dst, f), encoding='latin-1', errors='replace').read()):
                existe.add(f'{m.group(1).lower()}.{m.group(2).lower()}')
    for c in criados:
        existe.add(f'transformer.{c["EQ_TR"].lower()}')
    keep = []
    for ln in txt.split('\n'):
        m = re.search(r'(?i)new\s+monitor\.\S+.*element\s*=\s*(\S+)', ln)
        if m and m.group(1).lower() not in existe:
            log['C8_monitor_orfao_removido'] += 1
            continue
        keep.append(ln)
    txt = '\n'.join(keep)

    # C11 - fixa o estado das chaves normalmente abertas independentemente do modo de controle
    abertas = []
    fc = os.path.join(dst, f'CHAVES-CONTROLE-MT-{se}.dss')
    if os.path.exists(fc):
        for ln in logical(fc):
            if re.search(r'State\s*=\s*open', ln, re.I):
                mm = re.search(r'SwitchedObj\s*=\s*Line\.(\S+)', ln, re.I)
                if mm:
                    abertas.append(f'Open Line.{mm.group(1)} 1')
    if abertas:
        open(os.path.join(dst, '_CHAVES_ABERTAS.dss'), 'w', encoding='latin-1').write(
            '! Chaves normalmente abertas - estado fixado apos a montagem do circuito\n'
            + '\n'.join(abertas) + '\n')
        txt += '\nredirect _CHAVES_ABERTAS.dss\n'
        log['C11_chaves_NA_abertas_explicitamente'] += len(abertas)

    # C9 / C10
    txt = re.sub(r'(?im)^\s*Set\s+Voltagebases\s*=.*$', VBASES, txt)
    log['C9_Voltagebases_ampliada'] += 1
    txt = re.sub(r'(?im)^\s*show\s+.*$', '', txt)
    txt = re.sub(r'(?im)^\s*solve\s*$', '', txt)
    txt += ('\nSet maxcontroliter=200\nSet maxiterations=50\nSet controlmode=static\n'
            '\n! solucao inicial, recalculo das bases de tensao e solucao definitiva\n'
            'Set mode=snap\nSolve\nCalcVoltagebases\nSolve\n')
    log['C10_MaxControlIter_200'] += 1

    open(mp, 'w', encoding='latin-1').write(txt)
    return criados


# ------------------------------------------------------------------------ main
def corrigir(se, cen):
    src = os.path.join(BASE, se, f'{se}_{cen}')
    dst = os.path.join(DEST, f'{se}_{cen}')
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(src, dst)
    log = collections.Counter()
    zonas, eq = mapear_zonas(dst, se)
    corrigir_trafos_e_cargas(dst, se, log)
    corrigir_reguladores(dst, se, log)
    corrigir_pv_nulos(dst, se, log)
    corrigir_irradiancia(dst, se, log)
    criados = corrigir_master(dst, se, zonas, eq, log)
    return {'SE': se, 'cenario': cen, 'destino': dst, 'log': dict(log),
            'zonas': len(zonas), 'eq_originais': len(eq), 'eq_criados': criados}


if __name__ == '__main__':
    alvo = [a for a in sys.argv[1:] if a in SES] or SES
    res = []
    for se in alvo:
        for cen in CENARIOS:
            r = corrigir(se, cen)
            res.append(r)
            print(f'{se}_{cen}: zonas={r["zonas"]} EQ-TR originais={r["eq_originais"]} '
                  f'criados={len(r["eq_criados"])}', flush=True)
    json.dump(res, open('/sessions/relaxed-sweet-turing/mnt/outputs/correcao_log.json', 'w'),
              indent=1, ensure_ascii=False)
    print('FIM')
