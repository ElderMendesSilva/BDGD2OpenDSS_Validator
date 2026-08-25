# Entre as duas máquinas

**Criado em 25/08/2026.** Este arquivo é a conversa entre o **PC do CEAMAZON**
e o **PC de casa**. Ele existe porque o trabalho acontece em duas máquinas que
nunca estão ligadas ao mesmo tempo, e o que uma descobriu a outra precisa saber
sem que ninguém tenha de lembrar de contar.

## Por que aqui dentro, e não num arquivo solto

O arquivo mora no repositório de propósito. **O repositório é o canal.** Um
`.md` mandado por e-mail, WhatsApp ou pendrive tem de ser baixado de novo a
cada troca de máquina, e a versão que você abre nunca é comprovadamente a mais
nova. Aqui, `git pull` traz a conversa junto com o código, e as duas coisas
chegam na mesma versão — o que importa, porque metade das anotações só faz
sentido ao lado do commit que as gerou.

Consequência prática: **nada aqui vale enquanto não for enviado.** Escrever a
entrada e esquecer o `git push` é o mesmo que não ter escrito.

---

## O ritual: três comandos na chegada, três na saída

**Ao sentar em qualquer uma das duas máquinas:**

```bash
cd <pasta do projeto>
git pull --rebase
sed -n '1,120p' docs/ENTRE_MAQUINAS.md
```

O `--rebase` é proposital: sem ele, cada `pull` num repositório com trabalho dos
dois lados cria um commit de merge vazio, e o histórico vira uma trança
ilegível em duas semanas.

**Ao levantar, antes de fechar a máquina:**

```bash
git add -A
git commit -m "Diario: <o que mudou nesta sessao>"
git push
```

**Se você não fizer mais nada além disso, o sistema já funciona.** O resto
deste documento é sobre escrever a entrada bem.

---

## Estado de cada máquina

Esta seção é **reescrita**, não acrescentada — ela diz o que é verdade hoje.
Quando algo mudar, corrija a linha no lugar. O histórico de como chegou aqui
fica no diário, embaixo.

### PC do CEAMAZON — a máquina que alcança o cluster

