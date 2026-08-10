# -*- coding: utf-8 -*-
"""Corrige os defeitos estruturais dos modelos BDGD->OpenDSS e roda o fluxo de potencia."""
import os, re, json, shutil, math, sys, traceback, collections
import opendssdirect as dss

BASE = '/sessions/relaxed-sweet-turing/mnt/Criticidades'
WORK = '/sessions/relaxed-sweet-turing/tmp/fix'
OUT  = '/sessions/relaxed-sweet-turing/mnt/outputs'

PATCH_XY = """New XYCurve.MyEff  npts=4 xarray=[0.1 0.2 0.4 1.0] yarray=[0.86 0.90 0.93 0.97]
New XYCurve.MyPvsT npts=4 xarray=[0 25 75 100] yarray=[1.2 1.0 0.8 0.6]
"""

def logical(path):
    out = []
    for r in open(path, encoding='latin-1', errors='replace'):
        s = r.split('!')[0].rstrip()
        if not s.strip():
            continue
        if s.strip().startswith('~'):
            if out:
                out[-1] += ' ' + s.strip()[1:].strip()
        else:
            out.append(s.strip())
    return out


def corrigir(se, cen):
    src = os.path.join(BASE, se, f'{se}_{cen}')
    dst = os.path.join(WORK, f'{se}_{cen}')
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    log = collections.Counter()

    # ---------- 1. mapa das barras secundarias dos trafos de distribuicao ----------
    tpath = os.path.join(dst, f'TRAFOS-MT-{se}.dss')
    novos, sec = [], {}
    for ln in logical(tpath):
        if not ln.lower().startswith('new transformer'):
            novos.append(ln); continue
        # 1a) primario 3.8 kV -> 13.8 kV (truncamento na exportacao)
        def fix38(m):
            return m.group(0).replace('3.8', '13.8')
        if re.search(r'wdg=1\s+bus=\S+\s+conn=\w+\s+Kv=3\.8\b', ln, re.I):
            ln = re.sub(r'(wdg=1\s+bus=\S+\s+conn=\w+\s+Kv=)3\.8\b', r'\g<1>13.8', ln, flags=re.I)
            log['trafo_primario_3.8kV_corrigido_para_13.8'] += 1
        buses = re.findall(r'bus\s*=\s*([\w\-\.]+)', ln, re.I)
        kvs = re.findall(r'\bKv\s*=\s*([\d\.]+)', ln, re.I)
        if len(buses) > 1 and len(kvs) > 1:
            b2 = buses[1]; base = b2.split('.')[0].lower()
            nodes = b2.split('.')[1:]
            kv2 = float(kvs[1])
            n_ativos = len([n for n in nodes if n != '0'])
            # tensao de uma carga monofasica ligada nesse enrolamento
            if n_ativos >= 3:
                kv_1f = round(kv2 / math.sqrt(3), 4)
                alvo = [f'{base}.{n}.0' for n in nodes if n != '0']
            else:
                kv_1f = kv2
                alvo = [b2]
            sec[base] = {'bus': b2, 'kv2': kv2, 'kv_1f': kv_1f, 'alvo': alvo, 'nodes': nodes}
        novos.append(ln)
    open(tpath, 'w', encoding='latin-1').write('\n'.join(novos) + '\n')

    # ---------- 2. remapeia cargas BT e PV BT para os nos realmente energizados ----------
    def remap(path, classe):
        if not os.path.exists(path):
            return
        out = []
        for ln in logical(path):
            m = re.search(r'Bus1\s*=\s*([\w\-\.]+)', ln, re.I)
            if not m or not ln.lower().startswith('new'):
                out.append(ln); continue
            b = m.group(1); base = b.split('.')[0].lower()
            info = sec.get(base)
            if not info:
                log[f'{classe}_sem_trafo_correspondente'] += 1
                out.append(ln); continue
            nodes_carga = [n for n in b.split('.')[1:] if n != '0']
            # escolhe o no do enrolamento correspondente (round-robin pela fase original)
            idx = 0
            if nodes_carga:
                try:
                    idx = (int(nodes_carga[0]) - 1) % len(info['alvo'])
                except ValueError:
                    idx = 0
            novo_bus = info['alvo'][idx]
            if novo_bus.lower() != b.lower():
                ln = re.sub(r'(Bus1\s*=\s*)[\w\-\.]+', lambda mm: mm.group(1) + novo_bus, ln, count=1, flags=re.I)
                log[f'{classe}_barra_remapeada'] += 1
            # ajusta kV para o do enrolamento
            if re.search(r'\bkv\s*=', ln, re.I):
                antigo = float(re.search(r'\bkv\s*=\s*([\d\.]+)', ln, re.I).group(1))
                if abs(antigo - info['kv_1f']) > 1e-6:
                    ln = re.sub(r'(\bkv\s*=\s*)[\d\.]+', lambda mm: mm.group(1) + f"{info['kv_1f']:.4f}",
                                ln, count=1, flags=re.I)
                    log[f'{classe}_kv_corrigido'] += 1
            ln = re.sub(r'(\bPhases\s*=\s*)\d+', r'\g<1>1', ln, flags=re.I)
            out.append(ln)
        open(path, 'w', encoding='latin-1').write('\n'.join(out) + '\n')

    for f in os.listdir(dst):
        if f.startswith('EQUIVALENTE-UCBT-01'):
            remap(os.path.join(dst, f), 'carga_BT')
    remap(os.path.join(dst, f'PV-BT-{se}.dss'), 'pv_BT')

    # ---------- 3. master: stubs, XYCurves, voltagebases, limites ----------
    mpath = os.path.join(dst, f'MASTER-{se}.dss')
    txt = open(mpath, encoding='latin-1').read()
    arquivos = {f.lower() for f in os.listdir(dst)}
    for r in re.findall(r'(?im)^\s*redirect\s+(\S+)', txt):
        if r.lower() not in arquivos:
            open(os.path.join(dst, r), 'w').write('! STUB - arquivo ausente no pacote original\n')
            log[f'stub_criado_{r}'] += 1
    open(os.path.join(dst, '_PATCH_XY.dss'), 'w').write(PATCH_XY)
    txt = txt.replace('redirect LineCodes.dss', 'redirect _PATCH_XY.dss\nredirect LineCodes.dss')
    # remove monitores orfaos
    existentes = set()
    for f in os.listdir(dst):
        if f.lower().endswith('.dss'):
            for mm in re.finditer(r'(?im)^\s*new\s+"?([a-z]+)\.([^"\s]+)',
                                  open(os.path.join(dst, f), encoding='latin-1', errors='replace').read()):
                existentes.add(f'{mm.group(1).lower()}.{mm.group(2).lower()}')
    keep = []
    for ln in txt.split('\n'):
        mm = re.search(r'(?i)new\s+monitor\.\S+.*element\s*=\s*(\S+)', ln)
        if mm and mm.group(1).lower() not in existentes:
            log['monitor_orfao_removido'] += 1
            continue
        keep.append(ln)
    txt = '\n'.join(keep)
    txt = re.sub(r'(?im)^\s*show\s+.*$', '', txt)
    txt = re.sub(r'(?im)^\s*solve\s*$', '', txt)
    txt = re.sub(r'(?im)^\s*Set\s+Voltagebases\s*=.*$',
                 'Set Voltagebases=[88 13.8 0.44 0.38 0.24 0.22 0.208 0.127 0.11]', txt)
    txt += '\nSet maxcontroliter=200\nSet maxiterations=50\n'
    open(mpath, 'w', encoding='latin-1').write(txt)
    return dst, mpath, dict(log)


