# Plano de continuidade

**Corte:** 01/09/2026. Objetivo: conversor/auditor BDGD→OpenDSS generalizável,
reproduzível e validado por dados externos, com material para publicação em
2027.

**O que mudou desde o corte de 27/08:** saiu a safra **2025-12-31** da ANEEL, e
com ela o trabalho ganha uma pergunta que não tinha — se a qualidade do dado
melhorou. A fila abaixo está ordenada por isso.

## Estado consolidado

- 97 bases convertendo, 4.201 subestações, **97,4% com veredicto `OK`**. A V25
  é a rodada corrente, agregada, com clima real.
- Suíte em **789 testes**. É a especificação de regressão: cada defeito vira
  teste antes da correção ampla.
- **Dezessete achados** medidos em `ACHADOS_GENERALIZACAO.md`, que é o
  documento do artigo.
- O risco principal deixou de ser "o conversor não roda" e passou a ser
  interpretar dado local incompleto ou incoerente — e, agora, **comparar duas
  safras sem misturá-las**.

### O que caiu do plano anterior

Os itens 1 a 3 do corte de 27/08 estão fechados: os resultados foram trazidos e
analisados, os alimentadores implausíveis renderam os achados 6 a 11, e as
bases pequenas entraram na medição das 97. O item 4 (`--bt completo`) mudou de
natureza — ver a fila.

## A fila, antes de baixar a safra 2025

### 1. A colisão de tag entre safras — BLOQUEIO

`_sigla()` extrai o código do agente e ignora data, versão e carimbo, o que é
correto e mantém a comparação entre safras: `Sulgipe_46_2024-12-31_V11` e
`Sulgipe_46_2025-12-31_V11` viram os dois `SULGIPE46`. O efeito colateral é
que, **com as duas na mesma pasta**, `descobrir()` devolve a tag duas vezes e
as duas gravam em `MODELOS_SULGIPE46_<sufixo>`.

A rodada misturaria 2024 e 2025 **sem erro nenhum**. É falha silenciosa, o
padrão que já custou três colheitas neste projeto.

**RESOLVIDO EM 02/09/2026, e melhor do que estava planejado.** A guarda passou
a **desambiguar** em vez de recusar: a tag ganha a data-base só nas bases que
colidem (`RR_2024` e `RR_2025`), e a base única mantém a tag de sempre — o que
preserva a comparação com as rodadas anteriores. As duas safras podem ficar na
mesma pasta.

Recusar era defensável em lote e errado quando alguém aponta uma `.gdb`
específica e a irmã dela por acaso mora ao lado: transferia ao usuário um
trabalho que o código sabe fazer. O que continua recusado é a **mesma safra
duas vezes**, onde não há critério para escolher sem inventar um.

O sufixo de rodada já protege parcialmente — `MODELOS_SULGIPE46_V25` e
`_V26` não colidem —, mas só se as safras nunca forem lidas na mesma execução.

### 2. A versão do motor OpenDSS na procedência

Hoje `_procedencia.json` grava commit e versão do Python, **não a do motor**
(nesta máquina, DSS C-API 0.14.5). Nunca importou porque só havia uma safra.

Passa a importar: comparar 2024 com 2025 sem saber se o motor mudou no meio
deixa a diferença sem controle, e uma comparação assim não se sustenta em
revisão.

### 3. O teste de ponta a ponta

Não existe. Os 789 testes são de unidade e módulo; nenhum roda
`converter → verifica → validador → auditoria` e prova que a cadeia funciona
junta. A `.gdb` mínima do `fixture` nem tem `CRVCRG`, então não serve para
isso.

A safra nova é exatamente quando a ausência dói: 130 GB baixados e horas de
cluster para descobrir que uma camada mudou de esquema. Um smoke test sobre
uma base pequena responde em minutos.

### 4. Fechar a v1.0 antes de baixar

Marcar **v1.0 = safra 2024, 97 bases, 17 achados** dá um ponto de retorno e faz
a safra 2025 virar naturalmente a v1.1. Três itens:

- **README desatualizado**, e é o que o repositório promete antes de qualquer
  um rodar: fala em sete distribuidoras e 1.608 subestações quando o real é 97
  e 4.201, e traz uma tabela de razão modelo/declarado que os achados 8, 9 e 13
  desqualificaram como critério.
