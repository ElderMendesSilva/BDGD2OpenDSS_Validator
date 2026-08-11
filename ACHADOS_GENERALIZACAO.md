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

### RESOLVIDO em 11/08/2026 — e o erro não estava onde eu procurava

Primeiro a recusa: `BASE.DIST` (o código ANEEL, presente nas sete bases) é
confrontado com `--clima-dist`, e o dado medido de outra distribuidora é
**recusado** em favor do perfil sintético — que é pior, mas *se declara*
sintético. Um erro que quebra é corrigido; um que imprime número plausível
entra no artigo.

Depois a medição, e ela reposiciona o achado. A BDGD é SIRGAS 2000
(EPSG:4674), que é **geográfico**: a geometria já dá lon/lat, sem
reprojeção. O centroide da rede sai da própria base:

| base | lon | lat | kWh/m²/dia | temperatura |
|---|---:|---:|---:|---|
| Enel SP | −46,65 | −23,57 | 5,36 | 15,5 a 35,7 °C |
| **Roraima** | −60,70 | **+2,77** | 5,62 | **26,8 a 39,1 °C** |
| Equatorial PA | −49,35 | −2,77 | 5,12 | 22,9 a 33,8 °C |
| CPFL (interior SP) | −48,11 | −21,60 | **6,28** | 16,0 a 37,2 °C |
| Light | −43,36 | −22,88 | — | — |
| Enel CE | −39,33 | −4,60 | — | — |
| Cemig-D | −44,78 | −19,19 | — | — |

**O erro grosseiro era de TEMPERATURA, não de irradiância.** A irradiância de
Roraima é apenas 5% maior que a de São Paulo — janeiro é estação chuvosa
perto do equador, e a intuição de "equador logo mais sol" não se confirma.

Mas o conversor aplicava **19,3 a 26,1 °C** numa região que opera de **26,8 a
39,1 °C**. A mínima de Roraima é maior que a máxima que estava sendo
fornecida: **as duas faixas não têm um grau em comum.** Temperatura de célula
comanda o *derating* do painel, então a geração de Roraima saía fria demais,
logo eficiente demais.

### Dois subprodutos, e os dois mudaram decisão

**A CPFL não é caso de "mesma região, tanto faz".** O interior paulista tem
**6,28 kWh/m²/dia** contra 5,36 da capital — 17% mais sol. Foi esse número
que decidiu *não* usar `--clima-forcar` nela na regeração.

**E o arquivo medido de São Paulo é suspeito, confirmando dúvida já
registrada.** Ele declara 6,22 kWh/m²/dia, e o comentário no
`complementos.carregar_clima` já anotava que isso parecia ~10% acima da faixa
típica de janeiro (5,0 a 5,8). A NASA POWER dá **5,36 — dentro da faixa**.
Duas fontes independentes apontando para o mesmo lado, uma delas escrita
meses antes da outra.

### O que ficou pronto, e o que falta

`bdgd2dss/clima.py`: centroide pela geometria da própria base, consulta à
NASA POWER (grátis, sem cadastro, `urllib` da biblioteca padrão — nenhuma
dependência nova), e cache em disco com **procedência gravada** (fonte, URL,
coordenada, período, data do download). 22 testes, **nenhum tocando a rede**.

Falta **ligar no conversor**, e isso é de propósito: mudar o caminho do clima
antes da regeração agendada desperdiçaria o ciclo. Entra depois.

**Ressalva que precisa constar do artigo:** NASA POWER é satélite e
reanálise, **não medição de solo**. É incomparavelmente melhor que aplicar
São Paulo em Roraima e ainda assim não é estação meteorológica. As
referências para validar são o **Atlas Brasileiro de Energia Solar
(INPE/LABREN)**, que é a referência nacional mas não tem API, e as estações
do **INMET**, que medem radiação global no solo.

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

### RESOLVIDO em 11/08/2026 — e a correção candidata acima estava ERRADA

Medido nas **sete** bases com `diagnosticos/at_cobertura.py`, antes de mexer
em qualquer linha:

