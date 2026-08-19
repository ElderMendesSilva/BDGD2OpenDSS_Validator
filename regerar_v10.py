# -*- coding: utf-8 -*-
"""
REGERACAO COMPLETA — as sete bases, do zero, com o codigo atual.
================================================================

    python regerar_v10.py                 roda o que falta
    python regerar_v10.py --refazer       ignora o que ja esta pronto
    python regerar_v10.py --so RR ENCE    apenas essas
    python regerar_v10.py --sem-premissas conversao pura, sem modelagem

O CICLO, EM ORDEM
-----------------
    converter -> ligacao -> ampacidade -> verifica -> energia -> validador
              -> valida_perdas -> valida_balanco

`ligacao` e `ampacidade` sao PREMISSAS DE MODELAGEM, e nao conversao: a
primeira inventa um elo que a BDGD nao declara (achado 33, forma B) e a
segunda troca a resistencia de trecho que conduz acima da propria ampacidade
(achado 34). As duas vem antes de medir, porque o que se mede tem de ser o
modelo que o usuario recebe. `--sem-premissas` pula as duas.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdgd2dss import pausa                           # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
BDGDS = r'D:\Elder\Elder\BDGDs'
CRIT = os.path.dirname(AQUI)
LOGS = os.path.join(AQUI, 'logs', 'v10')      # ver PASTAS, no CLAUDE.md
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


def mesclar(antes, agora):
    """Junta o resumo desta rodada com o que ja estava no arquivo.

    `--so CMIG` sobrescrevia o resumo INTEIRO com uma base so. Aconteceu na
    V11: as seis bases da noite sumiram do JSON quando a Cemig-D foi
    reprocessada sozinha, e a tabela teve de ser remontada na mao a partir
    dos JSONs de cada modelo.

    O resumo e por base, entao a regra e por base: quem rodou agora vale
    agora, quem nao rodou continua como estava. A ordem segue a de `BASES`,
    para a tabela sair sempre igual.
    """
    novo = {r['tag']: r for r in agora}
    velho = {r['tag']: r for r in antes if r.get('tag') not in novo}
    juntos = {**velho, **novo}
    ordem = [t for t, _, _ in BASES]
    return sorted(juntos.values(),
                  key=lambda r: (ordem.index(r['tag'])
                                 if r.get('tag') in ordem else len(ordem)))


def _gravador(destino):
    """Devolve a funcao que grava o resumo mesclado em `destino`."""
    def gravar(proc, agora):
        antes = []
        if os.path.exists(destino):
            try:
                with open(destino, encoding='utf-8') as fh:
                    antes = json.load(fh).get('bases') or []
            except Exception:
                antes = []          # arquivo ilegivel nao pode travar a rodada
        with open(destino, 'w', encoding='utf-8') as fh:
            json.dump({'procedencia': proc, 'bases': mesclar(antes, agora)},
                      fh, indent=1, ensure_ascii=False)
    return gravar


def passo(rot, cmd, log, limite):
    """Roda um comando, despeja a saida no log, devolve (ok, minutos).

    O TEMPO EM PAUSA NAO CONTA. Nem para o limite — pausar tres horas nao pode
    fazer a etapa "estourar o tempo limite" quando for retomada — nem para os
    minutos gravados no resumo, que sao de trabalho e servem para comparar uma
    geracao com a outra.

    Quem de fato para sao os trabalhadores dentro da etapa, cada um olhando o
    mesmo arquivo. Aqui so se MEDE quanto durou a pausa, e se espera antes de
    comecar uma etapa nova.
    """
    pausa.espera(rot, avisa=lambda t: print(f'   {t}', flush=True))
    t0 = time.time()
    parado = 0.0
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(f'\n{"="*72}\n== {rot}  [{time.strftime("%d/%m %H:%M:%S")}]\n'
                 f'== {" ".join(cmd)}\n{"="*72}\n')
        fh.flush()
        try:
            p = subprocess.Popen(cmd, cwd=AQUI, stdout=fh,
                                 stderr=subprocess.STDOUT)
            while p.poll() is None:
                time.sleep(1)
                if pausa.pausado():
                    parado += 1
                elif time.time() - t0 - parado > limite:
                    p.kill()
                    p.wait()
                    fh.write('\n*** ESTOUROU O TEMPO LIMITE ***\n')
                    break
            ok = p.returncode == 0
        except Exception as e:
            fh.write(f'\n*** {type(e).__name__}: {e} ***\n')
            ok = False
    m = (time.time() - t0 - parado) / 60.0
    print(f'   {rot:16s} {"ok    " if ok else "FALHOU"} {m:7.1f} min'
          + (f'   (+{parado/60:.0f} min em pausa)' if parado > 60 else ''),
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

    amp = ler('ampacidade.json')
    if amp:
        ses = [x for x in (amp.get('subestacoes') or []) if not x.get('erro')]
        reg['ampacidade_trocados'] = sum(x.get('trocados', 0) for x in ses)
        reg['ampacidade_km'] = round(sum(x.get('km_trocado', 0.0)
                                         for x in ses), 1)

    lg = ler('ligacao.json')
    if lg:
        ses = [x for x in (lg.get('subestacoes') or []) if not x.get('erro')]
        reg['ligacao_elos'] = sum(x.get('elos', 0) for x in ses)
        reg['ligacao_cargas'] = sum(x.get('mortas_antes', 0)
                                    - x.get('mortas_depois', 0) for x in ses)

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


def _painel():
    """Sem argumento, pergunta na janela — o `menu.py` conta com isso.

    Este e o unico script que dispara HORAS de trabalho num clique, entao ele
    pergunta antes: quais bases, com que sufixo e se as premissas entram.
    """
    import interativo
    v = interativo.formulario('regerar', 'Ciclo completo das sete bases', [
        {'chave': 'sufixo', 'tipo': 'texto', 'rotulo': 'Sufixo da rodada',
         'padrao': 'V15',
         'dica': 'as saidas vao para MODELOS_<BASE>_<SUFIXO> e os logs para '
                 'logs/<sufixo>. Nunca por cima da rodada anterior'},
        {'chave': 'so', 'tipo': 'texto', 'rotulo': 'Apenas estas bases',
         'padrao': '',
         'dica': 'vazio = as sete   •   ex.: RR ENCE   '
                 '(RR ENCE EQPA SP LT CPFL CMIG)'},
        {'chave': 'jobs', 'tipo': 'inteiro', 'rotulo': 'Subestacoes em paralelo',
         'padrao': 8,
         'dica': 'usado nos passos que resolvem rede. Medido: satura perto de '
                 '8, porque o custo e ler o modelo do disco. Use 1 se for '
                 'usar o computador junto'},
        {'chave': 'max_ctmt', 'tipo': 'inteiro',
         'rotulo': 'Alimentadores por leitura', 'padrao': 850,
         'dica': 'a BDGD nao tem indice: cada leitura varre a tabela inteira. '
                 'Maior = menos varreduras e mais memoria. O limite do '
                 'formato e 900'},
        {'chave': 'premissas', 'tipo': 'bool',
         'rotulo': 'Aplicar as premissas de modelagem', 'padrao': True,
         'dica': 'religar rede sem tensao e trocar condutor sobrecarregado. '
                 'Desmarcado, o modelo reproduz SO o que a BDGD declara'},
        {'chave': 'refazer', 'tipo': 'bool', 'rotulo': 'Refazer o que ja esta pronto',
         'padrao': False,
         'dica': 'por padrao ele pula a base que ja tem validacao_balanco.json '
                 'e continua da proxima'},
    ], ajuda='Roda o ciclo inteiro nas sete distribuidoras: converter, as duas '
             'premissas, verificar, energia, validador e as duas validacoes. '
             'Sao HORAS — deixe rodando. Retoma de onde parou.',
       rodar='Rodar o ciclo')
    if not v:
        return False
    sys.argv += ['--sufixo', v['sufixo'], '--jobs', str(v['jobs']),
                 '--max-ctmt', str(v['max_ctmt'])]
    if v['so'].strip():
        sys.argv += ['--so'] + v['so'].split()
    if not v['premissas']:
        sys.argv.append('--sem-premissas')
    if v['refazer']:
        sys.argv.append('--refazer')
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    global SUFIXO, LOGS
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('--refazer', action='store_true',
                    help='ignora o que ja esta pronto e regera tudo')
    ap.add_argument('--sem-premissas', action='store_true',
                    help='pula a ligacao e a ampacidade: gera a conversao '
                         'PURA, so o que a BDGD declara. Serve para medir '
                         'quanto do resultado depende de premissa nossa')
    ap.add_argument('--so', nargs='+', metavar='TAG',
                    help='apenas estas bases (RR ENCE EQPA SP LT CPFL CMIG)')
    # A saida NUNCA vai por cima: cada rodada tem o seu sufixo, e as anteriores
    # ficam no disco. Sem elas nao ha com o que comparar, e comparar e o unico
    # jeito de saber se a mudanca melhorou ou piorou — foi assim que se
    # descobriu que o passo 5 nao moveu nenhum numero de energia (achado 23).
    ap.add_argument('--jobs', type=int, default=8, metavar='N',
                    help='subestacoes em paralelo nos passos que resolvem '
                         'rede (padrao 8). Medido: o ganho satura perto de 8, '
                         'porque o custo e ler o modelo do disco')
    ap.add_argument('--max-ctmt', type=int, default=850, dest='max_ctmt',
                    metavar='N',
                    help='alimentadores por leitura da BDGD na conversao '
                         '(padrao 850; o formato aceita 900)')
    ap.add_argument('--sufixo', default=SUFIXO, metavar='TAG',
                    help=f'sufixo das pastas de saida (padrao {SUFIXO}); '
                         f'MODELOS_<base>_<sufixo>')
    a = ap.parse_args()

    SUFIXO = a.sufixo
    LOGS = os.path.join(AQUI, 'logs', SUFIXO.lower())

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
    gravar = _gravador(dest_resumo)
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
            'converter', [PY, '-u', 'converter.py', gdb, '--saida', saida,
                          '--max-ctmt', str(a.max_ctmt)],
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

        # --- as duas premissas de MODELAGEM, nesta ordem e antes de medir
        #
        # A ordem importa. A `ligacao` energiza rede que estava no escuro; a
        # `ampacidade` decide pela corrente que passa em cada trecho. Rodar a
        # ampacidade primeiro mediria corrente numa rede menor e trocaria
        # menos condutor do que deve.
        #
        # As duas vem ANTES do `verifica`: o que se mede tem de ser o modelo
        # que o usuario vai receber, e nao um estagio intermediario dele.
        #
        # `--sem-premissas` pula as duas e regera a conversao pura, que e o
        # que a BDGD declara. Ter esse caminho e o que permite dizer, com
        # numero, quanto do resultado depende de premissa nossa.
        if not a.sem_premissas:
            ok, reg['min_ligacao'] = passo(
                'ligacao', [PY, '-u', 'ligacao.py', saida,
                            '--jobs', str(a.jobs)], log, 4 * 3600)
            reg['ligacao_ok'] = ok
            ok, reg['min_ampacidade'] = passo(
                'ampacidade', [PY, '-u', 'ampacidade.py', saida,
                            '--jobs', str(a.jobs)], log, 4 * 3600)
            reg['ampacidade_ok'] = ok

        ok, reg['min_verifica'] = passo('verifica', [PY, '-u', 'verifica.py', saida,
                                                     '--jobs', str(a.jobs)],
                                        log, 6 * 3600)
        reg['verifica_ok'] = ok
        ok, reg['min_energia'] = passo('energia', [PY, '-u', 'energia.py', saida,
                                                   '--jobs', str(a.jobs)],
                                       log, 8 * 3600)
        reg['energia_ok'] = ok
        # O validador entra na fila porque e ele que exercita a mudanca do
        # achado 3 — o limiar de REDE_EXTENSA vindo da propria base. Sem ele
        # a correcao seria regerada sem nunca ser executada.
        ok, reg['min_validador'] = passo('validador', [PY, '-u',
                                                       'validador.py', saida,
                                                       '--ses',
                                                       '--jobs', str(a.jobs)],
                                         log, 4 * 3600)
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
        gravar(proc, resumo)

    gravar(proc, resumo)

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
