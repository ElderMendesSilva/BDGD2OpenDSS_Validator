# Plano de continuidade

**Corte:** 27/08/2026. Objetivo: conversor/auditor BDGD→OpenDSS generalizável,
reproduzível e validado por dados externos, com material para publicação em
2027.

## Estado consolidado

- O conversor já foi exercitado em 97 bases; a V22 fechou 96 ciclos completos
  com procedência de um único commit.
- A suíte é a especificação de regressão; cada defeito encontrado deve virar
  teste antes de uma correção ampla.
- O principal risco deixou de ser “o conversor não roda” e passou a ser
  interpretar corretamente dados locais incompletos ou incoerentes.

## Ordem de prioridade

1. **Trazer `resultados/v22/` e fechar a análise.** Sem os artefatos locais,
   números da rodada não são auditáveis nem comparáveis.
2. **Explicar alimentadores implausíveis.** Usar os CSVs de violação e separar
   defeito de topologia, tensão, ampacidade e cadastro; não descartar dados
   silenciosamente.
3. **Analisar as 21 bases pequenas novas.** Verificar surgimento de classe de
   defeito, cobertura, contaminação e comportamento da âncora.
4. **Consertar `--bt completo`.** Só depois medir contribuição de BT, perdas e
   critérios de baixa tensão.
5. **Completar validação externa por distribuidora.** A âncora nacional serve
   para reprovar, não para calibrar cada concessão.
6. **Expandir a amostra de BDGDs por diversidade/complexidade.** A lista e a
   estratégia estão em `AS_53_BDGDS.md`.

## Critérios de aceite para mudanças

- saída determinística entre modos pessoal e cluster;
- modelos compilam, convergem e não têm `NaN`;
- nenhuma correção reduz cobertura ou piora grandezas físicas sem explicação;
- comparação de perda informa população, cobertura, corte de sensibilidade e
  contaminação;
- commit, comando e versão dos insumos acompanham a rodada.

## Fora de escopo por enquanto

Otimizar desempenho sem medição, usar valores absolutos de perda para otimizar
a BT, ou publicar conclusões por distribuidora sem referência externa.
