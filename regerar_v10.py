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
from bdgd2dss import escrita
from bdgd2dss import plataforma      # noqa: E402
from bdgd2dss import cobertura       # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
CRIT = os.path.dirname(AQUI)

# ONDE ESTAO AS .gdb — UMA LISTA DE PASTAS, e nao uma so.
#
# O caminho do Windows desta maquina era o padrao fixo, e num no de cluster ele
# simplesmente nao existe: a rodada morreria na primeira base, depois de ja ter
# esperado a noite na fila. `BDGD2DSS_BASES` resolveu isso.
#
# O QUE FALTAVA, e e o motivo de virar lista: a Enel SP mora FORA da pasta
# nesta maquina, e o resgate dela era o NOME COMPLETO DO ARQUIVO escrito aqui
# dentro, com codigo do agente, safra, versao e carimbo de exportacao. Isso
# prendia o projeto a este computador de duas formas ao mesmo tempo: pelo
# caminho e pelo carimbo. Na safra seguinte o nome muda e o resgate para de
# funcionar, calado.
#
# Agora quem tem base em mais de um lugar diz onde, separando com o separador
# do sistema (`;` no Windows, `:` no Linux):
#
#     set BDGD2DSS_BASES=D:\BDGDs;E:\outras
#     export BDGD2DSS_BASES=$HOME/bdgds:/mnt/dados/bdgds
#
# Sem a variavel, valem os dois lugares onde as bases estao NESTA maquina — e
# isso e conveniencia de quem trabalha aqui, nao premissa do codigo: qualquer
# pasta que nao exista e simplesmente ignorada.
def _pastas_das_bases():
    v = os.environ.get('BDGD2DSS_BASES')
    if v:
        return [p for p in v.split(os.pathsep) if p.strip()]
    return [r'D:\Elder\Elder\BDGDs', CRIT]


PASTAS_BDGD = _pastas_das_bases()
BDGDS = PASTAS_BDGD[0]        # compatibilidade: quem so quer "a pasta"
LOGS = os.path.join(AQUI, 'logs', 'v10')      # ver PASTAS, no CLAUDE.md
PY = sys.executable

def _acha(nome, *alternativas):
    """O caminho da base: onde ela estiver, nesta maquina ou na outra."""
    for raiz in (BDGDS,) + alternativas:
        cam = os.path.join(raiz, nome)
        if os.path.exists(cam):
            return cam
    return os.path.join(BDGDS, nome)          # inexistente: reportado na hora


# AS BASES SAO DESCOBERTAS NA PASTA, e nao listadas aqui.
#
# Ate 21/08/2026 esta lista tinha sete tuplas com o nome exato de cada
# .gdb. Rodar uma distribuidora nova exigia editar Python, e rodar as 53 do
# pais exigia escrever 53 linhas a mao — e errar uma delas as 3 da manha.
#
# Agora: qualquer *.gdb em BDGD2DSS_BASES entra. O que fica escrito aqui e
# so o que NAO da para descobrir: a sigla curta que a gente ja usa nos
# nomes de pasta e nos logs (trocar 'RR' por 'RORAIMA' quebraria a
# comparacao com todas as rodadas anteriores) e os minutos de conversao
# medidos, que servem para prever o tempo e para ordenar o canario.
APELIDO = {
    'roraima_energia': ('RR', 1.9),
    'enel_ce': ('ENCE', 21.6),
    'equatorial_pa': ('EQPA', 40.1),
    'enel_sp': ('SP', 48.2),
    'light': ('LT', 52.9),
    'cpfl_paulista': ('CPFL', 85.3),
    'cemig-d': ('CMIG', 148.4),
}


def _sigla(nome):
    """A sigla de uma .gdb. Conhecida vira apelido; nova vira o nome dela.

    O padrao da ANEEL e `<Distribuidora>_<codigo>_<data>_V11_<carimbo>.gdb`.
    O codigo e o numero do agente no cadastro, e e o unico identificador
    estavel — o nome muda com incorporacao, o carimbo muda a cada safra.
    """
    base = os.path.basename(nome)
    sem = base[:-4] if base.lower().endswith('.gdb') else base
    partes = sem.split('_')
    # o codigo do agente e a primeira parte que e so digito
    cod = next((p for p in partes if p.isdigit()), '')
    chave = '_'.join(partes[:partes.index(cod)]).lower() if cod else sem.lower()
    if chave in APELIDO:
        return APELIDO[chave]
    curta = chave.upper().replace('-', '')[:10] or 'BASE'
    return (f'{curta}{cod}' if cod else curta), None


