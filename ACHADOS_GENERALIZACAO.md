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

Três saídas foram consideradas — mais memória, `--bt nenhum` no modelo geral,
ou aceitar o recorte por subestação. **Nenhuma foi adotada, porque havia uma
quarta e ela é melhor.**

### A saída: decompor, sem apagar nada

Dois modelos acoplados, em vez de um monólito:

| | elementos | |
|---|---:|---|
| `MASTER-GERAL` | 2.391.177 | não cabe em 15,8 GB |
| **`MASTER-AT`** | **19.498** | **0,82% do porte** |
| `MASTER-<SE>` × 155 | intactos | BT completa, nada apagado |

O `MASTER-AT` é a malha de 88 kV com os transformadores de potência e cada
subestação representada pela demanda que ela de fato tem. O porte dele escala
com a **subtransmissão**, não com a concessão — cabe em qualquer máquina e
continua cabendo em qualquer distribuidora.

O acoplamento é a **tensão de cabeceira**, que hoje é declarada
(`CTMT.TEN_OPE`) e não calculada. O `decompor.py` itera: resolve a AT, mede a
demanda que cada subestação puxa naquela tensão, realimenta, repete.

### Validado contra o monólito, na base onde ele cabe

Roraima. O `MASTER-GERAL` dela compila (232.579 barras, 11 iterações), então
serve de referência:

| erro contra o monólito | mediano | p90 | pior |
|---|---:|---:|---:|
| premissa declarada *(hoje)* | 0,0220 | 0,0439 | 0,0807 |
| **decomposição AT↔SE** | **0,0081** | 0,0267 | 0,0439 |

**A decomposição erra 2,7× menos que a premissa que ela substitui**, e o pior
caso cai pela metade. Não é exata — é melhor, e isso está medido.

O laço converge em 4 iterações: deslocamento máximo 0,0344 → 0,0086 → 0,0033 pu.

### Duas decisões que o número forçou

**Realimentar o REATIVO, não só a potência ativa.** Com pf fixo em 0,92 o erro
mediano ficava em 0,0162 pu; realimentando kW *e* kvar caiu para 0,0081 — pela
metade. Numa malha de 88 kV o X domina o R, e a queda de tensão é comandada
pelo reativo. Fixar o fator de potência erra a tensão diretamente.

**Carga de potência constante (`Model=1`).** Com impedância constante a
demanda cairia junto com a tensão, e o resultado sairia otimista justamente no
caso que interessa medir: o da subestação mal alimentada.

### O que a decomposição já revelou em Roraima

A tensão de cabeceira declarada é **1,0000 em todas as 12** subestações da
malha. A calculada vai de **0,8754 a 0,9932**, e **10 das 12 diferem em 0,01 pu
ou mais — todas para baixo**. A pior opera 12,5 pontos abaixo do que o modelo
isolado dela supõe.

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

> **FECHADO em 12/08/2026 — ver o achado 17.** A causa não era a atribuição de
> base, e a conclusão "o efeito é de relato, não de física" estava errada. As
> 22 barras são a parte visível de 24 transformadores cujo primário bifásico
> foi escrito como trifásico. Duas das três fases de cada secundário estão
> genuinamente em meia tensão, com carga e sem carga. A base errada apenas
> **inverte o sinal** do defeito no relatório, e por isso ele passou um mês
> aparecendo como sobretensão.

### E a lição, que é a mesma de sempre

O número **1.669.937 barras, 4 iterações, sem NaN** estava no `PLANO.md` como
estado corrente. **Eu o tratei como linha de base durante toda a validação de
hoje sem nunca ter reproduzido.** Ele é da era V8, e não há `validacao.json`
da V9 no disco que o confirme.

Se o controle não tivesse sido rodado, o desfecho seria desfazer a âncora de
AT — a correção que resolve seis bases — para consertar um defeito que não
existia.

---

## Achado 16 — um trecho de 1 mm custou 3,5 h da rodada de sete bases

A regeração V10 gastou **221,6 min no `verifica` da Equatorial PA**, contra
6,4 min nas 129 subestações da Enel CE. Perfilando, o custo não estava
distribuído:

| medição | resultado |
|---|---|
| as 10 maiores subestações da EQPA, cronometradas | **3,2 min somadas** |
| as medianas, nos dois motores | 2,5 s cada — mais rápidas que as da ENCE |
| 119 subestações a esse ritmo | ~10 min, não 221,6 |

Sobravam ~216 min. Eles estavam numa subestação só, a **CUO**, que o log já
apontava e que eu tinha lido como ruído:

```
(#183) Y matrix build aborted due to error in primitive Y calculations
Matrix Inversion Error for Line "13302_10678971"
```

### A causa: o guarda protege a entrada e o formato desfaz na saída

```python
comp = num(col['COMP'][i], 1.0)
if comp <= 0:
    comp = 1.0                                   # o guarda
...
f'LineCode={lc} Length={comp:.2f} Units=m'       # e aqui ele é desfeito
```

O trecho `13302_10678971` tem **COMP = 0,001 m** na BDGD. Passa no guarda,
porque é positivo, e o `{:.2f}` escreve `Length=0.00`. Com comprimento zero a
matriz de impedância fica toda nula, o OpenDSS não consegue invertê-la e
**aborta a montagem da Y da rede inteira** — uma linha derruba a subestação.

São **três lugares** com a mesma forma, e o pior é a BT, que escreve o neutro
em km: `Length={comp/1000:.5f}` zera abaixo do mesmo 0,005 m.

| arquivo | o que escreve | zera abaixo de |
|---|---|---|
| `linhas.gerar` (MT) | `{comp:.2f}` em metros | 0,005 m |
| `linhas.gerar_bt` (fases) | `{comp:.2f}` em metros | 0,005 m |
| `linhas.gerar_bt` (neutro) | `{comp/1000:.5f}` em km | 0,005 m |
| `subtransmissao.linhas` (AT) | `{comp:.2f}` em metros | 0,005 m |

### A população: 6 trechos em 24,4 milhões

Censo de `SSDAT` + `SSDMT` + `SSDBT` nas sete bases:

| base | trechos | `COMP <= 0` | zeram no formato | alimentadores atingidos |
|---|---:|---:|---:|---:|
| Roraima | 299.105 | 0 | 0 | 0 |
| Enel CE | 2.783.883 | 0 | 0 | 0 |
| **Equatorial PA** | **2.640.585** | 0 | **5** | **5** |
| Enel SP | 3.894.761 | 0 | 0 | 0 |
| **Light** | **2.790.795** | 0 | **1** | **1** |
| CPFL Paulista | 3.549.487 | 0 | 0 | 0 |
| Cemig-D | 12.010.712 | 0 | 0 | 0 |

Nenhuma base tem `COMP <= 0` — o guarda existente nunca disparou uma vez em 24
milhões de registros. **O caso que ele deveria pegar não é o que aparece.**

O menor comprimento positivo revela que a maioria das distribuidoras aplica um
piso na própria BDGD: 1,00 m na Enel SP e na CPFL, 1,02 m na Enel CE, 0,10 m na
Cemig-D. A Equatorial PA não aplica nenhum — o menor dela é **0,001 m**.

Dos 5 da Equatorial, **4 estão na SSDBT**, em 4 alimentadores distintos. Eles
não quebraram a rodada porque ela roda com `--bt agregado` e a SSDBT não é
emitida. **Com `--bt completo` seriam 4 subestações a mais paradas**, e o modo
completo é justamente para onde o projeto está indo.

### E o segundo defeito, que é o que transformou o erro em 3,5 h

O `verifica` roda os dois motores. No C-API a compilação levanta exceção e ele
devolve `compila: False` sem resolver. No COM, `Error.Number` volta **zero**
depois do mesmo aborto, e o `verifica` segue para o `Solve` — que não falha
rápido: gira. Sozinho, esse `Solve` consumiu ~3,5 h das 3,7 h da etapa.

Não é um defeito de desempenho. É um modelo impossível sendo resolvido em
silêncio, e o único sintoma foi o relógio.

---

## Achado 17 — o primário bifásico escrito como trifásico

Este achado **substitui** o diagnóstico das 22 barras de base `0,1201`. Aquele
diagnóstico dizia que o efeito era "de relato, não de física". Ele é dos dois,
e a física é a parte grave.

### O que a medição encontrou

Na DALP, `MODELOS_SP_V10` reproduz o achado registrado número a número — 36
barras na base 0,1201, 22 acima de 1,10 pu. Separando por quem alimenta a barra,
são **duas populações distintas** que estavam sendo contadas como uma:

| população | n | base | acima de 1,10 pu |
|---|---:|---|---:|
| trafo monofásico de 3 enrolamentos, `[MT, 0,12, 0,12]`, ligado `.1.4` e `.4.2` | 14 | 0,1201 — **certa** | 0 |
| trafo trifásico de 2 enrolamentos, 13,8→0,24 kV | 22 | 0,1201 — **errada** | 22 |

