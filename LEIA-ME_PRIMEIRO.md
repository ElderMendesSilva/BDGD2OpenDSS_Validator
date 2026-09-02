# Leia-me primeiro

Você recebeu o **BDGD → OpenDSS**: uma ferramenta que lê uma BDGD da ANEEL
(`.gdb`) e devolve a rede da distribuidora modelada em OpenDSS — com o fluxo
resolvido, as 24 horas simuladas em passos de 15 minutos, as figuras e um
relatório em PDF por subestação.

Este arquivo tem só o necessário para sair do zero. O
[README.md](README.md) explica o que a ferramenta conclui, e o
[CHANGELOG.md](CHANGELOG.md) diz — de propósito, logo no começo — **o que ela
não faz**.

---

## 1. Instalar

Abra o **Git Bash** (ou o WSL) na pasta onde você descompactou, e rode:

```bash
bash instalar.sh
```

Sem argumento nenhum ele **não instala nada**: lista o que falta na sua máquina
e mostra o comando de cada item. Quando você tiver visto a lista e concordado:

```bash
bash instalar.sh --sim
```

Isso instala as bibliotecas de Python e, no Windows, o **OpenDSS da EPRI** e o
**Notepad++**. No fim ele confere sozinho e diz se ficou tudo de pé.

> **Você não precisa instalar o OpenDSS para a ferramenta funcionar.** O motor
> elétrico já vem embutido na biblioteca `opendssdirect` — que é o próprio
> OpenDSS compilado. O programa da EPRI serve para a interface gráfica e para
> a segunda opinião descrita no passo 4.

Se o Python não estiver instalado, o script diz o comando e para. No Windows:

```bash
winget install --id Python.Python.3.12
```

---

## 2. Conseguir uma BDGD

A ferramenta **não vem com dados**. A BDGD é pública e sai do portal da ANEEL,
uma por distribuidora, em `.gdb` (que é uma **pasta**, não um arquivo solto).

Se você já tem a sua, pule para o passo 3.

---

## 3. Rodar

```bash
python Validator.py
```

Abre uma janela. Logo no topo, em destaque, está **o caminho normal**: você
aponta a `.gdb` e clica em **RODAR TUDO**. A ferramenta converte, resolve,
simula o dia, valida e escreve os relatórios — sem mais nenhuma decisão sua.

O que sai, e onde:

```
MODELOS_<SIGLA>_<VERSÃO>/
├── <subestação>/
│   ├── MASTER-<subestação>.dss     o modelo, que abre no OpenDSS
│   └── RELATORIO/
│       ├── _PAINEL.pdf             O RELATÓRIO ESCRITO — comece por aqui
│       ├── _PAINEL.png             as 14 figuras num quadro só
│       └── perfil.png, dia.png…    cada figura em arquivo separado
└── RELATORIO/
    └── _GERAL.pdf                  o mesmo, para a concessão inteira
```

**Comece pelo `_PAINEL.pdf`.** A primeira página é a *ficha do circuito* — o
censo do que foi de fato simulado, lido da interface do OpenDSS, mais as
métricas que só a série de 96 passos produz (fator de carga, hora do pico,
coincidência entre a geração distribuída e a ponta de carga). Depois vêm as
figuras, uma por página, **cada uma com o parágrafo que a lê**.

Atrás do botão **`[ + ] Avançado`** ficam as etapas soltas, para quando você
quiser rodar só uma parte ou refazer um passo sem repetir os outros.

Uma concessão inteira leva da ordem de uma hora. Para experimentar antes,
escolha uma distribuidora pequena.

---

## 4. Se estiver no Linux

Roda inteiro, com uma diferença honesta: a etapa `verifica` compara o
resultado em **dois motores independentes** — a biblioteca e o COM da EPRI —, e
o COM é um servidor registrado no Windows, sem versão para Linux. No Linux essa
etapa roda com um motor só e **avisa no rodapé** que não houve confronto, em
vez de fingir que houve.

---

## 5. Quando algo der errado

- **O relatório saiu sem números.** Quase sempre a subestação não fechou. Abra
  o `_PAINEL.pdf` dela: a ficha do circuito e o veredicto na primeira página
  dizem o que aconteceu, e o texto avisa quando os números vêm de uma solução
  que o próprio OpenDSS não considera válida.
- **Faltou uma biblioteca.** `bash instalar.sh --conferir` diagnostica sem
  instalar nada.
- **Abrir um `.dss` no Bloco de Notas bagunçou o arquivo.** Use o Notepad++ —
  é por isso que ele está na lista de instalação.

---

## O que esperar dos resultados

A ferramenta julga o **modelo**, não a rede de verdade. Boa parte do que ela
acusa — trecho sem tensão, condutor acima da própria ampacidade, tensão
implausível — é **lacuna do cadastro publicado**, e não defeito da rede física
nem do conversor. Essa distinção é a tese central do projeto, e o texto do
relatório foi escrito para dizê-la em vez de escondê-la.

Os números medidos sobre as 97 distribuidoras estão em
[docs/ACHADOS_GENERALIZACAO.md](docs/ACHADOS_GENERALIZACAO.md), cada um com o
método e, quando foi o caso, a correção de um valor que publicamos errado
antes.
