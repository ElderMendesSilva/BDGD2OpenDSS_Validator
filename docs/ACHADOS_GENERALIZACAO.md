# Achados de generalização — síntese

**Corte:** 01/09/2026. Este arquivo conserva **conclusões, evidências e
números**; hipóteses intermediárias e o detalhe de cada rodada ficam no Git.

Dezessete achados, medidos sobre 97 distribuidoras e 4.201 subestações. Onde
uma conclusão minha caiu no teste seguinte, a correção está **dentro do próprio
achado**, com o número velho visível — quatro delas caíram, e isso é parte do
resultado.

## O que o projeto demonstrou

- A BDGD padroniza o **formato**, não a qualidade nem a semântica local do
  preenchimento. O conversor precisa inferir e auditar por concessão.
- Validar compilação, convergência ou ausência de `NaN` **não basta**: redes
  fisicamente implausíveis convergem. A validação inclui tensão, ampacidade,
  cobertura e balanço de energia (achado 1).
- **Cerca de 7% da rede modelada do país não recebe tensão** (achado 23,
  medido sobre 4.237 subestações). O valor de 25,70% que este documento
  publicou era artefato de medição, e a história de como ele caiu está nos
  achados 21 e 23 — vale ler, porque quatro achados se apoiaram nele.
- **A perda declarada pela distribuidora não serve de árbitro.** Ela tem casos
  fisicamente impossíveis (achado 8), um quinto das bases repete um valor
  padrão (achado 9) e em 40 de 81 bases ela é menor que o ferro dos próprios
  transformadores declarados (achado 13).
- A comparação agregada é frágil quando poucos alimentadores implausíveis
  dominam a perda. Publicar sempre agregado, mediana, corte de sensibilidade e
  parcela contaminada.

## Correções incorporadas

| Tema | Regra consolidada |
|---|---|
| Tensões | Usar `PAC_INI`, `TEN_OPE` e conciliar a tensão declarada com o parque de equipamentos; códigos desconhecidos são relatados, nunca mascarados. |
| AT e fontes | A malha de AT, fontes e barras são modeladas por topologia e nível de tensão; evitar uma fonte fixa de 88 kV e nomes de pátio tratados como barra. |
| Transformadores | Respeitar fases reais dos enrolamentos; um primário bifásico não pode ser escrito como trifásico. |
| Chaves e reguladores | Emitir elementos conectados à rede, preservar o estado aberto e manter reguladores entre chaves no modelo. |
| Nomes de elemento | O nome leva a camada: `COD_ID` é único DENTRO da tabela, não entre tabelas (achado 4). |
| Safras na mesma pasta | A tag ganha a data-base só quando duas safras da mesma distribuidora colidem — `RR_2024` e `RR_2025`. Recusar a rodada, como se fazia antes, transferia ao usuário um trabalho que o código sabe fazer (DESAMBIGUADA em 02/09/2026). |
| Leitura e escala | Ler tabelas grandes por fatias/lotes, tratar `dtype` heterogêneo e rejeitar comprimentos nulos antes de gerar DSS. |
| Execução | Ordenar subestações maiores primeiro, retomar etapas concluídas e manter a saída determinística entre laptop e cluster. |

## Limitações e fatos de dado relevantes

- **`--bt completo`:** deixou de ser "não roda nas grandes" e passou a ser
  **delimitável** — com a ressalva do achado 19, que mostra a métrica sensível
  ao critério de agrupamento das subestações. O critério de entrada é medido
  antes de simular — componentes por subestação na BDGD ≤ 3 —, e por ele a
  Enel SP tem 150 de 155 subestações elegíveis e a Cemig 163 de 412 (achados
  16 e 17). Falta provar que as elegíveis rodam de fato: escala é outra
  coisa. Até lá, não usar seus números como resultado de produção.
- **Enel SP:** o condutor 593 e, em geral, a incoerência entre condutor e uso
  explicam grande parte da perda impossível. É problema de cadastro, a marcar
  e não esconder no agregado.
- **Cemig-D:** o desvio agregado segue sem explicação completa e não deve ser
  atribuído ao conversor sem evidência. A base é **bimodal** em fragmentação
  (achado 17), o que é parte da resposta, não toda ela.
- **CPFL e Equatorial:** códigos de tensão e níveis misturados podem criar
  alimentadores com tensão incorreta. Corrigir exige evidência do cadastro, não
  substituição por um padrão.
- **Premissa de ligação:** pode energizar uma componente, mas só é aceitável se
  não introduzir perda, corrente ou tensão implausíveis.

## Achados de 28–29/08/2026

Cinco medidos nesta janela. Ficavam só em mensagem de commit e no diário — o
que os deixava fora do documento que alimenta o artigo.

### 1. Convergir não atesta plausibilidade física — agora medido

O princípio já estava declarado acima; faltava o número. Na V23, **71
subestações da COPELDIS2866 saíam `OK`** — convergidas, sem NaN, sem chave
ilhada — publicando perda modelada de até **10.309.528%**. O que as separava
das outras 103 **da mesma base** era tensão: mediana do `V_MT_min` em **0,082
pu contra 0,938**. Generaliza: **0,254 contra 0,906** nas 4.189 subestações das
97 bases.

A física fecha sozinha: carga de potência constante a 0,08 pu puxa ~12x a
corrente nominal, e a perda joule sobe ~150x. Não é cadastro nem condutor.

Virou o veredicto `TENSAO_IMPLAUSIVEL`. **Ressalva:** o corte de 0,5 pu foi
calibrado no histograma do MÍNIMO, que é bimodal com vale em 0,45–0,55; o
veredicto aplica sobre a MEDIANA, cuja distribuição não tem vale. Hoje o corte
se defende pela física, não pelos dados — falta estudo de sensibilidade antes
de virar número de artigo.

### 2. `m/trafo` NÃO prevê a viabilidade do `--bt completo` — hipótese refutada

A hipótese de 26/08 (Roraima 270 funciona, Enel CE 812 e Light 888 falham) não
sobreviveu. Medidas as 97: a mediana é 414 m, **12 bases passam de 800**, e a
Light vira a 5ª. Testadas 10 bases de 32 a 955 m/trafo, **nove das nove
modeláveis passaram com todas as subestações `OK`** e perdas de 3,4% a 9,3%.

A **MUX_ENERGI401** decide: 835 m/trafo com 17,1 m/UC é a assinatura exata da
Light — secundário longo em rede densa — e rodou com 4,85% de perda e duas
cargas sem tensão, contra 92% de cargas mortas da Light. Não há gradiente na
faixa.

### 3. O modo completo falha por FRAGMENTAÇÃO — corrigido em 30/08

A primeira leitura, com médias por base, atribuía a falha à escala. **A BT3
completa desmente isso.** As mesmas 370 subestações, nas duas rodadas:

| | agregado | completo |
|---|---:|---:|
| convergem | **99%** (366/370) | **62%** (231/370) |
| ramos isolados (mediana) | 43,5 | 210,5 |
| cargas sem tensão (mediana) | 0 | 27 |

Mesma rede de MT, mesmos trafos, mesmos km — a única diferença é a BT entrar.

E dentro do modo completo, o que separa quem converge de quem não converge
**não é tamanho**:

| | converge | falha | razão |
|---|---:|---:|---:|
| ramos isolados | 31 | 3.588 | **116x** |
| cargas sem tensão | 2 | 346 | **173x** |
| iterações | 4 | 500 | **125x** |
| trafos | 684 | 1.073 | 1,6x |
| km de MT | 195 | 450 | 2,3x |

Tamanho aparece com 1,6–2,3x; fragmentação com 116x. As 500 iterações são o
TETO do OpenDSS: elas não convergem devagar, batem no limite.

**Isso reconecta ao defeito conhecido da Light**, descrito em 26/08 como
fragmentação por recorte de CTMT — mesmo mecanismo, agora medido em 370
subestações de cinco distribuidoras. A NEOENERGIA40 é o extremo: 13% de
subestações OK e perda modelada em 10^300 — estouro numérico.

**Consequência prática:** subir o teto de iterações não resolve. Rede com 3.588
ramos isolados não converge com 500 nem com 5.000. E a fragmentação **já existe
na MT** (43 ramos isolados no agregado) e a BT a multiplica por cinco — então a
origem é anterior à baixa tensão.

### 3b. Leitura anterior, mantida como registro do erro

Nas bases de 1–2 milhões de UCs os modelos **compilam** mas **não convergem**,
de 6% a 43% das subestações — contra 0% nas bases pequenas. É defeito distinto
do da Light (cargas mortas) e do da Enel CE (perda excessiva).

E não segue nem `m/trafo` nem qualidade de dado: a única base da amostra com
dado bom pelo diagnóstico tem a **pior** taxa (57%). A hipótese em aberto é que
a unidade que importa é a **subestação**, não a base — o OpenDSS resolve uma
por vez.

### 4. `COD_ID` é único dentro da tabela, não entre tabelas

SSDMT, SSDBT e RAMLIG numeram cada uma do seu próprio espaço, e o mesmo `662`
existe nas três. No modo completo isso gerava `Duplicate new element
definition: "Line.662"` e **derrubava o modelo inteiro**. O modo agregado não
emite BT, então a colisão nunca aparecia.

Custou um experimento completo: as dez bases da BT1 saíram `NAO_COMPILA` e o
resultado media o nome do elemento, não a rede.

### 5. O clima medido cobria uma base de 97

O conversor já recusava aplicar clima de outra distribuidora (achado 4) e caía
no perfil sintético — comportamento correto, e ~23% otimista. Mas **96 das 97
bases rodavam assim**, e isso era invisível no resultado: `clima_fonte` só
existia no resumo do modelo. Enquanto durou, nenhuma conclusão sobre geração
distribuída se sustentava.

Resolvido: NASA POWER na coordenada de cada base, 97 de 97. A faixa nacional vai
de **4,37 a 6,81 kWh/m²/dia** — variação de 56% entre a base menos e a mais
ensolarada. Usar São Paulo para todas nunca foi aproximação inofensiva.

### 6. As violações não são "erro absurdo": são excesso MODERADO e sistemático

Investigado em 30/08 sobre a V24. **1.623 das 1.626 violações** têm cobertura
acima de 100% — a perda técnica que o modelo calcula excede a perda TOTAL que a
medição registra. Como a técnica é uma parcela da total, isso é impossível por
definição, e vale para 47 das 97 bases.

O que surpreende é a magnitude. Os 366 casos rotulados **"a investigar"** — os
que não têm causa conhecida — não são disparates:

| | mediana | faixa |
|---|---:|---|
| perda técnica modelada | 8,66% | 3,7% a 15,0% |
| perda total medida | 4,72% | 3,0% a 11,8% |
| razão modelo/medido | **1,56x** | 1,2x a 4,6x |
| não-técnica implícita | −3,03% | **negativa em todos** |

São perdas **plausíveis** que excedem a medição por um fator moderado e
constante. Não é ruído nem caso extremo: é viés.

**Duas leituras, e o dado não decide entre elas.** Ou o modelo superestima a
perda nesses alimentadores, ou a medição os subestima. A favor da segunda: a
mediana da técnica modelada nas violações (8,11%) fica perto da referência
nacional da ANEEL (7,4%), enquanto a total medida (5,20%) fica ABAIXO dela — e
total abaixo de técnica nacional é, de novo, impossível.

**O que já se descartou por medição:**

- **Fragmentação não explica.** Ramos isolados por km: 0,24 nas subestações sem
  violação, 0,26 nas com violação, 0,17 nas sem causa. A diferença bruta
  (71 contra 197) era efeito de tamanho e some ao normalizar.
- **Não é o mesmo defeito da BT.** As violações são do modo agregado, onde 99%
  das subestações convergem.

**RESPONDIDO em 30/08 — ver o achado 7.**

