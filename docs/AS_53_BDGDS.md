# Expansão para 53 BDGDs — síntese

**Fonte:** ranking de complexidade ANEEL (2024). A amostra atual cobre sete
concessões. O objetivo não é baixar todas as 53 de uma vez, mas testar variação
de cadastro, porte e região sem misturar safras.

## Próxima amostra recomendada

Baixar a mesma safra das bases atuais (2024-12-31, V11):

| Grupo | Bases | O que testa |
|---|---|---|
| Mesma holding | Enel RJ, CPFL Piratininga, Equatorial MA, Energisa MT | Se diferenças são locais ou do grupo. |
| Cobertura nova | Coelba, Copel, Elektro, CEA | Nordeste, Sul, interior paulista e máxima complexidade. |

Se CEA não publicar a safra, usar Amazonas Energia. Para a ponta pequena,
Roraima já é evidência suficiente; não é necessário baixar DME-PC apenas por
porte.

## Regras de expansão

- Usar o código ANEEL como identificador estável; o nome comercial varia.
- Não misturar safra/versão, pois isso invalida comparação de perdas.
- O descobridor de bases já encontra automaticamente novas .gdb; nenhuma
  lista fixa deve ser adicionada ao código.
- A cada nova concessão, conferir códigos de tensão desconhecidos, coerência
  R1×CNOM, clima, tensão CTMT versus parque e reguladores desconectados.

## Capacidade

As sete bases conhecidas somam cerca de 45 GB. A expansão sugerida pede mais
40–50 GB; a população completa pode ocupar 200–300 GB mais os modelos. Medir
o tempo na primeira rodada: tamanho do arquivo não prevê sozinho o custo de
conversão.
