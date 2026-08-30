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

**Isso resolve a ambiguidade do achado 6 a favor do modelo.** A pergunta era se
o modelo superestima ou a medição subestima. Uma perda técnica de 8,66% num
alimentador de 349 km com R1 = 1,31 Ω/km não é superestimativa: é o que a
física manda. O modelo está calculando certo.

**A consequência inverte a leitura da ferramenta.** Esses 366 casos não são
falsos positivos do validador — são alimentadores onde a **energia medida ou
declarada é inconsistente com a física da rede declarada**. A distribuidora
declara um comprimento e um condutor que implicam certa perda, e reporta uma
energia que implica perda menor. As duas afirmações são dela, e não fecham.

**É esse o produto do auditor**, e é um achado mais forte que "o modelo diverge
da medição": ele aponta contradição interna no dado regulatório, medida contra
os próprios atributos que a BDGD publica.

**O que falta:** repetir em outras bases para saber se o padrão é da Cemig ou
nacional. O comando já existe — trocar `BASE=` no `submeter_perfil.sh`.

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