### 7. Os alimentadores "sem causa" são LONGOS, finos e pouco carregados

O `perfil_violacao.py` na Cemig-D comparou os **143 alimentadores suspeitos**
contra os **2.260 restantes da mesma base**, em atributos da própria BDGD:

| | suspeitos | resto | razão |
|---|---:|---:|---:|
| **km de MT** | **349,2** | **33,8** | **10,3x** |
| trafos | 637 | 196 | 3,3x |
| **R1 ponderado** (Ω/km) | **1,31** | **0,85** | **1,5x** |
| CNOM ponderado | 176 | 217 | 0,8x |
| **kVA por km** | **41,9** | **86,2** | **0,5x** |

O produto `R1 x km`, que é o que governa a perda joule, é **15,8x maior** nos
suspeitos: alimentadores **longos, de condutor mais fino e com metade da
densidade de carga** — rurais e extensos.

**Eu concluí daqui que o modelo estava certo e a medição errada. CORRIJO
ABAIXO — a conclusão não sobreviveu ao teste seguinte.**

### 7b. A correção: existe uma TERCEIRA declaração, e ela não nos favorece

A BDGD traz `PERD_*`, a perda técnica que a **própria distribuidora declara por
alimentador**. Nos 68 casos sem causa que a têm:

| origem | perda |
|---|---:|
| nosso modelo | **9,50%** |
| declarada pela distribuidora (`PERD_*`) | **3,41%** |
| total medida (`ENE_01`) | **5,26%** |

**As duas declarações dela são consistentes entre si** — técnica 3,41% abaixo da
total 5,26%, como manda a definição. **Quem destoa é o nosso modelo**, em 2,7x.

E o erro **não cresce com o comprimento**, o que descarta a explicação mais
óbvia (carga concentrada na ponta em vez de distribuída). Por quartil de km:
4,24x, 2,70x, 2,42x, 3,38x. O modelo roda alto em toda a faixa, não só nas
longas. Na Cemig inteira a razão modelo/declarado é 1,44x; nas violações, ~3x.

**O que continua de pé:** o perfil dos suspeitos — longos, de condutor fino e
pouco carregados — replicado em 6 de 6 bases. Isso é medida, não interpretação.

**O que caiu:** a afirmação de que o modelo está certo. Com três números e
nenhuma verdade de campo, não há como decidir por evidência interna.

**O que fica em aberto, e é a próxima investigação real:**

1. Nosso modelo superestima a perda — e aí a causa está na alocação de carga ou
   na impedância que atribuímos, e é bug nosso.
2. As duas declarações da distribuidora subestimam **juntas** — o que é
   possível sem conluio: se ela calcula `PERD_*` com as mesmas premissas
   otimistas com que faz o balanço, a consistência entre elas não prova nada.

**Consistência mútua não é corroboração quando as duas saem da mesma fonte e do
mesmo método.** É por isso que a validação externa por distribuidora, já listada
como pendência, deixa de ser desejável e passa a ser necessária.

### O padrão é NACIONAL: replicou em 6 de 6 bases, nos três atributos

Repetido em 30/08 nas seis bases que concentram 60% dos 366 casos sem causa.
Cada uma comparada contra **ela mesma**:

| base | n | km susp. | km resto | razão | R1 susp. | R1 resto | kVA/km susp. | resto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CEEE_EQUAT5707 | 131 | 40 | 17 | 2,4x | 1,00 | 0,50 | 333 | 555 |
| CMIG | 143 | 349 | 34 | 10,3x | 1,31 | 0,85 | 42 | 86 |
| COPELDIS2866 | 259 | 197 | 19 | 10,4x | 2,69 | 0,74 | 95 | 408 |
| EQUATORIAL6072 | 168 | 307 | 29 | 10,6x | 1,45 | 0,89 | 49 | 122 |
| NEOENERGIA43 | 62 | 270 | 24 | 11,3x | 1,47 | 1,00 | 37 | 301 |
| NEOENERGIA47 | 88 | 281 | 37 | 7,5x | 1,40 | 1,12 | 37 | 126 |

**Seis de seis** em cada um dos três atributos: suspeitos mais longos, com
resistência por km maior, e com densidade de carga menor. **Sem exceção.**

Seis distribuidoras independentes, em regiões diferentes, com práticas de
cadastro diferentes, produzindo o mesmo perfil. A COPELDIS2866 é o extremo de
resistência (2,69 contra 0,74 Ω/km, 3,6x) e a CEEE a mais branda (2,4x em km),
mas o sinal é o mesmo em todas.

Isso torna o achado 7 **nacional, não anedótico** — e é o resultado mais forte
do projeto até aqui, porque não depende de escolher uma base nem de acreditar
no modelo: os dois lados da contradição vêm da própria BDGD.

### 8. O `PERD_*` declarado tem casos fisicamente impossíveis

Investigado em 30/08, como consequência da correção do achado 7. Se a
declaração da distribuidora vai ser usada como referência, ela precisa passar
no mesmo escrutínio que aplicamos ao modelo.

Nas **81 bases** que declaram `PERD_*` agregado:

| declaram perda técnica | bases |
|---|---:|
| abaixo de 0,5% | **7** |
| abaixo de 1% | **10** |
| abaixo de 2% | **21** |

| base | declara | nosso modelo |
|---|---:|---:|
| CERIPA5378 | **0,13%** | 5,37% |
| EQUATORIAL38 | 0,29% | 3,88% |
| EQUATORIAL6072 | 0,29% | 13,15% |
| CEA_EQUATO31 | 0,30% | 3,07% |
| EQUATORIAL44 | 0,31% | 26,13% |

**Uma rede de média tensão com 0,13% de perda técnica não existe.** É uma
ordem de grandeza abaixo de qualquer alimentador real, e a referência nacional
da ANEEL é 7,4%. Não depende de acreditar no nosso modelo: é implausível
contra a física e contra a própria referência do regulador.

**Consequência para a leitura do achado 7b.** A razão modelo/declarado nacional
tem mediana de 1,59x (73 de 81 bases com o modelo acima), mas os extremos —
43x, 45x, 84x — são puxados por declarações perto de zero, não por explosão do
modelo. São dois fenômenos distintos que a razão sozinha confunde:

- um **viés moderado e amplo** do nosso modelo, de ~1,6x, que continua sem
  explicação e é problema nosso;
- um **conjunto de declarações impossíveis**, em ~10 bases, que é achado de
  auditoria independente do modelo.

E há 8 bases onde o nosso modelo fica ABAIXO do declarado (0,74x a 0,89x), o
que impede tratar o viés como constante universal.

### 9. O `PERD_*` de um quinto das bases é um valor PADRÃO, não uma medição

Investigado em 30/08, seguindo a pista das 8 bases onde o nosso modelo fica
abaixo do declarado: cinco delas declaravam **exatamente 3,89%**.

Nas 81 bases com `PERD_*` agregado há apenas **60 valores distintos**, e:

| valor declarado | bases |
|---|---:|
| **3,89%** | **16** |
| 0,34% | 2 |
| 3,72% | 2 |
| 1,42% | 2 |
| 0,29% | 2 |

**28 das 81 bases (35%) declaram um valor que se repete em outra**, e 16
declaram o mesmo 3,89%. Distribuidoras distintas, em estados distintos, com
redes de porte distinto, não medem a mesma perda técnica com duas casas
decimais. **É um valor padrão.**

E o perfil delas confirma: as 16 têm **433 km de MT medianos contra 10.471** das
demais, e **4 subestações contra 20**. São as pequenas — cooperativas e
permissionárias, que provavelmente preenchem o campo com uma referência
regulatória em vez de um cálculo próprio.

**Isso derruba o argumento central do achado 7b.** Eu havia escrito que "as duas
declarações da distribuidora são consistentes entre si, logo quem destoa é o
nosso modelo". Se o `PERD_*` é uma constante preenchida por padrão, ela não
corrobora coisa nenhuma — concordar com ela ou não é irrelevante.

**O que isso NÃO faz:** não absolve o modelo. O viés de ~1,6x continua, e nas 65
bases que declaram valor próprio a comparação segue valendo. O que muda é que
**o `PERD_*` não serve como árbitro universal** — precisa ser filtrado por
plausibilidade (achado 8) e por originalidade (este) antes de virar referência.

### 10. O viés de ~1,4x sobrevive aos filtros, e a suspeita é o FERRO

Aplicados os filtros dos achados 8 e 9 à comparação nacional:

| filtro | bases | razão modelo/declarado |
|---|---:|---:|
| todas | 81 | 1,59x |
| só declaração original | 53 | 1,50x |
| só declaração plausível (≥ 2%) | 60 | 1,43x |
| **original E plausível** | **38** | **1,42x** |
| ... e sem os alimentadores implausíveis do nosso lado | 38 | **1,33x** |

**O viés é real.** Não era artefato de declaração padrão nem de valor absurdo:
em 35 das 38 bases filtradas o modelo fica acima, com mediana de 4,57% contra
3,15%.

**A suspeita principal é a perda de ferro dos transformadores**, e ela explica
as três observações de uma vez:

- **É constante e independente do comprimento** — depende do número de
  transformadores, não de quilômetros. Casa com a razão não crescer com o km
  (4,24x / 2,70x / 2,42x / 3,38x por quartil).
- **A magnitude bate.** O achado 53 mediu o ferro em 1,45% a 3,60% da carga
  viva — na Cemig, 3,60%, que é da ordem de TODO o modelo dela (4,63%).
- **Cresce onde a carga é baixa.** Ferro constante sobre carga menor dá
  percentual maior — e os alimentadores suspeitos do achado 7 têm METADE da
  densidade de carga do resto da base.

**Mas o teste que fiz não confirma.** Ordenando as 38 bases filtradas por kW
nominal por transformador, a razão vai de 1,44x (menos carga por trafo) a 1,30x
(mais carga) — direção certa, magnitude fraca demais para concluir.

**O teste que decide** é somar `PER_FER` da própria BDGD e comparar essa parcela
contra a perda total modelada. Se o ferro responder por ~30% do nosso número, o
viés está explicado e a questão passa a ser de CONVENÇÃO: o `PERD_*` da
distribuidora provavelmente não inclui perda a vazio. Lê `.gdb`, então é job.

### 11. O ferro é parcela GRANDE da perda modelada — e a comparação com o `PERD_*` pode ser de convenção, não de erro

Medido em 30/08 nas 97 bases (`medicoes/ferro.json`, job 34797), somando
`PER_FER` da EQTRMT — a placa declarada pela própria distribuidora.

Nas 38 bases com declaração original e plausível, o ferro representa uma
**mediana de ~60% da perda que o modelo reporta**, com faixa de 15% a 183%.

| base | ferro | modelo | ferro/modelo | declarado |
|---|---:|---:|---:|---:|
| NEOENERGIA40 | 1,61% | 11,01% | 15% | 2,15% |
| EFLUL86 | 1,39% | 4,43% | 31% | 3,12% |
| CHESP103 | 2,73% | 4,52% | 60% | 2,63% |
| COOPERNORT5345 | 6,46% | 4,74% | 136% | 3,55% |
| CRELUZD598 | 7,81% | 4,28% | 183% | 2,33% |

**RESSALVA QUE LIMITA A CONCLUSÃO.** Os dois percentuais têm denominadores
diferentes: o ferro está sobre a potência NOMINAL instalada, e a perda do
modelo sobre a energia INJETADA no dia simulado. A razão é ordem de grandeza,
não medida. Os casos acima de 100% denunciam isso — ferro não pode exceder a
perda total.

**O que se sustenta mesmo assim:** o ferro é parcela **grande**, não marginal,
da perda modelada. É suficiente para explicar um viés de 1,42x, e portanto a
diferença entre o nosso número e o `PERD_*` pode ser de **convenção contábil** —
se a distribuidora reporta só a parcela dependente de carga, os dois números
estão certos medindo coisas diferentes.

