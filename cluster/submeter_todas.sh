#!/usr/bin/env bash
# Submete as bases em ONDAS, dentro de um orcamento de nucleos E de memoria.
#
#     bash cluster/submeter_todas.sh                 # so MOSTRA o plano
#     bash cluster/submeter_todas.sh --rodar         # submete
#     SUFIXO=V22 bash cluster/submeter_todas.sh --rodar
#     SO="RR ENCE" SUFIXO=V22 bash cluster/submeter_todas.sh --rodar
#
# POR QUE ESTE SCRIPT MUDOU. A versao anterior submetia uma base por job, todas
# de uma vez. Em 25/08/2026 isso pos **20 jobs simultaneos** no unico no de
# trabalho — cerca de 80 nucleos e 240 GB — e rendeu uma chamada do
# administrador, que pediu cuidado com a quantidade de jobs e com comandos de
# remocao emitidos por agente.
#
# O ORCAMENTO E A SOMA, e nao o job: nucleos e GB somados sobre tudo o que
# estiver rodando ao mesmo tempo. Como o dimensionamento usa 3 GB por nucleo, a
# memoria acompanha os nucleos — mas ACOMPANHAR NAO E CABER, e foi por isso que
# o teto subiu de 64 em 28/08/2026.
#
# O QUE MUDOU: o administrador liberou os nos de calculo (so o head node saiu de
# cena). Os tres nos somam 768 nucleos e 753 GB. O gargalo, entao, deixa de ser
# permissao e passa a ser MEMORIA: a 3 GB por nucleo, 768 nucleos pediriam
# 2.304 GB, tres vezes o que existe. Contar so `ppn` passaria do limite de
# memoria sem o script perceber.
#
# Por isso agora sao DOIS tetos, e o menor manda. O padrao de 160 nucleos / 480
# GB usa 21% dos nucleos e 64% da memoria, deixando folga para o resto do
# laboratorio — que divide o mesmo cluster.
#
# A TECNICA E DEIXAR O PBS SER O GUARDA. Em vez de N jobs soltos, o script
# monta CORRENTES ligadas por `-W depend=afterany:<id>`: dentro de uma corrente
# os jobs esperam uns aos outros, entao o numero de jobs simultaneos e o numero
# de correntes — garantido pelo escalonador, sem processo nenhum vigiando e sem
# depender de ninguem lembrar.
#
# MOSTRA ANTES DE FAZER. Sem `--rodar` ele imprime o plano, a conta do
# orcamento e os comandos exatos, e nao submete nada. Quem submete e voce.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

FILA="${FILA:-BIRA_Q3}"
SUFIXO="${SUFIXO:-V1_cluster}"
ORCAMENTO="${ORCAMENTO:-160}"         # nucleos somados; NAO aumente sem combinar
# TETO DE MEMORIA, em GB somados. Existe porque o de nucleos nao o garante: o
# cluster tem 753 GB para 768 nucleos, e o dimensionamento pede 3 GB por nucleo.
# Sem este segundo teto, subir `ORCAMENTO` estoura a memoria em silencio.
ORCAMENTO_GB="${ORCAMENTO_GB:-480}"
# TETO DE `ppn` POR JOB. Nao e economia, e paralelismo: o orcamento e fixo em
# ORCAMENTO, entao ppn menor por base significa MAIS correntes ao mesmo tempo.
# E a conversao roda em processo unico (o `regerar_v10` nao repassa `--jobs` ao
# `converter.py`), entao nucleo extra por base fica ocioso justamente na fase
# longa. Medido: a Cemig usou ~3 GB na conversao, cabe folgado em 24 GB.
#   Com ORCAMENTO=160: TAMPA=16 -> 10 correntes, TAMPA=8 -> 20, TAMPA=4 -> 40.
TAMPA="${TAMPA:-8}"
WALLTIME="${WALLTIME:-12:00:00}"
# MOTOR DE PARTIDA: segundos entre a largada de uma corrente e a da seguinte.
# Nao e cerimonia, e I/O. As correntes comecam TODAS pela leitura da `.gdb`, e
# 20 delas abrindo 127 GB no mesmo instante disputam o mesmo disco: a fase mais
# longa de cada job vira a mais lenta de todas. Escalonar a partida espalha a
# leitura no tempo, e nao custa relogio no fim, porque o que atrasa e so a
# CABECA de cada corrente: o resto ja esperava dependencia de qualquer jeito.
# Com 20 correntes e 90s, a carga sobe ao longo de ~28 min. RAMPA=0 desliga.
RAMPA="${RAMPA:-90}"
RODAR="no"
[[ "${1:-}" == "--rodar" ]] && RODAR="sim"

