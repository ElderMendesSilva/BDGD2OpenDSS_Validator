# -*- coding: utf-8 -*-
"""Quantos lacos fechados a media tensao tem, e quantos passam por regulador.

    python diagnosticos/lacos.py --raiz . --sufixo V36 --jobs 16 \\
        --saida-json medicoes/lacos_v36.json

POR QUE A PERGUNTA. Na EQUATORIAL6072 (V34), 42% da energia estava em
subestacoes que colapsavam — 77% de perda, tensao mediana de 0,38 pu, 36
reguladores saturados. Quatro hipoteses cairam (PT de regulador, raiz de 3 nos
monofasicos, transformador depois de abaixador, achado 49). O que ficou de pe,
medido em 17/09/2026 nas duas piores:

    SE        lacos   perda como esta   perda com os lacos abertos
    5001306      38         77,2%                  11,5%
    5001242      55         66,8%                  14,6%

Os lacos vem da propria BDGD (`SSDMT` e `UNSEMT` fechadas), e nenhum no
perde tensao quando eles sao abertos — sao lacos de verdade. Na 5001306, 6
deles tem um regulador dentro, todos com 8 elementos e com os maiores fluxos
(394 a 2.027 A): o arranjo de campo de chave de entrada, regulador, chave de
saida e CHAVE DE BYPASS. A trava do achado 48 so reconhece o bypass que liga
exatamente os dois PACs do regulador, e este liga os das chaves vizinhas.

Duas SEs de uma base nao fazem lei. Este censo conta, em cada subestacao de
uma rodada:

- os lacos fechados por FASE (um trecho na fase A e outro na B entre as
  mesmas barras nao sao laco);
- quantos tem um regulador num ciclo curto — a forma do bypass;
- quantos sao fechados por elo que NOS criamos (`VAO_EXTRA_*`, achado 33) e
  nao pela BDGD.

COMO. Compila cada subestacao e le a topologia do OpenDSS, sem resolver. As
chaves abertas (`_CHAVES_ABERTAS.dss` e `SwtControl State=Open`) ficam fora do
grafo — sem isso, uma chave normalmente aberta fecha um "laco" que nao
conduz, que foi o erro da primeira medida. Transformadores entram primeiro na
arvore, entao o regulador nunca e escolhido como o elemento que fecha.

Roda sobre modelos ja gerados; e calculo, entao e job.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

CICLO_CURTO = 12          # o bypass medido fecha em 8; folga para variacoes


def _nos(bus, n):
    p = bus.split('.')
    b = p[0].lower()
    ns = [x for x in p[1:] if x != '0'] or [str(k) for k in range(1, n + 1)]
    return [f'{b}.{x}' for x in ns[:n]]


def _abertas(pasta_se):
    fora = set()
    # `^\s*New` e `^\s*Open`: linha comentada nao abre chave nenhuma
    for nome, padrao in (('Controles.dss',
                          r'^\s*New\s+SwtControl\..*SwitchedObj=Line\.(\S+) .*State=Open'),
                         ('_CHAVES_ABERTAS.dss', r'^\s*Open\s+Line\.(\S+)')):
        p = os.path.join(pasta_se, nome)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8', errors='replace') as fh:
            for linha in fh:
                m = re.search(padrao, linha, re.I)
                if m:
                    fora.add('line.' + m.group(1).lower())
    return fora


def lacos_da_se(master):
    """Os lacos de uma subestacao, sem resolver o circuito."""
    import opendssdirect as dss
    pasta = os.path.dirname(master)
    fora = _abertas(pasta)
    dss.Text.Command('Clear')
    dss.Text.Command(f'Redirect "{os.path.abspath(master)}"')

    pai = {}

    def acha(x):
        r = x
        while pai.get(r, r) != r:
            r = pai[r]
        while pai.get(x, x) != r:
            pai[x], x = r, pai.get(x, x)
        return r

    fontes = []
    i = dss.Vsources.First()
    while i:
        dss.Circuit.SetActiveElement('Vsource.' + dss.Vsources.Name())
        fontes += _nos(dss.CktElement.BusNames()[0], 3)
        i = dss.Vsources.Next()
    for n in fontes:
        pai[acha(n)] = acha(fontes[0])

    arestas = []
    for el in dss.Circuit.AllElementNames():
        cls = el.split('.')[0].lower()
        if cls not in ('line', 'transformer') or el.lower() in fora:
            continue
        dss.Circuit.SetActiveElement(el)
        if not dss.CktElement.Enabled():
            continue
        bs = dss.CktElement.BusNames()
        if len(bs) < 2:
            continue
        nf = dss.CktElement.NumPhases()
        arestas.append((0 if cls == 'transformer' else 1, el,
                        list(zip(_nos(bs[0], nf), _nos(bs[1], nf)))))

    arvore = collections.defaultdict(list)
    fecham = []
    for prio, el, pares in sorted(arestas, key=lambda a: a[0]):
        if prio == 1 and all(acha(a) == acha(b) for a, b in pares):
            fecham.append((el, pares))
            continue
        for a, b in pares:
            if acha(a) != acha(b):
                pai[acha(a)] = acha(b)
                arvore[a].append((b, el))
                arvore[b].append((a, el))

    def ciclo_tem_regulador(o, d):
        """BFS limitado: o regulador so conta num ciclo CURTO, que e a forma
        do bypass. Num ciclo longo ele pode ser so vizinho do anel."""
        ant = {o: None}
        fila = collections.deque([(o, 0)])
        while fila:
            x, k = fila.popleft()
            if x == d:
                break
            if k >= CICLO_CURTO:
                continue
            for y, e in arvore[x]:
                if y not in ant:
                    ant[y] = (x, e)
                    fila.append((y, k + 1))
        if d not in ant:
            return False
        x = d
        while ant[x]:
            a, e = ant[x]
            if e.lower().startswith('transformer.reg'):
                return True
            x = a
        return False

    com_reg = [el for el, pares in fecham if ciclo_tem_regulador(*pares[0])]
    nossos = [el for el, _ in fecham if el.lower().startswith('line.vao_extra')]
    return {'lacos': len(fecham), 'com_regulador': len(com_reg),
            'por_elo_nosso': len(nossos),
            'exemplos_com_regulador': com_reg[:5]}


def _uma(master):
    try:
        return master, lacos_da_se(master), None
    except Exception as e:                               # noqa: BLE001
        return master, None, f'{type(e).__name__}: {str(e)[:120]}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--raiz', default='.')
    ap.add_argument('--sufixo', required=True)
    ap.add_argument('--so', default='', help='tags separadas por espaco')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--saida-json', default=None)
    a = ap.parse_args(argv)

    so = {x for x in a.so.split() if x}
    masters = []
    for pasta in sorted(glob.glob(os.path.join(a.raiz, f'MODELOS_*_{a.sufixo}'))):
        tag = os.path.basename(pasta)[len('MODELOS_'):-len(a.sufixo) - 1]
        if so and tag not in so:
            continue
        for m in sorted(glob.glob(os.path.join(pasta, '*', 'MASTER-*.dss'))):
            if os.path.basename(os.path.dirname(m)).startswith('_'):
                continue
            masters.append((tag, m))
    if not masters:
        print('nenhuma subestacao encontrada', file=sys.stderr)
        return 1
    print(f'{len(masters)} subestacoes', flush=True)

    por_base = collections.defaultdict(dict)
    erros = 0
    if a.jobs > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = ex.map(_uma, [m for _, m in masters], chunksize=4)
            itens = list(zip([t for t, _ in masters], res))
    else:
        itens = [(t, _uma(m)) for t, m in masters]
    for tag, (m, r, err) in itens:
        se = os.path.basename(os.path.dirname(m))
        if err:
            erros += 1
            print(f'  ERRO {tag}/{se}: {err}', flush=True)
            continue
        por_base[tag][se] = r

    print(f'\n{"base":20s} {"SEs":>5s} {"com laco":>9s} {"lacos":>7s} {"c/ reg":>7s} {"nossos":>7s}')
    tot = collections.Counter()
    for tag in sorted(por_base):
        ses = por_base[tag]
        n_l = sum(1 for r in ses.values() if r['lacos'])
        c = collections.Counter()
        for r in ses.values():
            c['lacos'] += r['lacos']
            c['reg'] += r['com_regulador']
            c['nossos'] += r['por_elo_nosso']
        tot['ses'] += len(ses)
        tot['com_laco'] += n_l
        tot['com_reg'] += sum(1 for r in ses.values() if r['com_regulador'])
        tot.update(c)
        print(f'{tag[:20]:20s} {len(ses):5d} {n_l:9d} {c["lacos"]:7d} {c["reg"]:7d} {c["nossos"]:7d}')
    print(f'\nPAIS: {tot["ses"]} SEs | {tot["com_laco"]} com laco | '
          f'{tot["com_reg"]} com laco passando por regulador | '
          f'{tot["lacos"]} lacos, {tot["reg"]} com regulador, '
          f'{tot["nossos"]} fechados por elo nosso | {erros} erros')
    if a.saida_json:
        os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
        with open(a.saida_json, 'w', encoding='utf-8') as fh:
            json.dump({'sufixo': a.sufixo, 'bases': por_base,
                       'total': dict(tot), 'erros': erros}, fh,
                      ensure_ascii=False, indent=1)
        print(f'-> {a.saida_json}')
    return 0 if por_base else 1


if __name__ == '__main__':
    sys.exit(main())
