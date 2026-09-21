# -*- coding: utf-8 -*-
"""Lacos fechados da media tensao, por fase — achados 69 e 70.

Na EQUATORIAL6072 as duas piores subestacoes colapsavam por lacos que a
propria BDGD declara fechados (`SSDMT` e `UNSEMT`): abrir os 38 lacos da
5001306 levou a perda de 77,2% para 11,5%. Seis deles tem um regulador dentro,
no arranjo de campo de chave de entrada, regulador, chave de saida e CHAVE DE
BYPASS, esta fechada. A trava do achado 48 (`chaves.bypass_de_regulador`) so
reconhece o bypass que liga exatamente os dois PACs do regulador; este liga os
das chaves vizinhas.

O ACHADO 70 E O LACO QUE ATRAVESSA UM TRANSFORMADOR. Na mesma 5001306, com os
seis bypass abertos, um laco de 42 elementos ligava por chaves de MT os dois
lados do abaixador `MCG-D-TRF-TR1` (34,5/13,8 kV). Abri-lo levou a perda de
64,5% para 11,6%, sem desligar no. Os outros 31 lacos, todos na mesma tensao,
nao mudavam nada: na 5001242, abrir so os dois bypass ja dava os mesmos 14,6%
de abrir todos. O que faz mal nao e o laco — e o laco atravessar uma mudanca
de tensao. Por isso cada laco sai com a `razao` liquida em volta dele.

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
# Relacao liquida em volta do laco abaixo da qual ele e coerente. Tape de
# transformador de distribuicao anda em degraus de 2,5%; 34,5/13,8 e 150%.
RAZAO_TOLERADA = 0.05


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

    Devolve uma lista de `{'fecha', 'ciclo', 'regulador', 'transformadores',
    'razao'}`:

    - `fecha`: o elemento que fecha o laco;
    - `ciclo`: os elementos do ciclo fundamental que ele fecha, ele primeiro;
    - `regulador`: o primeiro regulador do ciclo, SO se o ciclo for curto
      (`CICLO_CURTO`) — a forma do bypass. Num ciclo longo o regulador pode
      ser so vizinho do anel;
    - `transformadores`: os transformadores do ciclo que NAO sao regulador;
    - `razao`: o produto das relacoes de tensao percorrendo o ciclo
      (achado 70). 1 e laco coerente — dois transformadores de subestacao em
      paralelo, por exemplo. Diferente de 1, o laco impoe a mesma tensao a
      barras que um transformador separa, e a diferenca circula.

    `reguladores`, quando dado, e o conjunto de `transformer.<nome>` em
    minusculas; sem ele vale o prefixo `REG_` do `complementos`.
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
    viz = collections.defaultdict(list)
    for n in fontes:
        if acha(n) != acha(fontes[0]):
            # a fonte liga as proprias fases; na arvore, pelo elemento dela
            viz[fontes[0]].append((n, 'Vsource', 1.0))
            viz[n].append((fontes[0], 'Vsource', 1.0))
        pai[acha(n)] = acha(fontes[0])

    arestas = []
    razao_de = {}
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
        if cls == 'transformer':
            dss.Transformers.Name(el.split('.', 1)[1])
            kvs = []
            for w in (1, 2):
                dss.Transformers.Wdg(w)
                kvs.append(dss.Transformers.kV())
            # de 1 para 2; a tensao de fase escala igual a de linha
            razao_de[el] = (kvs[1] / kvs[0]) if kvs[0] > 0 else 1.0
        arestas.append((0 if cls == 'transformer' else 1, el,
                        list(zip(_nos(bs[0], nf), _nos(bs[1], nf)))))

    fecham = []
    for prio, el, pares in sorted(arestas, key=lambda a: a[0]):
        if prio == 1 and all(acha(a) == acha(b) for a, b in pares):
            fecham.append((el, pares))
            continue
        for a, b in pares:
            if acha(a) != acha(b):
                pai[acha(a)] = acha(b)
                # (vizinho, elemento, fator de tensao indo daqui para la)
                r = razao_de.get(el, 1.0)
                viz[a].append((b, el, r))
                viz[b].append((a, el, 1.0 / r if r else 1.0))

    # A FLORESTA ENRAIZADA: cada no sabe o pai, o elemento que o liga a ele,
    # a profundidade e a tensao relativa a raiz. O ciclo sai pelo ancestral
    # comum, sem busca e sem limite de tamanho — o laco do achado 70 na
    # 5001306 tem 42 elementos.
    sobe, prof, tensao = {}, {}, {}
    for raiz in list(viz):
        if raiz in prof:
            continue
        prof[raiz], tensao[raiz] = 0, 1.0
        fila = collections.deque([raiz])
        while fila:
            x = fila.popleft()
            for y, e, r in viz[x]:
                if y not in prof:
                    prof[y], tensao[y] = prof[x] + 1, tensao[x] * r
                    sobe[y] = (x, e)
                    fila.append(y)

    def caminho(o, d):
        if o not in prof or d not in prof:
            return []
        a, b, ea, eb = o, d, [], []
        while prof[a] > prof[b]:
            a, e = sobe[a]
            ea.append(e)
        while prof[b] > prof[a]:
            b, e = sobe[b]
            eb.append(e)
        while a != b:
            if a not in sobe or b not in sobe:
                return []                  # arvores diferentes
            a, e = sobe[a]
            ea.append(e)
            b, e = sobe[b]
            eb.append(e)
        return ea + eb[::-1]

    saida = []
    for el, pares in fecham:
        o, d = pares[0]
        c = [el] + caminho(o, d)
        # o elemento que fecha e linha: impoe a mesma tensao nas duas pontas.
        # Pela arvore, as pontas estao em tensao[o] e tensao[d].
        razao = (tensao[d] / tensao[o]) if (o in tensao and d in tensao
                                            and tensao[o]) else 1.0
        curto = 1 < len(c) <= CICLO_CURTO + 1
        c = [e for e in c if e != 'Vsource']
        reg = (next((e for e in c if e_regulador(e, reguladores)), None)
               if curto else None)
        trafos = [e for e in c if e.lower().startswith('transformer.')
                  and not e_regulador(e, reguladores)]
        saida.append({'fecha': el, 'ciclo': c if len(c) > 1 else [],
                      'regulador': reg, 'transformadores': trafos,
                      'razao': razao})
    return saida


def incoerente(laco, tolerancia=RAZAO_TOLERADA):
    """O laco atravessa uma mudanca de tensao que ele mesmo desfaz."""
    return abs(laco.get('razao', 1.0) - 1.0) > tolerancia


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


# AVISO DE SOLUCAO NAO E MODELO QUEBRADO. O MASTER termina com `Solve`, e o
# `Max Control Iterations Exceeded` (#485) sobe como excecao do `Redirect`
# depois que o circuito ja esta montado. Ate 21/09/2026 a etapa
# `reguladores.py` desistia da subestacao por ele — e eram justamente as que
# nao convergem, sete delas na EQUATORIAL6072, as que mais precisam dos
# achados 69 e 70. O `validador.py` ja tinha aprendido isso.
#
# SO o #485. O `Duplicate new element definition` (#266) aborta a montagem no
# meio, e um censo sobre meio circuito mente: esse continua erro.
AVISOS_DE_SOLUCAO = ('(#485)',)


def _aviso_de_solucao(e):
    return any(a in str(e) for a in AVISOS_DE_SOLUCAO)


def compilar(dss, master):
    """`Clear` + `Redirect`, tolerando aviso de solucao. Devolve o aviso, ou
    `None`; qualquer outro erro sobe."""
    dss.Text.Command('Clear')
    try:
        dss.Text.Command(f'Redirect "{os.path.abspath(master)}"')
        return None
    except Exception as e:                                   # noqa: BLE001
        if _aviso_de_solucao(e) and (dss.Circuit.NumCktElements() or 0) > 0:
            return str(e).splitlines()[0][:120]
        raise


def resolver(dss):
    """`Solve` que devolve False, em vez de subir, num aviso de solucao."""
    try:
        dss.Text.Command('Solve')
        return True
    except Exception as e:                                   # noqa: BLE001
        if _aviso_de_solucao(e):
            return False
        raise


def lacos_da_se(master):
    """O censo de uma subestacao: quantos lacos, quantos com regulador,
    quantos atravessam uma mudanca de tensao (achado 70) e quantos sao
    fechados por elo nosso (`VAO_EXTRA_*`, achado 33)."""
    import opendssdirect as dss
    fora = abertas(os.path.dirname(master))
    compilar(dss, master)
    lista = lacos(dss, fora)
    com_reg = [x['fecha'] for x in lista if x['regulador']]
    com_trafo = [x['fecha'] for x in lista if incoerente(x)]
    nossos = [x['fecha'] for x in lista
              if x['fecha'].lower().startswith('line.vao_extra')]
    return {'lacos': len(lista), 'com_regulador': len(com_reg),
            'por_elo_nosso': len(nossos),
            'atraves_de_transformador': len(com_trafo),
            'exemplos_atraves_de_transformador': com_trafo[:5],
            'exemplos_com_regulador': com_reg[:5]}


CABECALHO = """! ==========================================================================
!  LACO FECHADO ATRAVES DE TRANSFORMADOR — achado 70
! ==========================================================================
!  Um caminho de media tensao que liga os dois lados de um transformador impoe
!  a mesma tensao a barras que ele separa (34,5/13,8 kV, por exemplo), e a
!  diferenca circula pelo laco. Na 5001306 da EQUATORIAL6072, um laco assim
!  levava a perda de 11,6% a 64,5%, sem que no algum estivesse desligado.
!
!  Laco na MESMA tensao nao entra aqui: nas duas piores subestacoes de Goias,
!  abrir os outros 84 nao mudava a perda. Dois transformadores em paralelo
!  tambem nao: a relacao liquida em volta do laco e 1.
!
!  O CRITERIO E ELETRICO. Das chaves do laco, servem as que, abertas, nao
!  desenergizam no nenhum; delas abre-se a de menor perda. Chaves em serie no
!  mesmo caminho dao o mesmo resultado, e isso fica dito. Laco sem chave, ou
!  sem candidata que sirva, fica como a BDGD declara, e e listado abaixo.
!
!  {n} laco(s) aberto(s), {amb} sem decisao.
!
!  Para rodar SEM esta premissa, apague o `redirect _LACOS.dss` do MASTER.
! =========================================================================="""


def escrever(caminho, abertas=(), sem_decisao=()):
    """Escreve o `_LACOS.dss`. SEMPRE, mesmo vazio: o MASTER redireciona sem
    condicao, e `redirect` de arquivo ausente aborta a compilacao.

    `abertas`: `{'chave', 'controle', 'transformadores', 'razao', 'perda_kW',
    'equivalentes'}`. `sem_decisao`: `{'fecha', 'razao', 'motivo'}`.
    """
    from . import escrita
    out = [CABECALHO.format(n=len(abertas), amb=len(sem_decisao)), '']
    for a in abertas:
        eq = a.get('equivalentes') or 1
        out.append('Edit %s enabled=no   ! atravessa %s (relacao %.3f); '
                   'com ela aberta, perda de %.0f kW%s'
                   % (a['chave'], ', '.join(a['transformadores']) or '-',
                      a['razao'], a['perda_kW'],
                      '' if eq == 1 else
                      '; %d chaves equivalentes, esta e a de menor perda' % eq))
        if a.get('controle'):
            out.append('Edit %s enabled=no' % a['controle'])
    for s in sem_decisao:
        out.append('! sem decisao: laco fechado por %s (relacao %.3f) — %s'
                   % (s['fecha'], s['razao'], s['motivo']))
    if not abertas and not sem_decisao:
        out.append('! nenhum laco atraves de transformador nesta subestacao.')
    texto = '\n'.join(out) + '\n'
    escrita.escreve(caminho, texto)
    return texto
