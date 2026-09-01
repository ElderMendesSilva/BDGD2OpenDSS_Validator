# -*- coding: utf-8 -*-
"""O que o conversor LE da BDGD, e o que ele deixa de ler — com o numero.

POR QUE EXISTE. O criterio 7 do PLANO_V1 pede as tabelas que sobraram
"resolvidas OU DECLARADAS". Declaracao que mora so num documento envelhece: a
safra seguinte muda os numeros e o documento continua dizendo os antigos.

Aqui a declaracao sai a CADA RODADA, com os numeros DAQUELA base, dentro do
`relatorio_rede.json`. Quem auditar o modelo ve o que ficou de fora e quanto
era, sem depender de ninguem ter atualizado um `.md`.

O QUE FOI MEDIDO NAS SETE, em 24/08/2026:

    tabela      registros    onde
    EQSE        3.026.708    nas sete
    UNSEBT        158.656    so em SP, LT, CMIG e CPFL — zero nas outras tres
    UNCRBT              0    ZERO nas sete
    UNREBT        ausente    a camada nao existe em base nenhuma

E POR QUE CADA UMA FICA DE FORA

`EQSE` — o detalhe de equipamento de cada chave. Medido em Roraima: o
`COR_NOM` dela e IDENTICO ao da UNSEMT em 23.962 de 23.962 casos, com zero
diferencas e zero registros exclusivos. Ou seja, a ampacidade que ela traz o
conversor ja tem. O que ela tem de proprio e `ELO_FSV` (elo fusivel) e
`MEI_ISO` (meio de isolacao): dado de PROTECAO e de patrimonio, que nao entra
no fluxo de potencia.

    Ela ja pagou uma divida, ainda assim: as 58 chaves que curto-circuitavam o
    regulador do ESM01 (achado 48) tem `ELO_FSV = '0'`, ou seja NAO sao
    fusiveis — sao chaves mesmo. Isso confirma a leitura de que sao bypass.
    Valor de diagnostico, e nao de modelagem.

`UNCRBT` e `UNREBT` — capacitor e regulador de BAIXA tensao. Nao ha o que
decidir: uma tem zero registros nas sete e a outra nao existe como camada.

`UNSEBT` — chave de baixa tensao. So faz diferenca com a rede de BT modelada,
que e o criterio 5 e esta em aberto. E ela falta em tres das sete bases, o que
por si so impede tratar como fonte confiavel.
"""

# As que o conversor NAO le, e o motivo em uma linha. A contagem sai da base
# em uso, e nao daqui: numero escrito no codigo envelhece na safra seguinte.
NAO_LIDAS = {
    'EQSE': 'detalhe de equipamento da chave; COR_NOM identico ao da UNSEMT '
            '(23.962/23.962 em RR). ELO_FSV e MEI_ISO sao dados de protecao e '
            'patrimonio, fora do fluxo de potencia',
    'UNSEBT': 'chave de BAIXA tensao; so vale com a rede de BT modelada '
              '(criterio 5, em aberto), e falta em tres das sete bases',
    'UNCRBT': 'capacitor de BAIXA tensao; zero registros nas sete',
    'UNREBT': 'regulador de BAIXA tensao; a camada nao existe em base nenhuma',
}


def censo(bdgd, log=None):
    """Quantos registros tem cada tabela que o conversor deixa de ler.

    Devolve `{tabela: {'registros': n | None, 'motivo': str}}`, com `None`
    quando a camada nem existe na base. Nunca levanta: isto e relatorio, e
    relatorio que derruba conversao nao serve para nada.
    """
    out = {}
    for tab, motivo in sorted(NAO_LIDAS.items()):
        try:
            n = bdgd.n_registros(tab)
        except Exception:
            n = None
        out[tab] = {'registros': n, 'motivo': motivo}
    if log:
        tem = [f'{t} {d["registros"]:,}' for t, d in out.items()
               if d['registros']]
        ausentes = [t for t, d in out.items() if not d['registros']]
        # AS PARTES SAEM ANTES DO f-STRING, e nao dentro dele. Expressao de
        # f-string que quebra linha so passou a ser valida no Python 3.12
        # (PEP 701); o `requirements.txt` declara 3.9+ e o no do cluster tem
        # 3.11.4, onde este modulo nao COMPILAVA — e como `converter.py` o
        # importa no topo, a ferramenta inteira morria no import, em qualquer
        # base, antes de ler um byte. Custou um job de diagnostico inteiro.
        lidas = ', '.join(tem) if tem else 'nenhuma com dado'
        vazias = ((' | vazias ou ausentes: %s' % ', '.join(ausentes))
                  if ausentes else '')
        log(f'  tabelas nao lidas: {lidas}{vazias}')
    return out
