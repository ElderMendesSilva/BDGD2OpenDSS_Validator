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
# O SUFIXO NAO TEM PADRAO, E DE PROPOSITO. Ele cai em V18 antes, e V18 e uma
# rodada FECHADA que serve de referencia. Quem submetesse sem definir gravava
# por cima dela em silencio, e so descobriria ao comparar geracoes e achar as
# duas iguais. Sem padrao, o script recusa e diz o que fazer.
SUFIXO="${SUFIXO:?defina o sufixo da rodada, ex.: SUFIXO=V20 bash cluster/submeter_todas.sh}"

echo "filas disponiveis (confira o nome antes de submeter):"
qstat -q || true
echo

# As bases sao descobertas na pasta, e nao listadas aqui: qualquer *.gdb
# em BDGD2DSS_BASES entra. Assim vale para as sete de hoje e para as 53
# do pais sem editar script nenhum.
TAGS=$(python -c "import regerar_v10 as r; print(' '.join(t for t,_,_ in r.BASES))")
echo "bases encontradas: $TAGS"
echo
for TAG in $TAGS; do
    id=$(qsub -q "$FILA" -N "bdgd_$TAG" \
              -v "TAG=$TAG,SUFIXO=$SUFIXO,PROJETO=$PWD,BDGD2DSS_BASES=${BDGD2DSS_BASES:-$HOME/elder/bdgds}" \
              cluster/uma_base.pbs)
    echo "  $TAG -> $id"
done

echo
echo "acompanhe com:  qstat -an -u \$USER"
echo "saida em:       logs/cluster/"
