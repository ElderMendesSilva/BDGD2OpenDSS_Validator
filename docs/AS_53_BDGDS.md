# As 53 BDGDs do país — o que falta baixar para a rodada no cluster

**Fonte da lista:** ANEEL, SGT/STR, *Perdas de Energia Elétrica na Distribuição
2025/2024*, Anexo II — "Ranking de Complexidade das distribuidoras".
São 36 de grande porte (Grupo 1) mais 17 demais (Grupo 2). **36 + 17 = 53.**

A lista não é nossa: é a que a própria ANEEL usa para analisar perdas. Isso
importa porque é contra os números dela que o critério 11 valida.

> **Baixar de:** portal da ANEEL, *Base de Dados Geográfica da Distribuidora*
> — https://dadosabertos.aneel.gov.br/dataset/base-de-dados-geografica-da-distribuidora-bdgd
>
> Pegar a **mesma safra das sete que já temos: 2024-12-31, versão V11.**
> Misturar safras invalida a comparação entre bases.

---

## O que já está em `D:\Elder\Elder\BDGDs` — 7 de 53

O número depois do nome é o **código do agente na ANEEL**. Ele é o
identificador estável: o nome muda com incorporação e o carimbo muda a cada
safra. É ele que aparece em `BASE.DIST` e é por ele que o
`regerar_v10._sigla` monta a sigla das pastas.

| # | distribuidora | código | sigla | .gdb | conversão |
|---|---|---|---|---|---|
| 2 | Equatorial PA | 371 | EQPA | 3,98 GB | 40,1 min |
| 4 | Light | 382 | LT | 5,26 GB | 52,9 min |
| 11 | Enel SP | 390 | SP | — | 48,2 min |
| 13 | Enel CE | 39 | ENCE | 5,35 GB | 21,6 min |
| 23 | Roraima Energia | 370 | RR | 0,32 GB | 1,9 min |
| 25 | Cemig | 4950 | CMIG | 14,83 GB | 148,4 min |
| 33 | CPFL Paulista | 63 | CPFL | 6,35 GB | 85,3 min |

**45 GB** somados (a Enel SP mora em outra pasta). Os minutos são do
`regerar_v10.APELIDO`, medidos, e valem só para a conversão — o ciclo
completo dá ~2,7× isso.

---

## O plano: 15 bases, e não 53

A pergunta foi: já que a BDGD é padronizada, não bastaria uma por
distribuidora? **Não basta, e a prova está na pasta.** Enel CE e Enel SP são a
mesma distribuidora:

| | Enel CE | Enel SP |
|---|---|---|
| razão agregada | **0,92×** | **3,09×** |
| perda declarada | 3,79% | 1,42% |
| achado 49 — CTMT contra o parque | 0 de 678 (0,0%) | 65 de 1.569 (4,1%) |
| achado 50 — regulador pendurado | 8 de 1.056 (0,8%) | **55 de 77 (71,4%)** |
| R1 médio do condutor | 5,307 Ω/km | 1,642 Ω/km |
| cobertura da comparação | 94% | 85% |

Com só a Enel CE, a conclusão seria "Enel está calibrada". A Enel SP está em
3,09× e 71% dos reguladores dela não regulam nada.

**O padronizado é o formato, não o preenchimento.** O Módulo 10 define as
tabelas e a TTEN define os códigos — por isso o conversor lê qualquer BDGD.
Quem preenche é a equipe de cada **concessão**, do cadastro de ativos local.
O `UNI_TR_AT` vazio de Roraima, o `-FC` da Equatorial PA e as 58 chaves sobre
o regulador da CPFL não são política de holding: são prática de concessão.

### As 8 a baixar

**Quatro testam a hipótese da holding.** Se baterem com as irmãs, o corte por
grupo se sustenta e o resto não precisa ser baixado.

| # | distribuidora | o que ela testa |
|---|---|---|
| 9 | Enel RJ | a terceira Enel — contra CE (0,92×) e SP (3,09×) |
| 16 | CPFL Piratininga | a segunda CPFL — contra Paulista |
| 10 | Equatorial MA | a segunda Equatorial — contra PA |
| 24 | Energisa MT | o maior grupo do país, do qual não temos nenhuma |

**Quatro cobrem o que as 7 não cobrem.**

| # | distribuidora | o que ela cobre |
|---|---|---|
| 7 | Coelba | a maior do Nordeste que falta |
| 28 | Copel | prática do Sul |
| 27 | Elektro | interior de SP, outra origem de cadastro |
| 53 | DME-PC | a MENOR das 53 — a ponta onde o conversor nunca rodou |

Com as 7 que já existem, isso cobre o ranking de complexidade da ANEEL do 1º
ao 53º. Estimativa de disco para as 8, extrapolando das 7: **40 a 50 GB**.

### O nome curto do relatório não é o nome do portal

O Anexo II abrevia. O portal usa o nome societário, quase sempre com a marca
do grupo na frente. Isso já custou uma busca frustrada por "DME-PC".

