# -*- coding: utf-8 -*-
"""
VERIFICACAO DE SANIDADE NUMERICA, SUBESTACAO POR SUBESTACAO, NOS DOIS MOTORES
============================================================================

    python verifica.py                     abre o painel e pergunta a pasta
    python verifica.py MODELOS_V8
    python verifica.py MODELOS_V8 --se DALP DPLA
    python verifica.py MODELOS_V8 --motor com --grafico

Por que dois motores. O mesmo arquivo se comporta de forma diferente em cada
build do OpenDSS. Medido na DALP, antes da correcao da GD:

    DSS C-API 0.14.5 (opendssdirect)      36 nos NaN, TotalPower 257.360 kW
    OpenDSS v11.0.0.1 COM (EPRI)      49.857 nos NaN, TotalPower NaN

Sao 9 barras isoladas em ambos os casos — mas o C-API contem o NaN na ilha
que o gerou, e o motor da EPRI o propaga pela fatoracao e derruba a rede
inteira. Como o COM e o motor que o usuario abre no OpenDSS e o que a
analise_com usa, validar so no C-API deixa passar modelo inutilizavel.

Por que `Converged` nao basta. Se ha NaN, toda comparacao do criterio de
convergencia e falsa, o teste passa trivialmente e o OpenDSS declara
convergencia em 2 iteracoes. Convergiu com NaN significa nao resolveu.

Saida: uma linha por subestacao e `verificacao.json` na raiz.
"""
import argparse
import glob
import json
import math
import os
import sys

CWD = os.getcwd()


def _masters(raiz, alvo=None):
    fora = {'_AT', '_global'}
    saida = []
    for p in sorted(glob.glob(os.path.join(raiz, '*'))):
        se = os.path.basename(p)
        if not os.path.isdir(p) or se in fora:
            continue
        if alvo and se not in alvo:
            continue
        m = sorted(glob.glob(os.path.join(p, 'MASTER-*.dss')))
        if m:
            saida.append((se, m[0]))
    return saida


# --------------------------------------------------------------- opendssdirect
def _capi(master):
    import opendssdirect as dss
    dss.Text.Command('Clear')
    try:
        dss.Text.Command(f'Compile "{master}"')
    except Exception as e:
        os.chdir(CWD)
        return {'compila': False, 'erro': str(e)[:200]}
    os.chdir(CWD)
    dss.Text.Command('Set mode=snap')
    dss.Text.Command('Set controlmode=static')
    try:
        dss.Text.Command('Solve')
    except Exception as e:
        os.chdir(CWD)
        return {'compila': True, 'erro_solve': str(e)[:200]}
    os.chdir(CWD)
    v = dss.Circuit.AllBusMagPu()
    nomes = dss.Circuit.AllNodeNames()
    carga = 0.0
    i = dss.Loads.First()
    while i:
        carga += dss.Loads.kW()
        i = dss.Loads.Next()
    gd = 0.0
    i = dss.PVsystems.First()
    while i:
        dss.Circuit.SetActiveElement('PVSystem.' + dss.PVsystems.Name())
        p = dss.CktElement.Powers()[0::2]
        gd += -sum(p[:dss.CktElement.NumPhases()])
        i = dss.PVsystems.Next()
    r = _mede(v, nomes, dss.Circuit.TotalPower()[0],
              dss.Circuit.Losses()[0] / 1000,
              bool(dss.Solution.Converged()), dss.Solution.Iterations(),
              carga, gd)
    if r['nan_nos']:
        b = nomes[r['_i0']].split('.')[0]
        dss.Circuit.SetActiveBus(b)
        r['nan_exemplo'] = (f"{b} PCE={[x for x in (dss.Bus.AllPCEatBus() or []) if x]} "
                            f"PDE={[x for x in (dss.Bus.AllPDEatBus() or []) if x]}")
    r.pop('_i0', None)
    r['compila'] = True
    return r


# ------------------------------------------------------------------------ COM
_COM = {}


