# Achados da generalização

Passo 3 do `PLANO.md`: rodar outras BDGDs **sem consertar nada**, anotando o que
quebra. Cada achado aqui vira caso de teste no passo 4 e correção no passo 5.

Todas as bases são V11 com data-base 2024-12-31, a mesma da Enel SP — as
diferenças observadas são da distribuidora, não da versão do formato.

---

## Roraima Energia (370) — 10/08/2026

```bash
python converter.py "Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb" --saida MODELOS_RR
python verifica.py MODELOS_RR
python validador.py MODELOS_RR --ses
```

Opções todas no padrão. **Nenhuma linha de código alterada.**

| | Enel SP (390) | Roraima (370) |
|---|---:|---:|
| subestações | 155 | 20 |
| alimentadores | 1.806 | 89 |
| transformadores de distribuição | 159.061 | 27.700 |
| condutores na SEGCON | 3.498 | 153 |
| tempo de conversão | 48,2 min | **1,9 min** |
| sadias nos dois motores | 155/155 | **19/20** |
| sem ressalva no validador | 131/155 | 12/20 |

**O conversor rodou numa segunda distribuidora na primeira tentativa.** É o
resultado mais importante do dia, e não era garantido.

### Achado 1 — BUG REAL: transformador de barra duplicado

Bloqueia a compilação de 1 das 20 subestações.

```
(#266) Duplicate new element definition: "Transformer.TRB_5003585_34p5"
```

**Mecanismo** (`bdgd2dss/subtransmissao.py:399-413`): o dicionário `derivadas` é
indexado por `(sub, barra_original, kv_alimentador)`, mas o transformador de
barra é nomeado `TRB_{sub}_{kv}` — **sem a barra original**. Uma subestação com
duas barras originais distintas que precisem de derivação na mesma tensão gera
dois transformadores com o mesmo nome.

Na Enel SP nunca disparou: lá nenhuma subestação tinha duas barras originais
demandando o mesmo nível derivado. É bug de nascença, exposto pela segunda base.

*Correção candidata:* nomear a partir de `nova` (a barra derivada), que já é
única por chave — `TRB_{nova}`.

### Achado 2 — a previsão de fragilidade errou de tabela

Eu havia ranqueado os códigos de tensão como fragilidade nº 1, esperando que
`CTMT.TEN_NOM` quebrasse. **Não quebrou:** Roraima usa só `49` (13,8 kV) e `72`
(34,5 kV), ambos já mapeados. Zero alimentadores com tensão adivinhada — contra
os códigos `27` e `62` que aparecem na própria Enel SP.

Quebrou em **outra tabela**, que eu não tinha auditado:

```
AVISO: codigo de tensao '82' desconhecido em EQTRAT.TEN_PRI — adotando 88.0 kV
AVISO: codigo de tensao '30' desconhecido em EQTRAT.TEN_SEC — adotando 13.8 kV
```

O padrão de 88 kV vem do censo das barras da Enel SP. Se a subtransmissão de
Roraima operar em outro nível, o primário dos 29 transformadores de potência
está errado — e o conversor avisa uma vez e segue. **Verificar qual é o nível
real antes de usar este modelo.**

### Achado 3 — limiar calibrado na Enel SP aplicado a outra concessão

`bdgd2dss/diagnostico.py:49` traz `KM_ALIM_ALTO = 60.0`, e a mensagem de
`REDE_EXTENSA` carrega o literal *"mediana da concessao: 8,9 km"*. Os dois saem
do censo da Enel SP.

Em Roraima os alimentadores têm **288 a 424 km** — 4 das 20 subestações caem em
`REDE_EXTENSA`. A classificação em si é defensável (queda de tensão fisicamente
real em alimentador de 400 km, não acionável), mas **o número de referência na
mensagem é falso para esta base**, e o limiar de 60 km foi escolhido olhando
outra distribuidora.

É o exemplo exato do que o plano prevê: limiar calibrado numa base só não
generaliza. A mediana tem de sair da base sendo convertida.

### Achado 4 — clima de São Paulo aplicado em silêncio

