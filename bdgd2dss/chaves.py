# -*- coding: utf-8 -*-
"""
UNSEMT -> New Line (Switch=Y) + New SwtControl

O campo P_N_OPE da BDGD indica o estado normal de operacao. As chaves
normalmente abertas sao o que separa os alimentadores entre si — sem elas,
todos os circuitos ficam em paralelo pela SOURCEBUS e a solucao diverge.

O estado e emitido DUAS vezes, de proposito:
  - no SwtControl (State=Open), que e a forma declarativa;
  - em comandos `Open Line.<nome> 1` no fim do MASTER, que garantem o estado
    mesmo com controlmode=off.
"""
from .leitor import num, txt, no
from .linhas import nos
from . import escrita
from . import dominios

# valores de P_N_OPE que significam chave aberta
ABERTA = {'A', 'ABERTA', 'ABERTO', '0', 'N'}


def bypass_de_regulador(bdgd, ctmts, log=None):
    """Os pares de PAC que tem um regulador entre eles.

    Chave FECHADA sobre esse par e o bypass do regulador, e bypass fechado
    com regulador em servico e um curto-circuito sobre o regulador.

    POR QUE ISTO EXISTE. O achado 32 ja tinha mostrado que o regulador da
    BDGD nao se liga a SSDMT: ele fica ENTRE DUAS CHAVES, e os dois PACs
    dele so existem na UNSEMT. O que faltava ver e que a CPFL declara
    dezenas de chaves NO MESMO PAR — 58 no ESM01, 73 no RIB02 —, todas com
    P_N_OPE='F'. Emitidas fechadas, elas ficam em paralelo com o regulador,
    cujo XHL e 0,04%: a impedancia do ramo paralelo fica na ordem de
    0,0007 ohm, o RegControl le subtensao, sobe o tape ate o maximo, e a
    corrente de circulacao explode.

    MEDIDO NO ESM01 DA CPFL, V18:

        REG_29143280 com 58 chaves fechadas em paralelo
        tape em 1,1000 (o maximo), barra de 11,4 kV em 0,1012 pu
        7.565 A no vao de 11,4 kV e 83.166 A no regulador
        perda da subestacao: 53,02%

        com as 58 chaves abertas: tape 1,0437, barra em 0,9981 pu,
        perda da subestacao: 0,75%

    Sao 8 reguladores na CPFL e ZERO nas outras seis bases. Sete deles sao
    exatamente os sete alimentadores da CPFL com perda modelada acima de
    2.500% na V18 — ESM01, NGR02, PRG07, UNE02, CDJ02, TNB01 e SCA01 —, os
    mesmos que carregavam a maior parte dos 81,7% de perda concentrada em
    alimentador implausivel.

    Devolve um `set` de pares ordenados `(pac_menor, pac_maior)`. Base sem
    UNREMT devolve vazio, e nada muda.
    """
    try:
        r = bdgd.ler_filtrado('UNREMT', 'CTMT', ctmts, ['PAC_1', 'PAC_2'])
    except Exception as e:
        if log:
            log(f'  AVISO: UNREMT indisponivel ({str(e)[:80]}) — bypass de '
                'regulador nao detectado, chaves em paralelo ficam sem trava')
        return set()
    pares = set()
    for i in range(len(r['PAC_1'])):
        a, z = no(r['PAC_1'][i]), no(r['PAC_2'][i])
        if a and z and a != z:
            pares.add((a, z) if a < z else (z, a))
    return pares


