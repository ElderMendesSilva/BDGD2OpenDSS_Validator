# PBS na prática — regras transferíveis

## Antes de submeter

- Descobrir com um humano a cota total de núcleos/memória e tratar a soma de
  todos os jobs como teto.
- Identificar a variante de PBS e verificar que ncpus e memória solicitados
  foram efetivamente concedidos por qstat -f.
- Executar um job curto no nó de execução: ele pode ter Python, Git, disco,
  variáveis e internet diferentes do nó de acesso.
- Compilar o projeto no Python real do nó; validação sintática local não
  substitui o interpretador de destino.

## Regras de segurança e confiabilidade

- Usar dependências PBS para limitar concorrência; não depender de um laço ou
  de vigilância manual.
- Começar com doutor.py e um canário. Capturar stderr de falhas.
- Conferir artefatos gerados, não a ausência de jobs na fila.
- Não usar escrita concorrente de um JSON de resumo; cada job publica o seu
  resultado e uma etapa posterior consolida.
- Passar o commit pela submissão e distinguir “repositório limpo” de “Git não
  pôde ser consultado”.
- Não apagar em conta compartilhada: use rodada/sufixo novo e revisão humana
  para qualquer remoção.

## Diagnóstico mínimo

    qstat --version; qstat -q
    pbsnodes -l
    df -h /home /tmp /scratch 2>/dev/null
    python3 -V
    qstat -f <jobid>

Se o trabalho é independente por base, mais nós não ajudam sem comunicação
entre processos; dimensione um nó pelo número de núcleos e memória realmente
utilizáveis.
