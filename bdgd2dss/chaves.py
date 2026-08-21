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


def gerar(bdgd, ctmts, caminho_chaves, caminho_controles, barras=None):
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
    ch = ['! ==========================================================',
          '! CHAVES — geradas de UNSEMT (Line com Switch=Y)',
          '! ==========================================================']
    ct = ['! SwtControl — estado normal de operacao (P_N_OPE)']
    abertas = []
    ilhadas = []
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
        estado = 'Open' if txt(col['P_N_OPE'][i]).strip().upper() in ABERTA else 'Closed'
        ct.append(f'New SwtControl.SW_{nome} SwitchedObj=Line.{nome} SwitchedTerm=1 '
                  f'Lock=No Delay=0 State={estado}')
        if estado == 'Open':
            abertas.append(nome)
    if ilhadas:
        # dito no proprio arquivo: chave suprimida em silencio e chave que
        # ninguem sabe que faltou
        ch.insert(3, f'! {len(ilhadas)} chave(s) omitida(s): os dois PACs fora '
                     f'da rede de MT deste alimentador, o que criaria ilha '
                     f'flutuante — ex.: {", ".join(ilhadas[:3])}')
    open(caminho_chaves, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(ch) + '\n')
    open(caminho_controles, 'w', encoding='utf-8', newline=escrita.FIM_DE_LINHA).write('\n'.join(ct) + '\n')
    return len(ch) - 3 - bool(ilhadas), abertas, ilhadas, criadas
