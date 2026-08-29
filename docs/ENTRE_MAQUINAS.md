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

### Orçamento: 160 núcleos e 480 GB (revisto em 28/08/2026)

O administrador liberou os nós de cálculo — só o head node saiu de cena. Os
três nós somam **768 núcleos e 753 GB**, e com isso o gargalo deixa de ser
permissão e passa a ser **memória**: o dimensionamento pede 3 GB por núcleo,
então usar os 768 núcleos exigiria 2.304 GB, o triplo do que existe.

Por isso o `submeter_todas.sh` passou a ter **dois tetos**, e o menor manda:
`ORCAMENTO=160` núcleos e `ORCAMENTO_GB=480`. Isso dá **20 correntes** em vez
das 8 da V22 — ~2,5x mais paralelo — usando 21% dos núcleos e 64% da memória,
o que deixa folga real para o resto do laboratório, que divide o mesmo cluster.

Contar só núcleo não bastava: sem o teto de GB, subir `ORCAMENTO` estouraria a
memória em silêncio.

### Motor de partida (`RAMPA=90`)

As correntes começam todas pela leitura da `.gdb`. Vinte delas abrindo 127 GB
no mesmo instante disputam o mesmo disco, e a fase mais longa de cada job vira
a mais lenta de todas. A **cabeça** de cada corrente agora larga escalonada
(`qsub -a`), uma a cada 90s: a carga sobe ao longo de ~28 min em vez de saltar.
Não custa relógio no fim, porque só a cabeça espera — os demais jobs já
estavam presos por dependência. `RAMPA=0` desliga.



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
  (commit `a4698e6`), **mesclada em `main` em 28/08/2026** (CEAMAZON), com a
  suíte em 647 testes verdes. O `motivo_da_violacao` passa a checar o
  veredicto da SE antes de qualquer número, e o passo 1 da pendência abaixo
  está cumprido: a próxima rodada já sai com o CSV limpo desse sintoma.
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

## V23 submetida — 28/08/2026, 18:36 (CEAMAZON)

97 jobs (`34475`–`34571`) mais o coletor (`34572`), commit único `e49363c`,
árvore limpa. Sufixo `V23`; a V24 do plano abaixo virou esta rodada.

`ORCAMENTO=160`, `ORCAMENTO_GB=480`, `TAMPA=32`, `RAMPA=90` → 13 correntes,
pico exato nos dois tetos. A rampa funcionou na primeira: corrente 1 em `R`
imediato, correntes 2–13 em `W` com largada a cada 90s (18:37:36 … 18:54:07),
85 jobs em `H` presos por dependência.

**Previsão: ~1,9 h, fechando por volta de 20:35.**

### O que a V22 ensinou sobre tempo (medido nos logs, não estimado)

Extraído de `logs/v22/*.log` pelo carimbo da primeira e da última etapa:

| medida | valor |
|---|---|
| trabalho somado nas 97 bases | 9,8 h |
| relógio real da V22 (8 correntes) | 3,8 h |
| **CMIG sozinha** | **150 min — 25% de todo o trabalho** |
| mediana por base | 0,5 min |
| 2ª mais longa (NEOENERGIA47) | 39 min |

**A distribuição é brutalmente desigual**, e isso muda como se planeja rodada:
metade das bases termina em meio minuto, e uma única base carrega um quarto do
esforço. Subir o número de correntes não ataca isso — é Amdahl. Com `TAMPA=8`
a previsão era 3,1 h, quase toda ela esperando a Cemig.

**O gargalo era `TAMPA`, não o orçamento.** O `regerar` passa `--jobs` e o
`plataforma.nucleos()` respeita a fatia do PBS corretamente — então a Cemig
convertia suas 341 subestações de 8 em 8 só porque `TAMPA=8` a limitava. A 16
núcleos ela cai para ~86 min e o caminho crítico vai de 3,1 h para 1,9 h. Foi
o maior ganho da noite, e custou uma variável de ambiente.

Nenhuma base alcançou o patamar de 32 (`.gdb` ≥ 20 GB): o maior `ppn` atribuído
foi 16, então `TAMPA=32` operou de fato como `TAMPA=16`.

### A conferir quando a V23 fechar

1. Tempo real contra a previsão de 1,9 h, e a Cemig contra os ~86 min. É isso
   que transforma `TAMPA` em padrão medido em vez de escolha desta rodada.
2. `resources_used.mem` e `.cput` dos 97 jobs: a reserva é conservadora de
   propósito (24 GB para ~3 GB usados na conversão), e só a medição diz quanta
   folga dá para devolver.
3. Os passos 1 a 3 do plano abaixo, que continuam valendo.

## Achado da V23: convergir nao atesta plausibilidade fisica

**71 subestacoes da COPELDIS2866 saiam `OK`** — convergidas, sem NaN, sem
chave ilhada — publicando perda modelada de ate **10.309.528%**. O que as
separava das outras 103 **da mesma base** nao era cadastro nem condutor: era
tensao. Mediana do `V_MT_min` em **0,082 pu contra 0,938 pu**.