| âncora | Enel SP | Roraima | Light | Eq. PA | CPFL | Enel CE | Cemig-D |
|---|---:|---:|---:|---:|---:|---:|---:|
| `PAC_1` na SSDAT *(em uso)* | 99,5% | **0,0%** | **0,0%** | **0,0%** | **0,0%** | **0,0%** | **0,0%** |
| `BARR_1` em `BAR.COD_ID` | 100% | 93,1% | 100% | 100% | 86,2% | 100% | 100% |
| `BARR_1`→`BAR.PAC`→SSDAT | 100% | **0,0%** | **0,0%** | **0,0%** | **0,0%** | **0,0%** | **0,0%** |
| **`UNTRAT.SUB` em `UNSEAT.SUB`** | 100% | **75,9%** | 100% | 98,2% | 97,9% | 99,1% | 95,4% |

Dois fatos, e o segundo é o que importa:

1. **A âncora em uso não funciona em nenhuma base além da Enel SP.** Não é
   "funciona menos bem": é 0,0% nas seis. Eu só tinha medido a Light.
2. **A correção que este achado propunha não resolveria.** `BARR_1` casa com
   `BAR.COD_ID` de 86% a 100% em todas — mas o `BAR.PAC` daquela barra não
   está na SSDAT fora da Enel SP. Ela **identifica a barra e não chega à
   rede.**

O que generaliza é a terceira: a âncora por **subestação**, que o `malha_at`
já usava para fechar a malha. Adotado `PAC_1` quando ele existe na malha, e a
barra de AT da subestação quando não — e só para as subestações que a malha
vai de fato ligar, senão troca-se um transformador ilhado por outro.

Resultado: Roraima sai de **0 trechos de AT** para **169 trechos (13,2 km)**,
com 20 de 29 transformadores pela reserva. Enel SP usa a reserva em **2 de
437**: a convenção dela fica preservada.

### A lição de método, que vale mais que a correção

O teste de aceitação deste achado foi escrito **pelo resultado** — *"o
primário do transformador tem de chegar à rede de AT, seja qual for a
âncora"* — e não pelo mecanismo. Foi o que salvou: um teste escrito contra a
correção proposta (`BARR_1`) teria ficado verde com a correção **errada**, e
o defeito continuaria em cinco bases.

### E um defeito que a própria correção introduziu

A barra da subestação não entrava no grupo que ela liga, e o
`transmissao.fontes` procura nos grupos os transformadores de cada pátio.
Roraima ficou com **1 fonte para 12 pátios** e 88,8% das cargas do
MASTER-GERAL sem tensão. Invisível nos modelos por subestação — que têm fonte
própria e passavam 20 de 20; só o modelo da concessão inteira mostrava.
Corrigido: 12 fontes, 13,2% de cargas mortas, tensão mediana de 0,737 para
0,936. Tem teste próprio.

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

### RESOLVIDO em 11/08/2026 — era a terceira suspeita, e era erro nosso

A última hipótese da lista acima estava certa. **O modelo roda com
`--bt agregado`: não há rede de baixa tensão nele, e portanto ele não produz
perda de rede de BT. Mesmo assim a comparação cobrava `PERD_A4 + PERD_B +
PERD_A4_B`.**

Corrigido no passo 5: a composição passou a sair do campo `bt` do
`relatorio_rede.json` que o próprio conversor grava, e o programa **mede** as
três candidatas em vez de arbitrar. Amostra comum por base, ancorada na soma
das três para que não se mova com a composição avaliada. Critério: fração
dentro de ±30%.

| base | `PERD_A4` | `+PERD_A4_B` | as três |
|---|---:|---:|---:|
| Light | **15,6%** | 12,8% | 5,2% |
| Equatorial PA | **22,2%** | 2,8% | 0,8% |
| CPFL Paulista | **39,5%** | 2,8% | 1,0% |
| Enel CE | 37,0% | **55,2%** | 27,6% |
| Enel SP | 0,8% | 10,1% | **18,0%** |
| Cemig-D | **14,6%** | 1,8% | 1,1% |

**A soma das três — a que estava em uso — é a pior em cinco das seis bases.**

Efeito na razão mediana, mesma amostra:

