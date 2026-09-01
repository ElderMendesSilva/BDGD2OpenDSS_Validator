# Operação entre máquinas — estado e protocolo

**Corte:** 01/09/2026. Este arquivo guarda o que precisa **sobreviver entre
sessões**: protocolo, regras do cluster e estado atual. O diário das rodadas
(V22, V23, V24, BT1, BT2) está no Git e não se repete aqui — histórico que
ninguém relê só faz o documento se contradizer.

## Onde o projeto está

- **97 bases**, 4.201 subestações, **97,4% com veredicto `OK`**. A V25 é a
  rodada corrente (`resultados/v25/`), agregada, com clima real.
- **Suíte em 789 testes.**
- **Dezessete achados** em `ACHADOS_GENERALIZACAO.md`, que é o documento do
  artigo. A fila de trabalho está em `PLANO.md`.
- Saiu a safra **2025-12-31** da ANEEL. Antes de baixá-la há uma fila curta —
  ver `PLANO.md`, itens 1 a 4. O item 1 é bloqueio de verdade.

## Responsabilidades

| Ação | Responsável |
|---|---|
| Submeter/cancelar jobs PBS e alterar a fila | Elder |
| Planejar a rodada, contar recursos, ler logs e analisar resultados | agente |
| Alterar código, testar e publicar commits | máquina local |

Nenhum agente executa operação destrutiva no cluster. Rodadas usam sufixo novo;
uma rodada antiga é aposentada, não apagada.

## Regra: o head node não processa

Determinação do administrador (28/08/2026). No head node (`10.107.1.23`) valem
`qsub`, `qstat`, `qdel`, `git pull`, `scp` e leitura de arquivo pequeno. Não
valem `auditoria.py`, conversão, energia, validação, nem leitura de modelo por
`python` via SSH — isso vai por PBS, ou vira `scp` do JSON e análise local.

A regra virou **código** em `bdgd2dss/tamanhos.py`: falta base no cache e não
há nó de cálculo, levanta `PrecisaDeNo`. Instrução em `.md` envelhece; guarda
com teste, não.

Consequência direta: **toda pergunta sobre resultado exige o
`resultados/<sufixo>/` publicado**, porque não há como calcular no head node
para responder. Rodada sem o coletor encadeado publicado é rodada que ninguém
analisa sem quebrar a regra.

## Regras do cluster

**Orçamento: 160 núcleos e 480 GB.** Os três nós somam 768 núcleos e 753 GB, e
o gargalo é **memória**: o dimensionamento pede 3 GB por núcleo, então usar os
768 núcleos exigiria 2.304 GB, o triplo do que existe. Por isso o
`submeter_todas.sh` tem **dois tetos** e o menor manda — `ORCAMENTO=160` e
`ORCAMENTO_GB=480`, o que dá 20 correntes usando 21% dos núcleos e 64% da
memória, com folga real para o resto do laboratório.

Contar só núcleo não bastava: sem o teto de GB, subir `ORCAMENTO` estouraria a
memória em silêncio.

**Motor de partida (`RAMPA=90`).** As correntes começam todas pela leitura da
`.gdb`, e vinte delas abrindo 127 GB no mesmo instante disputam o disco. A
**cabeça** de cada corrente larga escalonada (`qsub -a`), uma a cada 90 s. Não
custa relógio no fim, porque só a cabeça espera. `RAMPA=0` desliga.

**Outras invariantes:**

- Só submeter com `--rodar`; sem a flag, o comando mostra o plano.
- Tamanho das bases vem do cache (`medicoes/tamanho_bases.json`); base nova é
  medida uma vez, em nó de cálculo.
- Antes de nova rodada: fila vazia, commit do nó conferido, cota disponível.
- Uma rodada carrega **um único commit**, gravado na procedência. "Git
  indisponível" é diferente de árvore limpa.
- **Fila vazia nunca significa sucesso** — validar os arquivos produzidos.

### O que o cluster ensinou sobre tempo (medido, não estimado)

| medida | valor |
|---|---|
| trabalho somado nas 97 bases | 9,8 h |
| relógio real com 8 correntes | 3,8 h |
| **CMIG sozinha** | **150 min — 25% de todo o trabalho** |
| mediana por base | 0,5 min |
| 2ª mais longa (NEOENERGIA47) | 39 min |

**A distribuição é brutalmente desigual:** metade das bases termina em meio
minuto e uma única base carrega um quarto do esforço. Subir o número de
correntes não ataca isso — é Amdahl. O que atacou foi a **`TAMPA`**: a Cemig
convertia de 8 em 8 só porque `TAMPA=8` a limitava; a 16 núcleos ela cai para
~86 min e o caminho crítico vai de 3,1 h para 1,9 h. Foi o maior ganho de uma
noite inteira, e custou uma variável de ambiente.

Daí também vem `SOZINHA="CMIG:32"`: corrente exclusiva, colocada primeiro.

## Clima por base: dois passos, e por que dois

Baixar clima exige duas coisas que não moram juntas: a **coordenada**, que sai
da `.gdb` no cluster, e a **internet**, que o nó de cálculo não tem.

    1. no nó (PBS):  .gdb -> medicoes/centroides.json
    2. na casa:      centroides.json -> dados/clima/*.json

O passo 2 é `python baixar_clima.py --rodar`, depois de trazer o JSON por
`scp`. Ele pula quem já tem cache, então repetir é barato: falha de rede numa
base não custa as outras. O cache é **por DIST, não por tag**. `dados/` é
versionado, então basta commitar e o nó usa clima real no `pull` seguinte.

Padrão: **janeiro de 2024**, o mês que a conversão usa. Comparar estações exige
repetir com `--mes`.

Isso importa porque o conversor **recusa** aplicar clima de outra distribuidora
(achado 4) e cai no perfil sintético, que é honesto mas ~23% otimista. Enquanto
houvesse base sem clima real, nenhuma conclusão sobre geração distribuída se
sustentava. As 97 já têm.

## Ciclo de trabalho

1. Nó roda e publica resultados rastreáveis.
2. Máquina local importa os CSVs/JSONs e escolhe o pior caso acionável.
3. A máquina local reproduz, corrige, testa e publica o commit.
4. A próxima rodada usa esse único commit e um sufixo novo.

## Como as coisas falham aqui

As falhas que mais custaram **não quebraram nada**:

- coletor com sufixo errado publicando vazio com `rc=0`;
- `SUFIXO` colidindo no PBS, que repassa o ambiente de quem submete (por isso a
  variável do coletor virou `SUF_COLETA`, com `${SUF_COLETA:?}`);
- `NaN` desordenando percentis, com p75 saindo menor que a mediana;
- fragmentação medida só na SSDMT, ignorando chaves e transformadores;
- `col.get(x) or []` em array do numpy, que errou as 97 bases com `rc=0`;
- colisão de tag entre safras, que misturaria 2024 e 2025 em silêncio.

Todas passariam por resultado. **Desconfie de número bonito antes de
comemorar** — e prefira a guarda em código à linha de instrução no `LEIA-ME`.

### O `resultados/` é versionado, e o cluster não deve escrever nele

São 195 arquivos rastreados. Já travou `git pull` no nó quatro vezes. O coletor
publica em `saida_cluster/` (ignorado) justamente por isso; o `scp` de volta é
feito **da máquina local**, nunca de dentro do cluster.