A fisica fecha a conta sozinha. Carga de potencia constante a 0,08 pu puxa
~12x a corrente nominal para entregar a mesma potencia, e a perda joule, que
vai com o quadrado da corrente, sobe ~150x.

Generaliza: nas **4.189 subestacoes das 97 bases**, 0,254 pu contra 0,906 pu.
E nao e artefato de trecho desconectado — os `ramos_isolados` sao MAIORES no
grupo sadio (1.500 contra 870).

O `veredicto()` checava compilacao, NaN e convergencia, e nada mais. Agora ha
`TENSAO_IMPLAUSIVEL`, mesclado em `main`.

### RESSALVA IMPORTANTE, e ela e o motivo da V24

**O limiar de 0,5 pu foi escolhido sobre o `V_MT_min`; o veredicto aplica
sobre a MEDIANA.** Sao grandezas diferentes — a mediana e sempre >= o minimo —
e o vale bimodal do histograma (0,45–0,55 pu, as duas faixas mais vazias das
4.189) foi medido no minimo.

Consequencia: **as "981 subestacoes (23,4%)" citadas nas mensagens de commit
`8b7d92d` e `48be37e` sao a contagem de `V_MT_min < 0,5`, nao a de
`V_mediana < 0,5`.** O alcance real e MENOR e ainda desconhecido, porque a V23
nao coletou a mediana. O commit `2548b7d` fecha essa lacuna no coletor.

Usar a mediana continua sendo a decisao certa — minimo baixo pode ser uma
barra ruim em ponta de ramal, o que acontece em rede sadia, e ha teste para
esse caso. Mas o CORTE precisa ser reconferido sobre a distribuicao da
mediana, e so a V24 a produz.

## Plano da V24 — a partir daqui o trabalho é na CEAMAZON

**Corte:** 28/08/2026. A partir deste commit o Elder opera na máquina do
cluster. O código está pronto: `correcao-se-quebrada` mesclada, suíte em 660
testes verdes, coletor encadeado no submissor e cache de tamanho no lugar.

### Antes de submeter

- `git pull` no nó e conferir que o HEAD é este commit; a rodada carrega um
  único commit e ele vai na procedência.
- Fila vazia e cota disponível dentro de 64 núcleos / 192 GB.
- Sufixo novo (`V24`); rodada antiga é aposentada, não apagada.
- Na primeira execução do planejador, `MEDIDAS <n>` diz quantas `.gdb` ele
  mediu. Se `medicoes/tamanho_bases.json` não existir ainda, essa primeira
  varredura acontece uma vez — é esperado.

### Durante

O `auditoria.py` roda encadeado por PBS nas pontas das correntes. **Não rodar
à mão no head node**, que foi o desvio da V22.

### Depois do ciclo

1. `python analise/investigar_violacoes.py resultados/v24`. Comparar com a
   V22: as 17 linhas de modelo quebrado devem sair da competição com defeito
   real, e o total de violações reais deve ficar perto de 1.609.
2. `python diagnosticos/perfil_violacao.py --resultados resultados/v24 --so
   COPELDIS2866 --motivo "perda modelada absurda"`. Compara os 16 suspeitos
   contra o resto **da mesma base** em km, trafos, kVA, R1 e CNOM ponderados,
   e mede enriquecimento por condutor — o mesmo método que sustentou o 593 da
   Enel SP, agora sem caminho fixo no código.
3. Se nenhum atributo separar os grupos, **isso é resultado, não fracasso**:
   significa que a causa não está nos atributos de alimentador, e o próximo
   passo é topologia por barra nestes cinco CTMT — o candidato mais provável
   é malha fechada por engano ou chave mal tratada, que a convergência não
   pega: `71080/832100009`, `72857/874280005`, `72866/884720043`,
   `72205/815480008`, `72240/818000004`.

### O que pensar antes de agir sobre o resultado

- **Comparação com a V22 pelo campo `motivo` não é linha a linha.** A
  correção muda o rótulo das 17 linhas de SE quebrada de propósito. Diferença
  ali é o efeito esperado, não regressão.
- **Convergir não é prova.** As 16 de COPELDIS2866 estão em SE com veredicto
  `OK` e mesmo assim publicam perda de milhões por cento.
- **Não corrigir o conversor pelo caso isolado.** Defeito achado vira teste na
  suíte antes de qualquer correção ampla, e correção que muda saída espera a
  rodada fechar, em ramo separado.
- **As outras 242 continuam sem causa.** COPELDIS2866 é o caso mais concreto,
  não o único; 43 são prováveis Enel SP/condutor 593, 51 são borderline, 18
  são artefato de fórmula e ~130 são cauda espalhada em 22 bases.

## Ciclo de trabalho

1. Nó roda e publica resultados rastreáveis.
2. Máquina local importa os CSVs/JSONs e escolhe o pior caso acionável.
3. A máquina local reproduz, corrige, testa e publica o commit.
4. A próxima rodada usa esse único commit e um sufixo novo.