: "${BDGD2DSS_BASES:?defina onde estao as .gdb}"

# O PYTHON E O DO `.venv`, e nao o do sistema. O nó tem `python3` 3.6.8 e nao
# tem `python` nenhum: chamar `python` cru dava `command not found`, e chamar
# `python3` daria 3.6.8, que nao roda o projeto (o `requisitos.txt` pede 3.9+)
# nem tem numpy/pyogrio. O `uma_base.pbs` resolve com `source .venv/bin/
# activate`; aqui basta o caminho, porque e uma chamada so.
PY_VENV="$PWD/.venv/bin/python"
if [[ ! -x "$PY_VENV" ]]; then
    echo "!! nao achei $PY_VENV"
    echo "   rode antes: bash cluster/instalar.sh"
    exit 1
fi

echo "=============================================================="
echo " SUBMISSAO EM ONDAS — orcamento de $ORCAMENTO nucleos"
echo "=============================================================="
echo "sufixo   : $SUFIXO"
echo "fila     : $FILA"
echo "bases    : ${SO:-todas as encontradas}"
echo "tampa ppn: $TAMPA  (menor = mais correntes ao mesmo tempo)"
echo "modo     : $([[ $RODAR == sim ]] && echo 'SUBMETER' || echo 'so mostrar (use --rodar para submeter)')"
echo

# --- de qual codigo esta rodada sai -----------------------------------------
# O COMMIT E LIDO AQUI, no no de acesso, porque no no de CALCULO o `git` nao
# responde. A V21 inteira saiu com `commit` vazio — 97 modelos e ZERO commits
# distintos, isto e, rodada nao rastreavel: nao da para dizer de qual codigo
# aqueles numeros sairam. Quem sabe e quem submete.
#
# Vai por `-v`, e o `regerar_v10.procedencia` so usa este valor se o git de la
# falhar — nunca por cima do que o git diz, porque a variavel pode estar velha
# e o git nunca esta.
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo '')
DESCRICAO=$(git log -1 --pretty=%s 2>/dev/null | tr -cd '[:alnum:] .:-' | cut -c1-60)
if [[ -n "$(git status --porcelain 2>/dev/null | head -1)" ]]; then
    echo '!! ARVORE SUJA: ha alteracao nao commitada neste repositorio.'
    echo '   O modelo que sair daqui NAO seria reproduzivel pelo commit.'
    git status --short | head -5
    exit 1
fi
echo "commit   : ${COMMIT:0:10}  $DESCRICAO"
echo

# --- o que ja esta rodando NOSSO conta contra o orcamento -------------------
EM_USO=$(qstat -u "$USER" -f 2>/dev/null \
         | tr -d ' ' | grep -o 'Resource_List.ncpus=[0-9]*' \
         | cut -d= -f2 | paste -sd+ - | bc 2>/dev/null || echo 0)
EM_USO=${EM_USO:-0}
echo "nucleos ja comprometidos na fila: $EM_USO"
DISPONIVEL=$(( ORCAMENTO - EM_USO ))
if (( DISPONIVEL <= 0 )); then
    echo "!! o orcamento ja esta tomado. Espere terminar, ou use ORCAMENTO=<n> conscientemente."
    exit 1
fi
echo "disponivel para esta submissao  : $DISPONIVEL"
echo

# --- planeja: classifica por tamanho e distribui em correntes ---------------
"$PY_VENV" - "$DISPONIVEL" "$TAMPA" "$ORCAMENTO_GB" > /tmp/plano_ondas.txt <<'PY'
import os, sys
sys.path.insert(0, ".")
import regerar_v10 as r

teto = int(sys.argv[1])
tampa = int(sys.argv[2])
teto_gb = int(sys.argv[3])
so = {x for x in os.environ.get("SO", "").split() if x}

# O TAMANHO VEM DE CACHE, e a razao e a regra de 28/08/2026: o head node nao
# pode mais ser usado para processar. Varrer 97 `.gdb` — 127 GB e ~20 mil
# arquivos — para dimensionar job e I/O pesado, e acontecia a CADA execucao,
# inclusive nas que so mostram o plano.
#
# `.gdb` nao muda de tamanho depois de baixada, entao medir uma vez basta. Base
# nova e medida e entra no cache; o resto so e lido.
import json
CACHE = "medicoes/tamanho_bases.json"
try:
    tam = json.load(open(CACHE, encoding="utf-8"))
