#!/usr/bin/env bash
# INSTALA TUDO o que a ferramenta precisa, sem root, num no de cluster.
#
#     bash cluster/instalar.sh                  instala e confere
#     bash cluster/instalar.sh --offline        usa as rodas de cluster/rodas/
#     PYTHON=/opt/py312/bin/python3 bash cluster/instalar.sh
#
# O QUE ELE INSTALA
#   Python 3.9+        se o do sistema nao servir, baixa um proprio (micromamba)
#   numpy, pyogrio     leitura da .gdb; o GDAL vem embutido na roda do pyogrio
#   opendssdirect.py   O MOTOR ELETRICO JA VEM AQUI. Ver a nota abaixo.
#   matplotlib         figuras (opcional; sem ela o resto roda)
#
# O QUE ELE NAO INSTALA, E NAO E ESQUECIMENTO
#
#   O MOTOR COM DA EPRI NAO EXISTE EM LINUX. Ele e um servidor COM registrado
#   no Windows; nao ha versao, porte ou equivalente para Linux. Nao adianta
#   `pip install pywin32` — falha, e nao e para tentar.
#
#   Isso NAO deixa a ferramenta sem motor. O `opendssdirect.py` traz a DSS
#   C-API, que e o mesmo OpenDSS compilado como biblioteca (`libdss_capi.so`,
#   dentro da propria roda). E o motor que faz todas as contas do projeto.
#
#   O que se perde e a CONFERENCIA CRUZADA entre dois motores independentes,
#   que o `verifica` faz no Windows. No cluster ele roda com um motor so e diz
#   isso no rodape, em vez de fingir que houve confronto. Nenhum resultado do
#   projeto depende do COM: ele e auditoria, nao producao.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AQUI"
OFFLINE=0
[[ "${1:-}" == "--offline" ]] && OFFLINE=1

MIN_MAIOR=3
MIN_MENOR=9

diz() { printf '\n=== %s\n' "$*"; }

serve() {
    # Python utilizavel: existe, roda, e e novo o bastante.
    local py="$1"
    [[ -x "$(command -v "$py" 2>/dev/null || true)" ]] || return 1
    "$py" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_MAIOR, $MIN_MENOR) else 1)" 2>/dev/null
}

# ---------------------------------------------------------------- 1. Python
diz "procurando um Python $MIN_MAIOR.$MIN_MENOR ou mais novo"
PY=""
for cand in "${PYTHON:-}" python3 python3.13 python3.12 python3.11 python3.10 python3.9; do
    [[ -n "$cand" ]] || continue
    if serve "$cand"; then PY="$(command -v "$cand")"; break; fi
done

# Num cluster o Python util quase sempre esta atras de um `module`. Tentar
# antes de baixar qualquer coisa e o caminho educado: usa o que o laboratorio
# ja mantem, com as bibliotecas de sistema certas para aquele hardware.
if [[ -z "$PY" ]] && command -v module >/dev/null 2>&1; then
    diz "nenhum no PATH; tentando \`module load\`"
    for m in python/3.12 python/3.11 python/3.10 python3 python anaconda3; do
        if module load "$m" >/dev/null 2>&1 && serve python3; then
            PY="$(command -v python3)"
            echo "    module load $m"
            break
        fi
    done
fi

# Ultimo recurso: um Python proprio, na pasta do usuario, sem root e sem
# depender de nada do sistema. Micromamba e um binario unico de ~5 MB.
if [[ -z "$PY" ]]; then
    diz "instalando um Python proprio (micromamba), sem root"
    [[ $OFFLINE -eq 1 ]] && { echo "modo offline e sem Python: instale um antes"; exit 1; }
    export MAMBA_ROOT_PREFIX="$AQUI/.micromamba"
    mkdir -p "$MAMBA_ROOT_PREFIX"
    if [[ ! -x "$MAMBA_ROOT_PREFIX/bin/micromamba" ]]; then
        curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
            | tar -xvj -C "$MAMBA_ROOT_PREFIX" bin/micromamba
    fi
    "$MAMBA_ROOT_PREFIX/bin/micromamba" create -y -p "$AQUI/.venv" \
        -c conda-forge "python=3.12" >/dev/null
    PY="$AQUI/.venv/bin/python"
    JA_TEM_AMBIENTE=1
fi

echo "    Python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

# ------------------------------------------------------------- 2. ambiente
if [[ -z "${JA_TEM_AMBIENTE:-}" ]]; then
    diz "criando o ambiente em .venv"
    [[ -d .venv ]] || "$PY" -m venv .venv
fi
VPY="$AQUI/.venv/bin/python"
"$VPY" -m pip install --quiet --upgrade pip

diz "instalando as bibliotecas"
if [[ $OFFLINE -eq 1 ]]; then
    # Nos de calculo costumam nao ter internet. Baixe as rodas antes, numa
    # maquina que tenha (o comando esta em docs/CLUSTER.md), e traga a pasta.
    "$VPY" -m pip install --no-index --find-links cluster/rodas -r requirements.txt
else
    "$VPY" -m pip install -r requirements.txt
fi

# ------------------------------------------------------- 3. o motor mesmo
# `pip install` que termina sem erro nao garante motor que funciona: a roda
# pode nao trazer a .so da arquitetura do no. Melhor descobrir agora.
diz "conferindo o motor eletrico"
"$VPY" - <<'PY'
import opendssdirect as dss
dss.Text.Command('Clear')
dss.Text.Command('New Circuit.T basekv=13.8 phases=3 bus1=f')
dss.Text.Command('New Linecode.lc nphases=3 r1=0.5 x1=0.4 units=km')
dss.Text.Command('New Line.l1 bus1=f bus2=b linecode=lc length=0.1 units=km')
dss.Text.Command('New Load.c1 bus1=b phases=3 kV=13.8 kW=100')
dss.Text.Command('Set Voltagebases=[13.8]')
dss.Text.Command('Calcvoltagebases')
dss.Text.Command('Solve')
assert dss.Solution.Converged(), 'o motor compila mas nao resolve'
print('   ', dss.Basic.Version()[:70])
PY

# --------------------------------------------------------- 4. autoteste
diz "autoteste da maquina"
"$VPY" etapas/doutor.py --bases "${BDGD2DSS_BASES:-}" || true

cat <<FIM

=== pronto ===
  source .venv/bin/activate
  export BDGD2DSS_BASES=/caminho/para/as/gdb
  python etapas/doutor.py
  qsub -v TAG=RR,SUFIXO=V1_cluster cluster/uma_base.pbs   # a Roraima primeiro, sempre

FIM
