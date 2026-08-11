# Plano de continuidade

**Definido em 10/08/2026.** Objetivo final: conversor e auditor de BDGD que
atravessam distribuidoras diferentes, sustentando artigo de nível periódico
internacional, com prazo de submissão até março de 2027.

---

## Estado em que o plano começa

Medido, não estimado:

| | |
|---|---|
| Subestações que compilam, convergem e não têm NaN nos dois motores | **155 de 155** |
| Subestações que resolvem o dia inteiro de 96 passos | **155 de 155** |
| `MASTER-GERAL` (concessão inteira) | **1.669.937 barras, 4 iterações, sem NaN** |
| Validação das perdas contra o `PERD_*` declarado | **reprova** — razão mediana 1,88×, 18% dos alimentadores dentro de ±30% |
| Subestações com causa raiz acionável (`TENSAO_BAIXA`) | **19** — perdas de 17,4% contra 4,8% declarado, razão 4,08× |
| Testes automatizados | **0** |
| BDGDs em que a ferramenta já rodou | **1** |

Duas pendências conhecidas que não dependem do plano:

- **Os modelos não correspondem ao código.** O `MODELOS_V8` carrega a curva de
  irradiância anterior à correção: sol das 06:00 às 11:45, pico às 09:00,
  temperatura fixa em 25 °C. A energia diária de GD está certa (o `Pmpp` é
  retrocalculado pelo fator de capacidade da própria curva), mas o instante e a
  potência de pico não — o pico sai ~2,3× maior que o correto, concentrado de
  manhã.
- **Seis hipóteses refutadas** para a subtensão das 19, a última sendo `X1`.
  Restam alocação de carga, agregação de BT e topologia.

---

## A decisão de sequenciamento

**Não oficializar uma v1.0 só com a Enel SP.** Rodar uma segunda base antes.

O motivo não é de engenharia. O viés de 1,65× que sobra nas 136 subestações
sadias — depois de excluir as 19 defeituosas — tem duas leituras possíveis, e
**uma base só não distingue entre elas**:

- se o mesmo viés aparecer nas outras distribuidoras, ele é propriedade da
  conversão BDGD→OpenDSS, ou de como o `PERD_*` é calculado pelas
  concessionárias, e vira **o resultado do artigo**;
- se aparecer só na Enel SP, é defeito nosso.

Congelar uma v1.0 agora embute a segunda hipótese sem prova.

Vale também para o enquadramento: um conversor validado em uma distribuidora é
ferramenta local; um que roda em sete e **relata como as bases diferem entre si**
é contribuição sobre a BDGD como formato. As 6 bases não são a fase seguinte à
v1.0 — são a substância do trabalho.

---

## Os passos

### 1. Regerar os modelos — ✅ FEITO em 10/08/2026

`MODELOS_V9`, 155 subestações em 48,2 min. A V8 fica preservada para comparação.

Curva solar corrigida e conferida: sol das 05:00 às 18:30, pico às 11:15,
6,22 h equivalentes, temperatura de 19,3 a 53,0 °C, tudo de irradiância
**medida** (`clima: Janeiro medido`). Fator de capacidade 0,139 → 0,2388.

155/155 sadias nos dois motores, 155/155 resolvem o dia.

**A correção não mexeu na validação:** razão mediana 1,88× antes e depois,
18,0% dentro de ±30% antes e depois, mudança mediana de 0,003 pp por
alimentador. O motivo é que a GD é 0,53% da energia injetada. Uma hipótese a
menos disponível para explicar o viés — o que reforça o passo 3.

### 2. Marcar a linha de base reprodutível — ✅ FEITO em 10/08/2026

`MODELOS_V9/LINHA_DE_BASE.md` e `linha_de_base.json`: comandos exatos, opções
usadas, resultado, e o **SHA-256 dos 25 arquivos de código** que produziram os
modelos. Sem git no projeto, o hash é o que faz as vezes de tag — se algum não
bater, os modelos não vieram deste código.

*Pendência conhecida:* o projeto não é repositório git. Isso precisa mudar antes
do passo 6, e quanto antes melhor — a partir do passo 3 haverá alteração de
código com necessidade de voltar atrás.