```
clima: Janeiro medido — irradiancia media 0.2590 kW/m2, ambiente 19.3 a 26.1 C
```

Números **idênticos** aos da conversão da Enel SP. O padrão do `--clima` aponta
para a pasta de dados de São Paulo, e Roraima fica perto do equador. Não há
aviso: o modelo sai com irradiância e temperatura ambiente paulistas.

Pior que quebrar, porque passa silencioso. O conversor precisa exigir clima da
região ou recusar-se a usar o de outra, e o auditor precisa reportar qual clima
entrou.

### Achado 5 — `TEN_LIN_SE` com tensões de MT e com fase-neutro

32 dos 27.700 transformadores (0,12%) declaram no campo de tensão de linha do
secundário valores que o `Voltagebases` não contém:

| valor | n | leitura |
|---|---:|---|
| 13,8 | 11 | tensão de MT em campo de BT |
| 5,0 | 8 | a verificar |
| 4,207 | 7 | a verificar |
| **7,96** | 6 | **13,8 / √3** — fase-neutro em campo de fase-fase |

O `7,96` é diagnóstico: é a mesma classe de erro que o `_FN_PARA_FF` já trata em
BT (`0,127 → 0,22`), agora aparecendo em MT. Sugere trocar a tabela fixa por uma
**regra**: se o valor bate com um nível conhecido dividido por √3, é fase-neutro.

### Achado 6 — identificadores de subestação numéricos

Roraima usa `5003585`, `1018819824`; a Enel SP usa mnemônicos de quatro letras
(`DABR`, `TBAN`). Nada quebrou, mas nomes de pasta, de medidor e de arquivo
passam a ser numéricos — e o `de-para de 86 mnemônicos`, construído à mão para a
Enel SP, foi aplicado a Roraima assim mesmo (267 âncoras). **Verificar se casou
algo indevidamente.**

### O que NÃO quebrou, e vale registrar

- **As 24 tabelas que o conversor procura estão todas presentes.** Nenhuma
  ausente. É a primeira evidência real de que o esquema da ANEEL é padronizado —
  premissa em que o projeto inteiro se apoia e que até aqui era só esperança.
- **A dependência das planilhas da ISA degradou como projetado:** `0 com trafo
  da ISA, 6 com equivalente`, sem erro.
- **O ajuste auto-calibrado de R1 funcionou na base nova:** 8 dos 153 condutores
  tiveram a resistência substituída, calibrando na própria SEGCON de Roraima.
  É a peça que já generaliza, e agora está demonstrado.

### O que o teste de Roraima NÃO responde

A pergunta central — se o viés de 1,88× nas perdas é da Enel SP ou da conversão
— **continua aberta**. Roraima tem 89 alimentadores contra 1.806, e a
distribuição de causas é diferente demais para comparar: 4 de 20 subestações são
`REDE_EXTENSA` por alimentadores de 300 a 400 km, situação que quase não existe
na Enel SP. Falta rodar `energia` e `valida_perdas` aqui e, principalmente,
rodar uma base de porte comparável — CPFL Paulista ou Light.

---

## Light (382) — 10/08/2026

Escolhida por ser o análogo estrutural da Enel SP — metrópole densa,
alimentadores curtos, porte comparável. Se o viés das perdas aparecer aqui
também, ele não é da Enel SP.

| | Enel SP (390) | Roraima (370) | Light (382) |
|---|---:|---:|---:|
| subestações | 155 | 20 | 94 |
| alimentadores | 1.806 | 89 | 1.713 |
| unidades consumidoras de BT | 8.258.035 | — | 5.019.324 |
| transformadores de distribuição | 159.061 | 27.700 | 98.455 |
| condutores na SEGCON | 3.498 | 153 | 721 |
| R1 corrigido pelo auto-ajuste | 77 | 8 | 20 |
| tempo de conversão | 48,2 min | 1,9 min | 52,9 min |
| **sadias nos dois motores** | **155/155** | **19/20** | **92/94** |

### Achado 7 — a camada de AT amarra pelo campo errado

**O achado mais importante do levantamento.** A camada de alta tensão da Light
saiu vazia: `0 trechos de AT`, `0 fontes`, `0 km`.

