# -*- coding: utf-8 -*-
"""A orientação do regulador de tensão — de que lado está a carga.

ACHADO 59. O `RegControl` é emitido com `winding=2`, o que assume que o
`PAC_2` do registro UNREMT é o lado da carga. **A BDGD não declara direção.**
Quando o `PAC_2` é o lado da fonte, três coisas acontecem juntas:

1. o controle regula uma tensão que ele não pode mudar — a da fonte —, então
   nunca atinge o alvo e **corre o tape até o limite**;
2. o tape no enrolamento da fonte **divide** a tensão do lado da carga, então
   a rede fica pior do que ficaria sem regulador nenhum;
3. a ferramenta reporta `REGULADOR_SATURADO` e culpa a rede pelo defeito.

Medido em 03/09/2026, com o tape zerado para separar o efeito da causa:

    subestacao   sem regulador   como estava   controle no lado certo
    NHER3            0,9869        0,8984            1,0266
    IJI              0,9960        0,9056            1,0194

Ou seja: o regulador invertido subtrai cerca de **0,09 pu** da mediana, e
corrigi-lo devolve mais do que desligá-lo.

O CRITÉRIO É A DIREÇÃO DO FLUXO, e cheguei nele depois de errar duas vezes:

- «qual lado tem maior tensão» **não serve**. O regulador tem impedância quase
  nula (`XHL=0,04`, `%R=0,01`), então os dois lados diferem por 0,0002 pu —
  ruído. Uma estatística inteira que eu quase publiquei vinha disso.
- «qual lado está mais perto da fonte» **não serve**: o elemento tem
  comprimento zero e `Bus.Distance()` devolve o mesmo valor nos dois lados.

A potência não tem essa ambiguidade. O terminal por onde a potência **entra**
no elemento é o lado da fonte, e isso não depende de tape, de impedância nem
de geometria.

O QUE ISTO NÃO RESOLVE: regulador em trecho sem fluxo. Sem corrente não há
direção a medir, e ali a orientação fica como a BDGD a deixou — declarado, e
não adivinhado. Na Roraima são 70 dos 127.
"""

# Abaixo disto o fluxo não distingue lado nenhum: e' ruido numerico, nao
# direcao. Medido: os reguladores realmente carregados da NHER3 conduzem 51 kW
# e os de trecho morto, 0,00.
FLUXO_MINIMO_KW = 0.01


def lado_da_fonte(p_por_terminal):
    """Qual enrolamento é o da fonte: 1, 2, ou `None` quando não há fluxo.

    `p_por_terminal` é a potência ativa somada de cada terminal, na ordem dos
    enrolamentos. Positivo = entrando no elemento.
    """
    if not p_por_terminal or len(p_por_terminal) < 2:
        return None
    a, b = p_por_terminal[0], p_por_terminal[1]
    if max(abs(a), abs(b)) < FLUXO_MINIMO_KW:
        return None
    return 1 if a > b else 2


def corrigir(reguladores):
    """Quais `RegControl` estão no lado errado, e para onde vão.

    `reguladores` é uma lista de dicionários com `nome`, `winding` e
    `p_terminais`. Devolve (correcoes, sem_fluxo), onde cada correção é
    `{'nome', 'de', 'para', 'kW'}`.
    """
    correcoes, sem_fluxo = [], []
    for r in reguladores or []:
        fonte = lado_da_fonte(r.get('p_terminais'))
        if fonte is None:
            sem_fluxo.append(r.get('nome'))
            continue
        w = r.get('winding')
        if w != fonte:
            continue                     # ja esta no lado da carga
        # O controle esta no lado da fonte. O lado da carga e o OUTRO — e com
        # dois enrolamentos isso e sempre 3 menos o numero.
        correcoes.append({'nome': r.get('nome'), 'de': w, 'para': 3 - w,
                          'kW': max(abs(x) for x in r['p_terminais'][:2])})
    return correcoes, sem_fluxo


CABECALHO = """! ==========================================================================
!  ORIENTACAO DOS REGULADORES — achado 59
! ==========================================================================
!  O `RegControl` e emitido com `winding=2`, assumindo que o PAC_2 do UNREMT e
!  o lado da CARGA. A BDGD nao declara direcao, e quando o PAC_2 e o lado da
!  FONTE o controle regula o que nao pode mudar: corre o tape ate o limite e,
!  porque o tape no enrolamento da fonte DIVIDE o lado da carga, deixa a rede
!  pior do que ficaria sem regulador nenhum.
!
!  Medido: o regulador invertido subtrai cerca de 0,09 pu da tensao mediana.
!
!  O criterio e a DIRECAO DO FLUXO — o terminal por onde a potencia entra e o
!  lado da fonte. Tensao nao serve (os dois lados diferem por 0,0002 pu, que e
!  ruido) e distancia nao serve (o elemento tem comprimento zero).
!
!  {n} regulador(es) corrigido(s) de {total} medido(s).
!  {sem} sem fluxo: sem corrente nao ha direcao, e a orientacao fica como a
!  BDGD a deixou — declarado, e nao adivinhado.
!
!  Para rodar SEM esta correcao, apague o `redirect _REGULADORES.dss` do
!  MASTER. O modelo continua valido; o que muda e o regulador regular ou nao.
! =========================================================================="""


