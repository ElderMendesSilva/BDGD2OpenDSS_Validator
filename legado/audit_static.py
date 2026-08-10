import os, re, json, collections

BASE = '/sessions/relaxed-sweet-turing/mnt/Criticidades'
OUT = '/sessions/relaxed-sweet-turing/mnt/outputs'

def readf(p):
    return open(p, encoding='latin-1', errors='replace').read()

def logical_lines(txt):
    """Junta linhas de continuacao (~) do OpenDSS."""
    out = []
    for raw in txt.split('\n'):
        s = raw.strip()
        if not s or s.startswith('!'):
            continue
        s = s.split('!')[0].strip()
        if not s:
            continue
        if s.startswith('~'):
            if out:
                out[-1] += ' ' + s[1:].strip()
        else:
            out.append(s)
    return out

NEW_RE = re.compile(r'^new\s+"?([a-z]+)\.([^"\s]+)"?\s*(.*)$', re.I)

def parse_props(rest):
    props = {}
    # captura chave=valor, com valores entre parenteses/colchetes/aspas
    for m in re.finditer(r'([\w%\-\.]+)\s*=\s*(\[[^\]]*\]|\([^\)]*\)|"[^"]*"|\'[^\']*\'|\S+)', rest):
        props[m.group(1).lower()] = m.group(2).strip('"\'')
    return props

def parse_model(d):
    """Retorna dict com elementos por classe e metadados."""
    elems = collections.defaultdict(list)
    files = {f.lower(): f for f in os.listdir(d)}
    master = [f for f in os.listdir(d) if f.upper().startswith('MASTER')][0]
    mtxt = readf(os.path.join(d, master))
    redirects = re.findall(r'(?im)^\s*redirect\s+(\S+)', mtxt)
    missing = [r for r in redirects if r.lower() not in files]
    present = [r for r in redirects if r.lower() in files]

    sources = [os.path.join(d, master)] + [os.path.join(d, files[r.lower()]) for r in present]
    for src in sources:
        txt = readf(src)
        for ln in logical_lines(txt):
            m = NEW_RE.match(ln)
            if not m:
                continue
            cls, name, rest = m.group(1).lower(), m.group(2), m.group(3)
            elems[cls].append({'name': name, 'props': parse_props(rest),
                               'file': os.path.basename(src), 'raw': ln})
    return elems, redirects, missing, mtxt, master


def bus_key(b):
    return b.split('.')[0].lower()


