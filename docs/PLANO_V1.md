# Plano para a v1.0 — o que falta, em que ordem, e quanto cada coisa vale

Escrito em 14/08/2026. Prazo do artigo: março de 2027.

Este documento existe para que a pergunta "quanto falta?" tenha resposta
auditável em vez de palpite. A régua abaixo é a definição operacional de
"v1.0 extremamente consistente". Cada critério tem peso, nota de hoje e o que
precisa acontecer para a nota subir.

**Estado hoje: 53%.**  Última mudança: Fase 1 em curso, 17/08/2026 — duas das
sete bases regeradas (50% → 53%). O critério 4 é uma contagem e sobe 1,4 ponto
por base; a Fase 1 completa leva a régua a ~59%.

**A NOTA NÃO SOBE COM A V16, DE PROPÓSITO — 20/08/2026.** As sete foram
regeradas, mas o critério 4 diz "com o código ATUAL", e o código atual já não é
o da V16: o achado 41 foi corrigido depois dela. A V17 está rodando com ele, e
é ela que fecha o critério 4 em 100% e leva a régua a **60,2%**. Contar duas
vezes a mesma rodada, ou contar uma rodada que o código já superou, é
exatamente o que a régua existe para impedir.

O que a V16 mudou de verdade não foi a nota, foi o mapa: ela **fechou a
hipótese da Fase 2** (ver abaixo) e mostrou que os 20 pontos do critério 3 não
saem de regerar. Ver também a projeção realista no fim deste documento.

---

## 1. A régua

| # | critério | peso | hoje | contribui |
|---|---|---|---|---|
| 1 | O modelo energiza o que a BDGD declara | 15 | 85% | 12,8 |
| 2 | Compila, converge, sem NaN, nas sete | 10 | 90% | 9,0 |
| 3 | Perda valida contra o declarado nas sete | 20 | 60% | 12,0 |
| 4 | As sete regeradas com o código atual | 10 | 29% | 2,9 |
| 5 | BT modelada ou sua ausência quantificada | 8 | 20% | 1,6 |
| 6 | Camada de AT coerente ou limitação declarada | 4 | 70% | 2,8 |
| 7 | PIP, EQSE, UNSEBT resolvidas ou declaradas | 4 | 30% | 1,2 |
| 8 | Documentação e reprodutibilidade | 4 | 70% | 2,8 |
| 9 | **Robustez de execução** | 8 | 55% | 4,4 |
| 10 | **Cobertura de medição** | 7 | 45% | 3,2 |
| 11 | **Validação contra referência externa** | 6 | 0% | 0,0 |
| 12 | **Sobrevive à próxima safra da BDGD** | 4 | 10% | 0,4 |
| | | **100** | | **53,1** |

### Os quatro critérios novos, e por que entraram

Eu vinha medindo com oito. Ao escrever o plano, quatro coisas que a régua
antiga não cobria se mostraram capazes de derrubar a ferramenta inteira:

**9. Robustez de execução.** A Cemig-D quebrou **três vezes**, cada uma mais
fundo: subestação 265 de 413 depois de 5h57, subestação 278 depois de 4h26,
subestação 348 depois de 4h36. Três defeitos diferentes, nenhum reproduzível
nas outras seis. Uma ferramenta que precisa de babá por doze horas não é v1.0,
por mais corretos que sejam os números que ela produz quando enfim termina.

**10. Cobertura de medição.** Quantos alimentadores conseguem sequer ser
comparados com o declarado. Não é o mesmo que o critério 3: dá para acertar a
perda em 100% de uma amostra de 30%. Medido: Enel SP compara **963 de 1.806**
alimentadores (53%), Cemig-D compara **1.787 de 2.456** (73%). O resto fica
sem par ou sem declaração. Um resultado sobre metade da base precisa dizer que
é sobre metade da base.

**11. Validação contra referência externa.** Hoje a ferramenta valida contra
o `PERD_A4` da própria BDGD — o mesmo arquivo que ela lê. Isso é
autoconsistência, não validação. Falta bater contra algo de fora: a perda
publicada pela ANEEL no Módulo 7, ou os dados da ISA que já temos para os
transformadores de AT. Sem isso, o artigo afirma que o modelo concorda com o
cadastro, e não que concorda com a rede.

