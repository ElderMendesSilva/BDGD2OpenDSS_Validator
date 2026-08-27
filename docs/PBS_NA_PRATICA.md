# PBS na prática — notas de campo para outro agente

**O que é isto.** Notas de um agente (Claude Code) que levou uma ferramenta de
simulação de redes elétricas para um cluster PBS e rodou 97 bases de dados nele
em dois dias, em agosto de 2026. Cada item abaixo custou tempo real.

**Como usar.** Trate as afirmações marcadas 📍 como **hipóteses a verificar no
seu cluster**, nunca como fato — elas foram medidas num cluster específico e
vários vizinhos nossos discordariam. As marcadas 🌍 são propriedades do PBS ou
armadilhas de método, e devem transferir. Cada seção traz **o comando que
verifica**, para você não herdar a nossa configuração por engano.

**A parte mais importante deste documento é a seção 0.** Ela existe porque o
administrador do nosso cluster nos chamou a atenção, por escrito, sobre
comandos emitidos por agente.

---

## 0. Regras para você, o agente. Antes de qualquer comando.

### 0.1 Descubra a sua cota, e trate-a como teto da SOMA

O escalonador provavelmente **não vai te impedir** de tomar a máquina inteira.
📍 No nosso: nenhuma fila impõe limite de memória, não há `max_run` por
usuário, e os primeiros jobs saíram com `resources_assigned.mem = 0kb`.

Nós rodamos **20 jobs simultâneos** — ≈80 núcleos e ≈240 GB — com uma cota
combinada de **64 núcleos e 192 GB**. Nada nos barrou. Quem reclamou foi uma
pessoa, e havia outro usuário no mesmo nó.

**A cota não sai de comando nenhum. Pergunte a um humano.** E depois:

- o teto vale para a **soma de todos os seus jobs simultâneos**, não por job;
- **amarre memória a núcleo** no dimensionamento (nós usamos 3 GB por núcleo);
  assim basta contar `ncpus` e a memória segue;
- **antes de submeter em lote, conte o que já está rodando.**

```bash
qstat -an -u $USER | tail -n +6 | wc -l
```

### 0.2 Deixe o escalonador ser o guarda, não um laço seu

Não solte N jobs contando com vigilância. Monte `cota / ncpus` **correntes**
encadeadas — o número de correntes passa a ser o máximo de simultâneos, imposto
pelo PBS:

```bash
ANT=""
for BASE in $(cat lista.txt); do
    ANT=$(qsub ${ANT:+-W depend=afterany:$ANT} -v BASE="$BASE" job.pbs)
done
```

🌍 `afterany` continua mesmo se o anterior falhar; `afterok` só se ele deu
certo. Para varredura em lote, `afterany` costuma ser o certo — um dado ruim
não pode parar os outros 96.

### 0.3 Você não apaga nada no cluster

O administrador citou o `rm` por nome, referindo-se a comandos emitidos por
agente. Regras que adotamos:

- **Nunca `rm -rf` com glob.** `MODELOS_*` parece seu e pode não ser, sobretudo
  em conta compartilhada.
- **Rodada velha se aposenta, não se apaga.** Mova para `lixeira/<data>/` e
  deixe **uma pessoa** apagar depois, olhando.
- **Nada destrutivo sai de você direto para o nó.** Escreva o comando, e deixe
  um humano executar.
- **Use sufixo novo em vez de sobrescrever.** Nós quase apagamos a rodada
  anterior "para simplificar", e foi ela que permitiu medir o efeito de uma
  correção. Disco costuma ser o recurso mais barato do cluster — o nosso tinha
  11 TB livres.

### 0.4 Conta compartilhada

📍 A nossa era de avaliação, usada por mais gente. Se a sua também for:

- **nunca `gh auth login`** nem equivalente — o token fica legível por todos;
- **não configure identidade do git** na conta; você assinaria com o seu nome
  os commits de terceiros;
- **não presuma que um diretório é seu.**

---

## 1. Descubra QUAL PBS é, antes de escrever o script

🌍 "PBS" é família, não produto. Os dois comuns são **OpenPBS/PBS Pro** e
**Torque**, com sintaxes parecidas o bastante para enganar.

```bash
qstat --version
ls /opt/pbs/bin 2>/dev/null || command -v qsub
```

📍 A documentação interna do nosso dizia "PBS/Torque" e era **OpenPBS
22.05.11**.

```bash
#PBS -l nodes=1:ppn=32      # sintaxe TORQUE
#PBS -l select=1:ncpus=32   # sintaxe PBS Pro / OpenPBS
```

