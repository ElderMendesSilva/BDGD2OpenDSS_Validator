# Rede Enel SP em OpenDSS — o que confiar e o que não, antes de rodar NSGA-II

Nota para quem vai usar este modelo em otimização. Escrita em 14/08/2026.

O modelo foi gerado a partir da BDGD da Enel SP (`Enel_SP_390_2024-12-31_V11`)
por um conversor próprio. Ele **não** é um modelo de planejamento validado pela
distribuidora: é uma tradução automática do cadastro regulatório. Tudo abaixo
foi medido, e onde é leitura minha está dito.

---

## 1. O que está sólido

Rodei as 155 subestações e seis delas em detalhe.

- **Topologia e convergência.** As 155 compilam, resolvem e convergem, em 2 a 9
  iterações. **Zero nós NaN e zero cargas sem tensão** em toda a base.
- **Arquitetura elétrica correta.** Cada subestação tem **uma barra de MT** com
  o equivalente de curto do pátio de AT (`MVAsc3`/`MVAsc1` reais), e os
  alimentadores dividem essa barra — como na operação. Não há a fonte ideal por
  alimentador que versões antigas tinham.
- **EnergyMeter por alimentador**, no vão de saída. `Show Meters` /
  `Export Meters` dão perda e energia por alimentador sem pós-processamento.
  É o ponto por onde toda a energia do alimentador passa.
- **Chaves com estado real** (`P_N_OPE` da BDGD), emitidas como `Line ... Switch=Y`
  com `SwtControl`, e as normalmente abertas fixadas em `_CHAVES_ABERTAS.dss`.

## 2. O que NÃO está sólido — em ordem de impacto sobre a otimização

### 2.1 A perda absoluta está cerca de 10× acima do declarado

**Este é o problema que mais restringe o uso.** Contra o `PERD_A4` declarado na
própria BDGD, em 963 alimentadores comparados:

```
perdas % do modelo:  mediana  11,87%
perdas % declarado:  mediana   1,12%
razão modelo/declarado: mediana 9,92x   p10 2,76x   p90 22,55x
96,5% dos alimentadores acima de 1,5x
```

A causa **não está estabelecida**. Não é a declaração: o mesmo campo em outra
distribuidora dá 3,21%, e o mesmo conversor produz 1,3% lá. Está sendo
investigado.

**Consequência prática:** qualquer função-objetivo que use perda em kW ou em %
como valor absoluto, ou que compare com meta regulatória, está calibrada sobre
uma base errada por uma ordem de grandeza.

### 2.2 A tensão mínima é implausível em boa parte da base

Por subestação, o mínimo de MT:

```
mediana  0,819 pu    p10  0,618 pu    mínimo  0,187 pu
```

E a fonte de cada subestação é fixada em **1,09 pu** (`New Circuit ... pu=1.0900`),
o que já é o topo da faixa adequada do Módulo 8. A queda até 0,19 pu não é
estado operativo real.

**Consequência prática:** restrição de tensão como *constraint* rígido torna
grande parte do espaço de busca inviável antes da otimização começar. Se for
usar, use como objetivo a minimizar, ou aplique só às subestações da lista da
seção 5.

### 2.3 A rede de baixa tensão não existe

O modelo foi gerado em modo **agregado**: as unidades consumidoras de BT são
somadas e penduradas no **secundário do transformador MT/BT**, em 0,12–0,22 kV.
Não há SSDBT nem RAMLIG.

**Consequência:** a perda de BT não aparece (isso *reduz* a perda, em direção
contrária ao item 2.1) e não há como otimizar nada abaixo do transformador —
nem regulação, nem alocação de GD por ponto de consumo real.

### 2.4 Um defeito recém-corrigido que NÃO está neste modelo

Descobri em 14/08/2026 que o conversor descartava os **reguladores de tensão**
da BDGD, porque os pontos de conexão deles não são pontos da rede de média — o
regulador fica entre duas chaves. Onde isso acontece, o tronco é cortado logo
depois da cabeceira.

Na **Enel SP o estrago é pequeno**: 98,6% da rede permanece alcançável, contra
37,9% na Cemig-D e 25,1% na Enel CE. A Enel SP tem 77 reguladores; a Cemig-D
tem 3.099. Por isso este modelo é utilizável e os das outras não são.

**Mas:** o modelo que você tem foi gerado antes da correção. Se aparecer um
alimentador que morre logo depois da saída, é isto.

### 2.5 Convenções que vão surpreender

- **A carga vem da ENERGIA medida, não da demanda declarada.** `kW` é a média
  mensal (kWh/730) ajustada pelo fator de carga, com curva diária por classe
  (`Daily=COM-Tipo02`, `RES1_1`, …). Não é ponta.
- **Modelo de carga ZIP**: `Model=8 zipv=(0.5,0,0.5,1,0,0,0)`, `pf=0.92`.
  Metade impedância constante, metade potência constante.
- **A GD também vem da energia**, não de `POT_INST` — o campo `POT_INST` da
  BDGD replica a carga instalada do consumidor e erra por até 540×. Os
  inversores estão em `pf=1` e `irradiance=1`, que é **meio-dia de céu claro**,
  não a ponta de carga. Para o dia inteiro use as curvas `IRRAD_DIA`/`TEMP_DIA`
  já declaradas.