**12. Sobrevive à próxima safra.** As sete bases são todas `V11`, safra
2024-12-31. Até março de 2027 sai pelo menos mais uma. Se o conversor só
funciona nesta safra, o artigo nasce datado. Barato de testar assim que a
próxima aparecer, e caro de descobrir tarde.

Incluir os quatro derrubou a nota de 42% para 39% no dia em que a régua foi
escrita. A ferramenta não piorou; a régua ficou honesta. (A nota voltou a 42%
depois, pela Fase 0 — e desta vez por trabalho feito.)

---

## 2. As fases

### Fase 0 — achar a causa do 10× da Enel SP  ✅ FECHADA em 14/08/2026
**Custo previsto: dias. Real: uma tarde. Ganho previsto 39% → 44%; real 39% → 42%.**

Causa estabelecida por experimento controlado — **achado 34**. O condutor
`CND_593`, 31 A e 8,232 ohm/km, cobre 2.990 km: 13,5% da rede. Na Enel SP
inteira, 16% da quilometragem carrega 74% da resistência ponderada. Trocando o
R1 dos condutores abaixo de 100 A por um de tronco, a DALV cai de 11,85% para
3,05% e a DANC de 17,53% para 4,88%, enquanto a DIBP — que não tem fio fino —
não se move.

Ficou em 42% e não em 44% porque a causa foi **identificada, não tratada**:
substituir o R1 é decisão de modelagem, igual à forma B do achado 33, e entra
como premissa do artigo. Três opções registradas no achado 34.

Sobrou uma pergunta barata desta frente: **o mesmo censo de condutor nas
outras seis bases**, que não precisa de conversão.

---

### Fase 1 — regerar as sete com o código atual
**Custo: um fim de semana de máquina. Ganho: 44% → 60%.**

É a alavanca única. Leva o critério 4 de 0 a 100, destrava o 3 e o 10, e
exercita o 9. Sem ela, todo número de perda que temos — V10, V11, V12, as sete
bases — foi medido com dois terços da rede desligada em algumas delas e não
vale como resultado.

Ordem: canário primeiro (Roraima, 1,9 min), Cemig-D por último. O
`regerar_v10.py` já retoma de onde parou e já mescla o resumo por base.

Critério de saída: as sete com `validacao_balanco.json`, árvore limpa na
procedência, e a tabela das sete montada de uma vez.

### Premissas de modelagem — decididas e implementadas em 15/08/2026

As duas foram aprovadas pelo Elder e estão no `main`. As duas são
**reversíveis**: cada uma é um `_*.dss` que o MASTER redireciona, e
`regerar_v10.py --sem-premissas` gera a conversão pura, só o que a BDGD
declara. É esse caminho que permite dizer, com número, quanto do resultado
depende de premissa nossa.

**Ampacidade insuficiente (achado 34).** Troca R1 e R0 do trecho cuja corrente
calculada excede a ampacidade declarada, pelo condutor mais fino do catálogo
da própria base que cobre a corrente. Medido: DALV 11,53% → 3,56%, DANC
17,12% → 5,80%, DIBP (sem fio fino) 1,61% → 1,60%.

**Ligação à componente desenergizada (achado 33, forma B).** Liga a barra de
MT da subestação à barra de maior grau da componente que ficou sem tensão.
**Inventa um elo que a BDGD não declara**, e o cabeçalho do arquivo diz isso.
Medido na SUB 1645246100 da Cemig-D: 8.027 → 2.798 cargas sem tensão.

O ciclo passou a ser `converter → ligacao → ampacidade → verifica → …`, nesta
ordem: a ligação energiza rede que estava no escuro, e a ampacidade decide
pela corrente que passa depois disso.

### Fase 2 — fechar o resíduo de alcance
**Custo: dias. Ganho: 60% → 70%. Código pronto em 19/08/2026; a nota espera
a V15.**

As duas frentes previstas eram o achado 31 e a forma C / balde `-FC`. A
primeira estava certa. A segunda estava **olhando para o lugar errado**: medido
o alcance na V14, o resíduo não era a forma C nem os 20 alimentadores `-FC` —
era uma base inteira fora da curva, a Equatorial PA com **55,2% de carga
energizada** contra 99,5% a 100% das outras seis, e em **103 das 119
subestações**.

