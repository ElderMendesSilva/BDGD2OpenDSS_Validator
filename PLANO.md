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
| `MASTER-GERAL` (concessão inteira) | **1.669.937 barras, 4 iterações, sem NaN** ⚠️ |

⚠️ **Este número não é reproduzível nesta máquina, e eu o tratei como linha de
base sem conferir.** Medido em 11/08/2026: o `MASTER-GERAL` da Enel SP
(2.391.177 elementos) **estoura a memória do OpenDSS** — com o código novo *e*
com o da V9, que falha na mesma carga, num arquivo byte a byte idêntico. Ver
achado 13.
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
| Equatorial PA (371) | 119 | 118/119 | 40,1 min |
| CPFL Paulista (63) | 265 | 264/265 | 85,3 min |
| Enel CE (39) | 129 | **129/129** | 21,6 min |
| Cemig-D (4950) | 413 | em andamento | — |

**O conversor rodou em todas na primeira tentativa, sem alteração de código** —
780 de 787 subestações resolvem, somando com a Enel SP.

Onze achados registrados. Os dois de maior consequência:

- **nº 7** — a camada de AT amarra por `UNTRAT.PAC_1`, que casa a 94% na Enel SP
  e a **0% na Light**; a chave que funciona nas duas (~95%) é
  `BARR_1`→`BAR.COD_ID`. A parte que exigiu mais engenharia reversa é a que não
  generaliza.
- **nº 11** — o condutor **593** da SEGCON da Enel SP (31 A, 8,232 Ω/km,
  **13,5% de toda a rede de MT**) responde por 94,7% da quilometragem em
  sobrecarga e 97,4% da perda ali. Trocá-lo por um condutor plausível da própria
  base resolve **87,8%** dos alimentadores fisicamente impossíveis.

Falta a Cemig-D fechar. A conversão dela caiu na madrugada por bug de dtype no
leitor (achado 8b), foi corrigida, e **retomou de onde parou** — as 265
subestações já feitas foram aproveitadas.

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

### 4. Transformar as quebras em testes — ✅ FEITO em 11/08/2026

As falhas do passo 3 **são** os casos de teste, com dados reais de entrada.
Escrever a suíte antes de ver uma segunda base é testar o que se imagina que
varia, não o que varia.

**90 testes** rodando em 1,1 s com o `unittest` da biblioteca padrão, sem
dependência de teste a instalar, e uma **BDGD mínima de 127 KB** —
FileGeodatabase de verdade, gerada por `pyogrio.raw.write`, lida pelo caminho
de produção inclusive no `ler_filtrado`.

```bash
python -m unittest discover -s testes -t testes -v
```

Cada achado do passo 3 tem teste, e a tabela é o mapa entre um e outro:

| achado | arquivo | o que ficou fixado |
|---|---|---|
| 1 — trafo de barra duplicado | `test_subtransmissao.py` | nome vindo de `TRB_{sub}_{kv}` colide com duas barras de origem |
| 2, 5 — código de tensão e `TEN_LIN_SE` | `test_tensoes.py`, `test_transformadores.py` | `7,96` e `7,62` são fase-neutro; a correção tem de virar regra, não tabela |
| 7 — ancoragem da AT | `test_subtransmissao.py` | mesma SSDAT, só muda o campo de ligação: por `PAC` o trafo cai fora da malha; `BARR_1` é lido e **nunca consultado** |
| 8b — `pertence` e dtype | `test_pertence.py` | promoção de largura sem truncar |
| 9 — cruzamento com o `PERD_*` | `test_valida_perdas.py` | a parcela de BT **dobra** o que se cobra de um modelo `--bt agregado`, e o fator varia por alimentador |
| 10 — validação por medição | `test_valida_balanco.py` | limite físico, resíduo, cobertura, e a **medição degenerada** que hoje se confunde com defeito de modelo |
| 11 — condutor 593 | `test_linecodes.py` | o par (R1, CNOM) é coerente, fica a 1,6× do previsto contra limiar de 7,4×, e o ajuste **não enxerga quilometragem** |
| — caminho do OpenDSS | `test_opendss.py` | os LineCodes gerados compilam; perda medida = 3·R·I² com R = r1 × km; `Lines.Length()` devolve **metros** |

