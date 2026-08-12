# -*- coding: utf-8 -*-
"""
DECOMPOSIÇÃO AT ↔ SUBESTAÇÕES — a tensão de cabeceira CALCULADA
==============================================================

    python decompor.py                     abre o painel e pergunta
    python decompor.py MODELOS_V9
    python decompor.py MODELOS_V9 --aplicar

POR QUE ISTO EXISTE
-------------------
O `MASTER-GERAL` junta a concessão inteira num arquivo só. Na Enel SP são
2,39 milhões de elementos, e eles não cabem em 15,8 GB de RAM (achado 13). A
saída não é apagar a baixa tensão — é parar de exigir que tudo caiba junto.

A decomposição são dois modelos acoplados:

    MASTER-AT.dss      a malha de 88 kV, os transformadores de potência, e
                       cada subestação como carga equivalente na barra de MT.
                       ~19.500 elementos, menos de 1% do monolítico.

    MASTER-<SE>.dss    os 155 modelos por subestação, INTACTOS, com a BT
                       completa. Nada é apagado.

O acoplamento é a tensão de cabeceira. Hoje ela é DECLARADA em cada modelo
isolado, vinda de `CTMT.TEN_OPE` — na Enel SP, 1,09 pu em 1.586 dos 1.806
alimentadores. É a maior premissa não medida que restou no modelo, e é
exatamente o que a rede de AT calcularia.

Este programa resolve a AT e diz, subestação por subestação, qual é a tensão
que a malha de fato entrega. Com `--aplicar`, reescreve o `pu` dos modelos
isolados com o valor calculado.

O QUE ELE NÃO É
---------------
Não é equivalente a resolver o monólito. A decomposição supõe que, na
interface, a subestação se comporta como carga — o que é exato para rede
radial abaixo do transformador, e é o caso aqui. O erro fica na convergência
do laço, e é medido pelo próprio laço: a coluna `Δ` do relatório mostra
quanto a tensão ainda se moveu entre uma iteração e a seguinte.

A validação honesta é comparar com o monólito numa base onde ele CABE.
Roraima serve: lá o `MASTER-GERAL` compila.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _dss():
    try:
        import opendssdirect as dss
    except ImportError:
        raise SystemExit('Instale: pip install opendssdirect.py')
    return dss


def resolver_at(raiz, log=print, cargas=None):
    """Compila o MASTER-AT e devolve {SE: (pu na barra, kV base, barra)}.

    `cargas` sobrescreve a demanda de cada subestacao, em kW. E o que o laco
    de acoplamento usa: a demanda que a subestacao REALMENTE puxa depende da
    tensao que ela recebe, e a tensao depende da demanda.
    """
    dss = _dss()
    cam = os.path.join(raiz, 'MASTER-AT.dss')
    if not os.path.exists(cam):
        raise SystemExit(f'{cam} nao existe — regere com o conversor atual')
    cwd = os.getcwd()
    try:
        dss.Text.Command('Clear')
        dss.Text.Command(f'Compile "{cam}"')
        if cargas:
            for se, v in cargas.items():
                kw, kvar = v if isinstance(v, tuple) else (v, None)
                if not kw or kw <= 0:
                    continue
                # kW E kvar. Numa malha de 88 kV o X domina o R, entao a
                # queda de tensao e comandada pelo REATIVO: realimentar so a
                # potencia ativa e manter pf fixo em 0,92 deixava 0,0162 pu de
                # erro mediano contra o monolito.
                if kvar is not None:
                    dss.Text.Command(f'Load.SE_{se}.kW={kw:.4f} '
                                     f'kvar={kvar:.4f}')
                else:
                    dss.Text.Command(f'Load.SE_{se}.kW={kw:.4f}')
            dss.Solution.Solve()
    finally:
        os.chdir(cwd)
    if not dss.Solution.Converged():
        log('  AVISO: o modelo de AT nao convergiu — os numeros abaixo nao '
            'valem')
    # cada carga SE_<nome> esta na barra de MT daquela subestacao
    out = {}
    i = dss.Loads.First()
    while i:
        nome = dss.Loads.Name()
        if nome.lower().startswith('se_'):
            se = nome[3:]
            dss.Circuit.SetActiveElement('Load.' + nome)
            barra = dss.CktElement.BusNames()[0].split('.')[0]
            dss.Circuit.SetActiveBus(barra)
            v = [x for x in dss.Bus.puVmagAngle()[0::2] if x == x and x > 0]
            if v:
                out[se] = (sum(v) / len(v), dss.Bus.kVBase(), barra)
        i = dss.Loads.Next()
    return out


def demanda(raiz, se, pu, log=print):
    """Quanta potencia a subestacao puxa quando alimentada em `pu`.

    E a metade de baixo do acoplamento. As cargas do modelo sao ZIP com 50%
    de impedancia constante, entao a demanda CAI com a tensao — alimentar a
    subestacao a 0,95 e a 1,00 nao da o mesmo kW, e supor que da e o erro que
    a primeira versao deste programa cometeu.
    """
    dss = _dss()
    cam = os.path.join(raiz, se, f'MASTER-{se}.dss')
    if not os.path.exists(cam):
        return None
    cwd = os.getcwd()
    try:
        dss.Text.Command('Clear')
        dss.Text.Command(f'Compile "{cam}"')
        # `source` e o Vsource que o `New Circuit` cria; as barras extras
        # ganham FONTE1_, FONTE2_... e tambem acompanham
        dss.Text.Command(f'Vsource.source.pu={pu:.5f}')
        for v in dss.Vsources.AllNames():
            if v.lower() != 'source':
                dss.Text.Command(f'Vsource.{v}.pu={pu:.5f}')
        dss.Solution.Solve()
        if not dss.Solution.Converged():
            return None
        p, q = dss.Circuit.TotalPower()[:2]    # kW e kvar, negativos = entregues
    finally:
        os.chdir(cwd)
    if p != p or q != q:
        return None
    # O total ja e LIQUIDO: perdas internas somadas e geracao distribuida
    # descontada. E exatamente o que a subestacao pede a malha de AT.
    return abs(p), abs(q)


def acoplar(raiz, ses, passos=4, tol=0.002, log=print):
    """O laco: resolve a AT, mede a demanda real, realimenta, repete.

    Devolve (pu por subestacao, historico das diferencas). Para quando o
    maior deslocamento de tensao entre duas iteracoes cai abaixo de `tol`.
    """
    cargas, hist = None, []
    pu = {}
    for it in range(1, passos + 1):
        calc = resolver_at(raiz, log, cargas)
        novo = {se: v[0] for se, v in calc.items()}
        desl = max((abs(novo[s] - pu.get(s, novo[s])) for s in novo),
                   default=0.0)
        hist.append(desl)
        pu = novo
        log(f'   iteracao {it}: deslocamento maximo {desl:+.4f} pu, '
            f'tensao mediana {statistics.median(pu.values()):.4f}')
        if it > 1 and desl < tol:
            log(f'   convergiu em {it} iteracoes')
            break
        cargas = {}
        for se in ses:
            if se in pu:
                d = demanda(raiz, se, pu[se], log)
                if d:
                    cargas[se] = d
    return pu, hist, calc


_RX_PU = re.compile(r'(\bpu=)([\d.]+)', re.I)


def declarado(raiz, se):
    """O `pu` que o MASTER isolado declara hoje."""
    cam = os.path.join(raiz, se, f'MASTER-{se}.dss')
    if not os.path.exists(cam):
        return None
    with open(cam, encoding='utf-8', errors='replace') as fh:
        for l in fh:
            if l.lstrip().lower().startswith(('new circuit', 'new vsource')):
                g = _RX_PU.search(l)
                if g:
                    return float(g.group(2))
    return None


def aplicar(raiz, se, pu):
    """Reescreve o `pu` da fonte do modelo isolado. Devolve (antes, depois)."""
    cam = os.path.join(raiz, se, f'MASTER-{se}.dss')
    if not os.path.exists(cam):
        return None
    with open(cam, encoding='utf-8', errors='replace') as fh:
        linhas = fh.readlines()
    antes = None
    for k, l in enumerate(linhas):
        if l.lstrip().lower().startswith(('new circuit', 'new vsource')):
            g = _RX_PU.search(l)
            if not g:
                continue
            if antes is None:
                antes = float(g.group(2))
            linhas[k] = _RX_PU.sub(lambda m: f'{m.group(1)}{pu:.4f}', l, count=1)
    if antes is None:
        return None
    with open(cam, 'w', encoding='utf-8') as fh:
        fh.writelines(linhas)
    return antes, pu


def _painel():
    import interativo
    v = interativo.formulario('decompor', 'Decomposição AT ↔ subestações', [
        {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'precisa do MASTER-AT.dss — regere com o conversor atual'},
        {'chave': 'aplicar', 'tipo': 'bool', 'rotulo': 'Aplicar aos modelos',
         'padrao': False,
         'dica': 'reescreve o pu da fonte de cada subestação isolada'},
    ], ajuda='Resolve a rede de alta tensão com as subestações como carga '
             'equivalente e mede a tensão de cabeceira que a malha entrega. '
             'Hoje essa tensão é declarada (CTMT.TEN_OPE), não calculada.')
    if not v:
        return False
    sys.argv += [v['raiz']] + (['--aplicar'] if v.get('aplicar') else [])
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('raiz', nargs='?', default='MODELOS_V9')
    ap.add_argument('--aplicar', action='store_true',
                    help='reescreve o pu da fonte dos modelos isolados')
    ap.add_argument('--limiar', type=float, default=0.01,
                    help='diferenca em pu a partir da qual a subestacao e '
                         'listada (padrao 0,01)')
    ap.add_argument('--passos', type=int, default=4,
                    help='iteracoes do acoplamento AT <-> subestacoes. Uma '
                         'passada so ignora que a demanda cai com a tensao')
    a = ap.parse_args()
    raiz = os.path.abspath(a.raiz)

    print('resolvendo a rede de alta tensao...', flush=True)
    calc0 = resolver_at(raiz)
    if not calc0:
        raise SystemExit('nenhuma carga de subestacao encontrada no MASTER-AT')
    print(f'  {len(calc0)} subestacoes na malha\n')

    print(f'acoplando (ate {a.passos} iteracoes):')
    pu_ac, hist, calc = acoplar(raiz, sorted(calc0), passos=a.passos)
    calc = {se: (pu_ac.get(se, v[0]), v[1], v[2]) for se, v in calc.items()}
    print()

    linhas = []
    for se, (pu, kvb, barra) in sorted(calc.items()):
        dec = declarado(raiz, se)
        linhas.append({'se': se, 'pu_calculado': round(pu, 4),
                       'pu_declarado': dec, 'kv_base': round(kvb, 4),
                       'barra': barra,
                       'diferenca': None if dec is None else round(pu - dec, 4)})

    com = [x for x in linhas if x['diferenca'] is not None]
    pus = [x['pu_calculado'] for x in linhas]
    print(f'{"tensao de cabeceira CALCULADA":36s} '
          f'min {min(pus):.4f}  mediana {statistics.median(pus):.4f}  '
          f'max {max(pus):.4f}')
    if com:
        d = [x['diferenca'] for x in com]
        print(f'{"diferenca contra a DECLARADA":36s} '
              f'min {min(d):+.4f}  mediana {statistics.median(d):+.4f}  '
              f'max {max(d):+.4f}')
        fora = [x for x in com if abs(x['diferenca']) >= a.limiar]
        print(f'\n{len(fora)} de {len(com)} subestacoes diferem em '
              f'{a.limiar:g} pu ou mais:')
        print(f'   {"SE":8s} {"declarado":>10s} {"calculado":>10s} {"dif":>8s}')
        for x in sorted(fora, key=lambda z: -abs(z['diferenca']))[:20]:
            print(f'   {x["se"]:8s} {x["pu_declarado"]:10.4f} '
                  f'{x["pu_calculado"]:10.4f} {x["diferenca"]:+8.4f}')

    dest = os.path.join(raiz, 'tensao_cabeceira.json')
    with open(dest, 'w', encoding='utf-8') as fh:
        json.dump(linhas, fh, indent=1, ensure_ascii=False)
    print(f'\ndetalhe em {dest}')

    if a.aplicar:
        n = 0
        for x in linhas:
            r = aplicar(raiz, x['se'], x['pu_calculado'])
            n += bool(r)
        print(f'\n{n} modelos isolados tiveram o pu da fonte reescrito.')
        print('A tensao de cabeceira deles passa a ser CALCULADA pela malha '
              'de AT, e nao declarada. Rode verifica/energia de novo.')


if __name__ == '__main__':
    main()