Foram dois defeitos, os dois corrigidos e medidos:

1. **O achado 31** — âncora pelo trafo da própria `SUB` quando `BARR` está em
   branco e `UNI_TR_AT` aponta para o vazio. Provado: `sem_vao: []` nas duas
   subestações afetadas da Cemig-D, 7.803 cargas de volta à medição.
2. **O achado 38** — o grafo da premissa de ligação tratava chave aberta como
   aresta. Corrigido, e com ele a distinção entre o que é ilha (liga) e o que
   está atrás de chave que a BDGD declara aberta (não liga, e passa a ser
   resultado em vez de resíduo).
3. **O achado 39** — `BARR_2` nomeia o pátio, não a barra: dois níveis de
   secundário escritos na mesma barra faziam a rede do nível perdedor receber
   40% da tensão. Na RIM, perdas de **78,26% → 0,44%**.

Medido em 8 subestações da EQPA: **28.677 cargas sem tensão caem para 11.635**,
59,4% recuperadas. O que resta é **86% um motivo só** — chave aberta declarada.

**A NOTA NÃO SOBE AINDA.** A regra deste documento é que critério só muda com o
número que o justifica, e o número que vale é o da base inteira, não o da
amostra. Sobe quando a V15 medir.

Critério de saída: alcance acima de 95% nas sete, ou limitação declarada com
número por base. **A segunda metade do critério é a que se tornou possível**:
o resíduo agora tem nome e conta.

#### A V16 mediu, e os quatro fios têm resposta — 20/08/2026

As sete bases, com o código de `29b3241`:

| base | sadias | cobertura | razão | viola real |
|---|---|---|---|---|
| Roraima | 20/20 | 89,9% | 2,63× | 3,75% |
| Enel CE | 129/129 | 94,2% | 0,83× | 0,15% |
| Equatorial PA | 119/119 | 91,1% | **0,55×** | 0,00% |
| Enel SP | 155/155 | 87,2% | 3,19× | 2,80% |
| Light | 92/94 | 93,9% | 0,74× | 0,26% |
| CPFL Paulista | 265/265 | 94,6% | 0,88× | 0,58% |
| Cemig-D | — | 76,3% | **0,45×** | 0,95% |

A Cemig-D sai sem `sadias`: o `verifica` completou as 413 subestações e foi
morto pelo limite de 6 h antes de escrever, travado no `shutdown` do pool.
Corrigido em `ebdc207`, com teste.

**O RESULTADO PRINCIPAL DESTA RODADA É NEGATIVO, E É O MAIS IMPORTANTE ATÉ
AQUI.** Energizar rede não move a validação de perda. Nas duas bases onde o
alcance mudou muito:

| | carga energizada | cobertura | razão |
|---|---|---|---|
| Equatorial PA V14 | 55,2% | 91,0% | 0,55× |
| **Equatorial PA V16** | **81,1%** | 91,1% | **0,55×** |
| Cemig-D V14 | 90,0% | 76,3% | 0,45× |
| **Cemig-D V16** | **97,5%** | **76,3%** | **0,45×** |

A EQPA ganhou 26 pontos de carga energizada e a Cemig-D recuperou 382.258
cargas. A cobertura e a razão das duas saíram **idênticas às da V14**, até a
segunda casa.

Isso encerra a hipótese que sustentava a Fase 2 inteira: **o alcance não era a
causa da razão baixa**. A causa é própria, e vai para a Fase 4. Regerar de novo
não vai mexer nesses números — foi o que três gerações mostraram.

#### Os quatro fios da Equatorial PA, e o que a V16 respondeu

1. **Chave aberta declarada** — deixou de ser resíduo com a regra por CTMT.
2. **As 1.526 sem barra na tensão de um vão** — eram **64.726**, e viraram o
   achado 41: comparação de tensão de linha com tensão de fase. Corrigido e
   medido, 78,6% do resíduo de volta em oito subestações.
3. **O balde `-FC`** — virou o achado 40: é a rede de 34,5 kV arquivada sob um
   CTMT que declara 13,8 kV.