| | |
|---|---|
| Pasta do projeto | `C:\Elder\ENEL\BDGD2DSS` |
| Sistema | Windows 11, Git Bash |
| Python | 3.14.3 (do PATH) |
| Ambiente `.venv` | ✅ criado, `doutor.py` sem impedimento |
| Dependências | ✅ numpy 2.5.2, pyogrio 0.13.0, opendssdirect 0.9.4 |
| Chave SSH | ✅ `~/.ssh/id_ed25519` (ed25519, sem senha) — **pública ainda não instalada no nó** |
| Acesso a `10.107.1.23` | ✅ **alcança** — ping 2 ms, SSH responde. Autenticação é que falta |
| BDGDs presentes | **2** — Enel SP (`C:\Elder\Enel_SP_390_...gdb`) e Roraima, ambas em `C:\Elder\BDGDs\` |
| `BDGD2DSS_BASES` | `C:\Elder\BDGDs` |
| Memória | 17 GB livres → **`--jobs 5`**, mais que isso pagina |
| `rsync`, `zip` | ausentes (use `scp` e `tar`) |
| `gh` (GitHub CLI) | ❌ ausente. `winget` existe e instala |

### PC de casa — a máquina que tem as bases

| | |
|---|---|
| Pasta do projeto | ❓ **a preencher** |
| BDGDs presentes | `/d/Elder/Elder/BDGDs` — as 7, conferido em 24/08/2026 |
| Ambiente `.venv` | ❓ a confirmar |
| Chave SSH | ❓ a confirmar |
| Acesso a `10.107.1.23` | ❓ a confirmar (provavelmente só por VPN) |
| `rsync`, `zip` | ausentes, conferido em 24/08/2026 |

> **A assimetria é o fato central do projeto hoje.** As bases estão numa
> máquina e o cluster é alcançado da outra. O `cluster/enviar.sh` empurra a
> BDGD *da máquina onde roda* para o nó — então, do jeito que está, quem sobe
> base é o PC de casa, e ele precisa enxergar o nó. Enquanto isso não for
> testado, o caminho inteiro do cluster está bloqueado por uma pergunta de
> rede, não de código.

---

## Perguntas abertas

Quem souber a resposta, responde aqui e apaga a pergunta. **Pergunta
respondida vira linha na tabela de estado**, não fica acumulando.

1. **O PC de casa alcança `10.107.1.23`?** ⚠️ *Respondida só metade.* O
   CEAMAZON alcança (2 ms — está dentro da rede). Falta saber do PC de casa,
   que provavelmente precisa de VPN. Testar: `ssh <usuario>@10.107.1.23`.
4. ~~**Qual é o usuário no Ubiratan?**~~ **RESPONDIDA em 25/08/2026:** é
   `teste`, uma conta **compartilhada** de avaliação, com um diretório
   `~/elder/` reservado. Um usuário só seu foi solicitado ao Carlos Eduardo e
   está pendente.
5. **O nó tem internet?** O `cluster/LEIA-ME.md` começa por `git clone`, e o
   `instalar.sh` cai em micromamba via `curl` se o Python do sistema não
   servir. As duas coisas precisam de saída para a internet, e num cluster isso
   é frequentemente bloqueado. É o que o `primeiro_contato.sh` mede.
2. **Como as 6 BDGDs que faltam chegam ao CEAMAZON**, se for esse o caminho?
   HD externo, rede, ou nuvem. São ~45 GB.
3. **As wheels de `pyogrio` e `opendssdirect.py` existem para Python 3.14?**
   O CEAMAZON tem 3.14.3, que é recente. Se não existirem, o `.venv` precisa
   de um Python mais antigo.

---

## ⚠️ Nunca escreva credencial aqui

**Este arquivo vai para um repositório público no GitHub.** Senha, token, chave
privada ou CPF colocados aqui ficam expostos para sempre — apagar num commit
seguinte não resolve, porque o histórico guarda o conteúdo antigo, e o certo
passa a ser trocar a credencial, não editar o arquivo.

O que pode entrar: **usuário, IP, nome de fila, caminho.** Nada que autentique.

Onde as credenciais moram, de verdade:
- chave privada em `~/.ssh/id_ed25519`, nunca versionada, nunca copiada entre
  máquinas;
- senha, só digitada por você na hora, nunca gravada em arquivo do projeto.

---

## O cluster Ubiratan — o que é fato

Do manual do usuário (39 páginas) e do repasse do administrador, 25/08/2026.

| | |
|---|---|
| Endereço | **`10.107.1.23`** |
| Usuário hoje | `teste` — **conta compartilhada**, diretório próprio em `~/elder/` |
| Acesso | só dentro da rede UFPA/CEAMAZON, ou por VPN |
| Sistema | Oracle Linux 8.8 (base RHEL 8) |
| Escalonador | PBS/Torque |
| Nós | **3**, nomeados `n01`–`n03` |
| Por nó | 2× AMD EPYC 7713. O PBS reporta **`ncpus=256`** (SMT ligado sobre 128 núcleos físicos) e **251 GB** de RAM |
| Nó de acesso | 32 núcleos, 62 GB — **não é onde se roda nada** |
| `/home` | 15 TB, **11 TB livres**, compartilhado entre todos |
| `/tmp` | 200 GB, mas só **11 GB livres** — não serve de área de trabalho |
| `/scratch/local` | 960 GB, local a cada nó |
| Internet no nó | ✅ **tem** — pypi, github e dadosabertos respondem 200. Não é preciso modo `--offline` |
| Ferramentas lá | `git`, `rsync`, `zip`, `unzip`, `tar`, `sha256sum` — **`rsync` existe no nó**, embora não exista no Windows |

### As 7 filas, medidas em 25/08/2026

`qstat -q` no nó. **`workq` está desabilitada.** Todas vazias: 0 rodando, 0 na
fila — o cluster estava ocioso.

| fila | nós máx. | walltime máx. |
|---|---:|---:|
| `BIRA_Q1` | 3 | 2160 h (90 dias) |
| `BIRA_Q2` | 3 | 720 h |
| **`BIRA_Q3`** | 3 | **480 h** — é a que o `uma_base.pbs` usa |
| `BIRA_Q4` | 3 | 72 h — a do modo interativo |
| `BIRA_Q5` | 2 | 72 h |
| `BIRA_Q6` | 1 | 72 h |
| `BIRA_Q7` | 1 | 48 h |

O `walltime=12:00:00` do `uma_base.pbs` cabe em qualquer uma delas com folga
enorme.

### Três coisas que os documentos diziam errado

**1. Não é Torque, é OpenPBS 22.05.11** (`/opt/pbs/bin`). O `docs/CLUSTER.md`
diz "PBS/Torque". Acerta a família e erra o produto, e isso não é preciosismo:
`-l nodes=1:ppn=32` é sintaxe Torque, que o PBS Pro aceita como forma **legada
traduzida** para `select=1:ncpus=32`. O exemplo do próprio administrador também
usa a forma antiga, então ela provavelmente funciona — **mas isso não foi
verificado**, e um job que recebe 1 núcleo em vez de 32 termina, sem erro, 32
vezes mais devagar.

**2. Havia 2 filas citadas; há 7.** `BIRA_Q3` e `BIRA_Q4` vieram do exemplo do
administrador e por sorte existem.

**3. O `module load` do `instalar.sh` não acerta nenhum nome.** Os módulos de
Python do Spack aparecem no `module avail` mas o `load` responde
`unknown` — o `MODULEPATH` só tem as árvores do OpenHPC, e não
`/opt/spack/share/spack/modules/`. Nem `module use` resolveu.

**O que funciona, e é o caminho a usar:** apontar direto para o binário, que o
`instalar.sh` aceita por variável.

```
PYTHON=/opt/spack/opt/spack/linux-oracle8-x86_64/gcc-12.2.0/python-3.11.4-cnmrtip6m2qg5tblnohchxnvjtkl6jgr/bin/python3
```

O Python do sistema é **3.6.8**, velho demais — a ferramenta pede 3.9+.

**`ppn=32` do `uma_base.pbs` está justificado.** O nó tem 128 núcleos e 256 GB,
então 32 processos × 3 GB = 96 GB cabem com folga. A regra de memória do
projeto não é o gargalo aqui.

**Atenção a um erro de digitação que circulou:** o repasse do administrador diz
`10.107.1.123` em dois lugares e `10.107.1.23` em outro. **O certo é
`10.107.1.23`** — foi o que respondeu ao ping (2 ms) e o que aparece no
terminal do administrador. `ubiratan.ufpa.br` não resolveu.

---

## Como preencher: o tutorial

### Quando escrever

Escreva uma entrada **toda vez que a outra máquina precisaria saber** — não a
cada comando. O teste é: *"se eu sentar na outra máquina semana que vem, isto
me pouparia tempo ou me evitaria refazer algo?"* Se sim, entra.

Entra: decisão tomada, número medido, coisa que quebrou e por quê, tarefa
deixada pela metade, submissão feita no cluster.

Não entra: comando que funcionou como esperado, saída de execução (ela vive em
`logs/`), nem nada que o `git log` já conte sozinho. **Este arquivo é o que o
commit não registra.**

### O modelo — copie daqui

```markdown
## AAAA-MM-DD — <CEAMAZON | CASA>

