# O que mudou no conversor — relatório consolidado

De um conversor que gerava subestações isoladas de MT para baixo, para um que
gera a concessão inteira (AT → MT → BT) a partir da BDGD.

---

## 1. O problema estrutural que foi resolvido

**Antes:** cada um dos **1.806 alimentadores** recebia um transformador próprio
ligado a um `SOURCEBUS` infinito. Consequências: os alimentadores de uma mesma
subestação não dividiam trafo nem barra, a impedância de subtransmissão não
existia, e a tensão na cabeceira era 1,0 pu *por construção* — escondendo
exatamente a queda que o estudo quer medir.

**Agora:** a fonte está no pátio de AT, o transformador é o real da
`UNTRAT`/`EQTRAT`, e os alimentadores dividem a barra de MT através dos seus
vãos de saída.

### O achado que tornou isso possível

A BDGD **não modela o arranjo interno da subestação**. Verificado na DABR: os
seis `PAC_INI` estão na malha de MT, mas o `PAC_2` dos trafos de AT não se
conecta a nenhum deles. O elo existe só logicamente, em `CTMT.UNI_TR_AT` e
`CTMT.BARR`. Daí o **vão**: a barra de MT vira nó de verdade e de lá sai um
vão por alimentador. Resultado: **1.806 vãos, zero alimentadores sem conexão.**

---

## 2. Camada de alta tensão (nova)

| Tabela | Vira |
|---|---|
| `SSDAT` | 16.490 trechos de 88 kV (897 km) |
| `UNSEAT` | 2.010 chaves, com estado real (`P_N_OPE`) |
| `UNTRAT` + `EQTRAT` | 437 transformadores de potência |
| `UCAT_tab` / `UGAT_tab` / `UNCRAT` | cargas, geração e capacitores de AT |
| `BAR` + `CTAT` | barras e circuitos de AT |

**Fechamento da malha.** A malha de 88 kV da BDGD tem **844 componentes
desconexas** (656 dos 729 circuitos são ilhas isoladas — os circuitos que
chegam e saem de uma subestação nunca se encontram). O módulo `malha_at.py`
cria a barra de AT de cada subestação e liga a ela os trechos que lhe
pertencem, usando `UNSEAT.SUB` e `UNTRAT.SUB` (dado declarado) e, onde faltam,
o nome do circuito em `CTAT.NOME`. Resultado: **379 ilhas → 142**.

**Subestações da transmissora.** Cinco SUBs aparecem em `CTMT` sem trafo em
`UNTRAT` — TBAN, TCTR, TEMG, TMRE, SSJO — somando 69 alimentadores órfãos. As
planilhas da ISA resolvem três delas com transformador real.

---

## 3. Os oito defeitos encontrados e corrigidos

Cada um foi diagnosticado experimentalmente, não por suposição.

### 3.1 `TEN_OPE` ignorado — o de maior impacto
A Enel opera a barra de MT a **1,09 pu em 1.586 dos 1.806 alimentadores**, para
compensar a queda no tronco. Usávamos 1,0. A concessão inteira ficava ~9%
deslocada para baixo: mediana das SEs em 0,921 e cinco não convergiam.
**Correção:** tap do trafo AT/MT (fisicamente correto — elevar a fonte de 88 kV
poria 96 kV na subtransmissão). DABR: 0,929 → **1,014**.

### 3.2 Cutoff do ZIPV em 0,5 pu — 25 subestações não convergiam
O último termo do vetor ZIPV desliga a carga abaixo daquela tensão. Barras que
se estabilizam perto de 0,5 entram em **ciclo-limite**: a carga desliga, a
tensão sobe, religa, cai. Na DVMA eram **exatamente dois nós** oscilando entre
0,4623 e 0,4653 pu — e bastavam para estourar 100 iterações.
**Correção:** cutoff 0,5 → 0,25. As 25 passam a convergir em **4 a 6
iterações**, com tensão e potência idênticas.

### 3.3 Espaço no nome do PAC — DTAM não compilava
O PAC `0008200019A75850L_ 14266371` contém espaço; o OpenDSS corta o nome ali e
lê o resto como parâmetro. Erro críptico: *"Could not match enum Connection"*.
**Correção:** sanitizador único (`leitor.no`) usado por **todos** os módulos —
se a linha sanitiza e o transformador não, os dois deixam de se encontrar na
mesma barra. DTAM: não compilava → **OK, Vmed 1,061**.

