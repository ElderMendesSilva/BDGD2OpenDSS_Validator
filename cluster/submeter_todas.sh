#!/usr/bin/env bash
# Submete as sete distribuidoras, uma por job.
#
#     bash cluster/submeter_todas.sh
#     FILA=BIRA_Q4 SUFIXO=V16 bash cluster/submeter_todas.sh
#
# Uma por job, e nao um job so com as sete: elas sao independentes, entao sete
# jobs entram na fila em paralelo e cada um termina quando terminar. Num job
# unico a Cemig-D seguraria as outras seis ate o fim.
#
# A ORDEM E CANARIO PRIMEIRO. Roraima leva menos de um minuto de conversao. Se
# o codigo estiver quebrado, isso aparece nela — e nao depois de horas de
# Cemig-D. Submeter tudo de uma vez desperdicaria a fila inteira num defeito
# que a menor base mostraria em segundos.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
FILA="${FILA:-BIRA_Q3}"
SUFIXO="${SUFIXO:-V15}"

echo "filas disponiveis (confira o nome antes de submeter):"
qstat -q || true
echo

for TAG in RR ENCE EQPA SP LT CPFL CMIG; do
    id=$(qsub -q "$FILA" -N "bdgd_$TAG" \
              -v "TAG=$TAG,SUFIXO=$SUFIXO,PROJETO=$PWD,BDGD2DSS_BASES=${BDGD2DSS_BASES:-$HOME/elder/bdgds}" \
              cluster/uma_base.pbs)
    echo "  $TAG -> $id"
done

echo
echo "acompanhe com:  qstat -an -u \$USER"
echo "saida em:       logs/cluster/"