**Feito.** O que efetivamente mudou de estado. Verbo no passado, um item por
linha.

**Medido.** Números, com a unidade. Se não houver, apague a linha.

**Quebrou.** O que falhou e a mensagem real, não o resumo dela.

**Para a outra máquina.** O que a próxima sessão precisa fazer, ou o que ela
não deve refazer. **Esta é a linha mais importante do modelo** — é a única
endereçada a alguém.

**Commit.** O `<hash curto>` que fecha a sessão, se houver.
```

### As três regras

**1. Entrada nova vai no FIM do diário.** Ordem cronológica, sempre. A
tentação de pôr a mais recente no topo custa caro: as duas máquinas passariam a
escrever na mesma linha e todo `pull` daria conflito.

**2. Assine a máquina, não a pessoa.** É sempre você nas duas pontas. O que
distingue uma sessão da outra é *onde* ela aconteceu — porque é o ambiente que
muda o que é possível.

**3. Não apague entrada antiga, nem corrija número passado.** Se um número
estava errado, a entrada nova diz que estava e por quê. Achado 44 do
`ACHADOS_GENERALIZACAO.md` existe justamente porque uma escolha antiga ficou
registrada e pôde ser reexaminada.

### Se der conflito no `git pull`

Vai dar, uma hora — as duas máquinas escrevendo no mesmo arquivo. **Neste
arquivo o conflito tem sempre a mesma solução: ficam as duas entradas, na
ordem das datas.** Nunca escolha um lado.

```bash
git pull --rebase
# abra docs/ENTRE_MAQUINAS.md, apague as marcas <<<<<<< ======= >>>>>>>
# e deixe as duas entradas, a mais antiga primeiro
git add docs/ENTRE_MAQUINAS.md
git rebase --continue
git push
```

Se embananar e quiser recomeçar do zero sem perder nada: `git rebase --abort`
devolve tudo ao estado anterior ao `pull`.

---

# O diário

## 2026-08-25 — CEAMAZON

**Feito.**
- Repositório clonado em `C:\Elder\ENEL\BDGD2DSS` — máquina nova, primeira vez
  que o projeto roda aqui.
- Git configurado: `Elder <eldermendes40@gmail.com>`, a mesma identidade dos
  177 commits anteriores, para o histórico não se fragmentar em dois autores.
- Levantado o que esta máquina tem e não tem (ver a tabela de estado).
- Este arquivo criado.

**Medido.**
- 177 commits, 15 branches remotas, 35 MB de repositório.
- Repositório **público**, com 0 forks e 1 star.
- Achados **48 a 55** aparecem no código e nos testes
  (`test_teto_de_iteracoes.py`, `test_perdas_do_trafo.py`,
  `test_pac_invertido.py`, `test_sem_at.py`) e **não têm seção** no
  `ACHADOS_GENERALIZACAO.md`, cuja última alteração foi em 21/08 e que termina
  no achado 47. **Oito achados vivem só na mensagem de commit.**

**Quebrou.**
- Nada rodou ainda: `import opendssdirect` falha, não há `.venv` nesta máquina.

**Para a outra máquina.**
- **Responda as perguntas abertas 1 e 2** — o caminho do cluster está parado
  nelas, e só o PC de casa pode responder.
- O ciclo do `cluster/LEIA-ME.md` **nunca foi executado**: não existe
  `contato.txt` em lugar nenhum. O passo 3 (`primeiro_contato.sh` no nó) segue
  sendo o próximo do bloco de cluster.
- Não refaça o levantamento desta máquina; está na tabela acima.

**Commit.** —

## 2026-08-25 (continuação) — CEAMAZON

**Feito.**
- `.venv` criado e `requisitos.txt` instalado. **O risco do Python 3.14 não se
  materializou**: existem wheels `cp314` para tudo.
- `doutor.py` passou — OpenDSS resolve circuito de verdade, CRLF fixo, `spawn`.
- Chave SSH gerada em `~/.ssh/id_ed25519`, **sem senha**, para permitir uso não
  interativo. A pública ainda **não foi instalada no nó**.
- Roraima trazida para `C:\Elder\BDGDs\` e `.gitignore` corrigido.

**Medido.**
- Nó `10.107.1.23`: ping **2 ms**, SSH responde
  `Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password)`. Rede
  ✅, credencial ❌. O nó **aceita senha**, além de chave.
- 17 GB livres → cabem ~5 processos, não 8. Usar `--jobs 5` nesta máquina.

**Quebrou.**
- Quase: a pasta `BDGDs/` foi criada **dentro** do repositório e o `.gdb` é uma
  *pasta*, que escapava das regras `*.zip`/`*.rar` do `.gitignore`. Um
  `git add -A` — o ritual que este próprio arquivo prescreve — teria empurrado
  **320 MB de base para um repositório público**. Corrigido com `BDGDs/` e
  `*.gdb/` no `.gitignore`, e a pasta movida para fora do projeto.

**Para a outra máquina.**
- **A chave privada NUNCA sai da máquina onde nasceu.** O PC de casa gera a
  dele, separada. Duas máquinas, duas chaves, as duas públicas instaladas no
  nó — nunca copie `id_ed25519` de uma para a outra.
- O `BDGD2DSS_BASES` do CEAMAZON é `C:\Elder\BDGDs`. Se o de casa continuar
  em `/d/Elder/Elder/BDGDs`, os caminhos divergem e todo comando precisa da
  variável — não escreva caminho absoluto em script nenhum.

**Commit.** —

## 2026-08-25 (o Python 3.12 escondido) — CEAMAZON + NÓ

**A ferramenta não rodava no cluster, e o motivo não aparecia em teste nenhum
feito no Windows.**

**Feito.**
- `bdgd2dss/tabelas.py` corrigido. Verificado no nó: compila no 3.11 e a linha
  de saída sai **idêntica** à do 3.14.
- `diagnosticos/bt_completo.py`: passou a juntar `stderr` ao `stdout`.

**Medido.**
- O job **34037** rodou em `n02` e as **sete bases falharam em 5 segundos**,
  com a mensagem de erro **em branco**.
- Causa: `bdgd2dss/tabelas.py:73` usava expressão de f-string quebrando linha —
  **PEP 701, válido só a partir do Python 3.12**. O nó tem **3.11.4**; o
  CEAMAZON tem **3.14.3**.
- `converter.py` importa `tabelas` no topo, então **a ferramenta inteira morria
  no import**, em qualquer base, antes de ler um byte.
- `python -m compileall` com o 3.11 acusa **um único arquivo** no repositório
  inteiro. O conserto é local.

**Duas lições que valem mais que o conserto.**

1. **`ast.parse(feature_version=(3,11))` NÃO pega isso.** Rodei a varredura e
   ela deu limpo. A mudança de f-string do 3.12 é no *tokenizador*, e o
   `feature_version` filtra gramática. **O único juiz é um interpretador
   daquela versão de verdade** — `python -m compileall` no nó, que custa
   segundos.
2. **`capture_output=True` lendo só `p.stdout` engole `SyntaxError`.** Erro de
   import só existe no `stderr`. Sete bases reprovaram sem uma linha de motivo,
   e a tentação era culpar o conversor.

**Para a outra máquina.**
- **O `requisitos.txt` diz 3.9+ e isso não estava sendo verificado por nada.**
  Um Python novo demais na máquina de desenvolvimento esconde incompatibilidade
  com o alvo. Vale um passo de `compileall` na versão mínima antes de publicar.
- O `instalar.sh` aceita 3.9+, então o nó poderia ter caído num Python ainda
  mais antigo. O que salvou foi o Spack ter 3.11.

**Commit.** —

## 2026-08-25 (o acervo da ANEEL) — CEAMAZON

**A premissa de que baixar BDGD é caro estava errada, e ela sustentava o
`AS_53_BDGDS.md` inteiro.** Aquele documento planeja **15 bases** porque supõe
que cada uma custa disco local e um `scp` de horas. O nó tem internet e 11 TB
livres: o país inteiro cabe, e desce em minutos.

**Feito.**
- `baixar_bdgds.py` escrito e posto no nó. Baixa direto do acervo da ANEEL,
  confere `Content-Length`, extrai, apaga o `.zip` e grava manifesto com
  procedência (id, safra, versão, carimbo, SHA-256).

**Medido.**
- As `.gdb` **não estão no CKAN** da ANEEL, e sim no **ArcGIS Hub**, como itens
  de `owner:aneel_aneel`, tipo `File Geodatabase`. Download direto por
  `https://www.arcgis.com/sharing/rest/content/items/<id>/data`, **sem
  autenticação**.