A meia-bobina de derivação central, que o achado anterior deu por refutada,
**existe** — são as 14. Só que não são elas as doentes.

### O padrão, e ele é limpo demais para ser numérico

```
doente   [69,8 | 69,8 | 139,4]     duas fases em exatamente metade da terceira
sadio    [139,3 | 139,1 | 139,7]
```

Com toda a carga e toda a geração desligadas o padrão **não muda** — 24 de 355
transformadores, os mesmos 24. É topológico.

O primário resolve: nos 24, um dos três nós de média tensão está em **2.172 V**
e os outros dois em **8.689 V** — 75% de desequilíbrio, contra 0,0% nos 331
sadios. E 2.172 = 8.689/4 é a tensão de um nó que **não é alimentado** e fica
preso apenas pelas bobinas do delta.

O trecho que chega nessas barras é bifásico:

```
New Line.5104165S1  Bus1=...46880022.2.3  Bus2=...46880013.2.3  LineCode=CND_66_2F
New Line.5094792S1  Bus1=...46888128.3.1  Bus2=...46888101.3.1  LineCode=CND_1713_2F
```

E o transformador é escrito com as três fases:

```
New Transformer.14257963 phases=3 windings=2 Xhl=2.200
~ wdg=1 bus=2345093246880013.1.2.3 conn=delta Kv=13.8 ...
```

### A BDGD tinha o dado, e o conversor o descarta

Nos 23 transformadores encontrados na `UNTRMT`, `FAS_CON_P` declara **duas
fases** — 14 em `BC`, 8 em `AB`, 1 em `CA` — e `FAS_CON_S` declara `ABCN` nos
23. O campo do primário concorda com a rede em 17 dos 23 casos.

O conversor **lê esse campo e não o usa**:

```python
fp = _fases(col['FAS_CON_P'][i], 'A')      # calculado
...
if len(fs) >= 3:                            # decidido pelo SECUNDARIO
    out.append(f'... bus={b1}.1.2.3 conn=delta ...')   # e fp e descartado
```

`fp` é computado e não aparece em nenhum lugar do ramo trifásico. Nos outros
dois ramos ele é usado (`nd_p`). É um valor calculado e silenciosamente jogado
fora — a assinatura mais barata de encontrar e a mais fácil de não ver.

### Por que só apareceu como sobretensão

O OpenDSS atribui base lendo o **primeiro nó** da barra, multiplicando por raiz
de 3 e encaixando no vizinho mais próximo de `Voltagebases`. Nas 21 barras em
que o nó 1 calhou de ser uma das fases pela metade:

```
69,8 V x raiz(3) = 0,1208 kV  ->  vizinho mais proximo: 0,208
                              ->  base = 0,208/raiz(3) = 0,1201
```

e a fase **sadia** passa a marcar `139,4 / 120,1 = 1,16 pu`. Nas outras 3, o nó
1 é a fase cheia, a base sai 0,1386, e as duas fases pela metade aparecem como
**subtensão de 0,50 pu** — o mesmo defeito com o sinal trocado.

O `14257002` é o par de controle perfeito: mesmo defeito, `[139,1 | 69,6 |
69,6]`, e base 0,1386 porque o nó 1 é a fase cheia. Ele nunca foi contado.

### O que fica

`FAS_CON_P = BC` com `FAS_CON_S = ABCN` não é dado inconsistente: é a descrição
de um **banco em delta aberto (V-V)** — duas unidades monofásicas entre duas
fases entregando três no secundário. É isso que o conversor precisa escrever, e
não um trifásico em `.1.2.3` pendurado numa fase que não existe.

**Correção retida** enquanto a rodada V10 está em voo: ela muda a saída do
conversor, e aplicá-la agora deixaria RR/ENCE/EQPA/SP com um código e
LT/CPFL/CMIG com outro — que é exatamente o que torna a comparação entre bases
inútil. Vale para os dois achados desta noite.

---

## Achado 13, continuação — a decomposição em escala de 125 subestações

A decomposição AT-SE tinha sido validada em Roraima, onde são 12 subestações na
malha. A Enel CE dá o teste de escala:

| | Roraima | **Enel CE** |
|---|---:|---:|
| subestações na malha | 12 | **125** |
| iterações até < 0,002 pu | 4 | **5** |
| deslocamento final | 0,0033 | **0,0022** |
| tensão de cabeceira calculada | 0,8754 – 0,9932 | **0,9035 – 1,0442** |
| diferem da declarada em >= 0,01 pu | 10 de 12 | **115 de 125** |
| diferença mediana | −0,0294 | **−0,0248** |
| pior caso | −0,1246 | **−0,1065** |

A Enel CE não declara 1,0000 como Roraima: ela declara 1,02–1,05, vindo de
`CTMT.TEN_OPE`. Mesmo assim **as 115 diferenças são todas para baixo**, e a
mediana é praticamente a mesma das duas bases. O laço converge com dez vezes
mais subestações sem mudar de comportamento.

---

## Achado 15 FECHADO — e a causa é o achado 17

O achado 15 estava aberto desde o relatório da equipe externa, com três
hipóteses caídas: tensão de cabeceira, impedância do aterramento de neutro
(fator 500) e a faixa `Vminpu`/`Vmaxpu` do `PVSystem`. A quarta hipótese só
existiu depois do achado 17, e ela não vem da geração — vem das barras.

**O raciocínio.** A DALP tem 24 transformadores cujo primário bifásico foi
escrito como trifásico, e duas das três fases de cada secundário ficam em
**0,50 pu** da base verdadeira. O padrão do `PVSystem` é `Vminpu = 0,85`.
Abaixo disso ele deixa de ser injeção de potência constante e vira impedância
constante — que é exatamente o mecanismo de troca de modelo já documentado no
`cargas.py`: *"a carga desliga, a tensão sobe, a carga religa, a tensão cai, e
o fluxo nunca converge"*. **Um inversor a 0,50 pu está permanentemente do lado
errado da faixa.**

**O experimento, com controle de população** — que é a lição que este projeto
já pagou duas vezes:

| irradiância | base | desligando os 126 inversores das 24 barras | controle: 126 inversores sorteados entre barras sadias |
|---:|---:|---:|---:|
| 0,25 | 96/96 | 96/96 | 96/96 |
| 0,50 | 96/96 | 96/96 | 96/96 |
| **0,75** | **73/96** | **96/96** | **73/96** |
| **1,00** | **35/96** | **96/96** | **35/96** |

A coluna `base` reproduz **os dois números registrados no achado 15** — 73/96 e
35/96 — sem ajuste nenhum. O tratamento recupera **96/96 nas quatro
irradiâncias**. O controle, com a mesma quantidade de inversores desligados e
semente fixa, ganha **exatamente zero passos**.

Ganho somado: **+84 passos no tratamento, +0 no controle.**

**126 inversores, 3,0% dos 4.218, explicam 100% da falha de convergência.**

E fecha a última pergunta aberta do achado 15 — por que `Vmax = 1,229` era
idêntico em 75% e 100%: aquela tensão nunca veio da geração. Ela é a fase sadia
de uma barra da base 0,1201, dividida pela base errada. Os dois sintomas que
pareciam dois problemas eram o mesmo defeito visto de dois ângulos.

**Consequência para a equipe externa:** a correção do achado 17 resolve o
problema de convergência que eles relataram. Não é ajuste de parâmetro do
inversor, não é modo de controle e não é algoritmo — é conexão de fase.

---

## Achado 18 — a fonte duplicada, e o silêncio de um motor

A decomposição AT-SE não rodou na Equatorial PA:

```
(#266) Duplicate new element definition: "Vsource.FONTE_SSB_88kv".
Element being redefined.       [_AT/Trafos_Transmissora.dss, linha 112]
```

`trafos_transmissora` percorre pares **(subestação, nível de MT)**, mas a fonte
pertence ao **pátio**, que é (subestação, nível de AT). Uma subestação que
alimenta 13,8 kV e 34,5 kV a partir do mesmo barramento de 88 kV passava duas
vezes pela mesma fonte.

A linha repetida era **idêntica** — nome, barra, `basekV` e `MVAsc` saem todos
de `(sub, kv1)` —, então não havia diferença elétrica nenhuma. O estrago era o
tratamento, e ele difere por motor:

| motor | o que faz com a duplicata exata |
|---|---|
| DSS C-API | recusa, e o `MASTER-AT` inteiro deixa de compilar |
| OpenDSS COM (EPRI) | aceita calado, e a segunda definição apaga a primeira |

Nenhum dos dois é o que se quer de uma duplicata exata.

Medido nas quatro bases já regeradas: **2 na Equatorial PA** (SSB e TUR), **0**
em Roraima, **0** na Enel CE, **0** na Enel SP — que tem 19.484 elementos de AT.

**Corrigido** (`transmissao.trafos_transmissora`), com 8 testes. É a única
correção desta noite que foi aplicada com a rodada em voo, porque ela só pode
remover linha exatamente repetida, e nenhuma métrica da V10 lê esse arquivo —
os modelos por subestação não o redirecionam, e a Equatorial PA fechou 118/119
no `verifica` com a duplicata presente.

