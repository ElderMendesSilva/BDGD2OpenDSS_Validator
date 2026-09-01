# -*- coding: utf-8 -*-
"""
VALIDADOR — roda um modelo gerado e verifica o que costuma quebrar.

    python validador.py                    abre o painel e pergunta a pasta
    python validador.py MODELOS/DEMB       so uma subestacao
    python validador.py MODELOS            o MASTER-GERAL e todas as subestacoes
    python validador.py MODELOS --geral    so o modelo completo da concessao
    python validador.py MODELOS --ses      so os modelos por subestacao
    python validador.py MODELOS --jobs 1   em serie, um modelo de cada vez

Checa, nesta ordem:
  1. compila                     5. tensoes em p.u. por nivel
  2. converge                    6. linhas acima da ampacidade
  3. cargas eletricamente isoladas   7. perdas em % da injecao
  4. ramos isolados              8. barras fora da faixa do PRODIST M8
"""
import argparse
import os, sys, math, json, glob, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss import diagnostico, lote, pausa, plataforma, pool
from bdgd2dss import escrita

try:
    import opendssdirect as dss
except ImportError:
    raise SystemExit('Instale: pip install opendssdirect.py')

# PRODIST Modulo 8 — faixas para tensao nominal > 1 kV
ADEQ = (0.95, 1.05)
PREC = (0.93, 1.07)

# Quantos modelos validar ao mesmo tempo. Oito e o mesmo padrao do `energia`,
# do `verifica` e do `ampacidade`: medido, o ganho satura por volta de quatro
# porque o custo dominante e compilar o modelo a partir do disco, e acima disso
# so se paga memoria. `--jobs 1` volta a serie, que e a referencia.
JOBS = 8


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
    # ONDE A PERDA ACONTECE, e nao so quanto ela e. O achado 11 mediu que o
    # ferro dos transformadores e parcela GRANDE do que este modelo reporta —
    # mediana da ordem de 60% —, e isso muda a natureza da comparacao com o
    # `PERD_*` declarado: se a distribuidora reporta so a parcela dependente de
    # carga, os dois numeros estao certos medindo coisas diferentes. Sem esta
    # divisao a pergunta so se responde abrindo o modelo, que e o que
    # `resultados/` existe para evitar.
    #
    # ATENCAO A UNIDADE: `Circuit.Losses` vem em WATTS e `Circuit.LineLosses`
    # em kW. Dividir os dois por 1000 daria uma diferenca negativa e sem
    # sentido — o tipo de erro que passa por resultado.
    try:
        linhas_kw = dss.Circuit.LineLosses()[0]
        r['perdas_linhas_kW'] = round(linhas_kw, 1)
        # O resto e transformador: ferro (constante) mais cobre (com a carga).
        # O motor nao separa esses dois, entao o nome diz o que o numero e.
        r['perdas_trafos_kW'] = round(perdas - linhas_kw, 1)
        # NaN TEM DE VIRAR None, e nao passar adiante como float. A V25
        # publicou 2 subestacoes com `perdas_trafos_pct` NaN, e o efeito nao
        # foi um valor esquisito: foi `sorted()` devolvendo lista DESORDENADA,
        # porque toda comparacao com NaN e falsa. O percentil 75 saiu menor que
        # a mediana e o numero passaria por resultado. `None` diz "nao sei"; NaN
        # contamina a estatistica de quem consumir.
        pct = (100.0 * (perdas - linhas_kw) / perdas) if perdas else None
        if pct is not None and math.isnan(pct):
            pct = None
        r['perdas_trafos_pct'] = None if pct is None else round(pct, 1)
    except Exception:                                    # noqa: BLE001
        # Motor que nao expoe `LineLosses` nao pode custar a validacao inteira.
        r['perdas_linhas_kW'] = None
        r['perdas_trafos_kW'] = None
        r['perdas_trafos_pct'] = None
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
    # O MESMO DEFEITO VALE PARA OS RAMOS, e isso custou tres achados. O
    # comentario acima ja dizia que `AllIsolatedLoads` percorre a topologia a
    # partir de UMA fonte — mas `AllIsolatedBranches`, que tem exatamente o
    # mesmo problema, foi tratado como medida real ate 01/09/2026.
    #
    # Medido nas 4.189 subestacoes da V25: as de UMA fonte tem mediana de 0,86%
    # de ramos "isolados"; as de DUAS OU MAIS, 68,88%. Oitenta vezes mais, e a
    # rede esta energizada — conferido elemento a elemento na Light, onde 300
    # de 300 linhas "isoladas" tinham 1,02 pu e so morriam ao desligar a
    # segunda fonte.
    #
    # O campo fica, com nome que diz o que ele e. A medida ELETRICA e a de
    # baixo.
    r['ramos_isolados_topologia'] = len(dss.Topology.AllIsolatedBranches())
    # RAMO SEM TENSAO: a medida que sobrevive a mais de uma fonte. Uma barra
    # com menos de 1 V esta morta em qualquer topologia.
    mortas_b = set()
    nomes = dss.Circuit.AllBusNames()
    for b in nomes:
        dss.Circuit.SetActiveBus(b)
        v = dss.Bus.VMagAngle()[0::2]
        if not v or max(v) < 1.0:
            mortas_b.add(b.lower())
    sem_v = 0
    i = dss.Lines.First()
    while i:
        b1 = dss.Lines.Bus1().split('.')[0].lower()
        if b1 in mortas_b:
            sem_v += 1
        i = dss.Lines.Next()
    r['ramos_sem_tensao'] = sem_v
    r['barras_sem_tensao'] = len(mortas_b)
    # COMPATIBILIDADE: `ramos_isolados` continua existindo para nao quebrar o
    # coletor e as comparacoes com rodadas anteriores, mas passa a carregar a
    # medida ELETRICA — que e o que o nome sempre prometeu.
    r['ramos_isolados'] = sem_v
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