- Acervo: **915 itens**, **114 distribuidoras** distintas.
- Safra **2024-12-31**: **97 bases**, **31,0 GB** compactado, ~111 GB extraído.
- Safra **2023-12-31: 113 bases** — mais que 2024. A safra 2024 **ainda está
  sendo publicada**; 16 distribuidoras que publicaram 2023 ainda não publicaram
  2024.
- As 17 que não têm 2024 somam só **0,8 GB**, e nove usam esquema **M6/M10**,
  gerações anteriores ao V11. `CPFL_Santa_Cruz_72` (2017) e
  `CPFL_Santa_Cruz_69` (2024) são agentes diferentes — as CPFLs de 2017 e a
  RGE 397 parecem concessões extintas por incorporação.

**Para a outra máquina.**
- **Não use `--safra 2024-12-31`; use `--safra-mais-nova`.** O script descobre a
  safra mais recente sozinho, e é assim que a de 2025 entra sem editar código.
  Mas leia o quadro por safra que ele imprime antes: durante a transição, a
  safra mais nova tem poucas distribuidoras, e baixar 3 achando que são todas é
  o erro fácil.
- **Não é preciso ter `.gdb` no PC de casa.** As bases vivem no nó. O que viaja
  são `logs/` e `.json`, que são kilobytes.