def gerar(bdgd, ctmts, caminho_chaves, caminho_controles, barras=None, log=None):
    """`barras` sao os nos que a rede de media tensao ja criou.

    Chave cujos DOIS PACs estao fora dela nao liga nada: cria uma ilha de duas
    barras sem fonte e sem caminho para a terra, a matriz de admitancia daquele
    pedaco fica singular e a tensao sai NaN. O NaN nao fica quieto — a perda do
    elemento vira NaN e contamina `Circuit.Losses()` da subestacao inteira.

    Medido na Cemig-D V11: 72 subestacoes de 413 reprovadas por exatamente 2
    nos NaN cada, sempre no mesmo formato —

        Line.2294073839 len=0.001 Switch=Y
        barras=['node_2553646456.1', 'node_2553646457.1']   ambas so com ela

    e 2 elementos NaN em 25.326. Com `perdas_kW` NaN, o `energia` perde os 96
    passos do dia e a subestacao sai da medicao inteira.

    Uma ponta fora da rede continua sendo emitida: ali a chave energiza um
    trecho, e o dado e legitimo. O que nao se sustenta e a chave que nao toca
    a rede em ponta nenhuma.
    """
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON', 'P_N_OPE',
            'COR_NOM', 'TIP_UNID']
    col = bdgd.ler_filtrado('UNSEMT', 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])
    bypass = bypass_de_regulador(bdgd, ctmts, log=log)
    ch = ['! ==========================================================',
          '! CHAVES — geradas de UNSEMT (Line com Switch=Y)',
          '! ==========================================================']
    ct = ['! SwtControl — estado normal de operacao (P_N_OPE)']
    abertas = []
    ilhadas = []
    em_bypass = []
    n_emitidas = 0          # nao contar por len(ch): o arquivo tem avisos
    criadas = set()          # barras que as chaves emitidas trazem
    rede = set(barras) if barras else None
    for i in range(n):
        b1 = no(col['PAC_1'][i])
        b2 = no(col['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        if rede is not None and b1 not in rede and b2 not in rede:
            ilhadas.append(txt(col['COD_ID'][i]))
            continue
        nome = txt(col['COD_ID'][i])
        nd = nos(col['FAS_CON'][i])
        nf = max(1, len([c for c in txt(col['FAS_CON'][i]).upper() if c in 'ABC']))
        # A AMPACIDADE DA CHAVE ESTAVA SENDO JOGADA FORA. `COR_NOM` ja era
        # lido do UNSEMT e o arquivo saia com normamps=9999 — infinito —,
        # entao chave sobrecarregada nunca aparecia em lugar nenhum.
        # Medido: 100% das chaves das sete bases tem codigo valido na TCOR,
        # e Roraima sozinha tem 20.638 chaves de 100 A modeladas como 9999.
        #
        # Isto NAO muda a premissa de ampacidade: ela pula chave
        # (`if not dss.Lines.IsSwitch()`), entao nada e reescrito. O que
        # muda e a sobrecarga passar a ser VISIVEL para quem mede.
        amps = dominios.TCOR.get(txt(col['COR_NOM'][i])) or 9999
        ch.append(f'New Line.{nome} Phases={nf} Bus1={b1}{nd} Bus2={b2}{nd} '
                  f'Switch=Y r1=1e-4 x1=1e-4 r0=1e-4 x0=1e-4 '
                  f'normamps={amps:g}')
        # as barras que a chave cria fazem parte da rede tanto quanto as da
        # SSDMT — e o regulador so se liga por elas (achado 32)
        criadas.add(b1); criadas.add(b2)
        n_emitidas += 1
        estado = 'Open' if txt(col['P_N_OPE'][i]).strip().upper() in ABERTA else 'Closed'
        # BYPASS DE REGULADOR. Ver `bypass_de_regulador`: fechada, esta
        # chave curto-circuita o regulador que esta no mesmo par de PACs.
        # Em campo o bypass fica ABERTO com o regulador em servico.
        if estado == 'Closed' and ((b1, b2) if b1 < b2 else (b2, b1)) in bypass:
            estado = 'Open'
            em_bypass.append(nome)
        ct.append(f'New SwtControl.SW_{nome} SwitchedObj=Line.{nome} SwitchedTerm=1 '
                  f'Lock=No Delay=0 State={estado}')
        if estado == 'Open':
            abertas.append(nome)
    if em_bypass:
        # dito no arquivo, e nao so no log: chave que muda de estado sem
        # deixar rastro e a proxima duvida de quem for auditar o modelo
        ch.append(f'! {len(em_bypass)} chave(s) ABERTA(S) por estarem em paralelo com um '
                  f'regulador: a BDGD as declara fechadas (P_N_OPE=F) sobre o '
                  f'MESMO par de PACs do regulador, o que e o bypass dele. Bypass '
                  f'fechado com regulador em servico e curto no regulador — medido '
                  f'no ESM01 da CPFL: 53,02% de perda com as chaves fechadas, '
                  f'0,75% com elas abertas. Ex.: {", ".join(em_bypass[:3])}')
    if ilhadas:
        # dito no proprio arquivo: chave suprimida em silencio e chave que
        # ninguem sabe que faltou
        ch.insert(3, f'! {len(ilhadas)} chave(s) omitida(s): os dois PACs fora '
                     f'da rede de MT deste alimentador, o que criaria ilha '
                     f'flutuante — ex.: {", ".join(ilhadas[:3])}')
    open(caminho_chaves, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(ch) + '\n')
    open(caminho_controles, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(ct) + '\n')
    return n_emitidas, abertas, ilhadas, criadas