except Exception:
    tam = {}
novas = 0

bases = []
for tag, cam, _ in r.BASES:
    if so and tag not in so:
        continue
    if cam in tam:
        gb = tam[cam]
    else:
        gb = sum(os.path.getsize(os.path.join(d, f))
                 for d, _, fs in os.walk(cam) for f in fs) / 2**30
        tam[cam] = gb
        novas += 1
    if   gb <  1: ppn, mem = 4, 12
    elif gb <  5: ppn, mem = 8, 24
    elif gb < 20: ppn, mem = 16, 48
    else:         ppn, mem = 32, 96
    ppn = min(ppn, tampa)
    mem = ppn * 3
    bases.append((tag, ppn, mem, gb))

# CORRENTE = fila sequencial. O custo simultaneo de uma corrente e o MAIOR ppn
# dela, porque so um job dela roda por vez. O teto vale sobre a soma desses
# maiores — e isso e verificavel sem saber quanto cada base demora.
bases.sort(key=lambda x: -x[1])
correntes = []           # cada uma: [maior_ppn, [(tag, ppn, mem), ...], maior_mem]

# ABRIR CORRENTE VEM ANTES DE REAPROVEITAR, e a ordem inverteu um defeito real:
# procurando primeiro uma corrente cujo maior `ppn` coubesse, a PRIMEIRA
# engolia as 97 bases e o plano saia com UMA corrente e 16 nucleos de pico —
# seguro, e desperdicando tres quartos do orcamento numa fila indiana que
# levaria dias. Enquanto houver teto, cada base ganha corrente propria.
# Abrir corrente custa nucleo E memoria: o pico de uma corrente e o maior `ppn`
# dela e a memoria correspondente, porque so um job dela roda por vez. Os dois
# tetos valem juntos, e o que fechar primeiro manda.
for tag, ppn, mem, gb in bases:
    pico_ppn = sum(c[0] for c in correntes)
    pico_gb = sum(c[2] for c in correntes)
    if pico_ppn + ppn <= teto and pico_gb + mem <= teto_gb:
        correntes.append([ppn, [(tag, ppn, mem)], mem])
        continue
    # Teto cheio: entra na corrente MENOS CARREGADA que ja aguente este `ppn`
    # sem crescer. Crescer o maior de uma corrente subiria o pico, e o pico e
    # justamente o que o orcamento limita.
    cabem = [c for c in correntes if c[0] >= ppn]
    if not cabem:
        print("ERRO: base %s pede ppn=%d e nenhuma corrente aguenta" % (tag, ppn))
        raise SystemExit(1)
    min(cabem, key=lambda c: sum(t[1] for t in c[1]))[1].append((tag, ppn, mem))

if novas:
    os.makedirs("medicoes", exist_ok=True)
    json.dump(tam, open(CACHE, "w", encoding="utf-8"), indent=1)
print("MEDIDAS %d" % novas)
print("CORRENTES %d" % len(correntes))
print("PICO %d" % sum(c[0] for c in correntes))
print("PICOGB %d" % sum(c[2] for c in correntes))
for i, (mx, itens, _mg) in enumerate(correntes, 1):
    print("CHAIN %d %d %s" % (i, mx, " ".join("%s:%d:%d" % t for t in itens)))
PY

CORRENTES=$(awk '/^CORRENTES/{print $2}' /tmp/plano_ondas.txt)
PICO=$(awk '$1=="PICO"{print $2}' /tmp/plano_ondas.txt)
PICOGB=$(awk '$1=="PICOGB"{print $2}' /tmp/plano_ondas.txt)
MEDIDAS=$(awk '/^MEDIDAS/{print $2}' /tmp/plano_ondas.txt)
[[ "${MEDIDAS:-0}" != "0" ]] && echo "bases medidas agora (as demais vieram do cache): $MEDIDAS"

echo "plano: $CORRENTES correntes, pico de $PICO nucleos (teto $ORCAMENTO)"      "e $PICOGB GB (teto $ORCAMENTO_GB)"
echo
if [[ "$RAMPA" -gt 0 ]]; then
    echo "rampa: uma corrente a cada ${RAMPA}s; carga cheia em ~$(( (CORRENTES - 1) * RAMPA / 60 )) min"
else
    echo "rampa: DESLIGADA — as $CORRENTES correntes largam no mesmo instante"
