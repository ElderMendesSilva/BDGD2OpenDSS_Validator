# Operação entre máquinas — estado e protocolo

**Corte:** 28/08/2026. Diário detalhado preservado no Git; este é o estado
operacional que deve sobreviver entre sessões.

## Responsabilidades

| Ação | Responsável |
|---|---|
| Submeter/cancelar jobs PBS e alterar a fila | Elder |
| Planejar a rodada, contar recursos, ler logs e analisar resultados | agente |
| Alterar código, testar e publicar commits | máquina local |

Nenhum agente executa operação destrutiva no cluster. Rodadas usam sufixo novo;
uma rodada antiga é aposentada, não apagada.

## Regra: o head node não processa

Determinação do administrador (28/08/2026). No head node (`10.107.1.23`) valem
`qsub`, `qstat`, `qdel`, `git pull`, `scp` e leitura de arquivo pequeno. Não
valem `auditoria.py`, conversão, energia, validação, nem leitura de modelo por
`python` via SSH — isso vai por PBS, ou vira `scp` do JSON e análise local.

Consequência direta: **toda pergunta sobre resultado exige o
`resultados/<sufixo>/` publicado**, porque não há mais como calcular no head
node para responder. Rodada sem o coletor encadeado publicado é rodada que
ninguém analisa sem quebrar a regra.

## Regras do cluster

- Orçamento total: **64 núcleos e 192 GB**, incluindo jobs já na fila.
- `submeter_todas.sh` usa correntes com `depend=afterany`; só submeter com
  `--rodar`. Sem essa flag, o comando deve apenas mostrar o plano.
- O tamanho das bases vem de `medicoes/tamanho_bases.json`. O planejador não
  varre mais as 97 `.gdb` a cada execução; base nova é medida uma vez e entra
  no cache.
- Antes de nova rodada, confirmar fila vazia, commit do nó e cota disponível.
- A rodada deve carregar um único commit, passado na submissão e gravado na
  procedência. “Git indisponível” é diferente de árvore limpa.
- Validar arquivos produzidos; fila vazia nunca significa sucesso.

## Estado mais recente: V22

- 97 bases submetidas; **96 fecharam o ciclo** sob um único commit.
- `CERCOS5377` é a única exceção: declara um alimentador e nenhuma subestação,
  portanto não há rede a modelar.
- Pico medido: 8 correntes, 64/64 núcleos e 192/192 GB.
- As sete bases históricas mantiveram os números da V21; a rodada demonstrou
  robustez de execução, não mudança física relevante.
- As sete reprovações da âncora são dominadas por alimentadores implausíveis;
  após descontaminá-las, o agregado fica entre 2,64% e 8,93%.
- O `auditoria.py` da V22 foi rodado à mão no head node: ela foi submetida com
  o commit anterior ao do coletor encadeado. A próxima rodada não repete isso.

## As 21 bases pequenas

Medido nas que fecharam ciclo pela primeira vez:

- razão mediana contra `PERD_*` declarado: **1,23** (n=12), contra 1,10 a 3,16
  nas sete grandes;
- contaminação, violação real e reprovação da âncora: **zero** em todas;
- **cobertura 0,00% em todas as 21** — nenhum alimentador com medida utilizável.

As duas primeiras linhas só podem ser lidas junto da terceira: elas concordam
melhor com o eixo fraco e não têm o eixo forte para conferir. Nove das 21 nem
razão possuem.

O fato de dado que sai daí: **21 de 21 cooperativas declaram energia faturada
maior ou igual à injetada.** É característica de cadastro, não de rede, e é
afirmação sobre a BDGD.

Pergunta aberta: a ausência de medida utilizável acompanha porte ou é traço de
cooperativa? As 97 respondem por leitura de tabela.

## Catalogação das 1.626 violações da V22, por causa

`analise/investigar_violacoes.py` (main, commit `fa3210d`) separa cada
violação por sinal de SE contra a taxa de FUNDO da rodada — não contra zero.
Resultado: nenhum sinal de topologia de SE se destaca do fundo. O defeito é
de alimentador/condutor, fora do que `resultados/` guarda.

- **17 linhas** já são sintoma de modelo marcado quebrado pela verificação
  (`POTENCIA_NAN`, `NAO_CONVERGE`) — correção em `correcao-se-quebrada`
  (commit `a4698e6`), ainda **não mesclada em `main`**: espera a V22 fechar.
- Das 1.609 reais, **258 sem nenhum sinal de SE**. Catalogadas:
  - **43 — Enel SP:** provável mesmo achado já documentado (condutor 593).
  - **51 — COPELDIS2866, "no limite" (razão 1,01–1,20):** dentro da margem
    que já se trata como "passou raspando"; não necessariamente defeito.
  - **16 — COPELDIS2866, perda absurda (15,8% a 10.309.528,9%):** achado
    NOVO, ainda não documentado. GWh injetado real (6,9–56,6) e milhares de
    UCs por linha — não é artefato de denominador pequeno — e a SE está com
    veredicto `OK`, convergida, sem chave ilhada nem regulador pendurado.
    Convergência não garante plausibilidade física.
  - **18 — denominador minúsculo:** artefato de fórmula, não defeito de rede.
  - **~130 — cauda espalhada em 22 bases pequenas**, sem concentração.

### Pendência para o cluster

Confirmar os 16 casos de COPELDIS2866 exige o modelo aberto, que não está
nesta máquina. Ao rodar a próxima rodada (ou uma isolada de COPELDIS2866):

1. Mesclar `correcao-se-quebrada` antes de submeter, para o CSV não misturar
   os 17 casos de modelo quebrado com os defeitos reais.
2. Depois do ciclo, abrir os 5 piores CTMT de COPELDIS2866 e checar topologia
   por barra — o candidato mais provável é malha fechada por engano ou chave
   mal tratada que a convergência não pega:
   `71080/832100009`, `72857/874280005`, `72866/884720043`,
   `72205/815480008`, `72240/818000004`.
3. Rodar `analise/investigar_violacoes.py resultados/<sufixo-novo>` de novo
   e comparar contagem por causa com a tabela acima.

## Ciclo de trabalho

1. Nó roda e publica resultados rastreáveis.
2. Máquina local importa os CSVs/JSONs e escolhe o pior caso acionável.
3. A máquina local reproduz, corrige, testa e publica o commit.
4. A próxima rodada usa esse único commit e um sufixo novo.
