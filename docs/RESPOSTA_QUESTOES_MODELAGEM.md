# Resposta às questões de modelagem no pacote BDGD2OpenDSS

Referente a *Questões de modelagem no pacote BDGD2OpenDSS (MODELOS_V8)*,
11 de agosto de 2026.

Data desta resposta: 11 de agosto de 2026.

---

## 1. Antes de tudo

O relatório de vocês encontrou **um defeito real e nosso**, que a nossa própria
validação não tinha pego. Está corrigido, e a correção mudou a tensão de cinco
subestações — entre elas a DALP.

Encontrou também um **segundo defeito, que reproduzimos e ainda não sabemos
resolver**. Descrevemos abaixo tudo o que testamos e descartamos, para que
vocês não repitam o caminho.

E um terceiro grupo de observações já não existe na versão atual, por motivo
que explicamos na seção 2.

Este é o primeiro uso independente do conversor, e ele valeu mais que qualquer
revisão que fizemos internamente: vocês olharam para os modelos sem saber o que
esperar deles.

---

## 2. Sobre a versão do pacote

O pacote que vocês receberam é de **05/08/2026**. A pasta chama-se `MODELOS_V8`,
mas o conteúdo dela foi regerado várias vezes desde então — a `MODELOS_V8` que
temos hoje em disco é de 10/08 e já não é a mesma.

Três das observações de vocês se referem a coisas corrigidas nesse intervalo, e
estão marcadas abaixo como **[já corrigido]**.

Vamos entregar um pacote novo. Ver a seção 8.

---

## 3. Pergunta 2 — a tensão baixa na rede de 13,8 kV

**Não é retrato da operação. Era inconsistência nossa, e está corrigida.**

### O mecanismo

O conversor gera dois modelos da mesma subestação:

- o **isolado** (`MODELOS_*/DALP/MASTER-DALP.dss`), com a fonte na barra de MT;
- o **geral** (`MASTER-GERAL.dss`), onde quem sustenta a barra de MT é o
  transformador de alta tensão.

No modelo geral, o `tap` desse transformador vem da **mediana** de
`CTMT.TEN_OPE` dos alimentadores da subestação. A Enel declara 1,09 pu em
**1.586 dos 1.806 alimentadores** — é assim que ela compensa a queda ao longo
do tronco.

No modelo isolado não há esse transformador: a fonte o substitui, e portanto
deveria reproduzir o mesmo pu. **Não reproduzia.** O valor saía por dois outros
caminhos no nosso código:

1. do **primeiro alimentador** que aparecesse na iteração, e não da mediana;
2. de um **`1.0` fixo**, no ramo usado quando todas as barras da subestação são
   derivadas — que é exatamente o caso da DALP.

Medimos as 150 subestações que têm transformador de AT: **5 tinham `pu`
diferente do `tap`, e a diferença era sempre 0,09 pu.** Não é coincidência: é a
distância entre operar a 1,09 e operar a 1,00.

Vocês abriram o modelo isolado — que é o que recomendamos para estudo de
alimentador, e é o que o próprio cabeçalho do `MASTER` sugere — e receberam a
rede nove pontos percentuais abaixo.

### O efeito da correção

Tensão média por subestação, antes e depois, no mesmo caso instantâneo:

| Subestação | antes | depois | diferença |
|---|---:|---:|---:|
| **DALP** | 0,9351 | **1,0144** | +0,0793 |
| DTED | 0,9284 | 1,0091 | +0,0807 |
| DCAM | 0,9709 | 1,0562 | +0,0853 |
| DNAC | 0,8429 | 0,9148 | +0,0719 |
| DGPR | 0,9529 | **0,8774** | **−0,0755** |
| DVTA | 0,9230 | 0,9230 | 0,0000 |

Duas linhas merecem atenção, porque mostram que a correção não é um empurrão
para cima:

- **DGPR desce.** A mediana dela é 1,00, e o código antigo havia pegado 1,09 de
  um alimentador avulso. A correção faz os dois modelos concordarem, para
  qualquer lado.
- **DVTA não muda nem na quarta casa.** Ela já concordava, e serve de controle:
  o efeito observado vem da correção e não de outra coisa que tenha mudado
  junto.

### Respondendo item a item