Não é dado ruim da Light. A SSDAT dela é impecável — 7.909 trechos, 2.380,8 km,
nenhum PAC vazio, **100%** dos trechos casando com um circuito CTAT declarado
(a Enel SP tem 99,8%). O problema é a chave de ligação que o conversor usa:

| | Enel SP | Light |
|---|---:|---:|
| `UNTRAT.PAC_1` presente na SSDAT | **94,2%** | **0,0%** |
| `UNTRAT.PAC_1` em `BAR.PAC` | 32,5% | 0,0% |
| `UNTRAT.BARR_1` em `BAR.COD_ID` | **94,8%** | **94,6%** |
| `BAR.PAC` presente na SSDAT | 45,0% | 0,0% |

Na Light, transformadores de potência e trechos de subtransmissão vivem em
espaços de identificador **separados**: nenhum dos 297 transformadores casa por
PAC. Sem âncora, a malha não fecha; sem malha, nenhum trecho é emitido; sem
trecho, nenhuma fonte é posicionada.

O conversor amarra por `PAC` porque foi assim que a convenção da Enel SP foi
decifrada por engenharia reversa. **`BARR_1`/`BARR_2` contra `BAR.COD_ID`
funciona nas duas bases, a ~95%.** É a chave que deveria ter sido usada desde o
início.

Isto é a justificativa retrospectiva do plano inteiro: a parte do conversor que
exigiu mais engenharia reversa é exatamente a que não generaliza, e só uma
segunda base de porte comparável poderia mostrar isso.

*Correção candidata:* migrar a ancoragem da AT de `PAC` para `BARR`→`BAR.COD_ID`,
mantendo `PAC` como reserva.

### Achado 8 — `TypeError` em subestação sem energia

`energia.py` derrubava a rodada inteira na primeira subestação com energia
injetada nula:

```python
f'{pct if pct is None else round(pct, 2):>9}'   # None nao aceita :>9
```

Bug antigo, nunca disparado porque toda subestação da Enel SP tem carga. A Light
tem; Roraima também teria.

**Corrigido na hora, abrindo exceção à disciplina do passo 3** — é um `f-string`
de impressão que impedia qualquer medição, não uma premissa de modelagem. A
exceção fica registrada de propósito.

### Achados 2, 4 e 5 se repetem, e com mais força

- **Código de tensão desconhecido em escala:** `67` em **132 dos 1.713
  alimentadores (7,7%)**, contra zero em Roraima. Mais `46` em `EQTRAT.TEN_SEC`.
  O `67` também aparece na Enel SP sem valor confirmado — vê-lo em duas bases
  prova que é valor real do domínio da ANEEL, e abre caminho para inferi-lo.
- **Clima de São Paulo aplicado de novo em silêncio,** com os mesmos
  `0,2590 kW/m²` e `19,3 a 26,1 °C`. No caso da Light o erro é menor, porque Rio
  e São Paulo têm irradiância parecida — o que o torna *menos visível* sem
  torná-lo menos errado.
- **`TEN_LIN_SE` fora do `Voltagebases`: 2.735 de 98.455 (2,8%)**, contra 0,12%
  em Roraima:

| valor | n | leitura |
|---|---:|---|
| **0,216** | 1.659 | **216 V — tensão de BT real ausente da nossa lista** |
| 7,62 | 613 | **13,2/√3** — fase-neutro, segundo caso independente |
| 13,8 | 252 | MT em campo de BT |
| **0,4** | 172 | **400 V — outra tensão de BT real ausente** |
| 13,0 / 6,0 / 15,0 | 39 | MT em campo de BT |

Os `0,216` e `0,4` são o problema sério: são tensões de atendimento legítimas da
Light, e a lista do `bases()` saiu do censo dos 159.061 transformadores da Enel
SP, onde elas não existem. **1.831 transformadores recebem base de tensão
errada** — o mesmo mecanismo que já tinha colocado 2.805 barras acima de 1,10 pu
na Enel SP.

