# -*- coding: utf-8 -*-
"""O que distingue os alimentadores que violam, em QUALQUER base?

    python diagnosticos/perfil_violacao.py --bases $BDGD2DSS_BASES \
        --resultados resultados/v22 --so COPELDIS2866
    python diagnosticos/perfil_violacao.py --bases /d/BDGDs \
        --resultados resultados/v24 --so COPELDIS2866 --motivo "perda modelada absurda"

Generaliza o `perfil_458.py`, que respondeu isso para a Enel SP com caminho e
base fixos no codigo. A catalogacao da V22 mostrou que o problema nao e so da
Enel SP: sao 258 violacoes sem sinal de topologia de SE, espalhadas por 24
bases, e 16 delas em COPELDIS2866 com perda de 15,8% a 10.309.528,9% em SE
convergida e sem defeito declarado.

O METODO E O MESMO, e vale repetir por que: nao chuta causa. Separa os
alimentadores suspeitos dos demais DENTRO DA MESMA BASE e compara os dois
grupos em atributos MEDIVEIS da propria BDGD. Se nenhum atributo separa, isso
tambem e resultado — significa que a causa nao esta nos atributos lidos aqui,
e o proximo passo e topologia por barra, nao mais estatistica de alimentador.

COMPARAR DENTRO DA BASE E O PONTO. Entre bases, tudo difere: condutor, porte,
criterio de cadastro. So a comparacao interna isola o que e do alimentador.

Sai `medicoes/perfil_violacao_<BASE>.json` e imprime a tabela.
"""
import argparse
import collections
import csv
import glob
import json
import os
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss.leitor import BDGD, num, txt          # noqa: E402


