# Adendo — a pergunta 1 tem causa

*12/08/2026. Complementa o `RESPOSTA_QUESTOES_MODELAGEM.md`, seção 4.*

---

## O resumo, se for ler só um parágrafo

A não convergência com geração **não é do inversor**. Ela vem de **24
transformadores da DALP cujo primário bifásico foi escrito como trifásico**.
Duas das três fases de cada secundário ficam em 0,50 pu, os inversores dessas
barras vivem abaixo do `Vminpu` do `PVSystem`, e é a troca de modelo deles que
impede o fluxo de fechar. **São 126 inversores de 4.218 — 3,0% — e eles
explicam 100% da falha.**

Não é parâmetro de inversor, não é modo de controle, não é algoritmo.
É conexão de fase.

---

## Como chegamos

O caminho começou longe daqui. Na seção 4 registramos que `Vmax = 1,229` era
**idêntico** em 75% e 100% de irradiância, e que isso não podia ser sobretensão
causada pela injeção — se fosse, 100% teria de dar mais que 75%.

Puxando essa ponta: as barras acima de 1,10 pu na DALP têm todas a base
`0,1201 kV`, e só existem 36 barras nessa base. Dentro dessas 36 há **duas
populações diferentes**, que estávamos contando como uma:

| população | n | base 0,1201 | acima de 1,10 pu |
|---|---:|---|---:|
| transformador monofásico de 3 enrolamentos, derivação central `[MT, 0,12, 0,12]` | 14 | **correta** | 0 |
| transformador trifásico de 2 enrolamentos, 13,8 → 0,24 kV | 22 | **errada** | 22 |

As 22 têm um padrão limpo demais para ser numérico:

```
doente   [69,8 | 69,8 | 139,4]     duas fases em exatamente metade da terceira
sadio    [139,3 | 139,1 | 139,7]
```

Com toda a carga e toda a geração desligadas o padrão **não muda** — são 24 de
355 transformadores, os mesmos 24. É topológico.

O primário fecha o diagnóstico: nesses 24, um dos três nós de média tensão está
em **2.172 V** e os outros dois em **8.689 V**. E `2.172 = 8.689/4` é a tensão
de um nó que **não é alimentado** e fica preso apenas pelas bobinas do delta.

O trecho que chega nessas barras é bifásico:

```
New Line.5104165S1  Bus1=...46880022.2.3  Bus2=...46880013.2.3  LineCode=CND_66_2F
New Line.5094792S1  Bus1=...46888128.3.1  Bus2=...46888101.3.1  LineCode=CND_1713_2F
```

e o transformador é escrito com as três:

```
New Transformer.14257963 phases=3 windings=2 Xhl=2.200
~ wdg=1 bus=2345093246880013.1.2.3 conn=delta Kv=13.8 ...
```

**A BDGD tinha o dado.** Nos 23 desses transformadores que localizamos na
`UNTRMT`, o campo `FAS_CON_P` declara duas fases — 14 em `BC`, 8 em `AB`, 1 em
`CA` — e concorda com a rede em 17 dos 23. O conversor lê esse campo, guarda o
resultado numa variável, e no ramo trifásico **não a usa**: escreve `.1.2.3`
fixo.

---

## O experimento que fecha

Com controle de população, porque a diferença importa:

| irradiância | base | desligando os 126 inversores **das 24 barras** | controle: 126 inversores sorteados entre barras **sadias** |
|---:|---:|---:|---:|
| 0,25 | 96/96 | 96/96 | 96/96 |
| 0,50 | 96/96 | 96/96 | 96/96 |
| **0,75** | **73/96** | **96/96** | **73/96** |
| **1,00** | **35/96** | **96/96** | **35/96** |

A coluna `base` reproduz os dois números que já estavam na seção 4 — 73/96 e
35/96 — sem ajuste nenhum. O tratamento recupera **96/96 nas quatro
irradiâncias**. O controle, com a mesma quantidade de inversores desligados e
semente fixa, ganha **exatamente zero passos**.

