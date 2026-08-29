# As 30 bases do estudo da baixa tensão

Montada em 29/08/2026, a partir de `medicoes/bt_completude_97.json` — a medição
de completude da BT nas 97 bases, feita lendo `.gdb` sem simular nada.

## Por que 30, e por que estas

A pergunta é se dá para modelar a baixa tensão, e **o que prevê quando não dá**.
A hipótese de 26/08 era metros de BT por transformador: Roraima 270 funciona,
Enel CE 812 e Light 888 falham. Cinco pontos.

As 97 medidas enfraqueceram a versão simples. O `m/trafo` mediano é 414, a
faixa vai de 32 a 976, e **12 bases passam de 800** — a Light vira a 5ª e a
Enel CE a 8ª, deixando de ser extremas. Pior: a Equatorial GO tem **918 m/trafo
com 68 m/UC** (rural, onde secundário longo é normal) enquanto a Light tem
**888 com 17 m/UC** (metropolitana, onde não é). Se existe previsor, é
`m/trafo` **combinado com densidade**, não `m/trafo` sozinho.

Por isso a amostra tem três grupos com papéis distintos, e não uma varredura
uniforme:

| grupo | n | para que serve |
|---|---:|---|
| **as 7 originais** | 7 | calibração: o desfecho de 5 delas já é conhecido |
| **dado incompleto** | 7 | o diagnóstico já as reprova sem simular (`BT NÃO CHEGA NO TRAFO`, `RAMLIG INCOMPLETO`). Se falharem, o critério de entrada se confirma de graça |
| **espaço** | 16 | 4 por quadrante de `m/trafo` × densidade, pegando os extremos de cada um |

Isso separa três causas hoje confundidas: **dado incompleto**, **secundário
longo** e **densidade**.

## A BT2 refutou a hipótese — 29/08/2026

Dez bases de 32 a 955 m/trafo, com o nome de linha já corrigido. **Nove das
nove modeláveis passaram, com TODAS as subestações `OK`:**

| m/trafo | m/UC | base | SEs | OK | cargas s/ tensão | perda mediana |
|---:|---:|---|---:|---:|---:|---:|
| 32 | 18,7 | CERALDIS4248 | 6 | 6 | 3 | 8,31% |
| 126 | 49,5 | CERPRO5384 | 8 | 8 | 14 | 9,34% |
| 241 | 32,4 | CERIS5382 | 15 | 15 | 95 | 7,33% |
| 340 | 120,0 | CERTHIL527 | 11 | 11 | 0 | 5,79% |
| 434 | 29,1 | ELETROCAR398 | 4 | 4 | 1 | 6,49% |
| 538 | 89,2 | CEREJ5352 | 18 | 18 | 0 | 8,75% |
| 642 | 47,7 | COOPERA5370 | 2 | 2 | 22 | 3,38% |
| 727 | 25,6 | CERGAL5353 | 2 | 2 | 3 | 4,97% |
| **835** | **17,1** | **MUX_ENERGI401** | 1 | 1 | 2 | **4,85%** |

A décima, CERCOS5377 (955 m/trafo), tem **zero subestações na BDGD** — não há o
que modelar, então não conta nem a favor nem contra.

**A MUX_ENERGI401 é a que decide.** 835 m/trafo com 17,1 m/UC é a assinatura
exata da Light — secundário longo em rede densa — e ela rodou com perda de
4,85% e duas cargas sem tensão. Se a hipótese valesse, ela teria falhado.

As perdas ficam entre 3,4% e 9,3%, que é faixa plausível de rede real, e as
cargas sem tensão vão de 0 a 95 — contra os **92% da Light**. Não há gradiente:
o `m/trafo` não ordena nada nesta faixa.

**Conclusão: `m/trafo` não prevê a viabilidade do `--bt completo`.** A
correlação dos cinco pontos originais era coincidência, ou o mecanismo é de
ESCALA e não de topologia — as duas que falham têm milhões de UCs, e nenhuma
base pequena reproduziu o defeito, por mais comprida que fosse a secundária.

Isso reorienta o estudo: a pergunta deixa de ser "que atributo de topologia
prevê" e passa a ser **"o que muda com o tamanho"**. E torna a BT4 — as
grandes — a rodada que importa, em vez de mera confirmação.

