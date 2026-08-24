#!/usr/bin/env bash
# Leva o projeto e as BDGDs para o no do cluster.
#
#     bash cluster/enviar.sh elder@ubiratan                  as sete
#     bash cluster/enviar.sh elder@ubiratan RR               so a canario
#     DESTINO=/scratch/elder bash cluster/enviar.sh elder@ubiratan
#
# O CODIGO NAO VAI POR AQUI, e de proposito: ele vai por `git clone`. Copiar
# codigo por scp cria a duvida "qual versao esta rodando la?" — e essa duvida
# custa uma rodada inteira quando o resultado diverge. O `.pbs` carimba o
# commit no cabecalho do log justamente para responder isso.
#
#     git clone https://github.com/ElderMendesSilva/BDGD2OpenDSS_Validator
#     cd BDGD2OpenDSS_Validator && bash cluster/instalar.sh
#
# O QUE VAI POR AQUI SAO AS .gdb, e elas sao o volume:
#
#     Cemig-D        14,83 GB        Equatorial PA   3,98 GB
#     Enel SP         8,15 GB        Roraima         0,32 GB
#     CPFL Paulista   6,35 GB        ------------------------
#     Enel CE         5,35 GB        as sete        44,3 GB
#     Light           5,26 GB
#
# PORQUE COMPACTAR ANTES: a .gdb e uma PASTA com ~209 arquivos, e a maioria
# comprime bem — a Cemig-D vai de 14,83 GB para 4,09 GB, 3,6x. Mandar as sete
# cruas sao 44,3 GB; compactadas, cerca de 12 GB. Numa linha domestica isso e
# a diferenca entre uma noite e tres.
#
# A ALTERNATIVA MELHOR, SE O NO TIVER INTERNET: nao mandar nada. Baixar as
# .gdb direto da ANEEL no proprio no e mais rapido que subir daqui, e vem com
# a integridade do servidor deles. So vale a pena mandar daqui quando o no
# nao alcanca a internet, que e o caso de muitos clusters academicos.
#
#     https://dadosabertos-aneel.opendata.arcgis.com/search?tags=distribuicao
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALVO="${1:?uso: bash cluster/enviar.sh usuario@maquina [TAG ...]}"
shift || true
DESTINO="${DESTINO:-\$HOME/bdgds}"
PACOTES="${PACOTES:-envio_bdgd}"

# As pastas onde as .gdb moram nesta maquina. A mesma variavel que o
# `regerar_v10` usa, e pelo mesmo motivo: caminho de maquina nao vai no codigo.
PASTAS="${BDGD2DSS_BASES:-}"
if [[ -z "$PASTAS" ]]; then
    echo "defina BDGD2DSS_BASES com as pastas das .gdb, separadas por ':'" >&2
    exit 1
fi

mkdir -p "$PACOTES"
IFS=':' read -ra DIRS <<< "$PASTAS"

enviar_uma() {
    local gdb="$1" nome zip
    nome="$(basename "$gdb")"
    zip="$PACOTES/$nome.tgz"
    if [[ ! -f "$zip" ]]; then
        echo "== compactando $nome"
        ( cd "$(dirname "$gdb")" && tar czf "$OLDPWD/$zip" "$nome" )
    fi
    # A soma de conferencia viaja junto. .gdb truncada no meio da subida nao
    # da erro na hora: ela da erro as 3 da manha, no minuto 2 do job.
    sha256sum "$zip" > "$zip.sha256"
    echo "== enviando $nome ($(du -h "$zip" | cut -f1))"
    # scp, e nao rsync: o Git Bash desta maquina NAO tem rsync (conferido
    # em 24/08/2026). Se um dia tiver, troque — ele RETOMA de onde parou, e
    # o scp recomeca do zero, o que numa .gdb de 4 GB e a diferenca entre
    # perder minutos e perder a tarde.
    scp -C "$zip" "$zip.sha256" "$ALVO:$DESTINO/"
}

echo "destino: $ALVO:$DESTINO"
ssh "$ALVO" "mkdir -p $DESTINO"

# Sem TAG na linha de comando, vao todas. Com TAG, so as que casarem — util
# para mandar a Roraima primeiro e provar o caminho antes de subir 44 GB.
for d in "${DIRS[@]}"; do
    [[ -d "$d" ]] || continue
    for gdb in "$d"/*.gdb; do
        [[ -d "$gdb" ]] || continue
        if [[ $# -gt 0 ]]; then
            casou=0
            for t in "$@"; do
                [[ "$(basename "$gdb")" == *"$t"* ]] && casou=1
            done
            [[ $casou -eq 1 ]] || continue
        fi
        enviar_uma "$gdb"
    done
done

cat <<FIM

Agora, NO NO:

    cd $DESTINO
    sha256sum -c *.sha256          # confere antes de descompactar
    for z in *.tgz; do tar xzf "\$z"; done
    rm -f *.tgz *.sha256           # so depois de conferir

    cd ~/BDGD2OpenDSS_Validator
    export BDGD2DSS_BASES=$DESTINO
    python doutor.py --bases "\$BDGD2DSS_BASES"

E so entao submeter. A Roraima primeiro, sempre:

    qsub -v TAG=RR,SUFIXO=V1_cluster cluster/uma_base.pbs
FIM