def audit(d, tag):
    elems, redirects, missing, mtxt, master = parse_model(d)
    r = {'modelo': tag, 'master': master, 'redirects': len(redirects),
         'arquivos_faltando': missing, 'erros': [], 'alertas': [], 'contagem': {}}

    for cls, lst in sorted(elems.items()):
        r['contagem'][cls] = len(lst)

    # ---- separa chaves de linhas reais
    lines = elems.get('line', [])
    switches = [l for l in lines if l['props'].get('switch', '').lower().startswith('y')]
    real_lines = [l for l in lines if l not in switches]
    r['contagem']['line_trecho'] = len(real_lines)
    r['contagem']['line_chave'] = len(switches)

    # ---- nomes duplicados
    for cls, lst in elems.items():
        names = [e['name'].lower() for e in lst]
        dup = [n for n, c in collections.Counter(names).items() if c > 1]
        if dup:
            r['erros'].append(f'{cls}: {len(dup)} nome(s) duplicado(s), ex.: {dup[:3]}')

    # ---- linecodes referenciados x definidos
    lcs = {e['name'].lower() for e in elems.get('linecode', [])}
    used_lc = collections.Counter()
    for l in lines:
        lc = l['props'].get('linecode')
        if lc:
            used_lc[lc.lower()] += 1
    undef_lc = {k: v for k, v in used_lc.items() if k not in lcs}
    if undef_lc:
        r['erros'].append(f'LineCodes referenciados e nao definidos: {len(undef_lc)} '
                          f'(afetam {sum(undef_lc.values())} linhas) ex.: {list(undef_lc)[:5]}')
    unused_lc = lcs - set(used_lc)
    if unused_lc:
        r['alertas'].append(f'LineCodes definidos e nunca usados: {len(unused_lc)} de {len(lcs)}')

    # ---- loadshapes referenciados x definidos
    lss = {e['name'].lower() for e in elems.get('loadshape', [])}
    used_ls = collections.Counter()
    for cls in ('load', 'pvsystem'):
        for e in elems.get(cls, []):
            for k in ('daily', 'tdaily', 'yearly', 'duty'):
                v = e['props'].get(k)
                if v:
                    used_ls[v.lower()] += 1
    undef_ls = {k: v for k, v in used_ls.items() if k not in lss}
    if undef_ls:
        r['erros'].append(f'LoadShapes/curvas referenciadas e nao definidas: {list(undef_ls)[:6]} '
                          f'({sum(undef_ls.values())} elementos afetados)')

    # ---- xycurves (effcurve / P-TCurve)
    xy = {e['name'].lower() for e in elems.get('xycurve', [])}
    used_xy = collections.Counter()
    for e in elems.get('pvsystem', []):
        for k in ('effcurve', 'p-tcurve'):
            v = e['props'].get(k)
            if v:
                used_xy[v.lower()] += 1
    undef_xy = {k: v for k, v in used_xy.items() if k not in xy}
    if undef_xy:
        r['erros'].append(f'XYCurves de PV nao definidas: {list(undef_xy)} '
                          f'({sum(undef_xy.values())} PVs afetados)')

    # ---- conectividade: barras alimentadas x barras de carga
    supply_buses = set()   # barras tocadas por elementos de rede
    for cls in ('line', 'transformer', 'reactor'):
        for e in elems.get(cls, []):
            p = e['props']
            for k in ('bus1', 'bus2', 'bus'):
                if k in p:
                    supply_buses.add(bus_key(p[k]))
            if 'buses' in p:
                for b in re.split(r'[,\s]+', p['buses'].strip('[]()')):
                    if b:
                        supply_buses.add(bus_key(b))
    supply_buses.add('sourcebus')

    orph = collections.Counter()
    for cls in ('load', 'pvsystem', 'capacitor'):
        for e in elems.get(cls, []):
            b = e['props'].get('bus1') or e['props'].get('bus')
            if b and bus_key(b) not in supply_buses:
                orph[cls] += 1
    if orph:
        r['erros'].append('Elementos em barra sem conexao de rede (ilhados): ' +
                          ', '.join(f'{k}={v}' for k, v in orph.items()))

    # ---- SwtControl apontando para chave inexistente
    line_names = {e['name'].lower() for e in lines}
    bad_swt = []
    for e in elems.get('swtcontrol', []):
        so = e['props'].get('switchedobj', '')
        if so.lower().startswith('line.') and so.split('.', 1)[1].lower() not in line_names:
            bad_swt.append(so)
    if bad_swt:
        r['erros'].append(f'SwtControl referenciando Line inexistente: {len(bad_swt)} ex.: {bad_swt[:3]}')
    # chaves abertas
    aberta = [e['name'] for e in elems.get('swtcontrol', [])
              if e['props'].get('state', '').lower() == 'open']
    r['chaves_abertas'] = len(aberta)

    # ---- monitores apontando para elemento inexistente
    allnames = {f"{cls}.{e['name'].lower()}" for cls, lst in elems.items() for e in lst}
    bad_mon = []
    for e in elems.get('monitor', []):
        el = e['props'].get('element', '').lower()
        if el and el not in allnames:
            bad_mon.append(e['props'].get('element'))
    if bad_mon:
        r['erros'].append(f'Monitores apontando para elemento inexistente: {sorted(set(bad_mon))}')

    # ---- potencias
    def fnum(x, dflt=0.0):
        try:
            return float(x)
        except Exception:
            return dflt

    loads = elems.get('load', [])
    mt = [l for l in loads if fnum(l['props'].get('kv', 0)) > 1.0]
    bt = [l for l in loads if fnum(l['props'].get('kv', 0)) <= 1.0]
    r['carga_MT_kW'] = round(sum(fnum(l['props'].get('kw')) for l in mt), 1)
    r['carga_BT_kW'] = round(sum(fnum(l['props'].get('kw')) for l in bt), 1)
    r['n_carga_MT'] = len(mt)
    r['n_carga_BT'] = len(bt)
    zero = [l['name'] for l in loads if fnum(l['props'].get('kw'), -1) == 0]
    if zero:
        r['alertas'].append(f'Cargas com kW=0: {len(zero)}')
    semkv = [l['name'] for l in loads if 'kv' not in l['props']]
    if semkv:
        r['erros'].append(f'Cargas sem kV declarado: {len(semkv)}')

    pvs = elems.get('pvsystem', [])
    pv_mt = [p for p in pvs if fnum(p['props'].get('kv', 0)) > 1.0]
    pv_bt = [p for p in pvs if fnum(p['props'].get('kv', 0)) <= 1.0]
    r['GD_MT_kWp'] = round(sum(fnum(p['props'].get('pmpp')) for p in pv_mt), 1)
    r['GD_BT_kWp'] = round(sum(fnum(p['props'].get('pmpp')) for p in pv_bt), 1)
    r['n_GD_MT'] = len(pv_mt)
    r['n_GD_BT'] = len(pv_bt)
    pv0 = [p['name'] for p in pvs if fnum(p['props'].get('pmpp'), -1) == 0]
    if pv0:
        r['alertas'].append(f'PVSystems com pmpp=0: {len(pv0)}')
    pv_kva = [p['name'] for p in pvs if fnum(p['props'].get('kva'), 0) < fnum(p['props'].get('pmpp'), 0)]
    if pv_kva:
        r['alertas'].append(f'PVSystems com kVA < pmpp (limitacao de inversor): {len(pv_kva)}')

    caps = elems.get('capacitor', [])
    r['capacitor_kvar'] = round(sum(fnum(c['props'].get('kvar')) for c in caps), 1)
    cap_nocontrol = len(caps) - len(elems.get('capcontrol', []))
    if caps and not elems.get('capcontrol'):
        r['alertas'].append(f'{len(caps)} banco(s) de capacitor sem CapControl (sempre ligados)')

    trafos = elems.get('transformer', [])
    eqtr = [t for t in trafos if 'EQ-TR' in t['name'].upper()]
    regs = [t for t in trafos if t['name'].upper().startswith('REG')]
    dist = [t for t in trafos if t not in eqtr and t not in regs]
    r['n_trafo_dist'] = len(dist)
    r['n_trafo_EQ'] = len(eqtr)
    r['n_regulador_trafo'] = len(regs)
    r['n_regcontrol'] = len(elems.get('regcontrol', []))
    r['trafo_dist_kVA'] = round(sum(fnum(t['props'].get('kva')) for t in dist), 1)
    if regs and not elems.get('regcontrol'):
        r['erros'].append(f'{len(regs)} transformador(es) REG_ sem RegControl associado (regulador nao atua)')

    # sequencia dos EQ-TR
    nums = sorted(int(n) for t in eqtr for n in re.findall(r'EQ-TR(\d+)', t['name'].upper()))
    if nums:
        faltam = [i for i in range(1, max(nums) + 1) if i not in nums]
        r['EQ_TR_ids'] = nums
        if faltam:
            r['alertas'].append(f'Numeracao de EQ-TR nao sequencial; ausente(s): TR{faltam}')

    # tap fora de faixa
    badtap = [t['name'] for t in trafos if not (0.85 <= fnum(t['props'].get('tap'), 1.0) <= 1.15)]
    if badtap:
        r['alertas'].append(f'Trafos com tap fora de 0,85-1,15 pu: {len(badtap)}')

    # ---- linhas com comprimento zero / negativo
    badlen = [l['name'] for l in real_lines if fnum(l['props'].get('length'), 1) <= 0]
    if badlen:
        r['alertas'].append(f'Linhas com comprimento <= 0: {len(badlen)}')
    # linhas com bus1 == bus2
    loop = [l['name'] for l in lines
            if bus_key(l['props'].get('bus1', 'a')) == bus_key(l['props'].get('bus2', 'b'))]
    if loop:
        r['erros'].append(f'Linhas com Bus1 == Bus2 (auto-laco): {len(loop)}')

    r['n_barras'] = len(supply_buses)
    return r


if __name__ == '__main__':
    res = []
    for se in sorted(os.listdir(BASE)):
        for cen in sorted(os.listdir(os.path.join(BASE, se))):
            res.append(audit(os.path.join(BASE, se, cen), cen))
            print('ok', cen, flush=True)
    json.dump(res, open(os.path.join(OUT, 'audit_static.json'), 'w'),
              indent=1, ensure_ascii=False)
    print('gravado')