4. **A razão de 0,55×** — **não se moveu**, e a pergunta está respondida acima.

O texto abaixo é o de 19/08, mantido porque a previsão de cada fio e o que
aconteceu com ele é o registro que interessa.

#### O que a Equatorial PA deixava em aberto — 19/08/2026

Ela é a base que puxa todos os resíduos, e o que sobra dela tem de continuar
visível depois que a Fase 2 fechar. Quatro fios, com o número de cada um:

1. **As 10.057 cargas atrás de chave aberta declarada** (na amostra de 8
   subestações; 86% do resíduo restante). **Não é para corrigir** — ligar ali
   apagaria o que a BDGD diz. É para *declarar*, com número por base, e é
   exatamente a segunda metade do critério de saída da Fase 2. Falta a contagem
   base a base, que sai da V15.

2. **As 1.526 sem nenhuma barra na tensão de um vão.** Sobraram dos 6.662 do
   achado 38 depois do achado 39 explicar 77% deles. Não sei o que são. É o
   menor dos quatro e o menos entendido.

3. **O balde `-FC` do achado 33** — 20 alimentadores, 218.471 barras, 11% de
   toda a MT da EQPA, com `PAC_INI` na própria barra da subestação e grau 1.
   A investigação de 19/08 mostrou que **não era ele** o resíduo de alcance,
   e isso não é o mesmo que explicá-lo: o que `-FC` significa continua sem
   estabelecer. Vale medir de novo depois da V15, com a rede já energizada —
   pode ser que ele desapareça sozinho, e pode ser que não.

4. **A razão de 0,55×**, a mais baixa das sete. O modelo prevê metade da perda
   que a medição declara. Com 45% da carga sem tensão isso era esperado; com a
   rede energizada, a razão vai mudar, e **em que direção é o resultado que
   interessa**. Se subir para perto de 1, é evidência de que o alcance era a
   causa; se não subir, sobra causa própria e ela entra na Fase 4.

Os quatro só ficam mensuráveis depois de regerar a base inteira. Nenhum deles
justifica segurar a V15 — todos justificam olhar para a EQPA primeiro quando
ela sair.

### Fase 3 — quantificar o que falta e ler o que não lemos
**Custo: uma semana. Ganho: 70% → 82%.**

- **Medir a BT ausente** (critério 5). Comparar `--bt agregado` contra
  `--bt completo` numa subestação média de cada base. A leitura de que a BT
  explicava a razão de 0,41% caiu com o achado 32; o tamanho real nunca foi
  medido.
- **PIP** (critério 7), primeiro por ser universal nas sete e por ser viés de
  1,25% numa direção só. Depois **EQSE**, que traz a ampacidade que falta ao
  achado 21, e **UNSEBT**, que só existe em quatro das sete.
- **Escrever o limite da camada de AT** com os números que já temos (critério
  6): 315 componentes, fontes equivalentes por pátio, órfãs.

### Fase 4 — validar contra o mundo, e contra o tempo
**Custo: uma a duas semanas. Ganho: 82% → 96%.**

- **Referência externa** (critério 11): bater a perda agregada por
  distribuidora contra a publicada pela ANEEL, e a impedância dos
  transformadores de AT contra os dados da ISA que já temos. É o que separa
  "concorda com o cadastro" de "concorda com a rede".
- **Próxima safra** (critério 12): rodar as sete na safra seguinte assim que
  sair, sem tocar no código, e registrar o que quebra.
- **README e INDICE** (critério 8), parados na era pré-AT.

### O que sobra depois — e por que não chega a 100

Os 4% finais não são trabalho de engenharia, são limite do dado. Na Cemig-D,
**43,9% dos alimentadores faturam mais do que recebem** e 49,0% declaram perda
total abaixo de 2%. Quase metade da base não tem medição utilizável como
referência, e nenhum modelo pode ser validado contra ela.

Isso não é pendência: é achado, e precisa aparecer no artigo como limite
declarado. Uma v1.0 honesta chega a **96% e escreve por que os outros 4% não
existem** — não a 100% fingindo que existem.

---

## 3. Caminho crítico