**(a) O tap dos transformadores 34,5/13,8 kV deveria estar acima de 1,0?**
Sim, quando a BDGD declara `TEN_OPE` acima de 1,0 — e na DALP declara. O
transformador de barra que vocês viram no `Vaos.dss`
(`TRB_DALP_13p8`, 219 MVA, `Xhl=12,5%`) é sintético: a BDGD põe alimentadores
de 13,8 kV no mesmo `CTMT.BARR` da barra de 34,5 kV, sem declarar o
transformador entre as duas. Nós o criamos. O que faltava era a fonte a
montante estar no pu certo.

**(b) A subestação tem reguladores que não entraram no modelo?**
Não. Os `reguladores: 0` da DALP são o que a BDGD declara. As 32 subestações
com reguladores modelados são aquelas em que a base traz `UNREMT`. A informação
existe para algumas e não para outras porque assim está na base, não porque a
tenhamos descartado.

**(c) Os capacitores estão com controle ativo?**
Sim, o `Controles.dss` traz `CapControl`. O fato de desabilitá-los não mudar
nada é consistente com o diagnóstico acima: 12 capacitores não compensam nove
pontos percentuais de tensão de cabeceira.

---

## 4. Pergunta 1 — a não convergência com geração

**Reproduzimos, em motor independente. É defeito nosso, e continua aberto.**

Rodamos a varredura de vocês na DALP, com a tensão de cabeceira como única
variável, para separar este problema do anterior:

| irradiância | modelo antigo (pu = 1,00) | corrigido (pu = 1,09) | vocês |
|---|---:|---:|---:|
| desabilitada | 96/96 | 96/96 | 96/96 |
| 25 % | 96/96 | 96/96 | 93/96 |
| 50 % | 96/96 | 96/96 | 80/96 |
| 75 % | **73/96** | **73/96** | 30/96 |
| 100 % | **34/96** | **35/96** | **29/96** |

Vocês usaram OpenDSS 9.4.0.1 pelo `py_dss_interface`; nós usamos o DSS C-API
0.14.5 pelo `opendssdirect`. Os números absolutos diferem, a progressão é a
mesma, e o fenômeno é o mesmo. **A correção da seção 3 não o resolve** — muda
um passo, que é ruído.

### Hipóteses que já podem ser riscadas

Pelas de vocês, e concordamos com o método: histerese do inversor, modo de
controle, número de iterações, algoritmo, e sobredimensionamento da geração
frente ao transformador de atendimento.

Acrescentamos duas:

| hipótese | teste | resultado |
|---|---|---|
| tensão de cabeceira baixa | pu 1,00 contra 1,09 | **refutada** — 73/96 e ~35/96 nos dois |
| impedância do aterramento de neutro | R de 0,5 Ω a 0,001 Ω | **refutada** — fator 500, não muda um único passo |

A segunda era a hipótese de vocês, e era boa. Com `--bt agregado` não há rede
de baixa tensão: toda a carga e toda a geração de um transformador ficam na
mesma barra e voltam por um único reator de aterramento. Fazia sentido. Mas
variar esse reator por três ordens de grandeza não altera nada.

Uma terceira sonda que tentamos — inversores ligados a barras não energizadas —
saiu com instrumentação defeituosa e não produziu resultado utilizável.
Registramos para que ninguém a conte como testada.

---

## 5. Pergunta 4 — como a validação foi feita

Há dois critérios diferentes no pacote, e vocês estavam certos em desconfiar:

| arquivo | o que faz |
|---|---|
| `validacao.json` | validador **instantâneo**: compila, converge, NaN, cargas sem tensão, faixa do PRODIST |
| `energia_dia.json` | **dia inteiro**, 96 passos, com geração |
| `validacao_perdas.json` | cruzamento com o `PERD_*` declarado na CTMT |

Então sim: a simulação diária de 96 passos foi exercitada, e as 155
subestações a resolvem.

**Mas há uma ressalva que a sua pergunta nos obrigou a enxergar, e ela é
importante.** O nosso ciclo diário usa a irradiância **medida** de janeiro em
São Paulo. Na DALP isso dá **5,1 MW de pico contra 11,97 MW de potência
instalada — cerca de 43 % do nominal**. A divergência que vocês encontraram
começa entre 50 % e 75 %.

Ou seja: **a nossa validação de 96 passos nunca exercitou o regime em que o
modelo quebra.** O "155 de 155 resolvem o dia" é verdadeiro e não é garantia
para um cenário de irradiância plena. Isso é limitação da nossa validação, não
apenas do modelo, e passou a constar da nossa lista de achados.

---

## 6. Pergunta 3 — as barras de 88 kV com tensão zero

