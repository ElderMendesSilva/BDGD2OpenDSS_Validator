# Resposta às questões de modelagem — síntese

Documento histórico de 11/08/2026, referente ao pacote MODELOS_V8. As respostas
abaixo preservam as conclusões que continuam relevantes; a versão atual do
projeto e suas limitações estão no README e em ACHADOS_GENERALIZACAO.md.

## Conclusões

1. **Tensão baixa no modelo isolado:** havia inconsistência entre a fonte
   equivalente e o tap do modelo geral. A fonte passou a usar a tensão
   operacional representativa da subestação, em vez do primeiro alimentador ou
   de 1,0 pu fixo.
2. **Não convergência com alta geração:** era defeito de modelagem, reproduzido
   em motores distintos; a causa foi detalhada no adendo.
3. **Validação diária:** resolver os 96 passos da curva medida não prova
   robustez em cenários artificiais de irradiância máxima. Cenário real e teste
   de estresse são verificações diferentes.
4. **Barras de 88 kV no modelo isolado:** são consequência do recorte da camada
   de AT; não devem contaminar estatísticas do caso isolado.
5. **Limites conhecidos:** ampacidade de alguns vãos, dados de BT e certos
   códigos de tensão requerem cautela ou evidência complementar.

## Regra de uso

Resultados de um modelo devem ser interpretados com o modo de modelagem, a
cobertura e a versão da rodada. Não usar um pacote antigo como evidência do
estado atual do código.