O arquivo já gerado da `MODELOS_EQPA_V10` recebeu a mesma dedup à mão, com
cópia em `.antes_da_dedup`, para que a decomposição pudesse rodar nela hoje.

---

## Achado 19 — a tensão da fonte de AT é fixa em 88 kV

Deduplicadas as fontes, o `MASTER-AT` da Equatorial PA compila com 110
subestações e **não converge**: 100 iterações, 12 nós NaN, 27 em tensão zero, 7
cargas de subestação mortas.

As barras mortas têm base **79,6743** — que é `138/√3`.

| base | primário dos transformadores de AT | `basekV` das fontes | converge |
|---|---|---|---|
| Roraima | 88 kV x29 | 88 kV x18 | sim |
| Enel CE | 88 kV x208 | 88 kV x118 | sim |
| **Equatorial PA** | **88 kV x113 e 138 kV x107** | **88 kV x116** | **não** |
| Enel SP | 88 kV x425, 138 kV x12 | 88 kV x144, 230 x1, 345 x2 | sim |

**Metade da malha da Equatorial PA é de 138 kV e recebe fonte de 88 kV.**
Roraima e Enel CE convergem porque são 88 kV puras — não porque o código
esteja certo.

### É a mesma forma do achado 17

O `subtransmissao.trafos` **calcula** a tensão primária de cada transformador,
de `EQTRAT.TEN_PRI`, e a escreve no próprio transformador:

```python
kv1 = tensoes.kv(e.get('ten_pri'), kv_at_padrao, log, 'EQTRAT.TEN_PRI')
...
f'~ wdg=1 bus={no_at}{nd1} conn={conn1} kV={kv1:.4f} ...'
```

E depois **não a devolve**. O dicionário de retorno traz `barra_do_trafo`,
`kv_da_barra`, `pac_at`, `por_sub`, `mva_por_sub` — a tensão de MT está lá, a
de AT não. Sem ela, `fontes()` não tem de onde tirar o nível do pátio e usa o
parâmetro global:

```python
f'New Vsource.{nome} bus1={barra} basekV={kv_at_padrao} pu=1.0 ...'
```

Dois achados na mesma noite com a mesma assinatura: **um valor é calculado
corretamente e não chega onde é necessário.** No achado 17 é `fp` dentro da
mesma função; aqui é `kv1` atravessando a fronteira de dois módulos.

### O que a correção precisa fazer

Devolver `kv_at_do_trafo` em `info_trafos` e, em `fontes()`, tirar o `basekV` de
cada fonte dos transformadores daquele pátio — e registrar quando eles
discordarem entre si, porque pátio com dois níveis de AT é caso real (a TBAN da
Enel SP tem 88 e 345).

**Correção retida** enquanto a rodada V10 está em voo, pelo mesmo motivo dos
achados 16 e 17: ela muda a saída do conversor.

---

## As três correções retidas, medidas no modelo que elas produzem

Escritas num *worktree* separado (`correcoes-retidas`), sem tocar na árvore que
a rodada V10 está usando. Teste verde prova que a função faz o que o teste diz;
o que segue prova a outra coisa, que é a que importa: **que o modelo gerado
deixou de ter o defeito.**

### Regressão primeiro

Roraima convertida com as três correções: o `MASTER-AT.dss` sai **byte a byte
idêntico** ao da `MODELOS_RR_V10`. Onde não havia defeito, nada mudou.

### A DALP, convertida com as correções

| | antes (`MODELOS_SP_V10`) | depois |
|---|---:|---:|
| linhas com `Length=0.00` | 1 | **0** |
| transformadores com duas fases pela metade | 24 | **0** |
| barras na base 0,1201 | 36 | 20 |
| barras acima de 1,10 pu | 22 | **0** |
| **dia inteiro em irradiância 1,00** | **35/96** | **96/96** |
| `Vmax` | 1,229 | **1,0791** |
| `MASTER-AT`: converge / NaN / subestações mortas | — | sim / 0 / 0 |

**O dia fecha 96/96 em irradiância plena sem desligar inversor nenhum.** A
correção do achado 17 resolve o achado 15 sozinha, e o `Vmax` cai de 1,229 para
1,0791 — que é um número plausível para rede alimentada a 1,09, e não o
artefato de base que era antes.

As 20 barras que continuam na base 0,1201 são as **legítimas**: secundário de
transformador monofásico de derivação central, onde o nó 1 fica em 120 V por
construção e 0,1201 é a base certa.

### O que cada correção faz

| achado | onde | o que muda |
|---|---|---|
| 16 | `linhas.comprimento`, usada nas três camadas | piso de `COMP_MINIMO = 0,01 m`. 1 cm está abaixo de qualquer medição real (o menor piso entre as sete distribuidoras é 0,10 m, da Cemig-D), acima da resolução dos dois formatos de saída, e não move o km do relatório. O 1,0 m continua valendo só para campo **ausente**, onde não há dado a preservar |
| 17 | `transformadores.gerar` | o delta trifásico passa a exigir três fases **dos dois lados**; e `Kv` do primário passa a depender de quantos nós o enrolamento toca — dois nós é fase-fase e vê 13,8 kV, um nó vê 13,8/√3 |
| 19 | `subtransmissao.trafos` + `transmissao.fontes` | `kv_at_do_trafo` passa a ser devolvido e a fonte de cada pátio sai no nível dos transformadores que estão nele. Pátio com mais de um nível recebe a fonte no mais alto, **e isso é registrado no log e no arquivo** |

190 testes, e as 5 falhas esperadas deixam de ser esperadas.

### O que ainda não foi medido

A Equatorial PA, que é onde o achado 19 aparece (107 dos 220 transformadores de
AT em 138 kV) e onde estão 5 dos 6 trechos do achado 16, **não foi reconvertida**
— são ~35 min de conversão e a máquina está com a rodada V10 em voo. Fica como
a primeira coisa a rodar quando ela fechar.

---

## Correção de relato — quanto da concessão a decomposição realmente cobre

Registrei que "10 de 12 subestações de Roraima diferem da declarada" **sem
dizer que 12 não era o total**. Roraima tem 20 subestações modeladas; o
`MASTER-AT` escreve 18 como carga equivalente; e apenas **12 chegam a receber
tensão**. As outras 8 ficam com a tensão de cabeceira declarada e nunca são
medidas — o que é um resultado legítimo, mas só se for dito.

| base | subestações modeladas | no `MASTER-AT` | com tensão | cobertura | AT converge |
|---|---:|---:|---:|---:|---|
| Roraima | 20 | 18 | 12 | **60,0%** | sim |
| Enel CE | 129 | 127 | 125 | **96,9%** | sim |
| Equatorial PA | 119 | 117 | 110 | 92,4% | **não** (achado 19) |
| **Enel SP** | **155** | **155** | **154** | **99,4%** | sim |

**A base que menos cobre é justamente aquela em que a decomposição foi
validada.** Roraima serviu de referência porque é onde o monólito cabe — e é a
rede mais fragmentada das quatro, com 8 subestações fora do alcance da malha.
A validação contra o monólito continua valendo para as 12 que ela alcança; o
que não vale é ler "10 de 12" como se fossem 10 de 20.

Na Enel SP, que é a base do trabalho, a decomposição alcança **154 das 155**.

A causa das mortas é a mesma dos 844 componentes desconexos já registrados: o
pátio de AT dessas subestações não tem transformador na `UNTRAT`, ou a barra
não se liga a nenhuma fonte. Não é defeito novo — é o alcance da camada de AT,
e agora ele tem número por base.

---

## Achado 20 — a subtransmissão só se conecta ao resto do modelo na Enel SP

A Equatorial PA declara **21.811 trechos na `SSDAT`** e o conversor emite
**zero**:

| base | trechos de AT emitidos | km |
|---|---:|---:|
| Roraima | 169 | 13,2 |
| Enel CE | 4.024 | 1.522,2 |
| **Equatorial PA** | **0** | **0,0** |
| Enel SP | 16.490 | 896,8 |

O filtro de `subtransmissao.linhas` descarta o trecho cujo `PAC_1` não esteja
entre os nós dos pátios energizados. A primeira suspeita foi a **assimetria do
filtro** — ele olha só o `PAC_1`, e um trecho com `PAC_2` na malha e `PAC_1`
fora seria descartado sem motivo. Medindo, a causa é outra e é maior.

### O espaço de nomes da SSDAT não é o das outras tabelas de AT

| base | PACs distintos na `SSDAT` | na `UNSEAT` | `SSDAT ∩ UNSEAT` | `SSDAT ∩ UNTRAT` |
|---|---:|---:|---:|---:|
| Roraima | 3.891 | 306 | **7** | 0 |
| Enel CE | 15.636 | 2.729 | **102** | 0 |
| Equatorial PA | 21.968 | 493 | **0** | 0 |
| **Enel SP** | 32.213 | 5.244 | **5.224** | **435** |

