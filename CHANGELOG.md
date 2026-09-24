# Histórico de versões

Este arquivo registra **o que cada versão garante e o que ela não faz**.
Limitação escrita é limitação; limitação descoberta pelo usuário é defeito.

O detalhe de cada mudança está no Git; os achados numerados, com método e
número, estão em [docs/ACHADOS_GENERALIZACAO.md](docs/ACHADOS_GENERALIZACAO.md).

## 1.1.0 — em aberto (safra 2025-12-31)

### O monofásico que já declara a tensão de linha (achado 80)

O voto do parque (achado 49) multiplicava por √3 o `TEN_PRI` de todo
monofásico; as Energisa declaram nele a tensão de linha, e 59,8 kV saía em
centenas de alimentadores. Agora √3 só vale se levar a um nível de linha que os
trafos de dois ou três nós da base declaram. Energisa TO, cinco subestações:
carga morta de 42% para 6%, perda de ~1,8% para 2-4%. Equatorial PA, Cosern e
cooperativas: nenhum alimentador muda.

O que NAO faz: não resolve a GD que acorda junto — três das cinco perdem
passos do meio-dia sem convergir; o corte do inversor por sobretensão fica
para depois.

### Barra de origem de transformador de barra sem fonte (achado 79)

A etapa `ligacao.py` põe uma fonte na barra de origem de um `TRB_*` que está
MORTA depois de resolver o fluxo, antes de decidir os elos. Copel 71700: 4.581
cargas mortas para 66; Energisa MT 92: 2.135 para 62. Toda variante do
pré-voo passa a anunciar o 79 (a BDGD mínima é um caso misto); o único número
que muda é a perda da `trafo_de_consumidor`, de 16,99% para 16,98%.

O que NAO faz: não corrige a base de tensão das barras que estavam mortas no
`CalcVoltagebases` (afeta a leitura em pu, não a perda).

Os elos da premissa de ligação passam a se chamar `VAO_EXTRA_<SE>_<n>`: o
`MASTER-GERAL` carrega o `_LIGACAO.dss` de todas as subestações, e
`VAO_EXTRA_1` repetido era #266 nele.

### Quatro defeitos que a V39 escondia (achados 75 a 78)

Varredura dos resultados da V39 antes da V40, 24/09/2026. Nove bases saíram
sem comparação com a ANEEL, e duas delas — Cosern e Elektro — tinham perda de
MT acima da perda regulatória do sistema inteiro.

- **75** — sem alimentador comparável, o `valida_perdas` morria e levava junto
  a âncora da ANEEL. Agora a âncora sai sempre, e o arquivo diz sobre quais
  alimentadores (`comparacao_por_alimentador`, `base_da_ancora`).
- **76** — R1 de preenchimento na `SEGCON` (Cosern: 2,179 Ω/km em 545 de 598
  condutores). Com um valor em mais de metade da tabela e o ajuste plano, o
  valor é trocado pelo ajuste do resto da tabela ou por uma referência de
  sete bases. O Módulo 7 usa a mesma calibração.
- **77** — chave com o `COD_ID` de um trecho de MT vira `CH_<cod>` (Cosern:
  93 códigos; CCO e MCV não compilavam).
- **78** — ponto isolado zerado na curva de carga vira a média dos vizinhos
  (Elektro: `POT_96 = 0` em todas as curvas; 84 de 153 subestações perdiam o
  dia no passo 95).

Na Cosern, quatro subestações medidas: NEO de 7,90% para 1,86%, APD de
16,95% para 5,26%, CCO e MCV passam a compilar, as quatro com 96/96 passos.
Três variantes novas na fixture e no pré-voo: `r1_preenchimento`,
`chave_com_codigo_de_trecho`, `curva_com_ponto_zerado`; as variantes antigas
não mudaram um número.

O que NAO faz: não conserta a declaração de perda por alimentador da Cosern
(ela é ~1000× menor que o plausível — provavelmente MWh sobre kWh, mas isso
seria inferência); a comparação por alimentador dessas bases continua
inexistente, e é dito.

### Laco fechado atraves de transformador (achado 70)

