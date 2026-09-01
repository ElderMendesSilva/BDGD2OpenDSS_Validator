# -*- coding: utf-8 -*-
"""Conversor/auditor BDGD -> OpenDSS.

A VERSAO NAO SUBSTITUI A PROCEDENCIA, e as duas respondem perguntas
diferentes. `__version__` diz QUAL ENTREGA e esta — serve para quem baixa o
repositorio, cita o trabalho ou compara com o que leu num artigo. O
`_procedencia.json` diz de qual COMMIT, com qual Python e com qual versao do
motor OpenDSS um modelo especifico saiu, que e o que reproduz um numero.

Ate 01/09/2026 so existia a segunda. Funcionava para nos, que temos o
historico do git a mao, e nao para ninguem de fora.

A v1.0 e a safra BDGD 2024-12-31: 97 distribuidoras, 4.201 subestacoes, 97,4%
com veredicto OK e dezessete achados medidos. O que ela nao faz esta declarado
no README e no CHANGELOG — limitacao escrita e limitacao; limitacao descoberta
pelo usuario e defeito.
"""

__version__ = '1.0.0'

# A safra da BDGD que esta versao foi exercitada. NAO e a versao do formato
# (que a ANEEL chama de V11 no nome do arquivo): e a DATA-BASE dos dados. A
# safra 2025-12-31 saiu em 09/2026 e entra na v1.1.
SAFRA_VALIDADA = '2024-12-31'