- **Número de versão**, que não existe em lugar nenhum — nem `__init__.py`, nem
  `pyproject.toml`. Hoje a rodada se identifica por commit, o que serve para
  nós e não para quem baixa.
- **CHANGELOG** com o que a v1.0 garante e o que ela explicitamente **não**
  faz. A limitação da `--bt completo` (item 6) entra aí como declaração, não
  como descoberta do usuário.

Não bloqueia o download, mas bloqueia o rótulo.

## Depois de baixar

### 5. A comparação entre safras — o achado que a safra nova permite

Os dezessete achados foram medidos sobre 2024. Com 2025 na mão o auditor
responde o que hoje não responde: **a qualidade do dado melhorou?**

- Os **25,70%** de trechos que não chegam à fonte (achado 16) caíram?
- As **40 de 81 bases** cujo ferro declarado excede a perda técnica declarada
  (achado 13) continuam as mesmas?
- A Cemig ganhou subestações conexas, ou as 5 com mais de cem componentes
  seguem lá (achado 17)?

Isso transforma o trabalho de "auditamos uma foto" em "medimos a evolução", e
nenhum dos números depende de acreditar no nosso modelo.

**Regra de retenção, com exceção explícita:** a **V25 fica intacta** como
referência da safra 2024. O `CLAUDE.md` manda jogar fora rodada de duas
versões atrás; sem esta exceção alguém apaga a base de comparação achando que
está limpando disco.

### 6. A `--bt completo` deixou de ser "consertar" e virou "delimitar"

O achado 16 deu um critério de entrada barato, medido antes de simular:
**componentes por subestação na BDGD ≤ 3**. O achado 17 o aplicou às duas
grandes: **Enel SP 150 de 155 (96,8%)**, **Cemig 163 de 412 (39,6%)**.

O código já sabe agir sobre isso — `regerar_v10 --se`, `recorte.py
--elegiveis-dir` e `SES_ARQUIVO` no job. Falta **provar que as elegíveis
rodam**: o critério prevê fragmentação, e escala e custo são outra coisa.

Ordem sugerida: piloto com ~15 subestações conexas da Enel SP para medir custo
real por SE; só então as 150. A Cemig depois, e por último as 5 patológicas,
que interessam como caso de estudo e não como rodada.

### 7. Validação externa por distribuidora

Virou **necessária** no achado 7b e continua sendo a única saída do impasse:
nossa perda diverge do `PERD_*`, mas os achados 8, 9 e 13 mostraram que o
`PERD_*` não fecha nem consigo mesmo. Sem referência de fora, o viés de 1,42×
fica sem juiz.

### 8. Os 0,7% que falham

11 subestações `NAO_COMPILA` e 18 `NAO_CONVERGE`, mais **76 com
`TENSAO_IMPLAUSIVEL`**. Estão classificadas, não são surpresa — mas ninguém
abriu para ver se é uma causa só ou vinte.

## Critérios de aceite para mudanças

- saída determinística entre modos pessoal e cluster;
- modelos compilam, convergem e não têm `NaN`;
- nenhuma correção reduz cobertura ou piora grandezas físicas sem explicação;
- comparação de perda informa população, cobertura, corte de sensibilidade e
  contaminação;
- commit, comando e versão dos insumos acompanham a rodada — **incluindo a do
  motor OpenDSS**, assim que o item 2 estiver feito;
- **nenhuma rodada mistura safras**, e o código recusa em vez de avisar.

## Fora de escopo por enquanto

Otimizar desempenho sem medição, usar valores absolutos de perda para otimizar
a BT, ou publicar conclusões por distribuidora sem referência externa.

## Uma nota sobre como as coisas falham aqui

As falhas que mais custaram nesta base de código não quebraram nada: coletor
com sufixo errado publicando vazio com `rc=0`, variável colidindo no PBS, `NaN`
desordenando percentis, medida sobre a camada errada, e agora a colisão de tag
entre safras. Todas passariam por resultado.

Vale desconfiar de número bonito antes de comemorar — e é por isso que o item 1
desta fila é código, e não uma linha de instrução no `LEIA-ME`.
