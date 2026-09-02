# Ideias de artigo, a partir do que já existe

**Corte:** 02/09/2026. Este documento fixa **o que dá para publicar hoje**, com
os ativos na mão, e o que falta em cada caso. Prazo alvo: março/2027.

Nada aqui pede pesquisa nova. O que pede é escolher a tese e escrever.

## O que já está no armário

| ativo | número | onde |
|---|---|---|
| distribuidoras convertidas de ponta a ponta | **99** (safra 2025), 97 (2024) | `resultados/v26/`, `v25/` |
| subestações modeladas | **4.201** | idem |
| alimentadores | **26.655** | idem |
| subestações com veredicto `OK` | **97,4%** | idem |
| safras comparáveis | **2** (2024-12-31, 2025-12-31) | `medicoes/*_2024/2025.json` |
| achados medidos | **21**, ~6 citáveis | `ACHADOS_GENERALIZACAO.md` |
| clima real por base | 99 bases, NASA POWER | `dados/clima/` |
| suíte de regressão | **826 testes** | `testes/` |
| procedência por modelo | commit, árvore, Python, **motor OpenDSS** | `_procedencia.json` |

## A ideia principal

### A. Conversão e auditoria da BDGD em escala nacional

**A tese:** é possível converter automaticamente o cadastro georreferenciado de
**todas** as distribuidoras de um país em modelos elétricos executáveis — e o
que se aprende ao fazer isso é sobre a **qualidade do dado regulatório**, não
sobre o conversor.

**Por que é forte:** 99 concessões inteiras, com procedência por modelo e
suíte de regressão pública. Não conheço equivalente publicado nessa escala.
O leitor ganha método reproduzível e um retrato nacional.

**O que já tem:** tudo, menos a âncora de correção numérica.

**O que falta:** um caso canônico (IEEE 13/34) para responder "como sei que o
seu fluxo está certo?". É meio dia de trabalho e vira um parágrafo. Sem ele, a
divergência de 1,42× contra o declarado fica sem dono.

**Onde:** *Electric Power Systems Research*, *SEGAN*, *IEEE Access*.

## Os satélites, que saem do mesmo material

### B. A perda técnica declarada não fecha com o próprio cadastro

**A tese:** três campos da mesma BDGD se contradizem, e a contradição
**persiste entre safras**.

- em **40 de 81 bases**, o ferro implícito na placa dos próprios
  transformadores excede a perda técnica declarada (achado 13);
- **16 bases declaram exatamente 3,89%** — valor padrão, não medição
  (achado 9);
- há casos **fisicamente impossíveis** na declaração (achado 8);
- pareado nas **63 bases** presentes nas duas safras, nada mudou: 25 → 26
  bases em contradição, 31 pioraram e 32 melhoraram (achado 18).

**Por que é o mais forte cientificamente:** não depende do nosso modelo. São
campos da mesma base, e o nosso papel foi juntá-los. A réplica em duas safras
transforma "erro de preenchimento" em característica do processo de declaração.

**O que já tem:** tudo. `diagnosticos/contradicao.py` mede sem conversão, em
minutos.

**O que falta:** nada técnico. Falta escrever.

**Onde:** *Energy Policy*, *Utilities Policy* — é artigo de regulação, não de
engenharia.

### C. Armadilhas na medição de conectividade em modelos derivados de GIS

**A tese:** medidas topológicas usuais em OpenDSS induzem a erro sistemático em
modelos com mais de uma fonte, e isso não é óbvio.

`Topology.AllIsolatedBranches()` percorre a árvore a partir de **uma** fonte.
Subestação com duas barras de MT é comum, e toda a rede alimentada pelas demais
aparece como isolada — energizada e funcionando:

| subestações da V25 | mediana de "isolado" |
|---|---:|
| com uma fonte (3.301) | **0,86%** |
| com duas ou mais (888) | **68,88%** |

Na Light, 300 de 300 linhas "isoladas" tinham 1,02 pu e só morreram ao desligar
a segunda fonte. O isolamento real da pior subestação era **0,34%**, não 80%.

**Por que vale:** este erro custou **quatro achados** neste projeto antes de
ser encontrado. Qualquer grupo que meça conectividade em OpenDSS pode ter caído
nele, e não há aviso na documentação.

**O que já tem:** tudo, mais os testes que travam o comportamento.

**Onde:** nota técnica curta, ou uma subseção do artigo A. Como subseção, ela
responde de antemão à pergunta "como sabemos que suas medidas estão certas?".

### D. Quando modelar a baixa tensão muda o resultado

**A tese:** o modo agregado basta para estudo de MT; o completo muda o quê, e
sob que condições é viável.

**Status: NÃO ESCREVER AINDA.** O critério de entrada perdeu fundamento duas
vezes (achados 19b e 21), e a fragmentação que o justificava era artefato.
Precisa de base nova antes de virar texto.

## O que eu recomendaria

**Um artigo principal (A) com C embutido como subseção de método, e B em
paralelo** — B é independente, sai mais rápido e vai para outro público.

A ordem que economiza trabalho:

1. **IEEE 13 barras** como âncora. Meio dia, e destrava a única frase fraca de A.
2. **Escrever B**, que está pronto e não depende de mais nada.
3. **Fechar A** com os números da V26 e da revalidação da V25.

## O que NÃO entra em nenhum

- A perda modelada como resultado absoluto, enquanto não houver referência
  externa por distribuidora. Ela entra como **divergência medida**, nunca como
  erro atribuído.
- A cadeia 12 → 15 → 16 → 20 → 21. Ela é o processo, não o resultado: no texto
  vira um número final mais a nota de método (C).
- O critério de componentes por subestação, que mede topologia normal junto
  com defeito (achado 19b).
