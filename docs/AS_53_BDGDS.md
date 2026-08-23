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
