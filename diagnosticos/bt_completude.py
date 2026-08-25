# -*- coding: utf-8 -*-
"""A BDGD declara rede de BT suficiente para modelar, ou so declara os clientes?

    python diagnosticos/bt_completude.py --bases $BDGD2DSS_BASES
    python diagnosticos/bt_completude.py --bases /d/BDGDs --so Roraima,Light

POR QUE A PERGUNTA VEM ANTES DA DECISAO. Modelar a BT (`--bt completo`) so
aumenta a fidelidade se a BT DECLARADA estiver la. Rede de baixa incompleta e
pior do que rede de baixa ausente: o modelo agregado ADMITE que nao tem a BT,
enquanto o completo com dado faltando parece te-la e entrega numero errado com
cara de numero certo.

Isto nao converte nada e nao depende de modelo gerado — le a `.gdb` e mede.

A CADEIA QUE PRECISA ESTAR INTEIRA e `trafo -> SSDBT -> RAMLIG -> UC`, e o
`converter.py` registra o elo que costuma faltar: a UCBT e a PONTA DO RAMLIG, e
nao um no da rede secundaria. Uma base que publica SSDBT mas nao RAMLIG tem
rede de baixa e nao tem como ligar cliente nenhum nela.

Por isso a cobertura e medida em tres pontos, e nao um:

    1. o secundario do trafo (UNTRMT) aparece na rede de BT?
    2. o PAC da UC aparece no RAMLIG?           <- o elo critico
    3. o PAC da UC aparece em SSDBT + RAMLIG?   <- limite superior

O `PAC_2` do UNTRMT e o lado de baixa NA MAIORIA dos registros, mas o achado 54
mostrou que ha trafos invertidos. Por isso os dois lados sao medidos e o
relatorio mostra o melhor, dizendo qual foi.

Km POR UC e o indicador de plausibilidade: rede urbana de baixa tem dezenas de
metros por cliente. Valor muito abaixo disso denuncia rede declarada pela
metade mesmo quando a cobertura de PAC parece boa.
"""
import argparse
import glob
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss.leitor import BDGD, num, no            # noqa: E402


def _pacs_e_km(b, camada):
    """Conjunto de PACs e quilometragem de uma camada de rede. ({}, 0) se ausente."""
    try:
        col = b.ler(camada, ['PAC_1', 'PAC_2', 'COMP'])
    except Exception:                                            # noqa: BLE001
        return set(), 0.0, 0
    n = len(col.get('PAC_1', []))
    if not n:
        return set(), 0.0, 0
    pacs = set()
    for k in ('PAC_1', 'PAC_2'):
        for v in col[k]:
            p = no(v)
            if p:
                pacs.add(p.lower())
    km = sum(num(x) for x in col.get('COMP', [])) / 1000.0
    return pacs, km, n


def uma_base(gdb, passo=700_000):
    b = BDGD(gdb, verbose=False)
    r = {'base': os.path.basename(gdb)}

    ssdbt, km_ssdbt, n_ssdbt = _pacs_e_km(b, 'SSDBT')
    ramlig, km_ramlig, n_ramlig = _pacs_e_km(b, 'RAMLIG')
    rede = ssdbt | ramlig
    r.update(n_ssdbt=n_ssdbt, km_ssdbt=round(km_ssdbt, 1),
             n_ramlig=n_ramlig, km_ramlig=round(km_ramlig, 1),
             barras_bt=len(rede))

    # --- 1. o secundario do trafo chega na rede de BT?
    try:
        t = b.ler('UNTRMT', ['PAC_1', 'PAC_2'])
        n_tr = len(t['PAC_1'])
        lados = {}
        for k in ('PAC_1', 'PAC_2'):
            lados[k] = sum(1 for v in t[k] if no(v) and no(v).lower() in rede)
        melhor = max(lados, key=lados.get)
        r.update(n_trafos=n_tr, trafo_lado=melhor,
                 pct_trafo_na_bt=round(100.0 * lados[melhor] / max(1, n_tr), 1))
    except Exception as e:                                       # noqa: BLE001
        r.update(n_trafos=0, trafo_lado='?', pct_trafo_na_bt=None,
                 erro_untrmt=str(e)[:80])

    # --- 2 e 3. as UCs de BT. Em fatias: a Enel SP tem 8,26 M.
    n_uc = em_ramlig = em_rede = sem_pac = 0
    try:
        # `ler_em_fatias` devolve (colunas, lidos, total) — e nao so as colunas.
        for fatia, _lidos, _total in b.ler_em_fatias('UCBT_tab', ['PAC'],
                                                     passo=passo):
            for v in fatia['PAC']:
                n_uc += 1
                p = no(v)
                if not p:
                    sem_pac += 1
                    continue
                p = p.lower()
                if p in ramlig:
                    em_ramlig += 1
                    em_rede += 1
                elif p in ssdbt:
                    em_rede += 1
    except Exception as e:                                       # noqa: BLE001
        r['erro_ucbt'] = str(e)[:80]

    r.update(n_uc=n_uc, sem_pac=sem_pac,
             pct_uc_no_ramlig=round(100.0 * em_ramlig / max(1, n_uc), 1),
             pct_uc_na_rede=round(100.0 * em_rede / max(1, n_uc), 1),
             m_bt_por_uc=round(1000.0 * (km_ssdbt + km_ramlig) / max(1, n_uc), 1))
    return r