def _uma(tarefa):
    """Um modelo, num processo so dele. Trabalhador do modo paralelo.

    Precisa ser funcao de modulo, e nao um `lambda` ou uma closure: no Windows
    o `ProcessPoolExecutor` cria o filho por spawn, que importa este arquivo de
    novo e procura a funcao pelo nome.
    """
    # PAUSA: sempre antes de comecar, nunca no meio. Assim o que espera
    # segura poucos MB em vez do circuito inteiro.
    pausa.espera()
    pasta, ref = tarefa
    # UMA SUBESTACAO NAO PODE DERRUBAR A ETAPA. Ver o caso da 1726671 da
    # Cemig-D na V16: um AVISO do OpenDSS levantado como excecao matou o
    # `ligacao` inteiro e o trabalho das outras 412 subestacoes.
    try:
        return valida(pasta, ref)
    except Exception as e:
        return {'modelo': os.path.basename(pasta), 'compila': False,
                'erro': f'{type(e).__name__}: {str(e)[:200]}',
                'causa': 'MODELO_QUEBRADO', 'acionavel': True,
                'causa_detalhe': f'{type(e).__name__} ao validar',
                'diagnostico': ['falhou']}


def _linha(r):
    print(f"{r['modelo']:10s} compila={r['compila']} resolve={r.get('resolve')} "
          f"conv={r.get('converge')} iter={r.get('iteracoes')} "
          f"fontes={r.get('n_fontes','—')} vaos={r.get('n_vaos','—')} "
          f"mortas={r.get('cargas_sem_tensao','—')} nan={r.get('nos_nan','—')} "
          f"perdas={r.get('perdas_pct','—')}% Vmed={r.get('V_MT_mediana','—')} "
          f"sobrecarga={r.get('linhas_acima_ampacidade','—')} "
          f"| {r.get('causa','?'):18s} {r.get('causa_detalhe','')[:52]}", flush=True)


