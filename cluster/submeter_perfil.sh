#!/usr/bin/env bash
# Submete o perfil de violacao de UMA base, opcionalmente depois de outro job.
#
#     SUFIXO=V24 BASE=COPELDIS2866 bash cluster/submeter_perfil.sh
#     SUFIXO=V24 BASE=COPELDIS2866 DEPOIS=34572 bash cluster/submeter_perfil.sh
#     SUFIXO=V24 BASE=COPELDIS2866 \
#         MOTIVO="modelo quebrado na SE" bash cluster/submeter_perfil.sh
#
# `DEPOIS` e o id do coletor: o perfil le `resultados/<sufixo>/`, que so existe
# quando o coletor termina. Sem encadear, o job morre sem achar o CSV.
#
# MOSTRA ANTES DE FAZER, como o `submeter_todas.sh`: sem `--rodar` imprime o
# comando exato e nao submete. Quem submete e voce.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FILA="${FILA:-BIRA_Q3}"
: "${SUFIXO:?defina SUFIXO, ex: SUFIXO=V24}"
: "${BASE:?defina BASE, ex: BASE=COPELDIS2866}"
: "${BDGD2DSS_BASES:?defina onde estao as .gdb}"
WALLTIME="${WALLTIME:-02:00:00}"
RODAR="no"
[[ "${1:-}" == "--rodar" ]] && RODAR="sim"

DEP=""
[[ -n "${DEPOIS:-}" ]] && DEP="-W depend=afterany:$DEPOIS"

mkdir -p logs/cluster
echo "base    : $BASE"
echo "sufixo  : $SUFIXO"
echo "motivo  : ${MOTIVO:-<todos>}"
echo "depende : ${DEPOIS:-<nada>}"
echo

if [[ $RODAR != sim ]]; then
    echo "nada submetido. Para submeter:"
    echo "    SUFIXO=$SUFIXO BASE=$BASE${DEPOIS:+ DEPOIS=$DEPOIS}" \
         "bash cluster/submeter_perfil.sh --rodar"
    exit 0
fi

ID=$(qsub -N "perfil_$BASE" -q "$FILA" \
     -l nodes=1:ppn=2 -l mem=24gb -l walltime="$WALLTIME" \
     -j oe -o logs/cluster/ $DEP \
     -v "PROJETO=$PWD,BASE=$BASE,SUFIXO=$SUFIXO,MOTIVO=${MOTIVO:-},BDGD2DSS_BASES=$BDGD2DSS_BASES" \
     cluster/perfil.pbs)
echo "perfil submetido: $ID"