| base | antes (as três) | depois (`PERD_A4`) |
|---|---:|---:|
| Light | 0,19× | **2,07×** |
| Equatorial PA | 0,14× | **1,36×** |
| CPFL Paulista | 0,35× | **1,26×** |
| Enel SP | 1,88× | **11,89×** |

O "viés que troca de sinal" era, em boa parte, **isto**. A subestimação de
0,15× a 0,35% nas bases sadias vinha de cobrar do modelo uma parcela que ele
estruturalmente não gera.

### O detalhe desconfortável, e que precisa ficar registrado

A composição antiga é a **única** em que a Enel SP parece menos ruim: ela sai
de 11,89× para 1,88×. E a razão é mecânica — denominador maior disfarça
modelo inflado, e a Enel SP é justamente a base com o defeito do condutor
593 inflando o modelo.

Ou seja: **a escolha de método que estava em uso era, sem que ninguém tivesse
escolhido assim, a que mais escondia o defeito que o projeto acabou
encontrando por outro caminho.** Não foi má-fé nem sorte — foi uma decisão
tomada por plausibilidade, numa base só, nunca medida. É o mesmo padrão do
achado 7 (a ancoragem por `PAC`) e do achado 3 (o limiar de 60 km): o que se
calibra numa base e não se mede nas outras vira armadilha.

### E o que isso NÃO resolve

Mesmo na melhor composição, a concordância é de **39,5%** dentro de ±30% no
melhor caso (CPFL) e 15,6% na Light. **O cruzamento com o `PERD_*` continua
fraco em qualquer composição** — o que reforça, e não enfraquece, a decisão
de usar o balanço por energia MEDIDA (achado 10) como validador de verdade.

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
| Cemig-D¹ | 460 | 227 (49,3%) | 228 | **5 (1,1%)** |

**A Enel SP é discrepante por um fator de ~40.** As outras quatro ficam entre
0,3% e 0,9%, compatível com ruído residual de cadastro. A Enel SP tem 29,1%.

¹ **A linha da Cemig-D não é comparável às demais e está aqui com ressalva.**
Ela cruza 460 alimentadores de **2.456 declarados** — 23,9% de cobertura,
contra 87% a 95% em todas as outras. O 1,1% é medido sobre um quarto da rede,
e nada garante que esse quarto represente o resto. Ver achado 12.

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
| **Cemig-D** | **204** | **44,3%** |
| Equatorial PA | 116 | **18,7%** |
| Light | 113 | 7,3% |
| Enel SP | 19 | 1,2% |
| CPFL | 14 | 0,9% |
| **Enel CE** | **0** | **0,0%** |

A Enel CE é a única base sem um único alimentador nessa condição — e também a
de menor violação real. Pelo critério de coerência interna medida, **é a melhor
das seis**.

E a Cemig-D é a pior por larga margem: **quase metade dos alimentadores que
chegam à medição faturam mais energia do que recebem.** Isso arrasta a perda
não técnica implícita dela para 0,08% mediano — número que não descreve a
Cemig, descreve a medição.

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

**Medido em 11/08, em `testes/test_linecodes.py`:** o 593 fica a **1,6× do R1
previsto**, contra o limiar de **7,4×** que aciona a correção. Mexer no
`FATOR_CORRIGE` não é saída — para alcançá-lo seria preciso descer abaixo de
1,6×, que é dispersão normal de catálogo, e a correção varreria junto os
condutores legítimos. E, mais decisivo: o ajuste recebe pares `(R1, CNOM)` e
nada mais. **O mesmo condutor cobrindo 1 km ou 3.000 km produz exatamente o
mesmo veredito** — a informação que denuncia o 593 não chega até essa função.
A verificação que falta é de outra natureza, e só existe depois do fluxo.

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

---

## Achado 12 — a Cemig-D quebra a MEDIÇÃO, não a conversão

**11/08/2026.** Sexta e última base. Ela converte (413 de 413 subestações
geradas, 148,4 min — a mais demorada), mas é a primeira em que o resultado
**não pode ser lido junto com os das outras**.

### Três degradações, em ordem crescente de gravidade

