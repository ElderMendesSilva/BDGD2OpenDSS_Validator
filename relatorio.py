# -*- coding: utf-8 -*-
"""RELATORIO VISUAL — dez figuras por subestacao, dez da concessao.

    python relatorio.py MODELOS_LT_V26                  a concessao inteira
    python relatorio.py MODELOS_LT_V26 --se AGV DBAR    so estas subestacoes
    python relatorio.py MODELOS_LT_V26 --so-geral       so o painel da base

Sai em `<pasta>/RELATORIO/`: um PNG por subestacao e um `_GERAL.png`.

POR QUE ISTO EXISTE. As figuras estavam espalhadas por cinco executaveis, uma
ou duas em cada, com estilos diferentes — `energia.py`, `validador.py`,
`verifica.py`, `valida_perdas.py` e `valida_balanco.py`. Ver uma subestacao
exigia rodar cinco programas e juntar os PNG a mao, e ninguem fazia isso.

NAO RESOLVE CIRCUITO NENHUM POR PADRAO. Le o que as etapas ja mediram —
`validacao.json`, `energia_dia.json`, `resumo.json` — e desenha. Roda em
segundos no laptop, sem cluster. Com `--abrir-modelo` ele compila a subestacao
para extrair perfil de tensao, carregamento e coordenadas, que sao as tres
figuras que exigem o modelo vivo; ai custa alguns segundos por subestacao.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss import graficos                            # noqa: E402


def _le(caminho):
    try:
        with open(caminho, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def _por_se(dados, chave='modelo'):
    """Lista ou dicionario, indexado pelo nome da subestacao."""
    if isinstance(dados, dict):
        return dados
    if isinstance(dados, list):
        return {str(x.get(chave) or x.get('se')): x for x in dados
                if isinstance(x, dict)}
    return {}


def _figura(linhas, colunas, titulo):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(linhas, colunas,
                             figsize=(colunas * 5.2, linhas * 3.4))
    fig.suptitle(titulo, fontsize=13, x=0.02, ha='left', weight='bold')
    return fig, [a for linha in axes for a in
                 (linha if hasattr(linha, '__len__') else [linha])]


# ---------------------------------------------------------------- subestacao

def _do_modelo(pasta, se):
    """Perfil de tensao, carregamento e coordenadas — exige compilar.

    Devolve (distancias, pus, carregamentos, xs, ys, cores). Tudo vazio quando
    o modelo nao abre: relatorio de subestacao quebrada tem de sair assim
    mesmo, com as figuras dizendo que nao ha dado.
    """
    vazio = ([], [], [], [], [], [])
    try:
        import opendssdirect as dss
    except Exception:
        return vazio
    d = os.path.join(pasta, se)
    master = os.path.join(d, 'MASTER-%s.dss' % se)
    if not os.path.exists(master):
        return vazio
    try:
        dss.Text.Command('compile "%s"' % master)
        dss.Text.Command('solve')
    except Exception:
        return vazio

    dist, pus = [], []
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        if dss.Bus.kVBase() <= 1:
            continue
        v = [p for p in dss.Bus.puVmagAngle()[0::2] if 0.001 < p < 3]
        if not v:
            continue
        pus.append(min(v))
        dist.append(dss.Bus.Distance())

    carga = []
    i = dss.Lines.First()
    while i:
        try:
            nom = dss.Lines.NormAmps()
            dss.Circuit.SetActiveElement('Line.' + dss.Lines.Name())
            c = dss.CktElement.CurrentsMagAng()[0::2]
            if nom and c:
                carga.append(100.0 * max(c[:3]) / nom)
        except Exception:
            pass
        i = dss.Lines.Next()

    xs, ys, cor = [], [], []
    coords = os.path.join(d, 'BusCoords.dat')
    if os.path.exists(coords):
        pu_de = {}
        for b in dss.Circuit.AllBusNames():
            dss.Circuit.SetActiveBus(b)
            v = [p for p in dss.Bus.puVmagAngle()[0::2] if 0.001 < p < 3]
            if v:
                pu_de[b.lower()] = min(v)
        with open(coords, encoding='utf-8', errors='ignore') as fh:
            for L in fh:
                p = L.split(',')
                if len(p) >= 3:
                    try:
                        xs.append(float(p[1]))
                        ys.append(float(p[2]))
                        cor.append(pu_de.get(p[0].strip().lower()))
                    except ValueError:
                        pass
    return dist, pus, carga, xs, ys, cor


def uma_subestacao(pasta, se, val, ene, ger, destino, abrir=True):
    """As dez figuras de uma subestacao."""
    import matplotlib.pyplot as plt
    v = val.get(se) or {}
    e = ene.get(se) or {}
    g = ger.get(se) or {}
    serie = e.get('serie') or {}
    fonte = serie.get('fonte_kw') or []
    gd = serie.get('gd_kw') or []
    perdas = serie.get('perdas_kw') or []

    dist, pus, carga, xs, ys, cor = (_do_modelo(pasta, se) if abrir
                                     else ([], [], [], [], [], []))

    fig, ax = _figura(4, 3, '%s — subestacao %s' % (os.path.basename(pasta), se))
    graficos.perfil_de_tensao(ax[0], dist, pus)
    graficos.histograma_de_tensao(ax[1], pus)
    graficos.mapa(ax[2], xs, ys, cor, 'Rede (cor = tensao)')
    graficos.curva_do_dia(ax[3], fonte, gd, perdas)
    graficos.perdas_do_dia(ax[4], fonte, perdas)
    graficos.geracao_no_dia(ax[5], fonte, gd)
    graficos.cobertura_da_gd(ax[6], fonte, gd)
    graficos.carregamento_liquido(ax[7], fonte)
    graficos.carregamento(ax[8], carga)
    graficos.composicao_da_perda(ax[9], v.get('perdas_linhas_kW'),
                                 v.get('perdas_trafos_kW'))
    graficos.texto(ax[10], [
        'veredicto      %s' % (v.get('veredicto') or '—'),
        'converge       %s em %s iteracoes' % (v.get('converge'),
                                               v.get('iteracoes')),
        'alimentadores  %s' % (g.get('alimentadores') or '—'),
        'trafos         %s' % (g.get('trafos') or '—'),
        'km de MT       %s' % (g.get('km_MT') or '—'),
        'linhas         %s' % (v.get('n_linhas') or '—'),
        'cargas         %s' % (v.get('n_cargas') or '—'),
        'sem tensao     %s' % (v.get('cargas_sem_tensao') or 0),
        'perda do dia   %s%%' % (e.get('perdas_pct') or '—'),
        'V_MT min/med   %s / %s' % (v.get('V_MT_min'), v.get('V_MT_mediana')),
    ], 'Resumo')
    graficos.texto(ax[11], [
        'kWh injetado   %s' % _fmt(e.get('kWh_injetado')),
        'kWh perdas     %s' % _fmt(e.get('kWh_perdas')),
        'kWh da GD      %s' % _fmt(e.get('kWh_gd')),
        'pico da GD     %s kW' % _fmt(e.get('pico_gd_kW')),
        'passos ok      %s de %s' % (e.get('passos_ok'), e.get('passos')),
        '',
        'reg. pendurado %s' % (g.get('reguladores_pendurados') or 0),
        'chave ilhada   %s' % (g.get('chaves_ilhadas') or 0),
        'PAC invertido  %s' % (g.get('trafos_pac_invertido') or 0),
    ], 'Energia do dia e anomalias')

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    # A FIGURA MORA COM O MODELO. Quem abre a pasta de uma subestacao para
    # olhar o `.dss` acha o retrato dela do lado, sem precisar saber que existe
    # uma pasta de relatorio em outro lugar.
    dse = os.path.join(pasta, se)
    alvo = (os.path.join(dse, 'RELATORIO.png') if os.path.isdir(dse)
            else os.path.join(destino, '%s.png' % se))
    fig.savefig(alvo, dpi=110)
    plt.close(fig)
    return alvo


def _fmt(x):
    if x is None:
        return '—'
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return str(x)


# ----------------------------------------------------------------- concessao

def a_concessao(pasta, val, ene, ger, ver, destino):
    """As dez figuras da base inteira."""
    import collections
    import matplotlib.pyplot as plt

    ses = sorted(set(val) | set(ver) | set(ger))
    ses = [s for s in ses if str(s).strip().upper() not in ('AT', '_AT')]
    cont = collections.Counter(
        str((ver.get(s) or {}).get('veredicto') or '—').split('[')[0]
        for s in ses)

    def num(d, s, k):
        x = (d.get(s) or {}).get(k)
        try:
            f = float(x)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    perdas = [(num(ene, s, 'perdas_pct'), s) for s in ses]
    perdas = [(v, s) for v, s in perdas if v is not None]
    vmin = [(num(val, s, 'V_MT_min'), s) for s in ses]
    vmin = [(v, s) for v, s in vmin if v is not None]
    kms = [(num(ger, s, 'km_MT'), s) for s in ses]
    kms = [(v, s) for v, s in kms if v is not None]

    # a serie somada da concessao
    passos = 0
    for s in ses:
        sr = ((ene.get(s) or {}).get('serie') or {}).get('fonte_kw') or []
        passos = max(passos, len(sr))
    soma_f = [0.0] * passos
    soma_g = [0.0] * passos
    soma_p = [0.0] * passos
    for s in ses:
        sr = (ene.get(s) or {}).get('serie') or {}
        for alvo, chave in ((soma_f, 'fonte_kw'), (soma_g, 'gd_kw'),
                            (soma_p, 'perdas_kw')):
            v = sr.get(chave) or []
            for i in range(min(len(v), passos)):
                alvo[i] += v[i] or 0.0

    fig, ax = _figura(4, 3, '%s — concessao (%d subestacoes)'
                      % (os.path.basename(pasta), len(ses)))
    graficos.veredictos(ax[0], cont)
    graficos.histograma(ax[1], [v for v, _ in perdas],
                        'Perda por subestacao', '% da injecao', corte=10.0)
    graficos.ranking(ax[2], [s for _, s in perdas], [v for v, _ in perdas],
                     'Maiores perdas', '% da injecao', limite=10.0)
    graficos.curva_do_dia(ax[3], soma_f, soma_g, soma_p)
    graficos.geracao_no_dia(ax[4], soma_f, soma_g)
    graficos.cobertura_da_gd(ax[5], soma_f, soma_g)
    graficos.histograma(ax[6], [v for v, _ in vmin],
                        'Tensao minima por subestacao', 'pu', corte=0.93)
    graficos.ranking(ax[7], [s for _, s in kms], [v for v, _ in kms],
                     'Maiores redes', 'km de MT')
    graficos.dispersao(ax[8], [num(ger, s, 'km_MT') or 0 for s, in
                               [(s,) for s in ses]],
                       [num(ene, s, 'perdas_pct') or 0 for s in ses],
                       'Perda contra tamanho', 'km de MT', '% de perda')
    tot_l = sum(num(val, s, 'perdas_linhas_kW') or 0 for s in ses)
    tot_t = sum(num(val, s, 'perdas_trafos_kW') or 0 for s in ses)
    graficos.composicao_da_perda(ax[9], tot_l, tot_t)
    sem_v = sum(int(num(val, s, 'cargas_sem_tensao') or 0) for s in ses)
    graficos.texto(ax[10], [
        'subestacoes    %d' % len(ses),
        'com veredicto OK %d (%.1f%%)' % (cont.get('OK', 0),
                                          100.0 * cont.get('OK', 0) / len(ses)
                                          if ses else 0),
        'alimentadores  %d' % sum(int(num(ger, s, 'alimentadores') or 0)
                                  for s in ses),
        'trafos         %s' % _fmt(sum(int(num(ger, s, 'trafos') or 0)
                                       for s in ses)),
        'km de MT       %s' % _fmt(sum(v for v, _ in kms)),
        'cargas s/tensao %s' % _fmt(sem_v),
        'perda mediana  %.2f%%' % (sorted(v for v, _ in perdas)[len(perdas) // 2]
                                   if perdas else 0),
    ], 'Concessao em numeros')
    graficos.texto(ax[11], [
        'kWh injetado   %s' % _fmt(sum(num(ene, s, 'kWh_injetado') or 0
                                       for s in ses)),
        'kWh perdas     %s' % _fmt(sum(num(ene, s, 'kWh_perdas') or 0
                                       for s in ses)),
        'kWh da GD      %s' % _fmt(sum(num(ene, s, 'kWh_gd') or 0
                                       for s in ses)),
        '',
        'A SERIE DE 96 PASSOS e o que permite',
        'o modo daily, e o modo daily e o que',
        'torna a GD analisavel: fluxo reverso,',
        'nao-coincidencia com o pico e o',
        'carregamento MINIMO so aparecem nela.',
    ], 'Energia do dia')

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    alvo = os.path.join(destino, '_GERAL.png')
    fig.savefig(alvo, dpi=110)
    plt.close(fig)
    return alvo


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pasta', help='pasta MODELOS_* da rodada')
    ap.add_argument('--se', nargs='*', default=None,
                    help='apenas estas subestacoes')
    ap.add_argument('--so-geral', action='store_true',
                    help='so o painel da concessao')
    ap.add_argument('--sem-modelo', action='store_true',
                    help='nao compila: pula perfil, carregamento e mapa')
    ap.add_argument('--saida', default=None)
    a = ap.parse_args(argv)

    if not os.path.isdir(a.pasta):
        print('pasta nao encontrada: %s' % a.pasta, file=sys.stderr)
        return 1
    destino = a.saida or os.path.join(a.pasta, 'RELATORIO')
    os.makedirs(destino, exist_ok=True)

    val = _por_se(_le(os.path.join(a.pasta, 'validacao.json')) or [])
    # CADA ARQUIVO USA UMA CHAVE: `validacao` diz `modelo`, `verificacao`
    # diz `se` e `resumo_geral` diz `SE`. Ler todos com a mesma chave deixava
    # o veredicto vazio no relatorio, sem erro nenhum.
    ver = _por_se(_le(os.path.join(a.pasta, 'verificacao.json')) or [], 'se')
    ene = _por_se(_le(os.path.join(a.pasta, 'energia_dia.json')) or [], 'se')
    ger = _por_se(_le(os.path.join(a.pasta, 'resumo_geral.json')) or [], 'SE')

    if not (val or ver or ene):
        print('nenhum resultado em %s — rode o ciclo antes' % a.pasta,
              file=sys.stderr)
        return 1

    feitos = []
    feitos.append(a_concessao(a.pasta, val, ene, ger, ver, destino))
    print('concessao -> %s' % feitos[-1], flush=True)

    if not a.so_geral:
        alvo = a.se or sorted(s for s in (set(val) | set(ver))
                              if str(s).strip().upper() not in ('AT', '_AT'))
        for k, se in enumerate(alvo, 1):
            try:
                p = uma_subestacao(a.pasta, se, val, ene, ger, destino,
                                   abrir=not a.sem_modelo)
                feitos.append(p)
                print('[%d/%d] %s' % (k, len(alvo), p), flush=True)
            except Exception as e:                          # noqa: BLE001
                print('[%d/%d] %s: FALHOU (%s)' % (k, len(alvo), se, e),
                      flush=True)

    print('\n%d figuras em %s' % (len(feitos), destino))
    # Gerar nada nao e gerar: relatorio vazio que sai 0 vira "sucesso".
    return 0 if len(feitos) > 1 or a.so_geral else 1


if __name__ == '__main__':
    sys.exit(main())
