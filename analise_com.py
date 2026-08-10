# -*- coding: utf-8 -*-
"""
ANALISE DA REDE VIA INTERFACE COM DO OpenDSS
============================================

Resolve o modelo pelo OpenDSSEngine.DSS (COM) e produz os graficos de
diagnostico, inclusive o desenho geografico do circuito.

    python analise_com.py                     abre o painel e pergunta o MASTER
    python analise_com.py MODELOS_V2\\MASTER-GERAL.dss
    python analise_com.py MODELOS_V2\\DABR\\MASTER-DABR.dss --saida figuras
    python analise_com.py ...MASTER-GERAL.dss --diario

Saidas (pasta `--saida`, por padrao "analise" ao lado do MASTER):

    01_circuito_geografico.png   tracado real, espessura = corrente,
                                 cor = carregamento (o "circuit plot")
    02_tensao_geografica.png     mesmo tracado, cor = tensao em pu
    03_perfil_tensao.png         tensao x distancia eletrica da fonte
    04_histograma_tensao.png     distribuicao com as faixas do PRODIST M8
    05_carregamento_linhas.png   distribuicao do carregamento
    06_perdas_por_alimentador.png  ranking de perdas (EnergyMeter)
    07_potencia_por_subestacao.png
    08_curva_diaria.png          so com --diario
    resumo.csv / resumo.json     numeros da rodada

Por que COM e nao opendssdirect: e a interface oficial no Windows, e a mesma
que a Enel usa, e o `Plot` nativo do OpenDSS so existe por ela. Os graficos
aqui sao feitos em matplotlib para poderem ser salvos e publicados, mas o
BusCoords gerado tambem habilita os comandos nativos:

    Plot Circuit Power max=2000 dots=n labels=n C1=Blue
    Plot Circuit Voltage
    Plot profile phases=all
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize, LinearSegmentedColormap
except Exception:
    raise SystemExit('Instale matplotlib:  py -m pip install matplotlib')

try:
    import win32com.client
except Exception:
    raise SystemExit('Instale pywin32:  py -m pip install pywin32')


# faixas do PRODIST Modulo 8 para tensao nominal > 1 kV
ADEQ = (0.93, 1.05)

# Teto de trechos por figura, e em quantas faixas a espessura e quantizada.
# Ver _corta e _colecoes: os dois numeros existem por causa do MASTER-GERAL,
# que traz 2,35 milhoes de trechos.
MAX_SEG = 300_000
N_LARGURAS = 6

CMAP_CARGA = LinearSegmentedColormap.from_list(
    'carga', ['#2c7fb8', '#41ab5d', '#fecc5c', '#fd8d3c', '#e31a1c'])
CMAP_TENSAO = LinearSegmentedColormap.from_list(
    'tensao', ['#b2182b', '#ef8a62', '#f7f7f7', '#67a9cf', '#2166ac'])


# ============================================================== infraestrutura
class Rede:
    """Fachada sobre o COM. Concentra aqui o que muda entre versoes."""

    def __init__(self, master):
        # O caminho ABSOLUTO tem de sair antes do Dispatch: o Start(0) do COM
        # troca o diretorio de trabalho do processo, e um caminho relativo
        # dado na linha de comando passa a apontar para outro lugar. O sintoma
        # e traicoeiro — compila "0 barras", nao levanta erro, e os graficos
        # saem vazios.
        self.master = os.path.abspath(master)
        if not os.path.exists(self.master):
            raise SystemExit(f'nao encontrei o MASTER: {self.master}')
        self.dss = win32com.client.Dispatch('OpenDSSEngine.DSS')
        if not self.dss.Start(0):
            raise SystemExit('Nao foi possivel iniciar o OpenDSSEngine.')
        self.txt = self.dss.Text
        self.ckt = self.dss.ActiveCircuit
        self.n_nan = 0                       # preenchido por resolver()
        print(f'OpenDSS {self.dss.Version.strip()}')

    def compilar(self):
        self.txt.Command = 'Clear'
        self.txt.Command = f'Compile "{self.master}"'
        print(f'  {self.ckt.NumBuses:,} barras | {self.ckt.NumNodes:,} nos | '
              f'{self.ckt.NumCktElements:,} elementos')
        # Circuito vazio nao e "rede pequena", e compilacao que falhou. Sem
        # esta parada o script segue e entrega figuras em branco como se
        # fossem resultado.
        if not self.ckt.NumBuses:
            raise SystemExit(
                f'o Compile nao produziu circuito nenhum.\n'
                f'  arquivo: {self.master}\n'
                f'  erro do OpenDSS: {self.dss.Error.Description or "(vazio)"}')

    def resolver(self, modo='snap'):
        self.txt.Command = f'Set mode={modo}'
        self.txt.Command = 'Set controlmode=static'
        self.txt.Command = 'Solve'
        # Em snapshot o OpenDSS NAO amostra medidores sozinho: sem o Sample os
        # registradores de energia e perdas ficam zerados e os "Max" ficam com
        # o valor sentinela -1e50. Com ele, integra-se 1 h de operacao.
        self.txt.Command = 'Reset'
        self.txt.Command = 'Sample'
        s = self.ckt.Solution
        print(f'  convergiu={bool(s.Converged)} em {s.Iterations} iteracoes')

        # Converged=True nao basta. Se ha NaN, o criterio de convergencia passa
        # trivialmente (toda comparacao com NaN e falsa) e os graficos saem
        # bonitos porque o filtro de NaN os descarta em silencio. Aqui o NaN e
        # gritado: no motor da EPRI ele contamina a fatoracao inteira e o
        # numero abaixo costuma ser quase todos os nos.
        v = np.asarray(self.ckt.AllBusVmagPu, dtype=float)
        self.n_nan = int(np.isnan(v).sum())
        if self.n_nan:
            print(f'  *** {self.n_nan:,} de {v.size:,} nos com NaN — '
                  f'os graficos abaixo ignoram esses nos e NAO representam a '
                  f'rede. Rode o validador para a causa.')
        return bool(s.Converged) and not self.n_nan

    # ------------------------------------------------------------ extracao
    def coordenadas(self):
        """{barra: (x, y)} das barras que tem coordenada definida."""
        co = {}
        for nome in self.ckt.AllBusNames:
            b = self.ckt.Buses(nome)
            if b.Coorddefined:
                co[nome.lower()] = (b.x, b.y)
        return co

    def tensoes_pu(self):
        """{barra: tensao pu media dos nos com tensao valida}."""
        v = {}
        for nome in self.ckt.AllBusNames:
            b = self.ckt.Buses(nome)
            pu = [x for x in b.puVmagAngle[0::2] if 0.01 < x < 3]
            if pu:
                v[nome.lower()] = float(np.mean(pu))
        return v

    def trechos(self, nivel='tudo'):
        """Uma entrada por Line: barras, corrente, ampacidade, kW.

        `nivel` filtra pelo prefixo do nome, que o conversor padroniza:
          at   -> AT_* e BAT_* (subtransmissao e barras de subestacao)
          mt   -> tudo que nao e AT nem BT (rede de media tensao e vaos)
          bt   -> N_* e os trechos de SSDBT/RAMLIG
        Num modelo da concessao inteira sao ~1,2 milhao de trechos; desenhar
        todos numa folha so satura o desenho e nao mostra nada.
        """
        out = []
        i = self.ckt.Lines.First
        while i:
            el = self.ckt.ActiveCktElement
            b1 = self.ckt.Lines.Bus1.split('.')[0].lower()
            b2 = self.ckt.Lines.Bus2.split('.')[0].lower()
            na = el.NormalAmps or 0
            cur = np.array(el.CurrentsMagAng[0::2], dtype=float)
            nc = el.NumConductors
            imax = float(np.nanmax(cur[:nc])) if nc and len(cur) >= nc else 0.0
            pw = np.array(el.Powers, dtype=float)
            kw = float(np.nansum(pw[0:2 * nc:2])) if nc else 0.0
            nm = self.ckt.Lines.Name.lower()
            e_at = nm.startswith('at_') or nm.startswith('bat_')
            e_bt = nm.startswith('n_')
            if nivel == 'at' and not e_at:
                i = self.ckt.Lines.Next; continue
            if nivel == 'mt' and (e_at or e_bt):
                i = self.ckt.Lines.Next; continue
            if np.isfinite(imax):
                out.append({'nome': self.ckt.Lines.Name, 'b1': b1, 'b2': b2,
                            'i': imax, 'inom': na, 'kw': kw,
                            'carreg': 100 * imax / na if na > 1 else np.nan})
            i = self.ckt.Lines.Next
        return out

    def medidores(self):
        """EnergyMeter -> perdas e energia por alimentador."""
        out = []
        m = self.ckt.Meters
        i = m.First
        while i:
            reg = list(m.RegisterValues)
            nomes = list(m.RegisterNames)
            # -1e50 e o sentinela de registrador nunca escrito
            d = {n.strip(): (0.0 if v < -1e40 else v) for n, v in zip(nomes, reg)}
            out.append({
                'alimentador': m.Name.replace('em_', '').upper(),
                'kWh': d.get('kWh', 0.0),
                'perdas_kWh': d.get('Zone Losses kWh', d.get('Losses kWh', 0.0)),
                'max_kW': d.get('Max kW', 0.0),
            })
            i = m.Next
        return out

    def fontes(self):
        out = []
        self.ckt.SetActiveClass('Vsource')
        i = self.ckt.ActiveClass.First
        while i:
            el = self.ckt.ActiveCktElement
            nc = el.NumConductors
            pw = np.array(el.Powers, dtype=float)
            out.append({'nome': el.Name,
                        'MW': -float(np.nansum(pw[0:2 * nc:2])) / 1000,
                        'Mvar': -float(np.nansum(pw[1:2 * nc:2])) / 1000})
            i = self.ckt.ActiveClass.Next
        return out


# =================================================================== graficos
def _fundo(ax, titulo, sub=''):
    ax.set_title(titulo, fontsize=13, weight='bold', loc='left', pad=22)
    if sub:
        ax.text(0, 1.008, sub, transform=ax.transAxes, fontsize=9, color='#555',
                va='bottom')
    ax.set_facecolor('white')


def _corta(seg, val, lar):
    """Reduz a MAX_SEG trechos, guardando os de MAIOR corrente.

    O MASTER-GERAL tem 2,35 milhoes de trechos. Numa folha de 2.100 x 1.540 px
    isso e mais de um trecho por pixel: o desenho vira mancha e nao informa
    nada. O corte por corrente preserva o que da forma a figura — tronco de MT
    e subtransmissao — e descarta o capilar de BT, que nessa escala e ruido.

    Devolve (seg, val, lar, quantos ficaram de fora).
    """
    seg = np.asarray(seg, dtype=float)
    val = np.asarray(val, dtype=float)
    lar = np.asarray(lar, dtype=float)
    if len(seg) <= MAX_SEG:
        return seg, val, lar, 0
    fora = len(seg) - MAX_SEG
    # ordena por corrente, fica com os maiores, e devolve a ordem original
    # para o desenho nao ganhar vies de sobreposicao
    esc = np.sort(np.argsort(-np.nan_to_num(lar))[:MAX_SEG])
    return seg[esc], val[esc], lar[esc], fora


def _colecoes(ax, seg, val, lar, cmap, norm, lw_max):
    """Desenha os trechos com espessura proporcional a corrente, em FAIXAS.

    Por que nao uma colecao so com um vetor de larguras, que era o que estava
    aqui: o matplotlib expande esse vetor em UMA especificacao de tracejado
    por segmento (`Collection._bcast_lwls`). Com 2,35 milhoes de trechos a
    lista estoura a memoria antes de desenhar o primeiro pixel — foi o
    MemoryError no MASTER-GERAL.

    Quantizando a largura em N_LARGURAS faixas, cada colecao recebe um
    ESCALAR e a expansao nao acontece. A leitura da figura nao muda: a olho
    nu ninguem distingue mais do que meia duzia de espessuras.
    """
    p95 = np.nanpercentile(lar, 95) or 1.0
    faixa = np.clip((np.nan_to_num(lar) / p95 * N_LARGURAS).astype(int),
                    0, N_LARGURAS - 1)
    for k in range(N_LARGURAS):
        m = faixa == k
        if not m.any():
            continue
        ax.add_collection(LineCollection(
            seg[m], array=val[m], cmap=cmap, norm=norm, capstyle='round',
            linewidths=0.35 + lw_max * (k + 0.5) / N_LARGURAS))
    ax.autoscale_view()
    ax.set_aspect('equal', adjustable='datalim')
    return ScalarMappable(norm=norm, cmap=cmap)


def _tracado(seg, val, lar, saida, titulo, sub, cmap, norm, rotulo_cb,
             lw_max=3.2, nota_recorte=''):
    """O corpo comum dos dois tracados geograficos."""
    if not len(seg):
        print('  (sem coordenadas — BusCoords nao carregado)')
        return
    n0 = len(seg)
    seg, val, lar, fora = _corta(seg, val, lar)
    if fora:
        # O recorte e por CORRENTE, entao o que fica e o tronco. A distribuicao
        # de COR do desenho passa a nao ser a da rede — dizer so "N trechos
        # omitidos" deixa o leitor concluir errado a partir do mapa. A
        # estatistica valida e a do conjunto inteiro, e ela vai escrita aqui.
        sub += (f' | recorte pelos {len(seg):,} de maior corrente, '
                f'{fora:,} omitidos — a cor deste desenho NAO e a distribuicao '
                f'da rede' + (f'; {nota_recorte}' if nota_recorte else ''))
        print(f'  {n0:,} trechos nao cabem numa folha — desenhando os '
              f'{len(seg):,} de maior corrente'
              + (f'  ({nota_recorte})' if nota_recorte else ''))
    fig, ax = plt.subplots(figsize=(15, 11), dpi=140)
    sm = _colecoes(ax, seg, val, lar, cmap, norm, lw_max)
    cb = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label(rotulo_cb)
    _fundo(ax, titulo, sub)
    ax.set_xlabel('longitude'); ax.set_ylabel('latitude')
    ax.grid(alpha=0.15, lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}  ({len(seg):,} trechos)')


def g_circuito(co, tre, saida, titulo, chave='carreg'):
    """O 'circuit plot': tracado real, espessura pela corrente."""
    seg, val, lar = [], [], []
    for t in tre:
        if t['b1'] in co and t['b2'] in co:
            seg.append([co[t['b1']], co[t['b2']]])
            v = t[chave]
            val.append(0.0 if not np.isfinite(v) else v)
            lar.append(t['i'])
    c = [t[chave] for t in tre if np.isfinite(t[chave])]
    nota = (f'no conjunto inteiro, {100*sum(1 for x in c if x > 100)/len(c):.2f}% '
            f'dos trechos passam da ampacidade' if c and chave == 'carreg' else '')
    _tracado(seg, val, lar, saida, titulo,
             'espessura proporcional a corrente | coordenadas SIRGAS 2000 da BDGD',
             CMAP_CARGA, Normalize(0, 120), 'carregamento (% da ampacidade)',
             nota_recorte=nota)


def g_circuito_tensao(co, tre, vpu, saida, titulo):
    seg, val, lar = [], [], []
    for t in tre:
        if t['b1'] in co and t['b2'] in co and t['b2'] in vpu:
            seg.append([co[t['b1']], co[t['b2']]])
            val.append(vpu[t['b2']])
            lar.append(t['i'])
    _tracado(seg, val, lar, saida, titulo,
             f'vermelho = abaixo de {ADEQ[0]} pu (precaria/critica pelo Modulo 8)',
             CMAP_TENSAO, Normalize(0.90, 1.05), 'tensao (pu)', lw_max=2.6)


def g_perfil(rede, saida):
    """Tensao x distancia da fonte, por barra."""
    d, v = [], []
    for nome in rede.ckt.AllBusNames:
        b = rede.ckt.Buses(nome)
        pu = [x for x in b.puVmagAngle[0::2] if 0.01 < x < 3]
        if pu and b.Distance > 0:
            d.append(b.Distance); v.append(float(np.mean(pu)))
    if not d:
        return
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.scatter(d, v, s=2, alpha=0.25, color='#2166ac', edgecolors='none')
    ax.axhline(ADEQ[0], color='#e31a1c', lw=1, ls='--', label=f'{ADEQ[0]} pu — limite adequado')
    ax.axhline(ADEQ[1], color='#e31a1c', lw=1, ls='--')
    _fundo(ax, 'Perfil de tensao', 'cada ponto e uma barra; distancia eletrica da fonte')
    ax.set_xlabel('distancia (km)'); ax.set_ylabel('tensao (pu)')
    ax.legend(fontsize=8); ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}')


def g_hist_tensao(vpu, saida):
    v = np.array(list(vpu.values()))
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.hist(v, bins=90, color='#4292c6', edgecolor='white', lw=0.3)
    ax.axvspan(ADEQ[0], ADEQ[1], color='#41ab5d', alpha=0.12, label='faixa adequada (M8)')
    ax.axvline(ADEQ[0], color='#e31a1c', lw=1.2, ls='--')
    ax.axvline(ADEQ[1], color='#e31a1c', lw=1.2, ls='--')
    fora = 100 * float(((v < ADEQ[0]) | (v > ADEQ[1])).mean())
    _fundo(ax, 'Distribuicao das tensoes',
           f'{len(v):,} barras | {fora:.1f}% fora da faixa adequada')
    ax.set_xlabel('tensao (pu)'); ax.set_ylabel('barras')
    ax.legend(fontsize=8); ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}')


def g_carregamento(tre, saida):
    c = np.array([t['carreg'] for t in tre if np.isfinite(t['carreg'])])
    if not len(c):
        return
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.hist(np.clip(c, 0, 200), bins=100, color='#fd8d3c', edgecolor='white', lw=0.3)
    ax.axvline(100, color='#e31a1c', lw=1.4, ls='--', label='ampacidade nominal')
    _fundo(ax, 'Carregamento dos trechos',
           f'{len(c):,} trechos | {100*float((c>100).mean()):.2f}% acima da nominal')
    ax.set_xlabel('carregamento (%)'); ax.set_ylabel('trechos')
    ax.set_yscale('log'); ax.legend(fontsize=8); ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}')


def g_perdas(med, saida, n=30):
    m = [x for x in med if x['kWh'] > 0]
    if not m:
        print('  (sem EnergyMeter — pule se o modelo e por subestacao antiga)')
        return
    for x in m:
        x['pct'] = 100 * x['perdas_kWh'] / x['kWh'] if x['kWh'] else 0
    m.sort(key=lambda x: -x['pct'])
    top = m[:n]
    fig, ax = plt.subplots(figsize=(11, max(5, 0.28 * len(top))), dpi=140)
    ax.barh([x['alimentador'] for x in top][::-1], [x['pct'] for x in top][::-1],
            color='#41ab5d')
    _fundo(ax, f'Perdas por alimentador — {n} maiores',
           'perdas de zona do EnergyMeter, em % da energia entregue')
    ax.set_xlabel('perdas (%)'); ax.grid(alpha=0.25, axis='x', lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}')


def g_fontes(fon, saida, n=30):
    f = sorted([x for x in fon if x['MW'] > 0.01], key=lambda x: -x['MW'])[:n]
    if not f:
        return
    fig, ax = plt.subplots(figsize=(11, max(5, 0.28 * len(f))), dpi=140)
    rot = [x['nome'].split('.')[-1].replace('fonte_', '').upper() for x in f]
    ax.barh(rot[::-1], [x['MW'] for x in f][::-1], color='#2166ac')
    _fundo(ax, f'Potencia injetada por ponto de conexao — {len(f)} maiores',
           'cada barra e uma fonte de patio de AT')
    ax.set_xlabel('MW'); ax.grid(alpha=0.25, axis='x', lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}')


def _gd_agora(rede):
    """Potencia ativa que os PVSystem estao injetando no instante corrente."""
    gd = 0.0
    i = rede.ckt.PVSystems.First
    while i:
        rede.ckt.SetActiveElement('PVSystem.' + rede.ckt.PVSystems.Name)
        el = rede.ckt.ActiveCktElement
        pw = list(el.Powers)[0::2]
        gd += -sum(pw[:el.NumPhases])
        i = rede.ckt.PVSystems.Next
    return gd


def g_diario(rede, saida, passos=96):
    """Carga, geracao e potencia da fonte ao longo do dia.

    PASSOS INDEPENDENTES, nao a sequencia do OpenDSS. Medido neste projeto: no
    modo daily cada passo parte da solucao do anterior, a trajetoria degrada e
    trava — a DABR no passo 72, a DPIP no 44 — e nao se recupera, embora CADA
    instante isolado convirja. Como perda e geracao sao funcao do ponto de
    operacao e nao do caminho ate ele, resolver cada instante do zero e
    legitimo e devolve a curva inteira. O `energia.py` ja fazia assim; esta
    funcao ainda usava a sequencia e por isso podia entregar meia curva sem
    avisar.
    """
    def prepara():
        rede.txt.Command = 'Set mode=daily'
        rede.txt.Command = 'Set stepsize=15m'
        rede.txt.Command = 'Set number=1'
        rede.txt.Command = 'Set controlmode=static'

    prepara()
    h_passo = 24.0 / passos
    p, q, g, falhos = [], [], [], 0
    for k in range(passos):
        t = k * h_passo
        for tentativa in (0, 1):
            rede.txt.Command = f'Set hour={int(t)}'
            rede.txt.Command = f'Set sec={int(round((t - int(t)) * 3600))}'
            rede.txt.Command = 'Solve'
            if rede.ckt.Solution.Converged:
                break
            if tentativa == 0:               # estado sujo: recomeca limpo
                rede.txt.Command = 'Clear'
                rede.txt.Command = f'Compile "{rede.master}"'
                prepara()
        tp = rede.ckt.TotalPower
        if not rede.ckt.Solution.Converged or np.isnan(tp[0]):
            falhos += 1
            p.append(np.nan); q.append(np.nan); g.append(np.nan)
            continue
        p.append(-tp[0] / 1000); q.append(-tp[1] / 1000)
        g.append(_gd_agora(rede) / 1000)

    h = np.arange(passos) * h_passo
    p, q, g = np.array(p), np.array(q), np.array(g)
    carga = p + g                              # a fonte ja desconta a GD
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.plot(h, carga, lw=2, color='#2166ac', label='carga + perdas (MW)')
    ax.plot(h, g, lw=2, color='#e8a33d', label='geração distribuída (MW)')
    ax.plot(h, p, lw=1.4, color='#41ab5d', label='vindo da fonte (MW)')
    ax.plot(h, q, lw=1.1, color='#fd8d3c', ls='--', label='reativa da fonte (Mvar)')
    ax.axhline(0, color='#999', lw=0.8)
    if np.nanmin(p) < 0:
        ax.fill_between(h, 0, np.minimum(p, 0), color='#e31a1c', alpha=0.18,
                        lw=0, label='fluxo reverso')
    sub = 'passos independentes de 15 min (CRVCRG e irradiância da BDGD)'
    if falhos:
        sub += f' | {falhos} passos nao convergiram'
    _fundo(ax, 'Curva diaria: carga, geracao e fonte', sub)
    ax.set_xlabel('hora'); ax.set_ylabel('potencia')
    ax.set_xticks(range(0, 25, 2)); ax.set_xlim(0, 24)
    ax.legend(fontsize=8); ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(saida); plt.close(fig)
    print(f'  -> {os.path.basename(saida)}'
          + (f'  ({falhos} passos falharam)' if falhos else ''))
    return [x for x in carga if not np.isnan(x)], g


# ======================================================================= main
def _painel():
    """Sem argumento, pergunta o que falta em vez de mostrar o usage."""
    import interativo
    v = interativo.formulario('analise_com', 'Análise da rede (OpenDSS COM)', [
        {'chave': 'master', 'tipo': 'arquivo', 'rotulo': 'Arquivo MASTER',
         'filtros': [('MASTER do OpenDSS', 'MASTER-*.dss'), ('Arquivo .dss', '*.dss')],
         'padrao': os.path.join(interativo.modelos_recentes(), 'MASTER-GERAL.dss'),
         'dica': 'MASTER-GERAL.dss para a concessão inteira, ou o MASTER-<SE>.dss '
                 'dentro da pasta de uma subestação'},
        {'chave': 'nivel', 'tipo': 'opcao', 'rotulo': 'Desenhar', 'padrao': 'tudo',
         'valores': ['tudo', 'at', 'mt'],
         'dica': 'no MASTER-GERAL use "at" — "tudo" são ~1,2 milhão de trechos '
                 'e o traçado satura'},
        {'chave': 'diario', 'tipo': 'bool', 'rotulo': 'Curva diária',
         'padrao': False, 'dica': 'resolve 24 h em passos de 15 min (bem mais demorado)'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Salvar figuras em',
         'padrao': '', 'dica': 'vazio = pasta "analise" ao lado do MASTER'},
    ], ajuda='Compila, resolve e gera os gráficos de diagnóstico: traçado '
             'geográfico, perfil e histograma de tensão, carregamento, perdas '
             'por alimentador.')
    if not v:
        return False
    sys.argv += [v['master'], '--nivel', v['nivel']]
    if v['saida']:
        sys.argv += ['--saida', v['saida']]
    if v['diario']:
        sys.argv.append('--diario')
    return True


def main():
    do_painel = len(sys.argv) == 1
    if do_painel and not _painel():
        return

    ap = argparse.ArgumentParser(description='Analise do modelo OpenDSS via COM.')
    ap.add_argument('master')
    ap.add_argument('--saida', default=None)
    ap.add_argument('--diario', action='store_true',
                    help='resolve 24 h em passos de 15 min (mais demorado)')
    ap.add_argument('--nivel', default='tudo', choices=['tudo', 'at', 'mt'],
                    help='o que desenhar no tracado geografico. No MASTER-GERAL '
                         'use "at" para ver a malha de 88 kV; "tudo" sao ~1,2 '
                         'milhao de trechos e o desenho satura')
    a = ap.parse_args()

    saida = a.saida or os.path.join(os.path.dirname(os.path.abspath(a.master)), 'analise')
    os.makedirs(saida, exist_ok=True)

    r = Rede(a.master)
    print('compilando...')
    r.compilar()
    print('resolvendo...')
    conv = r.resolver()

    tp = r.ckt.TotalPower
    perdas = r.ckt.Losses
    resumo = {
        'master': r.master,
        'convergiu': conv,
        'nos_nan': r.n_nan,
        'iteracoes': r.ckt.Solution.Iterations,
        'barras': r.ckt.NumBuses,
        'nos': r.ckt.NumNodes,
        'elementos': r.ckt.NumCktElements,
        'P_MW': round(-tp[0] / 1000, 3),
        'Q_Mvar': round(-tp[1] / 1000, 3),
        'perdas_MW': round(perdas[0] / 1e6, 4),
        'perdas_pct': round(100 * (perdas[0] / 1e6) / max(-tp[0] / 1000, 1e-9), 3),
    }

    print('extraindo...')
    co = r.coordenadas()
    vpu = r.tensoes_pu()
    tre = r.trechos(a.nivel)
    med = r.medidores()
    fon = r.fontes()
    resumo.update({'barras_com_coordenada': len(co), 'trechos': len(tre),
                   'medidores': len(med), 'fontes': len(fon)})
    v = np.array(list(vpu.values()))
    if len(v):
        resumo.update({
            'V_min_pu': round(float(v.min()), 4),
            'V_mediana_pu': round(float(np.median(v)), 4),
            'V_max_pu': round(float(v.max()), 4),
            'pct_fora_faixa': round(100 * float(((v < ADEQ[0]) | (v > ADEQ[1])).mean()), 2)})
    c = np.array([t['carreg'] for t in tre if np.isfinite(t['carreg'])])
    if len(c):
        resumo['pct_trechos_sobrecarga'] = round(100 * float((c > 100).mean()), 3)

    nome = os.path.splitext(os.path.basename(r.master))[0]
    print('graficos...')
    g_circuito(co, tre, os.path.join(saida, '01_circuito_geografico.png'),
               f'{nome} — tracado geografico por carregamento'
               + ('' if a.nivel == 'tudo' else f' (nivel {a.nivel.upper()})'))
    g_circuito_tensao(co, tre, vpu, os.path.join(saida, '02_tensao_geografica.png'),
                      f'{nome} — tracado geografico por tensao')
    g_perfil(r, os.path.join(saida, '03_perfil_tensao.png'))
    g_hist_tensao(vpu, os.path.join(saida, '04_histograma_tensao.png'))
    g_carregamento(tre, os.path.join(saida, '05_carregamento_linhas.png'))
    g_perdas(med, os.path.join(saida, '06_perdas_por_alimentador.png'))
    g_fontes(fon, os.path.join(saida, '07_potencia_por_fonte.png'))
    if a.diario:
        p, g = g_diario(r, os.path.join(saida, '08_curva_diaria.png'))
        if p:
            resumo['pico_MW'] = round(max(p), 2)
            resumo['fator_carga'] = round(sum(p) / len(p) / max(p), 3)
            gv = [x for x in g if not np.isnan(x)]
            if gv and max(gv) > 0:
                i = list(g).index(max(gv))
                resumo['pico_gd_MW'] = round(max(gv), 2)
                resumo['hora_pico_gd'] = round(i * 24 / len(g), 2)
                resumo['gd_no_pico_pct_carga'] = round(100 * g[i] / p[i], 2) \
                    if p[i] else None
                resumo['gd_MWh_dia'] = round(sum(gv) * 24 / len(g), 1)

    json.dump(resumo, open(os.path.join(saida, 'resumo.json'), 'w',
                           encoding='utf-8'), indent=1, ensure_ascii=False)
    if med:
        with open(os.path.join(saida, 'perdas_por_alimentador.csv'), 'w',
                  newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=list(med[0]), delimiter=';')
            w.writeheader(); w.writerows(med)

    print('\n================ RESUMO ================')
    for k, v2 in resumo.items():
        if k != 'master':
            print(f'  {k:26s} {v2}')
    print(f'\nfiguras e planilhas em: {saida}')
    if do_painel:
        # quem abriu pelo painel nao viu o caminho passar no terminal:
        # abre a pasta das figuras, que e o resultado que ele foi buscar
        import interativo
        interativo.abrir(saida)


if __name__ == '__main__':
    main()
