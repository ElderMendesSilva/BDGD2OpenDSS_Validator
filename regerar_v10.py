# -*- coding: utf-8 -*-
"""
REGERACAO COMPLETA — as sete bases, do zero, com o codigo atual.
================================================================

    python regerar_v10.py                 roda o que falta
    python regerar_v10.py --refazer       ignora o que ja esta pronto
    python regerar_v10.py --so RR ENCE    apenas essas

Por que existe: o passo 5 do PLANO.md muda a SAIDA do conversor (ancoragem
da AT, tabelas de tensao derivadas da base, clima por regiao). Nenhuma dessas
mudancas pode ser validada sem regerar, e regerar sete bases e um ciclo de
~11 h. Este script e o que roda esse ciclo sozinho, de madrugada.

TRES DECISOES QUE IMPORTAM
--------------------------
1. SAIDA NOVA, NUNCA POR CIMA. Cada base vai para `MODELOS_*_V10`. A V9 e as
   demais ficam intactas — sem elas nao ha com o que comparar, e comparar e
   o unico jeito de saber se a mudanca melhorou ou piorou.

2. A MENOR PRIMEIRO, COMO CANARIO. Roraima converte em 1,9 min. Se o codigo
   estiver quebrado, isso aparece em dois minutos, e nao depois de 148 min de
   Cemig-D. Se o canario falhar na conversao, o script PARA — nao adianta
   gastar 11 h com codigo que nao compila uma base de 20 subestacoes.

3. RETOMA DE ONDE PAROU. Base cujo `validacao_balanco.json` ja existe e
   pulada. Uma queda no meio da noite nao custa a noite inteira.

Uma falha em qualquer etapa registra e segue para a proxima base — menos no
canario, e menos na conversao, sem a qual nao ha o que medir.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
BDGDS = r'D:\Elder\Elder\BDGDs'
CRIT = os.path.dirname(AQUI)
LOGS = os.path.join(AQUI, 'logs_v10')
PY = sys.executable

# (tag, caminho da .gdb, minutos de conversao medidos na rodada anterior)
# A ordem E o projeto: canario primeiro, depois por tamanho crescente.
BASES = [
    ('RR', os.path.join(BDGDS, 'Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb'), 1.9),
    ('ENCE', os.path.join(BDGDS, 'Enel_CE_39_2024-12-31_V11_20250822-1151.gdb'), 21.6),
    ('EQPA', os.path.join(BDGDS, 'Equatorial_PA_371_2024-12-31_V11_20250911-0946.gdb'), 40.1),
    ('SP', os.path.join(CRIT, 'Enel_SP_390_2024-12-31_V11_20250702-2009.gdb'), 48.2),
    ('LT', os.path.join(BDGDS, 'Light_382_2024-12-31_V11_20250925-1811.gdb'), 52.9),
    ('CPFL', os.path.join(BDGDS, 'CPFL_Paulista_63_2024-12-31_V11_20250731-1036.gdb'), 85.3),
    ('CMIG', os.path.join(BDGDS, 'Cemig-D_4950_2024-12-31_V11_20250929-1522.gdb'), 148.4),
]

os.environ['BDGD_SEM_JANELA'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'


class _Tee:
    """Escreve no console E num arquivo. Sem dependencia, sem logging."""

    def __init__(self, caminho):
        self.arq = open(caminho, 'a', encoding='utf-8', errors='replace')
        self.console = sys.__stdout__

    def write(self, s):
        self.arq.write(s)
        self.arq.flush()
        if self.console is not None:
            try:
                self.console.write(s)
                self.console.flush()
            except Exception:
                self.console = None      # sem console (Agendador de Tarefas)

    def flush(self):
        self.arq.flush()


def procedencia():
    """De qual codigo estes modelos sairam.

    A V9 resolveu isso com o SHA-256 de 25 arquivos, porque o projeto ainda
    nao era repositorio. Agora e: o commit identifica o codigo inteiro de uma
    vez. O que o commit NAO cobre e alteracao nao commitada — dai o `sujo`,
    que e o campo mais importante deste bloco. Modelo gerado com a arvore
    suja nao e reproduzivel, e isso tem de estar escrito, nao suposto.
    """
    import subprocess as sp

    def git(*a):
        try:
            return sp.run(['git'] + list(a), cwd=AQUI, capture_output=True,
                          text=True, timeout=30).stdout.strip()
        except Exception:
            return ''

    return {'commit': git('rev-parse', 'HEAD'),
            'descricao': git('log', '-1', '--pretty=%s'),
            'sujo': bool(git('status', '--porcelain')),
            'python': sys.version.split()[0],
            'gerado_em': time.strftime('%Y-%m-%d %H:%M:%S')}


SUFIXO = 'V10'          # sobrescrito por --sufixo


def saida_de(tag):
    return f'MODELOS_{tag}_{SUFIXO}'


def passo(rot, cmd, log, limite):
    """Roda um comando, despeja a saida no log, devolve (ok, minutos)."""
    t0 = time.time()
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(f'\n{"="*72}\n== {rot}  [{time.strftime("%d/%m %H:%M:%S")}]\n'
                 f'== {" ".join(cmd)}\n{"="*72}\n')
        fh.flush()
        try:
            r = subprocess.run(cmd, cwd=AQUI, stdout=fh,
                               stderr=subprocess.STDOUT, timeout=limite)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            fh.write('\n*** ESTOUROU O TEMPO LIMITE ***\n')
            ok = False
        except Exception as e:
            fh.write(f'\n*** {type(e).__name__}: {e} ***\n')
            ok = False
    m = (time.time() - t0) / 60.0
    print(f'   {rot:16s} {"ok    " if ok else "FALHOU"} {m:7.1f} min',
          flush=True)
    return ok, round(m, 1)


def colher(tag, reg):
    """Os numeros que interessam, lidos dos JSONs que as etapas escreveram."""
    d = os.path.join(AQUI, saida_de(tag))

    def ler(nome):
        cam = os.path.join(d, nome)
        if not os.path.exists(cam):
            return None
        try:
            with open(cam, encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return None

    v = ler('verificacao.json')
    if v:
        reg['subestacoes'] = len(v)
        reg['sadias'] = sum(1 for x in v if x['veredicto'] == 'OK')

    e = ler('energia_dia.json')
    if e:
        al = [x for s in e for x in (s.get('alimentadores') or {}).values()]
        med = [x for x in al if x.get('perdas_pct') is not None]
        reg['alimentadores'] = len(al)
        reg['medidos'] = len(med)
        reg['cobertura_pct'] = (round(100 * len(med) / len(al), 1)
                                if al else None)

    p = ler('validacao_perdas.json')
    if p:
        r = [x['razao'] for x in p if x['razao']]
        if r:
            reg['razao_mediana'] = round(statistics.median(r), 2)
            reg['parcelas'] = p[0].get('parcelas')

    b = ler('validacao_balanco.json')
    if b:
        reg['cruzados'] = len(b)
        reg['viola_limite'] = sum(1 for x in b if x['viola_limite'])
        reg['viola_de_verdade'] = sum(1 for x in b
                                      if x.get('viola_de_verdade'))
        reg['degenerada'] = sum(1 for x in b if x.get('medida_degenerada'))
        reg['pct_viola_real'] = (round(100 * reg['viola_de_verdade'] / len(b), 2)
                                 if b else None)
    return reg


def main():
    global SUFIXO, LOGS
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('--refazer', action='store_true',
                    help='ignora o que ja esta pronto e regera tudo')
    ap.add_argument('--so', nargs='+', metavar='TAG',
                    help='apenas estas bases (RR ENCE EQPA SP LT CPFL CMIG)')
    # A saida NUNCA vai por cima: cada rodada tem o seu sufixo, e as anteriores
    # ficam no disco. Sem elas nao ha com o que comparar, e comparar e o unico
    # jeito de saber se a mudanca melhorou ou piorou — foi assim que se
    # descobriu que o passo 5 nao moveu nenhum numero de energia (achado 23).
    ap.add_argument('--sufixo', default=SUFIXO, metavar='TAG',
                    help=f'sufixo das pastas de saida (padrao {SUFIXO}); '
                         f'MODELOS_<base>_<sufixo>')
    a = ap.parse_args()

    SUFIXO = a.sufixo
    LOGS = os.path.join(AQUI, f'logs_{SUFIXO.lower()}')

    os.makedirs(LOGS, exist_ok=True)
    # Rodando pelo Agendador de Tarefas nao ha console: sem isto, o resumo
    # final — a unica visao de conjunto da noite — se perderia.
    sys.stdout = _Tee(os.path.join(LOGS, '_console.log'))
    sys.stderr = sys.stdout
    bases = [b for b in BASES if not a.so or b[0] in a.so]
    prev = sum(b[2] for b in bases)
    t0 = time.time()
    print(f'REGERACAO V10 — {len(bases)} bases, inicio '
          f'{time.strftime("%d/%m/%Y %H:%M")}')
    print(f'conversao prevista: {prev:.0f} min; ciclo completo, ~2,7x isso\n',
          flush=True)

    proc = procedencia()
    print(f'codigo: {proc["commit"][:10] or "(sem git)"} '
          f'{"ARVORE SUJA — modelo nao reproduzivel" if proc["sujo"] else "limpo"}'
          f'  | {proc["descricao"][:60]}\n', flush=True)

    resumo = []
    # o nome acompanha o sufixo: a V11 gravava `resumo_v10.json` dentro de
    # `logs_v11/`, e nome que mente sobre a rodada e o tipo de coisa que
    # confunde quem for comparar duas delas daqui a um mes
    dest_resumo = os.path.join(LOGS, f'resumo_{SUFIXO.lower()}.json')
    for k, (tag, gdb, _) in enumerate(bases):
        saida = saida_de(tag)
        log = os.path.join(LOGS, f'{tag}.log')
        print(f'{"#"*72}\n# {tag}  ->  {saida}\n{"#"*72}', flush=True)
        reg = {'tag': tag, 'saida': saida,
               'inicio': time.strftime('%d/%m %H:%M')}

        if not os.path.isdir(gdb):
            print(f'   .gdb ausente: {gdb}', flush=True)
            reg['erro'] = 'gdb ausente'
            resumo.append(reg)
            continue

        pronto = os.path.exists(os.path.join(AQUI, saida,
                                             'validacao_balanco.json'))
        if pronto and not a.refazer:
            print('   ja pronto — pulando (use --refazer para forcar)',
                  flush=True)
            resumo.append(colher(tag, reg))
            continue

        # SEM `--refazer` no conversor, de proposito: assim uma conversao que
        # cai no meio retoma das subestacoes ja feitas. Foi o que salvou a
        # Cemig-D quando o bug de dtype a derrubou — 265 das 413 ja estavam
        # prontas e foram aproveitadas. O pulo por base, acima, e o que evita
        # refazer o que ja terminou; aqui dentro, retomar e sempre melhor.
        ok, reg['min_converter'] = passo(
            'converter', [PY, '-u', 'converter.py', gdb, '--saida', saida],
            log, limite=8 * 3600)
        reg['converter_ok'] = ok
        if not ok:
            resumo.append(reg)
            # o canario: se a menor base nao converte, o codigo esta quebrado
            if k == 0:
                print('\n*** o canario falhou na conversao. Parando aqui em '
                      'vez de gastar a noite. ***', flush=True)
                break
            continue

        ok, reg['min_verifica'] = passo('verifica', [PY, '-u', 'verifica.py',
                                                     saida], log, 6 * 3600)
        reg['verifica_ok'] = ok
        ok, reg['min_energia'] = passo('energia', [PY, '-u', 'energia.py',
                                                   saida], log, 8 * 3600)
        reg['energia_ok'] = ok
        # O validador entra na fila porque e ele que exercita a mudanca do
        # achado 3 — o limiar de REDE_EXTENSA vindo da propria base. Sem ele
        # a correcao seria regerada sem nunca ser executada.
        ok, reg['min_validador'] = passo('validador', [PY, '-u',
                                                       'validador.py', saida,
                                                       '--ses'], log, 4 * 3600)
        reg['validador_ok'] = ok
        ok, _ = passo('valida_perdas', [PY, '-u', 'valida_perdas.py', saida,
                                        gdb], log, 2 * 3600)
        reg['perdas_ok'] = ok
        ok, _ = passo('valida_balanco', [PY, '-u', 'valida_balanco.py', saida,
                                         gdb], log, 3 * 3600)
        reg['balanco_ok'] = ok

        resumo.append(colher(tag, reg))
        r = resumo[-1]
        print(f'   -> {r.get("sadias","?")}/{r.get("subestacoes","?")} sadias | '
              f'cobertura {r.get("cobertura_pct","?")}% | '
              f'razao {r.get("razao_mediana","?")}x | '
              f'viola real {r.get("pct_viola_real","?")}%\n', flush=True)
        # a procedencia vai TAMBEM para dentro do modelo: o resumo geral pode
        # se separar dele, o arquivo ao lado do MASTER nao
        with open(os.path.join(AQUI, saida, '_procedencia.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dict(proc, base=tag), fh, indent=1, ensure_ascii=False)
        with open(dest_resumo, 'w', encoding='utf-8') as fh:
            json.dump({'procedencia': proc, 'bases': resumo}, fh, indent=1,
                      ensure_ascii=False)

    with open(dest_resumo, 'w', encoding='utf-8') as fh:
        json.dump({'procedencia': proc, 'bases': resumo}, fh, indent=1,
                  ensure_ascii=False)

    print(f'\n{"="*72}\nRESUMO — {(time.time()-t0)/60:.0f} min no total')
    print(f'{"base":6s} {"sadias":>12s} {"cobertura":>10s} {"razao":>8s} '
          f'{"viola real":>12s} {"conv min":>9s}')
    for r in resumo:
        print(f'{r["tag"]:6s} '
              f'{str(r.get("sadias","—"))+"/"+str(r.get("subestacoes","—")):>12s} '
              f'{str(r.get("cobertura_pct","—")):>9s}% '
              f'{str(r.get("razao_mediana","—")):>7s}x '
              f'{str(r.get("pct_viola_real","—")):>11s}% '
              f'{str(r.get("min_converter","—")):>9s}')
    print(f'\ndetalhe em {dest_resumo}')


if __name__ == '__main__':
    main()
