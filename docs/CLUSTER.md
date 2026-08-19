# Rodar no cluster Ubiratan (UFPA/CEAMAZON)

Do zero até as sete bases regeradas. Escrito para ser seguido sem consultar
mais nada.

O gerenciador de filas é **PBS/Torque**, não Slurm — `qsub`, `qstat`, e
diretivas `#PBS` no cabeçalho do script.

## 0. Acesso

```bash
ssh <usuario>@10.107.1.23
```

Só de dentro da rede da UFPA/CEAMAZON, ou por VPN.

## 1. Instalar

Um comando, sem root:

```bash
git clone https://github.com/ElderMendesSilva/BDGD2OpenDSS_Validator.git
cd BDGD2OpenDSS_Validator
bash cluster/instalar.sh
```

O script resolve **tudo**, nesta ordem de preferência:

1. **Python.** Usa o do `PATH` se for 3.9+. Se não for, tenta `module load`
   (num cluster o Python bom quase sempre está atrás de um módulo, e usar o que
   o laboratório mantém é o caminho certo). Se ainda assim não houver, **baixa
   um Python próprio** com micromamba — um binário de ~5 MB, na pasta do
   usuário, sem root e sem depender de nada do sistema.
2. **O ambiente** em `.venv`.
3. **As bibliotecas** do `requisitos.txt`.
4. **Confere o motor elétrico de verdade** — compila e resolve um circuito. Um
   `pip install` que termina sem erro não garante motor que funciona: a wheel
   pode não trazer a `.so` da arquitetura do nó, e é melhor descobrir agora do
   que às 3 h da manhã.
5. **Roda o `doutor.py`.**

### O OpenDSS não precisa de instalação separada

`opendssdirect.py` **já traz o motor dentro da wheel** (`libdss_capi.so`). Não
há nada para compilar, registrar ou baixar à parte. `pyogrio` faz o mesmo com o
GDAL — não é preciso GDAL do sistema.

### O motor COM da EPRI não existe em Linux, e isso não é esquecimento

Ele é um **servidor COM registrado no Windows**. Não há versão, porte nem
equivalente para Linux, e `pip install pywin32` falha — não é para tentar.

**Isso não deixa a ferramenta sem motor.** A DSS C-API que vem no
`opendssdirect` é o mesmo OpenDSS compilado como biblioteca, e é ela que faz
todas as contas do projeto.

O que se perde é a **conferência cruzada entre dois motores independentes**,
que o `verifica` faz no Windows. No cluster ele roda com um motor só e **diz
isso no rodapé**, em vez de fingir que houve confronto. Nenhum resultado do
projeto depende do COM: ele é auditoria, não produção.

### Se o nó não tiver internet

É o normal em cluster. Baixe as wheels antes, numa máquina que tenha, e leve a
pasta junto:

```bash
pip download -r requisitos.txt -d cluster/rodas \n  --platform manylinux2014_x86_64 --python-version 312 --only-binary=:all:
```

```bash
bash cluster/instalar.sh --offline
```

## 2. Copiar as bases

45 GB de `.gdb`. Ponha onde houver disco e aponte:

```bash
export BDGD2DSS_BASES=/scratch/$USER/bdgds
```

## 3. Conferir antes de submeter

```bash
python doutor.py
```

Ele existe por um modo de falha específico daqui: a tarefa entra na fila,
espera, começa de madrugada e morre no minuto 2 porque faltava uma biblioteca.
O prejuízo não é o minuto — é a fila inteira, mais o tempo até alguém olhar.

Confere Python, as três bibliotecas obrigatórias, se o OpenDSS resolve um
circuito de verdade, se a `.gdb` abre, se o `multiprocessing` está em `spawn`,
se o fim de linha sai certo, e quantos processos cabem na memória.

## 4. Prova real, menos de um minuto

```bash
python converter.py $BDGD2DSS_BASES/Roraima_*.gdb --saida TESTE_RR
python validador.py TESTE_RR --ses --jobs 4
```

Roraima tem 20 subestações e converte em menos de um minuto. Se ela sair, sai
qualquer uma — o que muda nas outras é o tamanho, não o caminho de código.

## 5. Submeter

Antes de tudo, veja os nomes reais das filas — eles mudam e o script traz um
padrão que pode não ser o seu:

```bash
qstat -q
```

**O canário primeiro.** Roraima converte em menos de um minuto:

```bash
qsub -q BIRA_Q3 -v TAG=RR cluster/uma_base.pbs
```

Deu certo? As sete, uma por job:

```bash
bash cluster/submeter_todas.sh
```

Uma por job, e não um job só com as sete: elas são independentes, então os
sete entram na fila em paralelo e cada um termina quando terminar. Num job
único a Cemig-D seguraria as outras seis até o fim.

Acompanhar e cancelar:

```bash
qstat -an -u $USER
qdel <id_do_job>
```

A saída de cada job fica em `logs/cluster/`.

### Um nó só, de propósito