```
Fase 0 (10x da SP)  ──►  Fase 1 (regerar)  ──►  Fase 2 (resíduo)  ──►  Fase 3  ──►  Fase 4
    dias                 fim de semana          dias                  semana      2 semanas
    39% → 44%            44% → 60%              60% → 70%             70% → 82%   82% → 96%
                              ▲
                              └── a decisão da forma B pode entrar aqui e ser
                                  regerada junto, poupando um ciclo inteiro
```

A única dependência dura é **Fase 0 antes de Fase 1**. Se a decisão da forma B
sair antes de regerar, ela entra no mesmo ciclo e a Fase 2 encolhe.

Com folga de sobra para março de 2027 — o risco do cronograma não é tempo, é
descobrir na Fase 4 alguma coisa que obrigue a regerar de novo. Por isso a
Fase 0 vem primeiro.

---

## 4. Como esta nota se move

A nota muda quando um critério muda, e a mudança tem de vir com o número que a
justifica. Sem medição, sem alteração de nota — foi assim que cinco hipóteses
confiantes caíram este mês, inclusive duas minhas no mesmo dia.

---

## Quanto dá para chegar, e quando — 20/08/2026

Escrito porque a pergunta "ate uma V20 estamos em 90%?" merece aritmetica, e
nao otimismo.

**Nao. Somando o ganho realista de TODOS os doze criterios, a regua bate em
88,5%.** E os ultimos 4% deste documento ja explicam por que 100 nao existe.

| criterio | peso | hoje | ganho realista | de onde vem |
|---|---|---|---|---|
| 4 — as sete regeradas | 10 | 29% | **+7,1** | sai com a V17 |
| 3 — perda valida | 20 | 60% | +5,0 | **o gargalo** |
| 5 — BT quantificada | 8 | 20% | +4,8 | e medir |
| 11 — referencia externa | 6 | 0% | +4,8 | precisa de dado da ANEEL |
| 12 — proxima safra | 4 | 10% | +2,8 | depende da safra sair |
| 10 — cobertura de medicao | 7 | 45% | +2,45 | mede metade das bases |
| 9 — robustez | 8 | 55% | +2,4 | ja subiu em 20/08 |
| 1, 2, 6, 7, 8 | 37 | — | +6,1 | incremental |
| | | | **+35,4** | **88,5%** |

### Por que rodada nao resolve

O criterio 3 vale 20 pontos e **nao depende de regerar**. Quatro razoes nao se
mexeram em tres geracoes seguidas, com o alcance mudando muito no meio:

| base | V14 | V15 | V16 |
|---|---|---|---|
| Enel SP | 3,19× | 3,19× | 3,19× |
| Roraima | 2,63× | 2,63× | 2,63× |
| Equatorial PA | 0,55× | 0,54× | 0,55× |
| Cemig-D | 0,45× | 0,45× | 0,45× |

Duas superestimam a perda em tres vezes, duas subestimam pela metade. A EQPA
saiu de 55,2% para 81,1% de carga energizada entre a V14 e a V16 e a razao dela
andou 0,00. Rodar V18, V19 e V20 sem atacar a causa produz esta mesma tabela
tres vezes.

E o criterio 11, que vale 6, esta em **zero**: hoje a ferramenta valida a BDGD
contra a propria BDGD, o que e autoconsistencia e nao validacao.

### O que fazer no lugar

Uma rodada so — a V17, com o achado 41 — e depois **parar de regerar** e gastar
duas semanas nos criterios 3 e 11, que somam 26 dos 100 pontos e nao se movem
com rodada nenhuma.

Meta honesta para o fim de setembro de 2026: **75%**, com o 3 e o 11 atacados.
Os 90% sao conversa de dezembro, e so se a validacao externa fechar.

---

## O usuário roda UMA base, e nós rodamos sete — 23/08/2026

Observação do Elder, e ela reordena o plano.

Nós sofremos 9 h por rodada porque regeramos **as sete** para comparar geração
com geração. Isso é workflow de pesquisa. Quem for usar a ferramenta converte
**uma** BDGD, uma vez por safra.

Tempo real por base, da V18 — a rodada inteira levou 543 min para 141,6 min de
conversão, então o ciclo completo é **3,8× a conversão**:

| base | conversão | ciclo completo |
|---|---|---|
| Roraima | 0,6 min | ~5 min |
| Light | 5,7 min | ~22 min |
| Enel CE | 7,1 min | ~27 min |
| Equatorial PA | 10,5 min | ~40 min |
| Enel SP | 13,1 min | ~50 min |
| CPFL Paulista | 17,7 min | ~68 min |
| Cemig-D | 86,9 min | ~5,5 h |

**A mediana é 40 min.** A Cemig-D, a maior do país, leva 5,5 h — uma vez por
ano. O tempo nunca foi o problema do usuário; é o nosso.

### A inversão que sustenta o argumento

O achado 49 só apareceu porque a Light tinha 25,3% de alimentadores em
desacordo com o próprio parque e a Enel CE tinha 0,0%. Com uma BDGD só,
ninguém veria. **A dor das sete bases é o que torna a ferramenta confiável
para quem roda uma.** O nosso custo é a qualidade do produto do outro.

### O que isto muda no plano, e é bastante

**Sobe para o topo: o critério 8 e a tarefa da portabilidade.** Se o uso é uma
base, "roda em qualquer máquina que clone o repositório" deixa de ser item de
lista e passa a ser o item que decide se existe produto. Hoje toda medição
deste documento saiu de UMA máquina, com UM Python, sobre SETE bases. Software
que só roda num lugar não se comercializa, por melhor que seja o número.

**O cluster NÃO desce — e eu tinha errado isto.** Encurtar a rodada não vale
nada para o usuário, é verdade: ele nunca roda sete. Mas o cluster não é
throughput de MODELO, é throughput de EVIDÊNCIA, e a evidência é o que
melhora a ferramenta. Ver a seção própria abaixo.

**Entra no plano: a distância entre avisar e resolver.** O
`validacao_perdas.json` hoje diz

> ATENÇÃO: 73 alimentador(es) que a distribuidora DECLARA e que o modelo deixa
> sem energia (4,5% da base).

e quem lê precisa conhecer os achados 39 a 50 para saber o que fazer. Um
engenheiro de distribuidora vai ler e perguntar "e agora?". Essa é a distância
que separa validador de produto — e ela é menor do que parece: é documentação
e uma tela, não é código novo.

### O diferencial, dito na forma que se vende

Não é converter BDGD para OpenDSS; isso outros fazem. É **a ferramenta dizer
quando ela está mentindo**: quantos alimentadores entraram na conta, quantos
ficaram de fora e por quê, quais têm perda fisicamente impossível, e como o
resultado se compara com o que a ANEEL publica — e não só com o que a própria
BDGD declara.

---

## O cluster é a máquina de achados — 23/08/2026

Correção de rumo. Eu tinha posto o cluster fora do caminho crítico, com o
argumento de que o usuário nunca roda sete bases. O argumento está certo e a
conclusão estava errada: **o cluster não serve para entregar modelo, serve
para produzir evidência** — e evidência é a única coisa que faz esta
ferramenta melhorar.

### Todo achado deste mês veio de comparar bases

| achado | o que é | o que só se vê comparando |
|---|---|---|
| 40 | o `-FC` de 34,5 kV | Equatorial PA tem 21; as outras seis, zero |
| 41 | tensão de linha contra a de fase | EQPA 64.726 cargas, Cemig-D 17.201 |
| 48 | chave fechada sobre o regulador | CPFL 8; as outras seis, **zero** |
| 49 | CTMT contra o próprio parque | Light 25,3% contra Enel CE **0,0%** |
| 50 | regulador pendurado | Enel SP 71,4% a montante, Roraima 60,0% a jusante |

Cinco de cinco. Nenhum apareceu olhando uma base isolada — todos apareceram
porque **uma base destoava das outras**. Com sete bases enxergamos sete
práticas de preenchimento. Com 53, enxergamos 53.

### O ganho não é de tempo, é de variância

| | em série | em paralelo |
|---|---|---|
| as 7 da V18 | 543 min | ~5,5 h, limitado pela Cemig-D |
| as 53 | acima de 40 h | ~5,5 h, com nó suficiente |

Nas sete o ganho é 1,6× e não justifica nada. **Nas 53 o ganho é o que torna a
varredura possível**, porque uma rodada nacional em série não cabe numa noite
nem numa semana de paciência.