E o `7,62` confirma o padrão do `7,96` de Roraima. Dois valores, duas bases,
mesma regra: **se o valor bate com um nível conhecido dividido por √3, é
fase-neutro em campo de fase-fase.** Sugere trocar a tabela `_FN_PARA_FF` por uma
regra calculada.

### Terceira confirmação do que sustenta o projeto

As 24 tabelas que o conversor procura estão presentes nas três bases. Nenhuma
ausência em Enel SP, Roraima ou Light.

---

## Achado 9 — o viés das perdas TROCA DE SINAL entre distribuidoras

O resultado mais importante do levantamento, e o que responde à pergunta que
estava aberta desde o começo.

| | Enel SP (390) | Light (382) |
|---|---:|---:|
| alimentadores comparados | 1.492 | 1.451 |
| perdas do modelo (mediana) | **7,73%** | **1,01%** |
| perdas declaradas (mediana) | 4,39% | 5,17% |
| **razão modelo/declarado** | **1,88×** | **0,19×** |
| acima de 2× | 47,7% | 0,7% |
| abaixo de 0,67× | 18,6% | **92,4%** |

O modelo **superestima em 1,88× numa base e subestima em 0,19× na outra** — um
fator de dez entre elas. Isso descarta de imediato a hipótese de viés sistemático
da conversão: uma premissa de modelagem errada empurraria as duas para o mesmo
lado.

### Por que a diferença, e não é rede faltando

Primeira hipótese, refutada por medição: rede de MT incompleta na Light,
deixando as cargas eletricamente perto da fonte.

| | Enel SP | Light |
|---|---:|---:|
| SSDMT declara | 1.424.443 trechos / 22.243,9 km | 996.561 trechos / 25.611,0 km |
| o modelo tem | 1.421.983 linhas / 22.218,5 km (**99,9%**) | 996.561 linhas / 25.611,0 km (**100,0%**) |
| km por alimentador | 12,30 | **14,95** |

A rede da Light está inteira no modelo, e é **mais longa** por alimentador. Não
é rede faltando.

A explicação está na impedância declarada:

| | Enel SP | Light |
|---|---:|---:|
| R1 mediano na SEGCON | 0,519 Ω/km | 0,389 Ω/km |
| **R1 médio ponderado por km de rede** | **1,642 Ω/km** | **0,652 Ω/km** |
| carga total | 4.289 MW | 2.241 MW |

**2,5× mais resistência por quilômetro de rede na Enel SP, com o dobro da
carga.** Perda percentual escala aproximadamente com corrente × resistência;
0,52 × (1/2,5) ≈ 0,21, contra a razão observada de 1,01/7,73 = 0,13. A ordem de
grandeza fecha.

Repare que as *medianas* de R1 são parecidas (0,519 e 0,389) e a média ponderada
por extensão difere em 2,5×: na Enel SP são os condutores de alta resistência
que carregam a maior parte da quilometragem.

### O que isso significa

**O modelo reproduz o que os parâmetros declarados de rede implicam.** E aí está
a contradição, dentro da mesma base regulatória:

- os parâmetros de rede (SEGCON `R1`, SSDMT `COMP`, energia das UCs) dizem que a
  Light deve ter perda técnica bem menor que a Enel SP;
- as perdas declaradas (`PERD_A4 + PERD_B + PERD_A4_B`) dizem que a Light tem
  perda **maior** — 5,17% contra 4,39%.

Os dois conjuntos de campos vêm da mesma BDGD, da mesma data-base, submetidos ao
mesmo regulador. **São mutuamente inconsistentes, e o sinal da inconsistência
inverte entre distribuidoras.**

O argumento que sustenta essa leitura: as premissas do nosso modelo — razões
R0/X0, `Xhl` por faixa de potência, BT agregada, modelo ZIP, ajuste genérico de
regulador — são **as mesmas nas duas bases**. Premissa comum não produz erro que
troca de sinal.

### O que ainda não está descartado

Não é prova, é a leitura mais econômica. Falta:

- rodar as outras quatro bases e ver se o padrão se mantém;
- verificar se o `PERD_*` das duas distribuidoras é calculado com a mesma
  metodologia do Módulo 7 — a norma define o resultado, não o procedimento;
