#!/usr/bin/env bash
# Submete as bases em ONDAS, dentro do orcamento de 64 nucleos.
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
# O ORCAMENTO E A SOMA, e nao o job: 64 nucleos e 192 GB somados sobre tudo o
# que estiver rodando ao mesmo tempo. Como o dimensionamento usa 3 GB por
# nucleo, a memoria segue sozinha se os nucleos forem respeitados: basta contar
# `ppn`.
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
ORCAMENTO="${ORCAMENTO:-64}"          # nucleos somados; NAO aumente sem combinar
WALLTIME="${WALLTIME:-12:00:00}"
RODAR="no"
[[ "${1:-}" == "--rodar" ]] && RODAR="sim"

: "${BDGD2DSS_BASES:?defina onde estao as .gdb}"

echo "=============================================================="
echo " SUBMISSAO EM ONDAS — orcamento de $ORCAMENTO nucleos"
echo "=============================================================="
echo "sufixo   : $SUFIXO"
echo "fila     : $FILA"
echo "bases    : ${SO:-todas as encontradas}"
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
python - "$DISPONIVEL" <<'PY' > /tmp/plano_ondas.txt
import os, sys
sys.path.insert(0, ".")
import regerar_v10 as r

teto = int(sys.argv[1])
so = {x for x in os.environ.get("SO", "").split() if x}

bases = []
for tag, cam, _ in r.BASES:
    if so and tag not in so:
        continue
    gb = sum(os.path.getsize(os.path.join(d, f))
             for d, _, fs in os.walk(cam) for f in fs) / 2**30
    if   gb <  1: ppn, mem = 4, 12
    elif gb <  5: ppn, mem = 8, 24
    elif gb < 20: ppn, mem = 16, 48
    else:         ppn, mem = 32, 96
    bases.append((tag, ppn, mem, gb))

# CORRENTE = fila sequencial. O custo simultaneo de uma corrente e o MAIOR ppn
# dela, porque so um job dela roda por vez. O teto vale sobre a soma desses
# maiores — e isso e verificavel sem saber quanto cada base demora.
bases.sort(key=lambda x: -x[1])
correntes = []           # cada uma: [maior_ppn, [(tag, ppn, mem), ...]]
for tag, ppn, mem, gb in bases:
    posto = next((c for c in correntes if c[0] >= ppn), None)
    if posto is None:
        if sum(c[0] for c in correntes) + ppn <= teto:
            correntes.append([ppn, []])
            posto = correntes[-1]
        else:
            posto = min(correntes, key=lambda c: len(c[1])) if correntes else None
            if posto is None:
                print("ERRO: nem a menor base cabe no teto de %d" % teto)
                raise SystemExit(1)
    posto[1].append((tag, ppn, mem))

print("CORRENTES %d" % len(correntes))
print("PICO %d" % sum(c[0] for c in correntes))
for i, (mx, itens) in enumerate(correntes, 1):
    print("CHAIN %d %d %s" % (i, mx, " ".join("%s:%d:%d" % t for t in itens)))
PY

CORRENTES=$(awk '/^CORRENTES/{print $2}' /tmp/plano_ondas.txt)
PICO=$(awk '/^PICO/{print $2}' /tmp/plano_ondas.txt)

echo "plano: $CORRENTES correntes, pico de $PICO nucleos simultaneos (teto $ORCAMENTO)"
echo
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
        id=$(qsub -N "b_$TAG" -q "$FILA" \
             -l nodes=1:ppn="$PPN" -l mem="${MEM}gb" -l walltime="$WALLTIME" \
             $DEP \
             -v "TAG=$TAG,SUFIXO=$SUFIXO,PROJETO=$PWD,BDGD2DSS_BASES=$BDGD2DSS_BASES,BDGD2DSS_COMMIT=$COMMIT,BDGD2DSS_DESCRICAO=$DESCRICAO" \
             cluster/uma_base.pbs)
        printf "  corrente %-2s  %-18s ppn=%-3s mem=%-4s -> %s\n" "$n" "$TAG" "$PPN" "${MEM}gb" "$id"
        ANT="$id"
    done
done < <(grep '^CHAIN' /tmp/plano_ondas.txt)

echo
echo "acompanhe com:  qstat -an -u \$USER"
echo "nucleos em uso: qstat -u \$USER -f | tr -d ' ' | grep -o 'Resource_List.ncpus=[0-9]*' | cut -d= -f2 | paste -sd+ - | bc"