Não são resíduo da separação a partir do `MASTER-GERAL`. São o recorte:

- a camada de alta tensão fica em `_AT/` e é **compartilhada**, porque a malha
  de 88 kV liga as subestações entre si — recortá-la por subestação cortaria
  justamente os trechos que interessam;
- o modelo isolado **não** redireciona `_AT/`, e por isso não tem os
  transformadores de potência. É o que o comentário "sem trafos de AT" diz.

Concordamos que barra declarada e não energizada polui a estatística de vocês,
e que o `Voltagebases` do modelo isolado não precisaria trazer 88 kV. Vamos
limpar.

---

## 7. Pontos menores

**Os 120 geradores com `kv=0.1386` em barra de base 0,1097 kV — [já corrigido].**
`0,1097 = 190/√3`. O `Voltagebases` do pacote de vocês ainda traz `0.215` e
`0.19`, que foram removidos depois porque **nenhum** transformador da concessão
os declara. Com eles na lista, o `CalcVoltagebases` casava barras de 240 V com
base de 190 V. Na versão atual a lista de tensões de baixa sai do censo da
própria base convertida.

**O `VAO_` sem corrente nominal na DTIR.** Procede, e continua aberto. Dar ao
vão a ampacidade certa exige a bitola do condutor de cabeceira, que não está
disponível no momento em que o vão é escrito. Não quisemos improvisar um valor,
porque o carregamento do vão é justamente uma das métricas que vocês usam.

**O `kv_mt: 34.5` da DALP com a rede em 13,8 kV.** Vocês leram certo: o campo é
a tensão da **barra de entrada**, não a predominante da rede. O nome é ruim e
vamos separar em dois campos.

---

## 8. O que entregamos, e quando

Uma regeração completa das sete bases está agendada para a madrugada de
**12/08**, já com a correção da seção 3. Dela sai um pacote novo da Enel SP,
com:

- a tensão de cabeceira consistente entre o modelo isolado e o geral;
- a lista de tensões de base derivada do censo da própria base;
- procedência gravada em cada modelo — o commit exato do código que o gerou, e
  se a árvore estava limpa.

O que **não** estará resolvido nesse pacote: a convergência com irradiância
acima de 50 %, o `normamps` do vão e a limpeza das barras de 88 kV no modelo
isolado.

---

## 9. Sobre a aproximação — item 7 de vocês

Vocês perguntaram qual das três aproximações consideramos menos danosa.
Recomendamos a primeira, **reduzir a irradiância**, e com um argumento melhor
do que "é a menos ruim":

A curva medida de janeiro em São Paulo tem pico em torno de **43 % da potência
instalada**. Rodar com ela não é aproximação — é o dado. E o dia fecha 96/96
com 5,1 MW de geração na DALP. Cem por cento simultâneos nos 4.218 inversores
é teste de esforço, não cenário de janeiro.

As outras duas nos parecem piores: representar a geração como carga negativa
descarta o modelo de inversor, que é justamente o que vocês querem exercitar;
e redistribuir a injeção realocada muda a topologia sem que se saiba o efeito.

**A ressalva honesta:** se o estudo de armazenamento depende exatamente do caso
de alta penetração, essa aproximação não serve, e o defeito precisa ser
resolvido. É trabalho nosso e está registrado como aberto.

---

## 10. Como reproduzir o que está acima

Com o pacote novo, a partir da raiz dos modelos:

```bash
python verifica.py MODELOS_SP_V10 --se DALP
python energia.py MODELOS_SP_V10 --se DALP
python validador.py MODELOS_SP_V10 --ses
```

A varredura de irradiância da seção 4 usa apenas `opendssdirect`, com o modelo
como vem, em modo diário de 96 passos de 15 min, aplicando
`BatchEdit PVSystem..* irradiance=<fator>` antes do laço. O teste do
aterramento é o mesmo, trocando `BatchEdit Reactor.NEUTRO* R=<valor>`.

---

## 11. Agradecimento, e um pedido

O relatório de vocês foi preciso o bastante para que a causa da seção 3 fosse
localizada em algumas horas, e honesto o bastante para listar o que já tinha
sido descartado — o que nos poupou de refazer quatro testes.

Se puderem, avisem quando rodarem o pacote novo, sobretudo se a tensão da DALP
não subir como a tabela da seção 3 prevê. Um resultado que não se reproduz na
máquina de outra equipe é exatamente o que precisamos saber antes de publicar.
