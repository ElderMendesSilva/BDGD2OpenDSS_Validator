# -*- coding: utf-8 -*-
"""ESCREVER ARQUIVO DE MODELO SEMPRE DO MESMO JEITO, EM QUALQUER SISTEMA.

O problema, e ele e serio: `open(caminho, 'w')` traduz o `\\n` para o fim de
linha do SISTEMA. No Windows sai CRLF; no Linux sai LF. O mesmo codigo, lendo a
mesma BDGD, produziria arquivos DIFERENTES BYTE A BYTE em cada maquina.

Isso destruiria o metodo de verificacao do projeto. A prova de que uma mudanca
nao alterou o resultado e comparar os arquivos gerados byte a byte — foi assim
que se provou que o lote adaptativo, o `do_lote` das coordenadas e as cinco
etapas paralelas nao mexeram em nada. No dia em que uma geracao rodasse no
cluster e a anterior no laptop, TODOS os arquivos apareceriam como diferentes,
sem que um unico numero tivesse mudado. O metodo pararia de valer justamente
quando passasse a ser mais usado.

A ESCOLHA E CRLF, e nao LF, por um motivo so: e o que os modelos ja existentes
tem. As sete bases da V14 foram geradas no Windows. Adotar LF as invalidaria
todas de uma vez, obrigando a regerar 1.195 subestacoes para nao mudar numero
nenhum. O `.gitattributes` do projeto ja declara `*.dss text eol=crlf`, entao
CRLF tambem e o que o repositorio espera. O OpenDSS le os dois em qualquer
sistema.

Use `escreve()` para tudo que for artefato do modelo — `.dss`, `.dat`, o que o
usuario recebe. JSON e log nao passam por aqui: nao sao comparados byte a byte
e o `json.dump` ja tem regra propria.
"""
import os

# O fim de linha dos artefatos do modelo. Constante, e nao `os.linesep`: o
# ponto e justamente NAO depender do sistema.
FIM_DE_LINHA = '\r\n'


def abrir(caminho, modo='w'):
    """`open` para artefato de modelo: utf-8 e CRLF, em qualquer sistema."""
    return open(caminho, modo, encoding='utf-8', newline=FIM_DE_LINHA)


def escreve(caminho, texto):
    """Grava `texto` como artefato de modelo. Devolve o caminho."""
    with abrir(caminho) as fh:
        fh.write(texto)
    return caminho


def escreve_linhas(caminho, linhas, fim=True):
    """Grava uma sequencia de linhas, uma por linha, com quebra final.

    `fim=True` deixa a quebra no ultimo — que e o que todos os geradores do
    projeto ja faziam com `'\\n'.join(out) + '\\n'`, e mudar isso mudaria os
    arquivos.
    """
    texto = '\n'.join(linhas)
    return escreve(caminho, texto + '\n' if fim else texto)


def igual_ao_disco(caminho, texto):
    """Se o arquivo ja no disco tem exatamente este conteudo.

    Serve para nao reescrever o que nao mudou — e, principalmente, para os
    testes que comparam geracoes.
    """
    if not os.path.exists(caminho):
        return False
    with open(caminho, 'rb') as fh:
        return fh.read() == texto.replace('\n', FIM_DE_LINHA).encode('utf-8')