O OpenPBS aceita a forma antiga como **legada traduzida**. **O risco não é erro,
é silêncio:** se a tradução não acontecesse, o job receberia 1 núcleo em vez de
32 e terminaria 32 vezes mais devagar, sem uma linha de aviso.

**Verifique que foi honrado:**

```bash
qstat -an -u $USER      # procure  n02/1*32  — o *32 é o que você pediu
qstat -f <jobid> | grep -E 'Resource_List|exec_host'
```

## 2. O job não começa onde você acha

🌍 **O PBS inicia o job no `$HOME`, não na pasta de submissão.** Todo caminho
relativo quebra em silêncio.

```bash
cd "${PBS_O_WORKDIR:-$HOME/projeto}"
```

🌍 **Não confie no `PBS_NP`.** 📍 No nosso ele sai **vazio**. Tenha plano B:
contar linhas de `$PBS_NODEFILE`, ou deixar o programa decidir pela memória
livre.

```bash
echo "nucleos: ${PBS_NP:-$(wc -l < ${PBS_NODEFILE:-/dev/null} 2>/dev/null || echo '?')}"
```

## 3. Memória é recurso de CHUNK

🌍 Em PBS Pro/OpenPBS, `mem` pertence ao *chunk*, junto com `ncpus`. Um
`-l mem=96gb` escrito **ao lado** de `-l select=...` pode ser **ignorado sem
erro**. A forma segura:

```bash
#PBS -l select=1:ncpus=32:mem=96gb
```

📍 No nosso, com a forma legada, o `-l mem=` separado funcionou e apareceu como
`select=1:ncpus=32:mem=100663296KB`. **Confira no `qstat -f` que chegou.**

## 4. A armadilha que mais custou: a versão do Python do NÓ

🌍 Desenvolvemos em 3.14; o nó tinha 3.11. Uma linha usava expressão de
f-string quebrando linha — **PEP 701, válido só a partir do 3.12**. O módulo
não compilava, o `import` morria no topo, e **sete bases falharam em 5 segundos
com a mensagem de erro em branco**.

**Assinatura:** falha instantânea, em todos os casos, com stderr aparentemente
vazio.

**Duas lições que valem mais que o conserto:**

1. 🌍 **`ast.parse(feature_version=(3,11))` NÃO pega isso.** A mudança de
   f-string do 3.12 é no *tokenizador*; `feature_version` filtra gramática. **O
   único juiz é um interpretador daquela versão:**

```bash
"$PYTHON_DO_NO" -m compileall -q meu_pacote/     # custa segundos
```

2. 🌍 **`subprocess.run(capture_output=True)` lendo só `stdout` engole
   `SyntaxError`.** Erro de import só existe no `stderr`. Junte os dois antes de
   concluir que o programa está errado.

🌍 **Um Python novo demais na sua máquina esconde incompatibilidade com o
alvo.** Se o projeto diz "3.9+", teste no 3.9.

## 5. `module load` pode não funcionar

📍 No nosso, os módulos de Python apareciam no `module avail` e o `load`
respondia `unknown`: o `MODULEPATH` só tinha as árvores do OpenHPC, e não a do
Spack. `module use` também não resolveu.

🌍 **O que funciona quase sempre: apontar direto para o binário.**

```bash
ls -d /opt/spack/opt/spack/*/*/python-*/bin 2>/dev/null
compgen -c | grep -E '^python3\.[0-9]+$' | sort -u
python3 -V
```

📍 O Python do sistema era **3.6.8**; o Spack tinha **3.11.4**.

## 6. Autoteste como primeira linha do job

🌍 A falha clássica: o job espera a noite na fila, começa às 3 da manhã e morre
no minuto 2 por falta de biblioteca.

```bash
python doutor.py --bases "$MINHAS_BASES" || exit 1
```

O nosso confere versão do Python, bibliotecas importáveis, o motor de cálculo
resolvendo um caso real, fim de linha dos arquivos e se os dados de entrada
abrem. Custa 4 segundos e já salvou uma noite.

## 7. Fila esvaziando NÃO é prova de sucesso

🌍 **Este é um erro de agente, e nós cometemos.** Nosso monitor anunciou "TODAS
AS 97 FECHARAM" e era mentira: ele contava jobs na fila, e **91 sumirem em 5
minutos** era falha em massa, não conclusão.

**Confira o RESULTADO, nunca a ausência do processo.**

```bash
ls MODELOS_*/validacao_balanco.json | wc -l    # o que existe em disco
```

🌍 E o clássico do shell: `while read` **descarta a última linha** se o arquivo
não termina em quebra. Perdemos 1 base de 90 assim, com o laço reportando
`falhas: 0`.

## 8. Escrita concorrente no arquivo de resumo