def suspeitos_do_csv(pasta_resultados, base, motivo=None):
    """Os CTMT que violam naquela base, opcionalmente so de um `motivo`.

    Le o CSV publicado pelo coletor — nao o modelo. E o que permite rodar isto
    na maquina que tem a `.gdb` sem ter a rodada inteira.
    """
    caminho = os.path.join(pasta_resultados, f'{base}_violacoes.csv')
    if not os.path.exists(caminho):
        raise SystemExit(f'nao achei {caminho}')
    fora_de_escopo = 0
    alvo = set()
    with open(caminho, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            # Modelo ja marcado quebrado nao entra: e sintoma de outro defeito,
            # ja detectado, e poluiria a comparacao com numero sem sentido.
            if (r.get('se_veredicto') or 'OK') not in ('OK', ''):
                fora_de_escopo += 1
                continue
            if motivo and not r['motivo'].startswith(motivo):
                continue
            alvo.add(r['ctmt'].strip().upper())
    return alvo, fora_de_escopo


def atributos(gdb, passo=700_000):
    """km, condutor, trafo e kVA por CTMT — tudo da propria BDGD."""
    b = BDGD(gdb, verbose=False)

    print('  lendo SSDMT...', flush=True)
    km = collections.defaultdict(float)
    cnd = collections.defaultdict(collections.Counter)
    s = b.ler('SSDMT', ['CTMT', 'COMP', 'TIP_CND'])
    for i in range(len(s['CTMT'])):
        c = txt(s['CTMT'][i]).strip().upper()
        L = num(s['COMP'][i]) / 1000.0
        km[c] += L
        cnd[c][txt(s['TIP_CND'][i]).strip()] += L

    print('  lendo SEGCON...', flush=True)
    sc = b.ler('SEGCON', ['COD_ID', 'R1', 'CNOM'])
    r1 = {txt(sc['COD_ID'][i]).strip(): num(sc['R1'][i])
          for i in range(len(sc['COD_ID']))}
    cnom = {txt(sc['COD_ID'][i]).strip(): num(sc['CNOM'][i])
            for i in range(len(sc['COD_ID']))}

    print('  lendo UNTRMT...', flush=True)
    kva = collections.defaultdict(float)
    ntr = collections.Counter()
    t = b.ler('UNTRMT', ['CTMT', 'POT_NOM'])
    for i in range(len(t['CTMT'])):
        c = txt(t['CTMT'][i]).strip().upper()
        kva[c] += num(t['POT_NOM'][i])
        ntr[c] += 1

    return {'km': km, 'cnd': cnd, 'r1': r1, 'cnom': cnom,
            'kva': kva, 'ntr': ntr}


def _ponderado(cnd_do_ctmt, tabela, padrao):
    """Media do atributo do condutor, ponderada pelo km que o usa."""
    tot = sum(cnd_do_ctmt.values())
    if not tot:
        return None
    return sum(tabela.get(k, padrao) * v
               for k, v in cnd_do_ctmt.items()) / tot


def perfil(cods, at):
    """Mediana de cada atributo no grupo. Mediana e nao media: um alimentador
    com 10 milhoes por cento levaria qualquer media junto."""
    def m(f):
        v = [f(c) for c in cods if f(c) is not None]
        return statistics.median(v) if v else None
    return {
        'n': len(cods),
        'km': m(lambda c: at['km'].get(c)),
        'trafos': m(lambda c: at['ntr'].get(c) or None),
        'kVA': m(lambda c: at['kva'].get(c) or None),
        'R1_ponderado': m(lambda c: _ponderado(at['cnd'][c], at['r1'], 0.4)),
        'CNOM_ponderado': m(lambda c: _ponderado(at['cnd'][c], at['cnom'], 200.0)),
        'kVA_por_km': m(lambda c: (at['kva'][c] / at['km'][c])
                        if at['km'].get(c) and at['kva'].get(c) else None),
    }


def enriquecimento(suspeitos, resto, at, minimo_km=1.0):
    """Fracao de km de cada condutor nos suspeitos dividida pela fracao no
    resto. Acima de 1 = o condutor esta SOBRE-representado nos suspeitos.

    E o numero que decide, e nao a maioria simples: um condutor que ja e 13,5%
    da rede sendo 13,5% da violacao nao explica nada. Foi assim que o 593 da
    Enel SP se sustentou como achado.
    """
    def mistura(cods):
        acc = collections.Counter()
        for c in cods:
            acc.update(at['cnd'][c])
        tot = sum(acc.values()) or 1.0
        return {k: v / tot for k, v in acc.items()}, tot

    ms, km_s = mistura(suspeitos)
    mr, _ = mistura(resto)
    saida = []
    for cond, fs in ms.items():
        if fs * km_s < minimo_km:      # condutor irrelevante naquele grupo
            continue
        fr = mr.get(cond, 0.0)
        saida.append({
            'condutor': cond,
            'pct_nos_suspeitos': round(100 * fs, 2),
            'pct_no_resto': round(100 * fr, 2),
            'enriquecimento': round(fs / fr, 2) if fr else None,
            'R1': at['r1'].get(cond),
            'CNOM': at['cnom'].get(cond),
        })
    saida.sort(key=lambda x: -(x['enriquecimento'] or 0))
    return saida


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', 'bdgds'),
                    help='pasta(s) com as .gdb')
    ap.add_argument('--resultados', required=True,
                    help='resultados/<sufixo> publicado pelo coletor')
    ap.add_argument('--so', required=True, help='a TAG da base, ex: COPELDIS2866')
    ap.add_argument('--gdb', help='caminho da .gdb, se o nome nao casar com a TAG')
    ap.add_argument('--motivo', help='so as violacoes cujo motivo comeca assim')
    ap.add_argument('--saida-json', default=None)
    a = ap.parse_args(argv)

    suspeitos, fora = suspeitos_do_csv(a.resultados, a.so, a.motivo)
    if not suspeitos:
        raise SystemExit('nenhum CTMT suspeito com esse filtro')
    print(f'{len(suspeitos)} alimentadores suspeitos em {a.so}'
          + (f' (motivo comecando por "{a.motivo}")' if a.motivo else '')
          + (f'; {fora} ignorados por modelo quebrado' if fora else ''))

    gdb = a.gdb
    if not gdb:
        # QUEM SABE O MAPA TAG -> .gdb E O `regerar`, e nao um palpite sobre o
        # nome do arquivo. Adivinhar por prefixo falha justamente nas bases
        # conhecidas, que tem APELIDO: a Cemig-D e `CMIG`, a Enel CE e `ENCE`,
        # a Light e `LT` — nenhum deles aparece no nome da `.gdb`. Foi assim
        # que o perfil da CMIG morreu com "0 candidatas" em 30/08/2026.
        os.environ.setdefault('BDGD2DSS_BASES', a.bases or '')
        import regerar_v10 as rg
        gdb = next((c for t, c, _ in rg.descobrir(a.bases) if t == a.so), None)
        if not gdb:
            achadas = ', '.join(sorted(t for t, _, _ in rg.descobrir(a.bases)))
            raise SystemExit(
                f'nao achei a base {a.so} em {a.bases}.\n'
                f'   encontradas: {achadas or "nenhuma"}\n'
                f'   ou passe --gdb com o caminho.')
    print(f'lendo {os.path.basename(gdb)}', flush=True)

    at = atributos(gdb)
    todos = set(at['km']) | set(at['kva'])
    suspeitos &= todos            # so o que a BDGD realmente declara
    resto = todos - suspeitos
    if not suspeitos:
        raise SystemExit('os CTMT suspeitos nao aparecem nesta .gdb — '
                         'confira se a safra e a mesma da rodada')

    p_sus, p_res = perfil(suspeitos, at), perfil(resto, at)
    enr = enriquecimento(suspeitos, resto, at)

    campos = ['n', 'km', 'trafos', 'kVA', 'R1_ponderado', 'CNOM_ponderado',
              'kVA_por_km']
    print()
    print(f'{"grupo":14s}' + ''.join(f'{c:>16s}' for c in campos))
    for rot, p in (('SUSPEITOS', p_sus), ('resto da base', p_res)):
        print(f'{rot:14s}' + ''.join(
            f'{(p[c] if p[c] is not None else float("nan")):>16.2f}'
            for c in campos))

    print('\ncondutor mais SOBRE-representado nos suspeitos '
          '(enriquecimento > 1 = concentra):')
    for e in enr[:8]:
        print(f"  {e['condutor']:>12s}  nos suspeitos {e['pct_nos_suspeitos']:5.2f}%"
              f"  no resto {e['pct_no_resto']:5.2f}%"
              f"  enriquecimento {e['enriquecimento']}"
              f"  R1={e['R1']}  CNOM={e['CNOM']}")

    saida = a.saida_json or os.path.join(
        RAIZ, 'medicoes', f'perfil_violacao_{a.so}.json')
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump({'base': a.so, 'gdb': os.path.basename(gdb),
                   'motivo': a.motivo, 'suspeitos': sorted(suspeitos),
                   'perfil_suspeitos': p_sus, 'perfil_resto': p_res,
                   'enriquecimento_condutor': enr}, fh,
                  ensure_ascii=False, indent=1)
    print(f'\ngravado em {saida}')


if __name__ == '__main__':
    main()
