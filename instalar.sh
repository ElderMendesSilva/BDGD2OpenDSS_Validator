#!/usr/bin/env bash
# INSTALA TUDO para rodar o BDGD -> OpenDSS numa maquina nova.
#
#     bash instalar.sh              mostra o que falta e o que faria
#     bash instalar.sh --sim        instala de verdade
#     bash instalar.sh --conferir   so confere, nunca instala
#
# POR PADRAO ELE NAO INSTALA NADA. Instalar software mexe na maquina de quem
# roda, e um script que sai instalando sem avisar e a forma mais rapida de
# alguem perder a confianca nele. Sem `--sim` ele lista o que falta, diz o
# comando de cada item e para.
#
# O QUE ELE CUIDA
#
#   Python 3.9+          a base de tudo
#   numpy, pyogrio       leitura da .gdb — o GDAL vem embutido na roda
#   opendssdirect.py     O MOTOR ELETRICO. Ja e o OpenDSS compilado como
#                        biblioteca (DSS C-API); nao precisa instalar o
#                        OpenDSS a parte para o projeto funcionar
#   matplotlib           as figuras do relatorio
#   reportlab, Pillow    o PDF escrito
#   openpyxl             planilhas da transmissora
#   pywin32              SO NO WINDOWS: o motor COM da EPRI, usado pelo
#                        `verifica` para a conferencia cruzada entre dois
#                        motores independentes
#   OpenDSS (EPRI)       SO NO WINDOWS: o programa oficial, com a interface
#                        grafica e o COM. E o que registra o `OpenDSSEngine.DSS`
#   Notepad++            SO NO WINDOWS: para abrir os `.dss` sem que o editor
#                        troque o fim de linha
#
# NO LINUX o COM e o OpenDSS da EPRI NAO EXISTEM, e isso nao e limitacao do
# script: o COM e um servidor registrado no Windows, sem porte. A ferramenta
# roda inteira com a DSS C-API, e o `verifica` avisa no rodape que comparou um
# motor so em vez de fingir que houve confronto.
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AQUI"

MODO="mostrar"
case "${1:-}" in
    --sim) MODO="instalar" ;;
    --conferir) MODO="conferir" ;;
    '') ;;
    *) echo "opcao desconhecida: $1"; sed -n '2,8p' "$0"; exit 2 ;;
esac

# ------------------------------------------------------------------ o sistema
# `OSTYPE` e `uname` discordam no Git Bash: `uname` diz MINGW64 e e o que
# importa, porque ali existe `winget` e o Python do Windows.
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) SISTEMA="windows" ;;
    Darwin) SISTEMA="mac" ;;
    *) SISTEMA="linux" ;;
esac

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
    for c in python python3 py; do
        if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
    done
fi

echo "=============================================================="
echo " BDGD -> OpenDSS — instalacao"
echo "=============================================================="
echo "sistema : $SISTEMA"
echo "python  : ${PY:-<nao encontrado>}"
if [[ -n "$PY" ]]; then
    echo "versao  : $("$PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null || echo '?')"
fi
echo "modo    : $MODO"
echo

falta=0
pendentes=()

# --------------------------------------------------------------- os pacotes
# `import` e o teste que importa: pacote que instala e nao importa (roda errada
# para a arquitetura, DLL faltando) passaria numa checagem por `pip show`.
confere_py() {
    local mod="$1" nome="$2" obrig="$3"
    if [[ -z "$PY" ]]; then return; fi
    if "$PY" -c "import $mod" >/dev/null 2>&1; then
        printf '  %-16s ok\n' "$nome"
    else
        if [[ "$obrig" == "sim" ]]; then
            printf '  %-16s FALTA (obrigatorio)\n' "$nome"
            falta=$((falta + 1))
        else
            printf '  %-16s falta (opcional)\n' "$nome"
        fi
        pendentes+=("$nome")
    fi
}

echo "-- bibliotecas de Python --"
confere_py numpy numpy sim
confere_py pyogrio pyogrio sim
confere_py opendssdirect 'opendssdirect.py' sim
confere_py matplotlib matplotlib nao
confere_py reportlab reportlab nao
confere_py PIL Pillow nao
confere_py openpyxl openpyxl nao
if [[ "$SISTEMA" == "windows" ]]; then
    confere_py win32com pywin32 nao
fi
echo

# ------------------------------------------------------- programas do Windows
if [[ "$SISTEMA" == "windows" ]]; then
    echo "-- programas (Windows) --"
    if [[ -d "/c/Program Files/OpenDSS" || -d "/c/OpenDSS" ]]; then
        echo "  OpenDSS (EPRI)   ok"
    else
        echo "  OpenDSS (EPRI)   falta (opcional — a DSS C-API ja e o motor)"
        pendentes+=("OpenDSS")
    fi
    if command -v notepad++ >/dev/null 2>&1 \
       || [[ -f "/c/Program Files/Notepad++/notepad++.exe" ]]; then
        echo "  Notepad++        ok"
    else
        echo "  Notepad++        falta (opcional)"
        pendentes+=("Notepad++")
    fi
    echo
fi

# --------------------------------------------------------------- o que fazer
if [[ ${#pendentes[@]} -eq 0 ]]; then
    echo "Nada a instalar."
else
    echo "Faltam: ${pendentes[*]}"
    echo
fi

if [[ "$MODO" == "conferir" ]]; then
    exit $(( falta > 0 ? 1 : 0 ))
fi

if [[ "$MODO" == "mostrar" ]]; then
    echo "O que seria feito (rode com --sim para executar):"
    echo
    [[ -z "$PY" ]] && echo "    instalar o Python 3.12 (winget install Python.Python.3.12)"
    echo "    $PY -m pip install -r requirements.txt"
    if [[ "$SISTEMA" == "windows" ]]; then
        echo "    $PY -m pip install pywin32          # motor COM da EPRI"
        echo "    winget install --id EPRI.OpenDSS    # o OpenDSS oficial"
        echo "    winget install --id Notepad++.Notepad++"
    fi
    echo
    echo "Nada foi instalado."
    exit 0
fi

# ----------------------------------------------------------------- instalando
if [[ -z "$PY" ]]; then
    echo "Python nao encontrado. No Windows:"
    echo "    winget install --id Python.Python.3.12"
    echo "No Linux, use o gerenciador da distribuicao ou o cluster/instalar.sh."
    exit 1
fi

echo ">> instalando as bibliotecas"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt || exit 1

if [[ "$SISTEMA" == "windows" ]]; then
    echo ">> pywin32 (motor COM)"
    "$PY" -m pip install pywin32 || echo "   pywin32 falhou — o projeto roda sem ele"
    if command -v winget >/dev/null 2>&1; then
        echo ">> OpenDSS da EPRI e Notepad++ (winget)"
        # `--silent` e `--accept-*` porque sem eles o winget abre dialogo e o
        # script fica pendurado esperando alguem clicar.
        winget install --id EPRI.OpenDSS --silent \
            --accept-package-agreements --accept-source-agreements || true
        winget install --id Notepad++.Notepad++ --silent \
            --accept-package-agreements --accept-source-agreements || true
    else
        echo "   winget nao encontrado — instale o OpenDSS e o Notepad++ a mao:"
        echo "     https://sourceforge.net/projects/electricdss/"
        echo "     https://notepad-plus-plus.org/downloads/"
    fi
fi

echo
echo ">> conferindo"
bash "$0" --conferir
rc=$?
if [[ $rc -eq 0 ]]; then
    echo
    echo "Pronto. Para comecar:  $PY Validator.py"
fi
exit $rc