- O `AS_53_BDGDS.md` precisa ser revisto: a amostragem por 15 bases resolvia um
  problema de custo que não existe mais.

**Commit.** —

## 2026-08-25 (canário) — CEAMAZON

A Roraima rodou **localmente**, não no cluster — o SSH ainda está sem
autenticação. Serve como prova real do passo 4 do `CLUSTER.md` e como
referência para comparar com a rodada do nó quando ela acontecer.

**Feito.**
- `converter.py` + `validador.py` na Roraima, saída em `TESTE_RR`, `--jobs 5`.

**Medido.**
- Conversão: **20 subestações em 0,2 min**.
- Validação: **20/20** compilam, resolvem, convergem, **0 NaN**, 0 sobrecarga.
  **15 de 20 sem ressalva.**
- As 5 com ressalva:

  | subestação | classe | o quê |
  |---|---|---|
  | 5003625 | `TENSAO_BAIXA` | Vmed=0,812, perdas 6,7%, 288 km/alim |
  | 5003532 | `TENSAO_BAIXA` | Vmed=0,940, **perdas 32,1%**, 339 km/alim |
  | 5003488 | `TENSAO_BAIXA` | Vmed=0,891, perdas 18,2%, 354 km/alim |
  | 5003585 | `MODELO_QUEBRADO` | 3 cargas sem tensão — trecho sem ligação |
  | 5003525 | `MODELO_QUEBRADO` | 6 cargas sem tensão — trecho sem ligação |

- `EQSE` com **24.541 registros não lidos**; `UNCRBT`, `UNREBT`, `UNSEBT`
  vazias ou ausentes. É o critério 7 do `PLANO_V1.md`, em 30%.

**A conferir — a conversão ficou ~9× mais rápida que o registrado.** O
`PLANO.md` anota **1,9 min** para a Roraima; aqui deu **0,2 min**. A explicação
provável é o achado 36 ("85% da conversão era revarredura de geometria"), que é
posterior àquela medição — mas **isso não foi confirmado**, e pode ser só
diferença de máquina. Importa porque o `walltime` de 12 h do `uma_base.pbs` foi
dimensionado pela Cemig-D em 5,5 h *na medição antiga*. Se o ganho for real, a
folga é bem maior que a suposta.

**Para a outra máquina.**
- `TESTE_RR` **não é rodada oficial** — é `TESTE_*`, ignorado pelo git e
  descartável. Não compare geração com ele; a referência é a V18/V19.
- Quando o nó rodar a Roraima, os números acima são o gabarito: **qualquer
  divergência é diferença de ambiente**, porque o modo `cluster` não muda
  nenhuma conta (ver `CLUSTER.md`, "O modo, e o que ele não faz").

**Commit.** —