Nova premissa `_LACOS.dss`, preenchida pela etapa `reguladores.py` antes do
bypass e da orientacao: abre-se uma chave de cada laco cuja relacao de tensao
liquida e diferente de 1 — o caminho de MT que liga os dois lados de um
abaixador. Das chaves do laco, servem as que nao desenergizam no nenhum, e
abre-se a de menor perda. Lacos na mesma tensao, e transformadores em paralelo,
nao sao tocados. Nova variante `laco_por_transformador`; o `lacos.py` do censo
ganhou a coluna `c/ trf`.

Medido nas duas piores subestacoes da EQUATORIAL6072, com a etapa inteira:
5001306 de 77,2% para 11,6%, 5001242 de 66,8% para 14,6%, sem no perdido.

O que ela NAO faz: nao abre laco na mesma tensao (nas duas, abri-los nao muda
a perda), e modelo convertido antes dela — sem o `redirect _LACOS.dss` no
MASTER — segue sem a premissa ate ser reconvertido.

### Bypass de regulador fechado fora do par de PACs (achado 69)

A etapa `reguladores.py` abre, antes de medir a orientacao, a chave de bypass
que a BDGD declara fechada em volta do regulador — a forma de campo que a
trava do achado 48 nao ve, porque liga os PACs das chaves vizinhas e nao os do
regulador. O criterio e eletrico: dos candidatos do ciclo curto, servem os
que, abertos, nao desenergizam no nenhum; deles abre-se o que poe mais carga
no regulador. Chaves em paralelo abrem juntas; sem candidato que faca o
regulador conduzir, abre-se o de menor perda e o arquivo diz que o regulador
nao tem carga a jusante; laco so de trechos usa trecho como ultimo recurso.
Nova variante `bypass_de_regulador` na fixture e no pre-voo.

O que ela NAO faz: nao abre laco sem regulador. Na 5001306 da EQUATORIAL6072
o bypass leva a perda de 77,2% a 64,5%, e o resto vem desses.


### V39 — nenhuma base acima de 1,2x a ANEEL

Commit `6d6c189`, pre-voo 36940, coletor 37042 fechado em 22/09/2026. Traz o
achado 69 com as quatro formas de bypass, o laco em ilha que deixou de ser
decidido, e a etapa que nao desiste mais da subestacao com aviso #485.

| | V38 | V39 |
|---|---:|---:|
| EQUATORIAL6072 | 12,23% | **9,31%** (0,98x a ANEEL; era 3,0x na V36) |
| NEOENERGIA47 | 8,13% | 7,18% |
| NEOENERGIA43 | 4,87% | 4,08% |
| subestacoes sadias | 4.008 | 4.014 |
| bases acima de 1,2x a ANEEL | 1 | **0** |

Cinco bases ainda reprovam a ancora externa, todas por pouco: CERNHE6609
(7,70%), CERMISSOES2381 (7,54%), DMED51 (4,94%), COCEL82 (4,71%) e FORCEL83
(4,29%). A razao mediana segue em 0,51, e o que falta para ela virar erro
medido continua sendo o recorte: o modelo cobre MT e transformadores, e a
referencia soma o sistema inteiro.

O que ela NAO tem: BT completa (prevista para o fim de semana de 25-28/09) e
a decomposicao por segmento da ANEEL, pedida por LAI.

### V37 — achados 69 e 70 aplicados

Commit `afd5c6f`, pre-voo 36736, coletor 36837 fechado em 21/09/2026. As mesmas
99 bases e 4.061 subestacoes; 4.001 sadias (V36: 3.995), 26 sem convergir.
Mudaram SO as bases que os dois achados alcancam — o resto saiu identico:

| base | V36 | V37 | |
|---|---:|---:|---|
| EQUATORIAL6072 | 28,55% | **12,09%** | 51 bypass e 3 lacos abertos; sadias 124 -> 129 |
| RGE396 | 7,90% | **3,53%** | 13 lacos pela chave `BY-` da propria BDGD |
| NEOENERGIA47 | 8,61% | 8,13% | 3 bypass, 8 lacos |