| | Cemig-D | as outras cinco |
|---|---:|---:|
| sadias nos dois motores | **341/413 (82,6%)** | 780/787 (99,1%) |
| resolvem os 96 passos | 340/413 | 155/155 na Enel SP |
| **alimentadores que chegam à medição** | **492 de 2.062 (23,9%)** | **87,2% a 94,6%** |

Os 72 casos de NaN são leves — 266 nós no total, mediana de ~4 por
subestação, nos **dois** motores, convergindo em 3 iterações e com potência
coerente. Não é modelo quebrado; é nó flutuante.

O terceiro item é que inviabiliza a comparação. E os 1.570 alimentadores que
não medem registram **exatamente zero**, não "pouco" — é medidor com zona
vazia, não medidor com pouca carga.

### A causa, medida

Hipótese: os alimentadores de uma mesma subestação estão interligados na MT,
a zona de um `EnergyMeter` engole as vizinhas, e as outras ficam sem nada. Se
for isso, os que medem têm de carregar energia **inflada** frente à declarada.

Razão entre a energia do modelo (dia × 365) e a declarada na CTMT do mesmo
alimentador — 1,0 seria o medidor vendo exatamente o alimentador declarado:

| base | p10 | mediana | p90 | acima de 2× |
|---|---:|---:|---:|---:|
| **Cemig-D** | 0,21 | **2,71** | 8,70 | **58,7%** |
| Enel SP | 0,54 | 0,73 | 0,98 | 0,5% |
| Enel CE | 0,77 | 0,93 | 1,11 | 1,9% |
| CPFL | 0,80 | 0,93 | 1,05 | 0,8% |

**Confirmada.** Nas três bases de controle a razão fica em 0,73 a 0,93 com
menos de 2% acima do dobro; na Cemig-D a mediana é 2,71 e quase 60% passa do
dobro. Os medidores que sobraram estão medindo os vizinhos junto.

### O que isso invalida

O 1,1% de violação real da Cemig-D **não é comparável** aos 0,3%–0,9% das
outras nem aos 29,1% da Enel SP. Não é só cobertura baixa: o numerador (perda
do modelo) e o denominador (energia declarada daquele alimentador) passam a
ser de conjuntos diferentes de rede. Pela mesma razão, a perda não técnica
implícita de 0,08% não descreve a Cemig — descreve a medição.

E os 44,3% de alimentadores com faturado ≥ injetado, o pior índice das seis,
são em boa parte o outro lado do mesmo efeito: quem perdeu a zona fica com
energia injetada quase nula contra faturamento real.

### O que fica pendente

A causa da interligação em si não foi investigada — pode ser topologia real
da Cemig (rede de MT malhada, e não radial como as outras cinco), pode ser
`PAC_INI` apontando para dentro da zona de outro alimentador, pode ser o vão.
**São hipóteses, nenhuma testada.** O que está medido é o efeito.

Consequência para o auditor: **fração de alimentadores que chegam à medição**
vira indicador de primeira linha, ao lado de faturado ≥ injetado. Sem ele, a
Cemig-D teria entrado na tabela do achado 10 com um 1,1% de aparência
excelente.

---

## Achado 13 — o modelo único da concessão tem teto de memória

**11/08/2026.** Encontrado ao checar se o bloco B do passo 5 tinha causado
regressão. Não tinha — mas revelou outra coisa.

### O que aconteceu

O `MASTER-GERAL` da Enel SP não compila:

```
(#303) ... New Load.BT_14256255_2 Bus1=30646325737313880l.2.4 ...
Error Description: Out of memory
```

Primeira leitura, e errada: *"o bloco B quebrou o modelo da concessão
inteira"*. O controle desmentiu.

### O controle

Compilei o `MASTER-GERAL` da **V9** — gerado pelo código antigo — na mesma
máquina, no mesmo estado. **Falha também**, na mesma etapa, criando uma carga
em `DJKU/Cargas.dss`. E esse arquivo é **byte a byte idêntico** ao do bloco B
(SHA-256 `2A14D66B…`).

Contando os elementos dos dois modelos, sem compilar:

| | V9 | bloco B |
|---|---:|---:|
| **elementos totais** | **2.391.177** | **2.391.177** |
| Line | 1.527.968 | 1.527.968 |
| Load | 351.144 | 351.144 |
| Transformer | 159.679 | 159.679 |
| Reactor | 158.998 | 158.998 |
| SwtControl | 85.284 | 85.284 |
| PVSystem | 63.781 | 63.781 |

**Nem um elemento difere.** O bloco B é estruturalmente inerte na Enel SP.

### O achado de verdade, e ele é sobre o objetivo do projeto

O modelo único da concessão inteira — 2,39 milhões de elementos — **não cabe
em 15,8 GB de RAM**. Isso não é defeito do conversor nem da BDGD: é limite de
porte, e vale para qualquer versão do código.

Importa porque *"entregar um MASTER geral da rede toda"* é objetivo declarado
do trabalho. Ele funciona nas bases menores — o `MASTER-GERAL` de Roraima
compila, converge em 10 iterações e resolve. Na maior distribuidora do país,
com esta máquina, não.

Três saídas, nenhuma testada ainda:

1. **mais memória** — medir o pico real e dizer quanto pede. O cluster do
   laboratório resolveria, e é o primeiro uso concreto que ele ganha;
2. **`--bt nenhum` no modelo geral** — as 351.144 cargas e boa parte dos
   158.998 reatores de aterramento são de BT. Um MASTER-GERAL só de MT
   caberia, e para estudo de subtransmissão é o recorte certo;
3. **aceitar o recorte por subestação** como o produto principal, com o
   MASTER-GERAL restrito às bases que couberem.

### O primeiro uso externo, e o que ele encontrou

**11/08/2026.** Uma equipe de fora — estudo de despacho otimizado de
armazenamento, artigo em revisão na IEEE Access — recebeu o pacote de 05/08 e
devolveu um relatório com hipóteses testadas e comandos de reprodução. É o
primeiro uso independente do conversor, e vale mais que qualquer auditoria
interna: eles olharam para os modelos sem saber o que esperar deles.

Encontraram duas coisas. **Uma era nossa e está corrigida; a outra é nossa e
continua aberta.**

---

## Achado 14 — a mesma subestação com duas tensões de cabeceira

Eles relataram subtensão generalizada na DALP: metade da rede de 13,8 kV
abaixo da faixa adequada do PRODIST, mediana 0,9270, mínima 0,2403.

**A causa era inconsistência interna nossa.** No modelo geral, quem sustenta a
barra de MT é o transformador de AT, com `tap` = **mediana** de
`CTMT.TEN_OPE`. No modelo isolado não há esse transformador — a fonte o
substitui, e deveria reproduzir o mesmo pu. Não reproduzia: o pu saía do
`setdefault`, que faz vencer o **primeiro alimentador da iteração**, ou de um
**`1.0` embutido** no ramo de fallback usado quando todas as barras são
derivadas — que é o caso da DALP.

Medido: **5 de 150 subestações com `pu` ≠ `tap`, e a diferença sempre 0,09 pu**
— a distância entre operar a 1,09 e a 1,00. A Enel declara 1,09 em 1.586 dos
1.806 alimentadores.

| SE | V média antes | depois | |
|---|---:|---:|---|
| DALP | 0,9351 | **1,0144** | +0,0793 |
| DTED | 0,9284 | 1,0091 | +0,0807 |
| DCAM | 0,9709 | 1,0562 | +0,0853 |
| DNAC | 0,8429 | 0,9148 | +0,0719 |
| DGPR | 0,9529 | **0,8774** | **−0,0755** |
| DVTA | 0,9230 | 0,9230 | **0,0000** |

A DGPR **desce**: a mediana dela é 1,00 e o código antigo pegara 1,09 de um
alimentador avulso. A correção não empurra tensão para cima — faz os dois
modelos dizerem a mesma coisa. E a DVTA, que já concordava, não muda nem na
quarta casa: é o controle que separa o efeito da correção de qualquer outra
coisa.

Quem abriu o modelo isolado — que é o recomendado para estudo de alimentador,
e é o que o próprio `MASTER` sugere — recebeu a rede nove pontos abaixo.

---