def veredito(r):                                                 # noqa: C901
    """Da para modelar a BT desta base?

    O corte de 90% no RAMLIG nao e arbitrado por gosto: abaixo disso, uma UC em
    cada dez fica sem por onde se ligar, e o modelo completo passa a inventar
    barra isolada no lugar de rede. O de 10 m/UC e o piso do que uma rede de
    baixa real mede — abaixo disso a rede declarada nao chega nos clientes que
    ela mesma lista.
    """
    # Erro de leitura NAO pode virar veredito de qualidade. Sem isto, um
    # `TypeError` na varredura da UCBT deixa `n_uc=0` e a base e reprovada por
    # "RAMLIG incompleto" — diagnostico errado, com aparencia de medicao.
    # Aconteceu na primeira execucao deste script.
    if r.get('erro_ucbt') or r.get('erro_untrmt'):
        return 'NAO MEDIDO: %s' % (r.get('erro_ucbt') or r.get('erro_untrmt'))[:40]
    if not r.get('n_uc'):
        return 'NAO MEDIDO: UCBT_tab sem registros'
    if not r.get('n_ramlig'):
        return 'SEM RAMLIG — nao ha como ligar cliente'
    if not r.get('n_ssdbt'):
        return 'SEM SSDBT — so ramal, sem rede secundaria'
    if (r.get('pct_uc_no_ramlig') or 0) < 90.0:
        return 'RAMLIG INCOMPLETO'
    if (r.get('m_bt_por_uc') or 0) < 10.0:
        return 'REDE CURTA DEMAIS'
    if (r.get('pct_trafo_na_bt') or 0) < 80.0:
        return 'BT NAO CHEGA NO TRAFO'
    return 'ok'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', 'bdgds'))
    ap.add_argument('--so', help='prefixos das .gdb, separados por virgula (a ordem vale)')
    ap.add_argument('--passo', type=int, default=700_000)
    ap.add_argument('--saida-json', default='medicoes/bt_completude.json')
    a = ap.parse_args(argv)

    gdbs = []
    for d in a.bases.split(os.pathsep):
        gdbs += sorted(glob.glob(os.path.join(os.path.expanduser(d), '*.gdb')))
    if a.so:
        pref = [p.strip() for p in a.so.split(',') if p.strip()]
        ordenado = []
        for p in pref:
            ordenado += [g for g in gdbs
                         if os.path.basename(g).startswith(p) and g not in ordenado]
        gdbs = ordenado
    if not gdbs:
        print('nenhuma .gdb em %s' % a.bases)
        return 1

    print('%d bases\n' % len(gdbs), flush=True)
    saida = []
    for g in gdbs:
        t0 = time.time()
        try:
            r = uma_base(g, a.passo)
        except Exception as e:                                   # noqa: BLE001
            r = {'base': os.path.basename(g), 'erro': str(e)[:120]}
        r['veredito'] = veredito(r) if 'erro' not in r else 'FALHOU'
        r['seg'] = round(time.time() - t0, 1)
        saida.append(r)
        print('  %-46s %-28s %5.0fs' % (r['base'][:46], r['veredito'], r['seg']),
              flush=True)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8') as f:
        json.dump({'medido_em': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'bases': saida}, f, ensure_ascii=False, indent=1)

    cab = ('%-26s %10s %10s %9s %8s %8s %8s  %s'
           % ('base', 'UCs', 'RAMLIG', 'SSDBT km', 'UC/ram%', 'UC/rede%', 'm/UC', 'veredito'))
    print('\n' + '=' * len(cab))
    print(cab)
    print('=' * len(cab))
    for r in saida:
        if 'erro' in r:
            print('%-26s %s' % (r['base'][:26], r['erro']))
            continue
        print('%-26s %10s %10s %9s %7s%% %7s%% %8s  %s'
              % (r['base'][:26], f"{r['n_uc']:,}", f"{r['n_ramlig']:,}",
                 f"{r['km_ssdbt']:,.0f}", r['pct_uc_no_ramlig'],
                 r['pct_uc_na_rede'], r['m_bt_por_uc'], r['veredito']))
    print('\njson: %s' % a.saida_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