def _com(master):
    if 'dss' not in _COM:
        import win32com.client
        d = win32com.client.Dispatch('OpenDSSEngine.DSS')
        d.Start(0)
        _COM['dss'] = d
        _COM['versao'] = d.Version.strip()
    d = _COM['dss']
    t, c = d.Text, d.ActiveCircuit
    t.Command = 'Clear'
    t.Command = f'Compile "{master}"'
    os.chdir(CWD)
    if d.Error.Number:
        return {'compila': False, 'erro': d.Error.Description[:200]}
    t.Command = 'Set mode=snap'
    t.Command = 'Set controlmode=static'
    t.Command = 'Solve'
    os.chdir(CWD)
    v = list(c.AllBusVmagPu)
    nomes = list(c.AllNodeNames)
    carga = 0.0
    i = c.Loads.First
    while i:
        carga += c.Loads.kW
        i = c.Loads.Next
    gd = 0.0
    i = c.PVSystems.First
    while i:
        c.SetActiveElement('PVSystem.' + c.PVSystems.Name)
        p = list(c.ActiveCktElement.Powers)[0::2]
        gd += -sum(p[:c.ActiveCktElement.NumPhases])
        i = c.PVSystems.Next
    r = _mede(v, nomes, c.TotalPower[0], c.Losses[0] / 1000,
              bool(c.Solution.Converged), c.Solution.Iterations, carga, gd)
    if r['nan_nos']:
        b = nomes[r['_i0']].split('.')[0]
        bb = c.Buses(b)
        r['nan_exemplo'] = (f"{b} PCE={[x for x in (bb.AllPCEatBus or []) if x]} "
                            f"PDE={[x for x in (bb.AllPDEatBus or []) if x]}")
    r.pop('_i0', None)
    r['compila'] = True
    return r


# -------------------------------------------------------------------- comum
def _mede(v, nomes, p_total, perdas_kw, convergiu, iteracoes, carga=0.0, gd=0.0):
    """As perdas saem sobre a energia INJETADA, nao sobre a fonte.

    Com geracao distribuida a fonte deixa de ser o denominador certo. Medido
    na DALP: fonte 1.737 kW, GD 54.339 kW, carga 50.217 kW, perdas 5.296 kW.
    Sobre a fonte isso da 305%; sobre a injetada (fonte + GD), 9,44% — que e
    a definicao do Modulo 7 do PRODIST e o unico numero comparavel entre
    subestacoes com e sem GD.
    """
    maus = [i for i, x in enumerate(v) if math.isnan(x)]
    bons = [x for x in v if not math.isnan(x) and x > 0.01]
    p_fonte = None if math.isnan(p_total) else round(-p_total, 1)
    perdas = None if math.isnan(perdas_kw) else round(perdas_kw, 1)
    inj = None if p_fonte is None else p_fonte + gd
    r = {'nos': len(v),
         'nan_nos': len(maus),
         'nan_barras': len({nomes[i].split('.')[0] for i in maus}),
         'convergiu': convergiu,
         'iteracoes': iteracoes,
         'P_kW': p_fonte,
         'P_carga_kW': round(carga, 1),
         'P_gd_kW': round(gd, 1),
         'P_injetada_kW': None if inj is None else round(inj, 1),
         'perdas_kW': perdas,
         'perdas_pct': (None if (perdas is None or not inj or inj <= 1)
                        else round(100 * perdas / inj, 2)),
         'V_media': round(sum(bons) / len(bons), 4) if bons else None,
         'V_min': round(min(bons), 4) if bons else None}
    if maus:
        r['_i0'] = maus[0]
    # o veredicto: convergir com NaN nao e convergir
    r['saudavel'] = bool(convergiu) and not maus and r['P_kW'] is not None
    return r


def veredicto(cap, com):
    """Um so rotulo por subestacao, do defeito mais grave para o mais leve."""
    for m, rot in ((cap, 'C-API'), (com, 'COM')):
        if m and not m.get('compila'):
            return f'NAO_COMPILA[{rot}]'
    for m, rot in ((cap, 'C-API'), (com, 'COM')):
        if m and m.get('nan_nos'):
            return f'NAN[{rot}:{m["nan_nos"]}]'
    for m, rot in ((cap, 'C-API'), (com, 'COM')):
        if m and not m.get('convergiu'):
            return f'NAO_CONVERGE[{rot}:{m.get("iteracoes")}]'
    for m, rot in ((cap, 'C-API'), (com, 'COM')):
        if m and m.get('P_kW') is None:
            return f'POTENCIA_NAN[{rot}]'
    return 'OK'