- checar se há parcela de perda que o modelo não representa e que pese
  diferente nas duas (BT agregada é a suspeita natural).

---

## Achado 10 — a validação por MEDIÇÃO reprova a Enel SP e aprova as outras

**11/08/2026.** Primeira aplicação do `valida_balanco.py` em cinco bases. É o
único teste do projeto capaz de reprovar sozinho: a perda técnica do modelo tem
de caber dentro da perda total medida (`ENE_XX` injetada menos energia faturada
nas UCs). Passar dela é fisicamente impossível.

Violar o limite, porém, pode ser duas coisas muito diferentes: **modelo alto
demais** ou **medição degenerada** naquele alimentador — faturado maior que
injetado, o que é erro de cadastro, não de física. Separando os dois:

| base | alimentadores | violam | medida degenerada | **violação real** |
|---|---:|---:|---:|---:|
| **Enel SP** | 1.573 | 482 (30,6%) | 29 | **458 (29,1%)** |
| Equatorial PA | 619 | 124 (20,0%) | 121 | **5 (0,8%)** |
| CPFL Paulista | 1.537 | 43 (2,8%) | 67 | **14 (0,9%)** |
| Light | 1.546 | 165 (10,7%) | 196 | **4 (0,3%)** |
| Enel CE | 686 | 4 (0,6%) | 0 | **4 (0,6%)** |

**A Enel SP é discrepante por um fator de ~40.** As outras quatro ficam entre
0,3% e 0,9%, compatível com ruído residual de cadastro. A Enel SP tem 29,1%.

E os casos dela não são sutis:

| SE | alimentador | modelo | total medida | porte |
|---|---|---:|---:|---|
| DDIA | DIA0105 | **83,57%** | 19,91% | 66,3 GWh, 8.023 UCs |
| DSAU | SAU0104 | 73,61% | 11,13% | 47,5 GWh, 16.609 UCs |
| DEMB | EMB0106 | 71,85% | 18,59% | 60,4 GWh, 16.145 UCs |
| DREG | REG0302 | 66,47% | 18,58% | 41,1 GWh, 9.027 UCs |
| DJAN | JAN0106 | 49,90% | 8,47% | 34,3 GWh, 14.270 UCs |

Perda técnica de 83% num alimentador de 66 GWh não é ajuste fino: é defeito.
E DDIA, DEMB e DREG estão entre as 19 subestações que o validador já
classificava como `TENSAO_BAIXA` — **os dois sintomas são o mesmo defeito**,
agora com um teste objetivo que o localiza alimentador a alimentador, sem
depender do `PERD_*`.

### Isto reescreve os achados 9 e o diagnóstico anterior

O que parecia "viés que troca de sinal entre distribuidoras" era confusão
entre dois fenômenos:

1. **A Enel SP tem defeito localizado e severo** — 29,1% dos alimentadores com
   perda técnica impossível. É o que empurra a razão contra o `PERD_*` para
   1,88× e o que gera a subtensão das 19.
2. **Nas outras bases o modelo passa no teste físico.** O fato de a razão
   contra o `PERD_*` ficar em 0,15× a 0,60× nelas é outra questão — e a
   suspeita mais forte agora é de **erro de método nosso na comparação**: o
   modelo roda com `--bt agregado`, sem rede de BT, e portanto não produz
   `PERD_B`; mas comparamos contra `PERD_A4 + PERD_B + PERD_A4_B`. Estamos
   cobrando uma parcela que o modelo estruturalmente não gera. Verificar
   comparando só contra `PERD_A4`.

### A perda não técnica implícita reproduz o que se sabe do país

Subproduto do nível 2, e a evidência externa mais forte que o projeto produziu
até aqui. Nada foi ajustado para dar isto:

| base | não técnica implícita (mediana) |
|---|---:|
| Light (RJ) | **35,23%** |
| Equatorial PA | **22,17%** |
| CPFL Paulista (interior SP) | 13,62% |
| Enel CE | 11,46% |
| Enel SP (metropolitana) | 5,07%¹ |

