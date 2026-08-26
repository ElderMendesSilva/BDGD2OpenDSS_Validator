# -*- coding: utf-8 -*-
"""Colhe uma rodada e publica o que cabe no repositorio.

    python auditoria.py --sufixo V1_cluster
    python auditoria.py --sufixo V1_cluster --so CMIG SP

POR QUE ISTO EXISTE

`logs/` e `MODELOS*/` estao no `.gitignore`, e com razao: sao gigabytes e se
refazem a partir do `.gdb`. Mas a maquina que NAO alcanca o cluster fica sem
numero nenhum para auditar — ela le no diario que a Cemig viola 11,12% e nao
consegue perguntar QUAIS alimentadores.

Este programa le a rodada e escreve `resultados/<sufixo>/`, que **entra no
git**. Regra de entrada, e ela e o desenho todo: **cabe em kilobytes e nao se
refaz sem o cluster.**

O QUE SAI

    resultados/<sufixo>/_indice.json      as bases da rodada, o que faltou
    resultados/<sufixo>/<TAG>.json        uma linha por subestacao + o rollup
    resultados/<sufixo>/<TAG>_violacoes.csv   uma linha por alimentador que
                                              viola o limite fisico

O CSV e o que faz o trabalho em paralelo funcionar: e a tabela que alguem
abre, ordena por `pct_tecnica_modelo` e usa para escolher o pior caso — sem
ter o modelo na maquina. JSON para o resto, que e lido por codigo.

O QUE NAO SAI: nada por barra, nada por no, nenhum `.dss`, nenhuma curva. Se
um arquivo passa de `TETO_MB`, ele esta errado de granularidade e o programa
avisa em vez de gravar em silencio.

O CAMPO `motivo` DO CSV

Violacao nao e diagnostico. O `valida_balanco` ja separa `viola_limite` de
`viola_de_verdade` justamente porque medida degenerada produz violacao falsa.
Aqui a coluna `motivo` leva isso um passo adiante e diz, para cada linha, qual
das causas conhecidas se aplica — para que quem abrir o CSV nao gaste a
primeira hora redescobrindo que metade das linhas tem denominador minusculo.
"""
import argparse
import csv
import glob
import json
import os
import sys

TETO_MB = 1.0            # arquivo maior que isto esta errado de granularidade

# Limiares do campo `motivo`, MEDIDOS sobre as 77 violacoes reais da V19 nas
# sete bases — e nao escolhidos por parecerem redondos:
#
#     modelo %        min 2,23   p25  9,24   mediana 12,29   p75 24,15   max 236,78
#     medido %        min 2,07   p25  5,62   mediana  9,51   p75 12,65   max  65,09
#     modelo/medido   min 1,00   p25  1,07   mediana  1,34   p75  2,16   max  11,40
#     GWh injetado    min 1,20                                           max  73,13
NO_LIMITE = 1.2          # modelo/medido ate aqui: passou raspando, 32 das 77
MODELO_ABSURDO = 15.0    # perda tecnica modelada acima disto, 31 das 77
MEDIDA_SEM_PERDA = 3.0   # total medido abaixo disto, 11 das 77
GWH_MINUSCULO = 0.5      # denominador pequeno faz qualquer perda virar %

# As colunas do CSV, nesta ordem. Explicita e nao derivada do dicionario:
# ordem estavel e o que permite comparar dois CSV de rodadas diferentes com
# `diff`, e um dicionario reordenado por acaso destruiria isso.
COLUNAS = [
    'base', 'sub', 'ctmt', 'motivo',
    'pct_tecnica_modelo', 'pct_total_medido', 'pct_nao_tecnica_implicita',
    'GWh_injetado', 'GWh_faturado', 'ucs', 'cobertura',
    'viola_limite', 'medida_degenerada', 'faturado_maior_que_injetado',
    'declarado_pct', 'razao_vs_declarado',
    'se_kv_mt', 'se_trafos', 'se_km_MT', 'se_alimentadores',
    'se_convergiu', 'se_nos_nan', 'se_veredicto',
]