```
RR     SSDAT  1203737              UNSEAT  511
ENCE   SSDAT  100351899            UNSEAT  02b1-aca
EQPA   SSDAT  a100000              UNSEAT  aaz_490000010
SP     SSDAT  -1001043072b58bdbh   UNSEAT  -10470-2882b58b02a
```

Nas três primeiras a `SSDAT` usa identificador numérico e a `UNSEAT`/`UNTRAT`
usam mnemônico da subestação. **Só na Enel SP as duas famílias compartilham a
mesma codificação**, e é por isso que só lá a interseção é praticamente total
(5.224 de 5.244 PACs de chave).

Não é defeito do conversor: é como cada distribuidora exportou. E não é o
filtro: com interseção zero, nenhum critério sobre `PAC_1` ou `PAC_2` salvaria
a Equatorial PA.

### O que isso significa para a generalização

O `de_para_mnemonicos.csv` foi construído **para a Enel SP** — ele resolve
`CTAT.NOME` ("LTA ANH-MUT 1") em código de subestação, e é o que permite fechar
as componentes desconexas. Nas outras bases ele tem alcance parcial (86
mnemônicos na Equatorial PA) e não chega à `SSDAT`.

Consequência honesta, e ela pertence ao artigo:

> **A topologia de subtransmissão é efetivamente modelada em uma das quatro
> bases.** Nas outras, a camada de AT é uma coleção de pátios com fonte
> equivalente, ligados por chaves da `UNSEAT`, sem os trechos de linha que os
> unem. Isso não invalida os modelos por subestação — eles não dependem da
> `SSDAT` —, mas limita o que a decomposição AT↔SE pode afirmar fora da
> Enel SP.

Isso também explica, sem hipótese nova, três coisas já medidas: a cobertura de
**60% em Roraima**, os **97 pátios** da Equatorial PA que não se juntam, e o
fato de o `MASTER-AT` dela ter 1.458 chaves e nenhum trecho.

### Confirmação numérica do achado 19, de quebra

Rodando a decomposição na Equatorial PA da V10 (com as fontes duplicadas
removidas à mão), as subestações saem em **0,6250 – 0,6298 pu**, e
`88/138 = 0,6377`. É a assinatura exata de fonte de 88 kV alimentando barra de
138 kV, com a queda da malha por cima. O laço até "converge" em 5 iterações —
e o `decompor` avisa, em toda iteração, que o modelo de AT não convergiu e que
os números não valem.

---

## Achado 21 — a cabeceira de cada alimentador é invisível à checagem de sobrecarga

O vão de saída é escrito como chave, sem ampacidade:

```python
f'New Line.VAO_{cod} phases=3 Bus1={alvo}.1.2.3 Bus2={pac}.1.2.3 '
f'Switch=y r1={R_VAO} r0={R_VAO} x1=0 x0=0 c1=0 c0=0'
```

e o `validador` conta sobrecarga varrendo **todas** as linhas:

```python
na = dss.CktElement.NormalAmps()
if na > 1:
    ... if mx > na: sob += 1
```

Então o vão entra na conta com a ampacidade que o OpenDSS inventou. Medindo em
12 subestações da Enel SP, 130 vãos:

| | |
|---|---|
| `normamps` encontradas | **400,0 A em todos os 130** — o padrão do OpenDSS para `Switch=y` |
| corrente máxima num vão | 306,1 A |
| `I/normamps` | mediana 0,229 · p90 0,449 · **máx 0,765** |
| sobrecargas contadas que são vão | **0 de 5.092** |

**O número do validador não está inflado — e também não está medindo nada.**
Os 400 A são um valor que ninguém escolheu; ele simplesmente calha de estar
acima da maior corrente de cabeceira da amostra. Numa base cujo condutor de
cabeceira seja mais fino — e a Enel SP tem o caso do 593, com 31 A carregando a
maior fatia de km da rede (achado 11) —, uma sobrecarga real na saída da
subestação passaria despercebida.

O dado existe: a ampacidade da cabeceira é a do primeiro trecho de `SSDMT` a
jusante do vão, que já está no `LineCode` daquele trecho. A correção é herdar
`normamps` dele em vez de aceitar o padrão.

Fica **aberto**, junto com os achados 16, 17 e 19, para depois que a rodada V10
fechar.

### Um número que apareceu de lado e merece nota

**5.092 linhas acima da ampacidade em 12 subestações** — 1.214 só na DANC. Não
é novidade em si (é a assinatura do achado 11), mas é a primeira vez que ele
aparece contado por subestação, e a distribuição é muito desigual: de 18 linhas
na DAUG a 1.214 na DANC.

---

## Achado 22 — o modo `--bt completo` funciona, e o contador do log mente

O objetivo do projeto é a rede completa AT+MT+BT, e o modo `completo` da
`cargas.gerar_bt_completa` estava escrito sem nunca ter sido exercitado a
fundo. Rodando na 5003525 de Roraima (5 alimentadores):

O log do conversor imprime **`5.679 linhas` nos dois modos**. Isso assusta e é
falso: o contador só soma a MT. Compilando os dois modelos, o OpenDSS vê:

| | `--bt agregado` | `--bt completo` | fator |
|---|---:|---:|---:|
| barras | 6.994 | **15.990** | 2,3× |
| nós | 15.530 | **45.000** | 2,9× |
| linhas | 6.277 | **24.267** | 3,9× |
| transformadores | 729 | 729 | 1,0× |
| cargas | 1.079 | **7.390** | 6,8× |
| converge | sim, 3 it | **sim, 5 it** | |
| tensão média | 0,9199 | **0,8592** | −6,1 pontos |
| tensão mínima | 0,1539 | **0,0100** | |
| cargas sem tensão | 3 | **15** | |

**A rede de BT está lá e o modelo fecha.** `LinhasBT.dss` (861 KB) e
`Ramais.dss` (1,4 MB) são redirecionados pelo `REDE-<SE>.dss`, e o
`_ATERRAMENTO.dss` sobe para 57 KB — o neutro explícito do achado que custou
29.834 cargas sem tensão na primeira tentativa está funcionando.

### O que o modo completo revela, e que o agregado escondia

A tensão média cai **6,1 pontos** e as cargas mortas vão de 3 para 15. Não é
surpresa que a BT tenha queda — é para isso que ela existe no modelo —, mas
`Vmin = 0,0100` é nó praticamente morto, e 12 cargas novas sem tensão são
trechos de BT que não fecham.

**Isso é o próximo trabalho, e agora tem número.** O modo completo não está
pronto para ser o padrão; está pronto para ser depurado, que é diferente de
estar escrito e nunca ter rodado.

### Escala

2,3× em barras por subestação. Para a Enel SP, cujos modelos por subestação
hoje têm ~17 mil barras cada, isso dá ~40 mil — perfeitamente tratável **por
subestação**. O que não muda é o achado 13: o monólito continua fora de
alcance, e a decomposição AT↔SE continua sendo o caminho.

E o achado 16 tem consequência direta aqui: **4 dos 5 trechos degenerados da
Equatorial PA estão na `SSDBT`**, em 4 alimentadores distintos. Eles nunca
apareceram porque a rodada usa `--bt agregado`. No modo completo, seriam 4
subestações a mais paradas com `#183 Y matrix build aborted`.

---

## Achado 23 — o passo 5 não moveu um único número de energia, e isso é o resultado

A regeração V10 existe para validar as mudanças do passo 5: âncora de AT
derivada da base, tabela de tensões vinda do censo da própria distribuidora, e
composição das parcelas de perda. Nenhuma delas foi feita para mexer na razão
de perdas — mas todas podiam. Comparando as duas rodadas na Enel SP, população
inteira e não um par:

| | V9 | V10 |
|---|---|---|
| razão modelo/declarado — mediana | **9,919** | **9,919** |
| razão — média · p10 · p90 | 11,784 · 2,779 · 22,529 | 11,786 · 2,779 · 22,529 |
| alimentadores cruzados | 1.573 | 1.573 |
| viola o limite físico | 482 | 482 |
| viola de verdade | **458 (29,12%)** | **458 (29,12%)** |
| medição degenerada | 29 | 29 |
| subestações sadias | 155/155 | 155/155 |
| cobertura de medição | 87,2% | 87,2% |
| perdas% — mediana | 7,29 | 7,30 |

**Nada se moveu além da terceira casa.**

E os modelos **mudaram** — a distribuição de bases de tensão da DALP é outra:

```
V9    0,1201 (564) | 0,1270 (562) | 0,1386 (333)
V10   0,1386 (903) | 0,1328 (511) | 0,1201 (36) | 0,1270 (17)
```

As duas coisas juntas dizem exatamente o que aconteceu: **as mudanças do passo
5 são do lado do relato, e não do fluxo de potência.** A base de tensão
corrige o pu; ela não altera a corrente que passa no condutor nem a energia que
o medidor conta. É por isso que a razão de perdas fica igual até a terceira
casa enquanto 1.400 barras trocam de base.

