# O cluster é um prompt — e os arquivos entram por fora dele

O modelo mental que faltava, e ele é simples: **você nunca sobe arquivo de
dentro do cluster.** Você abre um terminal na **sua** máquina e *empurra* para
lá, ou *puxa* de lá. São duas janelas diferentes:

```
   SUA MÁQUINA (Windows, Git Bash)          O NÓ (Linux, prompt do PBS)
   ----------------------------             --------------------------
   scp arquivo  elder@no:~/           ──►    o arquivo aparece em ~/
   scp elder@no:~/resultado.json .    ◄──    você puxa de volta
   ssh elder@no                       ──►    aqui você digita qsub, qstat...
```

O `ssh` te dá o prompt. O `scp` move arquivo. **São comandos separados, e os
dois rodam aqui, não lá.**

---

## Antes de tudo: a chave

Você ainda não tem uma. Gere aqui, uma vez só:

```bash
ssh-keygen -t ed25519 -C "elder-bdgd2dss"
```

Aperte Enter em tudo. Isso cria dois arquivos em `~/.ssh/`:

- `id_ed25519` — a **privada**. Nunca sai da sua máquina, nunca é enviada a
  ninguém, nem para mim.
- `id_ed25519.pub` — a **pública**. É esta que você manda para quem administra
  o Ubiratan, ou instala com:

```bash
ssh-copy-id elder@ubiratan          # se o comando existir
```

Sem `ssh-copy-id`, mande o conteúdo de `id_ed25519.pub` para o administrador.

Depois disso, `ssh elder@ubiratan` entra sem pedir senha.

---

## O que esta máquina tem, e o que não tem

Conferido em 24/08/2026, no Git Bash:

| ferramenta | |
|---|---|
| `ssh`, `scp`, `sftp`, `ssh-keygen` | **existem** |
| `tar` | existe (GNU tar 1.35) |
| `unzip` | existe |
| `rsync` | **NÃO existe** |
| `zip` | **NÃO existe** |

Por isso tudo aqui usa `scp` e `tar`, e não `rsync` e `zip`. Se um dia o
`rsync` aparecer, ele é melhor para arquivo grande — ele **retoma** de onde
parou, e o `scp` recomeça do zero.

---

## Subir: os três comandos que você vai usar

**Um arquivo:**

```bash
scp contato.txt elder@ubiratan:~/
```

**Uma BDGD inteira** — ela é uma *pasta* de ~209 arquivos, então compacta
antes; a Cemig-D vai de 14,83 GB para ~4 GB:

```bash
cd /d/Elder/Elder/BDGDs
tar czf Roraima.tgz Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb
scp Roraima.tgz elder@ubiratan:~/bdgds/
```

E **no nó**, para descompactar:

```bash
cd ~/bdgds && tar xzf Roraima.tgz && rm Roraima.tgz
```

> `cluster/enviar.sh` faz esses três passos para várias bases de uma vez.
> Comece pela Roraima: 0,32 GB, prova o caminho inteiro em minutos.

---

## Puxar de volta: e isso é barato

O que interessa **não** são os 30 GB de modelos — é o resumo. Puxe só os
`logs/` e os `.json`:

```bash
# da sua máquina, na pasta do projeto
scp -r elder@ubiratan:~/BDGD2OpenDSS_Validator/logs/v1_cluster ./logs/
scp elder@ubiratan:'~/BDGD2OpenDSS_Validator/MODELOS_*_V1_cluster/validacao_perdas.json' .
```

São kilobytes. Os modelos `.dss` ficam lá — eles se refazem a partir da `.gdb`
com um comando, e por isso não valem a banda.

---

## O ciclo inteiro, na ordem

```bash
# 1. AQUI: gerar a chave (uma vez na vida)
ssh-keygen -t ed25519 -C "elder-bdgd2dss"

# 2. AQUI: entrar
ssh elder@ubiratan

# 3. LÁ: reconhecer o terreno antes de qualquer coisa
git clone https://github.com/ElderMendesSilva/BDGD2OpenDSS_Validator
cd BDGD2OpenDSS_Validator
bash cluster/primeiro_contato.sh > contato.txt

# 4. AQUI, noutra janela: puxar o reconhecimento e me mandar
scp elder@ubiratan:~/BDGD2OpenDSS_Validator/contato.txt .

# 5. LÁ: instalar o ambiente
bash cluster/instalar.sh

# 6. AQUI: subir a Roraima só, para provar o caminho
bash cluster/enviar.sh elder@ubiratan RR

# 7. LÁ: conferir e submeter
export BDGD2DSS_BASES=$HOME/bdgds
python doutor.py --bases "$BDGD2DSS_BASES"
qsub -v TAG=RR,SUFIXO=V1_cluster cluster/uma_base.pbs
qstat -an -u $USER
```

**Só depois que a Roraima fechar lá** é que vale subir as outras seis. Ela
converte em menos de um minuto e exercita o caminho inteiro — ambiente,
leitura da `.gdb`, motor elétrico, escrita, fila.

---

## Os cinco comandos do PBS

| comando | |
|---|---|
| `qstat -q` | que filas existem |
| `qsub -v TAG=RR,SUFIXO=V1_cluster cluster/uma_base.pbs` | submete |
| `qstat -an -u $USER` | seus jobs: `Q` na fila, `R` rodando, `C` terminado |
| `qdel <n>` | mata o job `<n>` |
| `tracejob <n>` | por que ele morreu |

**Uma armadilha do PBS que já está tratada:** ele começa o job no `$HOME`, e
não na pasta de onde você submeteu. O `uma_base.pbs` faz
`cd "${PBS_O_WORKDIR:-$PROJETO}"` por causa disso.

**E uma que não está:** se você fechar o `ssh`, o job **continua** — ele é do
escalonador, não da sua sessão. Mas qualquer coisa que você rodar direto no
prompt (sem `qsub`) morre junto. Por isso `bash cluster/instalar.sh` deve ser
feito e esperado; conversão, nunca — sempre por `qsub`.
