# BDGD → OpenDSS

Conversor que recebe uma BDGD (`.gdb`) e gera a rede da concessão em OpenDSS:
subtransmissão, média e baixa tensão. Sai um modelo único da concessão inteira
e também um modelo por subestação.

## Sem decorar nada

```bash
python menu.py
```

Abre uma janela com as sete ferramentas na ordem em que se usa. Cada uma
pergunta os parâmetros na própria janelinha, com o caminho já preenchido pelo
último uso, e o que ela imprime aparece ali mesmo.

A regra vale para todos os scripts: **com argumento** obedecem a linha de
comando exatamente como sempre; **sem argumento nenhum** abrem o painel de
parâmetros em vez de imprimir `error: the following arguments are required`.
Sem tela — servidor, SSH, ou `BDGD_SEM_JANELA=1` — o mesmo formulário é
perguntado no terminal. Nada depende de haver janela.

## Uso

```bash
pip install pyogrio numpy opendssdirect.py openpyxl matplotlib pywin32

# a concessão inteira
python converter.py "Enel_SP_390_2024-12-31_V11.gdb" --saida MODELOS

# só algumas subestações
python converter.py "...gdb" --saida MODELOS --se DEMB DGNA DCAM

# cenário de estresse para o NSGA-II
python converter.py "...gdb" --saida MODELOS --fator-carga 1.4
```

| Argumento | Padrão | Para que serve |
|---|---|---|
| `--se` | todas | subestações a gerar |
| `--mes` | 1 | mês da energia (1–12) |
| `--dia` | DU | tipo de dia: `DU`, `SA`, `DO` |
| `--fator-carga` | 1.0 | escala toda a demanda |
| `--bt` | agregado | `agregado`, `completo` ou `nenhum` (ver abaixo) |
| `--excel` | ao lado da .gdb | pasta com as planilhas da transmissora |
| `--kv-mt` / `--kv-at` | 13.8 / 88 | usados só quando o código de tensão é desconhecido |
| `--sem-at` | — | não gerar a camada de AT nem o MASTER-GERAL |
| `--reg-vreg` / `--reg-band` / `--reg-kva` | 122 / 2 / 5000 | ajuste dos reguladores |
| `--refazer` | — | regera subestações já existentes (padrão: pula e continua) |
| `--memoria-max` | 0 | limite em GB; ao passar, para limpo e diz onde retomar |

**Retomada.** Se a execução parar no meio, é só rodar o mesmo comando de novo.
Ele detecta as subestações que já têm `MASTER` e `resumo.json` e continua da
próxima. O `resumo.json` só é escrito no fim de cada SE, então nenhuma pasta
pela metade é confundida com pronta.

**Tempo esperado.** A agregação da UCBT (8,26 M registros) leva ~1,5 min e roda
uma única vez; cada subestação leva de 10 s a 2 min.

## O ciclo completo, e as duas premissas

O `converter.py` sozinho produz a rede que a BDGD **declara**. O ciclo completo
acrescenta duas etapas de MODELAGEM e depois mede:

```bash
python converter.py "...gdb" --saida MODELOS   # a rede como a BDGD declara
python ligacao.py    MODELOS                   # premissa 1 — achado 33, forma B
python ampacidade.py MODELOS                   # premissa 2 — achado 34
python verifica.py   MODELOS                   # NaN, convergência, dois motores
python energia.py    MODELOS                   # o dia em 96 passos, por alimentador
python validador.py  MODELOS --ses             # tensão, sobrecarga, carga sem tensão
python valida_perdas.py  MODELOS "...gdb"      # contra o PERD_A4 declarado
python valida_balanco.py MODELOS "...gdb"      # contra a energia medida

python regerar_v10.py --sufixo V13             # tudo isso, nas sete bases
python regerar_v10.py --sufixo V13 --sem-premissas   # sem as duas de modelagem
```

**A ordem importa.** A `ligacao` energiza rede que estava no escuro; a
`ampacidade` decide pela corrente que passa depois disso. E as duas vêm antes
de medir, porque o que se mede tem de ser o modelo que o usuário recebe.

**As duas são premissa, não conversão, e as duas se desligam.** Cada uma
escreve um `_*.dss` que o MASTER redireciona e que diz no cabeçalho o que fez
e como desfazer; apagar o `redirect` devolve o modelo ao cadastro. É esse
caminho que permite dizer, com número, quanto do resultado depende delas.

