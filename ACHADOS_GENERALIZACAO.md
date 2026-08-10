# Achados da generalização

Passo 3 do `PLANO.md`: rodar outras BDGDs **sem consertar nada**, anotando o que
quebra. Cada achado aqui vira caso de teste no passo 4 e correção no passo 5.

Todas as bases são V11 com data-base 2024-12-31, a mesma da Enel SP — as
diferenças observadas são da distribuidora, não da versão do formato.

---

## Roraima Energia (370) — 10/08/2026

```bash
python converter.py "Roraima_Energia_370_2024-12-31_V11_20250924-1424.gdb" --saida MODELOS_RR
python verifica.py MODELOS_RR
python validador.py MODELOS_RR --ses
```

Opções todas no padrão. **Nenhuma linha de código alterada.**

| | Enel SP (390) | Roraima (370) |
|---|---:|---:|
| subestações | 155 | 20 |
| alimentadores | 1.806 | 89 |
| transformadores de distribuição | 159.061 | 27.700 |
| condutores na SEGCON | 3.498 | 153 |
| tempo de conversão | 48,2 min | **1,9 min** |
| sadias nos dois motores | 155/155 | **19/20** |
| sem ressalva no validador | 131/155 | 12/20 |

**O conversor rodou numa segunda distribuidora na primeira tentativa.** É o
resultado mais importante do dia, e não era garantido.

### Achado 1 — BUG REAL: transformador de barra duplicado

Bloqueia a compilação de 1 das 20 subestações.

```
(#266) Duplicate new element definition: "Transformer.TRB_5003585_34p5"
```

**Mecanismo** (`bdgd2dss/subtransmissao.py:399-413`): o dicionário `derivadas` é
indexado por `(sub, barra_original, kv_alimentador)`, mas o transformador de
barra é nomeado `TRB_{sub}_{kv}` — **sem a barra original**. Uma subestação com
duas barras originais distintas que precisem de derivação na mesma tensão gera
dois transformadores com o mesmo nome.

Na Enel SP nunca disparou: lá nenhuma subestação tinha duas barras originais
demandando o mesmo nível derivado. É bug de nascença, exposto pela segunda base.

*Correção candidata:* nomear a partir de `nova` (a barra derivada), que já é
única por chave — `TRB_{nova}`.

### Achado 2 — a previsão de fragilidade errou de tabela

Eu havia ranqueado os códigos de tensão como fragilidade nº 1, esperando que
`CTMT.TEN_NOM` quebrasse. **Não quebrou:** Roraima usa só `49` (13,8 kV) e `72`
(34,5 kV), ambos já mapeados. Zero alimentadores com tensão adivinhada — contra
os códigos `27` e `62` que aparecem na própria Enel SP.

Quebrou em **outra tabela**, que eu não tinha auditado:

```
AVISO: codigo de tensao '82' desconhecido em EQTRAT.TEN_PRI — adotando 88.0 kV
AVISO: codigo de tensao '30' desconhecido em EQTRAT.TEN_SEC — adotando 13.8 kV
```

O padrão de 88 kV vem do censo das barras da Enel SP. Se a subtransmissão de
Roraima operar em outro nível, o primário dos 29 transformadores de potência
está errado — e o conversor avisa uma vez e segue. **Verificar qual é o nível
real antes de usar este modelo.**

### Achado 3 — limiar calibrado na Enel SP aplicado a outra concessão

`bdgd2dss/diagnostico.py:49` traz `KM_ALIM_ALTO = 60.0`, e a mensagem de
`REDE_EXTENSA` carrega o literal *"mediana da concessao: 8,9 km"*. Os dois saem
do censo da Enel SP.

Em Roraima os alimentadores têm **288 a 424 km** — 4 das 20 subestações caem em
`REDE_EXTENSA`. A classificação em si é defensável (queda de tensão fisicamente
real em alimentador de 400 km, não acionável), mas **o número de referência na
mensagem é falso para esta base**, e o limiar de 60 km foi escolhido olhando
outra distribuidora.

É o exemplo exato do que o plano prevê: limiar calibrado numa base só não
generaliza. A mediana tem de sair da base sendo convertida.

### Achado 4 — clima de São Paulo aplicado em silêncio

```
clima: Janeiro medido — irradiancia media 0.2590 kW/m2, ambiente 19.3 a 26.1 C
```

Números **idênticos** aos da conversão da Enel SP. O padrão do `--clima` aponta
para a pasta de dados de São Paulo, e Roraima fica perto do equador. Não há
aviso: o modelo sai com irradiância e temperatura ambiente paulistas.

Pior que quebrar, porque passa silencioso. O conversor precisa exigir clima da
região ou recusar-se a usar o de outra, e o auditor precisa reportar qual clima
entrou.

### Achado 5 — `TEN_LIN_SE` com tensões de MT e com fase-neutro

32 dos 27.700 transformadores (0,12%) declaram no campo de tensão de linha do
secundário valores que o `Voltagebases` não contém:

| valor | n | leitura |
|---|---:|---|
| 13,8 | 11 | tensão de MT em campo de BT |
| 5,0 | 8 | a verificar |
| 4,207 | 7 | a verificar |
| **7,96** | 6 | **13,8 / √3** — fase-neutro em campo de fase-fase |

O `7,96` é diagnóstico: é a mesma classe de erro que o `_FN_PARA_FF` já trata em
BT (`0,127 → 0,22`), agora aparecendo em MT. Sugere trocar a tabela fixa por uma
**regra**: se o valor bate com um nível conhecido dividido por √3, é fase-neutro.

### Achado 6 — identificadores de subestação numéricos

Roraima usa `5003585`, `1018819824`; a Enel SP usa mnemônicos de quatro letras
(`DABR`, `TBAN`). Nada quebrou, mas nomes de pasta, de medidor e de arquivo
passam a ser numéricos — e o `de-para de 86 mnemônicos`, construído à mão para a
Enel SP, foi aplicado a Roraima assim mesmo (267 âncoras). **Verificar se casou
algo indevidamente.**

### O que NÃO quebrou, e vale registrar

- **As 24 tabelas que o conversor procura estão todas presentes.** Nenhuma
  ausente. É a primeira evidência real de que o esquema da ANEEL é padronizado —
  premissa em que o projeto inteiro se apoia e que até aqui era só esperança.
- **A dependência das planilhas da ISA degradou como projetado:** `0 com trafo
  da ISA, 6 com equivalente`, sem erro.
- **O ajuste auto-calibrado de R1 funcionou na base nova:** 8 dos 153 condutores
  tiveram a resistência substituída, calibrando na própria SEGCON de Roraima.
  É a peça que já generaliza, e agora está demonstrado.

### O que este teste NÃO responde

A pergunta central — se o viés de 1,88× nas perdas é da Enel SP ou da conversão
— **continua aberta**. Roraima tem 89 alimentadores contra 1.806, e a
distribuição de causas é diferente demais para comparar: 4 de 20 subestações são
`REDE_EXTENSA` por alimentadores de 300 a 400 km, situação que quase não existe
na Enel SP. Falta rodar `energia` e `valida_perdas` aqui e, principalmente,
rodar uma base de porte comparável — CPFL Paulista ou Light.
