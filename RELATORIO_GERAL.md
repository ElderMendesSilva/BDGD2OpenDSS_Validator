# Conversor BDGD → OpenDSS: relatório geral

Enel Distribuição São Paulo — base 2024-12-31, versão V11.
155 subestações · 1.806 alimentadores · 8.258.035 unidades consumidoras.

Documento para acompanhamento de orientação. Registra o que foi feito, o que
foi medido, o que ficou aberto e os erros cometidos no percurso.

---

## 1. Ponto de partida

O conversor existente gerava um modelo por subestação em que **cada
alimentador recebia um transformador próprio ligado a uma fonte infinita** —
1.806 fontes ideais numa concessão de 155 subestações. Consequências: tensão
de cabeceira igual a 1,0 pu por construção, impedância de subtransmissão
invisível, e alimentadores da mesma subestação sem compartilhar barra. Não
havia camada de alta tensão.

**Objetivo definido:** um MASTER único, da subtransmissão para baixo, cobrindo
toda a BDGD exceto o que estiver genuinamente ilhado.

**Restrição permanente:** o conversor deve produzir a rede **a partir da BDGD**.
Dados externos entram como complemento, nunca como dependência.

---

## 2. O que foi construído

| arquivo | função |
|---|---|
| `converter.py` | BDGD → arquivos `.dss`. AT, MT e BT |
| `verifica.py` | sanidade numérica nos **dois motores** do OpenDSS |
| `energia.py` | dia de 96 passos, energia e perdas por alimentador |
| `valida_perdas.py` | cruzamento contra as colunas `PERD_*` da CTMT |
| `validador.py` | métricas elétricas e classificação de causa raiz |
| `analise_com.py` | 7 gráficos pela interface COM, incluindo traçado geográfico |
| `painel.py` | interface gráfica sobre os anteriores |

Módulos novos em `bdgd2dss/`: `tensoes`, `subtransmissao`, `transmissao`,
`malha_at`, `coordenadas`, `diagnostico`.

**Camada de alta tensão.** A BDGD não modela o arranjo interno da subestação.
Foi criado o **vão** — o disjuntor de saída ligando a barra de MT à cabeceira
de cada alimentador. São 1.806 vãos, **0 alimentadores sem ligação**.

A malha de 88 kV não é conexa na base: 844 componentes, 656 dos 729 circuitos
CTAT são ilhas próprias. Fechada parcialmente por âncoras de `UNSEAT.SUB` e
`UNTRAT.SUB`: de 379 para 142 ilhas.

---

## 3. Defeitos encontrados e tratados

Cada um com a medição que o comprova. **É a principal contribuição do
trabalho.**

| # | defeito | medição |
|---|---|---|
| 1 | GD de BT em barra inexistente | **54 de 155** subestações com NaN; 100% das barras afetadas são `PVSystem` sem elemento de rede |
| 2 | Cutoff do ZIPV | mesmo arquivo: **49.857** nós NaN no OpenDSS v11 e **36** no DSS C-API |
| 3 | Barra de MT compartilhada entre níveis de tensão | **1.484 de 1.491** transformadores da DALP com primário fora da tensão da barra |
| 4 | Perdas medidas contra a fonte, não contra a energia injetada | DALP: **305%** contra **9,44%** |
| 5 | GD acima da capacidade do transformador | 232 de 571 barras da DALP |
| 6 | **`PAC` da `UGMT_tab` inexistente na rede** | **0 de 319** válidos; 164 recuperados via `CEG_GD` = **568.084 kW** |
| 7 | `Voltagebases` com valores fase-neutro | DALP: de **2.805** para **21** barras acima de 1,10 pu |
| 8 | Inversores em `pf=0,92` | DEMB e DJAN divergiam com `Vmax` de 1e+69; com `pf=1,0` convergem em 37 iterações |
| 9 | **`POT_INST` não é a potência do gerador** | **1.399 MW** modelados contra **30,5 MW** pela energia; razão mediana 21× na BT e 34× na MT |
| 10 | `TEN_LIN_SE` fase-neutro em campo fase-fase | **492** transformadores |

