# -*- coding: utf-8 -*-
"""
LIGACAO A COMPONENTE DESENERGIZADA — achado 33, forma B
=======================================================

    python ligacao.py MODELOS_CMIG_V13
    python ligacao.py MODELOS_CMIG_V13 --min-cargas 50 --se 1645246100

Roda DEPOIS do `converter.py`, porque o criterio e eletrico: liga-se o que
ficou SEM TENSAO depois de resolver, e nao o que a topologia sugere.

ISTO E MODELAGEM, NAO CONVERSAO, E INVENTA UM ELO QUE A BDGD NAO DECLARA.
Sem rodar este script o modelo reproduz a BDGD como ela e — que continua
sendo o padrao.

Por que existe: fechado o achado 32, sobra na Cemig-D um residuo de 3,9%, e
61,9% dele esta em 29 alimentadores cuja rede esta inteira numa componente
conexa grande enquanto a cabeceira declarada esta numa ilha ao lado. A UHST04
tem 14.749 barras numa componente e a cabeceira na de 129. A BDGD nao diz
qual e o elo entre as duas.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from bdgd2dss import ligacao                          # noqa: E402

try:
    import opendssdirect as dss
except Exception as e:                                 # pragma: no cover
    raise SystemExit(f'opendssdirect indisponivel: {e}')

MORTA_V = 1.0            # volts: abaixo disso a barra nao esta energizada


def _bus(x):
    return x.split('.')[0].lower()


def radiografia():
    """Adjacencia, barras mortas, cargas por barra, kV por barra, vaos.

    Sao DOIS grafos. `adj` inclui os transformadores e serve para agrupar a
    rede desenergizada e contar a carga que ela carrega. `adj_mt` e so de
    linhas, e e a camada de media: e nela que a tensao declarada no primario
    do trafo se propaga, e e dela que sai a ancora.
    """
    adj, adj_mt = {}, {}

    def liga(a, b, onde=None):
        for g in ((adj,) if onde is None else (adj, onde)):
            g.setdefault(a, set()).add(b)
            g.setdefault(b, set()).add(a)

    kvs_vao, barra_de_vao = set(), {}
    for nome in dss.Lines.AllNames():
        dss.Lines.Name(nome)
        dss.Circuit.SetActiveElement('Line.' + nome)
        b = [_bus(x) for x in dss.CktElement.BusNames()]
        if len(b) >= 2:
            liga(b[0], b[1], adj_mt)
        if nome.lower().startswith('vao_'):
            dss.Circuit.SetActiveBus(b[0])
            kv = dss.Bus.kVBase()
            kvs_vao.add(round(kv, 4))
            barra_de_vao.setdefault(round(kv, 4), b[0])
    i = dss.Transformers.First()
    while i:
        dss.Circuit.SetActiveElement('Transformer.' + dss.Transformers.Name())
        b = [_bus(x) for x in dss.CktElement.BusNames()]
        for j in range(len(b) - 1):
            liga(b[0], b[j + 1])          # so no grafo completo
        i = dss.Transformers.Next()

    mortas = set()
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        v = dss.Bus.VMagAngle()[0::2]
        if not v or max(v) < MORTA_V:
            mortas.add(b.lower())

    # A TENSAO DE BARRA MORTA NAO SERVE. `kVBase` sai do `CalcVoltagebases`,
    # que le a tensao RESOLVIDA: barra sem tensao recebe a base que sobrar —
    # nesta subestacao, todas as 36.698 barras mortas vieram com 50,8068 kV,
    # que e a base de AT. Filtrar por ela descartava a rede inteira.
    #
    # A tensao que vale e a DECLARADA no primario do transformador, e ela se
    # propaga pela camada de MT, que aqui e o grafo so-de-linhas: no modo
    # agregado toda Line e de media e a carga mora atras do trafo.
    kv_prim, secundarias = {}, set()
    i = dss.Transformers.First()
    while i:
        nome = dss.Transformers.Name()
        dss.Circuit.SetActiveElement('Transformer.' + nome)
        bs = [_bus(x) for x in dss.CktElement.BusNames()]
        secundarias.update(bs[1:])
        try:
            dss.Transformers.Wdg(1)
            kv_prim[bs[0]] = dss.Transformers.kV()
        except Exception:
            pass
        i = dss.Transformers.Next()
    com_carga = set()
    kv_por_barra = {}

    cargas = {}
    i = dss.Loads.First()
    while i:
        dss.Circuit.SetActiveElement('Load.' + dss.Loads.Name())
        b = _bus(dss.CktElement.BusNames()[0])
        cargas[b] = cargas.get(b, 0) + 1
        com_carga.add(b)
        i = dss.Loads.Next()

    # a tensao declarada, propagada por cada componente da camada de MT
    for comp in ligacao.componentes(adj_mt, set(adj_mt)):
        kvs = [kv_prim[b] for b in comp if b in kv_prim]
        if not kvs:
            continue
        kv = max(set(kvs), key=kvs.count)
        for b in comp:
            # so barra de MEDIA entra: secundario de trafo e barra com carga
            # sao de baixa, e pendura-las na barra da SE seria pior que
            # deixa-las desligadas
            if b not in secundarias and b not in com_carga:
                kv_por_barra[b] = kv
    return adj, mortas, cargas, kv_por_barra, sorted(kvs_vao), barra_de_vao


def uma(pasta, se, min_cargas):
    d = os.path.join(pasta, se)
    if not os.path.exists(os.path.join(d, f'MASTER-{se}.dss')):
        return None
    cwd = os.getcwd()
    os.chdir(d)
    try:
        # idempotencia: o MASTER carrega o `_LIGACAO.dss` da rodada anterior,
        # e medir a linha de base sobre ele daria a rede ja ligada
        ligacao.escrever('_LIGACAO.dss', [], lambda kv: None)
        dss.Text.Command('Clear')
        dss.Text.Command(f'Redirect MASTER-{se}.dss')
        if not dss.Solution.Converged():
            return {'se': se, 'erro': 'nao convergiu'}
        adj, mortas, cargas, kvb, kvs, barra = radiografia()
        n_cargas = dss.Loads.Count()
        mortas_antes = sum(v for b, v in cargas.items() if b in mortas)
        comps = ligacao.componentes(adj, mortas)
        cand, fora = ligacao.decidir(comps, adj, cargas, kvb, kvs, min_cargas)

        def de_para(kv):
            return (barra.get(round(kv, 4))
                    or (barra.get(min(barra, key=lambda k: abs(k - kv)))
                        if barra else None))

        # CADA ELO E TESTADO NO PROPRIO MOTOR ANTES DE ENTRAR. Cria-se a Line
        # em memoria, resolve, e se a solucao divergir o elo e desabilitado e
        # recusado. Sai muito mais barato que reconstruir o circuito a cada
        # tentativa: o `Redirect` do MASTER custa segundos, o `New Line` custa
        # nada, e o que muda entre uma tentativa e outra e so um ramo.
        ordem = [0]

        def tenta(l):
            de = de_para(l['kv'])
            if not de:
                return False
            ordem[0] += 1
            nome = f"VAO_EXTRA_{ordem[0]}"
            dss.Text.Command(
                f"New Line.{nome} phases=3 Bus1={de}.1.2.3 "
                f"Bus2={l['barra']}.1.2.3 Switch=y r1=0.0001 r0=0.0001 "
                f"x1=0 x0=0 c1=0 c0=0")
            dss.Text.Command('Solve')
            if dss.Solution.Converged():
                return True
            dss.Text.Command(f'Edit Line.{nome} enabled=no')
            dss.Text.Command('Solve')
            return False

        lig, recusados = ligacao.aceitar(cand, tenta)
        fora = list(fora) + [dict(r, motivo='quebrou a convergencia')
                             for r in recusados]
        ligacao.escrever('_LIGACAO.dss', lig, de_para, fora)

        # o estado em memoria tem elos desabilitados no meio; recompila do
        # arquivo para medir exatamente o que o usuario vai receber
        dss.Text.Command('Clear')
        dss.Text.Command(f'Redirect MASTER-{se}.dss')
        dss.Text.Command('Solve')
        m2 = 0
        i = dss.Loads.First()
        while i:
            dss.Circuit.SetActiveElement('Load.' + dss.Loads.Name())
            v = dss.CktElement.VoltagesMagAng()[0::2]
            if v and max(v) < MORTA_V:
                m2 += 1
            i = dss.Loads.Next()
        p = dss.Circuit.TotalPower()
        return {'se': se, 'elos': len(lig), 'cargas': n_cargas,
                'recusados': len(recusados),
                'mortas_antes': mortas_antes, 'mortas_depois': m2,
                'componentes': len(comps), 'descartadas': len(fora),
                'carga_kW': round(-p[0], 1),
                'convergiu': bool(dss.Solution.Converged()),
                'ligacoes': lig}
    finally:
        os.chdir(cwd)


def _painel():
    """Sem argumento, pergunta na janela — o `menu.py` conta com isso."""
    import interativo
    v = interativo.formulario('ligacao', 'Ligação à componente desenergizada', [
        {'chave': 'pasta', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'a pasta que contém uma subpasta por subestação'},
        {'chave': 'min_cargas', 'tipo': 'inteiro',
         'rotulo': 'Cargas mínimas para ligar', 'padrao': 20,
         'dica': 'componente com menos cargas que isto é ruído, e ligá-la '
                 'não muda resultado nenhum'},
        {'chave': 'jobs', 'tipo': 'inteiro', 'rotulo': 'Subestações em paralelo',
         'padrao': 8,
         'dica': 'medido: o ganho satura perto de 8. Use 1 se for usar o '
                 'computador junto'},
        {'chave': 'se', 'tipo': 'texto', 'rotulo': 'Subestações', 'padrao': '',
         'dica': 'vazio = todas'},
    ], ajuda='PREMISSA DE MODELAGEM: liga a barra de MT da subestação à rede '
             'que ficou sem tensão. INVENTA um elo que a BDGD não declara, e '
             'por isso escreve tudo em _LIGACAO.dss, que dá para apagar. '
             'Elo que faz o modelo divergir é recusado.')
    if not v:
        return False
    sys.argv += [v['pasta'], '--min-cargas', str(v['min_cargas']),
                 '--jobs', str(v['jobs'])]
    if v['se'].strip():
        sys.argv += ['--se'] + v['se'].split()
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('pasta')
    ap.add_argument('--min-cargas', type=int, default=ligacao.MIN_CARGAS,
                    help='componente com menos cargas que isto e ruido '
                         f'(padrao {ligacao.MIN_CARGAS})')
    ap.add_argument('--jobs', type=int, default=8,
                    help='subestacoes em paralelo (padrao 8); cada uma custa '
                         'um processo com a sua instancia do OpenDSS')
    ap.add_argument('--se', nargs='+')
    a = ap.parse_args()

    raiz = a.pasta if os.path.isabs(a.pasta) else os.path.join(AQUI, a.pasta)
    if not os.path.isdir(raiz):
        raise SystemExit(f'pasta nao encontrada: {raiz}')
    ses = a.se or sorted(x for x in os.listdir(raiz)
                         if os.path.isdir(os.path.join(raiz, x))
                         and not x.startswith('_'))

    print(f'{len(ses)} subestacoes | componente com menos de '
          f'{a.min_cargas} cargas e ruido\n', flush=True)
    print(f'{"SE":14s} {"elos":>5s} {"comps":>6s} {"mortas antes":>13s} '
          f'{"depois":>9s} {"recuperadas":>12s}', flush=True)
    t0 = time.time()

    def _linha(r):
        if r.get('erro'):
            print(f'{r["se"]:14s} {r["erro"]}', flush=True)
            return
        print(f'{r["se"]:14s} {r["elos"]:5d} {r["componentes"]:6d} '
              f'{r["mortas_antes"]:13,d} {r["mortas_depois"]:9,d} '
              f'{r["mortas_antes"]-r["mortas_depois"]:12,d}', flush=True)

    # EM PARALELO, mesmo padrao do `energia.py`. Cada subestacao tem modelo
    # proprio e nenhum estado compartilhado; o que impedia rodar junto era o
    # `opendssdirect` guardar circuito e solucao em variaveis globais, e em
    # PROCESSOS separados isso deixa de existir.
    #
    # Aqui importa mais que nos outros: a aceitacao dos elos e feita UM A UM,
    # com um `Solve` por tentativa. E trabalho de motor, exatamente o que
    # ganha com processo proprio.
    #
    # A ORDEM DO JSON NAO PODE DEPENDER DE QUEM TERMINOU PRIMEIRO: ele sai na
    # ordem de `ses`, que e a da execucao serial.
    por_se = {}
    if a.jobs > 1 and len(ses) > 1:
        import concurrent.futures as cf
        print(f'{a.jobs} subestacoes em paralelo', flush=True)
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            fut = {ex.submit(uma, raiz, s_, a.min_cargas): s_ for s_ in ses}
            for f_ in cf.as_completed(fut):
                r = f_.result()
                if r is not None:
                    por_se[fut[f_]] = r
                    _linha(r)
    else:
        for se in ses:
            r = uma(raiz, se, a.min_cargas)
            if r is not None:
                por_se[se] = r
                _linha(r)
    saida = [por_se[s_] for s_ in ses if s_ in por_se]

    ok = [r for r in saida if not r.get('erro')]
    rec = sum(r['mortas_antes'] - r['mortas_depois'] for r in ok)
    print(f'\n{"="*70}')
    print(f'{sum(r["elos"] for r in ok):,} elos em {len(ok)} subestacoes, '
          f'{rec:,} cargas recuperadas ({time.time()-t0:.0f} s)')
    rec = sum(r.get('recusados', 0) for r in ok)
    if rec:
        print(f'{rec:,} elos RECUSADOS por quebrarem a convergencia — a rede '
              f'existe, mas premissa que piora o modelo nao entra')
    nc = [r['se'] for r in ok if not r['convergiu']]
    if nc:
        print(f'ATENCAO: {len(nc)} nao convergem NEM SEM elo — defeito '
              f'anterior a esta premissa: {", ".join(nc[:5])}')
    with open(os.path.join(raiz, 'ligacao.json'), 'w', encoding='utf-8') as fh:
        json.dump({'min_cargas': a.min_cargas, 'subestacoes': saida}, fh,
                  indent=1, ensure_ascii=False)
    print(f'\ndetalhe em {os.path.join(raiz, "ligacao.json")}')


if __name__ == '__main__':
    main()
