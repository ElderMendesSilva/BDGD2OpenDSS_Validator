#!/usr/bin/env bash
# Submete a medicao de completude da BT das 97 bases.
#
#     bash cluster/submeter_ferro.sh            # so mostra
#     bash cluster/submeter_ferro.sh --rodar
#     DEPOIS=34572 bash cluster/submeter_ferro.sh --rodar
#
# Nao depende de rodada nenhuma: le a `.gdb` e mede. `DEPOIS` existe so para
# nao disputar nucleo com uma rodada em andamento — a medicao pode esperar.
#
# Um nucleo nao basta e trinta e dois nao ajudam: o trabalho e ler tabela
# grande em sequencia, entao o que importa e memoria para abrir a maior `.gdb`.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FILA="${FILA:-BIRA_Q3}"
: "${BDGD2DSS_BASES:?defina onde estao as .gdb}"
WALLTIME="${WALLTIME:-12:00:00}"
RODAR="no"
[[ "${1:-}" == "--rodar" ]] && RODAR="sim"

DEP=""
[[ -n "${DEPOIS:-}" ]] && DEP="-W depend=afterany:$DEPOIS"

mkdir -p logs/cluster
echo "bases   : $BDGD2DSS_BASES"
echo "depende : ${DEPOIS:-<nada>}"
echo "saida   : medicoes/ferro.json"
echo

if [[ $RODAR != sim ]]; then
    echo "nada submetido. Para submeter:"
    echo "    ${DEPOIS:+DEPOIS=$DEPOIS }bash cluster/submeter_ferro.sh --rodar"
    exit 0
fi

ID=$(qsub -N ferro -q "$FILA" \
     -l nodes=1:ppn=4 -l mem=48gb -l walltime="$WALLTIME" \
     -j oe -o logs/cluster/ $DEP \
     -v "PROJETO=$PWD,BDGD2DSS_BASES=$BDGD2DSS_BASES" \
     cluster/ferro.pbs)
echo "medicao submetida: $ID"