**FECHADO na V25**, que passou a registrar onde a perda acontece. Nas 38 bases
com declaração original e plausível:

| | mediana |
|---|---:|
| perda modelada TOTAL | 4,57% |
| ... parcela nos transformadores | **78%** |
| perda modelada SÓ nas linhas | 0,87% |
| perda DECLARADA (`PERD_*`) | 3,15% |

| comparação | razão |
|---|---:|
| nosso total / declarado | 1,42x |
| nossas linhas / declarado | **0,29x** |

**A hipótese da convenção MORRE aqui.** Se o `PERD_*` cobrisse só a parcela
dependente de carga, ele deveria bater com as nossas linhas — e elas dão 0,87%
contra 3,15% declarados, quatro vezes menos. O declarado **inclui**
transformador; não há convenção que reconcilie.

**Mas o achado 11 entrega algo melhor que a hipótese que o motivou:** ele
localiza o excesso. Com 78% da nossa perda nos transformadores, o viés de 1,42x
está **dentro deles**, não nas linhas. Nossa perda de transformador é ~3,56%
contra um declarado TOTAL de 3,15%.

**O próximo suspeito, e é testável:** perda de ferro é potência CONSTANTE, então
como percentual ela depende do denominador — a energia entregue. Se a carga que
modelamos (`ENE_01/730 h`) for menor que a energia real do alimentador, o ferro
infla em percentual sem que o watt esteja errado. Comparar a energia injetada
do modelo contra a medida por alimentador decide isso, e os dois números já
estão em `resultados/`.

**Subproduto, e é um negativo limpo:** apenas **261 de 6.137.403
transformadores** não declaram `PER_FER` — 0,00%. Ao contrário do `PERD_*`
(achados 8 e 9), a placa dos transformadores é preenchida de forma consistente
em todo o país. Nem toda tabela da BDGD tem o mesmo problema.

### 12. A fragmentação é característica POR DISTRIBUIDORA, e a Light é o extremo

> **REVERTIDO PELO ACHADO 21 (01/09/2026).** O que variava por
> distribuidora era, sobretudo, quantas subestações de cada base têm duas
> barras de MT.

> **Encerrado pelos achados 15 e 16.** Este achado sabia dizer que a
> fragmentação variava por distribuidora, não de onde vinha nem quanto valia.
> O 15 mostrou que está na BDGD e o 16 lhe deu denominador adimensional. A
> medida por km usada aqui não estava errada — correlação de 0,975 com a
> definitiva —, mas "45,8 isolados por km" não diz se é muito, e "73,87% dos
> trechos" diz.

Investigado em 30/08 sobre a V24, seguindo o achado 3 (a BT completa falha por
fragmentação, e ela já existe na MT).

**Chave aberta não explica.** São **11,66 milhões** de ramos isolados contra
**90 mil** chaves ilhadas — 130 para 1. E 1.333 subestações têm ZERO chaves
ilhadas e ainda assim ramos isolados, com mediana de 55.

**Está concentrado, mas não é anedota.** As 200 piores subestações (5% de
4.190) concentram **50%** do total. Normalizado por km, a distribuição tem
cauda longa: mediana 0,28, p90 **17,9**, p99 **71,4** — e **22,5% das
subestações passam de 5 ramos isolados por km**.

**E é característica da BASE, não do conversor.** Mediana de ramos isolados por
km, por distribuidora:

| | bases |
|---|---:|
| mediana abaixo de 0,1 (praticamente zero) | **40 de 76** |
| mediana acima de 10 | **3** |

| base | isolados/km |
|---|---:|
| CASTRODIS11825, CEDRAP5381, CEDRI5366, CEREJ5352… | **0,000** |
| ENERGISA_M404 | 2,20 |
| EQUATORIAL37 | 7,12 |
| EDP_SP391 | 26,45 |
| **Light** | **45,84** |

**O conversor é o mesmo para as 97.** Se o defeito fosse do código, apareceria
de forma uniforme; ele aparece em quarenta bases como zero absoluto e na Light
como 45,8 por km. O gatilho está no dado, ou em como o dado de cada
distribuidora interage com uma premissa nossa.

**Isso fecha o círculo com a BT.** A Light é a pior em fragmentação de MT e é
justamente a que falha no `--bt completo` com 92% de cargas mortas. São o mesmo
fenômeno, não dois problemas.

**Ressalva:** "está no dado" não significa "não é problema nosso". Pode ser um
campo que algumas distribuidoras preenchem e outras não, e que o conversor
trata mal quando falta. Distinguir isso exige abrir a topologia de uma Light
contra a de uma base limpa — que é a próxima investigação, e precisa da `.gdb`.

### 13. A perda declarada não comporta o ferro dos próprios transformadores

Investigado em 30/08 com a V25, e este achado **não depende do nosso modelo**.

**Primeiro, a nossa perda de transformador foi validada contra o dado deles.**
Calculando o ferro a partir do `PER_FER` da EQTRMT — a placa que a própria
distribuidora publica — sobre a carga que modelamos a partir do `ENE_01` dela:

| | mediana |
|---|---:|
| ferro pela placa da distribuidora | 2,55% |
| nossa perda de transformador modelada | 3,30% |
| razão | **1,28x** |

A diferença é cobre, que é o esperado, e **57 de 81 bases** ficam entre 0,7x e
1,5x. Não estamos inventando perda de transformador: ela é consistente com a
placa deles.

**E é isso que expõe a contradição.** Se o ferro implícito nas placas deles é
2,55% e a perda técnica que eles declaram é 3,09%, sobra **meio ponto
percentual** para tudo o mais — linhas, cobre dos transformadores, ramais.
Nossas linhas sozinhas já dão 0,87%.

**Em 40 das 81 bases o ferro sozinho JÁ EXCEDE a perda técnica declarada.**
Entre as 38 com declaração original e plausível, são 15.

| base | ferro pela placa | declara | razão |
|---|---:|---:|---:|
| CRELUZD598 | 7,81% | 2,33% | **3,4x** |
| COOPERNORT5345 | 6,46% | 3,55% | 1,8x |
| CERTREL5369 | 3,77% | 2,35% | 1,6x |
| CERNHE6609 | 6,41% | 4,18% | 1,5x |

**Todos os números desta tabela são da distribuidora**: `PER_FER` da placa dos
transformadores, `ENE_01` das unidades consumidoras, `PERD_*` da declaração de
perdas. O nosso papel foi juntá-los. Uma perda técnica declarada menor que a
perda a vazio dos próprios transformadores é **contradição interna do dado**.

**Isto é o produto do auditor na sua forma mais forte** — mais que o achado 7,
que dependia de acreditar no nosso cálculo de perda. Aqui não há modelo no meio:
há três campos da mesma BDGD que não fecham entre si.

**Ressalva:** o denominador é a carga média que modelamos (`ENE_01/730 h`). Se
a energia real for maior que a faturada — furto, medição incompleta — o ferro
percentual cai. Isso não salva os casos extremos: a CRELUZD598 precisaria de
mais que o triplo da energia declarada para caber.

### 14. O recorte por subestação NÃO causa a fragmentação — hipótese refutada

Medido em 31/08 nas 97 bases (`medicoes/recorte.json`). A hipótese vinha de
26/08, do caso da Light, e nunca tinha sido verificada.

**O mecanismo suspeito era real, mas não acontece.** O `converter.py` monta um
modelo por subestação e filtra a SSDMT pelos CTMTs daquela SE, então um trecho
de CTMT alheio ficaria de fora e o que viesse depois dele viraria ramo isolado.
Um PAC tocado por trechos de duas subestações seria o ponto de corte.

| | |
|---|---:|
| bases com **ZERO** PACs multi-SE | **92 de 97** |
| **Light** (a pior em fragmentação, 45,8 isolados/km) | **0** |
| EDP_SP391 (a 2ª pior, 26,5/km) | **0** |
| única base com muitos: COPELDIS2866 | 5.751 (0,19%) |

**E a segunda hipótese caiu junto.** Trecho cujo CTMT não existe na tabela CTMT
é descartado pelo filtro, o que também órfãos vizinhos. São 74.593 no país —
mas **82 das 97 bases têm zero**, e a Light e a EDP_SP391 estão entre elas. A
base com mais órfãos (ENERGISA_M404, 3,1%) não é das piores em fragmentação.

**Sobra uma explicação, e ela muda de quem é o problema:** os PACs simplesmente
não encadeiam **dentro da própria subestação**. Se for isso, a BDGD declara
pedaços de rede que não se tocam, e o ramo isolado não é efeito do nosso
recorte — é o que está escrito na tabela.

O diagnóstico foi estendido para contar **componentes conexas por subestação**.
Uma SE radial sadia tem uma; milhares significam rede declarada em pedaços.
Falta rodar.

### 15. A fragmentação está na BDGD, e o grau dela prevê a do modelo

> **REVERTIDO PELO ACHADO 20 (01/09/2026).** A métrica usada aqui —
> `componentes por subestação` — mede a rede junto com o número de
> alimentadores por subestação e com o critério de agrupamento da base (achados
> 19 e 19b). Trocada pelo alcance a partir da cabeceira, que não tem esses
> vieses, a rede declarada aparece **99,92% conexa** e a correlação com a
> fragmentação do modelo **desaparece**. A conclusão abaixo está errada no
> ponto principal: a fragmentação é do conversor, não do dado. O texto fica
> como registro do erro.

Medido em 31/08 nas 97 bases, montando o grafo de conectividade **por
subestação** com as quatro camadas que o `converter` emite — SSDMT, UNSEMT
(chaves), UNREMT (reguladores) e UNTRMT.

**A correção importava.** Contando só a SSDMT, a mediana nacional dava 384
componentes por subestação e a CEREJ5352 — que tem ZERO ramos isolados no
modelo — aparecia com 42. Com as quatro camadas a mediana cai para **4**, e a
CEREJ5352 para **1**. Chaves e transformadores costuram a rede, e medir sem
eles media uma rede que nunca foi construída.

| base | componentes/SE | máx | SEs fragmentadas | isolados/km no modelo |
|---|---:|---:|---:|---:|
| CEREJ5352 | **1** | 3 | 17% | 0,00 |
| CASTRODIS11825 | **1** | 4 | 20% | 0,00 |
| CMIG | 5 | 1.844 | 87% | — |
| EDP_SP391 | 8 | 19 | 94% | 26,45 |
| **Light** | **28** | 156 | **100%** | **45,84** |

**E o grau prevê o resultado.** Agrupando as 96 bases pela fragmentação medida
na BDGD, contra os ramos isolados por km que o modelo produz:

| componentes/SE na BDGD | bases | isolados/km no modelo |
|---|---:|---:|
| 1 (conexa) | 26 | **0,02** |
| 2 a 3 | 20 | 0,05 |
| 4 a 9 | 40 | 0,21 |
| 10 ou mais | 10 | 0,19 |

Correlação de postos de **0,45**. Uma base cuja BDGD declara subestações
conexas produz modelo praticamente sem ramo isolado; uma que declara em pedaços
produz modelo fragmentado, na mesma ordem.

> **Correção de 01/09/2026.** A primeira redação deste achado publicou **0,61**
> para este par, e o valor não é dele: 0,61 é a correlação entre *ramos
> isolados por subestação* e *componentes médios por subestação* — dois
> agregados por SE, nenhum dos dois normalizado pelo tamanho da rede. O par que
> a tabela acima descreve (isolados por km × componentes/SE **mediana**) dá
> **0,445**, e é esse que vale. O erro foi de correspondência entre o número e
> a descrição, não de cálculo, e não muda a conclusão — muda a força dela.
> O achado 16 refaz a medida com denominador adimensional.