## Achado 15 — a geração fotovoltaica derruba a convergência acima de 50%

Este continua **aberto**, e é defeito nosso.

A equipe externa mediu, na DALP, quantos dos 96 passos do dia convergem
conforme se escala a irradiância. Reproduzi a varredura com o `pu` como única
variável, para separar do achado 14:

| irradiância | pu = 1,00 | pu = 1,09 (corrigido) | eles (OpenDSS 9.4.0.1) |
|---|---:|---:|---:|
| desabilitada | 96/96 | 96/96 | 96/96 |
| 25% | 96/96 | 96/96 | 93/96 |
| 50% | 96/96 | 96/96 | 80/96 |
| **75%** | **73/96** | **73/96** | 30/96 |
| **100%** | **34/96** | **35/96** | **29/96** |

**Reproduzido em dois motores independentes** — DSS C-API 0.14.5 aqui, OpenDSS
9.4.0.1 lá — e a correção do achado 14 não toca nele: muda um passo, que é
ruído.

### Por que nunca tínhamos pegado

O ciclo diário do projeto usa a irradiância **medida**, que dá 5,1 MW de pico
na DALP contra 11,97 MW de potência instalada — cerca de **43% do nominal**.
A divergência começa entre 50% e 75%. **A validação de 96 passos nunca
exercitou o regime onde o modelo quebra**, e por isso as 155 subestações
"resolvem o dia" sem que isso seja garantia para um cenário de irradiância
plena.

É uma limitação da nossa validação, não só do modelo.

### Hipóteses testadas

Pela equipe externa, e descartadas por eles: histerese do inversor
(`%cutin`/`%cutout`), modo de controle, número de iterações, algoritmo
(`normal` e `newton`), e sobredimensionamento da GD frente ao transformador
(das 544 barras com geração, só uma excede, e por 0,03 kVA em 75).

Por mim:

| hipótese | resultado |
|---|---|
| tensão de cabeceira baixa (achado 14) | **refutada** — 73/96 e ~35/96 nos dois pu |
| impedância do aterramento de neutro | **refutada** — 0,5 Ω a 0,001 Ω, fator 500, não muda um passo |
| faixa `Vminpu`/`Vmaxpu` do PVSystem | **refutada como causa** — ver abaixo |

A hipótese do neutro era a da própria equipe externa, e era boa: com
`--bt agregado` não há rede de baixa tensão, então toda a carga e toda a
geração de um transformador ficam na mesma barra e voltam por um único reator.
Mas o número não sustenta.

### A terceira hipótese, e por que ela quase convenceu

O `_pv` não declara `Vminpu` nem `Vmaxpu`, então valem os padrões do OpenDSS:
**0,85 e 1,10**. Fora dessa faixa o PVSystem deixa de ser injeção de potência
constante e vira impedância constante — que é **exatamente** o mecanismo do
cutoff do ZIPV já documentado em `cargas.py`: *"a carga desliga, a tensão sobe,
a carga religa, a tensão cai, e o fluxo nunca converge"*. E o próprio `_pv`
registra um segundo caso da família, em `MODELOS_V6`, com Vmax de 1e+69.

Três precedentes internos apontando para o mesmo lugar. Medindo:

| faixa | irrad 75% | irrad 100% | Vmax |
|---|---:|---:|---:|
| padrão (0,85–1,10) | **73/96** | 35/96 | 1,229 |
| 0,10–2,00 (nunca troca) | 60/96 | 57/96 | 1,229 |
| 0,80–1,20 | 70/96 | 63/96 | 1,229 |
| 0,85–1,50 | 72/96 | **66/96** | 1,229 |

Alargar recupera muito em 100% e **piora em 75%**, e não restaura 96/96 em
nenhuma configuração. É mitigação, não correção: trocaria um regime por outro.
**Não foi adotada.**

### O que o experimento encontrou sem estar procurando

**`Vmax = 1,229` nos quatro cenários, e idêntico em 75% e 100%.**

Se fosse sobretensão causada pela injeção fotovoltaica, 100% teria de dar mais
que 75%. Não dá — nem na terceira casa. **A tensão de 1,229 pu não vem da
geração.** No histórico deste projeto, barra acima de 1,10 quase sempre
significou base de tensão errada (foram 2.805 barras na DALP, pelo `0,127` no
`Voltagebases`).