🌍 Se N jobs leem–mesclam–gravam o mesmo JSON, eles se sobrescrevem. 48 bases
completaram e 45 entraram no nosso resumo. O teste que existia era
**sequencial** e passava.

Use escrita atômica, trava, ou — mais simples — **um arquivo por job** e um
passo de consolidação no fim.

## 9. `git` pode não existir no nó de EXECUÇÃO

🌍 O nó de acesso e os de trabalho podem ter software diferente. No nosso, a
procedência dos resultados saiu com o commit **vazio** nas 97 bases — e antes
do conserto ela dizia `limpo`, porque `git status --porcelain` não imprime nada
com a árvore limpa, que era exatamente o que o helper devolvia quando o comando
**falhava**.

1. 🌍 **Distinga "limpo" de "não deu para conferir".** Nosso campo virou
   `True`/`False`/`None`.
2. 🌍 **Passe o commit por variável de ambiente**, já que quem submete sabe:

```bash
qsub -v COMMIT="$(git rev-parse HEAD)" job.pbs
```

Sem isso a rodada é verificável só pela palavra de quem a rodou.

🌍 **Relacionado:** se a rodada deve ser UMA rodada, o nó tem de ficar pinado
num commit durante ela. Jobs que começam depois de um `git pull` rodariam
código diferente dos que começaram antes.

## 10. Onde escrever

📍 No nosso: `/home` 15 TB (11 livres, compartilhado), `/tmp` 200 GB mas **só
11 livres**, `/scratch/local` 960 GB **local a cada nó**.

🌍 `/tmp` de nó de cluster é lixo de todo mundo. Meça antes:

```bash
df -h /home /tmp /scratch 2>/dev/null
```

## 11. O nó pode ter internet — e isso muda o projeto

📍 O nosso tem: `pypi`, `github` e portais de dados responderam 200. Em vez de
subir 82 GB por `scp`, o nó baixou tudo em minutos.

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/simple/ https://github.com
```

🌍 **Meça antes de projetar em volta da suposição.** Muitos clusters bloqueiam
saída; o seu pode não bloquear.

## 12. Um nó pode estar caído sem aviso

📍 A documentação dizia 3 nós. `pbsnodes -l` mostrou dois em
`state-unknown,down`: tínhamos **um** nó de trabalho.

📍 Também achamos **7 filas** onde a documentação citava 2, e a `workq` padrão
estava **desabilitada** — submeter sem `-q` teria falhado.

```bash
pbsnodes -l
pbsnodes -a | grep -E 'Mom|state|resources_available'
qstat -q
```

## 13. MPI só se o problema pedir

🌍 Se o trabalho é **independente por unidade**, sem troca entre processos,
`nodes=2` não ajuda: o segundo nó fica parado. O que se aproveita é `ncpus`
**daquele** nó. Peça mais de um nó só quando houver comunicação real.

---

## Roteiro de primeiro contato

Rode isto e guarde a saída. Cada linha responde uma pergunta que custaria horas.

```bash
# escalonador
qstat --version; ls /opt/pbs/bin 2>/dev/null

# filas: quais existem, limites, quais estão desabilitadas
qstat -q

# nós: quantos, núcleos, memória, quais estão vivos
pbsnodes -a | grep -E 'Mom|state|ncpus|mem'
pbsnodes -l

# disco
df -h /home /tmp /scratch 2>/dev/null

# python
python3 -V
ls -d /opt/spack/opt/spack/*/*/python-*/bin 2>/dev/null
module avail 2>&1 | head -40

# ferramentas
for c in git rsync tar zip unzip sha256sum curl wget; do
    printf '%-10s %s\n' "$c" "$(command -v $c || echo AUSENTE)"; done

# internet
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/simple/ https://github.com

# o job vê o mesmo que o nó de acesso? rode o roteiro DENTRO de um job curto.
```

🌍 **O último item não é detalhe.** Metade das nossas surpresas — Python,
`git`, `PBS_NP` — foi diferença entre o nó de acesso e o de execução. Rode o
reconhecimento dentro de um job também.

**E a pergunta que nenhum comando responde: quanto do cluster é seu.** Pergunte
a uma pessoa, antes de submeter o primeiro lote.

---

## As três que eu diria a mim mesmo no primeiro dia

1. **Teste no Python do nó, não no seu.** Uma linha de sintaxe nova mata a
   ferramenta no import, em 5 segundos, com a mensagem em branco.
2. **Conte os núcleos antes de submeter.** O escalonador vai deixar você pegar
   a máquina inteira, e ele não é quem vai reclamar.
3. **Confira o resultado, nunca a ausência do processo.** Fila vazia significa
   que os jobs acabaram — não que funcionaram.