def _le(caminho):
    """JSON que pode nao existir. Rodada interrompida e o caso normal aqui."""
    try:
        with open(caminho, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def _por_chave(lista, chave):
    if not isinstance(lista, list):
        return {}
    return {str(x.get(chave)): x for x in lista if isinstance(x, dict)}


def motivo_da_violacao(v):
    """Por que esta linha aparece — a causa conhecida, ou 'a investigar'.

    OS TRES PRIMEIROS RAMOS SAO DEFENSIVOS, e e importante saber disso: quando
    a funcao recebe so as linhas com `viola_de_verdade`, que e o uso normal,
    eles NAO disparam nunca. O `valida_balanco` ja define
    `viola_de_verdade = viola_limite and not degenerada and not
    faturado_maior_que_injetado`, e nas 77 violacoes da V19 o menor GWh
    injetado e 1,20 — nenhuma perto de zero. Eles ficam porque a funcao tambem
    serve para varrer a tabela INTEIRA, onde os tres casos existem e sao a
    maioria do ruido.

    A ORDEM DOS DOIS SEGUINTES FOI ESCOLHIDA, e vale dizer por que. Uma linha
    pode ser ao mesmo tempo `modelo > 15%` e `razao < 1,2` — por exemplo modelo
    20% contra medido 18%. Nesse caso o que manda e a RAZAO: um modelo que fica
    a 11% do total medido nao esta errado, esta descrevendo um alimentador que
    perde muito de verdade. Classificar isso como perda absurda mandaria
    alguem caçar defeito onde ha so um alimentador ruim.

    `a investigar` e o rotulo que se quer POUCO. Sao esses que valem a hora de
    quem abre o CSV.
    """
    if v.get('faturado_maior_que_injetado'):
        return 'medida invertida: faturado > injetado'
    if v.get('medida_degenerada'):
        return 'medida degenerada'
    inj = _num(v.get('GWh_injetado'))
    if inj is not None and inj < GWH_MINUSCULO:
        return f'denominador minusculo: {inj:.3f} GWh injetados'

    mod, med = _num(v.get('pct_tecnica_modelo')), _num(v.get('pct_total_medido'))
    if mod is not None and med is not None and med > 0:
        if mod / med < NO_LIMITE:
            return f'no limite: modelo {mod / med:.2f}x o total medido'
        if med < MEDIDA_SEM_PERDA:
            return f'medida quase sem perda: {med:.2f}% total medido'
    if mod is not None and mod > MODELO_ABSURDO:
        return f'perda modelada absurda: {mod:.1f}%'
    return 'a investigar'


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def colher_base(pasta, base):
    """Le UMA pasta de modelo e devolve (resumo, linhas_de_violacao)."""
    bal = _le(os.path.join(pasta, 'validacao_balanco.json')) or []
    val = _por_chave(_le(os.path.join(pasta, 'validacao.json')) or [], 'modelo')
    ver = _por_chave(_le(os.path.join(pasta, 'verificacao.json')) or [], 'se')
    ger = _por_chave(_le(os.path.join(pasta, 'resumo_geral.json')) or [], 'SE')
    lig = _le(os.path.join(pasta, 'ligacao.json')) or {}
    per = _le(os.path.join(pasta, 'validacao_perdas.json')) or {}
    rede = _le(os.path.join(pasta, 'relatorio_rede.json')) or {}
    proc = _le(os.path.join(pasta, '_procedencia.json')) or {}

    decl = _por_chave(per.get('alimentadores') or [], 'ctmt')

    # ---------------------------------------------------------- por subestacao
    ses = []
    for se in sorted(set(val) | set(ver) | set(ger)):
        v, w, g = val.get(se, {}), ver.get(se, {}), ger.get(se, {})
        capi = w.get('capi') or {}
        ses.append({
            'se': se,
            'veredicto': w.get('veredicto'),
            'convergiu': v.get('converge', capi.get('convergiu')),
            'iteracoes': v.get('iteracoes', capi.get('iteracoes')),
            'nos_nan': v.get('nos_nan', capi.get('nan_nos')),
            'perdas_pct': v.get('perdas_pct'),
            'V_MT_min': v.get('V_MT_min'),
            'cargas_sem_tensao': v.get('cargas_sem_tensao'),
            'ramos_isolados': v.get('ramos_isolados'),
            'causa': v.get('causa'),
            'alimentadores': g.get('alimentadores'),
            'trafos': g.get('trafos'),
            'km_MT': g.get('km_MT'),
            'chaves_ilhadas': g.get('chaves_ilhadas'),
            'reguladores_pendurados': g.get('reguladores_pendurados'),
            'trafos_pac_invertido': g.get('trafos_pac_invertido'),
        })

    def _soma(campo):
        return sum(x.get(campo) or 0 for x in ses)

    # ------------------------------------------------------------- violacoes
    linhas = []
    for v in bal:
        if not isinstance(v, dict) or not v.get('viola_de_verdade'):
            continue
        sub = str(v.get('sub'))
        g, vv, w = ger.get(sub, {}), val.get(sub, {}), ver.get(sub, {})
        d = decl.get(str(v.get('ctmt')), {})
        linhas.append({
            'base': base, 'sub': sub, 'ctmt': v.get('ctmt'),
            'motivo': motivo_da_violacao(v),
            'pct_tecnica_modelo': v.get('pct_tecnica_modelo'),
            'pct_total_medido': v.get('pct_total_medido'),
            'pct_nao_tecnica_implicita': v.get('pct_nao_tecnica_implicita'),
            'GWh_injetado': v.get('GWh_injetado'),
            'GWh_faturado': v.get('GWh_faturado'),
            'ucs': v.get('ucs'), 'cobertura': v.get('cobertura'),
            'viola_limite': v.get('viola_limite'),
            'medida_degenerada': v.get('medida_degenerada'),
            'faturado_maior_que_injetado': v.get('faturado_maior_que_injetado'),
            'declarado_pct': d.get('declarado_pct'),
            'razao_vs_declarado': d.get('razao'),
            'se_kv_mt': g.get('kv_mt'), 'se_trafos': g.get('trafos'),
            'se_km_MT': g.get('km_MT'),
            'se_alimentadores': g.get('alimentadores'),
            'se_convergiu': vv.get('converge'),
            'se_nos_nan': vv.get('nos_nan'),
            'se_veredicto': w.get('veredicto'),
        })
    # Maior perda modelada primeiro: quem abre o CSV quer o pior caso na
    # primeira linha, e nao a ordem em que a rodada calhou de gravar.
    linhas.sort(key=lambda x: -(x.get('pct_tecnica_modelo') or 0))

    subs_lig = (lig.get('subestacoes') or []) if isinstance(lig, dict) else []
    resumo = {
        'base': base,
        'pasta': os.path.basename(pasta),
        'procedencia': proc,
        'bdgd': rede.get('gdb'), 'dist': rede.get('dist'),
        'bt': rede.get('bt'), 'mes': rede.get('mes'), 'dia': rede.get('dia'),
        'subestacoes_na_bdgd': rede.get('subestacoes_na_bdgd'),
        'subestacoes_geradas': rede.get('subestacoes_geradas'),
        'alimentadores': rede.get('alimentadores'),
        'rollup': {
            'ses': len(ses),
            'sadias': sum(1 for x in ses if x.get('veredicto') == 'OK'),
            'nao_convergiu': sum(1 for x in ses if x.get('convergiu') is False),
            'com_nan': sum(1 for x in ses if (x.get('nos_nan') or 0) > 0),
            'trafos': _soma('trafos'),
            'km_MT': round(_soma('km_MT'), 1),
            'chaves_ilhadas': _soma('chaves_ilhadas'),
            'reguladores_pendurados': _soma('reguladores_pendurados'),
            'trafos_pac_invertido': _soma('trafos_pac_invertido'),
            'kW_morto': round(sum(x.get('kW_morto') or 0 for x in subs_lig), 1),
            'kW_nominal': round(sum(x.get('kW_nominal') or 0
                                    for x in subs_lig), 1),
        },
        'perdas': {
            'agregado': per.get('agregado'),
            'referencia_externa': per.get('referencia_externa'),
            'populacao': per.get('populacao'),
            'modelo_implausivel': per.get('modelo_implausivel'),
            'parcelas': per.get('parcelas'),
        },
        'balanco': {
            'alimentadores': len(bal),
            'viola_de_verdade': len(linhas),
            'pct_viola': (round(100.0 * len(linhas) / len(bal), 2)
                          if bal else None),
            'por_motivo': _conta_motivos(linhas),
        },
        'tabelas_nao_lidas': rede.get('tabelas_nao_lidas'),
        'subestacoes': ses,
    }
    return resumo, linhas


def _conta_motivos(linhas):
    """Conta por CLASSE de motivo, e nao pelo texto com o numero dentro.

    `denominador minusculo: 0,003 GWh` e `... 0,014 GWh` sao o mesmo motivo; se
    a contagem fosse pelo texto inteiro, cada linha viraria sua propria
    categoria e o resumo nao resumiria nada.
    """
    c = {}
    for x in linhas:
        k = str(x.get('motivo', '')).split(':')[0]
        c[k] = c.get(k, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def _grava_json(caminho, dado, avisos):
    txt = json.dumps(dado, ensure_ascii=False, indent=1)
    with open(caminho, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt + '\n')
    mb = len(txt.encode('utf-8')) / 1e6
    if mb > TETO_MB:
        avisos.append(f'{os.path.basename(caminho)}: {mb:.1f} MB, acima do '
                      f'teto de {TETO_MB} MB — granularidade errada')
    return mb


def _grava_csv(caminho, linhas, avisos):
    # newline='' e exigencia do csv no Windows; sem ele sai uma linha em
    # branco entre cada registro e o `diff` entre rodadas fica ilegivel.
    with open(caminho, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS, extrasaction='ignore')
        w.writeheader()
        w.writerows(linhas)
    mb = os.path.getsize(caminho) / 1e6
    if mb > TETO_MB:
        avisos.append(f'{os.path.basename(caminho)}: {mb:.1f} MB, acima do '
                      f'teto de {TETO_MB} MB')
    return mb


def pastas_da_rodada(sufixo, raiz='.'):
    """`MODELOS_<TAG>_<SUFIXO>` -> [(TAG, caminho)], em ordem.

    A ANCORA E O SUFIXO, e nao um regex que tenta adivinhar onde a TAG acaba.
    Um `MODELOS_(.+?)_(.+)$` nao-guloso le `MODELOS_EQ_PA_V1_cluster` como
    TAG=`EQ` e sufixo=`PA_V1_cluster`, e a base some da colheita em silencio.
    Como o sufixo e dado pelo chamador, casar o FIM do nome resolve, e de
    quebra impede que `V1` arraste `V19` — duas rodadas viram uma, e essa e
    pior que sumir.

    Sem diferenciar maiuscula porque a rodada do cluster grava `V1_cluster` e o
    `resumo_v1_cluster.json` ja usa minuscula.
    """
    achadas = []
    fim = '_' + sufixo.lower()
    for p in sorted(glob.glob(os.path.join(raiz, 'MODELOS_*'))):
        if not os.path.isdir(p):
            continue
        nome = os.path.basename(p)
        if not nome.lower().endswith(fim):
            continue
        tag = nome[len('MODELOS_'):len(nome) - len(fim)]
        if tag:
            achadas.append((tag, p))
    return achadas


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Colhe uma rodada e publica resultados/<sufixo>/ '
                    '— o que cabe no repositorio e nao se refaz sem o cluster.')
    ap.add_argument('--sufixo', required=True,
                    help='o sufixo da rodada, ex.: V1_cluster')
    ap.add_argument('--saida', default='resultados',
                    help='pasta de saida (padrao: resultados)')
    ap.add_argument('--so', nargs='*', metavar='TAG',
                    help='so estas bases')
    ap.add_argument('--raiz', default='.', help='onde procurar MODELOS_*')
    a = ap.parse_args(argv)

    pastas = pastas_da_rodada(a.sufixo, a.raiz)
    if a.so:
        querid = {s.upper() for s in a.so}
        pastas = [(t, p) for t, p in pastas if t.upper() in querid]
    if not pastas:
        print(f'nenhuma pasta MODELOS_*_{a.sufixo} em {os.path.abspath(a.raiz)}')
        return 1

    destino = os.path.join(a.saida, a.sufixo.lower())
    os.makedirs(destino, exist_ok=True)
    avisos, indice, total_mb = [], [], 0.0

    print(f'{"base":<8}{"SEs":>6}{"sadias":>8}{"nao conv":>10}'
          f'{"viola":>8}{"%viola":>8}{"KB":>8}')
    for tag, pasta in pastas:
        resumo, linhas = colher_base(pasta, tag)
        mb = _grava_json(os.path.join(destino, f'{tag}.json'), resumo, avisos)
        mb += _grava_csv(os.path.join(destino, f'{tag}_violacoes.csv'),
                         linhas, avisos)
        total_mb += mb
        r, b = resumo['rollup'], resumo['balanco']
        indice.append({
            'base': tag, 'pasta': resumo['pasta'],
            'ses': r['ses'], 'sadias': r['sadias'],
            'nao_convergiu': r['nao_convergiu'], 'com_nan': r['com_nan'],
            'viola_de_verdade': b['viola_de_verdade'],
            'pct_viola': b['pct_viola'],
            'perda_modelo_pct': (resumo['perdas'].get('agregado') or {})
                                .get('pct_modelo'),
            'reprova_ancora': (resumo['perdas'].get('referencia_externa') or {})
                              .get('reprova'),
            'commit': (resumo['procedencia'] or {}).get('commit'),
        })
        print(f'{tag:<8}{r["ses"]:6,}{r["sadias"]:8,}{r["nao_convergiu"]:10,}'
              f'{b["viola_de_verdade"]:8,}'
              f'{(b["pct_viola"] if b["pct_viola"] is not None else 0):7.2f}%'
              f'{mb*1000:8.0f}')

    _grava_json(os.path.join(destino, '_indice.json'),
                {'sufixo': a.sufixo, 'bases': indice}, avisos)

    print(f'\n{len(pastas)} bases em {destino}/  ({total_mb*1000:.0f} KB)')
    for x in avisos:
        print(f'  AVISO {x}')
    print('\nO CSV de violacoes e a tabela para trabalhar sem o modelo: '
          'ordene por pct_tecnica_modelo e olhe as linhas com motivo '
          '"a investigar".')
    return 0


if __name__ == '__main__':
    sys.exit(main())