def descobrir(pasta=None):
    """(tag, caminho, minutos) para cada .gdb encontrada.

    Ordem: as conhecidas primeiro, na ordem medida — canario antes de tudo,
    porque uma base de 20 subestacoes falha em dois minutos e nao em duas
    horas. As novas vao depois, por tamanho de arquivo crescente, que e o
    melhor palpite de custo que existe sem ter rodado nenhuma vez.
    """
    import glob
    # Uma pasta pedida vale sozinha; sem pedido, valem TODAS as de
    # `PASTAS_BDGD`. Quem pede uma pasta especifica quer o que esta NELA, e
    # injetar base de outro lugar seria mentira — foi o que o teste de pasta
    # vazia pegou.
    pastas = [pasta] if pasta else PASTAS_BDGD
    achadas = []
    for p in pastas:
        for cam in sorted(glob.glob(os.path.join(p, '*.gdb'))):
            if cam not in achadas:
                achadas.append(cam)
    achadas.sort()

    conhecidas, novas = [], []
    ordem = [t for t, _ in APELIDO.values()]
    for cam in achadas:
        tag, min_conv = _sigla(cam)
        if min_conv is not None:
            conhecidas.append((tag, cam, min_conv))
        else:
            try:
                tam = sum(os.path.getsize(os.path.join(r, f))
                          for r, _, fs in os.walk(cam) for f in fs)
            except OSError:
                tam = 0
            novas.append((tag, cam, None, tam))
    conhecidas.sort(key=lambda x: ordem.index(x[0]))
    novas.sort(key=lambda x: x[3])
    return conhecidas + [(t, c, m) for t, c, m, _ in novas]


BASES = descobrir()

