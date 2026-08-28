# Índice do projeto

## Comece aqui

- README.md: instalação, uso e arquitetura do conversor.
- menu.py: interface das ferramentas na ordem operacional.
- doutor.py: diagnóstico do ambiente antes de uma rodada.

## Fluxo principal

1. converter.py: BDGD .gdb → modelos OpenDSS.
2. ligacao.py e ampacidade.py: premissas de modelagem explícitas.
3. verifica.py e validador.py: sanidade elétrica e causa raiz.
4. energia.py, valida_perdas.py e valida_balanco.py: medições e confronto com
   dados da BDGD.
5. auditoria.py: consolidação de resultados de rodada.

## Módulos e suporte

- bdgd2dss/: leitura, conversão e escrita por componente da rede.
- testes/: suíte de regressão baseada em falhas observadas.
- diagnosticos/ e analise/: investigações sobre modelos já gerados.
- cluster/: instalação, planejamento e execução PBS.

## Documentos de continuidade

| Documento | Uso |
|---|---|
| PLANO.md | prioridades atuais e critérios de aceite |
| ACHADOS_GENERALIZACAO.md | conclusões técnicas e limitações |
| ENTRE_MAQUINAS.md | protocolo operacional e estado de rodada |
| CLUSTER.md | execução no Ubiratan |
| AS_53_BDGDS.md | estratégia para ampliar bases |
| NOTA_OTIMIZACAO_ENEL_SP.md | escopo seguro para estudos da Enel SP |

O histórico completo dos documentos resumidos está no Git.
