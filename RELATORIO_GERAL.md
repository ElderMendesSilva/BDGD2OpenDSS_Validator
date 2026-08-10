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

## 5. Validação de perdas — reprova o critério

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

O declarado é praticamente plano com o porte; o do modelo escala com ele —
que é o comportamento fisicamente esperado, mais carga sobre a mesma rede.
O declarado **varia** entre alimentadores (coeficiente de variação 46,7%, 620
valores distintos em 1.496), então não é valor típico rateado: varia por algo
que não é o tamanho.

**Esta é a pergunta em aberto mais interessante do trabalho.** Duas leituras
possíveis, ainda não separadas: o modelo superestima perda em alimentador
grande por premissa de impedância, ou o cálculo regulatório não captura a
dependência com o carregamento. Distinguir exige olhar a metodologia do
Módulo 7 aplicada pela distribuidora.

Foram excluídos 272 alimentadores por não terem par ou declaração utilizável,
incluindo os com perda declarada de 0,00% ou 0,01% — casa vazia no cadastro,
que produziam razões de até 105.874×.

**Natureza da referência:** `PERD_*` é saída do cálculo da própria
distribuidora, conforme o Módulo 7 do PRODIST. Isto é **cruzamento entre dois
modelos**, não validação contra medição. A grandeza medida disponível é
`CTMT.ENE_XX` menos a soma das UCs, que dá a perda **total** — técnica mais
não técnica — e portanto não é cobrável do modelo. Verificado na DABR:
13.625,6 contra 10.821,5 MWh, 20,58%.

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

**Subtensão em 19 subestações.** Não é caso isolado da DPIP: o `validador`
classifica 131 modelos como OK, 19 como `TENSAO_BAIXA` acionável, 3 com
regulador saturado e 2 com rede extensa. As 19 têm `Vmin` de 0,196 a 0,75 pu,
30 a 65% das barras fora de faixa e — 18 delas — nenhum regulador.

O cruzamento com as perdas mostra que são um grupo distinto, não um extremo do
mesmo comportamento:

| grupo | alimentadores | modelo | declarado | razão |
|---|---:|---:|---:|---:|
| nas 19 com subtensão | 206 | 17,44% | 4,77% | **4,08×** |
| nas outras 136 | 1.286 | 6,90% | 4,35% | 1,65× |

Perda de 17% com 8 km por alimentador (DPIP, DDIA, DPEN) não é rede extensa.

**Seis hipóteses refutadas por medição**, todas: algoritmo numérico (Newton e
500 iterações não mudam nada), reguladores, lista de `Voltagebases`,
normalização de `TEN_LIN_SE`, resistência dos condutores (`R1` declarado contra
a ampacidade: mediana 1,19×, só 6 de 101 acima de 2×) e — verificado por
último — a **reatância**: nos LineCodes efetivamente usados, `X1` mediano fica
entre 0,30 e 0,42 Ω/km, sem zeros e sem valores acima de 1, e a razão `X1/R1`
é idêntica entre doentes e sadias (mediana 0,68 nas duas). A impedância não
separa os dois grupos. Restam alocação de carga, agregação de BT e topologia.

**Consertar as 19 não valida o modelo.** Excluindo-as inteiras, a razão mediana
cai de 1,88× para 1,65× e o critério continua reprovando — 20,0% dos
alimentadores dentro de ±30%, contra 18,0% com elas. São dois problemas
distintos: um defeito localizado e um viés sistemático.

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
entregando 8,5× o `Pmpp` como defeito do inversor (era estado já divergido).

**Erros de medição:** unidade de comprimento do OpenDSS, indexação de
terminais, interface `Lines` não acompanhando `SetActiveElement`, caixa no
nome do medidor, denominador de perdas sem a GD interna à zona, e um nome de
API inexistente.

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