A ordenação é a conhecida publicamente para perda comercial no Brasil: Light e
Equatorial no topo, distribuidoras paulistas na base. O modelo reproduz o
ranking **sem ter sido calibrado para isso** — ele só calcula a parcela técnica
e o resto sai por subtração contra medição.

¹ subestimada, porque a técnica da Enel SP está inflada pelo defeito acima.

### Qualidade de cadastro: alimentadores com faturado ≥ injetado

Impossível de medir e portanto erro de cadastro. Vira indicador do auditor:

| base | alimentadores | % |
|---|---:|---:|
| Equatorial PA | 116 | **18,7%** |
| Light | 113 | 7,3% |
| Enel SP | 19 | 1,2% |
| CPFL | 14 | 0,9% |
| **Enel CE** | **0** | **0,0%** |

A Enel CE é a única base sem um único alimentador nessa condição — e também a
de menor violação real. Pelo critério de coerência interna medida, **é a melhor
das cinco**.

---

## Achado 11 — um único registro de condutor explica a reprovação da Enel SP

**11/08/2026.** Rastreamento dos 458 alimentadores que violam o limite físico
até a causa, com dois controles independentes.

### O que os 458 têm de diferente

Comparados aos outros 1.115, **dentro das mesmas subestações**:

| | violam (27) | não violam (69) |
|---|---:|---:|
| km de MT | 13,80 | 6,72 |
| km acima da ampacidade | 12,8% | 8,5% |
| **km acima de 2× a ampacidade** | **7,0%** | **0,9%** |
| perda que ocorre em trecho sobrecarregado | 91,6% | 80,7% |

A sobrecarga leve quase não separa os grupos. A **severa** separa por fator 8.
E em ambos os grupos a perda está concentrada em trecho sobrecarregado — ou
seja, o problema não é só dos 458: é da Enel SP.

### Controle: a mesma medida numa base que passa

Enel CE, 46 alimentadores em 6 subestações: **0,0% da quilometragem acima da
ampacidade, 0,0% da perda em sobrecarga.** Zero, não "pouco".

Isso descarta que a sobrecarga seja artefato do método — se fosse, apareceria
lá. E a Enel CE tem condutor *pior*: R1 ponderado de 5,307 Ω/km contra 1,642 da
Enel SP, com a mesma fração de 14,2% da rede em condutor de 0-50 A. O que muda
é a densidade: **145 km por alimentador na Enel CE contra 12,3 na Enel SP.**
Cabo fino em rede rural esparsa não satura; o mesmo cabo em rede urbana densa
satura.

### A causa: o condutor 593

Censo da SEGCON ponderado pelo km de rede que cada condutor cobre:

```
Enel SP — os 5 condutores com mais quilometragem
   cnd  593    2.993 km (13,5%)   CNOM   31,0 A   R1  8,232 ohm/km
   cnd 1664    2.230 km (10,0%)   CNOM  254,0 A   R1  0,678
   cnd 2027    1.654 km ( 7,4%)   CNOM  600,0 A   R1  0,197
```

**13,5% de toda a rede de média tensão da Enel SP está declarada num condutor
de 31 A.**

Rastreando a sobrecarga em 30 subestações, cobrindo 237 dos 458 (52%):

| linecode | km na rede deles | km em sobrecarga | % da sobrecarga | **enriquecimento** | perda |
|---|---:|---:|---:|---:|---:|
| **CND_593** | 867,1 | **496,3** | **94,7%** | **4,64×** | 110.514 kW |
| CND_597 | 44,1 | 20,1 | 3,8% | 3,70× | 2.538 kW |
| CND_36 | 9,2 | 6,3 | 1,2% | 5,53× | 272 kW |

- o 593 é **20,4%** da rede desses alimentadores e **94,7%** da sobrecarga;
- **57,2% da própria quilometragem do 593 opera acima da ampacidade declarada**;
- ele responde por **97,4% da perda que ocorre em trecho sobrecarregado**.

### O que isso é, e o que não é

