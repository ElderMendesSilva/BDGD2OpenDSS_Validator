# -*- coding: utf-8 -*-
"""
VALIDADOR — roda um modelo gerado e verifica o que costuma quebrar.

    python validador.py                    abre o painel e pergunta a pasta
    python validador.py MODELOS/DEMB       so uma subestacao
    python validador.py MODELOS            o MASTER-GERAL e todas as subestacoes
    python validador.py MODELOS --geral    so o modelo completo da concessao
    python validador.py MODELOS --ses      so os modelos por subestacao

Checa, nesta ordem:
  1. compila                     5. tensoes em p.u. por nivel
  2. converge                    6. linhas acima da ampacidade
  3. cargas eletricamente isoladas   7. perdas em % da injecao
  4. ramos isolados              8. barras fora da faixa do PRODIST M8
"""
import os, sys, math, json, glob, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss import diagnostico

try:
    import opendssdirect as dss
except ImportError:
    raise SystemExit('Instale: pip install opendssdirect.py')

# PRODIST Modulo 8 — faixas para tensao nominal > 1 kV
ADEQ = (0.95, 1.05)
PREC = (0.93, 1.07)


def valida(pasta, referencia=None):
    # O Compile do OpenDSS TROCA o diretorio de trabalho do processo. Sem
    # guardar e restaurar, a partir da segunda subestacao todo caminho
    # relativo aponta para o lugar errado — na pratica so a primeira era
    # validada e a escrita do JSON no fim estourava.
    cwd = os.getcwd()
    pasta = os.path.abspath(pasta)
    m = sorted(glob.glob(os.path.join(pasta, 'MASTER-*.dss')))
    if not m:
        return None
    r = {'modelo': os.path.splitext(os.path.basename(m[0]))[0].replace('MASTER-', '')}
    dss.Text.Command('Clear')
    try:
        dss.Text.Command(f'Compile "{m[0]}"')
        r['compila'] = True
    except Exception as e:
        os.chdir(cwd)
        return {**r, 'compila': False, 'erro': str(e)[:300],
                'causa': 'MODELO_QUEBRADO', 'acionavel': True,
                'causa_detalhe': 'nao compila: ' + str(e)[:150]}

    dss.Text.Command('Set mode=snap')
    dss.Text.Command('Set controlmode=static')
    try:
        dss.Text.Command('Solve')
    except Exception as e:
        r['aviso_solve'] = str(e)[:120]

    p = dss.Circuit.TotalPower()[0]
    r['resolve'] = not (isinstance(p, float) and (math.isnan(p) or math.isinf(p)))
    r['converge'] = dss.Solution.Converged()
    r['iteracoes'] = dss.Solution.Iterations()
    r['n_barras'] = dss.Circuit.NumBuses()
    r['n_cargas'] = dss.Loads.Count()
    r['n_linhas'] = dss.Lines.Count()
    r['n_trafos'] = dss.Transformers.Count()
    # NaN no vetor de tensao. TotalPower sozinho NAO detecta: ele soma a
    # potencia das fontes, e uma ilha sem fonte nunca entra nessa conta. Foi
    # assim que a DALP passou como OK carregando 9 barras NaN — que no motor
    # oficial da EPRI (COM v11) viram 49.857 nos NaN e derrubam a rede inteira.
    vmag = dss.Circuit.AllBusMagPu()
    nomes_no = dss.Circuit.AllNodeNames()
    nan = [i for i, x in enumerate(vmag) if math.isnan(x)]
    r['nos_nan'] = len(nan)
    r['barras_nan'] = len({nomes_no[i].split('.')[0] for i in nan})
    if nan:
        b0 = nomes_no[nan[0]].split('.')[0]
        dss.Circuit.SetActiveBus(b0)
        r['nan_exemplo'] = f'{b0} PCE={[x for x in (dss.Bus.AllPCEatBus() or []) if x]}'

    if not r['resolve']:
        os.chdir(cwd)
        return r

    r['P_fonte_kW'] = round(-p, 1)
    perdas = dss.Circuit.Losses()[0] / 1000
    r['perdas_kW'] = round(perdas, 1)
    # Perdas sobre a energia INJETADA (fonte + GD), como no Modulo 7 do
    # PRODIST — nao sobre a fonte. Com geracao distribuida forte a fonte
    # quase zera e a razao perde sentido: na DALP sao 1.737 kW de fonte
    # contra 54.339 kW de GD, o que dava 305% de perdas sobre a fonte e
    # 9,44% sobre a injetada. Varias subestacoes foram classificadas como
    # TENSAO_BAIXA por causa dessa razao inflada.
    gd = 0.0
    i = dss.PVsystems.First()
    while i:
        dss.Circuit.SetActiveElement('PVSystem.' + dss.PVsystems.Name())
        pw = dss.CktElement.Powers()[0::2]
        gd += -sum(pw[:dss.CktElement.NumPhases()])
        i = dss.PVsystems.Next()
    r['P_gd_kW'] = round(gd, 1)
    injetada = -p + gd
    r['P_injetada_kW'] = round(injetada, 1)
    r['perdas_pct'] = round(100 * perdas / max(injetada, 1), 2)
    # AllIsolatedLoads() percorre a topologia a partir de UMA fonte. No
    # MASTER-GERAL ha uma fonte por patio de AT, entao tudo que e alimentado
    # pelas demais aparece como isolado — falso positivo em massa (1.271
    # contra as 54 reais, no teste com duas subestacoes). A medida confiavel
    # e eletrica: carga cuja barra ficou praticamente sem tensao.
    r['cargas_isoladas_topologia'] = len(dss.Topology.AllIsolatedLoads())
    r['ramos_isolados'] = len(dss.Topology.AllIsolatedBranches())
    mortas = 0
    i = dss.Loads.First()
    while i:
        dss.Circuit.SetActiveElement('Load.' + dss.Loads.Name())
        v = dss.CktElement.VoltagesMagAng()[0::2]
        if v and max(v) < 1.0:                 # volts, nao pu: barra morta
            mortas += 1
        i = dss.Loads.Next()
    r['cargas_sem_tensao'] = mortas
    # quantas fontes energizam este modelo: no MASTER-GERAL e uma por patio
    # de AT, entao o numero diz quantas subestacoes estao de fato alimentadas
    dss.Circuit.SetActiveClass('Vsource')
    r['n_fontes'] = dss.ActiveClass.NumElements()
    r['n_vaos'] = sum(1 for x in dss.Lines.AllNames() if x.lower().startswith('vao_'))

    mt = []
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        if dss.Bus.kVBase() > 1:
            pu = [x for x in dss.Bus.puVmagAngle()[0::2] if 0.01 < x < 3]
            if pu:
                mt.append(min(pu))
    if mt:
        r['V_MT_min'] = round(min(mt), 3)
        r['V_MT_mediana'] = round(statistics.median(mt), 3)
        r['V_MT_max'] = round(max(mt), 3)
        r['barras_precarias'] = sum(1 for v in mt if PREC[0] <= v < ADEQ[0] or ADEQ[1] < v <= PREC[1])
        r['barras_criticas'] = sum(1 for v in mt if v < PREC[0] or v > PREC[1])

    sob = 0
    for ln in dss.Lines.AllNames():
        dss.Circuit.SetActiveElement('Line.' + ln)
        na = dss.CktElement.NormalAmps()
        if na > 1:
            c = dss.CktElement.CurrentsMagAng()
            nc = dss.CktElement.NumConductors()
            mx = max(c[2 * i] for i in range(nc))
            if not math.isnan(mx) and mx > na:
                sob += 1
    r['linhas_acima_ampacidade'] = sob

    # reguladores no tape maximo: sinal de que a rede pede mais reforco do
    # que um regulador entrega. Sem isso, a subtensao parece defeito nosso.
    nreg = sat = 0
    i = dss.RegControls.First()
    while i:
        nreg += 1
        tr = dss.RegControls.Transformer()
        dss.Transformers.Name(tr)
        if dss.Transformers.Tap() >= dss.Transformers.MaxTap() - 1e-6:
            sat += 1
        i = dss.RegControls.Next()
    r['reguladores'] = nreg
    r['reguladores_saturados'] = sat

    os.chdir(cwd)
    d = []
    if not r['converge']:
        d.append('nao converge')
    if r['cargas_sem_tensao']:
        d.append(f'{r["cargas_sem_tensao"]} cargas sem tensao')
    if r.get('perdas_pct', 0) > 15:
        d.append(f'perdas de {r["perdas_pct"]}% — verificar tensoes de BT')
    if r.get('V_MT_mediana', 1) < 0.9 or r.get('V_MT_mediana', 1) > 1.1:
        d.append('tensao mediana fora de faixa — verificar Voltagebases')
    r['diagnostico'] = d or ['ok']

    # causa raiz: separa defeito do conversor de caracteristica da rede
    res = {}
    fr = os.path.join(pasta, 'resumo.json')
    if os.path.exists(fr):
        try:
            res = json.load(open(fr, encoding='utf-8'))
        except Exception:
            res = {}
    causa, detalhe, acionavel = diagnostico.classificar(
        r, res, {'reg_total': nreg, 'reguladores_saturados': sat,
                 'reg_saturados': sat, 'mva_instalado': res.get('mva_at')},
        referencia)
    r['causa'] = causa
    r['causa_detalhe'] = detalhe
    r['acionavel'] = acionavel
    return r


