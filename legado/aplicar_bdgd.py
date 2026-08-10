# -*- coding: utf-8 -*-
"""
Aplica aos modelos corrigidos a CARGA REAL extraida da BDGD.

Substitui o arquivo de carga de BT do pacote (que cobria um unico alimentador)
pelas cargas de todos os alimentadores extraidos da BDGD, e corrige a tensao
dos secundarios pelo campo TEN_LIN_SE da UNTRMT.

Gera, em cada modelo: _CARGA_BDGD.dss e _CURVAS_BDGD.dss
"""
import os, re, json, math, shutil, collections, sys

OUT = '/sessions/relaxed-sweet-turing/mnt/outputs'
COR = '/sessions/relaxed-sweet-turing/mnt/Criticidades/_CORRIGIDO'
SES = {'DBSI': ['BSI0105', 'BSI0112'], 'DCAM': ['CAM0013', 'CAM0301'],
       'DEMB': ['EMB0106', 'EMB0107', 'EMB0115'], 'DGNA': ['GNA0111', 'GNA0115']}
DIAS = {'DU': 21, 'SA': 4, 'DO': 5}          # dias tipicos por mes
FASES = {'A': '1', 'B': '2', 'C': '3'}

ucbt = json.load(open(f'{OUT}/ucbt_alvo.json'))
untr = json.load(open(f'{OUT}/untrmt_alvo.json'))
crv = json.load(open(f'{OUT}/crvcrg.json'))


def curvas_dss(tipo_dia):
    """LoadShapes normalizadas pela media, no padrao do pacote."""
    out = ['! Curvas de carga da BDGD (CRVCRG), tipo de dia ' + tipo_dia,
           '! Normalizadas pela demanda media de cada curva.']
    nomes = set()
    for k, v in crv.items():
        cod, td = k.split('|')
        if td != tipo_dia:
            continue
        med = sum(v) / len(v)
        if med <= 0:
            continue
        mult = ' '.join(f'{x / med:.4f}' for x in v)
        out.append(f'New LoadShape.{cod} npts=96 interval=0.25 mult=({mult})')
        nomes.add(cod)
    return '\n'.join(out) + '\n', nomes


def cargas_dss(se, mes, tipo_dia, nomes_curva):
    """Cargas de BT por transformador, a partir da energia mensal da UCBT."""
    horas = DIAS[tipo_dia] * 24 if False else 730.0   # demanda media mensal
    out = [f'! Carga de BT extraida da BDGD - {se} - mes {mes:02d} - {tipo_dia}',
           '! kW = energia mensal da UCBT / 730 h (demanda media).',
           '! Tensao conforme TEN_LIN_SE da UNTRMT.']
    tot = 0.0
    n = 0
    for ctmt in SES[se]:
        for cod, d in ucbt.get(ctmt, {}).items():
            t = untr.get(cod)
            if not t:
                continue
            kwm = d['ene'][mes - 1] / horas
            if kwm <= 0.001:
                continue
            bus = t['pac2'].lower()
            fs = [FASES[x] for x in (t['fas_s'] or 'AN') if x in FASES] or ['1']
            tl = t['ten_lin'] or 0.22
            # 1 ou 2 pernas -> secundario com derivacao central (ex.: 240/120)
            # 3 fases -> estrela (ex.: 220/127)
            kv = round(tl / math.sqrt(3), 4) if tl >= 0.30 else round(tl / 2.0, 4)
            if len(fs) < 2:
                fs = ['1', '2']              # as duas pernas do secundario
            curva = d['curva'] if d['curva'] in nomes_curva else 'RES-Tipo02'
            kwf = kwm / len(fs)
            for f in fs:
                out.append(f'New Load.BDGD_{cod}_{f} Bus1={bus}.{f}.4 Phases=1 Model=8 '
                           f'zipv=(0.5,0,0.5,1,0,0,0.5) kv={kv:.4f} pf=0.92 '
                           f'kW={kwf:.6f} Daily={curva}')
                n += 1
            tot += kwm
    return '\n'.join(out) + '\n', tot, n


def trafos_kv(se, dst):
    """Corrige o Kv do secundario dos trafos de BT pelo TEN_LIN_SE da BDGD."""
    p = os.path.join(dst, f'TRAFOS-MT-{se}.dss')
    txt = open(p, encoding='latin-1').read()
    # mapa barra secundaria -> tensao de linha
    porbus = {t['pac2'].lower(): t['ten_lin'] for t in untr.values() if t.get('pac2')}
    linhas, alt = [], 0
    for ln in txt.split('\n'):
        m = re.search(r'wdg=([23])\s+bus=([\w\-\.]+)\s+conn=(\w+)\s+Kv=([\d\.]+)', ln, re.I)
        if m:
            b = m.group(2).split('.')[0].lower()
            tl = porbus.get(b)
            if tl:
                nos = [x for x in m.group(2).split('.')[1:] if x not in ('0', '4')]
                novo = round(tl / math.sqrt(3), 4) if tl >= 0.30 else round(tl / 2.0, 4)
                if abs(novo - float(m.group(4))) > 1e-4:
                    ln = ln.replace(f'Kv={m.group(4)}', f'Kv={novo:.4f}')
                    alt += 1
        linhas.append(ln)
    open(p, 'w', encoding='latin-1').write('\n'.join(linhas))
    return alt


def aplicar(se, cen, mes=1):
    dst = f'{COR}/{se}_{cen}'
    cur, nomes = curvas_dss(cen)
    open(os.path.join(dst, '_CURVAS_BDGD.dss'), 'w', encoding='latin-1').write(cur)
    car, tot, n = cargas_dss(se, mes, cen, nomes)
    open(os.path.join(dst, '_CARGA_BDGD.dss'), 'w', encoding='latin-1').write(car)
    alt = trafos_kv(se, dst)
    # MASTER: tira a carga antiga e a estimativa, entra a da BDGD
    mp = os.path.join(dst, f'MASTER-{se}.dss')
    txt = open(mp, encoding='latin-1').read()
    txt = re.sub(r'(?im)^\s*redirect\s+EQUIVALENTE-UCBT.*$', '! (substituido pela carga da BDGD)', txt)
    txt = re.sub(r'(?im)^\s*redirect\s+_CARGA_ESTIMADA\.dss\s*$', '', txt)
    txt = re.sub(r'(?im)^\s*redirect\s+LoadShapes_\w+\.dss\s*$',
                 'redirect _CURVAS_BDGD.dss', txt)
    if '_CARGA_BDGD.dss' not in txt:
        txt = txt.replace('\n! solucao inicial', '\nredirect _CARGA_BDGD.dss\n\n! solucao inicial', 1)
    open(mp, 'w', encoding='latin-1').write(txt)
    return {'SE': se, 'cen': cen, 'kW_BT': round(tot, 1), 'n_cargas': n, 'trafos_kv_corrigidos': alt}


if __name__ == '__main__':
    res = []
    for se in (sys.argv[1:] or list(SES)):
        for cen in ['DU', 'SA', 'DO']:
            r = aplicar(se, cen)
            if cen == 'DU':
                res.append(r)
                print(f"{se}: {r['kW_BT']:,.0f} kW de BT em {r['n_cargas']:,} cargas | "
                      f"{r['trafos_kv_corrigidos']} trafos com kV corrigido", flush=True)
    json.dump(res, open(f'{OUT}/aplicacao_bdgd.json', 'w'), indent=1, ensure_ascii=False)
    print('FIM')
