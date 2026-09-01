#!/usr/bin/env bash
# Submete a medicao de FRAGMENTACAO (componentes conexas por subestacao).
#
#     bash cluster/submeter_recorte.sh            # so mostra
#     bash cluster/submeter_recorte.sh --rodar
#     DEPOIS=34572 bash cluster/submeter_recorte.sh --rodar
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

# AS ASPAS SIMPLES EM ARGS NAO SAO ENFEITE. No `-v` do PBS a VIRGULA separa
# variaveis e o espaco termina o valor, entao `ARGS=--so CMIG SP` chegaria
# truncado em "--so". Com aspas simples o valor viaja inteiro. Por isso ARGS
# nao pode conter virgula — se um dia precisar, passe por arquivo.
mkdir -p logs/cluster
echo "bases   : $BDGD2DSS_BASES"
echo "depende : ${DEPOIS:-<nada>}"
echo "argumentos: ${ARGS:-<padrao: as 97 bases, agregado>}"
echo

if [[ $RODAR != sim ]]; then
    echo "nada submetido. Para submeter:"
    echo "    ${DEPOIS:+DEPOIS=$DEPOIS }bash cluster/submeter_recorte.sh --rodar"
    exit 0
fi

ID=$(qsub -N recorte -q "$FILA" \
     -l nodes=1:ppn=4 -l mem=48gb -l walltime="$WALLTIME" \
     -j oe -o logs/cluster/ $DEP \
     -v "PROJETO=$PWD,BDGD2DSS_BASES=$BDGD2DSS_BASES,ARGS='${ARGS:-}'" \
     cluster/recorte.pbs)
echo "medicao submetida: $ID"