Defeito conhecido entra como `@unittest.expectedFailure`, não como teste
vermelho. São **9**, e cada um chama a API que o passo 5 precisa criar, com o
número que ela precisa devolver — quando a correção chegar, o teste só fica
verde se estiver certa. Conferido um a um que falham pelo motivo declarado
(`AssertionError` de intersecção vazia, `TypeError` de argumento inexistente,
`KeyError` de campo ausente, `AttributeError` de função ausente) e não por
acidente de montagem — erro que já aconteceu uma vez nesta suíte.

O `test_opendss.py` fixa a armadilha que me enganou **duas vezes**: ler
`Lines.Length()` e supor quilômetros. A perda medida bate com a analítica na
terceira casa (315,260 W), e a leitura errada daria 315.260 W — fator mil, com
resultado ainda plausível à primeira vista.

### 5. Tirar da Enel SP o que hoje é tabela fixa

Derivar da base sendo convertida, no padrão que o `linecodes._ajuste` já usa —
ele calibra a relação R1×CNOM na própria base a cada execução, em vez de tabela
externa. Aplicar o mesmo ao censo de `TEN_LIN_SE` (tensões de BT) e ao de
`TEN_NOM` (códigos de tensão).

**Item novo, vindo do achado 11 — coerência entre ampacidade e corrente.**

O `linecodes._ajuste` confere R1 contra CNOM *dentro da SEGCON*. Isso não pega o
condutor 593: 31 A com 8,2 Ω/km é um par internamente coerente. O que estava
errado era o **uso** — 13,5% de uma rede metropolitana num cabo de 31 A —, e
isso só aparece **depois de resolver o fluxo**, comparando a corrente calculada
com a ampacidade declarada.

Vira rotina, no conversor e no auditor:

- por condutor: fração da quilometragem dele que opera acima da ampacidade;
- por alimentador: fração do km em sobrecarga, e quanto da perda ocorre ali;
- alerta quando um único condutor concentra a sobrecarga — foi a assinatura que
  denunciou o 593 (enriquecimento 4,64×, 94,7% da sobrecarga).

Referência de calibração medida: **Enel CE tem 0,0%** de quilometragem em
sobrecarga; Enel SP tem 8,5% a 12,8%. O limiar não precisa ser arbitrado — sai
da comparação entre bases.

#### Os critérios de aceitação estavam escritos — e o bloco A já é verde

O passo 4 deixou `expectedFailure` que são a especificação executável deste
passo. Implementar é fazer cada um ficar verde, e nenhum passa só por existir:
todos conferem número.

**Bloco A — ✅ FEITO em 11/08/2026.** Só ferramenta de análise; nenhum modelo
precisou ser regerado.

| o que era pedido | estado |
|---|---|
| `linecodes.coerencia_de_uso` + `concentracao` | ✅ enriquecimento por condutor; devolve `None` quando não há sobrecarga, para o alerta não disparar numa base sadia |
| `valida_perdas.declarado(gdb, parcelas=[...])` | ✅ e a composição sai do campo `bt` do `relatorio_rede.json`, com as três candidatas **medidas** e reportadas |
| `medida_degenerada` / `viola_de_verdade` em `valida_balanco` | ✅ reproduz a tabela do achado 10 a partir do repositório, sem script externo |
| nome do trafo de barra (achado 1) | ✅ sai da barra derivada — precisa de regeração para valer em Roraima |

