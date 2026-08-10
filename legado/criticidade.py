# -*- coding: utf-8 -*-
"""
CHECK DE CRITICIDADE — carregamento por alimentador nos modelos corrigidos.

Para cada alimentador (zona delimitada pelas chaves normalmente abertas):
  - identifica o CTMT e o EQ-TR que o alimenta
  - mede a corrente de cabeceira ao longo do dia (96 passos de 15 min)
  - divide pela ampacidade do tronco (maior normamps entre os trechos com LineCode)
  - classifica nas faixas da Figura 2: 101-110 / 111-120 / 121-130 / >=131 %
"""
import os, re, sys, json, math, collections
import opendssdirect as dss

COR = '/sessions/relaxed-sweet-turing/mnt/Criticidades/_CORRIGIDO'
OUT = '/sessions/relaxed-sweet-turing/mnt/outputs'
RAIZ = {'DBSI': '2b58bee', 'DCAM': '2b58caf', 'DEMB': '2b58b2c', 'DGNA': '2b58dfe'}


def logical(p):
    out = []
    for r in open(p, encoding='latin-1', errors='replace'):
        s = r.split('!')[0].strip()
        if not s:
            continue
        if s.startswith('~'):
            if out:
                out[-1] += ' ' + s[1:].strip()
        else:
            out.append(s)
    return out


def zonas_do_modelo(d, se):
    """Zonas (alimentadores) delimitadas pelas chaves NA, com CTMT e ampacidade de tronco."""
    amp_lc = {}
    for ln in logical(os.path.join(d, 'LineCodes.dss')):
        m = re.match(r'New\s+Linecode\.(\S+)', ln, re.I)
        if m:
            a = re.search(r'normamps\s*=\s*([\d\.]+)', ln, re.I)
            amp_lc[m.group(1).lower()] = float(a.group(1)) if a else 0.0
    abertas = set()
    fc = os.path.join(d, f'CHAVES-CONTROLE-MT-{se}.dss')
    if os.path.exists(fc):
        for ln in logical(fc):
            if re.search(r'State\s*=\s*open', ln, re.I):
                m = re.search(r'SwitchedObj\s*=\s*Line\.(\S+)', ln, re.I)
                if m:
                    abertas.add(m.group(1).lower())
    adj = collections.defaultdict(set)
    amp_bus = collections.defaultdict(float)   # ampacidade do trecho com LineCode
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
            b1 = m1.group(1).split('.')[0].lower()
            b2 = m2.group(1).split('.')[0].lower()
            adj[b1].add(b2); adj[b2].add(b1)
            lc = re.search(r'LineCode\s*=\s*(\S+)', ln, re.I)
            nph = len([x for x in m1.group(1).split('.')[1:] if x != '0'])
            if lc and nph >= 3:                       # so tronco trifasico
                nome_lc = lc.group(1).lower()
                a = amp_lc.get(nome_lc, 0.0)
                # LineCodes "0_x" sao trechos ficticios de impedancia nula com
                # normamps=999; nao representam condutor e nao servem de referencia
                if nome_lc.startswith('0_') or a >= 999:
                    continue
                amp_bus[b1] = max(amp_bus[b1], a); amp_bus[b2] = max(amp_bus[b2], a)
    # EQ-TR -> barra secundaria
    eq = {}
    txt = open(os.path.join(d, f'MASTER-{se}.dss'), encoding='latin-1').read()
    for m in re.finditer(r'New\s+Transformer\.(\S*EQ-TR\d+)(.*?)(?=New\s+Transformer|redirect|$)',
                         txt, re.I | re.S):
        b2 = re.findall(r'wdg=2\s+bus=([\w\-\.]+)', m.group(2), re.I)
        if b2:
            eq[m.group(1).lower()] = b2[0].split('.')[0].lower()
    vistos, zonas = set(), []
    for x in list(adj):
        if x in vistos:
            continue
        pilha, comp = [x], set()
        while pilha:
            y = pilha.pop()
            if y in comp:
                continue
            comp.add(y); vistos.add(y)
            pilha.extend(adj[y] - comp)
        zonas.append(comp)
    pct = re.compile(r'_([a-z]{3}\d{4})$')
    saida = {}
    for c in zonas:
        trs = [t for t, b in eq.items() if b in c]
        if not trs:
            continue
        ct = sorted({pct.search(b).group(1) for b in c if pct.search(b)})
        amax = max((amp_bus[b] for b in c if b in amp_bus), default=0.0)
        for t in trs:
            saida[t] = {'ctmt': ct[0].upper() if ct else '(sem CTMT)',
                        'barras': len(c), 'Inom_tronco': round(amax, 1)}
    return saida


