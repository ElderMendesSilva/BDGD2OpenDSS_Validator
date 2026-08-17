# Onde cada coisa mora

Organizado em 17/08/2026. **Arquivo novo vai para a pasta certa desde o
começo** — mover depois quebra caminho que alguém já escreveu.

## As pastas

| pasta | o que vai nela |
|---|---|
| **raiz** | só os `.py` executáveis (`converter.py`, `verifica.py`, `energia.py`, `validador.py`, `valida_*.py`, `ampacidade.py`, `ligacao.py`, `regerar_v10.py`, `decompor.py`, `menu.py`, `painel.py`, `app.py`), o `README.md` e o `requirements.txt` |
| **`docs/`** | todo `.md` que não seja o `README.md` — achados, planos, relatórios, respostas |
| **`logs/`** | log de execução. A regeração escreve em `logs/<sufixo>/`: `logs/v13/`, `logs/v14/`… Log solto de script avulso fica em `logs/` mesmo |
| **`medicoes/`** | JSON de medição avulsa: alcance, censo de condutor, e o que mais sair de script de diagnóstico |
| **`bdgd2dss/`** | os módulos do conversor |
| **`testes/`** | a suíte, e o `fixture.py` que gera a BDGD mínima |
| **`analise/`** | scripts de análise que rodam sobre modelos já gerados |
| **`dados/`** | insumo do conversor, versionado — hoje o `de_para_mnemonicos.csv` |
| **`MODELOS_<TAG>_<SUFIXO>/`** | saída do conversor. **Não versionada e não reorganizável** |

## O que NÃO pode mudar de lugar

- **Qualquer coisa dentro de `MODELOS_*/`.** O código escreve e lê
  `resumo.json`, `verificacao.json`, `energia_dia.json`, `ampacidade.json`,
  `ligacao.json`, `relatorio_rede.json`, `_procedencia.json` e os `.dss` por
  caminho relativo à pasta da subestação. Mover um deles quebra a cadeia
  inteira.
- **`requirements.txt` e `README.md`**, que ficam na raiz por convenção.
- **`dados/de_para_mnemonicos.csv`**, lido pelo `converter.py` por caminho
  fixo — é insumo, não resultado, e por isso entra no repositório.

## Por que convenção e não automação

A tentação é pôr um gancho que mova arquivo novo sozinho. Não faça: o
conversor escreve dezenas de `.json` e `.dss` por subestação, e um gancho que
os realoque quebra o modelo na primeira execução. A regra vale para arquivo
que **nós** criamos na raiz — documento, log de script avulso, JSON de
medição —, e é isto aqui que a torna automática.

## O que já está ignorado pelo git

`logs/`, `medicoes/`, `MODELOS*/`, `memoria_*.csv`, `*.pkl`, `relatorios/`,
`dados/extraido_bdgd/`, `dados/resultados/`. Saída de execução não entra no
repositório; os **números medidos** entram, no
`docs/ACHADOS_GENERALIZACAO.md`.

## Retenção: o que se guarda e o que se joga fora

A saída do conversor é **reproduzível a partir do `.gdb`** — guardar rodada
velha é ocupar disco com o que um comando refaz. Em 17/08/2026 a pasta tinha
20 GB; foi a 8,3 GB apagando o que já não servia de comparação.

**Guardar:**

- a rodada **corrente** e a **anterior**, para comparar. Hoje: V13 (corrente)
  e V11/V12 (comparação). Quando a V13 fechar e validar, V11 e V12 saem.
- `logs/<sufixo>/` de **todas** as rodadas. São megabytes e são a memória do
  projeto: as tabelas "V11 → V13" saem deles, não dos modelos.
- `MODELOS_V9/LINHA_DE_BASE.md` e `linha_de_base.json`, que estão no git de
  propósito — é a linha de base declarada.
- `relatorios/`, que são PDF institucional e **não** se refazem.

**Jogar fora sem dó:** rodada de duas versões atrás, `TESTE_*`, `TF*`,
`PROVA_*`, pasta de modelo sem sufixo de versão, e qualquer saída que um
comando registrado reproduza.

**Nunca apagar sem olhar:** `dados/` é insumo, não resultado. `relatorios/`
não se refaz. E código, mesmo morto, sai por `git rm` e não por `rm` — fica
recuperável no histórico.