Ganho somado: **+84 passos no tratamento, +0 no controle.**

---

## Por que o mecanismo é o `Vminpu`, e não outra coisa

O `PVSystem` sem `Vminpu`/`Vmaxpu` declarados usa os padrões do OpenDSS: **0,85
e 1,10**. Fora dessa faixa ele deixa de ser injeção de potência constante e vira
impedância constante. Um inversor numa barra a **0,50 pu** está
permanentemente do lado errado da faixa, e a cada iteração o modelo troca.

É a mesma família do *cutoff* do ZIPV que já documentamos no pacote: *a carga
desliga, a tensão sobe, a carga religa, a tensão cai, e o fluxo nunca converge*.

Isso também explica por que **alargar a faixa não resolvia** — nós tínhamos
testado 0,10–2,00, 0,80–1,20 e 0,85–1,50, e nenhuma restaurava 96/96. Alargar
trata o sintoma numa barra que continua a 0,50 pu; o problema é a barra estar
a 0,50 pu.

E fecha a pergunta que tinha sobrado: o `Vmax = 1,229` idêntico nas duas
irradiâncias nunca veio da geração. É a **fase sadia** de uma dessas barras,
dividida pela base errada que o `CalcVoltagebases` atribuiu a partir do
primeiro nó — que, em 21 das 22, calhou de ser uma das fases pela metade.

Os dois sintomas que pareciam dois problemas eram o mesmo defeito visto de
dois ângulos.

---

## A correção

No ramo trifásico, exigir três fases **dos dois lados** antes de escrever o
delta em `.1.2.3`, e escrever `Kv` de acordo com quantos nós o enrolamento
toca — dois nós é ligação fase-fase e vê a tensão de linha; um nó vê
linha/√3.

Ela está escrita e coberta por testes, mas **ainda não foi aplicada ao pacote**:
há uma regeração das sete distribuidoras em andamento, e aplicar no meio
deixaria quatro bases geradas com um código e três com outro, que é exatamente
o que inviabiliza a comparação entre elas. Entra assim que a regeração fechar,
com o pacote atualizado.

---

## Duas correções menores que saíram no mesmo caminho

**Trecho de comprimento zero.** Um segmento com `COMP = 0,001 m` na BDGD vira
`Length=0.00` no `.dss`, a matriz de impedância fica nula e o OpenDSS **aborta
a montagem da Y da rede inteira** — uma linha derruba a subestação. São 6
ocorrências em 24,4 milhões de trechos nas sete distribuidoras, mas uma delas,
sozinha, consumiu 3,5 h de uma rodada. Vale um aviso para quem usa o pacote em
outras bases: se uma subestação retornar `#183 Y matrix build aborted`, procure
`Length=0.00`.

**Fonte de alta tensão fixa em 88 kV.** Onde a subtransmissão da distribuidora
não é de 88 kV, as fontes saem no nível errado. Na Equatorial PA, 107 dos 220
transformadores de AT são de 138 kV e o modelo de alta tensão não converge.
Roraima e Enel CE convergem por serem 88 kV puras — não porque o código
estivesse certo.

---

## Uma observação de método, já que vocês perguntaram como validamos

As duas primeiras vezes em que olhamos essas 22 barras, erramos o diagnóstico —
uma vez culpando a meia-bobina de derivação central, outra concluindo que o
efeito era "de relato, não de física". A meia-bobina existe: são as outras 14
barras, e nelas a base está certa. E o efeito é dos dois, com a física sendo a
parte grave.

O que virou o diagnóstico nas duas vezes foi a mesma coisa: **medir a população
inteira em vez de comparar um par**. O `14257002` é um transformador com
exatamente o mesmo defeito que nunca foi contado, só porque o nó 1 dele calhou
de ser a fase cheia e a base saiu 0,1386 em vez de 0,1201.