### E o cluster é, de graça, o teste de portabilidade

O nó é Linux, com outro Python, outro escalonador (PBS) e sem o motor COM. É
exatamente o que o critério 8 e a tarefa da portabilidade precisam provar. Já
existem `cluster/instalar.sh`, `cluster/uma_base.pbs` e
`cluster/submeter_todas.sh`, e o ramo `portabilidade-linux` registra o que já
foi descoberto: *"o nó tem ambiente gráfico: painel funciona, COM continua não
existindo"*.

Então o cluster resolve **duas** prioridades ao mesmo tempo — a máquina de
achados e a prova de que o software roda fora daqui. Isso o põe de volta no
caminho crítico, e não como conveniência.

### O que continua valendo do argumento do produto

Que o usuário roda uma base e nunca vai precisar de cluster. O cluster é
ferramenta **nossa**, de desenvolvimento — como a suíte de testes e o canário.
Ninguém compra a suíte de testes, e ainda assim ela é o que faz o produto
existir.

---

## O que o cluster roda, de verdade — 23/08/2026

Eu tinha dito que o cluster não rodaria o `energia` e o `valida_perdas` por
falta dos motores. **Está errado.** Conferido, etapa por etapa, qual motor
cada uma importa:

| etapa | motor | Linux |
|---|---|---|
| `converter.py` | nenhum | roda |
| `ligacao.py` | só `opendssdirect` | roda |
| `ampacidade.py` | só `opendssdirect` | roda |
| `verifica.py` | `opendssdirect` **e** `win32com` | roda com um |
| `energia.py` | só `opendssdirect` | roda |
| `validador.py` | só `opendssdirect` | roda |
| `valida_perdas.py` | **nenhum** — lê JSON e a `.gdb` | roda |
| `valida_balanco.py` | lê JSON | roda |

O `opendssdirect` traz a própria DSS C-API dentro do pacote e é
multiplataforma. **É ele que faz todas as contas do projeto.** Só o `verifica`
toca COM, e lá o COM é um dos dois motores — o código já cai em `capi` sozinho
quando o COM não existe:

```python
ap.add_argument('--motor', choices=['ambos', 'capi', 'com'],
                default='ambos' if plataforma.tem_com() else 'capi')
```

**O que se perde no cluster é UMA coisa:** a conferência cruzada entre dois
motores independentes no `verifica`. E ela pega outra classe de defeito —
modelo que o C-API resolve e o motor da EPRI derruba, que importa porque é o
da EPRI que o usuário abre no OpenDSS. Nenhum dos cinco achados do mês veio
dali; todos vieram de comparar bases.

**Como fechar essa lacuna sem perder nada:** rodar `verifica --motor com` aqui
no Windows, depois, só nas bases que interessarem. Custa pouco, porque só
compila e resolve.

### O `qsub` já roda o ciclo inteiro

`cluster/uma_base.pbs` chama `regerar_v10.py --so $TAG`, que é converter →
ligação → ampacidade → verifica → energia → validador → perdas → balanço. Não
é só o conversor. Uma distribuidora por job, com o canário primeiro:
Roraima aparece em minutos e um código quebrado não desperdiça a fila inteira.

Ajustado em 23/08/2026: **o sufixo padrão passou a ser `V1_cluster`.** Ele
caía em `V18`, que é uma rodada fechada e serve de referência — quem
submetesse sem definir gravaria por cima dela em silêncio, e só descobriria ao
comparar gerações e achar as duas iguais.

`V1_cluster` resolve as duas coisas de uma vez: não colide com a numeração
local (V10 a V19) e **a pasta já diz onde a rodada aconteceu** —
`MODELOS_CMIG_V1_cluster`, `logs/v1_cluster/`. Quando o resultado do cluster
divergir do daqui, o nome sozinho aponta para a diferença de ambiente antes de
alguém procurar no código. Para a segunda rodada, `SUFIXO=V2_cluster`.

**A conferir quando o cluster rodar de verdade:** o `walltime` está em 12 h e a
Cemig-D leva 5,5 h nesta máquina. Se o nó for duas vezes mais lento, ela
encosta no limite. Medir na primeira submissão e ajustar.