| premissa | o que faz | onde pesou |
|---|---|---|
| `ligacao.py` | liga a barra de MT da SE à componente que ficou sem tensão, na barra de maior grau. **Inventa um elo que a BDGD não declara** | Cemig-D: 697 elos, 269.673 cargas religadas |
| `ampacidade.py` | troca R1/R0 do trecho cuja corrente calculada excede a ampacidade declarada, pelo condutor mais fino do catálogo da própria base que a cobre | Enel SP: 88.354 trechos, 1.592 km, perda de 11,53% para 3,56% na DALV |

Cada elo é testado no próprio motor antes de entrar: se a solução divergir com
ele, o elo é recusado e isso fica escrito. Premissa que piora o modelo não
entra.

## O que sai

```
MODELOS/
├── MASTER-GERAL.dss      a concessão inteira: AT → MT → BT
├── _global/              LineCodes e curvas, declarados uma única vez
├── _AT/                  subtransmissão: fontes, linhas, chaves, trafos de potência
├── <SE>/MASTER-<SE>.dss  a subestação isolada, com equivalente na barra de MT
├── <SE>/REDE-<SE>.dss    só os elementos da SE — usado pelos dois MASTERs
└── relatorio_rede.json   cobertura, fontes, ilhas e o que ficou de fora
```

Os dois MASTERs compartilham os mesmos arquivos de rede, então não divergem. O
geral é para estudo sistêmico; o por-subestação existe porque carregar 155
subestações para otimizar um alimentador é desperdício — o NSGA-II e o estudo
de criticidade rodam no isolado.

## Um módulo por elemento gerado

| Módulo | Lê da BDGD | Gera |
|---|---|---|
| `linecodes.py` | SEGCON | `LineCode` (servem para AT, MT e BT) |
| `linhas.py` | SSDMT, SSDBT, RAMLIG | `Line` |
| `chaves.py` | UNSEMT | `Line` (Switch=Y) + `SwtControl` |
| `transformadores.py` | UNTRMT, EQTRMT | `Transformer` + `Reactor` de aterramento |
| `cargas.py` | UCBT_tab, UCMT_tab | `Load` |
| `complementos.py` | CRVCRG, UNCRMT, UNREMT, UGBT/UGMT | `LoadShape`, `Capacitor`, `RegControl`, `PVSystem` |
| `subtransmissao.py` | SSDAT, UNSEAT, UNTRAT, EQTRAT, UCAT, UGAT, UNCRAT, BAR, CTAT | camada de AT e os vãos |
| `transmissao.py` | planilhas da ISA | fontes e trafos das subestações da transmissora |
| `tensoes.py` | — | código TEN_NOM → kV |
| `master.py` | — | MASTER-GERAL, MASTER por SE, REDE-\<SE\> |

## As decisões que fazem o modelo resolver

**1 a 7 — a média e a baixa tensão.** Secundário de BT com derivação central
(`TEN_LIN_SE` é tensão de linha; cada meia bobina fica com metade). Neutro no nó
4, aterrado por um `Reactor` de 0,5 Ω — sem ele a matriz fica singular. Bancos de
transformadores com uma perna por unidade, nunca a mesma, senão viram curto entre
fases da MT. Chaves abertas emitidas duas vezes, no `SwtControl` e como `Open` no
fim do MASTER. `Voltagebases` com todos os níveis e a sequência
`Solve → CalcVoltagebases → Solve`. Geração com potência nula descartada, porque
um `PVSystem` com `kVA=0` espalha NaN pelo circuito.

**8. O vão de saída.** A BDGD **não modela o arranjo interno da subestação**.
Verificado na DABR: os seis `PAC_INI` dos alimentadores estão na malha de MT, mas
o `PAC_2` dos dois trafos de AT não se conecta a nenhum deles — não há barramento
nem disjuntor de saída entre o trafo e o alimentador. O elo existe só de forma
lógica, em `CTMT.UNI_TR_AT` e `CTMT.BARR`.