### 3. Bases estrangeiras — EM ANDAMENTO desde 10/08/2026

Achados em `ACHADOS_GENERALIZACAO.md`. Rodadas até agora:

| base | subestações | sadias nos dois motores | conversão |
|---|---:|---:|---:|
| Roraima Energia (370) | 20 | 19/20 | 1,9 min |
| Light (382) | 94 | 92/94 | 52,9 min |

**O conversor rodou nas duas na primeira tentativa, sem alteração de código** —
266 de 269 subestações resolvem, somando com a Enel SP. Não era garantido.

Oito achados registrados. O de maior consequência é o **nº 7**: a camada de AT
amarra por `UNTRAT.PAC_1`, que casa a 94% na Enel SP e a **0% na Light**, e a
chave que funciona nas duas (~95%) é `BARR_1`→`BAR.COD_ID`. A parte que exigiu
mais engenharia reversa é a que não generaliza.

Faltam: CPFL Paulista (63), Enel CE (39), Equatorial PA (371), Cemig-D (4950).

**Sem consertar nada antes.** Rodar e anotar tudo que quebra. Exceção aberta e
registrada: o `TypeError` do achado 8, que impedia qualquer medição.

O que já se sabe que é da Enel SP e não da BDGD, e portanto é candidato a
quebrar:

- `tensoes.TENSAO_KV` — mapa de código para kV derivado da Enel SP, com **6 dos
  11 códigos sem valor confirmado**;
- `tensoes.bases()` — lista de tensões de BT tirada do censo de 159.061
  transformadores da Enel SP;
- `transformadores._FN_PARA_FF` — mapa de correção de campo trocado, específico
  desta base;
- `transmissao.py` — depende inteiramente das planilhas da ISA (contornável com
  `--sem-at`).

*Timebox: um dia.* Anotando, não consertando.

### 4. Transformar as quebras em testes

As falhas do passo 3 **são** os casos de teste, com dados reais de entrada.
Escrever a suíte antes de ver uma segunda base é testar o que se imagina que
varia, não o que varia.

*Pronto quando:* houver `requirements.txt`, uma BDGD pequena versionada no
repositório e testes que reproduzam cada quebra observada.

### 5. Tirar da Enel SP o que hoje é tabela fixa

Derivar da base sendo convertida, no padrão que o `linecodes._ajuste` já usa —
ele calibra a relação R1×CNOM na própria base a cada execução, em vez de tabela
externa. Aplicar o mesmo ao censo de `TEN_LIN_SE` (tensões de BT) e ao de
`TEN_NOM` (códigos de tensão).

### 6. As outras cinco, depois oficializar

Tag, repositório público, modelos gerados pelo código publicado.

*Só depois de sobreviver a duas bases no mínimo.*

---

## O que faria mudar de rota

- **Se em um dia não der para converter nenhuma subestação da segunda base**, o
  problema é maior do que "três blocos hardcoded" e o plano é reavaliado antes
  do passo 4.
- **Se o viés de 1,65× aparecer também na segunda base**, ele deixa de ser bug e
  passa a ser o objeto do artigo — e os passos 4 e 5 ganham prioridade sobre
  investigar as 19.
- **Se o viés for exclusivo da Enel SP**, é defeito nosso e precisa ser fechado
  antes de qualquer submissão.

---

## O que fica de fora, e por quê

- **Otimização de desempenho.** `verifica` leva 4 a 10 min e `validador` 2 a 6
  min para as 155, uma vez por regeração. O único desperdício real são as 416
  compilações do `energia.py` (2,68 por subestação, quando 1 bastaria), e ele é
  sintoma da degradação do modo diário que nunca foi explicada — acelerar isso
  hoje é acelerar um remendo.
- **Os scripts de `analise/`.** Apontam para caminhos de um sandbox que não
  existe nesta máquina, e o método deles (estimativa de ponta por energia mensal
  × fator de ponta, comparada com a ampacidade do tronco) está superado pelo
  fluxo de potência que hoje roda de verdade. Todos os artefatos que produziriam
  já estão em `dados/resultados/` e `relatorios/`.
