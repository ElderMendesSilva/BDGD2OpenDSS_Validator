# Posicionamento — o que é defensável neste projeto

**Corte:** 28/08/2026. Este documento não é técnico: registra qual parte do
trabalho tem valor que não se copia, para orientar o que priorizar, o que
arquivar e o que nunca prometer.

## Premissa

Escrever um conversor BDGD→OpenDSS deixou de ser barreira. Uma equipe pequena
com assistente de código chega a um conversor que compila e converge em poucas
semanas. `PLANO.md` já registra a mesma virada: *o principal risco deixou de
ser "o conversor não roda"*.

Logo, o código não é o ativo. O ativo é o que só existe depois de rodar: as 97
bases percorridas, os 96 ciclos fechados, o condutor 593 identificado como
causa de perda impossível na Enel SP, e as sete bases que caíram de reprovação
para 2,64%–8,93% após separar alimentadores contaminados.

## O que é defensável, em ordem de força

### 1. Comparação entre concessões

A distribuidora tem a base dela. O acervo tem as demais. Perguntas do tipo
"minha perda de MT está fora do padrão para porte e qualidade de cadastro
equivalentes?" exigem ter convertido as outras bases sob a mesma safra, o
mesmo conversor e o mesmo critério de contaminação.

É a única entrega que o cliente não obtém reescrevendo o conversor: falta a
ele o conjunto de pares, não o software.

### 2. Auditoria de cadastro recorrente

Os achados consolidados em `ACHADOS_GENERALIZACAO.md` — incoerência entre
condutor e uso, tensão declarada incompatível com o parque, R1×CNOM, regulador
desconectado, primário bifásico escrito como trifásico — são defeitos do
cadastro do cliente, não do modelo. Têm valor regulatório direto.

Como a BDGD tem safra nova a cada ano, isso vira ciclo: entregar a lista de
alimentadores implausíveis, o cliente corrige, medir de novo na safra seguinte
e reportar o que melhorou e o que reincidiu. A série comparável só se mantém
sob o mesmo conversor e o mesmo critério; trocar de fornecedor reinicia a
contagem.

### 3. Taxonomia de defeitos

A suíte de regressão é a especificação, e cada caso nasceu de uma falha
observada. Um conversor novo reproduz o resultado fácil — compila, converge,
sem `NaN` — e cai exatamente na armadilha registrada: *redes fisicamente
implausíveis podem convergir*. Saber onde olhar é o conhecimento acumulado;
não está no código, está nos casos.

### 4. Procedência

Rodada rastreável por commit, comando e versão dos insumos, com saída
determinística entre laptop e cluster. Sozinha não retém ninguém. É o que
transforma o item 2 em evidência utilizável perante o regulador, em vez de um
relatório sem lastro.

## O que não prometer

Vale a mesma regra de `NOTA_OTIMIZACAO_ENEL_SP.md`:

- perda técnica absoluta em kW/% ou comparação direta com meta regulatória;
- faixa de tensão como restrição rígida em toda a base;
- qualquer conclusão abaixo do transformador MT/BT enquanto `--bt completo`
  estiver em correção.

Nesse terreno o projeto não tem vantagem defensável, e a limitação é conhecida
o bastante para se tornar passivo. O que se sustenta é análise topológica,
comparação relativa dentro da mesma subestação saudável e auditoria de dado.

## Consequência prática

A vantagem de "já ter convertido 97 bases" é de custo e tempo, não de acesso:
a BDGD é pública e o custo de computação cai. Ela encolhe.

O que não se reconstrói retroativamente é a série histórica por concessão —
mesma metodologia aplicada safra após safra, com os defeitos datados e o
resultado da correção medido. Isso pede uma decisão de arquivamento agora, e
não depois:

- preservar cada rodada por código ANEEL e safra, com commit e insumos;
- manter comparabilidade entre safras como restrição de projeto, tratando
  mudança de critério como evento datado e não como correção silenciosa;
- registrar os alimentadores implausíveis por safra, para que reincidência e
  correção sejam mensuráveis mais tarde.

`AS_53_BDGDS.md` já proíbe misturar safra por invalidar comparação de perdas.
Aqui a mesma regra tem outra razão: é o que preserva o único ativo que o tempo
valoriza em vez de corroer.