**Conclusão: a fragmentação não é defeito do conversor.** Ela está no dado de
origem, e o conversor a reproduz. Apenas **27 das 97 bases** declaram uma
subestação mediana eletricamente conexa; nas demais, a BDGD publica pedaços de
rede que não se tocam por nenhuma das quatro camadas.

**O que isso resolve e o que não resolve.** Resolve a pergunta de quem é o
problema — e fecha o achado 12, que só sabia dizer que variava por
distribuidora. Não resolve o `--bt completo`: se a rede vem partida da origem,
modelar a baixa sobre ela continua inviável, e a limitação passa a ser de dado,
não de código.

**Ressalva:** a correlação é 0,45, não 0,9. Há bases conexas com algum ramo
isolado e bases fragmentadas com poucos — outro fator em jogo, ainda não
identificado. E o grupo de "10 ou mais" tem mediana menor que o de "4 a 9",
o que a amostra de 10 não permite tratar como inversão real.

### 16. Um quarto da rede modelada do país não chega à fonte

> **SUBSTITUÍDO PELO ACHADO 23 (02/09/2026).** O número correto,
> medido por tensão sobre os mesmos modelos, é **7,09%** — os 25,70%
> vinham de `AllIsolatedBranches`, que reporta como isolada a rede
> alimentada pela segunda fonte de uma subestação.

> **REVERTIDO PELO ACHADO 21 (01/09/2026).** O numerador vinha de
> `Topology.AllIsolatedBranches()`, que reporta como isolada toda a rede
> alimentada pela segunda fonte de uma subestação — energizada e
> funcionando. Medido por tensão, o isolamento real da pior subestação da
> Light é **0,34%**, não 80%. Os 25,70% não existem.

Medido em 01/09/2026 nas 97 bases da V25, com o denominador que faltava.

`n_linhas` existia no `validador` desde sempre e **não era coletado**. Sem ele,
o achado 12 mediu fragmentação em ramos isolados **por quilômetro** — e km mede
comprimento, não número de trechos. Uma rede de poucos trechos longos e uma de
muitos curtos dão o mesmo km e fragmentações que não se comparam. Com o campo
no coletor, a medida vira adimensional: **que fração dos trechos modelados está
eletricamente desligada da fonte**.

**11.660.236 de 45.374.525 trechos, ou 25,70%.** Mediana por base de 5,48%,
com quartis em 0,21% e 31,02%. Só **duas** bases têm zero.

| base | trechos isolados | trechos | % |
|---|---:|---:|---:|
| CHESP103 | 29.180 | 32.873 | **88,77%** |
| CERSUL5368 | 22.017 | 26.800 | 82,15% |
| **Light** | 783.515 | 1.060.726 | **73,87%** |
| EQUATORIAL37 | 1.093.069 | 1.536.994 | 71,12% |
| EDP_SP391 | 402.366 | 607.771 | 66,20% |
| Cemig | 404.364 | 6.514.317 | 6,21% |
| CEREJ5352 | 8 | 21.693 | **0,04%** |

**O ranking por km não estava errado** — a correlação de postos entre as duas
métricas é **0,975**, e nenhuma conclusão do achado 12 cai. O que muda é a
leitura: "45,8 isolados por km" não diz se é muito, e "73,87% dos trechos" diz.

**E o gradiente contra a BDGD fica nítido**, o que a métrica por km escondia:

| componentes/SE na BDGD | bases | % de trechos isolados (mediana) |
|---|---:|---:|
| 1 (conexa) | 26 | **0,21%** |
| 2 a 3 | 20 | 0,30% |
| 4 a 9 | 40 | **22,87%** |
| 10 ou mais | 10 | 17,37% |

Duas ordens de grandeza entre "até 3 componentes" e "4 ou mais" — não é uma
rampa, é um **degrau**. A correlação de postos continua modesta (0,452) porque
dentro de cada lado do degrau a ordem é quase aleatória; o que existe é um
limiar, não uma proporcionalidade. Isso corrige a leitura do achado 15: a
fragmentação da BDGD não *gradua* a do modelo, ela a **liga**.

**Consequência para o `--bt completo`.** Modelar baixa tensão sobre uma rede
cuja média já vem 25,70% desligada não é caro, é sem sentido — a carga
pendurada num trecho isolado não recebe tensão qualquer que seja o esforço de
cálculo. A viabilidade passa a ter um critério de entrada barato e mensurável
antes de simular: componentes por subestação na BDGD ≤ 3.

### 17. A Enel SP sempre coube; a Cemig cabe em 40%

Medido em 01/09/2026, aplicando o critério do achado 16 subestação a
subestação nas duas maiores bases onde a `--bt completo` era dada como
inviável.

| base | SEs | elegíveis (≤3 componentes) | % | pior SE |
|---|---:|---:|---:|---:|
| **Enel SP** | 155 | **150** | **96,8%** | 15 |
| **Cemig** | 412 | **163** | 39,6% | 1.844 |

**A distribuição, que a mediana escondia:**

| componentes/SE | Enel SP | Cemig |
|---|---:|---:|
| 1 (conexa) | **136** | 55 |
| 2 a 3 | 14 | 108 |
| 4 a 9 | 4 | 174 |
| 10 a 99 | 1 | 70 |
| 100 ou mais | 0 | **5** |

**A Enel SP nunca foi um caso perdido.** 136 das 155 subestações dela são
eletricamente conexas na BDGD, e 150 passam no critério. A hipótese de 26/08
a classificava como limítrofe por ter 632 m de BT por transformador; o achado
16 mostra que o previsor era outro, e por ele ela é a base grande mais sadia
que temos.

**E a Cemig não é uniformemente ruim, e sim BIMODAL.** Cinco subestações com
mais de cem componentes — uma com 1.844 — puxavam a mediana da base inteira
para 5 e a reprovavam por atacado. Separadas essas, 163 subestações passam no
mesmo critério que a Enel SP.

**O que isto muda no produto.** A pergunta deixa de ser "esta base aguenta
baixa tensão completa?", que só admite sim ou não, e passa a ser "que parte da
concessão aguenta?" — respondida antes de simular, lendo a `.gdb`. A limitação
declarada deixa de ser *"a BT completa não roda nas grandes"* e passa a ser
*"a BT completa roda na parte da rede que a BDGD declara conexa, e essa parte
é mensurável: 96,8% da Enel SP, 39,6% da Cemig"*.

**O que ainda não está medido:** que as elegíveis de fato rodem. O critério
prevê fragmentação do modelo, e fragmentação era a causa suspeita do fracasso
da BT — mas escala e custo são outra coisa, e as 150 da Enel SP somam milhões
de UCs. Isso é rodada, não leitura de tabela.

### 18. A safra 2025 não corrigiu a contradição — ela persiste igual

Medido em 01/09/2026, no dia em que a safra 2025-12-31 entrou. **Este achado
não depende do nosso modelo nem de conversão nenhuma**: são três campos da
mesma BDGD, lidos das 99 bases novas e das 97 antigas.

A comparação que vale é **pareada** — as **63 bases** com declaração utilizável
nas duas safras. Comparar o agregado misturaria composição diferente:

| | 2024 | 2025 |
|---|---:|---:|
| ferro pela placa (mediana) | 2,46% | **2,42%** |
| perda técnica declarada (mediana) | 3,03% | **3,06%** |
| bases em que o ferro EXCEDE o declarado | 25 de 63 | **26 de 63** |
| razão piorou / melhorou | — | **31 / 32** |

**Nada mudou.** As distribuidoras republicaram a base com um ano a mais de
dados e a contradição interna seguiu no mesmo lugar, com a mesma intensidade, e
quase exatamente nas mesmas bases. Trinta e uma pioraram, trinta e duas
melhoraram: é ruído, não correção.

**Por que isso fortalece o achado 13 em vez de repeti-lo.** Uma contradição
observada em uma safra admite a leitura de erro pontual de preenchimento — um
ano ruim, um campo mal exportado. Observada em **duas safras consecutivas, nas
mesmas bases**, ela deixa de ser episódio e passa a ser **característica do
processo de declaração**. O `PERD_*` não é um número que erra às vezes: é um
número que não está sendo produzido a partir do parque declarado.

**O filtro é parte do achado, e custou uma execução errada.** A primeira
medição publicou "2.639% de ferro" e razões de 213.530x — denominador
degenerado, não contradição. A CERBRANORT6898 declara 0,2 GWh no ano para 1.810
transformadores. Ficam de fora as bases com ferro acima de 25% da energia (a
energia da CTMT é que está errada) e as que declaram menos de 0,5% (não há
perda com que comparar). Em 2024 isso descarta 29 das 97; em 2025, 23 das 99.

**O que a safra nova mudou, e não é pouco:** a fração de bases com declaração
utilizável subiu de 68/97 para 76/99. Mais distribuidoras estão declarando algo
comparável — e o que declaram continua não fechando com o próprio parque.

### 19. A métrica de fragmentação depende de como a base AGRUPA subestações

Medido em 01/09/2026, comparando a fragmentação das 97 bases nas duas safras.
**Este achado corrige a leitura dos achados 15, 16 e 17**, e apareceu porque o
número bruto era bom demais para ser verdade.

**O que o número bruto dizia:** a fragmentação teria piorado muito de 2024 para
2025 — bases com subestação mediana conexa caindo de 27 para 12, elegíveis para
BT completa de 47 para 32, e piora em 45 das 97.

**O que estava acontecendo:** 57 das 97 bases mudaram o número de subestações
declaradas, 32 delas para menos. E o padrão é inequívoco:

| base | subestações | componentes/SE |
|---|---:|---:|
| CELETRO5343 | 24 -> **1** | 1 -> **21** |
| CEREJ5352 | 18 -> **1** | 1 -> **18** |
| CEMIRIM7467 | 13 -> **2** | 1 -> **13** |
| CEDRAP5381 | 9 -> **1** | 1 -> **9** |

O número de componentes vira **exatamente** o número de subestações fundidas.
A rede não mudou: mudou o rótulo. Quando uma base declara vinte e quatro
subestações sob um único `CTMT.SUB`, as vinte e quatro redes — que nunca se
tocaram — passam a ser componentes da mesma subestação.

**A comparação limpa**, nas 40 bases que mantiveram o mesmo número de
subestações:

| | 2024 | 2025 |
|---|---:|---:|
| componentes/SE (mediana) | 5,0 | **5,5** |
| piorou / melhorou / igual | — | **13 / 7 / 20** |

Estabilidade com leve piora, e não colapso.

**A ressalva que isto impõe aos achados 15 a 17.** "Componentes por subestação"
mede a rede **e o critério de agrupamento junto**. Nas bases grandes, que
declaram centenas de subestações, o efeito é desprezível — a Cemig tem 412 e a
Enel SP 155, e nelas o rótulo corresponde a instalação física. Nas pequenas,
que declaram uma só, a métrica mede sobretudo o rótulo. O critério de entrada
para a `--bt completo` (≤ 3 componentes) **continua valendo onde foi medido**,
que são as grandes, e deve ser usado com cuidado em base de uma subestação.

### 19b. E há um segundo viés, elétrico: alimentador não se toca

Investigando o primeiro, apareceu outro — e este atinge a medida no alvo, não
só na comparação entre safras.

**A mediana nacional de componentes por subestação é 4,0. A mediana de
ALIMENTADORES por subestação também é 4,0.**

A explicação é elementar e elétrica: alimentadores da mesma subestação são
radiais e **só se encontram na barra da SE**, que não está em nenhuma das
quatro camadas unidas (SSDMT, UNSEMT, UNREMT, UNTRMT). Contar cada alimentador
como componente separada chama de fragmentação o que é topologia normal de
distribuição.

**Mas o viés não é uniforme, e é isso que salva o achado:**

