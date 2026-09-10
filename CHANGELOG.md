# Histórico de versões

Este arquivo registra **o que cada versão garante e o que ela não faz**.
Limitação escrita é limitação; limitação descoberta pelo usuário é defeito.

O detalhe de cada mudança está no Git; os achados numerados, com método e
número, estão em [docs/ACHADOS_GENERALIZACAO.md](docs/ACHADOS_GENERALIZACAO.md).

## 1.1.0 — em aberto (safra 2025-12-31)

Fecha a safra BDGD **2025-12-31**, que a 1.0 declarava não validar. Última
rodada completa: **V32**, com 99 bases e 4.078 subestações.

### O que ela garante

- **99 distribuidoras** da safra 2025, **4.078 subestações**, com **80,2% de
  veredicto `OK`** e **uma única** subestação em `MODELO_QUEBRADO` — falha de
  modelo deixou de ser a limitação dominante (era 1.250, ou 30,7%, na V27).
- **`_procedencia.json` grava a safra**, a data-base e o nome do `.gdb` de
  origem, com teste travando os três campos. Na 1.0 o nome da pasta não
  carregava a safra e comparar duas rodadas de safras diferentes era erro
  fácil e silencioso.
- **1.032 testes.**

### O que mudou no diagnóstico, e por que os números não se comparam com a 1.0

A régua mudou três vezes desde a 1.0, sempre para separar coisas que estavam
na mesma gaveta. **Somar classes para comparar com rodada antiga só funciona
com o mapa abaixo:**

| classe | nasceu em | do que foi separada |
|---|---|---|
| `SUBESTACAO_ILHADA`, `REDE_PARCIAL`, `RAMAIS_SOLTOS` | achado 25 | `MODELO_QUEBRADO` (era 96,7% dela) |
| `PERDA_ALTA`, `SEM_CARGA` | achado 29 | `TENSAO_BAIXA` (era 58% dela) |
| `NAO_CONVERGE_COM_GD` | achado 26 | `MODELO_QUEBRADO` |
| `TENSAO_IMPLAUSIVEL` | achados 1 e 60-B | `TENSAO_BAIXA`, `REGULADOR_SATURADO`, `CARGA_ALTA` |

`diagnostico.SEM_TENSAO` existe no código para reproduzir a contagem antiga.

### Correções de conversão desta versão

- **Regulador com o `RegControl` no lado da fonte** (achado 59). O tape corria
  ao limite e *dividia* a tensão do lado da carga. Corrigido pela direção do
  fluxo; `REGULADOR_SATURADO` caiu de 98 para 12 no país.
- **GD com `kv` fixo de 13,8 kV** (achado 60), mesmo em alimentador de 34,5 kV
  — o `PVSystem` entregava de 0,03x a 4,0x o `Pmpp` conforme a tensão local.
- **Geração cuja energia não cabe na própria potência** (achado 61): 221
  unidades no país passam do teto de 5 MW da mini-GD e somam 10,3% da GD
  declarada. Desligadas em `_GD_IMPLAUSIVEL.dss`, premissa reversível.
- **Percentual publicado sobre solução divergida** (achado 62): 19 das 29
  subestações que não convergem publicavam perda entre 0 e 15%, plausível e
  falsa.

### O que ela NÃO faz

- **Não incorpora as correções dos achados 61 e 62 em rodada nacional.** Elas
  entraram depois da V32; os números acima são da V32 e a V33 é que os refaz.
- **Herda todas as limitações da 1.0 abaixo** que não estejam explicitamente
  corrigidas aqui — em especial a ausência de referência externa.
- **Não explica quatro das subestações do achado 60** que saturam sem serem
  longas nem terem GD desproporcional.

## 1.0.0 — 01/09/2026

Primeira versão declarada. Fecha a safra BDGD **2024-12-31**.

### O que ela garante

- **97 distribuidoras** convertidas de ponta a ponta, **4.201 subestações**,
  **26.655 alimentadores**. Das subestações, **97,4% fecham com veredicto
  `OK`** — compilam, convergem, não têm `NaN` e passam nos limites de tensão e
  ampacidade.
- **Rastreabilidade por modelo.** Cada saída carrega `_procedencia.json` com a
  versão da entrega, o commit, se a árvore estava suja, a versão do Python e a
  do **motor OpenDSS**. `sujo: null` significa "não deu para conferir", que é
  diferente de "conferido e limpo" — a distinção existe porque a confusão entre
  as duas já carimbou uma rodada como reprodutível sem que ninguém verificasse.
- **Saída determinística entre laptop e cluster.** O modo de execução não muda
  nada que seja calculado, e há teste travando isso.
- **804 testes**, incluindo um de ciclo completo que roda
  `converter → verifica → validador` sobre uma `.gdb` de verdade em 3 segundos.
- **Dezessete achados medidos** sobre as 97 bases, com quatro autocorreções
  registradas dentro dos próprios achados — o número velho fica visível.

### O que ela NÃO faz

- **Não calibra contra referência externa.** A âncora nacional de 7,4% de perda
  técnica reprova, não valida. Comparar com o `PERD_*` da própria BDGD é
  comparar com um número que não fecha consigo mesmo (achados 8, 9 e 13), então
  a divergência de 1,42× entre a perda modelada e a declarada está **medida e
  não atribuída**. Nenhuma conclusão por distribuidora deve ser publicada sem
  referência de fora.
- **Não entrega baixa tensão completa como produto.** `--bt completo` roda, mas
  só é confiável onde a rede vem conexa da origem. O critério é medido antes de
  simular — componentes por subestação na BDGD ≤ 3 — e por ele a Enel SP tem
  150 de 155 subestações elegíveis e a Cemig 163 de 412 (achados 16 e 17). Que
  as elegíveis rodem **em escala** ainda não está provado. Não usar os números
  de perda, cobertura ou tensão do modo completo como resultado de produção.
- **Não explica os 0,7% que falham.** As 11 subestações `NAO_COMPILA` e as 18
  `NAO_CONVERGE` estão classificadas, não diagnosticadas uma a uma. O mesmo
  vale para as 76 com `TENSAO_IMPLAUSIVEL`.
- **Não valida a safra 2025-12-31.** Ela saiu em setembro de 2026 e entra na
  v1.1. O código já **recusa** misturar duas safras na mesma rodada, em vez de
  processá-las como se fossem a mesma base.
- **Não modela coordenadas.** O leitor trabalha sem geometria; coordenada
  errada aparece na figura, não no resultado elétrico.

### Fatos de dado que a versão documenta, e não corrige

Não são defeitos do conversor — são o que a BDGD publica:

- **Cerca de 7% dos trechos de MT modelados não recebem tensão** (medido em
  02/09/2026 sobre 4.237 subestações; 19% delas têm zero). O valor de 25,70%
  publicado antes era artefato de `Topology.AllIsolatedBranches`, que reporta
  como isolada a rede alimentada pela segunda fonte de uma subestação.
- **Em 40 de 81 bases, a perda técnica declarada é menor que o ferro dos
  próprios transformadores cadastrados** — a declaração não fecha consigo
  mesma, e isso não depende do nosso modelo.
- **Um quinto das bases repete o mesmo valor de perda declarada**, o que a
  caracteriza como valor padrão e não como medição.

## Antes da 1.0

O projeto rodou de fevereiro a agosto de 2026 sem numeração, identificado por
commit e por sufixo de rodada (`V9` a `V25`). `MODELOS_V9/LINHA_DE_BASE.md` é a
linha de base declarada daquele período e está versionada de propósito.