fi
awk '/^CHAIN/{n=$2; mx=$3; $1=$2=$3=""; printf "  corrente %-2s (ate %2s nucleos):%s\n", n, mx, $0}' /tmp/plano_ondas.txt
echo

if (( PICO > DISPONIVEL )); then
    echo "!! o plano estoura o disponivel. Nao submeto."
    exit 1
fi

if [[ $RODAR != sim ]]; then
    echo "--------------------------------------------------------------"
    echo " nada foi submetido. Para submeter:"
    echo "     bash cluster/submeter_todas.sh --rodar"
    echo "--------------------------------------------------------------"
    exit 0
fi

# --- submete: dentro da corrente, cada job espera o anterior ----------------
while read -r _ n mx itens; do
    ANT=""
    for it in $itens; do
        TAG="${it%%:*}"; resto="${it#*:}"; PPN="${resto%%:*}"; MEM="${resto##*:}"
        DEP=""
        [[ -n "$ANT" ]] && DEP="-W depend=afterany:$ANT"
        # So a CABECA da corrente ganha hora de largada. Os demais jobs
        # sao presos por `depend`; adiar um deles adiaria a corrente toda.
        LARGADA=""
        if [[ -z "$ANT" && "$RAMPA" -gt 0 && "$n" -gt 1 ]]; then
            LARGADA="-a $(date -d "+$(( (n - 1) * RAMPA )) seconds" +%Y%m%d%H%M.%S)"
        fi
        id=$(qsub -N "b_$TAG" -q "$FILA" \
             -l nodes=1:ppn="$PPN" -l mem="${MEM}gb" -l walltime="$WALLTIME" \
             $DEP $LARGADA \
             -v "TAG=$TAG,SUFIXO=$SUFIXO,PROJETO=$PWD,BDGD2DSS_BASES=$BDGD2DSS_BASES,BDGD2DSS_COMMIT=$COMMIT,BDGD2DSS_DESCRICAO=$DESCRICAO" \
             cluster/uma_base.pbs)
        printf "  corrente %-2s  %-18s ppn=%-3s mem=%-4s -> %s\n" "$n" "$TAG" "$PPN" "${MEM}gb" "$id"
        ANT="$id"
    done
    # A PONTA de cada corrente e o que o coletor tem de esperar.
    CAUDAS="${CAUDAS:-}:$ANT"
done < <(grep '^CHAIN' /tmp/plano_ondas.txt)

# --- o coletor, encadeado nas PONTAS -----------------------------------------
# Ele depende do ULTIMO job de cada corrente, e nao dos 97: sao 8 dependencias
# em vez de 97, e o efeito e o mesmo — quando a ponta de uma corrente termina,
# tudo o que vinha antes dela ja terminou, porque a corrente e sequencial.
#
# `afterany` e nao `afterok` de proposito: o coletor tem de rodar mesmo que uma
# base falhe. Uma rodada com 96 de 97 ainda vale, e sem isto o PBS apagaria o
# coletor quando a primeira base reprovasse.
#
# `ppn=4` porque ele so le JSON. Cabe no orcamento por definicao: quando ele
# roda, as correntes ja acabaram.
ID_COLETOR=$(qsub -W "depend=afterany${CAUDAS}" -N "colet_$SUFIXO" -q "$FILA" \
    -l nodes=1:ppn=4 -l mem=12gb -l walltime=02:00:00 -j oe -o logs/cluster/ \
    -v "PROJETO=$PWD,SUFIXO=$SUFIXO" - <<'PBS'
#!/bin/bash
set -uo pipefail
cd "${PBS_O_WORKDIR:-$PROJETO}"
source .venv/bin/activate
export BDGD2DSS_MODO=cluster
echo "## coletor da $SUFIXO — $(date)"
python -u auditoria.py --sufixo "$SUFIXO"
echo
echo "## resultados/$(echo "$SUFIXO" | tr 'A-Z' 'a-z')/"
du -sh "resultados/$(echo "$SUFIXO" | tr 'A-Z' 'a-z')" 2>/dev/null
echo "## fim $(date)"
PBS
)
echo
echo "  coletor (espera as $CORRENTES pontas) -> $ID_COLETOR"

echo
echo "acompanhe com:  qstat -an -u \$USER"
echo "nucleos em uso: qstat -u \$USER -f | tr -d ' ' | grep -o 'Resource_List.ncpus=[0-9]*' | cut -d= -f2 | paste -sd+ - | bc"
