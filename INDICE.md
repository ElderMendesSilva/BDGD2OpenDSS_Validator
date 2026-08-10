# Índice do projeto

```
BDGD2OpenDSS/
│
├── menu.py                   ★ COMECE AQUI ──  janela com as sete ferramentas
│                             na ordem de uso; cada uma pergunta o que precisa
├── interativo.py             o painel de parâmetros que todas usam: sem
│                             argumento, pergunta; com argumento, obedece
│
├── converter.py              conversor (sem argumento abre o app.py)
├── app.py                    interface da conversão (.gdb → modelos, log ao vivo)
├── verifica.py               sanidade numérica nos DOIS motores do OpenDSS
├── validador.py              roda os modelos gerados e diz a causa raiz
├── energia.py                o dia inteiro em 96 passos → energia_dia.json
├── valida_perdas.py          cruza a perda do modelo com o PERD_* da CTMT
├── painel.py                 ── INTERFACE ──  janela com todas as subestações,
│                             causa raiz, gráficos e o Plot nativo do OpenDSS
├── analise_com.py            ── ANÁLISE VIA COM ──  resolve pelo OpenDSSEngine
│                             e gera os gráficos, inclusive o traçado geográfico
├── README.md                 como usar, decisões de modelagem e limitações
├── PLANO.md                  ★ o plano de continuidade e o porquê da ordem
├── RELATORIO_GERAL.md        o que foi feito, medido e o que ficou em aberto
├── INDICE.md                 este arquivo
│
├── bdgd2dss/                 ── O CONVERSOR ──  um módulo por elemento gerado
│   ├── leitor.py             acesso à .gdb em fatias (não estoura memória)
│   ├── tensoes.py            código TEN_NOM → kV, com a procedência de cada valor
│   ├── linecodes.py          SEGCON            → LineCode (serve AT, MT e BT)
│   ├── linhas.py             SSDMT / SSDBT / RAMLIG → Line
│   ├── chaves.py             UNSEMT            → Line(Switch=Y) + SwtControl
│   ├── transformadores.py    UNTRMT + EQTRMT   → Transformer + Reactor de aterramento
│   ├── cargas.py             UCBT_tab / UCMT_tab → Load (agregada ou por UC)
│   ├── complementos.py       CRVCRG → LoadShape ; UNCRMT → Capacitor
│   │                         UNREMT → RegControl ; UGBT/UGMT → PVSystem ; XYCurve
│   ├── subtransmissao.py     ── ALTA TENSÃO ──
│   │                         SSDAT → Line ; UNSEAT → Line(Switch) ; UNTRAT+EQTRAT
│   │                         → Transformer ; UCAT → Load ; UGAT → Generator ;
│   │                         UNCRAT → Capacitor ; componentes conexas ; os VÃOS
│   ├── transmissao.py        planilhas da ISA → fontes por pátio e trafos das
│   │                         subestações da transmissora
│   ├── malha_at.py           fecha a malha de 88 kV: barra de AT por subestação,
│   │                         ancorada em UNSEAT.SUB/UNTRAT.SUB e no de-para
│   ├── coordenadas.py        geometria da BDGD → BusCoords (habilita Plot Circuit)
│   ├── diagnostico.py        causa raiz por subestação: separa defeito do
│   │                         conversor de característica da rede
│   └── master.py             MASTER-GERAL, MASTER por SE e REDE-<SE>
│
├── analise/                  ── ESTUDO DE CRITICIDADE ──  roda sobre a BDGD, sem OpenDSS
│   ├── extrai_bt.py          varre UCBT_tab (8,26 M) e agrega por alimentador
│   ├── extrai_mt.py          UCMT_tab + geração distribuída
│   ├── extrai_ampacidade.py  SSDMT × SEGCON → capacidade do tronco
│   ├── criticidade.py        calcula carregamento e índice de instabilidade
│   └── relatorio_estudo.py   gera o PDF do estudo
│
├── dados/
│   ├── extraido_bdgd/        o que foi lido da BDGD (reuso sem reprocessar)
│   └── resultados/           criticidade, ranking e resultados do OpenDSS
│
├── legado/                   ── PACOTE ANTIGO ──  scripts que corrigiam a exportação
│
├── relatorios/               os 6 PDFs produzidos ao longo do trabalho
│
└── MODELOS/                  ── SAÍDA DO CONVERSOR ──
    ├── MASTER-GERAL.dss      a concessão inteira: AT → MT → BT
    ├── relatorio_rede.json   cobertura, fontes, ilhas e o que ficou de fora
    ├── _global/              LineCodes, Curvas e XYCurves — declarados uma vez
    ├── _AT/                  Fontes, Linhas_AT, Chaves_AT, Barras_AT,
    │                         Trafos_AT, Trafos_Transmissora, BusCoords_AT.dat
    ├── _cache_ucbt.pkl.mesNN cache da agregação (evita reprocessar 8,26 M)
    └── <SE>/                 uma pasta por subestação
        ├── MASTER-<SE>.dss   a SE isolada, com equivalente na barra de MT
        ├── REDE-<SE>.dss     só os elementos — usado pelos dois MASTERs
        ├── Vaos.dss          barra de MT → cabeceira de cada alimentador
        ├── BusCoords.dat     coordenadas geográficas das barras
        ├── analise/          figuras geradas por analise_com.py
        └── resumo.json
```

