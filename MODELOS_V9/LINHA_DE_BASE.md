# Linha de base reprodutível — MODELOS_V9

Passo 2 do `PLANO.md`. **Não é uma v1.0 oficial** — é um ponto de retorno:
a primeira vez em que os modelos foram gerados pelo código que está no
disco, com os hashes registrados para conferência.

**Data:** 10/08/2026

## Como foi gerado

```bash
python converter.py "Enel_SP_390_2024-12-31_V11_20250702-2009.gdb" --saida MODELOS_V9
python verifica.py MODELOS_V9 --grafico
python energia.py MODELOS_V9 --grafico --curvas
python valida_perdas.py MODELOS_V9 "Enel_SP_390_2024-12-31_V11_20250702-2009.gdb" --grafico
```

Todas as demais opções em seus padrões: `--mes 1`, `--dia DU`,
`--bt agregado`, `--fator-carga 1.0`, `--gd-fp 1.0`, `--irradiancia 1.0`,
`--lote 10`, `--clima` apontando para `04_DADOS_AUXILIARES`.

Tempo de conversão: **48,2 min** para as 155 subestações.

## Resultado

| | |
|---|---|
| Subestações sadias nos dois motores | **155 de 155** |
| Resolvem o dia inteiro de 96 passos | **155 de 155** |
| Energia injetada no dia | 101.23 GWh |
| Perdas no dia | 11.01 GWh (10.87%) |
| Geração distribuída no dia | 0.54 GWh (0.53%) |
| Alimentadores comparados com o `PERD_*` | 1,492 |
| Razão mediana modelo/declarado | **1.88×** |
| Dentro de ±30% | 18.0% (o critério pede 80%) |

A validação de perdas **reprova** o critério declarado. Isso está aqui de
propósito: a linha de base registra o estado real, não um estado desejável.

## Arquivos de resultado

| arquivo | conteúdo |
|---|---|
| `verificacao.json` | as 155 nos dois motores do OpenDSS |
| `energia_dia.json` | energia, perdas e a série de 96 passos por subestação |
| `validacao_perdas.json` | cruzamento com `PERD_A4 + PERD_B + PERD_A4_B` |
| `relatorio_rede.json` | cobertura, fontes, ilhas e o que ficou de fora |
| `curva_gd_geral.png` | carga × geração da concessão ao longo do dia |
| `<SE>/curva_gd.png` | a mesma curva, por subestação |

## Código que produziu isto

SHA-256 de cada arquivo. Se algum hash não bater, os modelos não vieram
deste código.

| arquivo | sha256 |
|---|---|
| `analise_com.py` | `5fc57eaee7fa3dfa…` |
| `app.py` | `2842ca1e30181194…` |
| `converter.py` | `d186a97d4329405b…` |
| `energia.py` | `07b55bf546211e28…` |
| `interativo.py` | `c1df8d9d5d56bb42…` |
| `menu.py` | `333b9dd6de7ee834…` |
| `painel.py` | `085493846773c132…` |
| `valida_perdas.py` | `41c0f07e51ff41f9…` |
| `validador.py` | `508e8b6774d9c3ea…` |
| `verifica.py` | `60de789aa7197e4d…` |
| `bdgd2dss/__init__.py` | `e3b0c44298fc1c14…` |
| `bdgd2dss/cargas.py` | `1d15737291557686…` |
| `bdgd2dss/chaves.py` | `ef979d92e780da21…` |
| `bdgd2dss/complementos.py` | `994de95b29b13068…` |
| `bdgd2dss/coordenadas.py` | `dd8c50fc4e22392c…` |
| `bdgd2dss/diagnostico.py` | `52764fb36b1339cb…` |
| `bdgd2dss/leitor.py` | `ba25e52428a02642…` |
| `bdgd2dss/linecodes.py` | `7dc21ccb153ba6da…` |
| `bdgd2dss/linhas.py` | `dba19b37649b50e1…` |
| `bdgd2dss/malha_at.py` | `9eded9482a41d504…` |
| `bdgd2dss/master.py` | `ca318dcce3f3754b…` |
| `bdgd2dss/subtransmissao.py` | `b901ea2a415d66d4…` |
| `bdgd2dss/tensoes.py` | `98571d77ef41b9bc…` |
| `bdgd2dss/transformadores.py` | `7fa39d0176f4e98f…` |
| `bdgd2dss/transmissao.py` | `c58c2c5d535ac719…` |

25 arquivos. Hashes completos em `linha_de_base.json`.
