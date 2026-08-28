# Enel SP para otimização — uso seguro

## Pode usar com confiança relativa

- reconfiguração e análise topológica de MT;
- posição de capacitores ou GD em barras de MT;
- comparação relativa entre alternativas na mesma subestação saudável.

## Não usar como valor absoluto

- perda técnica em kW/% ou comparação direta com meta regulatória;
- faixa de tensão como restrição rígida em toda a base;
- decisões abaixo do transformador MT/BT;
- potência de GD como retrato de pico: ela deriva de energia e de curvas.

## Limitações relevantes

- O modelo agregado não contém rede física de BT.
- Há alimentadores com cadastro/tensão/condutor implausível; usar as saídas do
  validador antes de escolher uma subestação.
- Cenários de geração extrema exigem atenção especial a fases e convergência.

## Seleção e checagem

Prefira subestações sem cargas mortas, NaN, regulador saturado ou perda de MT
implausível. Antes de usar qualquer caso: compile o MASTER, resolva, confira
convergência, tensão mínima, cargas sem tensão, perda e ampacidade.

Regra prática: resultados topológicos e comparações relativas são mais
defensáveis que números absolutos de perda/tensão. Cite explicitamente essas
limitações em qualquer estudo NSGA-II.