os.environ['BDGD_SEM_JANELA'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'


class _Tee:
    """Escreve no console E num arquivo. Sem dependencia, sem logging."""

    def __init__(self, caminho):
        self.arq = open(caminho, 'a', encoding='utf-8', errors='replace', newline=escrita.FIM_DE_LINHA)
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
        """(respondeu, saida). `respondeu` diz se o git RODOU, nao se ha saida.

        A distincao e o conserto. `git status --porcelain` devolve string
        vazia quando a arvore esta LIMPA — exatamente o mesmo que a versao
        anterior devolvia quando o comando FALHAVA. As duas viravam
        `sujo=False`, e a rodada era carimbada `limpo`: um atestado de
        reprodutibilidade que ninguem verificou.

        Aconteceu no job 34039, no Ubiratan, em 25/08/2026 — a linha saiu
        `codigo: (sem git) limpo`. O `git` responde no no de acesso e nao no
        no de execucao, entao o `except` engolia e o modelo se declarava
        reproduzivel sozinho.
        """
        try:
            p = sp.run(['git'] + list(a), cwd=AQUI, capture_output=True,
                       text=True, timeout=30)
        except Exception:                                        # noqa: BLE001
            return False, ''
        return p.returncode == 0, p.stdout.strip()

    ok_commit, commit = git('rev-parse', 'HEAD')
    ok_status, status = git('status', '--porcelain')
    _, descricao = git('log', '-1', '--pretty=%s')

    return {'commit': commit,
            'descricao': descricao,
            # None NAO e False. `False` afirma "conferi e a arvore esta
            # limpa"; `None` diz "nao deu para conferir". Quem le o
            # `_procedencia.json` depois precisa poder separar as duas — a
            # segunda nao sustenta reivindicacao de reprodutibilidade.
            'sujo': bool(status) if ok_status else None,
            'git_respondeu': bool(ok_commit and ok_status),
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
    # A ORDEM CANONICA VEM DO APELIDO, e nao de `BASES`. Desde que as
    # bases sao descobertas na pasta, `BASES` depende de quais .gdb estao
    # na maquina — e a tabela final mudaria de ordem conforme o disco.
    # As conhecidas vem sempre na mesma ordem; o que foi descoberto e nao
    # tem apelido vai depois, e `mesclar` ja poe desconhecido no fim.
    ordem = [tag for tag, _ in APELIDO.values()]
    ordem += [t for t, _, _ in BASES if t not in ordem]
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
        with open(destino, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
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
    with open(log, 'a', encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
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
        # DUAS FORMAS. Ate a V17 o arquivo era uma LISTA de
        # alimentadores; passou a ser um dicionario, para caber a
        # sensibilidade ao corte, o agregado e o aviso de modelo
        # implausivel. Ler as duas mantem a tabela comparavel com as
        # rodadas velhas, que e o que permite dizer que um numero mudou.
        alim = p if isinstance(p, list) else (p.get('alimentadores') or [])
        r = [x['razao'] for x in alim if x['razao']]
        if r:
            reg['razao_mediana'] = round(statistics.median(r), 2)
            reg['parcelas'] = alim[0].get('parcelas')
        if isinstance(p, dict):
            ag = p.get('agregado') or {}
            im = p.get('modelo_implausivel') or {}
            reg['razao_agregada'] = (round(ag['razao'], 2)
                                     if ag.get('razao') else None)
            reg['sensibilidade'] = p.get('sensibilidade')
            reg['alim_implausiveis'] = im.get('n')
            reg['fatia_perda_implausivel'] = (
                round(im['fatia_da_perda_pct'], 1)
                if im.get('fatia_da_perda_pct') is not None else None)

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
        # Carga energizada nas DUAS medidas — ver `bdgd2dss/cobertura.py`.
        c = cobertura.energizada(ses)
        reg['energizada_cont_pct'] = c['cont_pct']
        reg['energizada_kW_pct'] = c['kW_pct']
        reg['MW_nominal'] = c['MW_nominal']

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
    ap.add_argument('--modo', choices=['pessoal', 'cluster'],
                    help='pessoal deixa nucleos livres e abre formulario; '
                         'cluster usa a maquina toda e nunca abre janela. '
                         'Sem isto e detectado: fila do Slurm, ou Linux sem '
                         'tela, valem cluster')
    ap.add_argument('--jobs', type=int, default=0, metavar='N',
                    help='subestacoes em paralelo nos passos que resolvem '
                         'rede. 0 = decide pelo modo: no pessoal deixa '
                         'nucleos livres, com teto de 8, porque medido o ganho '
                         'satura ai; no cluster usa a maquina')
    ap.add_argument('--max-ctmt', type=int, default=0, dest='max_ctmt',
                    metavar='N',
                    help='alimentadores por leitura da BDGD na conversao '
                         '(padrao 850; o formato aceita 900)')
    ap.add_argument('--sufixo', default=SUFIXO, metavar='TAG',
                    help=f'sufixo das pastas de saida (padrao {SUFIXO}); '
                         f'MODELOS_<base>_<sufixo>')
    a = ap.parse_args()
    # O modo antes de tudo: ele decide quantos processos usar, se ha
    # formulario, e viaja no ambiente para as etapas, que sao processos novos.
    plataforma.fixar(a.modo)
    if not a.jobs:
        a.jobs = plataforma.nucleos()

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
    # Tres estados, e nao dois. O terceiro — nao verificado — nao existia, e
    # por isso se disfarcava do primeiro.
    if proc['sujo'] is None:
        estado = 'PROCEDENCIA NAO VERIFICADA — o git nao respondeu neste no'
    elif proc['sujo']:
        estado = 'ARVORE SUJA — modelo nao reproduzivel'
    else:
        estado = 'limpo'
    print(f'codigo: {proc["commit"][:10] or "(sem git)"} {estado}'
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
              f'energizada {r.get("energizada_kW_pct","?")}% do kW '
              f'({r.get("energizada_cont_pct","?")}% das cargas) | '
              f'cobertura {r.get("cobertura_pct","?")}% | '
              f'razao {r.get("razao_mediana","?")}x | '
              f'viola real {r.get("pct_viola_real","?")}%\n', flush=True)
        # a procedencia vai TAMBEM para dentro do modelo: o resumo geral pode
        # se separar dele, o arquivo ao lado do MASTER nao
        with open(os.path.join(AQUI, saida, '_procedencia.json'), 'w',
                  encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
            json.dump(dict(proc, base=tag), fh, indent=1, ensure_ascii=False)
        gravar(proc, resumo)

    gravar(proc, resumo)

    print(f'\n{"="*72}\nRESUMO — {(time.time()-t0)/60:.0f} min no total')
    print(f'{"base":6s} {"sadias":>12s} {"energ kW":>9s} {"energ cont":>11s} '
          f'{"cobertura":>10s} {"razao":>8s} {"viola real":>12s} '
          f'{"conv min":>9s}')
    for r in resumo:
        print(f'{r["tag"]:6s} '
              f'{str(r.get("sadias","—"))+"/"+str(r.get("subestacoes","—")):>12s} '
              f'{str(r.get("energizada_kW_pct","—")):>8s}% '
              f'{str(r.get("energizada_cont_pct","—")):>10s}% '
              f'{str(r.get("cobertura_pct","—")):>9s}% '
              f'{str(r.get("razao_mediana","—")):>7s}x '
              f'{str(r.get("pct_viola_real","—")):>11s}% '
              f'{str(r.get("min_converter","—")):>9s}')
    print(f'\ndetalhe em {dest_resumo}')


if __name__ == '__main__':
    main()
