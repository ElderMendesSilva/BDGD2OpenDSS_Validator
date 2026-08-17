# Plano para a v1.0 — o que falta, em que ordem, e quanto cada coisa vale

Escrito em 14/08/2026. Prazo do artigo: março de 2027.

Este documento existe para que a pergunta "quanto falta?" tenha resposta
auditável em vez de palpite. A régua abaixo é a definição operacional de
"v1.0 extremamente consistente". Cada critério tem peso, nota de hoje e o que
precisa acontecer para a nota subir.

**Estado hoje: 50%.**  Última mudança: as duas premissas de modelagem
implementadas e fundidas, 15/08/2026 (46% → 50%).

---

## 1. A régua

| # | critério | peso | hoje | contribui |
|---|---|---|---|---|
| 1 | O modelo energiza o que a BDGD declara | 15 | 85% | 12,8 |
| 2 | Compila, converge, sem NaN, nas sete | 10 | 90% | 9,0 |
| 3 | Perda valida contra o declarado nas sete | 20 | 60% | 12,0 |
| 4 | As sete regeradas com o código atual | 10 | 0% | 0,0 |
| 5 | BT modelada ou sua ausência quantificada | 8 | 20% | 1,6 |
| 6 | Camada de AT coerente ou limitação declarada | 4 | 70% | 2,8 |
| 7 | PIP, EQSE, UNSEBT resolvidas ou declaradas | 4 | 30% | 1,2 |
| 8 | Documentação e reprodutibilidade | 4 | 70% | 2,8 |
| 9 | **Robustez de execução** | 8 | 55% | 4,4 |
| 10 | **Cobertura de medição** | 7 | 45% | 3,2 |
| 11 | **Validação contra referência externa** | 6 | 0% | 0,0 |
| 12 | **Sobrevive à próxima safra da BDGD** | 4 | 10% | 0,4 |
| | | **100** | | **50,2** |

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
**Custo: dias. Ganho: 60% → 70%.**

Sobram duas frentes, agora que a forma B está tratada:

1. **O achado 31** — cabeceira alcançada pela `SUB` quando `UNI_TR_AT` aponta
   para o vazio. Vale a subestação 1726751 inteira, 7.803 cargas.
2. **A forma C e o balde `-FC`** — rede estilhaçada em 1.922 componentes, e os
   20 alimentadores da EQPA que somam 11% da MT daquela base. É o menos
   entendido dos três.

Critério de saída: alcance acima de 95% nas sete, ou limitação declarada com
número por base.

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
