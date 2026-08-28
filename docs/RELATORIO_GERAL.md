# BDGD → OpenDSS — relatório geral resumido

**Corte:** 27/08/2026. O projeto converte BDGDs em modelos OpenDSS de AT, MT e
BT agregada, executa fluxo de potência/curva diária e confronta os resultados
com medição declarada e auditorias físicas.

## Entrega atual

- Conversão por concessão e por subestação, com masters reutilizando a mesma
  rede para evitar divergência.
- Leitura de tabelas grandes em fatias, geração determinística e retomada de
  rodadas interrompidas.
- Validação de compilação, convergência, NaN, carga sem tensão, tensão,
  ampacidade, perdas e cobertura.
- Execução reproduzível em laptop e PBS, com procedência por commit.

## Resultado de generalização

A V22 percorreu 97 bases e fechou 96 ciclos; a única exceção não possui
subestação declarada. A principal conclusão não é uma razão única de perdas:
cada concessão pode preencher corretamente o formato BDGD e ainda conter
semântica/topologia local incompatível com uma regra fixa.

## O que foi aprendido

- Perda agregada deve ser lida junto de mediana, cobertura e contaminação por
  alimentadores implausíveis.
- Dados de tensão, fase, condutor, regulador, chave e subtransmissão precisam
  de checagem cruzada contra a própria rede.
- Convergência numérica não é garantia de plausibilidade física.
- A baixa tensão agregada é uma aproximação declarada; a BT completa permanece
  em correção.

## Limites atuais

Ainda faltam validação externa por distribuidora, explicação dos alimentadores
implausíveis e uma BT completa confiável. Assim, o projeto é adequado para
conversão auditável e análise relativa de MT, mas não para afirmar perdas
absolutas universais ou resultados de BT sem ressalvas.

Prioridades e estado operacional estão em PLANO.md e ENTRE_MAQUINAS.md.