Era isso que obrigava a versão anterior a criar **uma fonte infinita por
alimentador** — 1.806 delas. Agora o elo lógico vira elétrico: a barra de MT
declarada em `BAR`/`UNTRAT.BARR_2` vira um nó de verdade, o secundário do trafo
chega nela, e de lá sai um vão por alimentador até o seu `PAC_INI`. Os
alimentadores da mesma subestação passam a dividir trafo e barra, como na
operação real.

**9. A cabeceira é dada, não adivinhada.** `CTMT.PAC_INI` é a cabeceira declarada.
A versão anterior a descobria por topologia, escolhendo a barra de maior
ampacidade da maior componente conexa — chute que erra sempre que a rede está
fragmentada.

**10. Uma fonte por pátio de AT.** Ver a seção seguinte.

## Até onde a alta tensão vai — e por quê

A malha de 88 kV desta BDGD **não é conexa**. Montando o grafo de `SSDAT` mais as
chaves fechadas de `UNSEAT`: 32.220 nós em **844 componentes**, a maior com 740
nós (2,3% do total). Delas, 230 têm cabeceira de circuito (`CTAT.PAC_INI`), 213
têm transformador de potência, **154 têm transformador mas nenhuma cabeceira** e
460 são ilhas puras. As 16 ETTs da ISA não possuem **uma única barra** em `BAR`.

Ou seja: os trechos de 88 kV que ligam uma subestação a outra não estão nesta
exportação. **Não dá para montar uma subtransmissão conexa só com a BDGD.**

O que o conversor faz então: monta o pátio de AT de cada subestação e o energiza.
Onde há cabeceira de circuito de AT, a fonte entra nela; senão, entra no primário
do transformador, como equivalente explícito. O `relatorio_rede.json` diz quantas
ficaram em cada caso.

### O papel das planilhas da ISA Energia

Elas **não fecham a malha** — trazem transformadores e subestações, não linhas de
transmissão. Resolvem dois problemas concretos:

1. **As subestações da transmissora.** Cinco SUBs aparecem em `CTMT` sem nenhum
   trafo em `UNTRAT` — TBAN, TCTR, TEMG, TMRE e SSJO —, somando 69 alimentadores
   que ficariam órfãos. Quatro são ETTs da ISA, e a planilha diz qual é o
   transformador: Bandeirantes 345/34,5 kV, Centro 230/20 kV, Miguel Reale
   345/20 kV. Esses alimentadores passam a ter trafo de verdade.
2. **O nível de curto.** Em vez de um MVAsc inventado, a potência instalada
   declarada em cada ETT dá uma estimativa defensável.

O que elas **não** permitem: representar a rede de 345/440 kV. Sem as linhas e
suas impedâncias, qualquer topologia acima do ponto de conexão seria invenção. O
modelo para no ponto de conexão com equivalente de curto — que é a prática normal
em estudo de distribuição.

## A baixa tensão: agregada ou completa

**`--bt agregado` (padrão).** A energia de todas as UCs de um transformador é
somada e pendurada no secundário dele. Modelar as 8,26 milhões de UCs
individualmente multiplicaria o modelo por ~30 sem mudar o carregamento do
alimentador. Do ponto de vista da MT as duas representações são
indistinguíveis, porque a BT é curta e radial. **Use este modo para
carregamento, criticidade e NSGA-II.**

**`--bt completo`.** Uma `Load` por unidade consumidora, no PAC real, com a rede
secundária (`SSDBT`) e os ramais de ligação (`RAMLIG`) a quatro fios. A cadeia
física é trafo → SSDBT → RAMLIG → UC: sem o ramal, 97% das UCs ficam soltas,
porque o PAC da UCBT é a ponta do ramal, não um nó da rede secundária. O neutro
sai como linha monofásica paralela (a SEGCON não tem LineCode de quatro
condutores) — sem ele as cargas não têm retorno.

**Use só para tensão de atendimento**, que é onde o equivalente agregado falha:
ele não enxerga a queda no secundário e no ramal, exatamente onde a violação do
Módulo 8 costuma aparecer. Custo: na DABR, 30.009 cargas contra 926, e as perdas
sobem de 6,35% para 16,05% — **esse número ainda precisa ser calibrado** contra
as colunas `PERD_B` da `CTMT` antes de ser usado como resultado.

## Limitações — leia antes de usar

