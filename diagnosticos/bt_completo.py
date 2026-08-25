# -*- coding: utf-8 -*-
"""O achado 45 ainda vale? Mede `--bt completo` contra `--bt agregado`, por base.

    python diagnosticos/bt_completo.py --bases $BDGD2DSS_BASES
    python diagnosticos/bt_completo.py --bases /d/BDGDs --so Roraima,Enel_CE
    python diagnosticos/bt_completo.py --bases /d/BDGDs --se-de "39=IPU,370=5003532"

O QUE ELE RESPONDE. O achado 45 registra `--bt completo` como QUEBRADO, com
93,5% das cargas sem tensao na Enel CE, 36,5% na Roraima e Vmin de 0,1023 pu na
Equatorial PA — e o criterio 5 do `PLANO_V1.md` (peso 8) esta parado nisso.

Em 25/08/2026 a Roraima foi remedida num laptop e **nao reproduziu**: 2 cargas
mortas de 3.617, contra as 1.292 registradas. O provavel motivo e o achado 51
(ilha de BT sem secundario), que e POSTERIOR ao 45 e atacou exatamente isso.

Uma base nao decide. Este script mede as tres do achado 45 e quantas mais
couberem, para dizer se ha conserto a fazer ou se o achado 45 virou historico.

AS DUAS ARMADILHAS DE MEDICAO, e as duas custaram uma leitura errada aqui:

1. **Limiar em volts nao serve.** A BT e 120 V; uma carga a 0,01 pu tem 1,2 V e
   passa em qualquer teste de "maior que 1 V". Carga morta aqui e fracao da
   tensao NOMINAL DELA MESMA, e nao um numero absoluto.

2. **`AllBusMagPu()` inclui o no 4.** O neutro fica em ~0,008 pu porque e isso
   que um neutro faz. O modo completo cria no 4 em toda barra de BT, entao ele
   sozinho responde por 22.833 dos 22.854 nos abaixo de 0,5 pu num modelo
   SADIO. Quem contar o neutro ve 89% de colapso onde nao ha nenhum. Aqui as
   estatisticas de tensao usam **so os nos 1, 2 e 3**.

A subestacao medida e a MEDIANA em numero de alimentadores, e nao a maior nem a
primeira: a maior exagera o efeito e a primeira e sorteio. `--se-de` permite
fixar a mesma que o achado 45 usou, para a comparacao ser do mesmo objeto.
"""
import argparse
import collections
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

PY = sys.executable