O `uma_base.pbs` pede `nodes=1:ppn=32`. **Pedir dois nós não ajudaria**: o
trabalho é independente por subestação e não há troca nenhuma entre processos
— não usamos MPI, e o segundo nó ficaria parado. O que aproveitamos é `ppn`,
os núcleos daquele nó.

Foi por isso também que a InfiniBand não entra na conta: ela serve para
processos que conversam entre si, e os nossos não conversam.

### Modo interativo, para depurar

```bash
qsub -q BIRA_Q4 -I
```

Cai num nó com terminal. Serve para instalar, rodar o `doutor.py` e converter
a Roraima na mão antes de confiar na fila. Roda em um nó só, o que para o
nosso caso não é limitação nenhuma.

## O modo, e o que ele não faz

`BDGD2DSS_MODO=cluster` (ou `--modo cluster`) muda três coisas: quantos
processos usar, nunca abrir formulário, e desenhar em arquivo em vez de na
tela. É detectado sozinho por `PBS_JOBID` (ou `SLURM_JOB_ID`) e por Linux sem
`DISPLAY`.

**O modo não muda nada que seja calculado.** Nem a ordem das contas, nem os
arquivos gerados, nem os passos do dia. Um modelo gerado no cluster tem de sair
**byte a byte igual** ao gerado no laptop — e há teste travando isso, porque é
disso que depende toda a verificação do projeto.

Foi por causa dessa exigência que o fim de linha teve de ser fixado em CRLF no
código: `open(x, 'w')` traduz a quebra de linha para o padrão do sistema, e sem
fixar, o mesmo código produziria arquivos diferentes em cada máquina, sem que
uma conta tivesse mudado.

## Se o nó tiver ambiente gráfico

Tem — e isso muda uma coisa e não muda outra.

**Muda:** `menu.py`, `painel.py` e `app.py` funcionam. `tkinter` é
multiplataforma, então a porta de entrada do projeto está disponível ali como
está aqui. Numa sessão com tela, ou por `ssh -X`, o painel abre.

Um detalhe de instalação: `tkinter` é da biblioteca padrão do Python, **mas em
Linux o `tk` costuma vir num pacote à parte** (`python3-tk`). Um Python
perfeito no resto pode falhar só no import do `tkinter`. O `doutor.py` confere
e diz. O Python instalado pelo micromamba já traz o `tk`.

**Não muda:** o motor COM da EPRI continua não existindo. Ele não depende de
haver tela — depende de ser Windows, porque é um servidor COM registrado no
sistema. Ter GUI no Linux não traz o segundo motor.

**Cuidado com a detecção do modo.** Num nó Linux com `DISPLAY` definido, a
detecção automática diz `pessoal` — que deixa núcleos livres e limita a 8.
Correto para quem está usando o painel interativamente; errado para uma rodada
de produção. Em lote, seja explícito:

```bash
BDGD2DSS_MODO=cluster python regerar_v10.py --sufixo V15 --so CMIG --jobs 0
```

O `cluster/uma_base.pbs` já faz isso, e dentro da fila o `PBS_JOBID` decide de
qualquer forma.

## Quantos processos pedir

`--jobs 0`, que é o padrão, deixa o código decidir: **o menor** entre os
núcleos que a fila deu (`PBS_NP`, ou a contagem de linhas do `PBS_NODEFILE`) e
a memória livre dividida por 3 GB.

Os 3 GB não são chute: é o que as subestações maiores das sete bases seguram
entre circuito compilado e solução — REN, na Equatorial PA, tem 108 mil barras.

**Pedir núcleo demais faz o nó paginar e ficar mais lento do que com metade.**
Num nó de 128 núcleos e 256 GB, cabem ~85 processos, não 128.

## Quanto esperar

| núcleos | ciclo das sete |
|---|---|
| 8 (laptop) | 9,1 h |
| 32 | ~2,5 h |
| 128 | ~2,5 h |

**Acima de ~32 núcleos, mais núcleo não compra nada**: tudo trava no
`converter` da Cemig-D, que hoje é processo único e leva 2,5 h sozinho.
Paralelizá-lo por lotes de subestações é o trabalho que derruba esse piso para
uns 30 min — e é o único motivo para pedir uma fatia maior.

Por isso o `uma_base.pbs` pede `ppn=32`: é o que a ferramenta aproveita com
folga, e é um pedido fácil de justificar. A conta da memória é 32 × 3 GB =
96 GB.

## Se algo falhar

O ciclo **retoma de onde parou**. Base com `validacao_balanco.json` pronto é
pulada; dentro de uma base, subestação com `resumo.json` é pulada. Submeter de
novo o mesmo comando continua o trabalho.

Para segurar sem cancelar — a máquina precisou ser usada para outra coisa:

```bash
python pausa.py --pausar
python pausa.py --retomar
```

As subestações em andamento terminam, nenhuma nova começa, e o tempo parado não
conta no limite de tempo das etapas nem no resumo de desempenho.
