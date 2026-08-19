# Rodar no cluster

Do zero até as sete bases regeradas. Escrito para ser seguido sem consultar
mais nada.

## 1. Instalar

```bash
git clone <repo> ~/BDGD2OpenDSS && cd ~/BDGD2OpenDSS
python -m venv .venv && source .venv/bin/activate
pip install -r requisitos.txt
```

`pyogrio` traz o GDAL embutido — não é preciso instalar GDAL do sistema. Se a
wheel não existir para a arquitetura do nó, `conda install -c conda-forge
pyogrio` resolve sem compilar nada.

**Não instale `pywin32`.** O motor COM da EPRI só existe registrado no Windows.
O `verifica` cai sozinho para o `opendssdirect` e **diz no rodapé que comparou
um motor só**, em vez de fingir que houve confronto entre dois.

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

```bash
sbatch --array=0-6 cluster/uma_base.sbatch      # as sete
sbatch --array=0   cluster/uma_base.sbatch      # só a Roraima
```

Uma base por tarefa. As sete são independentes: **não trocam nada entre si**,
então não há MPI e a InfiniBand não é usada. É um vetor de tarefas comum.

Índices: `0 RR · 1 ENCE · 2 EQPA · 3 SP · 4 LT · 5 CPFL · 6 CMIG`.

## O modo, e o que ele não faz

`BDGD2DSS_MODO=cluster` (ou `--modo cluster`) muda três coisas: quantos
processos usar, nunca abrir formulário, e desenhar em arquivo em vez de na
tela. É detectado sozinho por `SLURM_JOB_ID` ou por Linux sem `DISPLAY`.

**O modo não muda nada que seja calculado.** Nem a ordem das contas, nem os
arquivos gerados, nem os passos do dia. Um modelo gerado no cluster tem de sair
**byte a byte igual** ao gerado no laptop — e há teste travando isso, porque é
disso que depende toda a verificação do projeto.

Foi por causa dessa exigência que o fim de linha teve de ser fixado em CRLF no
código: `open(x, 'w')` traduz a quebra de linha para o padrão do sistema, e sem
fixar, o mesmo código produziria arquivos diferentes em cada máquina, sem que
uma conta tivesse mudado.

## Quantos processos pedir

`--jobs 0`, que é o padrão, deixa o código decidir: **o menor** entre os
núcleos que a fila deu (`SLURM_CPUS_PER_TASK`) e a memória livre dividida por
3 GB.

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

Por isso o `sbatch` pede **32 núcleos e 96 GB**: é o que a ferramenta sabe
aproveitar hoje, e é um pedido fácil de justificar.

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