Puxando a pista, **com a geração desabilitada**, na DALP:

```
22 barras acima de 1,10 pu (de 17.220)
   as 22 com base 0,1201 kV — e so existem 36 barras nessa base

bases em uso:  50,8068 (63) | 19,9186 (967) | 7,9674 (14.699)
               0,2540 (24)  | 0,1386 (903)  | 0,1328 (511)
               0,1270 (17)  | 0,1201 (36)   <- 22 das 36 acima de 1,10
```

**61% das barras de uma base específica estão acima de 1,10 pu, e as outras
sete bases não têm nenhuma.** Anomalia concentrada num único nível é assinatura
de base mal atribuída, não de física de rede.

E `0,1201 = 208/√3`. O suspeito é a colisão entre a meia-bobina do
transformador de derivação central — que sai em `TEN_LIN_SE / 2`, tipicamente
0,12 kV — e a entrada de 208 V do `Voltagebases`, cujo fase-neutro é 0,1201.
Um número praticamente idêntico ao outro.

### Rastreado até os transformadores, e o suspeito inicial caiu

As 22 barras são secundário de transformadores **trifásicos de dois
enrolamentos, 13,8 → 0,24 kV**. Não são de derivação central: a hipótese da
meia-bobina, escrita acima, **está errada**.

Com a base correta (`0,24/√3 = 0,1386`) os 0,1456 kV medidos dariam **1,050 pu**
— normal para uma rede alimentada a 1,09. Com a base atribuída, 1,212 pu.

O que foi eliminado, medindo:

| hipótese | teste | resultado |
|---|---|---|
| meia-bobina de derivação central | tipo dos 22 transformadores | **refutada** — todos 3f, 2 enrolamentos |
| texto do transformador diferente | diff contra um sadio | **refutada** — idênticos salvo `Xhl`, `kVA`, `%R` |
| presença de geração na barra | remover o `GD.dss` inteiro | **refutada** — 0 barras mudam de base |
| base do primário diferente | censo dos 355 | **refutada** — 7,9674 nas 22 e nas 333 |
| ordem de atribuição | `CalcVoltagebases` de novo, com a rede resolvida | **refutada** — 0 das 22 mudam |

A correlação com geração chegou a parecer causa numa comparação 1-a-1, e a
população desmentiu: das 22 anômalas 18 têm GD, e das 333 sadias 202 também
têm. Eu havia escolhido, por azar, uma barra sadia sem GD. **Comparação de um
par não é medida.**

### A pista que sobrou, e ela é numérica

`0,24 / 2 = 0,1200`, e a base atribuída é **`0,1201`** — o fase-neutro da
entrada `0,208` do `Voltagebases`. São o mesmo número até a quarta casa.

Isso sugere que o traçado do OpenDSS calculou **metade** da tensão de linha
para essas 22 barras e depois encaixou no vizinho mais próximo da lista. Por
que metade, em transformador que não é de derivação central, é o que falta
descobrir — e exige ler a atribuição de bases do próprio motor.

Fica **sem correção**. São 22 barras de 17.220, e o efeito é de *relato*, não
de física: a tensão em volts está certa, só o pu é que não. Mas é a mesma
doença do `0,127`, que já custou 2.805 barras, e por isso vale fechar.

Consequência imediata: a linha `0,1201 (208 V) | 1.060 nós | mediana 0,8318 |
80,2% abaixo de 0,93` da tabela da equipe externa **é, em parte, artefato de
base** — não retrato da rede.

### E a lição, que é a mesma de sempre

O número **1.669.937 barras, 4 iterações, sem NaN** estava no `PLANO.md` como
estado corrente. **Eu o tratei como linha de base durante toda a validação de
hoje sem nunca ter reproduzido.** Ele é da era V8, e não há `validacao.json`
da V9 no disco que o confirme.

Se o controle não tivesse sido rodado, o desfecho seria desfazer a âncora de
AT — a correção que resolve seis bases — para consertar um defeito que não
existia.