## Sem linha de comando

```bash
python menu.py
```

Todo script agora funciona dos dois jeitos. **Com argumento** ele se comporta
como sempre — a linha de comando continua valendo e é o que o `menu.py` e o
`painel.py` usam por dentro. **Sem argumento nenhum** ele abre uma janelinha
pedindo o que falta, com o caminho já preenchido pelo último uso e um botão de
procurar, em vez de imprimir `error: the following arguments are required`.

Onde o resultado é um número, sai no terminal como antes; onde ele só faz
sentido visto de uma vez (155 subestações, 1.492 alimentadores), abre também
um gráfico e salva o PNG ao lado do JSON.

Sem tela — servidor, SSH, ou com `BDGD_SEM_JANELA=1` — o mesmo formulário é
perguntado no terminal e os gráficos vão para arquivo. Nenhum script depende
de haver janela.

## Fluxo de trabalho

**1. Converter** — `converter.py` ou `app.py`. Gera `MASTER-GERAL.dss`, `_AT/` e
uma pasta por subestação.

**2. Verificar** — `python verifica.py MODELOS_V8` compila e resolve cada
subestação nos dois motores e aponta NaN, não convergência e falha de
compilação. É o primeiro teste depois de converter.

**3. Validar** — `python validador.py MODELOS_V8` classifica a causa raiz do que
está fora do esperado, separando defeito do conversor de característica da rede.

**4. Medir o dia** — `python energia.py MODELOS_V8` roda as 24 h em passos de
15 min e integra energia e perdas por alimentador (`energia_dia.json`).

**5. Cruzar com o declarado** — `python valida_perdas.py MODELOS_V8 <caminho.gdb>`
compara com `PERD_A4 + PERD_B + PERD_A4_B` da CTMT.

**6. Analisar** — `analise_com.py` para os gráficos de um MASTER; os scripts de
`analise/` dão o panorama sobre a BDGD inteira sem precisar simular.

## O que é o quê

| Se você quer... | Use |
|---|---|
| **começar por aqui** | `python menu.py` |
| a rede completa, da subtransmissão para baixo | `MODELOS/MASTER-GERAL.dss` |
| gráficos e traçado geográfico | `python analise_com.py` (ele pergunta o MASTER) |
| saber o que ainda precisa ser depurado | `python verifica.py` |
| estudar um alimentador sem carregar a concessão | `MODELOS/<SE>/MASTER-<SE>.dss` |
| gerar modelos de uma BDGD nova | `converter.py` ou `app.py` |
| conferir se um modelo gerado presta | `validador.py` |
| energia e perdas do dia, por alimentador | `energia.py` |
| comparar as perdas com o que a Enel declara | `valida_perdas.py` |
| saber o que ficou sem fonte ou sem vão | `MODELOS/relatorio_rede.json` |
| tensão de atendimento ao consumidor | `converter.py --bt completo` (leia a ressalva no README) |
| saber quais alimentadores são críticos sem simular | `analise/criticidade.py` |
| entender por que o modelo é montado assim | `README.md`, seção "As decisões" |
| refazer algo que foi feito no pacote antigo | `legado/` |
| reaproveitar extração da BDGD sem reler 8 GB | `dados/extraido_bdgd/` |

## Estado atual

O conversor gera a rede inteira com a camada de alta tensão real
(transformadores da UNTRAT/EQTRAT, linhas da SSDAT, chaves da UNSEAT) em vez de
uma fonte ideal por alimentador.

A pasta corrente é a **`MODELOS_V8`**: as **155 subestações** compilam,
convergem, sem NaN, nos dois motores do OpenDSS, e resolvem o dia inteiro de 96
passos. As versões anteriores ficam como histórico.

A validação de perdas contra o `PERD_*` declarado **reprova** pelo critério de
±30%: mediana de 7,74% no modelo contra 4,39% declarado, razão mediana 1,88×. O
detalhe e as leituras possíveis estão no `RELATORIO_GERAL.md`.