| base | alimentadores/SE | componentes/SE | leitura |
|---|---:|---:|---|
| Enel SP | 11,7 | **1** | os alimentadores SE TOCAM |
| NEOENERGIA5160 | 14,4 | **1** | idem |
| **Light** | 18,2 | **28** | 10 componentes ALÉM dos alimentadores |
| COPELDIS2866 | 10,8 | **76** | 65 além |

A correlação entre as duas é 0,436 — existe, e não explica tudo. Onde
`componentes/SE` excede `alimentadores/SE` com folga, sobra fragmentação real.
Onde é igual ou menor, o número mede topologia, não defeito.

**O que isto NÃO derruba:** o achado 16. Os 25,70% de trechos que não chegam à
fonte são medidos NO MODELO, pelo próprio OpenDSS, e não dependem desta
contagem. O que fica em xeque é o uso de `componentes/SE` como medida de
qualidade do dado, e o corte de ≤ 3 como critério de entrada.

**A medida robusta, agora implementada:** *fração dos trechos de cada
alimentador alcançável a partir do `CTMT.PAC_INI`*. Ela não depende do
agrupamento em subestações nem da separação natural entre alimentadores —
cada alimentador tem uma cabeceira declarada, e a pergunta é quanto da rede
dele se alcança dali.

Na Sulgipe 2025 as duas medidas discordam frontalmente, e a robusta acerta:
**6 componentes por subestação** contra **99,94% de alcance mediano** e 96,4%
dos alimentadores íntegros — e o modelo dessa base roda com 7 de 7 subestações
`OK` e 0,12% de trechos isolados.

### 20. A rede declarada É alcançável — a fragmentação é NOSSA

> **CORRIGIDO PELO ACHADO 21 (01/09/2026).** A parte medida continua
> válida — a rede declarada é 99,92% alcançável. Mas a atribuição está
> errada: não há fragmentação no modelo para atribuir a ninguém. O que
> existia era artefato de medição.

Medido em 01/09/2026 nas 97 bases de 2024 e nas 99 de 2025, com a medida
robusta do achado 19b. **Este achado reverte a conclusão do achado 15.**

**O alcance mediano nacional a partir da cabeceira é 99,92%.** A rede que a
BDGD declara é, para todos os efeitos, conexa: partindo do `CTMT.PAC_INI` de
cada alimentador e caminhando pelas quatro camadas, chega-se a praticamente
todos os trechos dele.

E o modelo, sobre essa mesma rede, perde um quarto:

| base | alcance na BDGD | trechos isolados no MODELO |
|---|---:|---:|
| CHESP103 | **99,92%** | **88,77%** |
| CERSUL5368 | 99,86% | 82,15% |
| **Light** | **100,00%** | **73,87%** |
| EQUATORIAL37 | 100,00% | 71,12% |
| EDP_SP391 | 100,00% | 66,20% |

**A correlação entre as duas medidas é −0,205** — nula. Das **57 bases com
alcance acima de 99,9%**, **18 produzem modelo com mais de 20% de trechos
isolados**.

**O que isso derruba.** O achado 15 concluiu que "a fragmentação está na BDGD e
o grau dela prevê a do modelo", com correlação de 0,45 contra
`componentes/SE`. O achado 19b mostrou que aquela métrica media, em boa parte,
o número de alimentadores por subestação — topologia normal — e o critério de
agrupamento da base. Trocada por uma medida que não tem esses vieses, **a
correlação desaparece e o sinal inverte de dono**: a rede vem inteira e o
modelo a quebra.

**A hipótese, concreta e verificável.** O modelo é montado por SUBESTAÇÃO e a
fonte fica na barra dela. Cada alimentador é internamente conexo — o alcance
prova isso —, mas precisa estar ligado à barra da SE pelo `PAC_INI`, através do
transformador de AT. Se essa ligação não é emitida para um alimentador, ele
inteiro fica isolado no modelo, intacto e sem tensão. Isso explicaria por que os
ramos isolados vêm em blocos grandes e por que não correlacionam com nada da
BDGD.

**O que isso NÃO muda:** o achado 16 continua valendo como MEDIDA — 25,70% dos
trechos modelados não chegam à fonte, e isso é fato do nosso modelo. O que muda
é a ATRIBUIÇÃO: a causa não está no dado de origem.

**Consequência para o produto.** A `--bt completo` não é inviável por dado
partido, e o critério de entrada do achado 17 (componentes/SE ≤ 3) não tem
fundamento. Há um defeito de conversão afetando um quarto da rede modelada do
país, e ele é a prioridade — acima da safra 2025 e acima da validação externa.

**Ressalva honesta:** o alcance mede conectividade nas quatro camadas de MT.
Ele não prova que o `.dss` emitido deveria ser conexo — o conversor faz
recortes legítimos. Mas 100% de alcance com 73,87% de isolamento é uma
distância que nenhum recorte legítimo explica.

### 21. Não havia fragmentação: `AllIsolatedBranches` mente com duas fontes

Medido em 01/09/2026, abrindo a subestação 18520353 da Light — a que mais
"isolava". **Este achado encerra a cadeia 12 → 15 → 16 → 20 e mostra que ela
inteira media um artefato.**

`Topology.AllIsolatedBranches()` percorre a árvore a partir de **uma** fonte.
Subestação com duas barras de MT é comum, e o `MASTER` emite uma `Vsource` para
cada — então **toda a rede alimentada pela segunda barra aparece como
isolada**, estando energizada e funcionando.

**A prova, elemento a elemento:**

| | valor |
|---|---:|
| `AllIsolatedBranches` na SE 18520353 | 36.695 de 45.868 (80%) |
| linhas realmente **sem tensão** | **155 de 45.868 (0,34%)** |
| linhas "isoladas" com tensão normal | 300 de 300 amostradas, a 1,02 pu |
| ao desligar a 2a fonte | **as 300 morreram** |

**E o padrão vale nas 4.189 subestações da V25:**

| subestações | mediana de "isolado" |
|---|---:|
| com **uma** fonte (3.301) | **0,86%** |
| com **duas ou mais** (888) | **68,88%** |

Oitenta vezes de diferença, decidida por quantas barras de MT a subestação tem
— não por qualidade de dado, nem por defeito de conversão.

**O que cai, e é muito:**

- **Achado 16** (25,70% dos trechos não chegam à fonte): falso. A rede está
  energizada. A ordem de grandeza real é ~1%.
- **Achado 20** (a fragmentação é nossa): falso na atribuição. Não há
  fragmentação a atribuir.
- **Achado 15** (está na BDGD): já revertido pelo 20, e agora por outro motivo.
- **Achado 12** (característica por distribuidora): media sobretudo quantas
  subestações de cada base têm duas barras de MT.
- **O critério de entrada da `--bt completo`** perde o fundamento pela segunda
  vez.

**O que se sustenta:** o achado 17 continua útil como descrição do dado — a
Enel SP tem 136 subestações eletricamente conexas na BDGD e a Cemig 55 —, mas
não mais como critério de viabilidade, porque o que ele previa não existia.

**O mais desconfortável: o projeto já sabia.** O `validador` carrega, desde
antes, o comentário explicando que `AllIsolatedLoads` percorre a topologia a
partir de uma fonte e por isso dá "falso positivo em massa" — e mantendo
`cargas_sem_tensao` como a medida confiável. `AllIsolatedBranches`, a função
irmã com o mesmo defeito, ficou ao lado sendo tratada como verdade por quatro
achados. O sinal estava a duas linhas de distância.

**A pista que não foi seguida:** subestações com 80% da rede "isolada" e
**ZERO cargas sem tensão**, veredicto `OK`. Isso é contraditório e estava
publicado em `resultados/` desde a V25. E `ramos_isolados` chegava a exceder
`n_linhas` — impossível para um subconjunto das linhas, e o primeiro sinal que
de fato levou à investigação.

**Correção aplicada:** `ramos_isolados` passa a ser medido por tensão —
linha cuja barra tem menos de 1 V. O valor topológico continua publicado como
`ramos_isolados_topologia`, com o nome dizendo o que ele é. Custo: 0,2 s por
subestação.

**O que falta:** os números nacionais corrigidos exigem reprocessar o
`validador` nas 97 bases. A V26 deixa de ser opcional e passa a ser **a rodada
que refaz as medidas**.

### 22. O regulador entra EM PARALELO com o trecho que ele deveria regular

Medido em 02/09/2026, abrindo a subestação AGV da NEOENERGIA385 — a base que
concentra 68 das 139 subestações fora do `OK` na V26. **Este é defeito NOSSO, e
o primeiro achado do projeto que aponta um erro de conversão com causa
precisa.**

**O sintoma:** a subestação dissipa **9,9 MW em perdas** com a tensão mediana
de MT em **0,415 pu**, e isso **não muda ao desligar as 1.282 cargas**. Sem
carga não deveria haver corrente.

**A bissecção, elemento a elemento** (`batchedit` não tem efeito e mascarou os
primeiros testes; o que vale é desabilitar um a um):

| desligando | V_MT | perdas |
|---|---:|---:|
| nada | 0,415 pu | 9.906 kW |
| cargas, PV, reatores, capacitores | 0,410 pu | 9.893 kW |
| **os 9 reguladores** | **1,013 pu** | **229 kW** |

**A causa, nas barras:**

    Line.1083769322   agv4824224137.1.2.3  ->  agv481083769275.1.2.3
    REG_AGV01760_1    agv4824224137.1      ->  agv481083769275.1

O regulador liga **o mesmo par de barras** que uma linha já liga. A BDGD
declara o regulador na UNREMT com `PAC_1` e `PAC_2`, e a SSDMT declara o
**trecho entre os mesmos dois PACs** — o vão onde o equipamento está instalado.
O conversor emite os dois, e o regulador fica em paralelo com um caminho de
impedância quase nula. Com o tap regulando contra esse curto, circula corrente
de laço: **2.506 A num condutor de 145 A**.

**Não é caso isolado: 9 de 9 reguladores da AGV estão assim.**

**O que isto explica.** `REGULADOR_SATURADO` aparece como causa em **89
subestações** só nesta base — o tap corre até o fim tentando vencer o paralelo.
E `reguladores_pendurados`, que o validador já mede, **não pega**: ele detecta
ponta solta, e aqui as duas pontas estão conectadas. O defeito não tem
detecção hoje.

**Quanto vale.** 252 das 4.061 subestações têm regulador com alguma anomalia
registrada, e a NEOENERGIA385 sozinha responde por metade do que falta para
100% de veredictos `OK`. Se a correção valer para as demais, é o maior ganho
isolado disponível.

**A correção NÃO é remover o regulador.** Ele existe na rede real. O trecho e
o regulador são o mesmo vão físico declarado em duas tabelas — ou o trecho sai
e o regulador o substitui, ou o regulador entra em série, com barra
intermediária. Isto ainda não está implementado.

### 23. Os números definitivos, depois de remedir as três safras

Medido em 02/09/2026, revalidando os 97 modelos da V25 com o validador
corrigido — **97 modelos, zero falhas, 4.237 subestações**. Este achado fecha a
cadeia 12 → 15 → 16 → 20 → 21 com valores que não mudam mais.

**As três medidas, agora separáveis:**

| medida | valor |
|---|---:|
| V25 pelo método antigo (topológico) | 25,70% |
| **V25 remedida, por tensão (safra 2024)** | **7,09%** |
| V26 por tensão (safra 2025) | 8,62% |

**Dois terços da queda são correção da medida.** Comparando a mesma safra e os
mesmos modelos, 25,70% viram 7,09% só por trocar `AllIsolatedBranches` — que
reporta como isolada a rede alimentada pela segunda fonte de uma subestação —
por tensão medida barra a barra.

**E a diferença entre safras é pequena:** 7,09% em 2024 contra 8,62% em 2025,
com a safra nova ligeiramente pior. Nada que se compare com o artefato.

**O número correto do isolamento da rede modelada do país é ~7%**, e **814 das
4.237 subestações (19%) têm zero** trecho sem tensão.