def grafico(out, alvo):
    """A causa raiz por barra: separa defeito nosso de caracteristica da rede.

    E a leitura que interessa depois de uma varredura — nao "quantos deram
    problema", e sim quantos dao problema QUE E NOSSO. Verde e o que esta
    no esperado, vermelho o que e acionavel aqui.
    """
    import collections
    import interativo
    plt = interativo.pyplot()

    c = collections.Counter(r.get('causa') or '(sem causa)' for r in out)
    acion = {r.get('causa') for r in out if r.get('acionavel')}
    rot = [k for k, _ in c.most_common()]
    val = [c[k] for k in rot]
    cor = ['#b3261e' if k in acion else ('#1a7f37' if k == 'OK' else '#b35c00')
           for k in rot]

    v = [r.get('V_MT_mediana') for r in out if r.get('V_MT_mediana')]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=110)
    a1.barh(rot[::-1], val[::-1], color=cor[::-1])
    for i, n in enumerate(val[::-1]):
        a1.text(n, i, f' {n}', va='center', fontsize=9)
    a1.set_title(f'Causa raiz — {len(out)} modelos', loc='left',
                 fontsize=12, weight='bold')
    a1.set_xlabel('modelos   (vermelho = acionável no conversor)')
    a1.grid(alpha=.25, axis='x', lw=.4)

    if v:
        a2.hist(v, bins=40, color='#4292c6', edgecolor='white', lw=.4)
        a2.axvspan(ADEQ[0], ADEQ[1], color='#41ab5d', alpha=.12,
                   label='faixa adequada (M8)')
        a2.legend(fontsize=9)
    a2.set_title('Tensão mediana de MT', loc='left', fontsize=12, weight='bold')
    a2.set_xlabel('tensão (pu)')
    a2.set_ylabel('modelos')
    a2.grid(alpha=.25, lw=.4)

    fig.suptitle(os.path.basename(alvo), fontsize=10, color='#666', x=.01, ha='left')
    fig.tight_layout()
    interativo.mostra(plt, os.path.join(alvo, 'validacao.png'))


