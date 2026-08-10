# -*- coding: utf-8 -*-
"""
ENERGIA DIARIA POR ALIMENTADOR, PARA VALIDACAO CONTRA AS PERDAS DECLARADAS
==========================================================================

    python energia.py                      abre o painel e pergunta a pasta
    python energia.py MODELOS_V8
    python energia.py MODELOS_V8 --se DABR TBAN
    python energia.py MODELOS_V8 --passos 96 --grafico

Por que existe: a comparacao com as colunas PERD_* da CTMT e entre ENERGIAS
(MWh), e o instantaneo so entrega POTENCIA (kW). Sem integrar no tempo os dois
lados nao sao comparaveis — foi o que manteve a discrepancia de 9,3% contra
4,54% sem explicacao.

POR QUE PASSOS INDEPENDENTES, E NAO A SEQUENCIA DO OpenDSS
----------------------------------------------------------
No modo `daily` cada passo parte da solucao do anterior. Medido na DABR e na
DPIP: a sequencia degrada e trava — a DABR para no passo 72, a DPIP no 44 — e
nao se recupera. Nao e a rede: compilando do zero e saltando DIRETO para o
passo 72, a DABR converge em 3 iteracoes com Vmin 0,467; o passo 95, as 23:45,
tambem. Todos os instantes resolvem; a trajetoria e que nao.

Isso foi confirmado sem margem: com `Set number=96` e um unico `Solve` — a
sequencia conduzida pelo proprio motor — o resultado e identico ao do laco
manual. E desligar RegControl, Capacitor, PVSystem ou todos os controles nao
muda NADA, nem uma iteracao, o que descarta o circuito como causa.

A saida e resolver cada passo como um instantaneo proprio. Para o que
queremos e legitimo: perda e funcao do PONTO DE OPERACAO, nao do caminho
percorrido para chegar nele. O que se perde e a dinamica entre passos —
atraso de regulador, temporizacao de capacitor — que nesta base e generica de
qualquer forma, porque a BDGD nao traz ajuste de campo.

O QUE SAI
---------
Por alimentador: energia entregue, perdas e a razao entre elas, tudo em kWh
do dia. E o numero comparavel com PERD_A4 + PERD_B + PERD_A4_B da CTMT.
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
        if not os.path.isdir(p) or se in fora or (alvo and se not in alvo):
            continue
        m = sorted(glob.glob(os.path.join(p, 'MASTER-*.dss')))
        if m:
            saida.append((se, m[0]))
    return saida


def dia(dss, master, passos=96):
    """Roda o dia em `passos` instantaneos independentes.

    Devolve (kWh injetado, kWh de perdas, passos que convergiram, passos que
    falharam, numero de compilacoes gastas).
    """
    def compila():
        dss.Text.Command('Clear')
        dss.Text.Command(f'Compile "{master}"')
        os.chdir(CWD)
        dss.Text.Command('Set mode=daily')
        dss.Text.Command('Set stepsize=15m')
        dss.Text.Command('Set number=1')
        dss.Text.Command('Set controlmode=static')

    compila()
    h_passo = 24.0 / passos
    ent = perd = 0.0
    ok, falhos, n_comp = 0, [], 1
    # Serie do dia, para as curvas de geracao. Sai de graca: fonte, GD e
    # perdas ja sao lidas a cada passo para o balanco de energia — aqui elas
    # so param de ser jogadas fora depois de somadas. Passo que falha fica
    # None, para nao desalinhar o eixo do tempo.
    serie = {'fonte_kw': [None] * passos, 'gd_kw': [None] * passos,
             'perdas_kw': [None] * passos}
    # Por alimentador, acumulado em Python e nao nos registradores do medidor:
    # a recompilacao zera os registradores, entao a cada passo o medidor e
    # reiniciado e amostrado uma vez — o que le exatamente a energia daquele
    # passo — e a soma fica aqui.
    por_alim = {}
    i_reg = None
    for k in range(passos):
        t = k * h_passo
        # Uma falha nao e do instante, e do estado acumulado: recompilar
        # devolve o ponto de partida limpo e o mesmo passo entao converge.
        # Medido: DABR 72/96 -> 96/96 com 2 compilacoes, DPIP 44/96 -> 96/96
        # com 3. E fica MAIS RAPIDO (11,3 s -> 3,3 s na DPIP), porque cada
        # passo que falhava gastava 100 iteracoes antes de desistir.
        for tentativa in (0, 1):
            dss.Text.Command(f'Set hour={int(t)}')
            dss.Text.Command(f'Set sec={int(round((t - int(t)) * 3600))}')
            dss.Text.Command('Solve')
            os.chdir(CWD)
            if dss.Solution.Converged():
                break
            if tentativa == 0:
                compila()
                n_comp += 1
        if not dss.Solution.Converged():
            falhos.append(k)
            continue
        p = dss.Circuit.TotalPower()[0]          # kW, negativo = entregue
        L = dss.Circuit.Losses()[0] / 1000.0     # kW
        if math.isnan(p) or math.isnan(L):
            falhos.append(k)
            continue
        gd = 0.0
        i = dss.PVsystems.First()
        while i:
            dss.Circuit.SetActiveElement('PVSystem.' + dss.PVsystems.Name())
            pw = dss.CktElement.Powers()[0::2]
            gd += -sum(pw[:dss.CktElement.NumPhases()])
            i = dss.PVsystems.Next()
        ent += (-p + gd) * h_passo               # energia INJETADA (fonte + GD)
        perd += L * h_passo
        ok += 1
        serie['fonte_kw'][k] = round(-p, 1)      # negativo = fluxo reverso
        serie['gd_kw'][k] = round(gd, 1)
        serie['perdas_kw'][k] = round(L, 1)

        # --- energia deste passo, por alimentador -------------------------
        dss.Text.Command('Reset Meters')
        dss.Text.Command('Sample')
        if i_reg is None:
            nomes = [x.strip().lower() for x in dss.Meters.RegisterNames()]
            i_reg = (nomes.index('zone kwh') if 'zone kwh' in nomes else 0,
                     nomes.index('zone losses kwh') if 'zone losses kwh' in nomes
                     else None)
        j = dss.Meters.First()
        while j:
            nome = dss.Meters.Name()
            alim = nome[3:] if nome.lower().startswith('em_') else nome
            r = dss.Meters.RegisterValues()
            e = r[i_reg[0]] if i_reg[0] < len(r) else 0.0
            pl = r[i_reg[1]] if (i_reg[1] is not None and i_reg[1] < len(r)) else 0.0
            # `Zone kWh` conta o que ATRAVESSA o medidor. A GD que injeta
            # DENTRO da zona nao passa por ele, entao sozinho o registrador
            # subestima a energia injetada e inflaciona a perda percentual —
            # medido: 0,92 na DABR e 0,79 na DPIP contra fonte+GD, ou seja
            # ate 26% de erro justo onde ha mais geracao. Somar a GD da zona
            # devolve o denominador certo.
            gd_zona = 0.0
            for e_pce in (dss.Meters.ZonePCE() or []):
                if e_pce.lower().startswith('pvsystem.'):
                    dss.Circuit.SetActiveElement(e_pce)
                    pw = dss.CktElement.Powers()[0::2]
                    gd_zona += -sum(pw[:dss.CktElement.NumPhases()])
            gd_zona *= h_passo
            if not (math.isnan(e) or math.isnan(pl) or math.isnan(gd_zona)):
                d = por_alim.setdefault(alim, [0.0, 0.0])
                d[0] += e + gd_zona
                d[1] += pl
            dss.Meters.Name(nome)          # SetActiveElement mexeu no ponteiro
            j = dss.Meters.Next()
    return ent, perd, ok, falhos, n_comp, por_alim, serie


def curva_dia(serie, passos, titulo, caminho, plt=None, mostrar=False):
    """Carga, geracao e o que vem da fonte, ao longo do dia.

    As tres juntas porque separadas nao dizem nada. A curva de geracao sozinha
    e sempre o mesmo sino de irradiancia; o que informa e a RELACAO dela com a
    carga: quanto da demanda o sol cobre ao meio-dia, e se em algum instante a
    fonte inverte — a subestacao passa a exportar em vez de importar, que e o
    fenomeno que muda o estudo de uma rede com GD.

    `fonte` e a potencia vinda da subtransmissao (negativa = fluxo reverso).
    `carga` sai do balanco: fonte + GD - perdas.
    """
    import interativo
    plt = plt or interativo.pyplot()

    h = [k * 24.0 / passos for k in range(passos)]
    f = [None if x is None else x / 1000.0 for x in serie['fonte_kw']]
    g = [None if x is None else x / 1000.0 for x in serie['gd_kw']]
    pe = [None if x is None else x / 1000.0 for x in serie['perdas_kw']]
    c = [None if (a is None or b is None or d is None) else a + b - d
         for a, b, d in zip(f, g, pe)]
    if not any(x is not None for x in g):
        return None

    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=120)
    ax.plot(h, c, lw=2.0, color='#2166ac', label='carga (MW)')
    ax.plot(h, g, lw=2.0, color='#e8a33d', label='geração distribuída (MW)')
    ax.plot(h, f, lw=1.4, color='#41ab5d', label='vindo da subtransmissão (MW)')
    ax.axhline(0, color='#999', lw=0.8)

    # fluxo reverso: onde a subestacao exporta em vez de importar
    rev = [x for x in f if x is not None and x < 0]
    if rev:
        ax.fill_between(h, 0, [min(0, x) if x is not None else 0 for x in f],
                        color='#e31a1c', alpha=0.18, lw=0,
                        label=f'fluxo reverso ({len(rev)} passos)')

    gv = [x for x in g if x is not None]
    if gv:
        i = g.index(max(gv))
        cov = 100 * g[i] / c[i] if c[i] else 0
        ax.annotate(f'pico de GD {g[i]:,.1f} MW às {int(h[i]):02d}:'
                    f'{int((h[i]%1)*60):02d}\ncobre {cov:.0f}% da carga do instante',
                    xy=(h[i], g[i]), xytext=(h[i] + 1.2, g[i] * 1.02),
                    fontsize=8, color='#7a5518',
                    arrowprops=dict(arrowstyle='-', color='#c99', lw=0.8))

    ax.set_title(titulo, fontsize=12, weight='bold', loc='left')
    ax.set_xlabel('hora do dia')
    ax.set_ylabel('potência (MW)')
    ax.set_xticks(range(0, 25, 2))
    ax.set_xlim(0, 24)
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(alpha=.25, lw=.4)
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    if not mostrar:
        plt.close(fig)
    return caminho


def _soma_series(saida, passos):
    """Soma as series das subestacoes passo a passo — a curva da concessao."""
    tot = {k: [0.0] * passos for k in ('fonte_kw', 'gd_kw', 'perdas_kw')}
    conta = [0] * passos
    for se in saida:
        s = se.get('serie') or {}
        if not s:
            continue
        for k in tot:
            for i, v in enumerate(s.get(k) or []):
                if v is not None and i < passos:
                    tot[k][i] += v
        for i, v in enumerate(s.get('gd_kw') or []):
            if v is not None and i < passos:
                conta[i] += 1
    # passo que nenhuma subestacao resolveu vira None, para nao desenhar zero
    for k in tot:
        tot[k] = [v if conta[i] else None for i, v in enumerate(tot[k])]
    return tot


def grafico(saida, raiz):
    """Onde estao as perdas: por alimentador e por subestacao."""
    import interativo
    plt = interativo.pyplot()

    alim = [(v['perdas_pct'], v['kWh'])
            for se in saida for v in (se.get('alimentadores') or {}).values()
            if v.get('perdas_pct') is not None and 0 < v['perdas_pct'] < 60]
    ses = sorted((x for x in saida if x['perdas_pct']),
                 key=lambda x: -x['perdas_pct'])[:20]
    ent = sum(x['kWh_injetado'] for x in saida) / 1e6
    per = sum(x['kWh_perdas'] for x in saida) / 1e6

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=110)
    if alim:
        p = [x[0] for x in alim]
        a1.hist(p, bins=45, color='#41ab5d', edgecolor='white', lw=.4)
        med = sorted(p)[len(p) // 2]
        a1.axvline(med, color='#e31a1c', lw=1.4, ls='--',
                   label=f'mediana {med:.2f}%')
        a1.legend(fontsize=9)
    a1.set_title(f'Perdas por alimentador — {len(alim):,} alimentadores',
                 loc='left', fontsize=12, weight='bold')
    a1.set_xlabel('perdas (% da energia injetada no dia)')
    a1.set_ylabel('alimentadores')
    a1.grid(alpha=.25, lw=.4)

    if ses:
        a2.barh([x['se'] for x in ses][::-1], [x['perdas_pct'] for x in ses][::-1],
                color='#fd8d3c')
    a2.set_title('20 subestações com maior perda', loc='left',
                 fontsize=12, weight='bold')
    a2.set_xlabel('perdas (%)')
    a2.grid(alpha=.25, axis='x', lw=.4)

    fig.suptitle(f'{os.path.basename(raiz)} — {ent:,.1f} GWh injetados no dia, '
                 f'{per:,.1f} GWh de perdas ({100*per/max(ent,1e-9):.2f}%)',
                 fontsize=10, color='#555', x=.01, ha='left')
    fig.tight_layout()
    interativo.mostra(plt, os.path.join(raiz, 'energia_dia.png'))


def _painel():
    import interativo
    v = interativo.formulario('energia', 'Energia e perdas do dia', [
        {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes()},
        {'chave': 'se', 'tipo': 'texto', 'rotulo': 'Subestações', 'padrao': '',
         'dica': 'vazio = todas   •   ex.: DABR TBAN'},
        {'chave': 'passos', 'tipo': 'inteiro', 'rotulo': 'Passos no dia',
         'padrao': 96, 'minimo': 4, 'maximo': 1440,
         'dica': '96 = um passo de 15 min, o mesmo da curva de carga da BDGD'},
        {'chave': 'curvas', 'tipo': 'bool', 'rotulo': 'Curvas de geração',
         'padrao': True,
         'dica': 'carga × GD ao longo do dia: uma por subestação, mais a geral'},
    ], ajuda='Roda o dia inteiro em instantâneos independentes e integra a '
             'energia entregue e as perdas de cada alimentador. É o número '
             'comparável com o PERD_* declarado na CTMT.')
    if not v:
        return False
    sys.argv += [v['raiz'], '--passos', str(v['passos']), '--grafico']
    if v['curvas']:
        sys.argv.append('--curvas')
    if v['se'].strip():
        sys.argv += ['--se'] + v['se'].split()
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('raiz', nargs='?', default='MODELOS_V8')
    ap.add_argument('--se', nargs='*')
    ap.add_argument('--passos', type=int, default=96,
                    help='passos no dia (96 = 15 min, o passo da CRVCRG)')
    ap.add_argument('--grafico', action='store_true',
                    help='mostra a distribuicao das perdas ao final')
    ap.add_argument('--curvas', action='store_true',
                    help='curva de carga x geracao do dia: uma por subestacao '
                         'em <SE>/curva_gd.png, mais a geral na raiz')
    a = ap.parse_args()

    raiz = os.path.abspath(a.raiz)
    itens = _masters(raiz, set(a.se) if a.se else None)
    if not itens:
        raise SystemExit(f'nenhum MASTER em {raiz}')

    import opendssdirect as dss
    print(f'{len(itens)} subestacoes | {a.passos} passos de '
          f'{24*60//a.passos} min\n')
    print(f'{"SE":6s} {"passos":>8s} {"injetado kWh":>14s} {"perdas kWh":>12s} '
          f'{"perdas %":>9s} {"pico GD MW":>9s}')
    saida = []
    plt = None
    n_curvas = 0
    for se, m in itens:
        ent, perd, ok, falhos, n_comp, por_alim, serie = dia(dss, m, a.passos)
        pct = 100 * perd / ent if ent > 1 else None
        gd = [x for x in serie['gd_kw'] if x]
        print(f'{se:6s} {ok:4d}/{a.passos:<3d} {ent:14,.0f} {perd:12,.0f} '
              f'{pct if pct is None else round(pct, 2):>9} '
              f'{(max(gd)/1000 if gd else 0):9,.1f} '
              f'{"" if not falhos else f"falham {len(falhos)}"}', flush=True)
        saida.append({'se': se, 'passos_ok': ok, 'passos': a.passos,
                      'kWh_injetado': round(ent, 1), 'kWh_perdas': round(perd, 1),
                      'perdas_pct': None if pct is None else round(pct, 3),
                      'passos_falhos': falhos, 'compilacoes': n_comp,
                      'kWh_gd': round(sum(gd) * 24.0 / a.passos, 1),
                      'pico_gd_kW': round(max(gd), 1) if gd else 0.0,
                      'serie': serie,
                      'alimentadores': {
                          k: {'kWh': round(v[0], 1),
                              'kWh_perdas': round(v[1], 1),
                              'perdas_pct': (round(100 * v[1] / v[0], 3)
                                             if v[0] > 1 else None)}
                          for k, v in sorted(por_alim.items())}})
        if a.curvas:
            import interativo
            plt = plt or interativo.pyplot()
            if curva_dia(serie, a.passos, f'{se} — dia útil',
                         os.path.join(raiz, se, 'curva_gd.png'), plt):
                n_curvas += 1

    json.dump(saida, open(os.path.join(raiz, 'energia_dia.json'), 'w',
                          encoding='utf-8'), indent=1, ensure_ascii=False)
    bons = [x for x in saida if x['passos_ok'] == a.passos]
    print(f'\n{len(bons)} de {len(saida)} com o dia inteiro resolvido')
    if n_curvas:
        print(f'{n_curvas} curvas de geração em <SE>/curva_gd.png')
    print(f'detalhe em {os.path.join(raiz, "energia_dia.json")}')

    if a.grafico or a.curvas:
        import interativo
        plt = plt or interativo.pyplot()
        gd_tot = sum(x['kWh_gd'] for x in saida) / 1e6
        ent_tot = sum(x['kWh_injetado'] for x in saida) / 1e6
        curva_dia(_soma_series(saida, a.passos), a.passos,
                  f'{os.path.basename(raiz)} — concessão inteira, {len(saida)} '
                  f'subestações  |  GD = {gd_tot:,.1f} de {ent_tot:,.1f} GWh '
                  f'no dia ({100*gd_tot/max(ent_tot,1e-9):.1f}%)',
                  os.path.join(raiz, 'curva_gd_geral.png'), plt, mostrar=True)
        print(f'curva geral em {os.path.join(raiz, "curva_gd_geral.png")}')
    if a.grafico:
        grafico(saida, raiz)
    elif a.curvas:
        import interativo
        interativo.mostra(plt)


if __name__ == '__main__':
    main()