def rodar(se, cen='DU'):
    d = f'{COR}/{se}_{cen}'
    info = zonas_do_modelo(d, se)
    dss.Text.Command('Clear')
    dss.Text.Command(f'Compile "{d}/MASTER-{se}.dss"')
    # Os PV de BT desestabilizam o regime diario (ver ressalva no relatorio).
    # Sao desabilitados; os PV de MT permanecem ativos.
    n_off, kwp_off = 0, 0.0
    for p in dss.PVsystems.AllNames():
        dss.Circuit.SetActiveElement('PVSystem.' + p)
        if dss.CktElement.BusNames()[0].lower().split('.')[0].endswith('l'):
            dss.PVsystems.Name(p); kwp_off += dss.PVsystems.Pmpp()
            dss.Circuit.SetActiveElement('PVSystem.' + p)
            dss.CktElement.Enabled(False); n_off += 1
    dss.Text.Command('Set mode=daily'); dss.Text.Command('Set stepsize=15m')
    dss.Text.Command('Set number=1'); dss.Text.Command('Set controlmode=static')
    dss.Solution.Hour(0); dss.Solution.Seconds(0)
    eq = [t for t in dss.Transformers.AllNames() if 'eq-tr' in t.lower()]
    reg = {t: {'I': [], 'kW': []} for t in eq}
    nconv = 0
    for _ in range(96):
        try:
            dss.Solution.Solve()
        except Exception:
            pass
        if not dss.Solution.Converged():
            nconv += 1
        for t in eq:
            dss.Circuit.SetActiveElement('Transformer.' + t)
            c = dss.CktElement.CurrentsMagAng(); n = dss.CktElement.NumConductors()
            # terminal 2 = secundario de 13,8 kV
            im = max(c[2 * n + 2 * i] for i in range(n))
            p = dss.CktElement.Powers()
            kw = -sum(p[2 * n + 2 * i] for i in range(n))
            reg[t]['I'].append(im); reg[t]['kW'].append(kw)
    res = []
    for t in eq:
        d0 = info.get(t.lower())
        if not d0:
            continue
        na = d0['Inom_tronco']
        I = [x for x in reg[t]['I'] if not math.isnan(x)]
        K = [x for x in reg[t]['kW'] if not math.isnan(x)]
        if not I or na <= 0:
            continue
        car = [100 * x / na for x in I]
        n = len(car)
        r = {'SE': se, 'alimentador': d0['ctmt'], 'EQ_TR': t.upper(),
             'barras': d0['barras'], 'Inom_A': na,
             'I_max_A': round(max(I), 1), 'I_med_A': round(sum(I) / n, 1),
             'kW_max': round(max(K), 1) if K else None,
             'carreg_max': round(max(car), 1), 'carreg_med': round(sum(car) / n, 1),
             'h_ponta': round(car.index(max(car)) * 0.25, 2),
             'f_101_110': round(100 * sum(1 for x in car if 101 <= x < 111) / n, 1),
             'f_111_120': round(100 * sum(1 for x in car if 111 <= x < 121) / n, 1),
             'f_121_130': round(100 * sum(1 for x in car if 121 <= x < 131) / n, 1),
             'f_131_mais': round(100 * sum(1 for x in car if x >= 131) / n, 1),
             'tempo_acima_100': round(100 * sum(1 for x in car if x > 100) / n, 1),
             'perfil': [round(x, 1) for x in car]}
        res.append(r)
    return res, {"passos_nao_convergidos": nconv, "PV_BT_desabilitados": n_off, "kWp_BT_fora": round(kwp_off,1)}


if __name__ == '__main__':
    todos, meta = [], {}
    for se in (sys.argv[1:] or ['DBSI', 'DCAM', 'DEMB', 'DGNA']):
        r, nc = rodar(se)
        todos += r
        nc["alimentadores"] = len(r); meta[se] = nc
        print(f'{se}: {len(r)} alim | {nc}', flush=True)
        json.dump({'alimentadores': todos, 'meta': meta},
                  open(f'{OUT}/criticidade_{"_".join(sys.argv[1:]) or "todos"}.json', 'w'),
                  indent=1, ensure_ascii=False)
    print('FIM')