**Os itens 6 e 9 são os dois lados da mesma tabela.** O ponto de conexão da
geração de média tensão nunca existe onde é declarado, e a potência declarada
não é a do gerador — nas seis unidades acima de 1 MW verificadas, `POT_INST` é
**exatamente igual** ao `CAR_INST` do consumidor. Uma delas declara
15.175 kW com demanda medida de 228 kW.

**O item 2 tem alcance além deste trabalho.** Quem valida modelos pelo
`opendssdirect` pode estar certificando modelos que não abrem no OpenDSS
oficial: o motor permissivo devolve `Converged=True` em 2 iterações sobre uma
solução inteiramente NaN.

---

## 4. Resultado

Verificação subestação a subestação, nos dois motores:

| | V4 | V6 | V7 | V8 | **V9** |
|---|---:|---:|---:|---:|---:|
| sadias nos dois motores | ~0¹ | 132 | 152 | 155 | **155** |
| não convergem | — | 23 | 3 | 0 | **0** |
| com NaN | 54² | 0 | 0 | 0 | **0** |
| tempo de conversão | 75,6 min | 74,3 min | 44,4 min | 53,4 min | **48,2 min** |

¹ amostra de 14 subestações no motor da EPRI: **14 falharam**, incluindo 5
classificadas como `OK` pelo validador antigo.
² no DSS C-API; no motor da EPRI, praticamente todas.

**Simulação diária: 155 de 155 resolvem o dia inteiro** de 96 passos de 15 min.

**Modelo único da concessão:** o `MASTER-GERAL.dss` compila **1.669.937 barras,
4.705.271 nós e 2.352.848 elementos** e converge em **4 iterações sem NaN**. Os
**1.806 medidores** presentes confirmam que todos os alimentadores da concessão
estão no modelo.

A **V9 é a versão de referência**: é a primeira em que os modelos foram gerados
pelo código atual. A V8 tinha sido gerada antes da correção das curvas solares e
por isso carregava irradiância e temperatura erradas — ver a seção 6.

---

## 4b. O conversor em outras cinco distribuidoras

Rodadas em 10 e 11/08/2026, **sem nenhuma alteração de código**:

| base | subestações | sadias nos dois motores | conversão |
|---|---:|---:|---:|
| Roraima Energia (370) | 20 | 19/20 | 1,9 min |
| Light (382) | 94 | 92/94 | 52,9 min |
| Equatorial PA (371) | 119 | 118/119 | 40,1 min |
| CPFL Paulista (63) | 265 | 264/265 | 85,3 min |
| Enel CE (39) | 129 | **129/129** | 21,6 min |
| Cemig-D (4950) | 413 | em processamento | — |

**780 de 787 subestações resolvem**, somando com a Enel SP. As 24 tabelas que o
conversor procura estavam presentes em todas as bases.

Onze achados sobre a BDGD estão registrados em `ACHADOS_GENERALIZACAO.md`. Os
de maior consequência:

- a **camada de AT amarra pelo campo errado**: `UNTRAT.PAC_1` casa com a SSDAT
  em 94,2% na Enel SP e em **0,0%** na Light; `BARR_1`→`BAR.COD_ID` funciona nas
  duas, a ~95%;
- **tensão fase-neutro em campo de fase-fase** aparece em bases independentes —
  7,96 = 13,8/√3 em Roraima, 7,62 = 13,2/√3 na Light — o que sugere trocar a
  tabela de correção por uma regra;
- **tensões de BT legítimas ausentes** da lista montada com o censo da Enel SP:
  216 V e 400 V na Light, 254 V na Equatorial;
- o **clima padrão de São Paulo** era aplicado a qualquer base, em silêncio.

---

## 5. Validação de perdas — o critério antigo e o que o substituiu

Critério declarado antes de medir: ±30% em pelo menos 80% dos alimentadores,
viés mediano abaixo de 15%.

Resultado na V9 (1.492 alimentadores comparáveis, de 1.806):

```
perdas do modelo:  mediana 7,73%
perdas declaradas: mediana 4,39%
razão mediana:     1,88x   |  acima de 2x: 47,7%  |  abaixo de 0,67x: 18,6%
                           |  p10 0,40x           |  p90 5,86x
dentro de +-30%:   18,0% dos alimentadores  (o critério pede 80%)
```

**Não passa.** E a discordância é **estrutural, não um fator de escala**:

| porte do alimentador | n | modelo | declarado | razão |
|---|---:|---:|---:|---:|
| até 5 GWh/ano | 70 | 0,81% | 4,29% | 0,19× |
| 5 a 15 GWh | 238 | 3,20% | 4,06% | 0,83× |
| 15 a 40 GWh | 853 | 8,99% | 4,44% | 2,15× |
| acima de 40 GWh | 331 | 13,51% | 4,70% | 3,25× |

Foram excluídos 272 alimentadores por não terem par ou declaração utilizável,
incluindo os com perda declarada de 0,00% ou 0,01% — casa vazia no cadastro,
que produziam razões de até 105.874×.

### Por que este critério foi abandonado

**`PERD_*` é saída de modelo, não medição.** O Módulo 7 do PRODIST manda a
distribuidora *calcular* a perda técnica por fluxo de potência na própria rede.
Comparar o nosso resultado com ele é cruzamento entre dois modelos — e a
validade da conclusão depende de a referência ser confiável.

Ela não é. Rodando o mesmo cruzamento nas outras bases, a razão vai de **1,88×
na Enel SP a 0,15× na Equatorial PA** — um fator de doze. E há um erro de
método do nosso lado: o modelo roda com `--bt agregado`, sem rede de baixa
tensão, logo **não produz `PERD_B`**; mas a comparação era contra
`PERD_A4 + PERD_B + PERD_A4_B`. Estávamos cobrando uma parcela que o modelo
estruturalmente não gera.

### O critério que o substituiu: balanço de energia MEDIDA

A BDGD traz duas grandezas de **medidor**: `CTMT.ENE_XX`, a energia injetada na
cabeceira, e a energia faturada nas UCs. A diferença é a perda **total** —
técnica mais não técnica. O modelo produz a parcela técnica, que está *contida*
na total. Daí um limite rígido:

> a perda técnica do modelo tem de ser **menor** que a perda total medida.
> Passar dela é fisicamente impossível, sem leitura alternativa.

É o único teste do projeto capaz de reprovar um modelo sozinho. Aplicado às
cinco bases, separando violação real de medição degenerada — alimentador com
faturado ≥ injetado é erro de cadastro, não de física:

| base | alimentadores | **violação real** |
|---|---:|---:|
| **Enel SP** | 1.573 | **458 (29,1%)** |
| CPFL Paulista | 1.537 | 14 (0,9%) |
| Equatorial PA | 619 | 5 (0,8%) |
| Enel CE | 686 | 4 (0,6%) |
| Light | 1.546 | 4 (0,3%) |

**A Enel SP é discrepante por um fator de 40.** As outras quatro passam.

### A causa, rastreada: o condutor 593

Os 458 têm o dobro do comprimento dos demais e **sobrecarga severa 8× maior**
(7,0% contra 0,9% da quilometragem acima de 2× a ampacidade). Controle
decisivo: a mesma medida na Enel CE dá **0,0%** de quilometragem em sobrecarga
— o que descarta artefato do método, já que a Enel CE tem condutor pior (R1
ponderado 5,307 contra 1,642 Ω/km) e passa.

Censo da SEGCON ponderado pela quilometragem de rede:

```
Enel SP — condutor com mais km
   cnd 593    2.993 km (13,5% da rede de MT)   CNOM 31,0 A   R1 8,232 ohm/km
```

Rastreando a sobrecarga em 30 subestações, cobrindo 237 dos 458:

| | |
|---|---:|
| o 593 é, na rede desses alimentadores | 20,4% |
| o 593 é, da quilometragem em sobrecarga | **94,7%** |
| enriquecimento | **4,64×** |
| perda que ocorre em trecho sobrecarregado, atribuível ao 593 | **97,4%** |
| fração do próprio 593 que opera acima da ampacidade | 57,2% |

Os valores do 593 são **internamente coerentes** — 31 A pede mesmo ~8 Ω/km — e
por isso o auto-ajuste do `linecodes` não os toca. O implausível é o **uso**:
2.993 km de rede metropolitana num cabo de 31 A.

### Sensibilidade: quanto do fracasso vem daí