- **`Voltagebases` são tensões de LINHA.** Se for criar barras novas, rode
  `CalcVoltagebases` com cuidado: ele lê o primeiro nó de cada barra.

---

## 3. O que dá para otimizar com confiança

| objetivo | serve? | por quê |
|---|---|---|
| Reconfiguração / abertura de chaves | **sim** | a topologia e o estado das chaves vêm do cadastro |
| Alocação de banco de capacitores (posição) | **sim** | o ótimo relativo se mantém mesmo com a perda deslocada |
| Alocação de GD (posição, entre barras de MT) | **sim** | idem |
| Dimensionamento de GD em kW absoluto | com ressalva | a carga é média mensal, não ponta |
| Minimizar perda em kW/% absoluto | **não** | item 2.1 |
| Restrição de faixa de tensão do Módulo 8 | **não** | item 2.2 |
| Qualquer coisa abaixo do trafo MT/BT | **não** | item 2.3 |

Regra prática: **objetivos relativos e topológicos são confiáveis; objetivos
calibrados em valor absoluto não são.**

---

## 4. Como carregar

Uma subestação isolada:

```
Redirect MODELOS_SP_V11/DIBP/MASTER-DIBP.dss
Solve
Show Meters
```

A concessão inteira, com subtransmissão:

```
Redirect MODELOS_SP_V11/MASTER-GERAL.dss
```

Cada pasta de subestação traz `REDE-<SE>.dss` (a rede, sem fonte nem medição),
`Vaos.dss` (os vãos de saída), `Chaves.dss` + `Controles.dss`,
`_CHAVES_ABERTAS.dss`, `Trafos.dss`, `Cargas.dss`, `GD.dss`,
`Reguladores.dss`, `Capacitores.dss`, `LineCodes.dss` e `resumo.json`.

Para montar variantes, redirecione `REDE-<SE>.dss` a partir de um master
próprio — ele é neutro de propósito.

---

## 5. Quais subestações usar

**155 modelos: 126 sem ressalva, 22 com tensão baixa, 5 com regulador saturado,
2 com rede muito extensa.**

As mais saudáveis (tensão mínima alta e perda em faixa plausível) — bons
candidatos para um caso de estudo:

| SE | Vmin (pu) | barras | cargas | perdas |
|---|---|---|---|---|
| DIBP | 1,041 | 5.846 | 1.417 | 2,08% |
| DJKU | 1,036 | 6.886 | 2.068 | 2,29% |
| DVMA | 1,033 | 7.197 | 1.971 | 4,55% |
| DPPR | 1,029 | 3.142 | 671 | 1,93% |
| DIMG | 1,017 | 7.399 | 715 | 3,28% |
| DSAM | 1,015 | 9.147 | 2.932 | 3,77% |
| DCAM | 1,007 | 6.916 | 1.229 | 4,24% |
| DSOC | 1,002 | 3.633 | 693 | 4,94% |

Nestas, a perda está entre 1,9% e 4,9% — faixa fisicamente razoável para média
tensão —, o que sugere que o problema do item 2.1 se concentra na cauda ruim e
não é uniforme. **Isso é leitura, não medição:** não verifiquei uma a uma.

**Evitar, salvo se o estudo for justamente sobre elas:**

- Tensão baixa (22): DANC DCOI DCRA DDIA DITN DITR DLUB DMAD DMAU DMPA DNAC
  DPEN DPER DPIP DROS DSAU DTMO DUTI DVGR DVIT DVPC DVTA
- Regulador saturado (5): DEMB DGPR DIVI DJAN DPSD
- Rede muito extensa (2): DREG TMRE

E ignore `DUSP` e `DPEC`: têm 48 e 28 barras com **uma** carga cada. Não são
subestações de estudo.

---

## 6. Checagem antes de confiar numa subestação

```
Redirect MASTER-<SE>.dss
Solve
! 1. convergiu?
! 2. algum NaN?           -> Export Voltages, procurar NaN
! 3. carga sem tensão?    -> percorrer Loads e conferir CktElement.VoltagesMagAng
! 4. perda plausível?     -> Show Meters; acima de ~8% em MT, desconfiar
! 5. tensão mínima?       -> abaixo de 0,9 pu em massa, desconfiar
```

Os itens 3 e 4 são os que pegam os dois defeitos conhecidos. Se a carga sem
tensão for grande, é o item 2.4 (regulador descartado) — nesse caso peça o
modelo regerado, porque a correção já existe.

---

## 7. O que não afirmar a partir deste modelo

- Que a perda técnica da Enel SP é X% — não é o que está medido aqui.
- Que N% dos nós violam o Módulo 8 — o piso de tensão do modelo não é confiável.
- Que a GD instalada é X MW — a potência foi derivada da energia, por
  necessidade, e não da potência declarada.
- Qualquer comparação entre distribuidoras usando os números deste conversor,
  enquanto as outras bases não forem regeradas com a correção do item 2.4.

Com essas ressalvas explícitas, o modelo é uma base honesta para estudo de
otimização topológica. Sem elas, os números viram afirmação que o dado não
sustenta.
