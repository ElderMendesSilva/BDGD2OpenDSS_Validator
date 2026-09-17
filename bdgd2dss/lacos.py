# -*- coding: utf-8 -*-
"""Lacos fechados da media tensao, por fase — achado 69.

Na EQUATORIAL6072 as duas piores subestacoes colapsavam por lacos que a
propria BDGD declara fechados (`SSDMT` e `UNSEMT`): abrir os 38 lacos da
5001306 levou a perda de 77,2% para 11,5%. Seis deles tem um regulador dentro,
no arranjo de campo de chave de entrada, regulador, chave de saida e CHAVE DE
BYPASS, esta fechada. A trava do achado 48 (`chaves.bypass_de_regulador`) so
reconhece o bypass que liga exatamente os dois PACs do regulador; este liga os
das chaves vizinhas.

Este modulo so le a topologia do circuito ja compilado, sem resolver. Quem
decide qual chave abrir e o `etapas/reguladores.py`, pelo criterio eletrico.

A MEDIDA ERROU DUAS VEZES ANTES DE ACERTAR, e as duas licoes moram aqui:

- o grafo e por FASE (`barra.no`): um trecho na fase A e outro na B entre as
  mesmas barras nao sao laco. O primeiro grafo, por barra, os contava;
- chave normalmente aberta fica FORA do grafo (`SwtControl State=Open` e
  `_CHAVES_ABERTAS.dss`), e elemento desabilitado tambem.

Transformadores entram primeiro na arvore, entao o regulador nunca e escolhido
como o elemento que fecha o laco.
"""
import collections
import os
import re

CICLO_CURTO = 12          # o bypass medido fecha em 8; folga para variacoes
LIMIAR_REGULADOR = 'transformer.reg_'


def _nos(bus, n):
    p = bus.split('.')
    b = p[0].lower()
    ns = [x for x in p[1:] if x != '0'] or [str(k) for k in range(1, n + 1)]
    return [f'{b}.{x}' for x in ns[:n]]


def abertas(pasta_se):
    """As chaves que o modelo declara abertas, como `line.<nome>`."""
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


def e_regulador(el, reguladores=None):
    el = el.lower()
    if reguladores is not None:
        return el in reguladores
    return el.startswith(LIMIAR_REGULADOR)


def lacos(dss, fora=(), reguladores=None):
    """Os lacos do circuito compilado no `dss`.

    Devolve uma lista de `{'fecha', 'ciclo', 'regulador'}`: o elemento que
    fecha o laco, os elementos do ciclo CURTO que ele fecha (vazio quando o
    ciclo passa de `CICLO_CURTO`) e o primeiro regulador desse ciclo, ou
    `None`. `reguladores`, quando dado, e o conjunto de `transformer.<nome>`
    em minusculas; sem ele vale o prefixo `REG_` do `complementos`.
    """
    fora = {x.lower() for x in fora}
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

    def ciclo(o, d):
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
            return []
        caminho, x = [], d
        while ant[x]:
            a, e = ant[x]
            caminho.append(e)
            x = a
        return caminho

    saida = []
    for el, pares in fecham:
        c = [el] + ciclo(*pares[0])
        reg = next((e for e in c if e_regulador(e, reguladores)), None)
        saida.append({'fecha': el, 'ciclo': c if len(c) > 1 else [],
                      'regulador': reg})
    return saida


def banco(transformador):
    """`transformer.reg_5896508_1` -> `reg_5896508`: as fases de um regulador
    sao transformadores monofasicos com o mesmo codigo."""
    nome = transformador.split('.', 1)[-1].lower()
    return nome.rsplit('_', 1)[0] if re.search(r'_\d+$', nome) else nome


def candidatos_de_bypass(dss, lista):
    """Por banco de regulador, as CHAVES dos ciclos curtos que o contem.

    So chave: abrir trecho de condutor nao e manobra de campo. A decisao de
    qual delas e o bypass e eletrica e fica com quem chama.
    """
    chaves = {}
    por_banco = collections.OrderedDict()
    for lc in lista:
        if not lc['regulador']:
            continue
        cs = por_banco.setdefault(banco(lc['regulador']), [])
        for e in lc['ciclo']:
            e = e.lower()
            if not e.startswith('line.') or e in cs:
                continue
            if e not in chaves:
                dss.Lines.Name(e.split('.', 1)[1])
                chaves[e] = bool(dss.Lines.IsSwitch())
            if chaves[e]:
                cs.append(e)
    return por_banco


def lacos_da_se(master):
    """O censo de uma subestacao: quantos lacos, quantos com regulador e
    quantos fechados por elo nosso (`VAO_EXTRA_*`, achado 33)."""
    import opendssdirect as dss
    fora = abertas(os.path.dirname(master))
    dss.Text.Command('Clear')
    dss.Text.Command(f'Redirect "{os.path.abspath(master)}"')
    lista = lacos(dss, fora)
    com_reg = [x['fecha'] for x in lista if x['regulador']]
    nossos = [x['fecha'] for x in lista
              if x['fecha'].lower().startswith('line.vao_extra')]
    return {'lacos': len(lista), 'com_regulador': len(com_reg),
            'por_elo_nosso': len(nossos),
            'exemplos_com_regulador': com_reg[:5]}