Contra a ANEEL, acima de 1,2 ficou uma base so (V36: 2): a EQUATORIAL6072,
1,28x, que ja foi 3,0x. Seis reprovam a ancora (V36: 7) — a RGE saiu.

A etapa abriu 110 dos 111 lacos atraves de transformador e 55 bypass; 31 bypass
ficaram sem decisao, ditos no arquivo (16 sem candidata, 11 sem chave no laco,
4 com mais de uma).

O que ela NAO tem, e a proxima rodada precisa: (1) a etapa ainda desistia da
subestacao com `Max Control Iterations` (#485) — 7 na EQUATORIAL6072 ficaram
sem os dois achados (corrigido em `5f95db7`); (2) os 59 lacos da COPELDIS2866,
e os da ENERGISA_R369 e A26, estavam em ilha sem fonte e nao mudaram nada —
a etapa passa a ignora-los; (3) a contagem de nucleos do `submeter_todas.sh`
(`15b51ac`).

### V36 — achados 67 e 68 aplicados

Commit `5189014`, pre-voo 36584, coletor 36684 fechado em 17/09/2026. As mesmas
99 bases e 4.061 subestacoes da V35, 82 bases com rede, um commit so; 3.995
sadias (V35: 3.993) e 26 sem convergir (V35: 28).

Contra a ANEEL, nos 45 agentes com numero proprio, a razao modelo/referencia
mediana foi de 0,60 para **0,51**, e acima de 1,2 ficaram **2** (V35: 4) — a
COCEL82 e a FORCEL83 sairam, pelo ferro de transformador de consumidor. As
maiores quedas, todas explicadas:

| base | V35 | V36 | por que |
|---|---:|---:|---|
| NEOENERGIA43 | 10,63% | 4,87% | achado 67: sai o alimentador de 2.626%, fisicamente impossivel |
| ENERGISA_M405 | 7,52% | 1,86% | achado 67 (SE 65) e 68: metade dos kVA e de consumidor |
| ENERGISA_R369 | 7,12% | 2,41% | achado 68: 22% dos kVA de consumidor |
| FORCEL83 | 5,09% | 4,29% | achado 68: 46% dos kVA de consumidor |

O que ela NAO tem: os achados 69 e 70 (posteriores). A EQUATORIAL6072 segue em
28,55%, 3,0x a ANEEL — e e ela que os dois resolvem nas subestacoes medidas.
Sete bases reprovam a ancora externa; a RGE396 (1,3x) e a proxima a olhar.

### V35 — a primeira rodada nacional que passou pela porta

Commit `cadbd37`, submetida so depois do pre-voo 36481 aprovar com a arvore
limpa. **82 das 99 bases** validadas: as 17 cooperativas sem `CTMT.SUB` agora
FALHAM visivelmente (achado 65), em vez de entrarem como um `MASTER-AT.dss`
vazio que o validador dava por "sem ressalva".

Frente a V34: 4.061 subestacoes (as 17 a menos eram esses modelos vazios) e
**nenhuma causa mudou** nas subestacoes em comum. O `_procedencia.json` das
82 bases lista um commit so para as 4.061 subestacoes — a primeira rodada em
que isso se pode afirmar lendo o arquivo, e nao supondo.

O que ela NAO tem: o achado 67 (commit `f23a2bd`, posterior). A SE `65` da
ENERGISA_M405 ainda entra nos numeros desta rodada.

### Pre-voo: a rodada nacional passou a ter porta

`bash cluster/submeter_todas.sh --prevoo` roda, num no de calculo, a suite e o
ciclo inteiro sobre as seis fixtures — a minima e as cinco variantes que ligam
um achado cada — e compara contra `dados/referencia_prevoo.json`. Passando,
grava `logs/prevoo/<commit>.ok`; **sem esse selo, `--rodar` recusa submeter**.

Custo: minutos de um no. O que ele teria evitado: a V33 gastou 99 jobs para
descobrir um `NameError` de uma linha, e a V29 e a primeira V30 rodaram
inteiras sem chamar o `reguladores.py`. Reinjetando as duas, o pre-voo acusa
23 e 6 diferencas.

O que ele NAO faz: nao afere engenharia (a rede minima perde 97% de
proposito), nao roda base real, e nao substitui a comparacao entre rodadas.
Responde uma pergunta so — *o codigo faz hoje o que fazia quando a referencia
foi gravada?*

**A primeira execucao real reprovou, e foi por isso que valeu.** Quatro falhas,
tres delas invisiveis fora do cluster: o no de calculo nao tem `git` e o selo
saiu `sem_commit.ok`, que a porta jamais acharia; `test_plataforma` isolava so
as variaveis que ele proprio define, e dentro de um job o `PBS_NP` real vazava;
`_sigla` nao cortava caminho do Windows lido no Linux. A segunda execucao
morreu no caminho do selo, que nenhum teste alcancava — `prevoo.py` nao inseria
a raiz no `sys.path`.

**O que ela confirmou:** com a suite verde, a comparacao de numeros bateu
EXATAMENTE entre Windows/Python 3.14 e Linux/Python 3.11 — zero diferenca em
perdas, tensoes, contagens e causas, nas seis fixtures. E a evidencia mais
direta de determinismo entre plataformas que o projeto tem.
Fecha a safra BDGD **2025-12-31**, que a 1.0 declarava não validar. Última
rodada completa: **V32**, com 99 bases e 4.078 subestações.

### O que ela garante

- **99 distribuidoras** da safra 2025, **4.078 subestações**, com **80,2% de
  veredicto `OK`** e **uma única** subestação em `MODELO_QUEBRADO` — falha de
  modelo deixou de ser a limitação dominante (era 1.250, ou 30,7%, na V27).
- **`_procedencia.json` grava a safra**, a data-base e o nome do `.gdb` de
  origem, com teste travando os três campos. Na 1.0 o nome da pasta não
  carregava a safra e comparar duas rodadas de safras diferentes era erro
  fácil e silencioso.
- **1.032 testes.**

### O que mudou no diagnóstico, e por que os números não se comparam com a 1.0

A régua mudou três vezes desde a 1.0, sempre para separar coisas que estavam
na mesma gaveta. **Somar classes para comparar com rodada antiga só funciona
com o mapa abaixo:**

| classe | nasceu em | do que foi separada |
|---|---|---|
| `SUBESTACAO_ILHADA`, `REDE_PARCIAL`, `RAMAIS_SOLTOS` | achado 25 | `MODELO_QUEBRADO` (era 96,7% dela) |
| `PERDA_ALTA`, `SEM_CARGA` | achado 29 | `TENSAO_BAIXA` (era 58% dela) |
| `NAO_CONVERGE_COM_GD` | achado 26 | `MODELO_QUEBRADO` |
| `TENSAO_IMPLAUSIVEL` | achados 1 e 60-B | `TENSAO_BAIXA`, `REGULADOR_SATURADO`, `CARGA_ALTA` |

`diagnostico.SEM_TENSAO` existe no código para reproduzir a contagem antiga.

### Correções de conversão desta versão

- **Regulador com o `RegControl` no lado da fonte** (achado 59). O tape corria
  ao limite e *dividia* a tensão do lado da carga. Corrigido pela direção do
  fluxo; `REGULADOR_SATURADO` caiu de 98 para 12 no país.
- **GD com `kv` fixo de 13,8 kV** (achado 60), mesmo em alimentador de 34,5 kV
  — o `PVSystem` entregava de 0,03x a 4,0x o `Pmpp` conforme a tensão local.
- **Geração cuja energia não cabe na própria potência** (achado 61): 221
  unidades no país passam do teto de 5 MW da mini-GD e somam 10,3% da GD
  declarada. Desligadas em `_GD_IMPLAUSIVEL.dss`, premissa reversível.
- **Percentual publicado sobre solução divergida** (achado 62): 19 das 29
  subestações que não convergem publicavam perda entre 0 e 15%, plausível e
  falsa.

### O que ela NÃO faz

- **Não incorpora as correções dos achados 61 e 62 em rodada nacional.** Elas
  entraram depois da V32; os números acima são da V32 e a V33 é que os refaz.
- **Herda todas as limitações da 1.0 abaixo** que não estejam explicitamente
  corrigidas aqui — em especial a ausência de referência externa.
- **Não explica quatro das subestações do achado 60** que saturam sem serem
  longas nem terem GD desproporcional.

## 1.0.0 — 01/09/2026

Primeira versão declarada. Fecha a safra BDGD **2024-12-31**.

### O que ela garante

- **97 distribuidoras** convertidas de ponta a ponta, **4.201 subestações**,
  **26.655 alimentadores**. Das subestações, **97,4% fecham com veredicto
  `OK`** — compilam, convergem, não têm `NaN` e passam nos limites de tensão e
  ampacidade.
- **Rastreabilidade por modelo.** Cada saída carrega `_procedencia.json` com a
  versão da entrega, o commit, se a árvore estava suja, a versão do Python e a
  do **motor OpenDSS**. `sujo: null` significa "não deu para conferir", que é
  diferente de "conferido e limpo" — a distinção existe porque a confusão entre
  as duas já carimbou uma rodada como reprodutível sem que ninguém verificasse.
- **Saída determinística entre laptop e cluster.** O modo de execução não muda
  nada que seja calculado, e há teste travando isso.
- **804 testes**, incluindo um de ciclo completo que roda
  `converter → verifica → validador` sobre uma `.gdb` de verdade em 3 segundos.
- **Dezessete achados medidos** sobre as 97 bases, com quatro autocorreções
  registradas dentro dos próprios achados — o número velho fica visível.

### O que ela NÃO faz

- **Não calibra contra referência externa.** A âncora nacional de 7,4% de perda
  técnica reprova, não valida. Comparar com o `PERD_*` da própria BDGD é
  comparar com um número que não fecha consigo mesmo (achados 8, 9 e 13), então
  a divergência de 1,42× entre a perda modelada e a declarada está **medida e
  não atribuída**. Nenhuma conclusão por distribuidora deve ser publicada sem
  referência de fora.
- **Não entrega baixa tensão completa como produto.** `--bt completo` roda, mas
  só é confiável onde a rede vem conexa da origem. O critério é medido antes de
  simular — componentes por subestação na BDGD ≤ 3 — e por ele a Enel SP tem
  150 de 155 subestações elegíveis e a Cemig 163 de 412 (achados 16 e 17). Que
  as elegíveis rodem **em escala** ainda não está provado. Não usar os números
  de perda, cobertura ou tensão do modo completo como resultado de produção.
- **Não explica os 0,7% que falham.** As 11 subestações `NAO_COMPILA` e as 18
  `NAO_CONVERGE` estão classificadas, não diagnosticadas uma a uma. O mesmo
  vale para as 76 com `TENSAO_IMPLAUSIVEL`.
- **Não valida a safra 2025-12-31.** Ela saiu em setembro de 2026 e entra na
  v1.1. O código já **recusa** misturar duas safras na mesma rodada, em vez de
  processá-las como se fossem a mesma base.
- **Não modela coordenadas.** O leitor trabalha sem geometria; coordenada
  errada aparece na figura, não no resultado elétrico.

### Fatos de dado que a versão documenta, e não corrige

Não são defeitos do conversor — são o que a BDGD publica:

- **Cerca de 7% dos trechos de MT modelados não recebem tensão** (medido em
  02/09/2026 sobre 4.237 subestações; 19% delas têm zero). O valor de 25,70%
  publicado antes era artefato de `Topology.AllIsolatedBranches`, que reporta
  como isolada a rede alimentada pela segunda fonte de uma subestação.
- **Em 40 de 81 bases, a perda técnica declarada é menor que o ferro dos
  próprios transformadores cadastrados** — a declaração não fecha consigo
  mesma, e isso não depende do nosso modelo.
- **Um quinto das bases repete o mesmo valor de perda declarada**, o que a
  caracteriza como valor padrão e não como medição.

## Antes da 1.0

O projeto rodou de fevereiro a agosto de 2026 sem numeração, identificado por
commit e por sufixo de rodada (`V9` a `V25`). `MODELOS_V9/LINHA_DE_BASE.md` é a
linha de base declarada daquele período e está versionada de propósito.