Consequência prática, e ela é boa: **a comparação entre distribuidoras feita na
V9 continua válida para energia**, e a V10 acrescenta o pu correto e a camada
de AT sem invalidar nada do que já estava medido. Uma regeração de 11 h que não
muda número nenhum não é desperdício — é a única forma de saber que não mudou.

### O que só a V10 tem

O `validador.py --ses` entrou na fila desta rodada, e é a primeira vez que ele
roda na concessão inteira:

| veredicto | subestações |
|---|---:|
| OK | 126 |
| TENSAO_BAIXA | 22 |
| REGULADOR_SATURADO | 5 |
| REDE_EXTENSA | 2 |

E o número que ele produziu de lado: **86.499 linhas acima da ampacidade nas
155 subestações** — mediana 422 por subestação, máximo 1.938. É a assinatura do
achado 11 medida na concessão inteira pela primeira vez.

### A tabela entre distribuidoras, com quatro das sete

| base | sadias | cobertura | razão mediana | viola de verdade | medição degenerada |
|---|---|---:|---:|---:|---:|
| Roraima | 20/20 | 88,8% | 3,95× | 10,13% | 29 |
| Enel CE | 129/129 | 94,2% | **1,32×** | **0,44%** | 0 |
| Equatorial PA | 118/119 | 93,5% | **1,10×** | **0,65%** | 121 |
| **Enel SP** | 155/155 | 87,2% | **9,92×** | **29,12%** | 29 |

A Enel SP continua discrepante por uma ordem de grandeza contra duas
distribuidoras cujo modelo fecha em 1,1–1,3×. Isso reproduz o achado 10 com o
código atual, e agora com o `validador` junto.

---

## A decomposição AT↔SE na Enel SP — a base do trabalho

Com a `MODELOS_SP_V10` fechada, a decomposição rodou na concessão inteira:

| | |
|---|---|
| subestações na malha | **154 de 155** |
| iterações até `< 0,002 pu` | **4** (0,0403 → 0,0027 → 0,0003) |
| tensão de cabeceira calculada | 0,6797 – 1,1256, mediana **1,0646** |
| diferença contra a declarada | −0,4103 a +0,1174, mediana **−0,0229** |
| diferem em ≥ 0,01 pu | **147 de 154** |

A Enel SP declara `1,09` na maioria e `1,00` em algumas — é o `CTMT.TEN_OPE`,
o comutador sob carga. A malha entrega **1,0646** na mediana: 2,3 pontos abaixo
do declarado, e **147 das 154 subestações diferem**.

Três subestações aparecem **acima** do declarado — `daug` +0,1174, `dpso`
+0,1049, `dreg` +0,0672 — todas declarando 1,00 onde a malha entrega ~1,07 a
1,12. Nas outras 144 a diferença é para baixo, como em Roraima e na Enel CE.

### Quatro dessas 154 são artefato do achado 19, e isso foi previsto antes de medir

Quatro subestações saíram muito fora da distribuição: `ditp` 0,6797, `dbav`
0,6811, `dmaz` 0,6828, `dpre` 0,6903. A previsão, escrita antes do teste, era
que fossem as alimentadas em 138 kV — porque a Enel SP tem 12 transformadores
de AT nesse nível contra 425 em 88 kV, e o achado 19 põe **todas** as fontes em
88 kV.

| nível do transformador de AT | n | pu mediano | mín | máx |
|---|---:|---:|---:|---:|
| **138 kV** | 5 | **0,6828** | 0,6797 | 1,0672 |
| 88 kV | 145 | 1,0649 | 0,9732 | 1,1256 |
| sem transformador próprio | 4 | 0,9849 | 0,9789 | 0,9930 |

E `88/138 = 0,6377`. **As quatro mais baixas são exatamente quatro das cinco de
138 kV** — a quinta, `dreg`, é alimentada por um pátio de 88 kV e sai em 1,0672,
dentro da distribuição normal.

Então o resultado honesto é: **150 das 154 valem; 4 estão contaminadas pelo
achado 19** e vão para ~1,0 quando a correção entrar. Não muda a mediana nem a
conclusão — muda o mínimo, de 0,6797 para algo perto de 1,0.

É a terceira vez esta noite que o mesmo `88/138` aparece: nos 107 trafos da
Equatorial PA, nas subestações dela em 0,626–0,630, e agora em 4 da Enel SP.

---

## A Equatorial PA reconvertida — o que a correção conserta e o que ela não conserta

A Equatorial PA é onde os achados 16 e 19 realmente aparecem: 5 dos 6 trechos
degenerados de todas as bases, e 107 dos 220 transformadores de AT em 138 kV.
Reconvertida com as três correções:

| | antes (`MODELOS_EQPA_V10`) | depois |
|---|---:|---:|
| linhas com `Length=0.00` | 1 | **0** |
| **a CUO compila** | **não** — `#183 Y matrix build aborted` | **sim** |
| **a CUO resolve o dia em irradiância 1,00** | não rodava | **96/96**, `Vmax` 0,9792 |
| transformadores com meia fase na CUO | — | 0 |
| `basekV` das fontes de AT | 88 kV × 116 | **138 kV × 52, 88 kV × 64** |

**A subestação que sozinha consumiu 3,5 h da rodada agora compila e resolve o
dia inteiro.** É a verificação do achado 16 no caso exato que o produziu.

### O achado 19 melhorou e não fechou, e a medição encontrou defeito na própria correção

Com as fontes já nos dois níveis, o `MASTER-AT` da Equatorial PA **continua não
convergindo** — 100 iterações, 12 nós NaN, 7 subestações mortas, os mesmos
números de antes. E o diagnóstico apontou **três fontes cuja `basekV` a barra
não tem**:

```
mab_490000065   fonte 138,0 kV, barra base 50,8068  (= 88/raiz(3))
jui_03b1        fonte 138,0 kV, barra base  7,9674  (= 13,8/raiz(3))
barra_at_cap    fonte 138,0 kV, barra base 50,8068
```

A primeira versão da correção escolhia o **nível mais alto do pátio**. Isso está
errado quando a barra de injeção não é desse nível — e `jui_03b1` é uma barra de
**13,8 kV** recebendo fonte de 138. Antes da correção as três também estavam
erradas, de outro jeito: todas em 88 kV. Trocar um valor errado por outro não é
progresso, e só apareceu porque a correção foi **medida no modelo em vez de
declarada pronta pelos testes**.

Regra corrigida: a fonte usa o nível do transformador cujo `PAC_1` **é** a barra
de injeção; o mais alto do pátio vira último recurso, e a escolha fica escrita
no arquivo.

Reconvertida de novo com a regra nova: **de 3 fontes desalinhadas para 2**, e
138 kV × 52 → × 50. As duas que restam — `jui_03b1` e `barra_at_cap` — não têm
transformador nenhum na barra de injeção, então o nível veio do conjunto do
pátio e não do ponto.

E `jui_03b1` fecha o caso: a barra dela está em **7,9674 = 13,8/√3**. É uma
barra de **média tensão** recebendo fonte de alta. Ali nenhuma tensão de fonte
estaria certa, porque o defeito é a **âncora** do pátio — achado 7 — e não a
tensão. A correção que cabia era outra: **contar e dizer**. Fonte cujo nível
ninguém confirmou passa a ser registrada no log, comentada no próprio arquivo e
devolvida no relatório como `nivel_deduzido`.

### A não convergência que sobra é o achado 20, e não o 19

Com 12 NaN e 27 nós em tensão zero **idênticos antes e depois**, a causa
restante não é a tensão das fontes: é a malha não ter trechos. A Equatorial PA
tem **1.458 chaves de AT e zero linhas de AT** — 284 componentes conexas que a
`SSDAT` uniria se o espaço de nomes dela casasse com o das outras tabelas.

Isso fecha o diagnóstico da subestação `TUR`, cujos nós `tur_lt_tur_brb_goi` e
`tur_490000107` são os 12 NaN: são pontas de linha de transmissão que existem na
`SSDAT` e não chegam ao modelo.

**A camada de AT da Equatorial PA não é recuperável só com correção de código.**
Ou se constrói o de-para de PACs para essa base, como já existe o de mnemônicos
para a Enel SP, ou a decomposição AT↔SE não se aplica a ela — e essa é uma
limitação da BDGD exportada, não do conversor.

---

## Achado 25 — a BT isolada: o neutro não é a causa, o ramal também não, e o método quase mentiu

A rede de baixa tensão de cada transformador é uma **ilha**: liga-se ao resto
só pelo próprio trafo. Medido na 5003525 de Roraima, **723 das 725** barras de
secundário pertencem a um transformador só. Isso torna a BT estudável sem
resolver a concessão — e o estudo inteiro abaixo custou três compilações de um
modelo de 0,3 min.

### Primeiro: separar desligada de longe

| | |
|---|---|
| cargas de BT | 7.348 |
| acima de 0,80 pu | 7.231 |
| entre 0,01 e 0,80 | 144 |
| **abaixo de 0,01** | **15** |