def _painel():
    import interativo
    v = interativo.formulario('validador', 'Validador dos modelos', [
        {'chave': 'alvo', 'tipo': 'pasta', 'rotulo': 'Pasta',
         'padrao': interativo.modelos_recentes(),
         'dica': 'a raiz dos modelos, ou a pasta de uma subestação só'},
        {'chave': 'escopo', 'tipo': 'opcao', 'rotulo': 'Validar', 'padrao': 'tudo',
         'valores': ['tudo', 'só o MASTER-GERAL', 'só as subestações']},
    ], ajuda='Compila e resolve cada modelo e classifica a causa raiz do que '
             'estiver fora do esperado — separando defeito do conversor de '
             'característica da rede.')
    if not v:
        return False
    sys.argv += [v['alvo'], '--grafico']
    if v['escopo'].startswith('só o'):
        sys.argv.append('--geral')
    elif v['escopo'].startswith('só as'):
        sys.argv.append('--ses')
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    flags = {x for x in sys.argv[1:] if x.startswith('--')}
    alvo = os.path.abspath(args[0] if args else 'MODELOS')

    # A pasta de saida agora tem MASTER-GERAL.dss na raiz E um MASTER por
    # subestacao nas subpastas. Sem tratar os dois casos, a presenca do geral
    # faria o validador parar nele e nunca varrer as subestacoes.
    raiz = sorted(glob.glob(os.path.join(alvo, 'MASTER-*.dss')))
    subs = sorted(d for d in glob.glob(os.path.join(alvo, '*'))
                  if os.path.isdir(d) and glob.glob(os.path.join(d, 'MASTER-*.dss')))
    if raiz and not subs:
        pastas = [alvo]                       # apontaram direto para uma SE
    elif '--geral' in flags:
        pastas = [alvo] if raiz else []
    elif '--ses' in flags:
        pastas = subs
    else:
        pastas = ([alvo] if raiz else []) + subs
    # O limiar de REDE_EXTENSA sai da PROPRIA base (achado 3): 60 km e a
    # mediana de 8,9 km vieram do censo da Enel SP, e em Roraima — onde os
    # alimentadores tem 288 a 424 km — classificavam 4 de 20 subestacoes
    # citando uma mediana que nao era daquela concessao. Os resumo.json ja
    # estao no disco, entao o censo custa uma varredura de arquivos pequenos.
    resumos = []
    for p in pastas:
        fr = os.path.join(p, 'resumo.json')
        if os.path.exists(fr):
            try:
                with open(fr, encoding='utf-8') as fh:
                    resumos.append(json.load(fh))
            except Exception:
                pass
    ref = diagnostico.referencia_de(resumos)
    if ref.get('km_alim_mediana'):
        print(f'referencia desta base: mediana de '
              f'{ref["km_alim_mediana"]:.1f} km por alimentador em '
              f'{ref["n"]} subestacoes; REDE_EXTENSA acima de '
              f'{ref["km_alim_alto"]:.0f} km\n')

    out = []
    for p in pastas:
        r = valida(p, ref)
        if not r:
            continue
        out.append(r)
        print(f"{r['modelo']:10s} compila={r['compila']} resolve={r.get('resolve')} "
              f"conv={r.get('converge')} iter={r.get('iteracoes')} "
              f"fontes={r.get('n_fontes','—')} vaos={r.get('n_vaos','—')} "
              f"mortas={r.get('cargas_sem_tensao','—')} nan={r.get('nos_nan','—')} "
              f"perdas={r.get('perdas_pct','—')}% Vmed={r.get('V_MT_mediana','—')} "
              f"sobrecarga={r.get('linhas_acima_ampacidade','—')} "
              f"| {r.get('causa','?'):18s} {r.get('causa_detalhe','')[:52]}", flush=True)
    if out:
        # encoding explicito: com ensure_ascii=False o JSON leva acento, e sem
        # dizer utf-8 o Python grava na codificacao do sistema (cp1252 aqui).
        # O arquivo entao nao volta: `can't decode byte 0x97`.
        json.dump(out, open(os.path.join(alvo, 'validacao.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)
        ok = sum(1 for r in out if r.get('diagnostico') == ['ok'])
        print(f'\n{ok} de {len(out)} modelos sem ressalva.')
        if '--grafico' in flags:
            grafico(out, alvo)


if __name__ == '__main__':
    main()
