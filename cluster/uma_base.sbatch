#!/bin/bash
# Uma base por tarefa. As sete sao independentes: nao trocam nada entre si,
# entao nao ha MPI e nao se usa a InfiniBand — e um vetor de tarefas comum.
#
#     sbatch --array=0-6 cluster/uma_base.sbatch
#     sbatch --array=0 cluster/uma_base.sbatch        # so a Roraima, canario
#
# O indice do vetor escolhe a base, na ordem de BASES do regerar_v10.py:
#     0 RR   1 ENCE   2 EQPA   3 SP   4 LT   5 CPFL   6 CMIG
#
#SBATCH --job-name=bdgd2dss
#SBATCH --output=logs/cluster/%x-%A_%a.out
#SBATCH --error=logs/cluster/%x-%A_%a.out
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=12:00:00

set -euo pipefail

# --- o que muda de instalacao para instalacao -------------------------------
PROJETO="${PROJETO:-$HOME/BDGD2OpenDSS}"
export BDGD2DSS_BASES="${BDGD2DSS_BASES:-$HOME/bdgds}"
SUFIXO="${SUFIXO:-V15}"

# `cluster` tambem seria detectado sozinho pelo SLURM_JOB_ID; explicito e
# melhor num script que alguem vai ler daqui a um ano.
export BDGD2DSS_MODO=cluster

cd "$PROJETO"
mkdir -p logs/cluster

TAGS=(RR ENCE EQPA SP LT CPFL CMIG)
TAG="${TAGS[${SLURM_ARRAY_TASK_ID:-0}]}"

echo "=== $TAG em $(hostname), $(date '+%d/%m %H:%M') ==="
echo "=== ${SLURM_CPUS_PER_TASK:-?} nucleos, $(free -g 2>/dev/null | awk '/^Mem:/{print $7}') GB livres ==="

# O autoteste custa segundos e evita a falha classica: a tarefa espera na
# fila, comeca de madrugada, e morre no minuto 2 por falta de biblioteca.
python doutor.py --bases "$BDGD2DSS_BASES" || exit 1

# --jobs 0 deixa o proprio codigo decidir: o menor entre os nucleos da fatia
# e a memoria disponivel dividida por processo. Passar um numero na mao aqui
# e a forma mais facil de fazer o no paginar.
python -u regerar_v10.py --sufixo "$SUFIXO" --so "$TAG" --jobs 0

echo "=== $TAG terminou em $(date '+%d/%m %H:%M') ==="