def subestacao_mediana(gdb):
    """A subestacao do meio em numero de alimentadores. Determinista."""
    from bdgd2dss.leitor import BDGD
    from bdgd2dss.leitor import txt
    col = BDGD(gdb, verbose=False).ler('CTMT', ['SUB'])
    conta = collections.Counter(txt(s) for s in col['SUB'] if txt(s))
    if not conta:
        return None
    # ordena por (alimentadores, nome) para nao depender da ordem do dicionario
    ordenado = sorted(conta.items(), key=lambda kv: (kv[1], kv[0]))
    return ordenado[len(ordenado) // 2][0]


def converte(gdb, saida, se, modo, limite):
    cmd = [PY, '-u', os.path.join(RAIZ, 'converter.py'), gdb,
           '--saida', saida, '--se', se, '--bt', modo, '--refazer']
    t0 = time.time()
    # `stderr` JUNTO, e nao separado. Com `capture_output` e so `p.stdout`, um
    # SyntaxError no import — que e o unico lugar onde ele aparece — some, e o
    # relatorio diz "NAO CONVERTEU" sem uma linha de motivo. Foi o que
    # aconteceu no job 34037: sete bases falharam e o log saiu em branco.
    p = subprocess.run(cmd, cwd=RAIZ, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=limite)
    return p.returncode == 0, round(time.time() - t0, 1), p.stdout[-800:]


def resolve(master):
    """Resolve e mede. Devolve None se nem compilar."""
    import opendssdirect as dss
    dss.Text.Command('Clear')
    dss.Text.Command('Redirect "%s"' % master)
    if dss.Error.Number():
        return None
    dss.Text.Command('Solve')

    nomes = dss.Circuit.AllNodeNames()
    pu = dss.Circuit.AllBusMagPu()
    nan = sum(1 for v in pu if math.isnan(v))
    # SO AS FASES. Ver a armadilha 2 no cabecalho.
    fases = [v for nm, v in zip(nomes, pu)
             if nm.rsplit('.', 1)[-1] in ('1', '2', '3') and not math.isnan(v)]
    if not fases:
        return None

    mortas = 0
    for nm in dss.Loads.AllNames():
        dss.Circuit.SetActiveElement('Load.' + nm)
        vs = dss.CktElement.VoltagesMagAng()
        dss.Loads.Name(nm)
        base = dss.Loads.kV() * 1000.0
        if vs and base > 0 and vs[0] / base < 0.5:
            mortas += 1

    p = dss.Circuit.TotalPower()
    perdas = dss.Circuit.Losses()
    kw = -p[0]
    return {
        'convergiu': bool(dss.Solution.Converged()),
        'barras': dss.Circuit.NumBuses(),
        'cargas': dss.Loads.Count(),
        'mortas': mortas,
        'pct_mortas': round(100.0 * mortas / max(1, dss.Loads.Count()), 2),
        'nan': nan,
        'vmin': round(min(fases), 4),
        'vmed': round(sum(fases) / len(fases), 4),
        'pct_sub90': round(100.0 * sum(1 for v in fases if v < 0.90) / len(fases), 1),
        'kw': round(kw, 1),
        'pct_perdas': round(100.0 * perdas[0] / 1000.0 / kw, 2) if kw > 0 else None,
    }


def uma_base(gdb, se, trabalho, limite):
    nome = os.path.basename(gdb)
    reg = {'base': nome, 'se': se}
    caches = []
    for modo in ('agregado', 'completo'):
        saida = os.path.join(trabalho, '%s_%s' % (nome[:24], modo))
        # O cache da UCBT (milhoes de linhas) e por pasta de saida. Copiar o do
        # agregado evita pagar a mesma agregacao duas vezes — ela nao depende
        # do modo, so da base e do mes.
        if caches and not glob.glob(os.path.join(saida, '_cache_ucbt*')):
            os.makedirs(saida, exist_ok=True)
            for c in caches:
                shutil.copy2(c, os.path.join(saida, os.path.basename(c)))
        ok, seg, cauda = converte(gdb, saida, se, modo, limite)
        reg[modo] = {'converteu': ok, 'seg': seg}
        if not ok:
            reg[modo]['cauda'] = cauda
            continue
        caches = glob.glob(os.path.join(saida, '_cache_ucbt*')) or caches
        master = os.path.join(saida, se, 'MASTER-%s.dss' % se)
        if not os.path.exists(master):
            reg[modo]['erro'] = 'MASTER nao gerado'
            continue
        m = resolve(os.path.abspath(master))
        if m is None:
            reg[modo]['erro'] = 'nao compilou ou sem tensao'
        else:
            reg[modo].update(m)
    return reg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', 'bdgds'))
    ap.add_argument('--so', help='prefixos das .gdb, separados por virgula')
    ap.add_argument('--se-de', default='',
                    help='fixa a subestacao por codigo de agente: "39=IPU,370=5003532"')
    ap.add_argument('--trabalho', default='DIAG_BT')
    ap.add_argument('--limite', type=float, default=5400,
                    help='teto por conversao, em segundos (padrao 90 min)')
    ap.add_argument('--saida-json', default='medicoes/bt_completo.json')
    a = ap.parse_args(argv)

    gdbs = []
    for d in a.bases.split(os.pathsep):
        gdbs += sorted(glob.glob(os.path.join(os.path.expanduser(d), '*.gdb')))
    if a.so:
        # A ORDEM DO `--so` E RESPEITADA, e nao a alfabetica. Num job com teto de
        # tempo, a base que interessa nao pode ficar atras da Cemig-D — que e a
        # mais lenta e, por acaso do alfabeto, viria em segundo.
        pref = [p.strip() for p in a.so.split(',') if p.strip()]
        ordenado = []
        for p in pref:
            ordenado += [g for g in gdbs
                         if os.path.basename(g).startswith(p) and g not in ordenado]
        gdbs = ordenado
    if not gdbs:
        print('nenhuma .gdb em %s' % a.bases)
        return 1

    fixas = {}
    for par in a.se_de.split(','):
        if '=' in par:
            k, v = par.split('=', 1)
            fixas[k.strip()] = v.strip()

    print('%d bases; trabalho em %s\n' % (len(gdbs), a.trabalho))
    os.makedirs(a.trabalho, exist_ok=True)

    saida = []
    for g in gdbs:
        nome = os.path.basename(g)
        # <Nome>_<codigo>_<safra>_... — o codigo do agente e o campo antes da safra
        partes = nome[:-4].split('_')
        cod = next((partes[i - 1] for i, p in enumerate(partes)
                    if len(p) == 10 and p[4] == '-'), '')
        se = fixas.get(cod)
        if not se:
            try:
                se = subestacao_mediana(g)
            except Exception as e:                               # noqa: BLE001
                print('  %s: nao consegui listar subestacoes (%s)' % (nome[:40], e))
                continue
        if not se:
            continue
        print('--- %s  (agente %s, SE %s)' % (nome[:46], cod or '?', se), flush=True)
        try:
            reg = uma_base(g, se, a.trabalho, a.limite)
        except subprocess.TimeoutExpired:
            reg = {'base': nome, 'se': se, 'erro': 'estourou %ss' % a.limite}
        saida.append(reg)
        for modo in ('agregado', 'completo'):
            d = reg.get(modo, {})
            if 'pct_mortas' in d:
                print('    %-9s cargas %6d  mortas %5d (%5.2f%%)  Vmed %.4f  '
                      'NaN %d  perdas %s%%'
                      % (modo, d['cargas'], d['mortas'], d['pct_mortas'],
                         d['vmed'], d['nan'], d['pct_perdas']), flush=True)
            else:
                print('    %-9s %s' % (modo, d.get('erro') or d.get('cauda', 'sem medida')[-120:]),
                      flush=True)
        print(flush=True)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8') as f:
        json.dump({'medido_em': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'bases': saida}, f, ensure_ascii=False, indent=1)

    print('=' * 78)
    print('%-30s %8s %8s %8s %8s' % ('base', 'mortas%', 'Vmed', 'perdas%', 'veredito'))
    print('=' * 78)
    for r in saida:
        ag, cp = r.get('agregado', {}), r.get('completo', {})
        if 'pct_mortas' not in cp:
            print('%-30s %8s %8s %8s %8s'
                  % (r['base'][:30], '-', '-', '-', 'NAO CONVERTEU'))
            continue
        # o achado 45 chamava de quebrado o modo com dezenas de % de carga morta
        vered = 'QUEBRADO' if cp['pct_mortas'] >= 5.0 or cp['nan'] else 'ok'
        print('%-30s %7.2f%% %8.4f %7s%% %8s'
              % (r['base'][:30], cp['pct_mortas'], cp['vmed'],
                 cp['pct_perdas'], vered))
        print('%-30s %7.2f%% %8.4f %7s%%   (agregado, para comparar)'
              % ('', ag.get('pct_mortas', -1), ag.get('vmed', 0), ag.get('pct_perdas')))
    print('\njson: %s' % a.saida_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