Das 15 sem tensão, **14 não são alcançadas por nenhum secundário** — são 3
componentes órfãs, 20 barras de 15.990 (0,13%). E a origem:

| tabela da BDGD | dos 20 PACs órfãos |
|---|---:|
| `UNTRMT.PAC_2` (secundário de trafo) | **0** |
| `SSDBT` | 10 |
| `RAMLIG` | 12 |
| `UCBT_tab` | 7 |

**Nenhum é secundário de transformador**: o conversor não perdeu trafo nenhum.
A base tem trechos de BT com unidades consumidoras penduradas que não chegam a
transformador algum. É o achado 20 um nível abaixo, e é da exportação.

### Segundo: o `K_NEUTRO`, que o próprio código convidava a contestar

`linhas.py` declara `K_NEUTRO = 1.0` como "hipótese conservadora... para poder
ser contestada". Varrendo de 0,01 (retorno quase ideal) a 3,0:

| `K_NEUTRO` | mediana na carga | < 0,92 | < 0,80 |
|---:|---:|---:|---:|
| 0,01 | 0,9323 | 2.804 | 464 |
| **1,00** | **0,9308** | **2.972** | **557** |
| 3,00 | 0,9286 | 3.178 | 683 |

**Um fator de 300 move a mediana em 0,0037 pu — 2% da queda.** A hipótese está
refutada como causa. Ela custa 168 cargas a mais abaixo de 0,92 contra o
retorno ideal: 6%, e só na cauda.

### O erro de método que a própria varredura denunciou

A primeira medição usou `Bus.puVmagAngle`, que é tensão **nó‑terra**. A carga
de BT está entre a fase e o nó 4, e quando o neutro piora **os dois sobem
juntos**:

| `K_NEUTRO` | na carga (certo) | nó‑terra (errado) |
|---:|---:|---:|
| 0,01 | 0,3702 | 0,6617 |
| 3,00 | **0,2207** | **0,7163** |

A grandeza errada melhorava enquanto a rede piorava. O sinal foi a
monotonicidade invertida — piorar o neutro por 300× não pode elevar a tensão
mínima. As duas colunas ficam no registro lado a lado de propósito.

### Terceiro: rede secundária ou ramal de ligação?

O `Ramais.dss` tem **11.262 linhas contra 6.728** do `LinhasBT.dss`, e é o
último salto, o mais fino. Parecia o suspeito. Medindo os três pontos do
caminho — secundário → fronteira → carga, sempre fase‑neutro na mesma barra:

| ponto | mediana |
|---|---:|
| pu no secundário do trafo | 0,9495 |
| pu na fronteira rede/ramal | 0,9321 |
| pu na carga | 0,9308 |

| trecho | queda mediana | fatia |
|---|---:|---:|
| **rede secundária (SSDBT)** | **0,0129** | **94,4%** |
| ramal de ligação (RAMLIG) | 0,0008 | 5,6% |

E entre as 2.972 abaixo de 0,92, a separação é ainda mais nítida: **98,3% na
rede, 1,7% no ramal**, com mediana de 1 salto de ramal e máximo de 2.

**O ramal está inocentado.** Ele é 63% das linhas e 5,6% da queda — tamanho de
arquivo não é importância elétrica, e a suspeita baseada nele estava errada.

### O que sobra, e é onde o próximo trabalho vai

O secundário do transformador já está em **0,9495** enquanto a MT da mesma
subestação está em 0,982. A rede de BT inteira custa **1,9 ponto** da mediana;
os outros ~3,3 nascem antes dela.

E a cauda é outra história: as dez piores têm o próprio secundário em
**0,8055 a 0,9255**, e uma delas perde **0,3976 pu só na rede secundária**.
São redes secundárias específicas, não um viés geral.

Então a pergunta que ficou tem forma nova, e é mais barata do que a original:
**não é "por que a BT cai", é "por que estes secundários específicos começam
baixo e por que estas redes secundárias específicas perdem 40 pontos"** — e as
duas se respondem numa ilha de dezenas de barras.

---

## Achado 26 — o `%R` do transformador de distribuição, e o próprio projeto já faz certo um nível acima

Perseguindo por que certos secundários começam baixos (achado 25), a coluna que
saltou não foi a esperada:

```
pctR    min 4.1500   p10 4.1500   mediana 4.1500   p90 4.1500   max 4.1500
```

**Idêntico nos 62 transformadores da subestação**, de 30 a 112,5 kVA.
Resistência percentual real cai com o tamanho — valor único não é distribuição.

### Primeiro: o campo é dado em uma base e preenchimento em duas

| base | registros na `EQTRMT` | valores distintos de `R` | mediana | varia com `POT_NOM`? |
|---|---:|---:|---:|---|
| Roraima | 27.700 | **16** | **4,150** | **não** — 4,15 de 2 a 20 kVA |
| Enel CE | 169.357 | **6** | 2,960 | quase não |
| **Enel SP** | 236.523 | **38** | **1,330** | **sim** — 1,95 · 1,56 · 1,23 · 1,19 conforme cresce |

Só a Enel SP tem `R` que se comporta como grandeza física. E **1,33% é o `%R`
total de placa de um transformador de distribuição** — perda em carga sobre a
potência nominal. Roraima usa 4,15 em tudo, **3,1× a mediana da Enel SP**.

Isso sozinho já explica parte do achado 25: os transformadores de Roraima estão
modelados com três vezes a resistência dos equivalentes da Enel SP, e a queda é
proporcional ao carregamento — que nos 25 piores é 42,5% contra 8,8% no resto.

### Segundo, e maior: o valor provavelmente está dobrado

```python
~ wdg=1 bus={b1}.1.2.3 conn=delta Kv={kvp:g} Kva={kva:.1f} %R={r:.3f}
~ wdg=2 bus={b2}.1.2.3.4 conn=wye Kv={kv2:.4f} Kva={kva:.1f} %R={r:.3f}
```

No OpenDSS, `Xhl` é a reatância **do par** de enrolamentos — e o conversor a
passa direto, correto. Mas `%R` é **por enrolamento**, e a resistência série
total do transformador é a **soma dos dois**. Escrever `r` nos dois dá `2r`.

### O argumento mais forte está dentro do próprio projeto

O caminho de **alta tensão**, no `subtransmissao.trafos`, escreve outra coisa:

```python
New Transformer.AT_{cod} phases=3 windings=2 Xhl={...}
~ %loadloss={carga:.3f} %noloadloss={per_fer:.3f}
```

`%loadloss` é a perda em carga **total**, exatamente a grandeza de placa. Ou
seja: **o mesmo código já trata o transformador de potência da forma correta, e
o de distribuição não.** Os dois leem campos análogos de tabelas análogas
(`EQTRAT` e `EQTRMT`).

### O efeito, medido

Metade do `%R` por enrolamento, na 5003525 de Roraima:

| | mediana na carga | mín | < 0,92 | < 0,80 |
|---|---:|---:|---:|---:|
| `%R` inteiro nos dois (hoje) | 0,9311 | 0,3019 | 2.972 | 557 |
| **`%R`/2 por enrolamento** | **0,9439** | 0,3259 | **2.284** | 431 |

**688 cargas saem de baixo de 0,92 — 23% delas.** A mediana sobe 0,0128 pu, que
é **dez vezes** o efeito do `K_NEUTRO` (0,0015) que o achado 25 refutou.

### O que falta, e é decisão de vocês

A favor da correção: `R` fica ao lado de `XHL`, que é grandeza do par; a única
base com dado real dá 1,33%, que é `%R` total típico (por enrolamento daria
2,66% total, alto demais); e o próprio projeto usa `%loadloss` no nível acima.

O que falta: **confirmação no dicionário de dados da BDGD (ANEEL) de que
`EQTRMT.R` é o percentual total.** A correção muda todo transformador de
distribuição de todas as bases, e o argumento acima é forte mas é inferência,
não citação.

**Correção escrita e testada no ramo `correcao-pctr`, fora da `main`**, com a
V11 no ar. Não entra sem a confirmação documental.

---

## Achado 26, confirmação documental — `EQTRMT.R` é a resistência TOTAL

O Módulo 10 do PRODIST, **Anexo I — Estrutura da Base de Dados Geográfica da
Distribuidora**, Revisão 2, página 98, define na mesma tabela:

| campo | descrição no Anexo I |
|---|---|
| `PER_FER` | Perda ferro (W) |
| `PER_TOT` | Perda total (W) |
| **`R`** | **Resistência percentual na base de potência do transformador (%)** |
| `XHL` | Reatância percentual do primário para o secundário (%) |

E a página 91, para o regulador, repete a construção em texto corrido: *"R: Deve
apresentar o valor da resistência percentual na base de potência do regulador.
XHL: ... reatância percentual do primário para o secundário..."*.

`R` é grandeza **do transformador**, na base de potência dele — mesma classe do
`XHL`, que é explicitamente primário‑para‑secundário. **Nenhum dos dois é por
enrolamento.**