Os valores do 593 são **internamente coerentes**: 31 A pede mesmo R1 da ordem
de 8 Ω/km, e o ajuste calibrado da própria base prevê ~19 A para essa
resistência. Por isso o auto-ajuste do `linecodes` não o toca — ele corrige
incoerência entre R1 e CNOM, e aqui não há.

O que é implausível é o **uso**: 2.993 km de rede metropolitana de MT num cabo
de 31 A. Duas leituras possíveis, nenhuma testada ainda:

1. o `TIP_CND` atribui o 593 a trechos que em campo são de condutor mais
   grosso;
2. o registro 593 na SEGCON tem valores errados.

Nos dois casos é **problema de dado da BDGD, não do conversor** — e o conversor
é o instrumento que o revela.

### Como tratar

**Não corrigir o 593 para o resultado melhorar.** Ajustar dado até o número
agradar destrói a credibilidade de tudo o mais.

O tratamento honesto: declarar e quantificar. *A Enel SP declara 13,5% da rede
de MT num condutor de 31 A; tomando o dado ao pé da letra, 29,1% dos
alimentadores produzem perda técnica maior que a perda total medida, o que é
fisicamente impossível.*

### Análise de sensibilidade

**Método.** Uma variável, e só ela. Os modelos já gerados foram copiados
inteiros — topologia, cargas, transformadores, curvas e clima idênticos, byte a
byte — e apenas as 35 definições `New LineCode.CND_593_*` foram reescritas com
os parâmetros do **CND_1664**, condutor de 254 A e 0,678 Ω/km que cobre
2.230 km da mesma concessão. Depois, `energia` e `valida_balanco` nas mesmas 30
subestações.

O 1664 **não é uma afirmação sobre qual cabo está em campo**. É um condutor
plausível da própria base, escolhido para responder "quanto do fracasso vem
daqui".

**Resultado**, em 382 alimentadores comparáveis:

| | técnica mediana | violam | não técnica implícita |
|---|---:|---:|---:|
| antes (593 original) | 14,27% | 237 (62,0%) | **−2,99%** |
| depois (593 = 1664) | **4,08%** | **29 (7,6%)** | **+6,91%** |

Restrito aos 237 que violavam:

| | técnica mediana | violam | não técnica implícita |
|---|---:|---:|---:|
| antes | 22,35% | 237 (100%) | **−8,86%** |
| depois | **4,95%** | **29 (12,2%)** | **+5,27%** |

**208 dos 237 — 87,8% — deixam de violar.**

O detalhe mais eloquente é a perda não técnica implícita passando de
**negativa** para positiva. Negativa é o enunciado matemático de "impossível":
a perda técnica do modelo excedia a perda total medida. Depois da troca, o
resíduo vira +5,27%, plausível.

Casos individuais:

| SE | alimentador | antes | depois | medida | |
|---|---|---:|---:|---:|---|
| DDIA | DIA0105 | 83,57% | **10,95%** | 19,91% | resolvido |
| DEMB | EMB0106 | 71,85% | **10,95%** | 18,59% | resolvido |
| DVFO | VFO0107 | 59,42% | **6,17%** | 31,00% | resolvido |
| DLUB | LUB0109 | 61,13% | **19,48%** | 20,02% | resolvido |
| DJAN | JAN0106 | 49,90% | 8,76% | 8,47% | ainda viola |

E a técnica mediana de 4,08% depois da troca fica ao lado dos **4,39%
declarados** na CTMT — contra 14,27% antes. A razão de 1,88× que reprovava a
Enel SP era, em boa parte, este registro.

**Os 29 que resistem** são o trabalho que sobra: neles a perda impossível tem
outra causa, ainda não investigada.

### O que isto autoriza a afirmar

Que **um único registro da SEGCON de uma distribuidora responde por 87,8% dos
alimentadores fisicamente impossíveis do modelo dela** — e que o conversor,
cruzado com a energia medida da própria base, é capaz de localizar isso sem
nenhuma informação externa.

O que **não** autoriza: dizer qual é o valor correto do 593, nem publicar os
números "corrigidos" como se fossem os da Enel SP. A sensibilidade é uma
medida da influência do dado, não uma correção dele.