**108 testes, falhas esperadas de 9 para 5.** O resultado de maior
consequência está no achado 9: a composição `PERD_A4 + PERD_B + PERD_A4_B`
que estava em uso é a **pior das três em cinco das seis bases**, e corrigi-la
leva Light, Equatorial PA e CPFL de 0,19×/0,14×/0,35× para 2,07×/1,36×/1,26×.

**Bloco B — ✅ FEITO em 11/08/2026.** Altera a saída do conversor; a validação
completa depende da regeração das sete bases, agendada para 12/08 às 01:30
(`regerar_v10.py`).

| o que era pedido | estado |
|---|---|
| âncora de AT que chegue na malha | ✅ medida nas sete antes de decidir; ver abaixo |
| `tensoes.bases()` derivado da própria base | ✅ `censo_bt` lê a base em conversão; a lista da Enel SP fica só como piso |
| `tensoes.TENSAO_KV` derivado da própria base | ❌ **não é derivável** — ver abaixo |
| `_FN_PARA_FF` virar regra (÷√3) | ✅ com duas tolerâncias, porque 380/√3 e 190/√3 exigem decisões opostas à mesma distância relativa |
| clima por região | ✅ `BASE.DIST` contra `--clima-dist`; recusa e cai no sintético |
| `KM_ALIM_ALTO` e a mediana da mensagem | ✅ `diagnostico.referencia_de` mede a base |

**130 testes, zero falhas esperadas.** Todo defeito registrado no
levantamento está corrigido.

#### A âncora de AT: a medição refutou a correção proposta

Antes de mexer, medi as três candidatas nas **sete** bases
(`diagnosticos/at_cobertura.py`). O `PAC_1` em uso cobre 99,5% na Enel SP e
**0,0% nas outras seis** — não é "funciona menos bem", é não funciona. E a
candidata que o achado 7 registrava, `BARR_1`, também não resolve: casa com
`BAR.COD_ID` de 86% a 100%, mas o `BAR.PAC` daquela barra não está na SSDAT
fora da Enel SP. Identifica a barra e não chega à rede.

O que generaliza é `UNTRAT.SUB` em `UNSEAT.SUB`: 75,9% no pior caso, mediana
98,2%. **O teste de aceitação tinha sido escrito pelo resultado e não pelo
mecanismo — foi o que impediu que a correção errada ficasse verde.**

#### O que não foi feito, e por quê

`tensoes.TENSAO_KV` — o mapa código→kV, com 6 dos 11 códigos sem valor — **não
é derivável da BDGD**. Não existe, em nenhuma tabela, um kV que permita
resolver o código: `CTMT.TEN_NOM`, `BAR.TEN_NOM` e `EQTRAT.TEN_PRI/TEN_SEC`
são todos códigos do mesmo domínio. Isso precisa da tabela de domínio da
ANEEL. Fingir derivar seria inventar.

O que foi feito no lugar: o conversor avisa uma vez por código e **grava a
lista no `relatorio_rede.json`**, para o auditor reportar quantos
alimentadores usaram o padrão em vez do valor real.

### 5b. Ligar o clima por coordenada — PRONTO, esperando a regeração

`bdgd2dss/clima.py` está escrito e testado (22 testes, nenhum tocando a rede),
e **não está ligado no conversor de propósito**: trocar o caminho do clima
antes do ciclo agendado desperdiçaria a noite.

O que ele faz: tira o centroide da rede da **própria geometria da BDGD** (que
é SIRGAS 2000, geográfico — lon/lat sem reprojeção), consulta a NASA POWER e
grava um cache com procedência. A conversão lê o cache e **nunca toca a
rede** — sem isso o modelo deixaria de ser reproduzível offline e passaria a
depender de um serviço externo continuar no ar.

Por que importa, medido (achado 4):

> O conversor aplicava **19,3 a 26,1 °C** em Roraima, que opera de **26,8 a
> 39,1 °C**. As duas faixas não têm um grau em comum. E o erro era de
> temperatura, não de irradiância — a de Roraima é só 5% maior que a de São
> Paulo, porque janeiro é estação chuvosa perto do equador.

