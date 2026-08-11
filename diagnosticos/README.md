# Diagnósticos

Os scripts que produziram os achados 10 e 11 de `ACHADOS_GENERALIZACAO.md` —
o rastreamento da reprovação da Enel SP até o condutor 593.

Estão aqui porque são o **instrumento**, não só o resultado. Sem eles, o
raciocínio existiria apenas como prosa e ninguém poderia refazê-lo.

## Ressalva, e ela importa

**Vários carregam caminho absoluto embutido**, apontando para a `.gdb` da Enel
SP e para `MODELOS_V9`. É exatamente a doença que diagnosticamos na pasta
`analise/` — código que só roda na máquina onde nasceu.

Está registrado de propósito, e não corrigido de propósito: transformá-los em
ferramenta parametrizada **é** o trabalho do auditor (passos 5 e 6 do
`PLANO.md`). Corrigir agora, um a um, seria fazer duas vezes.

Quem for usar hoje: abra e troque as constantes do topo.

## O que cada um faz

| script | o que responde |
|---|---|
| `sonda_bdgd.py` | **O mais reutilizável.** Recebe uma `.gdb` e confronta com o que o conversor assume: tabelas presentes, códigos de tensão sem valor, `TEN_LIN_SE` fora do `Voltagebases`, condutores com R1 ou X1 inválidos, porte da subtransmissão. É o que economizou horas antes de cada conversão. **Embrião do auditor.** |
| `rodar_bases.py` | Piloto que roda o ciclo completo — extrair, sondar, converter, verificar, energia, perdas — sobre uma lista de bases, uma de cada vez, sem que falha em uma derrube as outras. |
| `diag_balanco.py` | Separa **violação real** do limite físico de **medição degenerada** (faturado ≥ injetado, que é erro de cadastro). Foi o corte que revelou a Enel SP como discrepante por fator 40. |
| `perfil_458.py` | Compara os alimentadores que violam contra os que não violam em atributos medíveis: km, transformadores, kVA, UCs, R1 ponderado, ampacidade, carregamento. |
| `km_sobrecarga.py` | Fração da quilometragem que opera acima da ampacidade, e quanto da perda ocorre ali — **dentro das mesmas subestações**, para o efeito não se confundir com característica da SE. |
| `quem_sobrecarrega.py` | Qual condutor causa a sobrecarga, com **enriquecimento** (fração na sobrecarga ÷ fração na rede). Foi ele que apontou o 593 com 4,64×. |
| `censo_cnom.py` | Ampacidade e R1 declarados por cada base, **ponderados pelo km de rede** que os usa. Mostrou os 2.993 km da Enel SP num cabo de 31 A. |
| `r1_coerencia.py` | Razão entre o R1 declarado e o previsto pela ampacidade, por condutor e por alimentador. Refutou a hipótese de que a incoerência distinguia os grupos. |
| `sensibilidade_593.py` | O experimento controlado: copia os modelos, troca **só** as definições de um `LineCode` e remede. Uma variável. |
| `mt_completude.py` | A rede de MT do modelo bate com a que a BDGD declara? Refutou "rede faltando na Light" (100,0% presente). |
| `at_ligacao.py` | Como o `UNTRAT` liga na rede de AT: por `PAC` ou por `BARR`. Descobriu que `PAC` casa 94,2% na Enel SP e **0,0%** na Light. |
| `r1_bases.py` | R1 mediano e ponderado por km, por base. |

## O que fazer com eles

O `sonda_bdgd.py` e o `quem_sobrecarrega.py` são os dois que devem virar parte
do auditor. O primeiro já roda em qualquer `.gdb` com uma linha de mudança; o
segundo precisa do fluxo resolvido, e é a verificação de coerência entre
ampacidade declarada e corrente calculada que o `PLANO.md` incorporou ao passo 5.