### 3.4 Duas fontes no mesmo nó com tensões diferentes — 2.238 cargas mortas
A TBAN alimenta 9 saídas em 20 kV e 29 em 34,5 kV. As duas `Vsource` caíam no
mesmo `barra_at_tban`, uma de 88 kV e outra de 345 kV. O `CalcVoltagebases`
atribuía 88/√3 à barra de 34,5 kV e os 29 alimentadores ficavam sem tensão.
**Correção:** uma barra de AT por nível de tensão, e uma fonte por barra de MT
no master da subestação. TBAN: 2.238 cargas mortas → **0**.

### 3.5 Campo vazio virando barra fantasma
Vários campos da BDGD vêm preenchidos com espaço em vez de nulo. Sem `strip`,
um `' '` virava a barra `'_'`, e todos os alimentadores sem `BARR` declarada
ficavam ligados a uma mesma barra que não se conecta a fonte alguma. Era o que
deixava as 24 saídas da TCTR sem alimentação.

### 3.6 Cabeceira adivinhada por topologia
A versão anterior escolhia a barra de maior ampacidade da maior componente
conexa — chute que erra sempre que a rede está fragmentada. **Correção:**
`CTMT.PAC_INI`, que é a cabeceira declarada.

### 3.7 Tensão de MT fixa em 13,8 kV
**122 alimentadores** operam em 20 kV (código 59) ou 34,5 kV (código 72).
**Correção:** `tensoes.py`, com a procedência de cada valor documentada
(84→88 kV pela nomenclatura das barras; 59→20 kV e 72→34,5 kV por cruzamento
com a ISA). Códigos 27, 55, 62, 67, 73 e 74 permanecem indeterminados e o
conversor **avisa** em vez de fingir precisão.

### 3.8 `Buscoords` antes do `Solve` e `Sample` ausente
A lista de barras do OpenDSS só existe após a montagem — `Buscoords` emitido
antes não casa nenhuma coordenada. E em snapshot o OpenDSS não amostra
medidores sozinho: sem `Sample`, os registradores de energia ficam zerados.

### 3.9 GD de BT em barra que não existe — NaN em 54 subestações
O `PAC` da `UGBT_tab` aponta para um nó da rede secundária. Com `--bt
agregado` essa rede não é modelada, então o `PVSystem` **criava a barra
sozinho**: sem linha, sem transformador, sem fonte. Ilha isolada devolve NaN.

Censo nas 155 (`MODELOS_V4`): **54 subestações, 380 nós, 95 barras** — e o
perfil é homogêneo, *toda* barra com NaN da concessão é `sem PDE: PVSystem`.

Corrigido pela mesma agregação já usada nas cargas: a GD de BT vai para o
secundário do transformador de `UNI_TR_MT`, dividida entre as pernas reais.
Na DALP, 1.970 unidades realocadas e 3 descartadas por não ter ponto de
conexão nenhum. O mesmo bloqueio foi estendido a capacitores, reguladores e
cargas de MT.

### 3.10 O cutoff do ZIPV — o defeito que inutilizava o modelo no OpenDSS
Este só aparece no motor que o usuário abre. Os dois builds discordam do
**mesmo arquivo**:

| motor | nós NaN | `TotalPower` |
|---|---|---|
| DSS C-API 0.14.5 (`opendssdirect`, o validador) | 36 | 257.360 kW |
| **OpenDSS v11.0.0.1 COM (EPRI)** | **49.857** | **NaN** |

O C-API contém o NaN na ilha que o gerou; o da EPRI o propaga pela fatoração
e derruba a rede inteira. Pior: `Converged` volta **True em 2 iterações**,
porque toda comparação com NaN é falsa e o critério passa trivialmente.

Ablação por classe de elemento apontou a carga; variando um termo do ZIPV por
vez, apontou **só o cutoff**:

| ZIPV | nós NaN |
|---|---|
| cutoff 0,25 (o valor anterior) / 0,50 / 0,80 | 49.821 |
| **cutoff 0,00** | **0** — converge em 5 iterações |
| Z puro, P puro, I puro (cutoff 0,25) | 49.821 |

No v11 o ramo abaixo do cutoff devolve NaN em vez de zerar a injeção, e sempre
há barra colapsada (o mínimo da DALP é 0,071 pu). `ZIPV` passou a cutoff zero:
a parcela de impedância constante limita a corrente, que era a função do
cutoff.

### 3.11 Uma barra de MT por nível de tensão
Sete subestações têm alimentadores em tensões diferentes e a BDGD põe todos no
mesmo `CTMT.BARR`. Como a tensão da **barra** prevalecia sobre a do
alimentador, 12 dos 14 alimentadores da DALP — declarados 13,8 kV — eram
energizados a 34,5 kV. Medido: **1.484 dos 1.491 transformadores** com o
primário fora da tensão da barra, secundários a 1,9 pu.