def grafico(saida, raiz):
    """Duas leituras da rodada: o que quebrou, e como as perdas se distribuem.

    O JSON tem tudo, mas ninguem le 155 registros. O veredicto por barra diz
    em um olhar se sobrou defeito, e o histograma mostra se as perdas estao
    numa faixa plausivel ou se ha subestacao com numero absurdo.
    """
    import collections
    import interativo
    plt = interativo.pyplot()

    cont = collections.Counter(x['veredicto'].split('[')[0] for x in saida)
    perd = [(x['com'] or x['capi'] or {}).get('perdas_pct') for x in saida]
    perd = [p for p in perd if p is not None and 0 < p < 100]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5), dpi=110)
    rot = [k for k, _ in cont.most_common()]
    val = [cont[k] for k in rot]
    cor = ['#1a7f37' if k == 'OK' else '#b3261e' for k in rot]
    a1.barh(rot[::-1], val[::-1], color=cor[::-1])
    for i, v in enumerate(val[::-1]):
        a1.text(v, i, f' {v}', va='center', fontsize=9)
    a1.set_title(f'Veredicto — {len(saida)} subestações', loc='left',
                 fontsize=12, weight='bold')
    a1.set_xlabel('subestações')
    a1.grid(alpha=.25, axis='x', lw=.4)

    if perd:
        a2.hist(perd, bins=30, color='#4292c6', edgecolor='white', lw=.4)
        med = sorted(perd)[len(perd) // 2]
        a2.axvline(med, color='#e31a1c', lw=1.4, ls='--',
                   label=f'mediana {med:.2f}%')
        a2.legend(fontsize=9)
    a2.set_title('Perdas sobre a energia injetada', loc='left',
                 fontsize=12, weight='bold')
    a2.set_xlabel('perdas (%)')
    a2.set_ylabel('subestações')
    a2.grid(alpha=.25, lw=.4)

    fig.suptitle(os.path.basename(raiz), fontsize=10, color='#666', x=.01, ha='left')
    fig.tight_layout()
    interativo.mostra(plt, os.path.join(raiz, 'verificacao.png'))


def _painel():
    import interativo
    v = interativo.formulario('verifica', 'Verificação de sanidade numérica', [
        {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'a pasta que contém uma subpasta por subestação'},
        {'chave': 'se', 'tipo': 'texto', 'rotulo': 'Subestações', 'padrao': '',
         'dica': 'vazio = todas   •   ex.: DALP DPLA DABR'},
        {'chave': 'motor', 'tipo': 'opcao', 'rotulo': 'Motor', 'padrao': 'ambos',
         'valores': ['ambos', 'capi', 'com'],
         'dica': 'ambos é o que vale: o mesmo arquivo se comporta diferente '
                 'no C-API e no motor da EPRI'},
    ], ajuda='Compila e resolve cada subestação nos dois motores do OpenDSS e '
             'diz quais têm NaN, não convergem ou não compilam.')
    if not v:
        return False
    sys.argv += [v['raiz'], '--motor', v['motor'], '--grafico']
    if v['se'].strip():
        sys.argv += ['--se'] + v['se'].split()
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('raiz', nargs='?', default='MODELOS_V8')
    ap.add_argument('--se', nargs='*', help='so estas subestacoes')
    ap.add_argument('--motor', choices=['ambos', 'capi', 'com'], default='ambos')
    ap.add_argument('--grafico', action='store_true',
                    help='mostra o resumo da rodada em grafico ao final')
    a = ap.parse_args()

    raiz = os.path.abspath(a.raiz)
    itens = _masters(raiz, set(a.se) if a.se else None)
    if not itens:
        raise SystemExit(f'nenhum MASTER em {raiz}')
    print(f'{len(itens)} subestacoes em {raiz}   motor={a.motor}\n')

    saida, contagem = [], {}
    for k, (se, m) in enumerate(itens, 1):
        cap = _capi(m) if a.motor in ('ambos', 'capi') else None
        com = _com(m) if a.motor in ('ambos', 'com') else None
        vd = veredicto(cap, com)
        contagem[vd.split('[')[0]] = contagem.get(vd.split('[')[0], 0) + 1
        ref = com or cap
        print(f'[{k:3d}/{len(itens)}] {se:6s} '
              f'capi(nan={_c(cap, "nan_nos")} conv={_c(cap, "convergiu")} '
              f'it={_c(cap, "iteracoes")}) '
              f'com(nan={_c(com, "nan_nos")} conv={_c(com, "convergiu")} '
              f'it={_c(com, "iteracoes")}) '
              f'carga={_c(ref, "P_carga_kW")} gd={_c(ref, "P_gd_kW")} '
              f'perdas={_c(ref, "perdas_pct")}% V={_c(ref, "V_media")} '
              f'| {vd}', flush=True)
        saida.append({'se': se, 'veredicto': vd, 'capi': cap, 'com': com})

    json.dump(saida, open(os.path.join(raiz, 'verificacao.json'), 'w',
                          encoding='utf-8'), indent=1, ensure_ascii=False)
    print('\n' + '-' * 60)
    for k, n in sorted(contagem.items(), key=lambda x: -x[1]):
        print(f'  {k:22s} {n:4d}')
    print(f'\n{contagem.get("OK", 0)} de {len(itens)} subestacoes sadias nos dois motores.')
    print(f'detalhe em {os.path.join(raiz, "verificacao.json")}')
    if a.grafico:
        grafico(saida, raiz)


def _c(m, k):
    return '—' if not m else m.get(k, '—')


if __name__ == '__main__':
    main()