**Sequência zero é premissa, não dado.** A `SEGCON` traz apenas `R1` e `X1`.
Adotam-se `R0 = 3,0·R1` e `X0 = 3,5·X1`. Para carregamento e tensão equilibrada
o efeito é pequeno. **Para desequilíbrio (FD95% do Módulo 8) o resultado não tem
validade.** Se obtiver a tabela de estruturas, migre para `LineGeometry`.

**A impedância dos trafos de potência é adotada.** A BDGD traz perdas
(`PER_TOT`, `PER_FER`), não impedância. O `Xhl` sai de uma tabela por faixa de
potência em `subtransmissao.XHL_POR_MVA`.

**Códigos de tensão desconhecidos.** `TEN_NOM` é um domínio da ANEEL que não
acompanha o `.gdb`. Estão confirmados 49→13,8 kV, 59→20 kV, 72→34,5 kV, 84→88 kV
e 94→138 kV (por nomenclatura de barra e cruzamento com a ISA). Os códigos 27,
55, 62, 67, 73 e 74 aparecem em poucos registros e **não** foram confirmados —
o conversor avisa e aplica o padrão. Preencha em `bdgd2dss/tensoes.py`.

**Reguladores com ajuste típico.** Existem 213 reguladores e eles atuam na
solução, mas `vreg`, `band` e `kVA` não vêm da BDGD. São iguais para todos.
Se a distribuidora fornecer o ajuste de campo, passe por `--reg-*`.

**Harmônicos estão fora de alcance.** A BDGD não tem espectro de carga nem de
inversor. O Módulo 8 exige DTT, DTTp e DTTi; nada disso é derivável daqui.

**Fator de potência é assumido** (0,92), não medido.

**Capacitores são banco fixo.** A BDGD não traz ajuste de `CapControl`. Em carga
leve isso eleva a tensão artificialmente.

**A energia declarada na CTMT não bate com a soma das UCs.** No BSI-105, 1.753
MWh contra 1.000 MWh. Este conversor usa a soma das UCs.

**Registros inconsistentes.** Cerca de 3% dos alimentadores têm energia
incompatível com a rede física. Rode `analise/criticidade.py` para listá-los.

**Subtensão pré-existente em parte da MT.** Na DABR, 14,1% dos nós de MT já
ficavam abaixo de 0,92 pu no modelo antigo, com mínimo de 0,489. A versão atual
desloca a mediana ~3,4% (0,964 → 0,930) porque agora modela a impedância real do
transformador e da fonte, que o modelo anterior ignorava. É comportamento
esperado, não regressão — mas o mínimo profundo merece investigação à parte.

**Quase metade da base não tem referência utilizável para validar perda.** Na
Cemig-D, **43,9%** dos alimentadores faturam mais energia do que recebem e
**49,0%** declaram perda total abaixo de 2%. Contra esses não há como aferir
modelo nenhum — não é limitação do conversor, é limite do dado, e qualquer
resultado tem de dizer sobre que fração da base ele fala. A cobertura efetiva
da comparação vai de 53% (Enel SP) a 73% (Cemig-D).

**A perda do modelo não é a perda da rede.** Medido nas sete bases contra o
`PERD_A4` declarado, depois de corrigidos os achados 26 e 32 e aplicadas as
duas premissas:

| base | razão modelo/declarado |
|---|---|
| Equatorial PA | 0,55× |
| Light | 0,74× |
| Enel CE | 0,83× |
| CPFL Paulista | 0,88× |
| Roraima | 2,63× |
| Enel SP | 3,19× |

Quatro pousam entre 0,74× e 0,88×, que é a faixa esperada de um modelo com MT
e transformadores e **sem rede secundária**. As duas fora têm causa conhecida e
não tratada: a Enel SP declara 1,12%, o mais baixo das sete, e a Roraima tem
duas subestações rurais com cauda de tensão colapsada. Enquanto não houver
validação contra referência **externa** à BDGD — a perda publicada no Módulo 7,
por exemplo —, o que se afirma é concordância com o cadastro, não com a rede.

**Parte da rede declarada não é alcançável a partir da cabeceira.** Refazendo a
conectividade na BDGD crua, sem OpenDSS, o alcance a partir do `PAC_INI` vai de
99,8% (Enel SP) a 81,8% (Equatorial PA). O que sobra são três formas: cabeceira
que não existe entre os PACs do próprio alimentador, rede inteira numa
componente com a cabeceira numa ilha ao lado, e rede estilhaçada em milhares de
componentes. A segunda é tratada pelo `ligacao.py`, como premissa; as outras
duas ficam como limitação declarada.