**O que isso encerra:**

- o achado 16 (25,70%) fica **substituído** por este;
- o achado 21 fica **confirmado** com número definitivo — o artefato era
  responsável por dois terços da medida;
- o achado 12 e o 15 seguem revertidos, e agora se sabe por quanto;
- o achado 20 continua válido no que mediu (a rede declarada é 99,92%
  alcançável) e inválido na atribuição, porque não há fragmentação a atribuir.

**A lição que fica, e é metodológica.** Quatro achados publicados se apoiaram
numa função cujo nome prometia uma coisa e cuja implementação fazia outra. O
sinal de que algo estava errado esteve publicado o tempo todo em
`resultados/`: subestações com 80% de "isolamento" e **zero cargas sem
tensão**, com veredicto `OK`. Duas medidas do mesmo arquivo se contradiziam, e
ninguém — nem eu — cruzou uma com a outra até que `ramos_isolados` excedesse
`n_linhas`, o que é aritmeticamente impossível.

## Achado 24 — o efeito nacional da correção do regulador (V26 → V27)

**Medido em 02/09/2026**, comparando as duas rodadas completas das mesmas 99
bases e 4.078 subestações, com os `validacao.json` trazidos por `scp` e somados
fora do cluster.

**As duas rodadas são a safra 2025-12-31.** Confirmado nos logs: as 297
referências de entrada de cada uma apontam para `bdgds_2025/`, com nomes do
tipo `Cemig-D_4950_2025-12-31_V11_*`. A confirmação foi necessária porque o
`_procedencia.json` da época **não gravava a safra** — o nome da pasta
(`MODELOS_NEOENERGIA385_V27`) também não a carrega, já que a tag só ganha o ano
quando duas safras colidem na mesma pasta. A partir de 02/09/2026 o
`_procedencia.json` grava `safra`, `data_base` e o nome do `.gdb` de origem,
e há teste travando os três campos.

A correção do achado 22 — o regulador que era emitido **em paralelo** com o
trecho, fechando um laço por onde a corrente circulava — foi aplicada entre a
V26 e a V27. O resultado responde à pergunta que ficou em aberto quando a Light
saiu idêntica nas duas rodadas.

| causa | V26 | V27 | delta |
|---|---:|---:|---:|
| `OK` | 2.388 | **2.505** | **+117** |
| `MODELO_QUEBRADO` | 1.284 | 1.250 | −34 |
| `TENSAO_BAIXA` | 199 | 208 | +9 |
| `REGULADOR_SATURADO` | 172 | **80** | **−92** |
| `REDE_EXTENSA` | 20 | 20 | 0 |
| `CARGA_ALTA` | 15 | 15 | 0 |

**Duas bases mudaram. Noventa e sete não mudaram em nada.**

| base | subestações | `OK` V26 → V27 | tensão mediana de MT | perda mediana |
|---|---:|---|---|---|
| NEOENERGIA385 | 153 | 16 → **128** | 0,698 → **0,987 pu** | 86,3% → **7,3%** |
| COPREL2351 | 8 | 0 → **5** | 0,267 → **0,987 pu** | 95,2% → **8,7%** |

Perda mediana de 86% nunca foi rede: era o laço drenando corrente por um
caminho paralelo. Depois da correção, as duas bases caem para 7,3% e 8,7%, que
é a faixa em que uma rede de média tensão vive.

### O que este achado corrige de uma expectativa nossa

Depois da comparação da Light — 95 subestações **idênticas** nas duas rodadas —
o projeto registrou que a correção atingia 4,56% dos reguladores do país e que
o efeito seria "local, não nacional". A extensão estava certa e a importância
estava errada.

Dos **2.266 reguladores em paralelo**, 2.152 estavam na NEOENERGIA385 e 114 na
COPREL2351. **Concentrado não é o mesmo que pequeno**: onde o defeito ocorre,
ele reprovava 89 de 153 subestações de uma distribuidora inteira.

### O que as 97 bases inalteradas provam

Elas são o controle do experimento, e valem tanto quanto as duas que mudaram: a
correção **não mexeu em nada onde não havia laço**. Nenhuma subestação mudou de
causa, de tensão ou de perda por efeito colateral. Uma correção que melhora o
alvo e desloca o resto seria indistinguível de um ajuste de parâmetro.

### Uma comparação que NÃO se pode fazer com estes números

Os 58,6% → 61,4% de `OK` acima **não são** os 97,4% que o `CHANGELOG` publica
para a v1.0, e misturar os dois seria erro grosseiro por **duas** razões
independentes, não uma.

**Primeira: são safras diferentes.** Estes números são da 2025-12-31; os 97,4%
são da 2024-12-31.

**Segunda: são métricas diferentes.**

- o **veredicto da v1.0** exige compilar, convergir, não ter `NaN` e passar nos
  limites de tensão e ampacidade;
- a **`causa` do `diagnostico.classificar`** é muito mais estrita — **uma única
  carga sem tensão** já classifica a subestação como `MODELO_QUEBRADO`.

É por isso que `MODELO_QUEBRADO` soma 1.284 subestações (31%) enquanto as
`NAO_COMPILA` e `NAO_CONVERGE` da v1.0 somam 29. Os dois números descrevem a
mesma realidade com réguas diferentes, e cada tabela deve dizer qual régua usa.

## Achado 25 — o limiar que descartava a subestação inteira

**Medido em 02/09/2026** sobre as 4.078 subestações da safra 2025 (V27).

`MODELO_QUEBRADO` é a maior classe de reprovação do projeto — **1.250
subestações, 30,7% do total** — e o rótulo escondia quatro defeitos diferentes
na mesma gaveta. Aberta a gaveta:

| motivo real | subestações | fração dos quebrados |
|---|---:|---:|
| carga sem tensão | **1.209** | **96,7%** |
| não converge | 23 | 1,8% |
| não compila | 16 | 1,3% |
| nós com `NaN` | 2 | 0,2% |

**Falha de modelo são 41 subestações, ou 1,0% do país.** O resto é o cadastro,
e a doutrina do `diagnostico.py` dizia o contrário: «MODELO_QUEBRADO … é
defeito nosso: sempre acionável».

E dentro das 1.209, a gravidade varia por três ordens de grandeza:

| quanta carga fica sem tensão | subestações |
|---|---:|
| exatamente 1 carga | 61 |
| menos de 0,1% | 159 |
| 0,1% a 1% | 430 |
| 1% a 10% | 290 |
| **acima de 10%** | **269** |

**650 das 1.209 (54%) perdem menos de 1% da carga** e mesmo assim recebem um
rótulo que afirma que o modelo está quebrado.

### O defeito que estava escondido no meio disso

Oito subestações têm uma assinatura própria: **100% das cargas mortas, fonte
com 0 kW e tensão sem nenhuma variação** — `V_MT_min` igual a `V_MT_mediana`.
Cinco distribuidoras diferentes, o mesmo padrão. A rede inteira existe, a fonte
existe, e as duas não se tocam; o fluxo converge em duas iterações porque não
há carga alguma ligada.

Somam **13.762 cargas** e **53.842 trechos modelados e nunca usados**.

Perseguido na ROL da CEEE Equatorial, a menor delas, o `_LIGACAO.dss` dizia:

```
! nenhuma componente desenergizada relevante nesta subestacao.
! descartada: 212 barras, 13 cargas — poucas cargas
```

A etapa de ligação **encontrou** a componente desconectada e a descartou porque
13 < `MIN_CARGAS` = 20. Só que a ROL tem 13 cargas **no total**: o que foi
jogado fora como ruído era 100% da subestação.

O limiar existe para não inventar elo para fragmento solto, e é um bom limiar.
O erro era ser **absoluto sem denominador**: 13 é pouco numa subestação de
5.000 cargas e é tudo numa de 13. Agora a componente sobrevive por qualquer um
dos dois critérios — `MIN_CARGAS` absoluto **ou** `FRACAO_RELEVANTE` = 10% das
cargas da subestação.

### Dois defeitos que a suíte pegou na própria correção

- **Componente com zero cargas passou a ser ligada.** Numa subestação
  inteiramente morta o piso relativo também é zero, e `0 < 0` é falso — o zero
  escapava pela fresta. Ligar o que não tem carga não muda resultado e só
  acrescenta um elo inventado.
- **Um teste passava por acidente.** `test_componente_pequena_e_ruido` usava um
  fixture com 3 cargas e nada mais, então media o limiar absoluto num universo
  onde ele coincidia com o relativo. Corrigido para declarar as outras mil
  cargas da subestação, que é o que torna as três de fato ruído.

### A reclassificação, e o que ela muda em cada número publicado

Implementada em 02/09/2026. `MODELO_QUEBRADO` passa a guardar **só falha de
modelo** — não compila, não converge, tem `NaN`. A carga sem tensão vira três
classes graduadas pela **fração**, porque o número absoluto não diz nada sem o
denominador.

Simulado sobre as 4.078 subestações da safra 2025:

| causa | antes | depois |
|---|---:|---:|
| `OK` | 2.505 | 2.505 |
| **`MODELO_QUEBRADO`** | **1.250** | **41** |
| `RAMAIS_SOLTOS` (1% a 10%) | — | 290 |
| `REDE_PARCIAL` (acima de 10%) | — | 257 |
| `SUBESTACAO_ILHADA` (99% ou mais) | — | 13 |
| abaixo de 1%: segue para os testes seguintes | — | 649 |
| `TENSAO_BAIXA` | 208 | 208 |
| `REGULADOR_SATURADO` | 80 | 80 |
| `REDE_EXTENSA` | 20 | 20 |
| `CARGA_ALTA` | 15 | 15 |

**`MODELO_QUEBRADO` cai de 30,7% para 1,0% das subestações do país.**

Duas ressalvas que a tabela não mostra sozinha:

- **`SUBESTACAO_ILHADA` deu 13 e não os 8 medidos pela assinatura completa.**
  O corte de 99% pega cinco subestações que perdem quase tudo sem satisfazer o
  teste estrito (fonte com 0 kW **e** tensão sem variação). São 13 casos de
  "quase toda a carga morta", dos quais 8 têm a fonte comprovadamente
  desconectada. Elas saem de `REDE_PARCIAL`, que por isso dá 257 e não 269.
- **Não sei quantas das 649 terminam `OK`.** Elas ainda passam por
  `CARGA_ALTA`, `REDE_EXTENSA`, `REGULADOR_SATURADO` e `TENSAO_BAIXA`, e a
  simulação não pôde rodar esses testes — dependem do `resumo.json` e do
  `extra`, que não vieram no `scp`. O número sai na próxima rodada completa.

**Nada disso mudou a realidade: mudou a régua.** Para reproduzir a contagem
antiga a partir de uma rodada nova, some `MODELO_QUEBRADO` com as três classes
de `diagnostico.SEM_TENSAO` — o conjunto está declarado no código, e não numa
lembrança, exatamente para essa comparação continuar possível.

## Achado 26 — «não converge» é o instantâneo, e o dia resolve

**Medido em 02/09/2026** sobre três das 23 subestações da safra 2025 que não
convergem, escolhidas em **três distribuidoras diferentes** — CYQ da
Neoenergia 47, PTD da Neoenergia 43 e 1425307420 da Cemig.

As 23 param todas em **exatamente 500 iterações**, o teto. Nenhuma é caso de
teto: com 10.000 iterações o resultado sai **idêntico bit a bit**, o que
significa que o motor está preso num ciclo, e não convergindo devagar.

### O que foi refutado por medição

| hipótese | resultado |
|---|---|
| teto de iterações baixo | 100, 500, 2.000 e 10.000 dão o mesmo número |
| controle de regulador | desligar não muda nada |
| capacitor chaveando | não há capacitor em duas delas |
| `controlmode=off` | não muda nada |
| histerese do inversor (`%cutin`/`%cutout`) | zerar não muda nada |
| `Vminpu` do PVSystem | **piora muito** — Vmax vai de 73 a 754 pu |
| `algorithm=newton` | não muda nada |
| GD em barra morta | explica a Cemig; na CYQ **nenhuma** GD está abaixo de 0,9 pu |