### Confirmado também pelo dado, e não só pelo texto

Se `R` é a resistência total, ela é a perda no cobre em percentual. Juntando
`EQTRMT` a `UNTRMT` pela chave, na Enel SP (o `POT_NOM` da `EQTRMT` é código, e
o kVA real está na `UNTRMT`):

| código | n | kVA real | `R` % | cobre (`PER_TOT − PER_FER`) | cobre % | **R / cobre** |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 19.264 | 10,0 | 1,95 | 200 W | 2,00 | **0,975** |
| 16 | 10.397 | 75,0 | 1,47 | 1.140 W | 1,52 | **0,967** |
| 24 | 7.535 | 150,0 | 1,23 | 1.910 W | 1,27 | **0,966** |
| 20 | 5.704 | 112,5 | 1,33 | 1.550 W | 1,38 | **0,965** |
| 30 | 5.305 | 225,0 | 1,16 | 2.700 W | 1,20 | **0,967** |

Os grupos que destoam (códigos 7, 14, 19) têm kVA mediano de 62,5 e 60,0 —
valores não padronizados, porque o próprio Módulo 10 define `UNTRMT.POT_NOM`
como *"a soma entre a parcela regulada e a parcela direta"*: são bancos, e a
razão por unidade não se aplica.

**A trava documental do achado 26 está removida.** O ramo `correcao-pctr` pode
ser fundido assim que a V11 fechar.

---

## Achado 27 — o que a BDGD tem e o conversor não lê

Censo das camadas da BDGD da Enel SP contra o que o código referencia:
**43 camadas, 26 usadas, 17 não.** As que têm conteúdo elétrico:

| camada | registros | o que é | por que importa |
|---|---:|---|---|
| **`UNSEBT`** | **119.109** | chaves de baixa tensão | **372 normalmente ABERTAS**, e nenhuma é modelada |
| **`PIP`** | **466.117** | iluminação pública | **40 GWh/mês de carga**, com `PAC` e `CTMT` |
| `EQSE` | 316.298 | equipamento seccionador | tem `COR_NOM` — a ampacidade que falta ao achado 21 |
| `EQTRM` | 55.474 | — | não investigado |
| `EQCR` | 1.789 | equipamento de compensação reativa | ratings dos capacitores |
| `EQRE` | 226 | equipamento regulador | ratings dos reguladores |
| `CONJ` | 143 | conjunto elétrico | é a unidade em que a ANEEL agrupa para o PRODIST |

`EQME` (8,8 M medidores) e `PONNOT` (1,4 M pontos notáveis) não têm efeito
elétrico e a ausência é correta.

### O que isso custa hoje, medido

**As chaves de BT.** No modo `--bt completo` o modelo não tem nenhuma das
119.109, e **372 estão normalmente abertas**. Uma chave aberta que o modelo
fecha junta trechos que na rede real estão separados — e é candidato direto às
componentes órfãs do achado 25, que ficaram sem explicação do lado do conversor.

**A iluminação pública, e esta toca o resultado principal.** O
`valida_balanco` soma o faturado varrendo `UCBT_tab` e `UCMT_tab`:

```python
for tab in ('UCBT_tab', 'UCMT_tab'):
```

Na Enel SP:

| tabela | energia | registros | entra no faturado? |
|---|---:|---:|---|
| `UCBT_tab` | 2.104.148.338 kWh/mês | 8.258.035 | sim |
| `UCMT_tab` | 1.095.144.148 kWh/mês | 15.892 | sim |
| `UCAT_tab` | 394.431.233 kWh/mês | 186 | **não** |
| **`PIP`** | **40.064.351 kWh/mês** | **466.117** | **não** |

A `UCAT_tab` **não tem coluna `CTMT`** — aqueles 186 consumidores de alta
tensão não estão a jusante de alimentador nenhum, então a energia deles também
não está na injetada, e excluí‑los está **certo**.

A `PIP` é o oposto: **os 466.117 pontos têm `CTMT` válido, todos.** Eles
consomem de alimentadores cuja energia injetada É contada, e o consumo deles
não entra no faturado. **É um viés de mão única que infla a perda medida em
~1,25%.**

Não explica os 9,92× da Enel SP — mas é um erro sistemático de sinal conhecido
no número que é o resultado do trabalho, e é o tipo de coisa que um revisor
encontra.

### Correção do achado 27, no mesmo dia em que ele foi escrito

Escrevi acima que a `UNSEBT` ausente é "candidato direto" às componentes órfãs
do achado 25. Isso foi **afirmado, não medido**. Medindo:

**A `UNSEBT` da 5003525 de Roraima tem zero chaves.** Nenhuma toca as 20 barras
órfãs, porque não há nenhuma para tocar. O teste não refuta a hipótese — ele é
**inconclusivo nessa base**, e a redação original dava a entender outra coisa.

E o censo nas sete mostra por quê:

| base | `UNSEBT` | `PIP` | `EQSE` |
|---|---:|---:|---:|
| Roraima | **0** | 60.311 | 24.541 |
| Enel CE | **0** | 439.142 | 210.166 |
| Equatorial PA | **0** | 590.463 | 343.877 |
| Enel SP | 119.109 | 466.117 | 316.298 |
| Light | 26.330 | 468.881 | 186.087 |
| CPFL | 3.605 | 1.388.652 | 518.011 |
| Cemig-D | 9.612 | 2.373.663 | 1.427.728 |

Três leituras, e elas reordenam o trabalho:

**A `UNSEBT` está vazia em 3 das 7.** Não é tabela que se possa assumir: modelar
chave de BT beneficia quatro distribuidoras e não faz nada pelas outras três.
Isso a tira da frente da fila — e mantém de pé a conclusão do achado 25, de que
as componentes órfãs de Roraima são limitação da base, sem elo faltando do lado
do conversor.

**A `PIP` existe nas sete**, somando **5,8 milhões de pontos**. É a lacuna
universal, e é a que toca o resultado do trabalho pelo viés de 1,25% no
faturado. **É ela que deve vir primeiro.**

**A `EQSE` existe nas sete**, somando 3,0 milhões de registros com `COR_NOM` —
a ampacidade que falta ao achado 21.

A hipótese da chave de BT continua **aberta e não testada**, e para testá-la é
preciso rodar `--bt completo` numa subestação da Enel SP, da Light, da CPFL ou
da Cemig-D. Fica dito assim, e não como suspeita que virou fato por repetição.

---

## Achado 28 — quatro chaves que não tocam a rede tiram 72 subestações da medição

A Cemig-D fechou o ciclo pela primeira vez na V11 e trouxe números que
destoavam de tudo: **341/413 sadias**, **cobertura 23,9%**, **razão 0,46×**.

### Quatro hipóteses minhas, e as quatro caíram

| hipótese | teste | resultado |
|---|---|---|
| o veredicto NaN é severo demais | mediana de 2 nós NaN em 42.556 | **verdadeiro, mas não é a causa da cobertura** |
| as zonas de medidor são canibalizadas | PACs da `SSDMT` por alimentador | **refutada** — 0 nós em comum entre pares |
| os alimentadores são tocos | censo de porte | **parcial** — 16,1% abaixo de 50 trechos, não 76% |
| falta transformador ou UC | contagem por alimentador | **refutada** — só 2,6% sem trafo |
| o PAC do trafo não casa com a rede | junção `UNTRMT` × `SSDMT` | **refutada** — 99,9% casam |

Registro isso porque cheguei a escrever "zonas canibalizadas" como fato antes
de medir. Não era.

### O que era

O `nan_exemplo` do `verifica` tinha a resposta desde o começo, na mesma forma
nas 72:

```
node_2553646456  PCE=[]  PDE=['Line.2294073839']

Line.2294073839  len=0.001  Switch=Y  C1=1.1  R1=0.0001  phases=1
   barras=['node_2553646456.1', 'node_2553646457.1']
SwtControl.sw_2294073839
```

**Uma chave cujas duas barras existem só por causa dela.** É uma ilha de dois
nós, sem fonte e sem caminho para a terra: a matriz de admitância daquele
pedaço fica singular e a tensão sai NaN. Foram **2 elementos NaN em 25.326**.

E o estrago não é local. `Circuit.Losses()` soma tudo, então **a perda da
subestação inteira vira NaN**, o `energia` perde os 96 passos do dia e a
subestação sai da medição. `P_kW` continuava correto — 1.048,1 kW — e só
`perdas_kW` era NaN, nos dois motores, nas 72.

### A correção, e o que ela não muda

`chaves.gerar` passa a receber as barras que a rede de MT criou e **omite a
chave cujos DOIS PACs estão fora dela** — a que não liga nada. Uma ponta fora
continua valendo: ali a chave energiza um trecho e o dado é legítimo.

Medido na subestação `1323264954`:

| | antes | depois |
|---|---:|---:|
| nós NaN | 2 | **0** |
| perdas | **NaN** | **14,3 kW** |
| potência da fonte | 1.048,1 kW | **1.048,1 kW** |
| barras | 15.432 | 15.428 |