| no relatório | procurar no portal por |
|---|---|
| DME-PC | **DME Distribuição S.A. (DMED)** — Poços de Caldas/MG, CNPJ 23.664.303/0001-04 |
| Coelba | Neoenergia Coelba |
| Elektro | Neoenergia Elektro |
| Celpe | Neoenergia Pernambuco |
| Cosern | Neoenergia Cosern |
| Copel | Copel Distribuição |
| Enel RJ | Enel Distribuição Rio (a antiga Ampla) |
| Equatorial MA | Equatorial Maranhão (a antiga Cemar) |
| Energisa MT | Energisa Mato Grosso (a antiga Cemat) |
| Ame | Amazonas Energia |
| CEA | Companhia de Eletricidade do Amapá |

**O padrão do arquivo**, deduzido dos 7 que já temos:

    <Nome>_<codigo do agente>_<safra>_<versao>_<carimbo>.gdb
    Enel_CE_39_2024-12-31_V11_20250822-1151.gdb

O código do agente vem no próprio nome do arquivo — não é preciso descobri-lo
antes. É ele que o `regerar_v10._sigla` usa para nomear as pastas, e é ele que
aparece em `BASE.DIST`.

**Se a DME-PC não estiver publicada**, qualquer uma do Grupo 2 serve para o
mesmo fim, que é testar a ponta pequena: Cocel, Forcel, Hidropan, Urussanga.
O que importa é ter UMA distribuidora minúscula na amostra, porque todo
defeito que achamos até hoje veio de base grande.

**O critério de corte é cobrir a variação, e não o dono.** Se as quatro
primeiras divergirem das irmãs como CE e SP divergiram, a hipótese cai e a
amostragem passa a ser por complexidade.

---

## Grupo 1 — grande porte (36)

As sete que temos aparecem marcadas.

| # | distribuidora | | # | distribuidora | |
|---|---|---|---|---|---|
| 1 | CEA | | 19 | CEEE | |
| 2 | **Equatorial PA** | ✔ 371 | 20 | CEB | |
| 3 | Ame (Amazonas) | | 21 | EDP SP | |
| 4 | **Light** | ✔ 382 | 22 | Cosern | |
| 5 | Celpe | | 23 | **Roraima Energia** | ✔ 370 |
| 6 | Energisa AC | | 24 | Energisa MT | |
| 7 | Coelba | | 25 | **Cemig** | ✔ 4950 |
| 8 | EDP ES | | 26 | Energisa TO | |
| 9 | Enel RJ | | 27 | Elektro | |
| 10 | Equatorial MA | | 28 | Copel | |
| 11 | **Enel SP** | ✔ 390 | 29 | Equatorial GO | |
| 12 | Energisa RO | | 30 | Energisa MG | |
| 13 | **Enel CE** | ✔ 39 | 31 | RGE Sul | |
| 14 | Energisa PB | | 32 | Energisa MS | |
| 15 | Energisa SE | | 33 | **CPFL Paulista** | ✔ 63 |
| 16 | CPFL Piratininga | | 34 | Celesc | |
| 17 | Equatorial AL | | 35 | Nova Santa Cruz | |
| 18 | Equatorial PI | | 36 | Energisa SS | |

## Grupo 2 — demais distribuidoras (17)

Nenhuma delas está baixada. São pequenas — várias são cooperativas ou
municipais — e devem converter em minutos.

| # | distribuidora | | # | distribuidora |
|---|---|---|---|---|
| 37 | Energisa BO | | 46 | João Cesa |
| 38 | Santa Maria | | 47 | Eletrocar |
| 39 | Sulgipe | | 48 | Hidropan |
| 40 | Cocel | | 49 | Urussanga |
| 41 | DCELT | | 50 | Mux Energia |
| 42 | Forcel | | 51 | Cooperaliança |
| 43 | Energisa NF | | 52 | DEMEI |
| 44 | Chesp | | 53 | DME-PC |
| 45 | Nova Palma | | | |

---

## O que dá para dizer sobre custo, e o que não dá

**Disco.** As 7 que temos ocupam 45 GB e cobrem as maiores do país — Cemig,
CPFL Paulista, Enel SP, Light, Coelba não. Um palpite grosseiro para as 53
fica entre **200 e 300 GB** de `.gdb`, mais a saída dos modelos. Hoje há
262 GB livres no D:, então **o disco vai apertar** e o cluster precisa de
área própria.

**Tempo.** Não dá para extrapolar honestamente. As 7 medidas vão de 1,9 min
(Roraima) a 148,4 min (Cemig-D) só na conversão, e o que manda não é o
tamanho do arquivo e sim o número de subestações e de registros de UCBT. As
46 restantes só terão número depois de rodarem uma vez.

**O que NÃO precisa mudar no código.** O `regerar_v10.descobrir()` acha
sozinho o que estiver na pasta: base nova entra com sigla derivada do nome e
do código do agente, e vai para o fim da fila, ordenada por tamanho. Não há
lista de `.gdb` no código, e `testes/test_descobrir_bases.py` tranca isso.

**O que precisa ser conferido a cada base nova**, porque já mordeu antes:

- **códigos de tensão** fora da `TTEN` — o `relatorio_rede.json` traz
  `codigos_tensao_desconhecidos`;
- **`SEGCON.R1` incoerente com a `CNOM`** — o conversor corrige acima de
  7,4× e registra em `condutores_r1_corrigido`;
- **clima da região errada** — o `--clima` recusa dado de outra
  distribuidora, comparando `BASE.DIST` (achado 4);
- **achado 49**, alimentador cujo `CTMT.TEN_NOM` discorda do próprio parque;
- **achado 50**, regulador com um PAC que não existe na rede.
