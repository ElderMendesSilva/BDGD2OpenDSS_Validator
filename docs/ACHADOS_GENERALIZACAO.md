# Achados de generalização — síntese

**Corte:** 27/08/2026. Este arquivo conserva conclusões, evidências e ações.
O histórico de hipóteses, experimentos intermediários e números de cada rodada
permanece no Git.

## O que o projeto demonstrou

- A BDGD padroniza o **formato**, não a qualidade nem a semântica local do
  preenchimento. O conversor precisa inferir e auditar por concessão.
- Validar somente compilação, convergência ou ausência de `NaN` não basta:
  redes fisicamente implausíveis podem convergir. A validação deve incluir
  tensão, ampacidade, cobertura e balanço de energia.
- O modelo agregado de BT é útil para estudos de MT; `--bt completo` ainda não
  é uma base confiável para perdas ou otimização na baixa tensão.
- A comparação agregada é frágil quando poucos alimentadores implausíveis
  dominam a perda. Sempre publicar agregado, mediana, corte de sensibilidade e
  a parcela contaminada.

## Correções incorporadas

| Tema | Regra consolidada |
|---|---|
| Tensões | Usar `PAC_INI`, `TEN_OPE` e conciliar a tensão declarada com o parque de equipamentos; códigos desconhecidos são relatados, nunca mascarados. |
| AT e fontes | A malha de AT, fontes e barras são modeladas por topologia e nível de tensão; evitar uma fonte fixa de 88 kV e nomes de pátio tratados como barra. |
| Transformadores | Respeitar fases reais dos enrolamentos; um primário bifásico não pode ser escrito como trifásico. |
| Chaves e reguladores | Emitir elementos conectados à rede, preservar o estado aberto e manter reguladores entre chaves no modelo. |
| Leitura e escala | Ler tabelas grandes por fatias/lotes, tratar `dtype` heterogêneo e rejeitar comprimentos nulos antes de gerar DSS. |
| Execução | Ordenar subestações maiores primeiro, retomar etapas concluídas e manter a saída determinística entre laptop e cluster. |

## Limitações e fatos de dado relevantes

- **Enel SP:** o condutor 593 e, em geral, incoerência entre condutor e uso
  explicam grande parte da perda impossível. É um problema de cadastro/uso que
  deve ser marcado, não escondido no agregado.
- **Cemig-D:** há diferença importante ainda não explicada; o desvio não deve
  ser atribuído ao conversor sem evidência adicional.
- **CPFL e Equatorial:** códigos de tensão e redes de níveis misturados podem
  criar alimentadores com tensão incorreta. A correção exige evidência do
  cadastro, não substituição automática por um padrão.
- **Premissa de ligação:** pode energizar uma componente, mas só é aceitável se
  não introduzir perda, corrente ou tensão implausíveis. Convergir não é prova
  de validade física.
- **BT completa:** continua em diagnóstico. Não usar seus números de perda,
  cobertura ou tensão como resultado de produção.

## Validação externa e contaminação

A âncora nacional de 7,4% de perda técnica total da ANEEL é apenas um teste de
reprovação: como o modelo agregado não contém a BT, ultrapassá-la é evidência
de problema; ficar abaixo não prova acerto. A validação preferida é o balanço
de energia medido por alimentador, acompanhado da cobertura e da classificação
de casos degenerados/implausíveis.

Na V22, as sete bases que reprovavam a âncora ficaram entre **2,64% e 8,93%**
após retirar alimentadores implausíveis. A conclusão é que o alvo de análise é
o conjunto de alimentadores contaminantes, não “consertar” bases inteiras.

## Próxima investigação técnica

1. Importar e analisar `resultados/v22/` localmente.
2. Explicar os alimentadores implausíveis apontados nos CSVs de violação.
3. Medir as 21 bases pequenas que fecharam ciclo pela primeira vez.
4. Corrigir a BT completa antes de usar qualquer métrica de baixa tensão.
5. Obter referência externa por distribuidora para completar a validação.