def _painel():
    import interativo
    v = interativo.formulario('validador', 'Validador dos modelos', [
        {'chave': 'alvo', 'tipo': 'pasta', 'rotulo': 'Pasta',
         'padrao': interativo.modelos_recentes(),
         'dica': 'a raiz dos modelos, ou a pasta de uma subestação só'},
        {'chave': 'escopo', 'tipo': 'opcao', 'rotulo': 'Validar', 'padrao': 'tudo',
         'valores': ['tudo', 'só o MASTER-GERAL', 'só as subestações']},
        {'chave': 'jobs', 'tipo': 'inteiro', 'rotulo': 'Modelos em paralelo',
         'padrao': JOBS, 'minimo': 1, 'maximo': 32,
         'dica': 'cada um custa um processo com a sua cópia do OpenDSS; '
                 'com 1 valida em série'},
    ], ajuda='Compila e resolve cada modelo e classifica a causa raiz do que '
             'estiver fora do esperado — separando defeito do conversor de '
             'característica da rede.')
    if not v:
        return False
    sys.argv += [v['alvo'], '--grafico', '--jobs', str(v['jobs'])]
    if v['escopo'].startswith('só o'):
        sys.argv.append('--geral')
    elif v['escopo'].startswith('só as'):
        sys.argv.append('--ses')
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(
        description=__doc__.split('\n')[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('alvo', nargs='?', default='MODELOS',
                    help='pasta dos modelos, ou de uma subestacao so')
    ap.add_argument('--geral', action='store_true',
                    help='so o modelo completo da concessao')
    ap.add_argument('--ses', action='store_true',
                    help='so os modelos por subestacao')
    ap.add_argument('--grafico', action='store_true',
                    help='desenha a causa raiz e a tensao mediana ao fim')
    ap.add_argument('--jobs', type=int, default=JOBS, metavar='N',
                    help=f'modelos em paralelo (padrao {JOBS}); com 1 valida '
                         f'em serie')
    a = ap.parse_args()
    alvo = os.path.abspath(a.alvo)

    # A pasta de saida agora tem MASTER-GERAL.dss na raiz E um MASTER por
    # subestacao nas subpastas. Sem tratar os dois casos, a presenca do geral
    # faria o validador parar nele e nunca varrer as subestacoes.
    raiz = sorted(glob.glob(os.path.join(alvo, 'MASTER-*.dss')))
    subs = sorted(d for d in glob.glob(os.path.join(alvo, '*'))
                  if os.path.isdir(d) and glob.glob(os.path.join(d, 'MASTER-*.dss')))
    if raiz and not subs:
        pastas = [alvo]                       # apontaram direto para uma SE
    elif a.geral:
        pastas = [alvo] if raiz else []
    elif a.ses:
        pastas = subs
    else:
        pastas = ([alvo] if raiz else []) + subs
    # O limiar de REDE_EXTENSA sai da PROPRIA base (achado 3): 60 km e a
    # mediana de 8,9 km vieram do censo da Enel SP, e em Roraima — onde os
    # alimentadores tem 288 a 424 km — classificavam 4 de 20 subestacoes
    # citando uma mediana que nao era daquela concessao. Os resumo.json ja
    # estao no disco, entao o censo custa uma varredura de arquivos pequenos.
    #
    # ELE E DE TODA A BASE, e por isso fica AQUI, antes de qualquer paralelismo:
    # se cada trabalhador calculasse o seu, o limiar mudaria conforme o lote e
    # a mesma subestacao seria classificada de um jeito sozinha e de outro no
    # meio das demais.
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

    # EM PARALELO, mesmo padrao do `energia.py`, do `verifica.py` e do
    # `ampacidade.py`. Cada modelo e independente: compila, resolve e e
    # descartado. O que impedia rodar junto era o `opendssdirect` guardar
    # circuito e solucao em variaveis globais do processo — em PROCESSOS
    # separados isso deixa de existir, e cada trabalhador faz exatamente o
    # mesmo trabalho que faria em serie.
    #
    # A ORDEM DO JSON NAO PODE DEPENDER DE QUEM TERMINOU PRIMEIRO: `validacao`
    # sai na ordem de `pastas`, que e a da execucao serial. Sem isso o arquivo
    # mudaria a cada rodada sem nenhum numero ter mudado, e a comparacao entre
    # duas geracoes — que e como se prova que uma mudanca nao mexeu no
    # resultado — deixaria de valer.
    por_pasta = {}

    def grava():
        """Poe no disco o que ja terminou, e devolve na ordem de `pastas`.

        Chamada DENTRO do `with` do pool, e nao depois. Sair do `with` e
        `shutdown(wait=True)`, e essa espera nao tem prazo: na V16 o
        `verifica` da Cemig-D terminou as 413 subestacoes e foi morto pelo
        limite de 6h antes de escrever — ver
        `testes/test_grava_antes_de_esperar.py`.

        encoding explicito: com ensure_ascii=False o JSON leva acento, e sem
        dizer utf-8 o Python grava na codificacao do sistema (cp1252 aqui). O
        arquivo entao nao volta: `can't decode byte 0x97`.
        """
        o = [por_pasta[p] for p in pastas if p in por_pasta]
        if o:
            json.dump(o, open(os.path.join(alvo, 'validacao.json'), 'w',
                              encoding='utf-8', newline=escrita.FIM_DE_LINHA), indent=1, ensure_ascii=False)
        return o

    if a.jobs > 1 and len(pastas) > 1:
        import concurrent.futures as cf
        # `spawn` nos dois sistemas. No Linux o padrao e `fork`, e o
        # filho nasceria com uma COPIA da DLL do OpenDSS ja carregada,
        # com circuito e solucao dentro — o estado compartilhado que os
        # processos separados existem para evitar.
        plataforma.prepara_processos()
        print(f'{a.jobs} modelos em paralelo', flush=True)
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            fila = lote.maior_primeiro(pastas, lambda p: p)
            fut = {ex.submit(_uma, (p, ref)): p for p in fila}
            for f_ in cf.as_completed(fut):
                r = f_.result()
                if r:
                    por_pasta[fut[f_]] = r
                    _linha(r)
            grava()
            # A SEGUNDA DEFESA. Gravar antes de sair do `with` salva o
            # RESULTADO; nao salva as horas de fila que vem depois.
            # Sair do `with` e `shutdown(wait=True)`, sem prazo.
            # Ver `bdgd2dss/pool.py` e o caso da Cemig-D na V16.
            pool.encerrar(ex, log=lambda m: print(m, flush=True))
    else:
        for p in pastas:
            pausa.espera()   # mesmo ponto de parada do paralelo
            r = valida(p, ref)
            if r:
                por_pasta[p] = r
                _linha(r)
    out = grava()

    if out:
        ok = sum(1 for r in out if r.get('diagnostico') == ['ok'])
        print(f'\n{ok} de {len(out)} modelos sem ressalva.')
        if a.grafico:
            grafico(out, alvo)


if __name__ == '__main__':
    main()