Agora a tensão do alimentador (`CTMT.TEN_NOM`) prevalece, e quando difere da
barra o alimentador vai para uma barra derivada, ligada à original por um
**transformador de barra** — que existe em campo e a BDGD não declara,
dimensionado por rateio da capacidade de AT da subestação. São 7 barras
derivadas em 6 subestações (a TBAN já tinha duas barras reais).

Depois: DALP com 2.964 cargas vivas, 50.217 kW, **0 mortas**, barra de 34,5 kV
a 0,999 pu e a derivada de 13,8 kV a 0,999 pu.

### 3.12 Perdas medidas contra a fonte, não contra a energia injetada
`perdas_pct` usava a potência da fonte como denominador. Com geração
distribuída a fonte quase zera e a razão perde sentido. Na DALP:

| grandeza | kW |
|---|---|
| fonte | 1.737 |
| **GD (5.375 unidades)** | **54.339** |
| injetada | 56.076 |
| carga | 50.217 |
| perdas | 5.296 |

perdas/fonte = **305%**; perdas/injetada = **9,44%**, que é a definição do
Módulo 7 do PRODIST e o único número comparável entre subestações com e sem
GD. Parte das classificações `TENSAO_BAIXA` vinha dessa razão inflada.

Ficou exposto também que o instantâneo roda com `irradiance=1.0` — meio-dia de
céu claro — contra uma carga que é a média mensal (`ENE/730`). Na DALP a GD
cobre 108% da carga e a subestação exporta. Não é defeito, é cenário: agora há
`--irradiancia` para escolher.

---

## 4. Melhorias de qualidade de dado

**Coerência R1 × ampacidade na SEGCON.** 144 dos 3.495 condutores têm
resistência incompatível com a corrente declarada — o extremo é `R1 = 8,43
Ω/km` para um condutor de `1500 A` (esperado: ~0,04). O `linecodes.py` ajusta
`R1 = a·CNOM^b` sobre o miolo coerente da própria base (`R1 = 219,2·CNOM^−1,120`,
calibrado em 3.187 condutores) e substitui os que estão >7,4× acima —
**77 condutores**, cada um marcado com `!! R1 CORRIGIDO` no `.dss`.

Duas ressalvas honestas: corrige **só para baixo** (R muito *abaixo* do previsto
costuma ser barramento declarado de propósito), e **não resolve a subtensão** —
medido na DREG o efeito foi nulo. É qualidade de dado, não explicação de queda
de tensão.

**Baixa tensão completa (`--bt completo`).** A cadeia física é trafo → `SSDBT` →
`RAMLIG` → UC. Sem o ramal, 97% das UCs ficam soltas (o PAC da UCBT é a ponta do
ramal). E sem o neutro explícito as cargas não têm retorno — 29.834 de 30.009
ficavam sem tensão. Ambos implementados. Perdas de 16% ainda **pendentes de
calibração** contra as colunas `PERD_B` da `CTMT`.

---

## 5. Ferramentas novas

| Arquivo | O que faz |
|---|---|
| `painel.py` | **janela principal** — lista as 155 com causa raiz, valida, analisa, e abre o `Plot Circuit` nativo do OpenDSS |
| `analise_com.py` | análise pela interface COM: 7 gráficos, incluindo o traçado geográfico |
| `verifica.py` | **sanidade numérica nos DOIS motores** (C-API e COM da EPRI), subestação por subestação: NaN, convergência, carga, GD e perdas |
| `bdgd2dss/diagnostico.py` | classifica cada SE por causa raiz, separando defeito nosso de característica da rede |
| `bdgd2dss/coordenadas.py` | geometria da BDGD → `BusCoords` (habilita `Plot Circuit`) |
| `bdgd2dss/malha_at.py` | fecha a malha de 88 kV |
| `bdgd2dss/subtransmissao.py` | toda a camada de AT |
| `bdgd2dss/transmissao.py` | interface com a ISA |
| `bdgd2dss/tensoes.py` | código `TEN_NOM` → kV |

O **validador** também foi corrigido: o `Compile` do OpenDSS troca o diretório
de trabalho do processo, e sem salvar/restaurar só a primeira subestação era
validada — o que fez um relatório inteiro parecer bom sem ter rodado.

---

## 6. O que a BDGD não permite

Não é falha de execução; é limite do dado. Cada item vira pedido à Enel.

