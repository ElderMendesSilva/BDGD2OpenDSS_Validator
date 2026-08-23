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
# O SUFIXO PADRAO DIZ ONDE A RODADA ACONTECEU. Antes caia em V18, que e uma
# rodada FECHADA e serve de referencia: quem submetesse sem definir gravava por
# cima dela em silencio, e so descobriria ao comparar geracoes e achar as duas
# iguais. `V1_cluster` nao colide com a numeracao local (V10, V18, V19...) e a
# pasta ja diz de onde veio — MODELOS_CMIG_V1_cluster.
#
# Continua dando para mandar outro: SUFIXO=V2_cluster bash cluster/submeter_todas.sh
SUFIXO="${SUFIXO:-V1_cluster}"

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