### O que sobrou

**A geração.** Desligar os `PVSystem` faz o fluxo fechar em **44 a 59
iterações** nas três. E a convergência volta de forma **gradual** ao baixar a
irradiância, que é a assinatura de uma solução saindo da bacia de convergência
— e não de um controle chaveando:

| irradiância | CYQ (GD 1,52× a carga) | Cemig (GD 0,75×) |
|---|---|---|
| 5% | 59 iterações | 54 iterações |
| 25% | 51 | 54 |
| 50% | 42 | **283** |
| 100% | **não converge** | **não converge** |

### E é por isso que o veredicto estava errado

O instantâneo põe **toda a geração no máximo junto com a carga declarada de
pico**, e essa combinação não ocorre no dia. Resolvidos os 96 passos das mesmas
três subestações:

| subestação | passos que convergem |
|---|---|
| CYQ | **96 de 96** |
| PTD | **96 de 96** |
| Cemig 1425307420 | 79 de 96 (falha das 8h45 às 15h00) |

**Duas das três resolvem o dia inteiro no mesmo modelo que o instantâneo
reprova.** A curva de irradiância chega a 1,0000 exatamente ao meio-dia, então
o dia visita o mesmo ponto — e ainda assim passa, porque ali a carga está na
sua curva e não no valor declarado de pico.

### O que mudou

O `validador.py`, **e só quando o fluxo não fecha** (23 de 4.078), resolve uma
vez mais com a geração desligada e grava `converge_sem_gd`, `iteracoes_sem_gd`
e `n_gd`. Com essa evidência o `diagnostico.py` devolve a causa
`NAO_CONVERGE_COM_GD`, que diz o que fazer: **julgar pelo dia, e não pelo
instantâneo**.

Sem a sonda, o rótulo continua `MODELO_QUEBRADO` — a classe nova exige
evidência, e não suposição.

### O que fica em aberto

**O mecanismo exato não foi encontrado.** Sabe-se que é a geração no máximo, e
sabe-se o que não é (a tabela acima). Não se sabe *por que* o ponto de operação
com toda a GD no máximo sai da bacia de convergência em algumas redes e não em
outras. A caracterização é empírica e suficiente para classificar; não é uma
explicação.

## Achado 27 — a linha de um centímetro que apagava a perda da subestação

**Medido em 02/09/2026** na CMIG 1726588 da safra 2025, uma das duas
subestações do país com `NaN`.

Seis nós com `NaN`, em duas barras. O culpado:

```
New Line.1388482702 Bus1=node_8931988 Bus2=node_1683403983
~ LineCode=CND_210597_1_ABCN_MT_3F Length=0.01 Units=m
```

**Uma linha de um centímetro**, e os dois nomes de barra aparecem **exatamente
uma vez** no modelo inteiro — nela. Nenhuma carga, nenhum transformador,
nenhuma fonte. É pura impedância série flutuando: a submatriz de admitância é
singular, e o OpenDSS devolve `NaN`.

E o `NaN` não fica quieto. A perda da subestação inteira saía `NaN`.

| | `NaN` | P da fonte | perdas | cargas sem tensão |
|---|---:|---:|---:|---:|
| como estava | 6 | 23.939,0 kW | **`NaN`** | 27 |
| **só essa linha desligada** | **0** | 23.939,0 kW | **862,46 kW** | 27 |

Uma linha de 1 cm custava o número de perda de uma subestação de 10.857 barras.

### Por que as defesas existentes não pegavam

O **achado 28** defende a média tensão contra *chave* com os dois PACs fora da
rede. O **achado 51** defende a baixa tensão contra trecho que não alcança
secundário. Esta é uma **linha de MT**, e cai no vão entre as duas.

### O critério é o motor, e não o grafo — e isso custou duas tentativas erradas

Ambas estão registradas como caso de teste, porque um critério plausível que
destrói o modelo é exatamente o que volta se ninguém o registrar.

**Primeira tentativa: raciocinar sobre o grafo das barras mortas.**
`componentes(adj, mortas)` corta a rede na fronteira do que está sem tensão, e
um pedaço morto pendurado na rede viva vira ali uma «componente» que *parece*
isolada e não está. Deu 45 componentes e 432 linhas — e desabilitá-las levou as
cargas sem tensão de 27 para **186** e as perdas para **1,4 × 10¹⁴ kW**.

**Segunda tentativa: guardar `barra → linhas`.** Uma linha com uma ponta na
componente e a outra fora entrava na lista, e desligá-la cortava o lado de
fora.

**O critério que funciona não interpreta grafo nenhum:** *todo elemento que
toca as barras desta componente está dentro dela?* Se sim, ela não se comunica
com o circuito por caminho algum e removê-la não pode mudar nada. Um único
elemento externo — ramo que sai, transformador, capacitor, reator de neutro —
a desqualifica. **Não há lista de tipos de propósito: lista de tipos esquece
um, e o reator de neutro foi o que quase passou.**

Medido com o critério final: **43 componentes, 110 linhas**, e o resultado é
idêntico ao de desligar apenas a linha culpada — mesma potência, mesma perda,
mesmas 27 cargas sem tensão, mesmas 4 iterações. As 110 são provadamente
inertes.

### Um defeito de comparação achado no caminho

A barra com `NaN` é a mais morta que existe, e **escapava do conjunto de
mortas**:

```python
if not v or max(v) < MORTA_V:      # False quando v é NaN
```

Toda comparação com `NaN` é falsa, então a barra nunca entrava em componente
nenhuma — e o detector de órfã deixava de fora justamente a que produzia o
`NaN`. A forma negada, `not (max(v) >= MORTA_V)`, pega os dois casos. Há teste
lendo o fonte para o dia em que alguém "simplificar" a expressão de volta.

## Achado 28-B — o transformador monofásico ligado entre duas fases

**Medido em 03/09/2026** na ROL da CEEE Equatorial, depois que a V28 mostrou
que o achado 25 **não** tinha recuperado as subestações que eu disse que
recuperaria.

Das 8 subestações com 100% da carga sem tensão na V27, a V28 recuperou **uma**.
A ROL continuava com 13 de 13 cargas mortas — mas o motivo do descarte tinha
mudado, de «poucas cargas» para **«nenhuma barra na tensão de um vão»**. O
limiar relativo funcionou; o filtro seguinte é que barrava.

`kv_de_fase` decidia a conversão pelo `NumPhases()` do elemento, e isso erra o
caso mais comum da média tensão brasileira. Os 24 transformadores da ROL:

| fases | nós da barra | kV declarado | quantos | o que é |
|---:|---|---:|---:|---|
| 1 | `.1` | 7,9674 | 9 | fase-neutro |
| 1 | `.1.2` | 13,8000 | 2 | **entre fases** |
| 1 | `.3.1` | 13,8000 | 9 | **entre fases** |
| 3 | `.1.2.3` | 13,8000 | 4 | entre fases |

Os **onze do meio** têm `NumPhases()` = 1, então não eram divididos por raiz de
três e ficavam em 13,8 — enquanto `Bus.kVBase()` é **sempre** fase-neutro e
vale 7,9674 ali. A comparação de `decidir` nunca casava.

**O que decide não é quantas fases o elemento tem: é a quantos nós de fase o
enrolamento se conecta.** Um nó é fase-neutro; dois ou três é linha-linha.
`fases_do_enrolamento` lê isso da especificação da barra.

Com a correção, a ROL religa: **13 de 13 cargas**, 100% energizada.

### Uma ressalva que o próprio arquivo levanta

O elo criado na ROL vem anotado com *«só alcançava a rede viva por chave
declarada ABERTA»*. A doutrina do `ligacao.py` diz que componente assim está
escura **porque a BDGD declara aquela chave aberta**, e que inventar elo ali é
apagar o que o dado diz. O código liga mesmo assim e registra a ressalva; a
premissa é reversível apagando o `redirect _LIGACAO.dss` do MASTER.

Para a ROL a leitura provável é que os alimentadores dela sejam alimentados por
outra subestação, e que o modelo por subestação não tenha como representar
isso. **Isto não está resolvido — está declarado.**

### E o que a V28 mediu de fato

| causa | V27 | V28 | delta |
|---|---:|---:|---:|
| `OK` | 2.505 | **3.073** | **+568** |
| `MODELO_QUEBRADO` | 1.250 | **41** | −1.209 |
| `RAMAIS_SOLTOS` | — | 292 | +292 |
| `REDE_PARCIAL` | — | 253 | +253 |
| `TENSAO_BAIXA` | 208 | 262 | +54 |
| `REGULADOR_SATURADO` | 80 | 98 | +18 |
| `REDE_EXTENSA` | 20 | 28 | +8 |
| `CARGA_ALTA` | 15 | 19 | +4 |
| `SUBESTACAO_ILHADA` | — | 12 | +12 |

**`OK` sobe de 61,4% para 75,4%.** Das 649 subestações que a reclassificação
mandou seguir adiante, **568 terminam `OK`** e 84 caem em outras causas — a
resposta à pergunta que a simulação não pôde dar.

E o número que **não** se moveu: a carga sem tensão do país foi de 742.836 para
742.073, apenas **763 a menos**. A reclassificação mudou o julgamento, e não a
rede. É o que se esperava, e é bom que esteja medido: se esse número tivesse
caído junto, a reclassificação estaria escondendo dado em vez de nomeá-lo.

## Achado 29 — «tensão baixa» era o nome de tudo o que sobrava

**Medido em 03/09/2026** sobre as 4.078 subestações da V28.

O classificador testava `OK` como *tensão adequada **e** perda plausível*, e
tudo o que falhasse caía, no fim da cadeia, em `TENSAO_BAIXA`. Das **262**
assim rotuladas:

| situação real | quantas |
|---|---:|
| só tensão baixa (< 0,90 pu) | 73 |
| **só perda alta, tensão em ordem** | **151** |
| as duas coisas | 38 |

**58% da classe levava um rótulo que não descrevia o problema dela** — e o
rótulo é o que decide para onde alguém vai olhar. Exemplos, todos com tensão
perfeita:

```
CELESCDIS5697  SUB          V=1,000  perda=100,2%
ENEL_RJ383     PCH_PFU      V=1,096  perda=100,0%
CMIG           1924897275   V=1,044  perda=100,0%
```

### A perda do instantâneo é quase o máximo do dia

O instantâneo põe **toda carga no kW declarado**, que é o pico, e a perda
ôhmica cresce com o **quadrado** da corrente enquanto a energia cresce
linearmente. Julgar «perda plausível» por ele é julgar pelo pior instante.

Medido: das **322** subestações com perda ≥ 15% no instantâneo, **96 (30%) têm
perda do dia abaixo de 15%**. Os saltos são grandes:

| base | subestação | instantâneo | dia |
|---|---|---:|---:|
| ENERGISA_R369 | 12147726 | 97,0% | **26,98%** |
| CELESCDIS5697 | RCP | 79,4% | **41,66%** |
| CPFL | ATU | 76,4% | **37,15%** |
| ENERGISA_M405 | 166 | 65,4% | **4,40%** |

O `energia.py` roda **antes** do `validador.py` na ordem das etapas, então o
número do dia já existe quando a classificação acontece — ele simplesmente não
era lido. Agora é, e o do instantâneo fica gravado ao lado, porque **comparar
os dois é o achado**.

### Perda alta sem carga não é perda alta

Subestação sem consumidor recebe da fonte apenas o ferro dos transformadores:
100% do que entra é perdido **por definição**, e não por defeito. Das 13
subestações com perda ≥ 99%, **10 têm zero cargas**. Elas passam a ser
`SEM_CARGA`, que fica **fora** de `ACIONAVEL` — não há o que acionar.

