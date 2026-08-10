# -*- coding: utf-8 -*-
"""
ESTIMATIVA INDICATIVA da carga de BT ausente.

O pacote traz carga de baixa tensao apenas para um alimentador por subestacao
(o CTMT do cabecalho do arquivo EQUIVALENTE-UCBT). Este script:

  1. calibra o fator de utilizacao (kW de demanda media / kVA instalado) e a
     composicao por tipo de curva usando SOMENTE os transformadores que tem
     carga real no pacote;
  2. aplica essa calibracao aos transformadores sem carga, gerando o arquivo
     _CARGA_ESTIMADA.dss dentro de cada modelo corrigido;
  3. NAO altera nenhuma carga real existente.

O resultado e INDICATIVO. Serve para dimensionar a ordem de grandeza enquanto a
exportacao correta nao chega, e nao substitui o dado da BDGD.
"""
import os, re, sys, json, collections

COR = '/sessions/relaxed-sweet-turing/mnt/Criticidades/_CORRIGIDO'
OUT = '/sessions/relaxed-sweet-turing/mnt/outputs'
SES = ['DBSI', 'DCAM', 'DEMB', 'DGNA']


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


def calibrar(d, se):
    """Devolve (fu, composicao, trafos) a partir dos transformadores com carga real."""
    # transformadores de BT: barra secundaria -> (kVA, nos, kv)
    trafos = {}
    for ln in logical(os.path.join(d, f'TRAFOS-MT-{se}.dss')):
        if not ln.lower().startswith('new transformer'):
            continue
        nome = re.match(r'New\s+Transformer\.(\S+)', ln, re.I).group(1)
        if nome.upper().startswith('REG') or 'EQ-TR' in nome.upper():
            continue
        bs = re.findall(r'bus\s*=\s*([\w\-\.]+)', ln, re.I)
        ks = re.findall(r'\bKva\s*=\s*([\d\.]+)', ln, re.I)
        kvs = re.findall(r'\bKv\s*=\s*([\d\.]+)', ln, re.I)
        if len(bs) < 2:
            continue
        b = bs[1].split('.')[0].lower()
        ns = [n for n in bs[1].split('.')[1:] if n not in ('0', '4')]
        kva = float(ks[1] if len(ks) > 1 else ks[0])
        kv2 = float(kvs[1]) if len(kvs) > 1 else 0.22
        trifasico = len(ns) >= 3
        kv_carga = round(kv2 / (3 ** 0.5), 4) if trifasico else kv2
        if b in trafos:
            trafos[b]['kva'] += kva
            trafos[b]['nos'] = sorted(set(trafos[b]['nos']) | set(ns))
        else:
            trafos[b] = {'kva': kva, 'nos': ns or ['1'], 'kv': kv_carga,
                         'neutro': '4' if '4' in bs[1].split('.')[1:] else '0'}
    # cargas reais de BT
    comcarga = collections.defaultdict(float)
    comp = collections.Counter()
    arq = [f for f in os.listdir(d) if f.startswith('EQUIVALENTE-UCBT-01')]
    for f in arq:
        for ln in logical(os.path.join(d, f)):
            m = re.search(r'Bus1\s*=\s*([\w\-\.]+)', ln, re.I)
            k = re.search(r'kW\s*=\s*([\d\.]+)', ln, re.I)
            cur = re.search(r'Daily\s*=\s*(\S+)', ln, re.I)
            if not (m and k):
                continue
            comcarga[m.group(1).split('.')[0].lower()] += float(k.group(1))
            if cur:
                comp[cur.group(1)] += float(k.group(1))
    kva_com = sum(trafos[b]['kva'] for b in comcarga if b in trafos)
    kw_com = sum(comcarga.values())
    fu = kw_com / kva_com if kva_com else 0.0
    total = sum(comp.values()) or 1.0
    composicao = {k: v / total for k, v in comp.most_common()}
    return fu, composicao, trafos, set(comcarga)


def gerar(se, cen='DU'):
    d = f'{COR}/{se}_{cen}'
    fu, comp, trafos, com = calibrar(d, se)
    sem = [b for b in trafos if b not in com]
    linhas = [f'! Carga de BT ESTIMADA para os transformadores sem dado no pacote - {se}',
              f'! Calibracao a partir dos {len(com)} transformadores com carga real:',
              f'!   fator de utilizacao = {fu:.4f} kW/kVA (demanda media)',
              f'!   composicao por curva = ' + ', '.join(f'{k}:{v*100:.1f}%' for k, v in list(comp.items())[:8]),
              f'! Aplicado a {len(sem)} transformadores. RESULTADO INDICATIVO - nao substitui a BDGD.']
    kw_total = 0.0
    for b in sem:
        t = trafos[b]
        kw_tr = fu * t['kva']
        if kw_tr <= 0.01:
            continue
        kw_total += kw_tr
        fases = t['nos'] or ['1']
        for curva, frac in comp.items():
            kw_c = kw_tr * frac / len(fases)
            if kw_c < 0.001:
                continue
            for i, f in enumerate(fases):
                nome = f'EST_{b}_{curva}_{f}'.replace('.', '_')
                linhas.append(
                    f'New Load.{nome} Bus1={b}.{f}.{t["neutro"]} Phases=1 Model=8 '
                    f'zipv=(0.5,0,0.5,1,0,0,0.5) kv={t["kv"]:.4f} pf=0.92 '
                    f'kW={kw_c:.6f} Daily={curva}')
    p = os.path.join(d, '_CARGA_ESTIMADA.dss')
    open(p, 'w', encoding='latin-1').write('\n'.join(linhas) + '\n')
    # inclui no MASTER, se ainda nao estiver
    mp = os.path.join(d, f'MASTER-{se}.dss')
    txt = open(mp, encoding='latin-1').read()
    if '_CARGA_ESTIMADA.dss' not in txt:
        txt = txt.replace('\n! solucao inicial',
                          '\nredirect _CARGA_ESTIMADA.dss\n\n! solucao inicial', 1)
        open(mp, 'w', encoding='latin-1').write(txt)
    return {'SE': se, 'cenario': cen, 'fu_kW_por_kVA': round(fu, 4),
            'trafos_calibracao': len(com), 'trafos_estimados': len(sem),
            'kW_estimado': round(kw_total, 1),
            'composicao': {k: round(v, 4) for k, v in comp.items()}}


if __name__ == '__main__':
    res = []
    for se in (sys.argv[1:] or SES):
        for cen in ['DU', 'SA', 'DO']:
            r = gerar(se, cen)
            if cen == 'DU':
                res.append(r)
                print(f"{se}: FU={r['fu_kW_por_kVA']:.4f} kW/kVA | calibrado em "
                      f"{r['trafos_calibracao']} trafos | estimados {r['trafos_estimados']} "
                      f"| +{r['kW_estimado']:.0f} kW", flush=True)
    json.dump(res, open(f'{OUT}/estimativa_carga.json', 'w'), indent=1, ensure_ascii=False)
    print('FIM')
