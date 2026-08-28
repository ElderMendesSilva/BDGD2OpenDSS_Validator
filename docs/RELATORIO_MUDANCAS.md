# Mudanças do conversor — síntese

O conversor evoluiu de uma rede que se apoiava em fontes isoladas para um
modelo integrado de subtransmissão, média tensão e baixa tensão agregada, com
validação automatizada.

## Mudanças de maior impacto

| Área | Consolidação |
|---|---|
| Fonte e tensão | Fonte isolada passou a reproduzir a tensão operacional declarada; tensão e base são conciliadas com o parque. |
| AT | Subtransmissão, pátios, fontes e transformadores respeitam topologia e níveis de tensão. |
| Topologia | Cabeceira declarada, chaves abertas, reguladores e barras derivadas passaram a entrar de forma rastreável. |
| Fases | Transformadores e conexões usam as fases reais, evitando enrolamentos bifásicos escritos como trifásicos. |
| Medição | Perdas usam energia injetada e balanço medido; cobertura e contaminação são publicadas. |
| Escala | Lotes de leitura, ordem de despacho, paralelismo e retomada reduziram tempo sem alterar a saída. |

## Garantias que acompanham mudanças

- correção deve ter teste de regressão;
- premissa de modelagem deve ser explícita e reversível no DSS;
- resultados devem trazer procedência, cobertura e causa acionável;
- nenhuma saída física é aceita apenas porque compilou ou convergiu.

Detalhes históricos, versões e medições de cada correção estão no Git e nos
testes correspondentes.
