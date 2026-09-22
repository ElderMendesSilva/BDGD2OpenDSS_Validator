# -*- coding: utf-8 -*-
"""
ORIENTACAO DOS REGULADORES DE TENSAO — achado 59
================================================

    python reguladores.py MODELOS_CMIG_V30
    python reguladores.py MODELOS_CMIG_V30 --se 1726536 --jobs 1

Roda DEPOIS do `converter.py` e ANTES do `ampacidade.py`, porque o criterio e
eletrico e porque a ordem importa: corrigir a orientacao muda a tensao em cerca
de 0,09 pu, e a tensao muda a corrente que o `ampacidade` mede.

O QUE ELE FAZ. Resolve o modelo, mede a direcao do fluxo em cada regulador e
escreve `_REGULADORES.dss` com um `RegControl.X.winding=N` para os que estao
com o controle no lado da FONTE. O arquivo e legivel, conta quantos foram, e
apagar o `redirect _REGULADORES.dss` do MASTER devolve o modelo ao que a BDGD
declara.

ANTES DE TUDO, O LACO ATRAVES DE TRANSFORMADOR — achado 70. Um caminho de MT
que liga os dois lados de um abaixador circula a diferenca de tensao, e com
ele fechado nenhuma medida adiante vale. Vai para `_LACOS.dss`. Ver
`escolher_lacos_de_transformador`.

DEPOIS, O BYPASS — achado 69. Regulador com a chave de bypass
fechada circula corrente de laco, e a direcao medida nele e a do laco, nao a
da carga. Dos candidatos de cada ciclo curto que contem um regulador, abre-se
o que nao desenergiza no nenhum e poe mais carga no regulador; as duas
medidas vao para o mesmo `_REGULADORES.dss`. Ver `escolher_bypass`.

POR QUE NAO DA PARA DECIDIR NA CONVERSAO. A BDGD nao declara qual PAC do
UNREMT e o lado da fonte, e a resposta depende da topologia resolvida — a
mesma razao pela qual o `ligacao.py` tambem roda depois. Ver
`bdgd2dss/orientacao.py` para o criterio e para as duas medicoes erradas que
precederam a certa.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import lacos, orientacao, pausa, plataforma     # noqa: E402
from bdgd2dss import escrita                                     # noqa: E402

try:
    import opendssdirect as dss
except Exception as e:                                 # pragma: no cover
    raise SystemExit(f'opendssdirect indisponivel: {e}')


def quais():
    """Nome, enrolamento controlado e transformador de cada RegControl.

    SO A IDENTIFICACAO, e nao a medida. O iterador do OpenDSS **pula elemento
    desabilitado**, e o passo desabilita os controles antes de medir o fluxo —
    juntar as duas coisas na mesma funcao devolvia lista VAZIA e a etapa
    reportava zero regulador numa subestacao com seis.
    """
    saida = []
    i = dss.RegControls.First()
    while i:
        saida.append({'nome': dss.RegControls.Name(),
                      'winding': dss.RegControls.Winding(),
                      'transformador': dss.RegControls.Transformer()})
        i = dss.RegControls.Next()
    return saida


def fluxos(regs):
    """Preenche `p_terminais` lendo os TRANSFORMADORES, que seguem ativos.

    A potencia vem por condutor e intercalada com o reativo; somar o ativo de
    cada terminal e o que da a direcao. Pegar so a primeira fase erraria em
    regulador trifasico desequilibrado.
    """
    for r in regs:
        dss.Circuit.SetActiveElement('Transformer.' + r['transformador'])
        p = dss.CktElement.Powers() or []
        n = dss.CktElement.NumConductors() or 1
        term = []
        for t in range(2):
            a, b = 2 * n * t, 2 * n * (t + 1)
            term.append(sum(p[a:b:2]) if len(p) >= b else 0.0)
        r['p_terminais'] = term
    return regs

# Quantas compilacoes a escolha do bypass pode custar numa subestacao. Cada
# candidata e um `Redirect` do MASTER inteiro; a 5001306, com 88 mil nos e
# seis bypass, pede doze. Acima disto a subestacao fica sem decisao, dito.
MAX_COMPILACOES_BYPASS = 60
# Laco com mais chaves que isto nao tem a forma de campo (entrada, saida e
# bypass): abrir a chave errada dele seria manobra inventada.
MAX_CHAVES_NO_LACO = 4
# Laco so de trechos (a AGT da NEOENERGIA43 tem seis): o teto e mais alto
# porque cada trecho e um candidato, e nao ha agrupamento em paralelo.
MAX_TRECHOS_NO_LACO = 12
# Dois candidatos que poem no regulador cargas a menos disto um do outro sao
# a mesma manobra — chaves em serie no mesmo caminho.
KW_EQUIVALENTE = 1.0


def _controles_das_chaves():
    """`line.<nome>` -> `SwtControl.<nome>` de quem a comanda."""
    saida = {}
    i = dss.SwtControls.First()
    while i:
        saida[dss.SwtControls.SwitchedObj().lower()] = (
            'SwtControl.' + dss.SwtControls.Name())
        i = dss.SwtControls.Next()
    return saida


def _p_banco(transformadores):
    """Potencia ativa no terminal 1, somada nas fases do banco, em modulo."""
    tot = 0.0
    for t in transformadores:
        dss.Circuit.SetActiveElement('Transformer.' + t)
        n = dss.CktElement.NumConductors() or 1
        tot += abs(sum((dss.CktElement.Powers() or [])[0:2 * n:2]))
    return tot


def _vivos():
    return sum(1 for v in dss.Circuit.AllBusMagPu() if v > 1e-3)


# Laco atraves de transformador com mais chaves que isto fica sem decisao: cada
# uma e uma compilacao. O da 5001306 tem tres.
MAX_CHAVES_LACO_TRAFO = 12
# Duas candidatas cuja perda difere menos que isto sao a mesma manobra — chaves
# em serie no mesmo caminho.
PERDA_EQUIVALENTE_KW = 1.0


def _chaves(elementos):
    saida = []
    for e in elementos:
        e = e.lower()
        if e.startswith('line.'):
            dss.Lines.Name(e.split('.', 1)[1])
            if dss.Lines.IsSwitch():
                saida.append(e)
    return saida


def _compila(master, chaves, controle):
    """Compila com as `chaves` abertas: `(convergiu, nos_vivos)`.

    Aviso de solucao (#485) nao derruba: vira `convergiu=False`, e a
    candidata que o provoca e recusada — ver `lacos.compilar`.
    """
    aviso = lacos.compilar(dss, master)
    for c in chaves:
        dss.Text.Command(f'Edit {c} enabled=no')
        if controle.get(c):
            dss.Text.Command(f'Edit {controle[c]} enabled=no')
    ok = lacos.resolver(dss) if chaves else aviso is None
    return bool(ok and dss.Solution.Converged()), _vivos()


def escolher_lacos_de_transformador(master):
    """Quais lacos atraves de transformador abrir: `(abertas, sem_decisao)`.

    ACHADO 70. Na 5001306 da EQUATORIAL6072, depois dos seis bypass, um laco
    de 42 elementos ligava por chaves de MT os dois lados do abaixador
    `MCG-D-TRF-TR1`, 34,5/13,8 kV. Abrir qualquer uma das tres chaves dele
    levou a perda de 64,5% para 11,6%, com os 88.003 nos vivos. Os outros 31
    lacos, na mesma tensao, nao mudavam nada.

    Um laco de cada vez, recompilando: abrir um pode desfazer outro.
    Chamada com o circuito compilado; deixa-o compilado de outro jeito.
    """
    pasta = os.path.dirname(master)
    fora = lacos.abertas(pasta)
    controle = _controles_das_chaves()
    abertas, sem_decisao = [], []
    decididas, vistos = [], set()
    base = _vivos()
    compilacoes = 0
    while True:
        lista = [x for x in lacos.lacos(dss, fora | set(decididas))
                 if lacos.incoerente(x) and x['fecha'].lower() not in vistos]
        if not lista:
            break
        lc = lista[0]
        vistos.add(lc['fecha'].lower())
        cands = _chaves(lc['ciclo'])
        motivo = None
        if not cands:
            motivo = 'nenhuma chave no laco'
        elif len(cands) > MAX_CHAVES_LACO_TRAFO:
            motivo = '%d chaves no laco' % len(cands)
        elif compilacoes + len(cands) > MAX_COMPILACOES_BYPASS:
            sem_decisao += [{'fecha': x['fecha'], 'razao': x['razao'],
                             'motivo': 'limite de compilacoes'} for x in lista]
            break
        servem = []
        for c in ([] if motivo else cands):
            compilacoes += 1
            conv, viv = _compila(master, decididas + [c], controle)
            # ACHADO 70: so a que nao desenergiza no nenhum
            if conv and viv >= base:
                servem.append((dss.Circuit.Losses()[0] / 1000, c))
        if not motivo and not servem:
            motivo = 'nenhuma candidata mantem todos os nos'
        if motivo:
            sem_decisao.append({'fecha': lc['fecha'], 'razao': lc['razao'],
                                'motivo': motivo})
        else:
            servem.sort()
            perda, c = servem[0]
            eq = sum(1 for p, _ in servem if p - perda < PERDA_EQUIVALENTE_KW)
            decididas.append(c)
            abertas.append({'chave': 'Line.' + c.split('.', 1)[1],
                            'controle': controle.get(c),
                            'transformadores': [t.split('.', 1)[1] for t in
                                                lc['transformadores']],
                            'razao': lc['razao'], 'perda_kW': perda,
                            'equivalentes': eq})
        # a lista seguinte sai do circuito com as decididas abertas
        compilacoes += 1
        _compila(master, decididas, controle)
    return abertas, sem_decisao


def escolher_bypass(master, regs):
    """Quais elementos abrir para desfazer o laco do regulador:
    `(abertas, sem_decisao)`.

    ACHADO 69. So o criterio eletrico serve. Na 5001306, as duas chaves de
    cada laco ficam a trechos de distancia do regulador, e a regra
    topologica marcou as doze — abri-las derrubou 33 mil nos. Abrir uma de
    cada vez separa as duas limpo: a chave em SERIE, aberta, deixa o
    regulador pendurado com 0 kW; o BYPASS, aberto, deixa-o conduzindo, e
    nenhum no perde tensao. Validado com os seis: 77,2% -> 64,5% de perda,
    88.003 nos vivos antes e depois.

    AS QUATRO FORMAS, medidas nos 31 que a V37 deixou sem decisao:

    - chaves em PARALELO no mesmo par de barras (ETR, NEOENERGIA47): abrem
      juntas, como um candidato so — ver `lacos.candidatos_de_bypass`;
    - chaves em SERIE no mesmo caminho (5000858, EQUATORIAL6072): todas
      deixam o regulador com os mesmos 250 kW. Sao a mesma manobra; abre-se
      a que mais carga poe no regulador, e o arquivo diz quantas empatavam;
    - regulador SEM CARGA A JUSANTE (5000749 e 5000944): entrada e saida
      voltam ao mesmo no, 5 kA e 4,6 kA circulando, e nenhuma abertura faz o
      regulador conduzir — porque nao ha o que ele alimente. O laco nao
      pode operar fechado; abre-se o candidato de menor perda, dito;
    - laco SO DE TRECHOS (AGT, NEOENERGIA43): 28 MW circulando e nenhuma
      chave. Trecho entra como ultimo recurso, e o arquivo diz que nao e
      manobra de campo.

    Decide-se um banco de cada vez, com os ja decididos abertos, porque dois
    bypass no mesmo anel mudam a resposta um do outro. Chamada com o
    circuito compilado; deixa-o compilado de outro jeito.
    """
    nomes = {'transformer.' + r['transformador'].lower() for r in regs}
    candidatos = lacos.candidatos_de_bypass(
        dss, lacos.lacos(dss, lacos.abertas(os.path.dirname(master)),
                         reguladores=nomes))
    if not candidatos:
        return [], []
    controle = _controles_das_chaves()
    fases = {}
    for r in regs:
        t = r['transformador'].lower()
        fases.setdefault(lacos.banco(t), []).append(t)

    abertas, sem_decisao = [], []
    compilacoes = [0]

    def estado(elementos):
        compilacoes[0] += 1
        return _compila(master, elementos, controle)

    def perda():
        return dss.Circuit.Losses()[0] / 1000

    _, base = estado([])
    decididas = []

    def medir(bco, grupos, limite):
        """`None` se o laco nao cabe no teto ou no orcamento; senao as
        medidas `(grupo, kW no regulador, perda)` dos que nao apagam no."""
        if not grupos or len(grupos) > limite:
            return None
        if compilacoes[0] + len(grupos) + 1 > MAX_COMPILACOES_BYPASS:
            return None
        out = []
        for g in grupos:
            conv, viv = estado(decididas + list(g))
            # ACHADO 69: nenhum candidato pode desenergizar no
            if conv and viv >= base:
                out.append((g, _p_banco(fases.get(bco, [])), perda()))
        return out

    def conduzem(medidas):
        return [m for m in medidas or [] if m[1] > orientacao.FLUXO_MINIMO_KW]

    for bco, cand in candidatos.items():
        todos = [e for g in cand['chaves'] + cand['trechos'] for e in g]
        if not todos:
            sem_decisao.append({'regulador': bco, 'candidatas': [],
                                'motivo': 'nenhum elemento no laco'})
            continue
        # A ORDEM: chave que poe o regulador em servico; senao trecho que o
        # poe; so entao "sem carga a jusante". Com chaves que so tiram o
        # regulador de servico e o bypass num trecho, pular direto para "sem
        # carga" abriria a chave errada e desligaria o regulador.
        tipo, medidas = 'chave', medir(bco, cand['chaves'], MAX_CHAVES_NO_LACO)
        conduz = conduzem(medidas)
        if not conduz and cand['trechos']:
            m_t = medir(bco, cand['trechos'], MAX_TRECHOS_NO_LACO)
            if conduzem(m_t) or not medidas:
                tipo, medidas, conduz = 'trecho', m_t, conduzem(m_t)
        if medidas is None:
            sem_decisao.append({'regulador': bco, 'candidatas': todos,
                                'motivo': ('limite de compilacoes'
                                           if compilacoes[0] >= MAX_COMPILACOES_BYPASS
                                           else 'laco sem a forma de bypass')})
            continue
        sem_carga = False
        if conduz:
            # o regulador de volta em servico, com a maior carga possivel —
            # o criterio da validacao manual na 5001306
            g, kw, _p = max(conduz, key=lambda m: (m[1], -m[2]))
            eq = sum(1 for m in conduz if kw - m[1] < KW_EQUIVALENTE)
        elif medidas:
            estado(decididas)
            atual = perda()
            g, kw, p_ = min(medidas, key=lambda m: m[2])
            # so abre se desfizer circulacao de verdade; laco que nao circula
            # nada fica como a BDGD declara
            if atual - p_ < PERDA_EQUIVALENTE_KW:
                sem_decisao.append({'regulador': bco, 'candidatas': todos,
                                    'motivo': 'nenhuma candidata'})
                continue
            sem_carga = True
            eq = sum(1 for m in medidas if m[2] - p_ < PERDA_EQUIVALENTE_KW)
        else:
            sem_decisao.append({'regulador': bco, 'candidatas': todos,
                                'motivo': 'nenhuma candidata'})
            continue
        decididas += list(g)
        abertas.append({'chave': 'Line.' + g[0].split('.', 1)[1],
                        'chaves': ['Line.' + e.split('.', 1)[1] for e in g],
                        'controle': controle.get(g[0]),
                        'controles': [controle[e] for e in g if controle.get(e)],
                        'regulador': bco, 'kW': kw, 'tipo': tipo,
                        'equivalentes': eq, 'sem_carga': sem_carga})
    return abertas, sem_decisao


def uma(pasta, se):
    pausa.espera()
    d = os.path.join(pasta, se)
    master = os.path.join(d, f'MASTER-{se}.dss')
    if not os.path.exists(master):
        return None
    cwd = os.getcwd()
    os.chdir(d)
    try:
        # IDEMPOTENCIA, e aqui ela e mais delicada que no `ampacidade`: o
        # MASTER redireciona este arquivo, e medir com a correcao anterior
        # aplicada mediria o fluxo de um circuito JA corrigido. Zera-se antes.
        orientacao.escrever('_REGULADORES.dss', [], 0, ())
        # modelo anterior ao achado 70 nao redireciona o arquivo: escrever
        # nele nao mudaria nada, e a decisao sairia sem efeito
        with open(f'MASTER-{se}.dss', encoding='utf-8', errors='replace') as fh:
            tem_lacos = 'redirect _lacos.dss' in fh.read().lower()
        if tem_lacos:
            lacos.escrever('_LACOS.dss')
        master_abs = os.path.abspath(f'MASTER-{se}.dss')
        # NAO CONVERGIR NAO E MOTIVO PARA DESISTIR AQUI. Ate 21/09/2026 a
        # etapa voltava neste ponto, e o `Max Control Iterations Exceeded`
        # subia como erro: as sete subestacoes da EQUATORIAL6072 que nao
        # convergem nunca tiveram laco nem bypass tratados — e o laco e a
        # causa mais provavel de nao convergirem. Os dois criterios decidem
        # por candidata; so a orientacao, abaixo, precisa do fluxo resolvido.
        aviso = lacos.compilar(dss, master_abs)

        # O LACO ATRAVES DE TRANSFORMADOR VEM PRIMEIRO (achado 70): com ele
        # fechado a rede inteira esta em circulacao, e nem o bypass nem a
        # orientacao medem o que devem.
        l_abertos, l_sem = [], []
        if tem_lacos:
            l_abertos, l_sem = escolher_lacos_de_transformador(master_abs)
            if l_abertos or l_sem:
                lacos.escrever('_LACOS.dss', l_abertos, l_sem)
                aviso = lacos.compilar(dss, master_abs)

        # O BYPASS VEM PRIMEIRO (achado 69): com ele fechado, o fluxo medido
        # no regulador e corrente de laco, e a orientacao sairia dela.
        bypass, sem_decisao = escolher_bypass(master_abs, quais())
        if bypass or sem_decisao:
            # a escolha deixou o circuito com a ultima candidata aberta
            orientacao.escrever('_REGULADORES.dss', [], 0, (),
                                bypass=bypass, sem_decisao=sem_decisao)
            aviso = lacos.compilar(dss, master_abs)

        decididos = {'lacos_abertos': [x['chave'] for x in l_abertos],
                     'lacos_sem_decisao': l_sem,
                     'bypass_abertos': [c for x in bypass for c in x.get('chaves', [x['chave']])],
                     'bypass_sem_decisao': sem_decisao}
        if aviso or not dss.Solution.Converged():
            # sem fluxo resolvido nao ha direcao a medir: a orientacao fica
            # de fora, e o que foi decidido acima continua valendo
            return {'se': se, 'erro': 'nao convergiu' + (f' ({aviso})' if aviso else ''),
                    **decididos}

        # O TAPE VOLTA AO NEUTRO ANTES DE MEDIR. O `Solve` embutido no MASTER
        # ja correu o tape ao limite, e o tape mexe na tensao dos dois lados —
        # medir sobre ele foi o primeiro erro desta investigacao. A DIRECAO do
        # fluxo nao muda com o tape, mas zerar torna a medida legivel e
        # protege contra o caso em que o tape saturado inverte o sinal.
        regs = quais()
        for r in regs:
            dss.Text.Command('Transformer.%s.wdg=2' % r['transformador'])
            dss.Text.Command('Transformer.%s.tap=1.0' % r['transformador'])
            dss.Text.Command('RegControl.%s.enabled=no' % r['nome'])
        if regs:
            lacos.resolver(dss)
            fluxos(regs)

        corr, sem = orientacao.corrigir(regs)
        orientacao.escrever('_REGULADORES.dss', corr, len(regs), sem,
                            bypass=bypass, sem_decisao=sem_decisao)

        # CONFERE NO PROPRIO MOTOR: o arquivo vale o que ele faz. Recompila do
        # zero, porque acima os controles ficaram desabilitados.
        aviso = lacos.compilar(dss, master_abs)
        v = sorted(x for x in dss.Circuit.AllBusMagPu() if x > 1e-6)
        sat = 0
        i = dss.RegControls.First()
        while i:
            dss.Transformers.Name(dss.RegControls.Transformer())
            if dss.Transformers.Tap() >= dss.Transformers.MaxTap() - 1e-6:
                sat += 1
            i = dss.RegControls.Next()
        return {'se': se, 'reguladores': len(regs), 'corrigidos': len(corr),
                'sem_fluxo': len(sem), 'saturados_depois': sat,
                **decididos,
                'V_mediana_depois': round(v[len(v) // 2], 4) if v else None,
                'convergiu': bool(dss.Solution.Converged()) and not aviso}
    except Exception as e:
        # UMA SUBESTACAO NAO PODE DERRUBAR A ETAPA — a licao da 1726671.
        return {'se': se, 'erro': f'{type(e).__name__}: {str(e)[:200]}'}
    finally:
        os.chdir(cwd)


def _painel():
    """Sem argumento, pergunta na janela — o `Validator.py` conta com isso."""
    if not plataforma.tem_janela():
        return False
    from bdgd2dss import interativo
    v = interativo.pedir('Orientacao dos reguladores', [
        {'chave': 'pasta', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': ''},
        {'chave': 'jobs', 'tipo': 'inteiro',
         'rotulo': 'Subestacoes em paralelo', 'padrao': 8}])
    if not v:
        return False
    sys.argv += [v['pasta'], '--jobs', str(v['jobs'])]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('pasta', help='pasta do modelo (MODELOS_*)')
    ap.add_argument('--jobs', type=int, default=8,
                    help='subestacoes em paralelo (padrao 8)')
    ap.add_argument('--se', nargs='+', help='apenas estas subestacoes')
    a = ap.parse_args()

    # O CAMINHO RELATIVO E CONTRA A RAIZ DO PROJETO, e nao contra `etapas/` —
    # a licao da mudanca de 02/09/2026, que quebrou duas etapas assim.
    raiz = (a.pasta if os.path.isabs(a.pasta)
            else os.path.join(os.path.dirname(AQUI), a.pasta))
    if not os.path.isdir(raiz):
        raise SystemExit(f'pasta nao encontrada: {raiz}')
    ses = a.se or sorted(x for x in os.listdir(raiz)
                         if os.path.isdir(os.path.join(raiz, x))
                         and not x.startswith('_'))

    print('ORIENTACAO DOS REGULADORES — achado 59')
    print(f'{len(ses)} subestacoes | o criterio e a direcao do fluxo\n',
          flush=True)
    print(f'{"SE":14s} {"regs":>6s} {"corrig":>7s} {"sem flx":>8s} '
          f'{"satur":>6s} {"V med":>8s} {"bypass":>7s} {"lacos":>6s}',
          flush=True)
    t0 = time.time()
    por_se = {}

    def _linha(r):
        if r.get('erro'):
            print(f'{r["se"]:14s} {r["erro"]}', flush=True)
            return
        print(f'{r["se"]:14s} {r.get("reguladores",0):6d} '
              f'{r.get("corrigidos",0):7d} {r.get("sem_fluxo",0):8d} '
              f'{r.get("saturados_depois",0):6d} '
              f'{(r.get("V_mediana_depois") or 0):8.4f} '
              f'{len(r.get("bypass_abertos") or ()):7d} '
              f'{len(r.get("lacos_abertos") or ()):6d}', flush=True)

    def grava():
        """No disco o que ja terminou, na ordem de `ses`.

        DENTRO do `with` do pool: sair dele e `shutdown(wait=True)`, e essa
        espera nao tem prazo — ver `test_grava_antes_de_esperar.py`.
        """
        s_ = [por_se[k] for k in ses if k in por_se]
        n = sum(x.get('corrigidos') or 0 for x in s_)
        tot = sum(x.get('reguladores') or 0 for x in s_)
        sem = sum(x.get('sem_fluxo') or 0 for x in s_)
        with open(os.path.join(raiz, 'reguladores.json'), 'w',
                  encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
            json.dump({'corrigidos': n, 'reguladores': tot,
                       'sem_fluxo': sem,
                       'bypass_abertos': sum(len(x.get('bypass_abertos') or ())
                                             for x in s_),
                       'lacos_abertos': sum(len(x.get('lacos_abertos') or ())
                                            for x in s_),
                       'subestacoes': s_}, fh,
                      indent=1, ensure_ascii=False)
        return s_

    if a.jobs > 1 and len(ses) > 1:
        import concurrent.futures as cf
        import multiprocessing as mp
        ctx = mp.get_context('spawn')
        with cf.ProcessPoolExecutor(max_workers=a.jobs,
                                    mp_context=ctx) as ex:
            fut = {ex.submit(uma, raiz, s_): s_ for s_ in ses}
            for f in cf.as_completed(fut):
                r = f.result()
                if r:
                    por_se[r['se']] = r
                    _linha(r)
            saida = grava()
    else:
        for s_ in ses:
            r = uma(raiz, s_)
            if r:
                por_se[r['se']] = r
                _linha(r)
        saida = grava()

    n = sum(r.get('corrigidos') or 0 for r in saida)
    tot = sum(r.get('reguladores') or 0 for r in saida)
    sem = sum(r.get('sem_fluxo') or 0 for r in saida)
    afetadas = sum(1 for r in saida if (r.get('corrigidos') or 0))
    byp = sum(len(r.get('bypass_abertos') or ()) for r in saida)
    amb = sum(len(r.get('bypass_sem_decisao') or ()) for r in saida)
    lac = sum(len(r.get('lacos_abertos') or ()) for r in saida)
    lsd = sum(len(r.get('lacos_sem_decisao') or ()) for r in saida)
    if lac or lsd:
        print(f'ACHADO 70: {lac} laco(s) atraves de transformador aberto(s), '
              f'{lsd} sem decisao')
    if byp or amb:
        print(f'ACHADO 69: {byp} bypass de regulador aberto(s), '
              f'{amb} laco(s) com regulador sem decisao')
    print(f'\n{n:,} de {tot:,} reguladores corrigidos em {afetadas} '
          f'subestacoes ({sem:,} sem fluxo, {time.time()-t0:.0f} s)')
    print('detalhe em %s' % os.path.join(raiz, 'reguladores.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