### O efeito, simulado sobre a V28

| causa | V28 | com o achado 29 | delta |
|---|---:|---:|---:|
| `TENSAO_BAIXA` | 262 | 111 | **−151** |
| `PERDA_ALTA` | — | 133 | +133 |
| `SEM_CARGA` | — | 16 | +16 |
| `OK` | 3.073 | 3.075 | **+2** |

**O ganho é de rótulo, e não de aprovação.** Eu esperava que a perda do dia
movesse dezenas de subestações para `OK`; move **duas**. As 96 com perda do dia
abaixo de 15% estão majoritariamente em classes que o classificador decide
*antes* do teste de perda — `REDE_PARCIAL`, `RAMAIS_SOLTOS`,
`REGULADOR_SATURADO`. Continua valendo, porque um rótulo errado manda a pessoa
depurar a coisa errada; mas não é o ganho que eu previa.

### O que este achado NÃO tocou

`REGULADOR_SATURADO`, que eram 98 na V28. O critério dela é *«há regulador e
todos estão no tape máximo»*, medido no mesmo instantâneo, e a suspeita de que
o instantâneo a distorça continua **levantada e não verificada**.

## Achado 30 — o regulador de tensão que aponta para o lado errado

A suspeita levantada no achado 29 (`REGULADOR_SATURADO` medido no mesmo
instantâneo suspeito) foi verificada — e a causa não era o instantâneo.

O `RegControl` é emitido com `winding=2`, o que assume que o `PAC_2` do
registro UNREMT é o lado da carga. **A BDGD não declara direção.** Quando o
`PAC_2` é, na verdade, o lado da fonte, três coisas acontecem juntas:

1. o controle regula uma tensão que ele não pode mudar — a da fonte —, então
   nunca atinge o alvo e **corre o tape até o limite**;
2. o tape no enrolamento da fonte **divide** a tensão do lado da carga, então
   a rede fica pior do que ficaria sem regulador nenhum;
3. a ferramenta reporta `REGULADOR_SATURADO` e **culpa a rede pelo defeito**.

Medido em 03/09/2026, com o tape zerado para separar o efeito da causa:

| subestação | sem regulador | como estava | controle no lado certo |
|---|---:|---:|---:|
| NHER3 (CERNHE6609) | 0,9869 | **0,8984** | **1,0266** |
| IJI (NEOENERGIA47) | 0,9960 | **0,9056** | **1,0194** |

O regulador invertido subtrai cerca de **0,09 pu** da tensão mediana, em
ambos os casos — corrigi-lo devolve mais do que simplesmente desligá-lo.

### O critério certo é a direção do fluxo, e chegar até ele custou duas medidas erradas

- **«qual lado tem maior tensão»** não serve. O regulador tem impedância
  quase nula (`XHL=0,04`, `%R=0,01`), então os dois lados diferem por
  **0,0002 pu** — puro ruído numérico. Uma estatística inteira baseada nisso
  quase foi publicada.
- **«qual lado está mais perto da fonte»** também não serve: o elemento tem
  comprimento zero e `Bus.Distance()` devolve o mesmo valor nos dois lados.

A potência não tem essa ambiguidade. **O terminal por onde a potência entra
no elemento é o lado da fonte**, e isso não depende de tape, de impedância
nem de geometria. Nos dois casos medidos, a direção foi inequívoca: 100% dos
reguladores com fluxo real estavam com o controle no lado da fonte.

### O que este achado não resolve

Regulador em trecho sem fluxo — sem corrente não há direção a medir, e ali a
orientação fica como a BDGD a deixou: declarado, e não adivinhado. Na
Roraima, 70 dos 127 reguladores estão nessa situação.

### A correção

Um passo novo, `etapas/reguladores.py`, roda depois de `ligacao.py` e
**antes** de `ampacidade.py` — a ordem importa porque a correção move a
tensão em ~0,09 pu, e a tensão muda a corrente que a ampacidade mede. Ele
resolve o circuito, mede o fluxo em cada regulador (com o tape neutro, para
não medir o próprio efeito da saturação) e escreve `_REGULADORES.dss` com um
`RegControl.X.winding=N` para cada um que estiver do lado errado. Como as
outras três premissas de modelagem do projeto, o arquivo é sempre escrito
(mesmo vazio) e conta o que fez; apagar o `redirect` no MASTER devolve o
modelo ao que a BDGD declara.

**Ressalva de execução:** a etapa entrou na lista `ETAPAS` de `regerar_v10.py`
mas ficou sem o bloco que a dispara no laço principal — `'ligacao'` seguido
direto de `'ampacidade'`, sem `'reguladores'` no meio. A V29 e a primeira V30
rodaram sem a correção nunca ser aplicada; `REGULADOR_SATURADO` ficou
estagnado em 98 nas duas. Corrigido em 04/09/2026 (commit `79f0014`), depois
de comparar V29 com V30 e ver que o número esperado não caiu.

## Achado 30-B — a CTAT sumiu em nove bases da safra 2025, com a Enel em duas

Medido em 04/09/2026, depois de o chefe do Elder relatar que a CTAT da Enel SP
"veio vazia". Conferido direto nos `.gdb`, não de memória: **728 registros em
2024 viraram 0 em 2025**.

Generalizado nas 97 bases pareadas entre as duas safras:

| código | base | 2024 | 2025 |
|---|---|---:|---:|
| 390 | **Enel SP** | 728 | **0** |
| 383 | **Enel RJ** | 223 | **0** |
| 404 | Energisa MS | 107 | **0** |
| 44 | Equatorial AL | 136 | **0** |
| 32 | Energisa TO | 61 | **0** |
| 2763 | Ceriluz | 4 | **0** |
| 3627 | Cooperluz | 1 | **0** |
| 86 | Eflul | 1 | **0** |
| 7371 | Certel Energia | 1 | **0** |

**Nove bases zeraram, e as duas maiores quedas são as duas bases do grupo
Enel da amostra** — 728 e 223 registros, as maiores magnitudes da tabela.
Padrão, não coincidência isolada: aponta para algo no processo de exportação
da Enel (ou de um fornecedor comum), não para um problema geral do arcabouço
2025.

**Contexto que evita alarme falso:** 50 das 97 bases **nunca** preencheram a
CTAT, nos dois anos — a tabela já era pouco usada. 37 mantiveram CTAT normal
em 2025. Não é uma regressão estrutural do arcabouço; é localizada, com peso
claro no grupo Enel.

**Impacto no conversor, confirmado no log de conversão (V25=2024 contra
V29=2025, mesma base):** `bdgd2dss/transmissao.py:fontes()` prefere a barra de
uma ETT (ponto de conexão real); na falta dela, cai para `CTAT.PAC_INI` — a
cabeceira do circuito de AT; só na falta das duas usa o primário do
transformador como equivalente grosseiro, apagando o trecho de AT entre a
cabeceira real e o trafo. Com a CTAT vazia esse segundo nível nunca é
alcançado:

| | Enel SP: 2024 → 2025 | Enel RJ: 2024 → 2025 |
|---|---:|---:|
| fontes em cabeceira real | 49 → **1** | 0 → 0 |
| fontes equivalentes (grosseiras) | 92 → 141 | 91 → 91 |
| componentes conexas da malha | 837 → 1.353 | 675 → 674 |

**Só a Enel SP perde de verdade.** A Enel RJ já operava com **zero** fontes em
cabeceira real nos dois anos — a CTAT nunca alcançava esse papel lá, então
sumir não piorou nada por esse caminho específico. A malha física (`SSDAT`,
`UNSEAT`, `UNTRAT`) segue em magnitude normal nas duas bases — o que se perde
é o ponto de injeção correto de 48 fontes na Enel SP, não a rede declarada.

**Achado colateral, e maior em escopo: um bug de caminho, não de dado.** O log
também mostrava "de-para: 86 → 0 mnemônicos" — mas esse número é o TAMANHO do
`dados/de_para_mnemonicos.csv` carregado por `etapas/converter.py`, uma
constante nacional, não algo que a CTAT deveria mudar. Rastreado: a
reorganização de 02/09/2026 (commit `a10ab11`) moveu `converter.py` para
`etapas/`, e o código montava o caminho do CSV relativo ao **próprio
diretório** do arquivo — passou a procurar em `etapas/dados/`, que não existe.
`carregar_depara()` aceita caminho ausente e devolve `{}` sem erro, então o
de-para mnemônico→subestação (o segundo dos dois mecanismos de fechamento da
malha de AT) ficou **sempre vazio, em toda base, em toda rodada desde a V26**
— não é efeito da safra 2025 nem específico da Enel. Corrigido em 04/09/2026
(commit `7d96ffc`).

**Não há comunicado oficial sobre a CTAT.** Nem o portal de dados abertos da
ANEEL nem o Manual de Instruções da BDGD publicam changelog campo a campo
entre safras — a única forma de achar isso foi rodar e comparar base por
base.

**Status, separando as duas causas:**

| causa | natureza | resolução |
|---|---|---|
| bug de caminho do de-para | código nosso | **corrigido** em 04/09/2026 (commit `7d96ffc`), travado por teste (`testes/test_depara_caminho.py`) |
| CTAT vazia na Enel SP/RJ 2025 | dado de origem, na exportação da distribuidora | **em aberto** — não é algo que o conversor conserte |

Não existe um jeito de "resolver" a CTAT vazia dentro deste repositório: o
conversor já faz o melhor com o que a base declara (cai para `CTAT.PAC_INI`
e, na falta desse, para o primário do trafo como aproximação grosseira — é
esse fallback que evita o modelo quebrar, não uma correção do dado). Fechar
isso de verdade é ação de fora do código, e o caminho cabível é um destes
dois, não excludentes:

1. **Reportar à Enel** (o achado já nasceu de um relato do chefe do Elder) —
   pedir que a distribuidora confira a exportação 2025 e, se for erro dela,
   reenvie a BDGD com a CTAT preenchida. É o único caminho que corrige o
   dado na fonte.
2. **Registrar como achado de qualidade de dado junto à ANEEL**, já que a
   CTAT é campo do Manual de Instruções da BDGD — a agência não publica
   changelog entre safras, mas recebe reporte de inconsistência via canal
   regulatório. Isso não conserta a base já publicada, mas documenta a
   falha para a próxima safra.

Enquanto nenhum dos dois acontece, a Enel SP 2025 continua rodando —
completa, com relatório — só que com a fidelidade da AT documentada acima
(49 → 1 fontes em cabeceira real) registrada como limitação conhecida do
dado, não do conversor.

## Validação externa e contaminação

A âncora nacional de 7,4% de perda técnica total da ANEEL é apenas um **teste
de reprovação**: como o modelo agregado não contém a BT, ultrapassá-la é
evidência de problema; ficar abaixo não prova acerto. A validação preferida é o
balanço de energia medido por alimentador, com cobertura e classificação de
casos degenerados.

Na V25, **7 das 97 bases** reprovam a âncora, e a contaminação passa de 10% em
16 delas. O alvo de análise é o conjunto de alimentadores contaminantes, não
"consertar" bases inteiras.

**Mas a validação externa por distribuidora virou necessária, e não opcional.**
Os achados 8, 9 e 13 mostraram que o `PERD_*` declarado não fecha nem consigo
mesmo, então o viés de 1,42× entre nossa perda e a dele fica sem juiz. Enquanto
não houver referência de fora, esse número é uma divergência medida — não um
erro atribuído.

## O que vem depois

A fila de trabalho está em `PLANO.md`, com a ordem e o motivo de cada item.
Em resumo: fechar a entrada da safra 2025 sem misturar safras, provar que as
subestações elegíveis do achado 17 rodam de fato, e obter a referência externa.