## Sobre o NSGA-II

Com `--fator-carga 1.0`, **71% dos alimentadores operam abaixo de 50%** da
ampacidade e apenas 1,8% acima de 100%. Nessa condição as restrições de corrente
ficam quase todas inativas e a fronteira de Pareto degenera.

1. **Escalar a demanda.** `--fator-carga 1.4` aproxima a maior parte da rede do
   limite. Cenário sintético, mas controlado e reprodutível.
2. **Selecionar os alimentadores já críticos.** `analise/ranking.py` lista os 28
   circuitos acima de 100% e os 36 entre 80% e 100%. Casos reais, em menor número.

A segunda é mais defensável num trabalho acadêmico; a primeira dá mais casos.

## O painel — use isto, não a linha de comando

```bash
python painel.py
```

Abre uma janela com todas as subestações geradas, cada uma com a sua **causa
raiz** já classificada. De lá você:

| Botão | O que faz |
|---|---|
| **Validar** | compila, resolve e diz *por que* está ruim, se estiver |
| **Analisar (gráficos)** | roda a análise COM e abre a pasta com as figuras |
| **Plot Circuit no OpenDSS** | abre o traçado nativo do OpenDSS, com as coordenadas da BDGD |
| **Perfil de tensão no OpenDSS** | `Plot profile phases=all` |
| **Validar TODAS** | varre a pasta inteira e preenche a coluna de causa |
| **Exportar diagnóstico** | CSV com o estado de cada subestação |

A cor da linha separa o que é **nosso** (vermelho/laranja — acionável) do que é
**da rede** (azul — depende de dado que a BDGD não tem).

### Por que tkinter

A janela lista, dispara e mostra imagem. Para isso o tkinter já vem no Python
(zero instalação) e o matplotlib tem backend nativo. PySide6 ficaria mais
bonito ao custo de ~120 MB de dependência; Dear PyGui tem sistema de gráficos
próprio e obrigaria a reescrever tudo; Streamlit sobe um servidor web e
complica o objeto COM, que é *apartment-threaded*. O gargalo real não é o
widget e sim desenhar 30 mil segmentos — por isso o gráfico é renderizado em
PNG numa thread e a exploração interativa fica com o próprio OpenDSS.

## Análise e gráficos (interface COM)

```bash
python analise_com.py MODELOS_V2/MASTER-GERAL.dss
python analise_com.py MODELOS_V2/DABR/MASTER-DABR.dss --diario
```

Resolve pelo `OpenDSSEngine.DSS` (COM, a interface oficial no Windows) e grava
em `analise/`: traçado geográfico por carregamento e por tensão, perfil de
tensão, histogramas, perdas por alimentador, potência por ponto de conexão e,
com `--diario`, a curva de 24 h.

O conversor extrai a geometria da BDGD (SIRGAS 2000) para `BusCoords.dat`, o
que também habilita os comandos nativos:

```
Plot Circuit Power max=2000 dots=n labels=n C1=Blue
Plot Circuit Voltage
Plot profile phases=all
```

Duas armadilhas que custaram tempo e estão resolvidas no código: o `Buscoords`
tem de vir **depois do primeiro Solve** (antes disso a lista de barras do
OpenDSS ainda não existe e nenhuma coordenada casa), e em modo snapshot é
preciso emitir `Sample` explicitamente, senão os registradores do EnergyMeter
ficam zerados.

## Diagnóstico por subestação

`bdgd2dss/diagnostico.py` classifica cada subestação por **causa raiz**, e a
distinção que ele faz é a mais importante do projeto: separar defeito do
conversor de característica da rede.

| Causa | Significa | Acionável aqui? |
|---|---|---|
| `MODELO_QUEBRADO` | não compila, não converge ou tem carga sem tensão | **sim** |
| `CARGA_ALTA` | demanda acima da capacidade instalada declarada | **sim** |
| `TENSAO_BAIXA` | subtensão sem nenhuma explicação — investigar | **sim** |
| `REDE_EXTENSA` | alimentador muito longo; a queda é fisicamente correta | não |
| `REGULADOR_SATURADO` | reguladores no tape máximo; falta ajuste de campo | não |
| `OK` | dentro do esperado | — |