Experimento de uma variável. Os modelos gerados foram copiados inteiros —
topologia, cargas, transformadores, curvas e clima idênticos — e apenas as 35
definições `New LineCode.CND_593_*` foram reescritas com os parâmetros do
CND_1664 (254 A, 0,678 Ω/km, 2.230 km da mesma concessão).

| 382 alimentadores | técnica mediana | violam | não técnica implícita |
|---|---:|---:|---:|
| antes (593 original) | 14,27% | 237 (62,0%) | **−2,99%** |
| depois (593 = 1664) | **4,08%** | **29 (7,6%)** | **+6,91%** |

**208 dos 237 — 87,8% — deixam de violar.** A perda não técnica implícita sai
de **negativa** — o enunciado matemático de "impossível" — para positiva e
plausível. E a técnica mediana de 4,08% fica ao lado dos **4,39% declarados**
na CTMT, contra 14,27% antes.

**A discordância de 1,88× não era propriedade do conversor. Era, em boa parte,
este registro.**

Ressalva de método, que é parte do resultado: o CND_1664 **não é afirmação
sobre qual cabo está em campo**, e os números pós-troca **não devem ser
publicados como se fossem os da Enel SP**. A sensibilidade mede a influência do
dado; não o corrige.

### Subproduto: a perda não técnica implícita

O resíduo do nível 2 — total medida menos técnica do modelo — estima a perda
**comercial** por alimentador a partir de dado público:

| base | não técnica implícita (mediana) |
|---|---:|
| Light (RJ) | **35,23%** |
| Equatorial PA | 22,17% |
| CPFL Paulista | 13,62% |
| Enel CE | 11,46% |
| Enel SP | 5,07% |

É a ordenação publicamente conhecida de perda comercial no Brasil, **reproduzida
sem nenhuma calibração para isso**: o modelo só calcula a parcela técnica, e o
resto sai por subtração contra medição. É a evidência externa mais forte que o
trabalho produziu.

---

## 6. Dados externos utilizados

| origem | uso | situação |
|---|---|---|
| Diagrama de LT (2020) | validação da camada de AT | 1.836 km contra 1.892 km da BDGD, **+3,0%**; contagens de EBC, ESD, ECH, ETSD e ECD batem exatamente |
| Planilhas da ISA | transformadores das subestações da transmissora | de-para de 90 mnemônicos construído à mão |
| Irradiância e temperatura (NASA POWER) | curvas de 96 pontos | **10 dos 12 meses úteis**; novembro e dezembro com irradiância 100% zerada |

Sobre o clima: substituir o perfil sintético pelo medido mudou o fator de
capacidade de 0,286 para **0,2388** e revelou que os 25 °C fixos anteriores
anulavam completamente o derating térmico do módulo. Cada arquivo é **um dia**,
não a média do mês — limitação relevante para a validação anual.

### As curvas solares da V8 estavam erradas — e não era isso

Descoberto ao construir as curvas diárias de geração, em 10/08/2026. A V8 tinha
sido gerada **antes** da correção e carregava:

| | V8 | **V9** |
|---|---|---|
| janela de sol | 06:00 – 11:45 | **05:00 – 18:30** |
| pico | 09:00 | **11:15** |
| equivalente de sol pleno | 3,34 h | **6,22 h** |
| temperatura de célula | 25 °C fixos | **19,3 a 53,0 °C** |
| fator de capacidade | 0,139 | **0,2388** |

Eram 24 valores horários escritos em passo de 15 min: ocupavam 6 h de um dia de
24. Como o `Pmpp` de cada GD é retrocalculado dividindo a energia declarada pelo
fator de capacidade da própria curva, os dois erros se cancelavam na energia
diária — mas a potência de pico saía ~2,3× maior que a correta, concentrada de
manhã.

**Regenerar mudou quase nada**, e isso é o resultado:

| | V8 | V9 |
|---|---:|---:|
| energia injetada no dia | 101,23 GWh | 101,23 GWh |
| perdas do dia | 11,02 GWh (10,88%) | 11,01 GWh (10,87%) |
| razão modelo/declarado | 1,88× | 1,88× |
| dentro de ±30% | 18,0% | 18,0% |

Mudança mediana por alimentador: **0,003 pontos percentuais** em 1.492; o que
mais mudou, 0,35 pp. O motivo aparece no balanço: a geração distribuída é
**0,54 GWh de 101,23 injetados — 0,53% da energia**. Corrigir o horário de meio
por cento não move o agregado.

