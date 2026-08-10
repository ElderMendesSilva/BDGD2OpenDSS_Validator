# -*- coding: utf-8 -*-
"""Carregamento por alimentador nos modelos corrigidos (regime diario, 96 passos)."""
import os, re, sys, json, math, collections
import opendssdirect as dss

COR = os.environ.get('DEST_CORRIGIDO', '/sessions/relaxed-sweet-turing/tmp/COR')
OUT = '/sessions/relaxed-sweet-turing/mnt/outputs'
FAIXAS = [(100, 110), (110, 120), (120, 130), (130, 1e9)]


def rodar(se, cen='DU', sem_pv_bt=False):
    m = f'{COR}/{se}_{cen}/MASTER-{se}.dss'
    dss.Text.Command('Clear')
    dss.Text.Command(f'Compile "{m}"')
    if sem_pv_bt:
        n = 0
        for p in dss.PVsystems.AllNames():
            dss.Circuit.SetActiveElement('PVSystem.' + p)
            if dss.CktElement.BusNames()[0].lower().split('.')[0].endswith('l'):
                dss.CktElement.Enabled(False); n += 1
        print(f'   [{se}] {n} PV de BT desabilitados', flush=True)

    # mapa alimentador -> EQ-TR, a partir dos comentarios gerados pelo corretor
    rot = {}
    txt = open(m, encoding='latin-1').read()
    for mm in re.finditer(r'!\s*alimentador\s+(\S+).*?\n\s*New Transformer\.(\S+)', txt, re.I):
        rot[mm.group(2).lower()] = mm.group(1)

    eq = [t for t in dss.Transformers.AllNames() if 'eq-tr' in t.lower()]
    heads = {}
    for tr in eq:
        dss.Circuit.SetActiveElement('Transformer.' + tr)
        s = dss.CktElement.BusNames()[1].split('.')[0].lower()
        outs = []
        for ln in dss.Lines.AllNames():
            dss.Lines.Name(ln)
            if s in (dss.Lines.Bus1().split('.')[0].lower(), dss.Lines.Bus2().split('.')[0].lower()):
                if dss.Lines.NormAmps() > 1:
                    outs.append(ln)
        heads[tr] = outs

    dss.Text.Command('Set mode=daily'); dss.Text.Command('Set stepsize=15m')
    dss.Text.Command('Set number=1'); dss.Text.Command('Set controlmode=static')
    dss.Solution.Hour(0); dss.Solution.Seconds(0)

    reg = {t: {'car': [], 'kw': [], 'amp': []} for t in eq}
    vmin = []
    nconv = 0
    for k in range(96):
        try:
            dss.Solution.Solve()
        except Exception:
            pass
        if not dss.Solution.Converged():
            nconv += 1
        for t in eq:
            a, na = 0.0, 0.0
            for ln in heads[t]:
                dss.Circuit.SetActiveElement('Line.' + ln)
                c = dss.CktElement.CurrentsMagAng(); nc = dss.CktElement.NumConductors()
                im = max(c[2 * i] for i in range(nc))
                if im > a:
                    a, na = im, dss.CktElement.NormalAmps()
            dss.Circuit.SetActiveElement('Transformer.' + t)
            p = dss.CktElement.Powers(); nc = dss.CktElement.NumConductors()
            kw = -sum(p[2 * nc + 2 * i] for i in range(nc))
            reg[t]['amp'].append(a)
            reg[t]['kw'].append(kw)
            reg[t]['car'].append(100 * a / na if na else 0.0)
        v = [x for x in dss.Circuit.AllBusMagPu() if 0.01 < x < 2]
        if v:
            vmin.append(min(v))

    res = []
    for t in eq:
        car = [c for c in reg[t]['car'] if not math.isnan(c)]
        kw = [k for k in reg[t]['kw'] if not math.isnan(k)]
        if not car:
            continue
        d = {'SE': se, 'EQ_TR': t.upper(), 'alimentador': rot.get(t.lower(), '(original)'),
             'I_max_A': round(max(reg[t]['amp']), 1),
             'kW_max': round(max(kw), 1) if kw else None,
             'kW_med': round(sum(kw) / len(kw), 1) if kw else None,
             'carreg_max_pct': round(max(car), 1),
             'carreg_med_pct': round(sum(car) / len(car), 1),
             'h_ponta': round(car.index(max(car)) * 0.25, 2)}
        for lo, hi in FAIXAS:
            n = sum(1 for c in car if lo <= c < hi)
            d[f'tempo_{lo}_{"mais" if hi > 1000 else hi}'] = round(100 * n / len(car), 1)
        d['tempo_acima_100'] = round(100 * sum(1 for c in car if c >= 100) / len(car), 1)
        res.append(d)
    return res, {'passos_nao_convergidos': nconv,
                 'V_pu_min': round(min(vmin), 4) if vmin else None}


if __name__ == '__main__':
    saida, meta = [], {}
    for se in (sys.argv[1:] or ['DBSI', 'DCAM', 'DEMB', 'DGNA']):
        r, mt = rodar(se, 'DU', sem_pv_bt=(se == 'DGNA'))
        saida += r
        meta[se] = mt
        print(f'{se}: {len(r)} alimentadores | {mt}', flush=True)
        json.dump({'alimentadores': saida, 'meta': meta},
                  open(f'{OUT}/carregamento_{"_".join(sys.argv[1:]) or "todos"}.json', 'w'),
                  indent=1, ensure_ascii=False)
    print('FIM')