Contexto para as duas últimas: a mediana da concessão é **8,9 km por
alimentador**, e apenas **7 dos 1.808** passam de 100 km. Dois deles estão na
DREG, com **440 e 335 km** — nessa escala a queda de 30% é o resultado
correto, e o que a sustenta na operação real é o ajuste escalonado dos
reguladores, que a BDGD não traz.

Isso foi verificado experimentalmente na DREG, isolando cada suspeito:

| Cenário | V mediana |
|---|---|
| como está | 0,709 |
| linhas com R e X ≈ 0 | **1,037** |
| sem as cargas de BT | 0,977 |
| sem os reguladores | 0,709 |

Ou seja: a queda está nas linhas, provocada pela carga de BT, e os reguladores
não ajudam porque já estão saturados no tape máximo.

## Coerência entre resistência e ampacidade na SEGCON

144 dos 3.495 condutores da SEGCON têm resistência incompatível com a corrente
nominal declarada — o extremo é `R1 = 8,43 Ω/km` para um condutor de `1500 A`,
quando o esperado seria ~0,04. O `linecodes.py` ajusta `R1 = a · CNOM^b` sobre
o miolo coerente da própria base (nesta: `R1 = 219,2 · CNOM^−1,120`, calibrado
em 3.187 condutores) e substitui os que estão mais de 7,4× acima do previsto —
**77 condutores**, cada um marcado com `!! R1 CORRIGIDO` no `.dss`.

Duas ressalvas honestas: a correção só age **para baixo** (condutor com R muito
*abaixo* do previsto costuma ser barramento ou jumper declarado de propósito), e
**ela não resolve a subtensão** — medido na DREG, o efeito foi nulo, porque os
condutores afetados são 13% dos km e estão em ramais. É melhoria de qualidade de
dado, não a explicação da queda de tensão.

**E há um segundo mecanismo, que este não pega.** O ajuste acima confere `R1`
contra `CNOM` *dentro do registro*. O condutor 593 da Enel SP — 31 A com
8,232 Ω/km — é internamente coerente: fio fino tem mesmo essa resistência. O
defeito dele está no **uso**: ele cobre 2.990 km, 13,5% da rede, servindo de
tronco. Na Enel SP inteira, 16,1% da quilometragem carrega **73,6%** da
resistência ponderada.

Isso é o achado 34, e quem trata é o `ampacidade.py`, com critério de uso e
não de registro: só o trecho cuja corrente **calculada** excede a ampacidade
**declarada**. Nas outras cinco bases ele quase não age — Enel CE, que tem
perfil de condutor parecido, teve 46 trechos trocados de 99.832 km, porque lá
os fios finos estão em ramais de pouca corrente. É premissa de modelagem e se
desliga; o ajuste desta seção, não — ele é qualidade de dado.

## Fechamento da malha de 88 kV

A BDGD não modela o barramento interno da subestação: os circuitos de AT que
chegam e que saem nunca se encontram, e a malha fica em **844 ilhas**. O módulo
`malha_at.py` cria a barra de AT de cada subestação e liga a ela os trechos que
lhe pertencem, usando `UNSEAT.SUB` e `UNTRAT.SUB` (dado declarado, 2.482 chaves
e 437 trafos) e, onde estes faltam, o nome do circuito em `CTAT.NOME` via
`dados/de_para_mnemonicos.csv`.

## Validação

```bash
python validador.py MODELOS            # o MASTER-GERAL e todas as subestações
python validador.py MODELOS --geral    # só o modelo completo
python validador.py MODELOS/DEMB       # uma subestação
```

Verifica compilação, convergência, cargas sem tensão, tensões em p.u. por nível,
sobrecarga e perdas.

Uma observação sobre a métrica de cargas isoladas: `Topology.AllIsolatedLoads()`
do OpenDSS percorre a rede a partir de **uma** fonte. No `MASTER-GERAL` há uma
fonte por pátio de AT, então tudo alimentado pelas demais aparece como isolado —
falso positivo em massa. O validador usa a medida elétrica (carga cuja barra
ficou sem tensão) e reporta a topológica só como referência.