**Isso levanta uma pergunta nova.** Os contadores do conversor mostram 63.781
PVSystem gerados, 9.379 descartados por potência nula, 23.734 realocados para o
secundário do transformador e apenas **1.130 kW cortados** pelo teto do trafo,
contra 4.289 MW de carga. O descarte não explica o número: ou a BDGD registra
mesmo pouca GD nesta concessão, ou a potência lida por unidade está
subdimensionada. **Decidir exige cruzar com a geração distribuída que a ANEEL
publica para a distribuidora** — verificação que ainda não foi feita, e que é
candidata natural a entrar no auditor.

---

## 7. Otimizações

| | ganho |
|---|---|
| Processamento em lote | leitura filtrada varre a camada inteira: 49 linhas custam os mesmos 13,19 s de 6.927. Lotes de 10 reduzem 155 varreduras a 16 |
| `leitor.no` com `str.translate` | **4,6× mais rápido**, saída idêntica em 3.014 casos testados |
| LineCodes só os referenciados | **215 MB → 2 MB**; cada subestação usa mediana de 152 dos 10.500 |

Verificação: **136 arquivos byte a byte idênticos** entre a versão original e
a otimizada, em 8 subestações. A única diferença são os `LineCodes.dss`.

---

## 8. Em aberto

**Subtensão em 19 subestações — RESOLVIDO em 11/08/2026.** Durante semanas isto
foi tratado como problema próprio, com nove hipóteses levantadas e refutadas
por medição: algoritmo numérico, reguladores, lista de `Voltagebases`,
normalização de `TEN_LIN_SE`, resistência dos condutores contra a ampacidade,
reatância `X1`, incoerência de condutor nos alimentadores afetados, unidade de
comprimento, e a irradiância deslocada.

A décima explicou: **é o condutor 593** (seção 5). Subtensão e perda impossível
eram o mesmo defeito — corrente muito acima da ampacidade num cabo de alta
resistência derruba a tensão e infla a perda pelo mesmo `I²R`. DDIA, DEMB e
DREG estavam nas duas listas.

Sobram **29 alimentadores** que continuam impossíveis depois da troca do
condutor. Esses têm outra causa, ainda não investigada — e agora são um alvo
pequeno e nominal, não um fenômeno difuso.

**Lição de método, e o motivo de registrar as nove.** Todas as nove hipóteses
eram sobre *o modelo*. A causa estava *no dado*. O que quebrou o impasse não foi
uma hipótese melhor: foi trocar a referência de validação — de `PERD_*`, que é
saída de modelo, para energia medida, que dá um limite físico impossível de
contornar. **A pergunta certa valeu mais que nove tentativas de resposta.**

**Falha de trajetória no modo diário.** A sequência degrada e trava — DABR no
passo 72, DPIP no 44 — e não se recupera. Não é a rede: compilando do zero e
saltando direto para o passo 72, converge em 3 iterações. Contornado
recompilando ao falhar, o que também ficou mais rápido. A causa não foi
identificada, e **corrigir as curvas solares não a eliminou**: as recompilações
caíram de 416 para 392 no conjunto das 155 (2,68 → 2,53 por subestação), uma
redução de 6% que não sustenta a hipótese de que a irradiância deslocada era a
origem.

**Modelo único da concessão — resolvido.** Ficou registrado como `Out of
memory` desde uma tentativa antiga. Não é mais verdade: o `MASTER-GERAL.dss`
compila **1.669.937 barras, 4.705.271 nós e 2.352.848 elementos** e converge em
**4 iterações sem nenhum NaN**. A concessão inteira roda num modelo só.

*Ressalva:* esse teste foi feito no `MASTER-GERAL` da **V8**. O da V9 foi
gerado mas ainda não foi resolvido. Duas medidas do instantâneo da V8 merecem
ser refeitas na V9 antes de qualquer uso: `V_max` de 1,196 pu e fator de
potência de 0,79 na fonte, contra 0,92 modelado nas cargas. A explicação mais
provável é que o modo `snap` ignora a curva diária e usa `irradiance=1.0` — ou
seja, toda a GD a pleno, com o `Pmpp` inflado da V8.