Para ligar, depois da regeração:

1. `carregar_clima` ganha a cadeia **medido local → cache baixado → sintético**;
2. um passo explícito baixa o cache das sete bases (`python -m bdgd2dss.clima <gdb>`);
3. os caches vão para o repositório — são pequenos e carregam a procedência;
4. **nova regeração**, porque mudar o clima muda `Curvas.dss` e o `Pmpp` da GD.

O impacto nos números de perda e tensão é pequeno (GD é 0,53% da energia
injetada). O ganho é de **honestidade metodológica** e de destravar estudo
focado em GD, que hoje não dá para fazer com o clima errado.

### 6. As outras cinco, depois oficializar

Tag, repositório público, modelos gerados pelo código publicado.

*Só depois de sobreviver a duas bases no mínimo.*

---

## O que faria mudar de rota

- **Se em um dia não der para converter nenhuma subestação da segunda base**, o
  problema é maior do que "três blocos hardcoded" e o plano é reavaliado antes
  do passo 4.
- ~~**Se o viés de 1,65× aparecer também na segunda base**, ele deixa de ser bug
  e passa a ser o objeto do artigo.~~
- ~~**Se o viés for exclusivo da Enel SP**, é defeito nosso.~~

~~**RESPONDIDO em 10/08/2026:** o viés troca de sinal, e a contradição fica
dentro da BDGD.~~ *Leitura intermediária, superada em 11/08.*

## RESPONDIDO em 11/08/2026 — e a resposta é a terceira, não as duas previstas

O caminho até aqui passou por três leituras, e vale registrar as duas primeiras
porque cada uma parecia definitiva quando foi escrita:

1. *"o viés é da Enel SP ou é sistemático"* — as duas hipóteses do plano
   original;
2. *"o viés troca de sinal entre bases"* (10/08) — verdadeiro como observação,
   mas confundia dois fenômenos;
3. **a resposta:** a Enel SP tem um **defeito de dado localizado**, e as outras
   bases passam no teste físico.

O que a mediu foi o `valida_balanco.py`, que compara a perda técnica do modelo
com a perda **total medida** (`ENE_XX` injetada menos energia faturada). É o
único teste do projeto capaz de reprovar sozinho, porque a referência é
medidor, não saída de modelo.

| base | violação real do limite físico |
|---|---:|
| **Enel SP** | **29,1%** |
| CPFL Paulista | 0,9% |
| Equatorial PA | 0,8% |
| Enel CE | 0,6% |
| Light | 0,3% |

Rastreado até a causa (achado 11): o condutor **593** da SEGCON da Enel SP.
Sensibilidade de uma variável: trocá-lo resolve **87,8%** dos alimentadores
impossíveis, e a perda técnica mediana cai de 14,27% para 4,08% — ao lado dos
4,39% declarados na CTMT.

### Consequências para o plano

- **A discordância com o `PERD_*` não era do conversor.** Era, em boa parte,
  este registro. O passo 5 ganha o item de coerência ampacidade × corrente.
- **As 19 subestações e os 458 alimentadores deixam de ser dois problemas** —
  eram o mesmo, e está resolvido em 87,8%.
- **Sobram 29 alimentadores** impossíveis por outra causa. Trabalho concreto e
  pequeno, para depois do passo 5.
- ~~**A comparação contra o `PERD_*` precisa de correção de método**~~ —
  **FEITO em 11/08/2026.** Medido em vez de arbitrado: `PERD_A4` sozinho é a
  melhor composição em quatro das seis bases, `PERD_A4 + PERD_A4_B` na Enel
  CE, e a soma das três só na Enel SP — que é a base com o defeito do 593.
  Denominador maior disfarça modelo inflado, e a composição que estava em uso
  era, sem que ninguém tivesse escolhido assim, a que mais escondia o defeito
  que o projeto encontrou por outro caminho. Detalhe no achado 9.

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