| Limitação | Consequência |
|---|---|
| `SEGCON` só traz R1 e X1 | R0/X0 são premissa → **desequilíbrio e Módulo 8 fora de alcance** |
| Sem impedância dos trafos de potência | `Xhl` adotado por faixa de potência |
| Sem ajuste de reguladores | 213 reguladores com `vreg`/banda genéricos; **saturam no tape máximo** em rede longa |
| Sem ajuste de `CapControl` | capacitores como banco fixo |
| Sem espectro harmônico | DTT/DTTp/DTTi impossíveis |
| Fator de potência não medido | 0,92 assumido |
| Malha de 88 kV entre subestações ausente | subtransmissão não fecha; cada pátio recebe fonte própria |
| Domínio de tensão ausente | 6 códigos indeterminados |

**Limite da ferramenta:** o `MASTER-GERAL` com as 155 subestações **não compila
— `Out of memory`**. São ~1,2 milhão de `Line`, 130 mil trafos e 290 mil cargas
num único circuito OpenDSS. Os modelos por subestação rodam sem problema.

---

## 7. Onde estamos — as 155 revalidadas uma a uma

Regeração completa em `MODELOS_V4` (75,6 min) e validação das 155, com todas as
correções da seção 3 aplicadas. Comparação contra `MODELOS_V3` (antes das
correções 3.2, 3.3 e 3.4):

| Causa raiz | V3 | V4 | |
|---|---:|---:|---|
| `OK` | 100 | **122** | +22 |
| `MODELO_QUEBRADO` | 27 | **1** | −26 |
| `TENSAO_BAIXA` | 20 | 25 | +5 |
| `REGULADOR_SATURADO` | 6 | 5 | −1 |
| `REDE_EXTENSA` | 2 | 2 | = |

O aumento de `TENSAO_BAIXA` não é regressão: são subestações que antes nem
convergiam e agora convergem, expondo a subtensão que estava escondida atrás da
falha.

Saúde estrutural do modelo — os três números que dizem se o conversor está
produzindo OpenDSS válido:

| Verificação | Resultado |
|---|---|
| Não compila | **0 de 155** |
| Não converge | **1 de 155** (DBSI, 100 iterações) |
| Cargas sem alimentação | **0 de 155** |
| Alimentadores sem vão | **0 de 1.808** |

Números agregados: perdas com **mediana 9,6%** (média 10,0%, máx. 21,7% na
DJAN); tensão média com **mediana 0,993 pu** (mín. 0,709 na DREG, máx. 1,082);
convergência em **3 iterações na mediana**.

A classificação separa o que é acionável do que depende de dado externo:

- `MODELO_QUEBRADO`, `CARGA_ALTA`, `TENSAO_BAIXA` → **nosso**
- `REDE_EXTENSA`, `REGULADOR_SATURADO` → depende de dado que a BDGD não tem

Contexto para os dois últimos: a mediana da concessão é **8,9 km por
alimentador** e apenas **7 dos 1.808** passam de 100 km. Dois estão na DREG,
com 440 e 335 km — nessa escala a queda de 30% é o resultado correto, e o que a
sustenta na operação real é o ajuste escalonado dos reguladores.

---

## 8. Quanto falta para uma rede fechada e funcional

Não cabe um número só, porque as dimensões travam por motivos diferentes.

| Dimensão | Onde está | O que trava |
|---|---|---|
| **Cobertura** — todas as SEs e alimentadores presentes e ligados | **100%** | — |
| **Subestações que rodam** (compila, converge, sem carga morta) | **99%** | 154/155 — só a DBSI não converge |
| **Subestações sem ressalva elétrica** | **79%** | 122/155 — 25 com subtensão a investigar |
| **Fidelidade elétrica** para carregamento e tensão equilibrada | **~75%** | `Xhl` adotado, fp assumido, regulador genérico |
| **Malha de 88 kV fechada** | **~40%** | falta a planilha de Linhas de Subtransmissão (item 1 da solicitação) |
| **Modelo único da concessão** | **0%** | `Out of memory` — limite do OpenDSS, não do modelo |
| **Validade regulatória** (Módulo 8 completo) | **~40%** | R0/X0 são premissa; harmônicos impossíveis |

**Número único, se precisar de um: ~70%.** As duas primeiras linhas agora são
medidas nas 155, não estimadas — a incerteza restante está nas quatro de baixo.

E o mais importante é como se reparte o que falta:

- **~10% é trabalho nosso** — as subestações com subtensão a investigar, a
  calibração das perdas da BT completa, e uma estratégia para o modelo único
  (dividir por região ou equivalentar a MT).
- **~20% depende de dado que a BDGD não tem** — e está integralmente listado
  em `Solicitacao_Dados_Complementares_ENEL.txt`. Os itens 1 e 2 daquele
  documento (planilha de subtransmissão e tabela de estruturas) sozinhos
  levariam de ~70% para ~90%.

Ou seja: o conversor está mais próximo do limite do dado do que do limite do
código. É por isso que a solicitação à Enel virou o caminho crítico.