O que quebrava era o desenho, não a rede: o `matplotlib` expande o vetor de
larguras de linha em uma especificação de tracejado por segmento, e 2,35
milhões delas estouram a memória antes do primeiro pixel. Corrigido
quantizando a espessura em seis faixas — cada coleção recebe um escalar — e
recortando a figura nos 300 mil trechos de maior corrente, o que é dito na
legenda e no terminal. Medido: 2,4 milhões de trechos desenham em 5,4 s.

**Premissas sem respaldo na base:** `Xhl` adotado por faixa de potência, R0/X0
como múltiplo de R1/X1, ajuste de regulador genérico (`vreg`, banda, kVA),
fator de potência das cargas em 0,92.

---

## 9. Erros cometidos no percurso

Registrados porque afetam a confiança nos números.

**Afirmações confiantes e incorretas, todas depois refutadas por medição:**
infactibilidade da rede nos extremos do dia (a rede converge com carga
dobrada); a falha diária ser do laço de simulação (o `Solve` único do próprio
motor falha igual); a lista de `Voltagebases` causar subtensão (afeta o pu, não
a física); o declarado ser valor típico rateado (varia, CV 46,7%); GD
entregando 8,5× o `Pmpp` como defeito do inversor (era estado já divergido); a
irradiância deslocada causar a falha do modo diário (corrigi-la reduziu as
recompilações em 6%, de 416 para 392); a incoerência R1×ampacidade distinguir
os alimentadores defeituosos (razão ponderada 1,48× contra 1,49× nos sadios).

**Diagnósticos intermediários que pareciam definitivos e não eram.** Vale
registrar porque cada um foi escrito com convicção:

1. *"a subtensão da DPIP é caso isolado"* — eram 19 subestações;
2. *"o viés das perdas troca de sinal entre distribuidoras"* (10/08) —
   verdadeiro como observação, mas confundia defeito localizado da Enel SP com
   erro de método na comparação;
3. **a resposta** (11/08): defeito de dado localizado, o condutor 593.

**Erros de medição:** unidade de comprimento do OpenDSS — **duas vezes**, a
segunda em 11/08, quando li `Lines.Length()` como quilômetros e anunciei
trechos de 120 km que eram de 120 m; indexação de terminais; interface `Lines`
não acompanhando `SetActiveElement`; caixa no nome do medidor; denominador de
perdas sem a GD interna à zona; e um nome de API inexistente.

**Erro de comparação, que invalidou o critério original:** o modelo roda com
`--bt agregado`, sem rede de baixa tensão, e portanto não produz `PERD_B`; a
validação comparava contra `PERD_A4 + PERD_B + PERD_A4_B`. Isso cobrava do
modelo uma parcela que ele estruturalmente não gera, e contribuiu para a
razão discrepante em todas as bases.

**Erros de processo:** edição do conversor durante execução, que corrompeu
duas rodadas de 2 h — o `converter.py` se relança por subestação e relê o
fonte; e remoção da pasta de saída sob um processo ainda ativo.

**Consequência:** os números deste documento não foram verificados de forma
independente. Verificação escrita por quem escreveu o original tem valor
limitado — um erro de premissa tende a se repetir. **Antes de qualquer
submissão, os valores centrais precisam ser reproduzidos por terceiro.**

---

## 10. Encaminhamento sugerido

O trabalho está mais perto do limite do dado do que do limite do código.

**Recorte com maior valor:** a BDGD como fonte para simulação, não o conversor.
Conversores BDGD→OpenDSS já existem; auditoria sistemática da base, não. O
artefato publicável seria um **auditor** — recebe qualquer `.gdb` e devolve o
relatório de inconsistências com a consequência elétrica de cada classe.

**Para generalizar:** rodar o catálogo em cinco ou seis distribuidoras de
grupos, portes e regiões diferentes. É consulta, não conversão — dias, não
meses. Se os defeitos se repetem, o achado é sobre o formato; se cada uma tem
os seus, o achado é a ausência de padronização efetiva de preenchimento.
Ambos são resultados.

**Pendências para publicação:** verificação independente dos números, código
em repositório público, revisão da literatura internacional de qualidade de
dado em redes de distribuição, e resolução ou declaração formal da subtensão
da DPIP.