**A potência é idêntica.** Nada elétrico foi removido — só quatro barras que
não conduziam nada e envenenavam o agregado. E a omissão fica escrita no
próprio `Chaves.dss`, com os códigos.

### O veredicto do `verifica`, que também mudou

A regra "convergir com NaN não é convergir" nasceu do caso da DALP: 49.857 nós
NaN propagados, `TotalPower` inteira NaN. Ali reprovar é o certo. Reprovar uma
subestação de 42.556 nós por dois nós de ponta solta é o outro extremo.

O critério passa a ser proporcional ao que o NaN atinge: NaN em barra **com**
carga ou geração reprova; NaN que não chega a agregado nenhum não reprova, mas
**aparece** — o veredicto vira `OK_PONTA_SOLTA[n]` em vez de `OK`. Silenciar
seria trocar um extremo pelo outro.

### O que continua aberto

Corrigidas as 72, a cobertura da Cemig-D deve subir — **mas não se sabe para
quanto**. Restam 1.219 alimentadores (59%) com rede e zero energia no medidor,
e as hipóteses acima não os explicam. **Fica aberto, e com quatro caminhos já
eliminados.**

---

## Achado 29 — a coluna que não volta, e a Cemig-D como caça-suposições

Terceira tentativa de converter a Cemig-D, terceira falha, cada uma mais
funda que a anterior:

| tentativa | caiu em | causa |
|---|---|---|
| V10 | subestação **265** de 413, após 5h57 | `pertence` com `dtype` de objeto (achado 26 do `leitor`) |
| V11 | subestação **278**, após 4h26 | `glob` com `AssertionError` no corte do `LineCodes` |
| V12 | subestação **348**, após 4h36 | `KeyError: 'UNI_TR_MT'` |

Nenhuma das três aparece nas outras seis distribuidoras. **A Cemig-D é a maior
das sete e a única que exercita essas suposições até quebrá-las** — 413
subestações, 2.456 alimentadores, 12 milhões de registros de UCBT. Cada
correção revela a próxima, e isso é o que se espera de uma base que nunca
tinha sido convertida até o fim.

### A terceira

```
File ".../complementos.py", line 476, in geracao
    s = sec.get(txt(col['UNI_TR_MT'][i]))
KeyError: 'UNI_TR_MT'
```

O `leitor.ler` monta o dicionário a partir do que o `pyogrio` devolveu:

```python
cs = list(meta['fields'])
return {c: data[cs.index(c)] for c in cs}
```

Coluna que não volta **some do dicionário sem ruído**, e o erro aparece muito
depois, em quem consome.

### Não foi reproduzido, e a correção assume isso

`UNI_TR_MT` existe em `UGBT_tab` nas **sete** bases. A mesma leitura, refeita
depois — direta e com o lote aberto, nas dez subestações do mesmo grupo —
devolve as oito colunas, sempre. Não consegui forçar a falha.

Por isso a correção não é no ponto: é no **contrato**. Quem pede N colunas
recebe N colunas. Coluna que não volta passa a ser preenchida vazia e **dita
no log**, e quem consome decide o que fazer com o vazio — no caso da geração,
contar como "sem rede", que é o balde que já existia para isso.

Vale para os dois caminhos: a leitura direta e a servida pelo cache do lote,
que era o que estava em uso quando caiu.

### E um teste que só passava por carona

`test_leitor_fixture.py` importava `fixture` sem pôr a própria pasta no
`sys.path` — funcionava porque outro teste da suíte inseria o caminho antes.
Rodado sozinho, quebrava. Corrigido junto: módulo de teste que só passa em
companhia não é teste.

---

## Achado 30 — o inversor de 127 V na barra de 7,97 kV

Fechado o achado 28, a Cemig-D V12 passou de 341 subestações medidas para
**412 de 413**. A que sobrou tinha **6 nós NaN em 31.834**, nas duas mesmas
barras, com os dois motores concordando nó a nó — sinal de defeito de modelo,
não de solver.

### O que está escrito no modelo

```
New Transformer.484736801_484736800 phases=1 windings=3
~ wdg=1 bus=node_754880953.3 conn=wye Kv=7.9674 Kva=15.0     <- MT
~ wdg=2 bus=node_457463634.1.4 conn=wye Kv=0.1200            <- BT
New Line.244637127 Bus1=node_754880953.3 Bus2=node_429598913.3
New PVSystem.GD_acab...891_1 bus1=node_754880953.1.4 kv=0.1270   <- BT!
```

`node_754880953` é barra de **média**: primário do transformador e ponta de
uma linha, e só a fase C existe nela. O inversor de 127 V foi escrito nos nós
**1, 2 e 4** dessa barra — três nós que nascem do próprio PVSystem e que
ninguém mais toca. Um PVSystem nessa condição é uma fonte de corrente solta,
sem caminho para a fonte: a solução devolve NaN.

Censo na subestação: **4 unidades em 2 barras**, de 2.377 PVSystems. Dois nós
por barra mais o neutro — exatamente os 6 nós NaN medidos.

### A condição que deixava passar

```python
s = sec.get(pac)
if s is None and barras is not None and pac not in barras:
    ...  # plano B: UNI_TR_MT
```

`barras` é a rede **inteira**, a de MT inclusive. Um PAC de UGBT que casasse
com uma barra de MT satisfazia `pac in barras`, e isso contava como "já está
na rede": o plano B do `UNI_TR_MT` era desligado e o inversor escrito ali
mesmo, com `kv = 0.127` de padrão.

Pertencer à BT tem de ser verificado **contra a BT** — `sec`, que são os
secundários de transformador, ou `barras_bt`, que só existe com `--bt`
completo. O `converter` passou a entregar as duas coisas separadas em vez de
um saco único de barras.

Sem plano B a unidade é descartada e **contada** em `sem_rede`, que é o balde
que já existe. Perder uma unidade de 0,8 kW é preferível a envenenar a perda
da subestação inteira: `Circuit.Losses()` soma tudo, e um NaN em 6 nós de
31.834 tirava a subestação da medição — o mesmo estrago do achado 28, por
outra porta.

### Por que só apareceu agora

O defeito exige que o PAC de uma UGBT case com uma barra de MT do mesmo
alimentador. É raro: 4 ocorrências em 413 subestações da maior das sete bases.
As outras seis passaram por sorte de dado, como no achado do `pertence`.

### Estado

Retido no ramo `correcao-gd-bt-na-mt`, com 7 testes novos em
`testes/test_geracao.py`. Cinco deles falham na condição antiga e dois passam
— os dois que verificam que o caminho normal não foi estreitado junto. Suíte
em 230 testes, verde.

---

## Achado 31 — a subestação sem vão não tem medidor, e some da medição

Diagnóstico apenas. **A correção não foi implementada nem provada.**

O `energia` da Cemig-D V12 fechou em 411 de 413. A que não rodou não falhou
por convergência:

```
1726751   ERRO: (#8989) No active EnergyMeter object found!
```

O EnergyMeter é escrito no vão de saída — `element=Line.VAO_<ctmt>` — porque é
o único ponto por onde toda a energia do alimentador passa. Sem vão não há
medidor; sem medidor a subestação inteira sai da medição. São **7.803 cargas,
25.974 barras e 1.782 km de MT** que existem no modelo, compilam e resolvem,
mas não entram em nenhum número de perda.

### Por que não houve vão

`relatorio_rede.json` diz `sem_vao: 6` — e cinco dos seis são de 1726751:

| alimentador | SUB | BARR | UNI_TR_AT |
|---|---|---|---|
| FMA03…FMA07 | 1726751 | `' '` | `'0'` |
| IUMD34 | 1726790 | `' '` | `'192244623'` (não existe na UNTRAT) |

A ordem de preferência do `vaos()` é BARR-que-é-secundário → trafo do
`UNI_TR_AT` → BARR mesmo sem trafo → nada. Com `BARR` preenchida com **um
espaço** e `UNI_TR_AT` valendo `'0'`, os quatro caminhos morrem e o
alimentador cai no quarto.

O dado para resolver existe: a **UNTRAT tem 2 transformadores de AT na SUB
1726751**. Ninguém os alcança porque o único elo que o `vaos()` conhece é o
`UNI_TR_AT` do CTMT, que aqui não aponta para lugar nenhum. Falta uma quarta
preferência — a barra de um transformador de AT da **própria SUB**.

Na base inteira: 487 CTMTs de 2.456 têm `BARR` em branco e 279 têm
`UNI_TR_AT` que não existe na UNTRAT. Que só 6 tenham terminado sem vão diz
que os caminhos existentes já cobrem quase tudo; o que falta é o último.

### O que ainda não se sabe

Se a quarta preferência resolve as seis ou só as cinco — a IUMD34 está numa
SUB que já tem vãos para os outros alimentadores, e o caso dela pode ser
outro. Medir antes de afirmar.