CABECALHO_BYPASS = """
! --------------------------------------------------------------------------
!  BYPASS DE REGULADOR FECHADO — achado 69
! --------------------------------------------------------------------------
!  Em campo o regulador fica entre uma chave de entrada e uma de saida, e uma
!  CHAVE DE BYPASS liga as duas pontas por fora. Com o regulador em servico o
!  bypass fica ABERTO; a BDGD o declara fechado, e o regulador tentando impor
!  10% contra um caminho de impedancia nula circula corrente de laco. Na
!  5001306 da EQUATORIAL6072 eram seis, com 394 a 2.027 A.
!
!  A trava do achado 48 so reconhece o bypass entre os dois PACs do proprio
!  regulador. Este liga os PACs das chaves vizinhas, e nenhuma das chaves do
!  laco toca o regulador — a regra topologica marcaria todas.
!
!  O CRITERIO E ELETRICO: dos candidatos do laco, servem os que, abertos,
!  nao desenergizam no nenhum; deles abre-se o que poe mais carga no
!  regulador. A chave em serie, aberta, deixa o regulador com 0 kW. Chaves em
!  paralelo no mesmo par de barras abrem juntas. Quando nenhum candidato faz
!  o regulador conduzir mas abrir desfaz a circulacao, o regulador nao tem
!  carga a jusante e abre-se o de menor perda. Trecho de linha so entra se o
!  laco nao tem chave. Cada caso e dito na linha dele.
!
!  O elemento e o controle saem juntos: `SwtControl State=Closed` fecharia de
!  novo a chave que um `Open` abrisse.
!
!  {n} bypass aberto(s), {amb} laco(s) com regulador sem decisao.
! --------------------------------------------------------------------------"""


def escrever(caminho, correcoes, total=0, sem_fluxo=(), escreve=None,
             bypass=(), sem_decisao=()):
    """Escreve o `_REGULADORES.dss`. SEMPRE, mesmo vazio.

    O MASTER redireciona sem condição, e `redirect` de arquivo ausente aborta
    a compilação. Vazio também é informação: diz que a conferência rodou.

    `bypass` são as chaves abertas pelo achado 69, cada uma
    `{'chave', 'controle', 'regulador', 'kW'}`, e vêm ANTES da orientação:
    a orientação foi medida com elas já abertas. `sem_decisao` são
    `{'regulador', 'candidatas', 'motivo'}`.
    """
    out = []
    if bypass or sem_decisao:
        out += [CABECALHO_BYPASS.format(n=len(bypass),
                                        amb=len(sem_decisao)).lstrip('\n'), '']
        for b in bypass:
            elementos = b.get('chaves') or [b['chave']]
            if b.get('sem_carga'):
                nota = ('laco de %s; regulador sem carga a jusante, aberto o '
                        'de menor perda' % b['regulador'])
            else:
                nota = ('bypass de %s, que passa a conduzir %.1f kW'
                        % (b['regulador'], b['kW']))
            if len(elementos) > 1:
                nota += '; %d em paralelo, abertos juntos' % len(elementos)
            if (b.get('equivalentes') or 1) > 1:
                nota += '; %d candidatos equivalentes' % b['equivalentes']
            if b.get('tipo') == 'trecho':
                nota += '; TRECHO de linha, nao chave: o laco nao tem chave'
            for i, e in enumerate(elementos):
                out.append('Edit %s enabled=no%s'
                           % (e, '   ! ' + nota if i == 0 else ''))
            for c in (b.get('controles')
                      or ([b['controle']] if b.get('controle') else [])):
                out.append('Edit %s enabled=no' % c)
        for s in sem_decisao:
            out.append('! sem decisao: %s — %s (%s)'
                       % (s['regulador'], s['motivo'],
                          ', '.join(s['candidatas']) or 'nenhuma chave'))
        out.append('')
    out += [CABECALHO.format(n=len(correcoes), total=total,
                             sem=len(sem_fluxo)), '']
    if correcoes:
        for c in sorted(correcoes, key=lambda x: -x['kW']):
            out.append('RegControl.%s.winding=%d'
                       '   ! estava no %d (lado da fonte), conduz %.1f kW'
                       % (c['nome'], c['para'], c['de'], c['kW']))
    else:
        out.append('! nenhum regulador invertido nesta subestacao.')
    texto = '\n'.join(out) + '\n'
    if escreve is not None:
        escreve(caminho, texto)
    else:
        from . import escrita
        escrita.escreve(caminho, texto)
    return texto
