# Achados de generalização — síntese

**Corte:** 27/08/2026. Este arquivo conserva conclusões, evidências e ações.
O histórico de hipóteses, experimentos intermediários e números de cada rodada
permanece no Git.

## O que o projeto demonstrou

- A BDGD padroniza o **formato**, não a qualidade nem a semântica local do
  preenchimento. O conversor precisa inferir e auditar por concessão.
- Validar somente compilação, convergência ou ausência de `NaN` não basta:
  redes fisicamente implausíveis podem convergir. A validação deve incluir
  tensão, ampacidade, cobertura e balanço de energia.
- O modelo agregado de BT é útil para estudos de MT; `--bt completo` ainda não
  é uma base confiável para perdas ou otimização na baixa tensão.
- A comparação agregada é frágil quando poucos alimentadores implausíveis
  dominam a perda. Sempre publicar agregado, mediana, corte de sensibilidade e
  a parcela contaminada.

## Correções incorporadas

| Tema | Regra consolidada |
|---|---|
| Tensões | Usar `PAC_INI`, `TEN_OPE` e conciliar a tensão declarada com o parque de equipamentos; códigos desconhecidos são relatados, nunca mascarados. |
| AT e fontes | A malha de AT, fontes e barras são modeladas por topologia e nível de tensão; evitar uma fonte fixa de 88 kV e nomes de pátio tratados como barra. |
| Transformadores | Respeitar fases reais dos enrolamentos; um primário bifásico não pode ser escrito como trifásico. |
| Chaves e reguladores | Emitir elementos conectados à rede, preservar o estado aberto e manter reguladores entre chaves no modelo. |
| Leitura e escala | Ler tabelas grandes por fatias/lotes, tratar `dtype` heterogêneo e rejeitar comprimentos nulos antes de gerar DSS. |
| Execução | Ordenar subestações maiores primeiro, retomar etapas concluídas e manter a saída determinística entre laptop e cluster. |

## Limitações e fatos de dado relevantes

- **Enel SP:** o condutor 593 e, em geral, incoerência entre condutor e uso
  explicam grande parte da perda impossível. É um problema de cadastro/uso que
  deve ser marcado, não escondido no agregado.
- **Cemig-D:** há diferença importante ainda não explicada; o desvio não deve
  ser atribuído ao conversor sem evidência adicional.
- **CPFL e Equatorial:** códigos de tensão e redes de níveis misturados podem
  criar alimentadores com tensão incorreta. A correção exige evidência do
  cadastro, não substituição automática por um padrão.
- **Premissa de ligação:** pode energizar uma componente, mas só é aceitável se
  não introduzir perda, corrente ou tensão implausíveis. Convergir não é prova
  de validade física.
- **BT completa:** continua em diagnóstico, mas o diagnóstico mudou de lugar —
  ver o achado 3 abaixo. Funciona em bases pequenas; falha por convergência
  acima de ~1 milhão de UCs. Não usar seus números de perda, cobertura ou
  tensão como resultado de produção.

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
se defende pela física, não pelos dados — e isso precisa de estudo de
sensibilidade antes de virar número de artigo.

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
fragmentação por recorte de CTMT. É o mesmo mecanismo, agora medido em 370
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
acima de 100% — isto é, a perda técnica que o modelo calcula excede a perda
TOTAL que a medição registra. Como a técnica é uma parcela da total, isso é
impossível por definição, e vale para 47 das 97 bases.

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
suspeitos. Eles são alimentadores **longos, de condutor mais fino e com metade
da densidade de carga** — rurais e extensos.

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
da ANEEL é 7,4%. Isso não depende de acreditar no nosso modelo: é implausível
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
demais, e **4 subestações contra 20**. São as pequenas — cooperativas e permis-
sionárias, que provavelmente preenchem o campo com uma referência regulatória
em vez de um cálculo próprio.

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

## Validação externa e contaminação

A âncora nacional de 7,4% de perda técnica total da ANEEL é apenas um teste de
reprovação: como o modelo agregado não contém a BT, ultrapassá-la é evidência
de problema; ficar abaixo não prova acerto. A validação preferida é o balanço
de energia medido por alimentador, acompanhado da cobertura e da classificação
de casos degenerados/implausíveis.

Na V22, as sete bases que reprovavam a âncora ficaram entre **2,64% e 8,93%**
após retirar alimentadores implausíveis. A conclusão é que o alvo de análise é
o conjunto de alimentadores contaminantes, não “consertar” bases inteiras.

## Próxima investigação técnica

1. Importar e analisar `resultados/v22/` localmente.
2. Explicar os alimentadores implausíveis apontados nos CSVs de violação.
3. Medir as 21 bases pequenas que fecharam ciclo pela primeira vez.
4. Corrigir a BT completa antes de usar qualquer métrica de baixa tensão.
5. Obter referência externa por distribuidora para completar a validação.