def amps_max(name):
    dss.Circuit.SetActiveElement(name)
    c = dss.CktElement.CurrentsMagAng()
    n = dss.CktElement.NumConductors()
    return max([c[2 * i] for i in range(n)] or [0])


def rodar(se, cen):
    res = {'SE': se, 'cenario': cen}
    dst, mpath, log = corrigir(se, cen)
    res['correcoes'] = log
    dss.Text.Command('Clear')
    dss.Text.Command(f'Compile "{mpath}"')
    dss.Text.Command('Set mode=snap'); dss.Text.Command('Set controlmode=static')
    dss.Text.Command('Solve')
    res['snap_convergiu'] = dss.Solution.Converged()
    res['P_total_kW'] = round(-dss.Circuit.TotalPower()[0], 1)
    res['perdas_kW'] = round(dss.Circuit.Losses()[0] / 1000, 1)
    res['ramos_isolados'] = len(dss.Topology.AllIsolatedBranches())
    res['cargas_isoladas'] = len(dss.Topology.AllIsolatedLoads())
    vv = [v for v in dss.Circuit.AllBusMagPu() if v > 0.01]
    res['V_pu_min_snap'] = round(min(vv), 4) if vv else None
    res['V_pu_max_snap'] = round(max(vv), 4) if vv else None

    eq = [t for t in dss.Transformers.AllNames() if 'eq-tr' in t.lower()]
    heads = {}
    for tr in eq:
        dss.Circuit.SetActiveElement('Transformer.' + tr)
        s = dss.CktElement.BusNames()[1].split('.')[0].lower()
        outs = []
        for ln in dss.Lines.AllNames():
            dss.Lines.Name(ln)
            if s in (dss.Lines.Bus1().split('.')[0].lower(), dss.Lines.Bus2().split('.')[0].lower()):
                outs.append((ln, dss.Lines.NormAmps()))
        heads[tr] = {'sec': s, 'outs': outs}

    dss.Text.Command('Set mode=daily'); dss.Text.Command('Set stepsize=15m'); dss.Text.Command('Set number=1')
    dss.Solution.Hour(0); dss.Solution.Seconds(0)
    tr_amps = {t: [] for t in eq}; tr_kw = {t: [] for t in eq}
    vmin = []; nc = 0; ce = 0
    for _ in range(96):
        try:
            dss.Solution.Solve()
        except Exception as e:
            if 'Control Iterations' in str(e):
                ce += 1
            else:
                raise
        if not dss.Solution.Converged():
            nc += 1
        for t in eq:
            a = max([amps_max('Line.' + ln) for ln, _ in heads[t]['outs']] or [0])
            tr_amps[t].append(a)
            dss.Circuit.SetActiveElement('Transformer.' + t)
            p = dss.CktElement.Powers(); n = dss.CktElement.NumConductors()
            tr_kw[t].append(-sum(p[2 * n + 2 * i] for i in range(n)))
        v = [x for x in dss.Circuit.AllBusMagPu() if x > 0.01]
        if v:
            vmin.append(min(v))
    res['passos_nao_convergidos'] = nc
    res['passos_estouro_controle'] = ce
    res['V_pu_min_diario'] = round(min(vmin), 4) if vmin else None

    ali = []
    for t in eq:
        outs = heads[t]['outs']
        na = max([x[1] for x in outs], default=0)
        A = tr_amps[t]; K = tr_kw[t]
        car = [100 * a / na for a in A] if na else []
        ali.append({
            'EQ_TR': t, 'bus_sec': heads[t]['sec'], 'n_linhas_saida': len(outs),
            'Inom_tronco_A': round(na, 1),
            'I_max_A': round(max(A), 1) if A else None,
            'kW_max': round(max(K), 1) if K else None,
            'kW_min': round(min(K), 1) if K else None,
            'carreg_max_pct': round(max(car), 1) if car else None,
            'carreg_med_pct': round(sum(car) / len(car), 1) if car else None,
            'h_pico': (car.index(max(car)) * 0.25 if car else None),
            'pct_tempo_>100': round(100 * sum(1 for c in car if c > 100) / len(car), 1) if car else None,
            'pct_tempo_>110': round(100 * sum(1 for c in car if c > 110) / len(car), 1) if car else None,
            'pct_tempo_>120': round(100 * sum(1 for c in car if c > 120) / len(car), 1) if car else None,
            'perfil': [round(c, 1) for c in car],
        })
    res['alimentadores'] = ali
    dss.Text.Command('Set mode=snap'); dss.Text.Command('Solve')
    res['status'] = 'OK'
    return res


if __name__ == '__main__':
    os.makedirs(WORK, exist_ok=True)
    ses = sys.argv[1:] or ['DBSI', 'DCAM', 'DEMB', 'DGNA']
    out = []
    for se in ses:
        try:
            r = rodar(se, 'DU')
        except Exception:
            r = {'SE': se, 'cenario': 'DU', 'status': 'EXCECAO', 'erro': traceback.format_exc()[-900:]}
        out.append(r)
        print(se, r.get('status'), r.get('P_total_kW'), flush=True)
        json.dump(out, open(os.path.join(OUT, f'fix_results_{"_".join(ses)}.json'), 'w'),
                  indent=1, ensure_ascii=False)
    print('FIM')
