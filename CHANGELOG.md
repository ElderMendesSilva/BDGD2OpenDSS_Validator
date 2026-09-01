# Histórico de versões

Este arquivo registra **o que cada versão garante e o que ela não faz**.
Limitação escrita é limitação; limitação descoberta pelo usuário é defeito.

O detalhe de cada mudança está no Git; os achados numerados, com método e
número, estão em [docs/ACHADOS_GENERALIZACAO.md](docs/ACHADOS_GENERALIZACAO.md).

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

- **25,70% dos trechos de MT modelados no país não chegam eletricamente à
  fonte.** Só 27 das 97 bases declaram uma subestação mediana conexa.
- **Em 40 de 81 bases, a perda técnica declarada é menor que o ferro dos
  próprios transformadores cadastrados** — a declaração não fecha consigo
  mesma, e isso não depende do nosso modelo.
- **Um quinto das bases repete o mesmo valor de perda declarada**, o que a
  caracteriza como valor padrão e não como medição.

## Antes da 1.0

O projeto rodou de fevereiro a agosto de 2026 sem numeração, identificado por
commit e por sufixo de rodada (`V9` a `V25`). `MODELOS_V9/LINHA_DE_BASE.md` é a
linha de base declarada daquele período e está versionada de propósito.
