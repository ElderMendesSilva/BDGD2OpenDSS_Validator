#!/usr/bin/env bash
# RECONHECIMENTO DO NO — roda isto ANTES de qualquer outra coisa.
#
#     bash cluster/primeiro_contato.sh
#     bash cluster/primeiro_contato.sh > contato.txt   e me manda o arquivo
#
# Ele NAO instala, NAO submete e NAO escreve nada fora da tela. So pergunta.
#
# POR QUE EXISTE. Os nossos scripts tem valores que vieram de conversa e nao
# de medicao: a fila `BIRA_Q3`, `ppn=32`, `walltime=12:00:00`. Se algum
# estiver errado, o `qsub` ou recusa na hora — o que e barato — ou aceita e
# mata o job no fim, depois de horas, que e o caro.
#
# Cada pergunta aqui ja custou tempo de alguem em algum cluster.
echo "=============================================================="
echo " RECONHECIMENTO — $(date '+%d/%m/%Y %H:%M')"
echo "=============================================================="

secao() { printf '\n--- %s\n' "$*"; }

secao "1. onde estou"
echo "maquina : $(hostname -f 2>/dev/null || hostname)"
echo "usuario : $(whoami)"
echo "home    : $HOME"
echo "sistema : $(cat /etc/os-release 2>/dev/null | grep -m1 PRETTY_NAME | cut -d= -f2- | tr -d '\"')"

secao "2. o PBS existe? e qual?"
# Torque e PBS Pro respondem diferente; os dois entendem qsub/qstat/qdel.
for c in qsub qstat qdel pbsnodes tracejob; do
    printf '  %-10s %s\n' "$c" "$(command -v $c 2>/dev/null || echo 'NAO EXISTE')"
done
qstat --version 2>&1 | head -2

secao "3. AS FILAS — e o nome certo de uma delas vai para o .pbs"
# O `uma_base.pbs` tem BIRA_Q3 como padrao. Se nao estiver na lista abaixo,
# TROQUE, ou o qsub recusa.
qstat -q 2>&1 | head -25

secao "4. os limites de cada fila (walltime, nucleos, memoria)"
# O nosso job pede walltime=12:00:00 e ppn=32. Se o teto da fila for menor,
# o job e RECUSADO — melhor descobrir agora.
qmgr -c "print server" 2>/dev/null | grep -Ei 'resources_max|resources_default|queue ' | head -30 \
  || echo "  (qmgr sem permissao — normal para usuario; use o qstat -Qf abaixo)"
qstat -Qf 2>/dev/null | grep -Ei 'Queue:|resources_max|resources_default|max_running' | head -30

secao "5. os nos: quantos nucleos e quanta memoria de verdade"
# `ppn=32` so faz sentido se existir no com 32. E a memoria e o que limita a
# Cemig-D, nao o nucleo.
pbsnodes -a 2>/dev/null | grep -E 'np =|status = |resources_available' | head -12 \
  || echo "  (pbsnodes indisponivel para usuario)"
echo "  neste no de acesso: $(nproc 2>/dev/null) nucleos, $(free -g 2>/dev/null | awk '/^Mem:/{print $2}') GB"

secao "6. python — a ferramenta pede 3.9 ou mais"
for p in python3 python python3.12 python3.11 python3.10 python3.9; do
    v="$(command -v $p 2>/dev/null)" && printf '  %-12s %s  (%s)\n' "$p" "$v" "$($p -V 2>&1)"
done
command -v module >/dev/null 2>&1 && { echo "  ha 'module' — modulos de python disponiveis:"; module avail 2>&1 | grep -i python | head -5; }

secao "7. TEM INTERNET? decide se subimos 44 GB ou baixamos direto aqui"
# Se houver, NAO vale a pena subir as .gdb daqui: baixar da ANEEL no proprio
# no e mais rapido e vem com a integridade do servidor deles.
if command -v curl >/dev/null 2>&1; then
    curl -s -o /dev/null -w '  pypi.org      -> %{http_code} em %{time_total}s\n' --max-time 8 https://pypi.org/simple/ || echo "  pypi.org      -> SEM ACESSO"
    curl -s -o /dev/null -w '  dadosabertos  -> %{http_code} em %{time_total}s\n' --max-time 8 https://dadosabertos.aneel.gov.br/ || echo "  dadosabertos  -> SEM ACESSO"
    curl -s -o /dev/null -w '  github.com    -> %{http_code} em %{time_total}s\n' --max-time 8 https://github.com/ || echo "  github.com    -> SEM ACESSO"
else
    echo "  curl nao existe; tentando wget"
    command -v wget >/dev/null 2>&1 && wget -q --spider --timeout=8 https://pypi.org && echo "  pypi.org OK" || echo "  SEM ACESSO"
fi

secao "8. ONDE CABEM 44 GB de .gdb mais ~30 GB de modelos"
# O $HOME de cluster costuma ter cota apertada. O scratch e o lugar certo.
df -h "$HOME" 2>/dev/null | tail -1 | awk '{print "  $HOME       "$4" livres de "$2}'
for d in /scratch /work /lustre /tmp "/scratch/$(whoami)" "/work/$(whoami)"; do
    [[ -d "$d" ]] && df -h "$d" 2>/dev/null | tail -1 | awk -v n="$d" '{printf "  %-12s %s livres de %s\n", n, $4, $2}'
done
command -v quota >/dev/null 2>&1 && { echo "  cota:"; quota -s 2>/dev/null | head -4; }

secao "9. ferramentas que o envio precisa"
for c in git rsync unzip zip sha256sum tar; do
    printf '  %-10s %s\n' "$c" "$(command -v $c 2>/dev/null || echo 'FALTA')"
done

echo
echo "=============================================================="
echo " Manda esta saida inteira. Com ela eu ajusto a fila, o ppn, o"
echo " walltime e o caminho das bases antes de submeter qualquer job."
echo "=============================================================="