## Por que em duas rodadas, e não uma

As 30 somam **52 milhões de UCs**. A BT2, com 151 mil, levou ~15 min em dez
correntes. Escalando, as 30 pedem quase um dia de cluster — e o cluster é
compartilhado com o laboratório.

E o custo não se distribui: **13 bases carregam 51 dos 52 milhões**. A Cemig
sozinha tem 11,3 M de UCs e, no modo completo, multiplica os elementos por ~15.
No agregado ela já pede 48 GB; no completo pode passar dos 251 GB de um nó
inteiro — ou seja, pode ser **impossível**, não apenas lenta. Isso se descobre
com ela isolada, não no meio de uma rodada de 30.

### BT3 — as 5 intermediárias, com METADE do teto

A BT2 mudou a prioridade. Varrer `m/trafo` em bases pequenas já foi feito e não
mostrou nada: as 17 pequenas confirmariam o óbvio. O que ninguém sabe é **onde
a escala começa a quebrar** — entre as centenas de milhares de UCs que
funcionam e os milhões que falham.

Por isso a BT3 são as cinco bases da faixa intermediária, entre 900 mil e 2
milhões de UCs. Elas somam **6,7 M**, cerca de 44 vezes a BT2:

| base | UCs | m/trafo | m/UC | papel |
|---|---:|---:|---:|---|
| ENERGISA_R369 | 934.877 | 165 | 25,9 | dado incompleto |
| AMAZONAS_E7019 | 941.962 | 205 | 21,3 | dado incompleto |
| ENERGISA_S6587 | 1.066.358 | 326 | 17,1 | espaço |
| NEOENERGIA40 | 1.814.910 | 899 | 34,8 | espaço |
| CEEE_EQUAT5707 | 1.972.986 | 531 | 25,3 | dado incompleto |

A faixa de `m/trafo` (165 a 899) segue coberta, então se a topologia importasse
em alguma escala, aqui ela apareceria junto com o efeito de tamanho.

**Orçamento pela METADE do da V24**, por decisão explícita de não monopolizar um
cluster compartilhado: `ORCAMENTO=80` e `ORCAMENTO_GB=240`, contra 160/480. Com
menos correntes abertas as bases enfileiram e a rodada demora mais — e isso é
aceito de propósito. Uma rodada lenta que não incomoda o laboratório vale mais
que uma rápida que rende telefonema.

    SUFIXO=BT3 BT=completo TAMPA=8 GB_POR_NUCLEO=12     ORCAMENTO=80 ORCAMENTO_GB=240     SO="ENERGISA_R369 AMAZONAS_E7019 ENERGISA_S6587 NEOENERGIA40 CEEE_EQUAT5707"

Três das cinco têm dado incompleto pelo diagnóstico (`BT NÃO CHEGA NO TRAFO`).
Se elas falharem e as outras duas passarem, a causa é **dado**, não escala — e
o critério de entrada se resolve sem simular nada.

### BT4 — as 13 grandes, depois

    SO="CMIG SP CPFL LT NEOENERGIA43 ENCE RGE396 EQPA CEEE_EQUAT5707 \
        NEOENERGIA40 ENERGISA_S6587 AMAZONAS_E7019 ENERGISA_R369"

| base | UCs | estimativa sozinha |
|---|---:|---:|
| CMIG | 11,3 M | ~19 h |
| SP | 8,3 M | ~14 h |
| CPFL | 5,1 M | ~8,5 h |
| LT | 5,0 M | ~8,3 h |
| NEOENERGIA43 | 4,5 M | ~7,5 h |
| ENCE | 4,1 M | ~6,8 h |

**Não submeter as 13 juntas.** Ordem sugerida: primeiro as seis abaixo de 2 M
(`ENERGISA_R369`, `AMAZONAS_E7019`, `ENERGISA_S6587`, `NEOENERGIA40`,
`CEEE_EQUAT5707`), que cabem numa tarde; a Cemig **isolada e por último**,
com `SOZINHA="CMIG:32"` e `GB_POR_NUCLEO` alto, para descobrir se ela cabe
sem arrastar as outras se não couber.

A estimativa assume tempo linear com o número de UCs, o que é chute — o modo
completo pode escalar pior. Tratar como ordem de grandeza, não como previsão.
