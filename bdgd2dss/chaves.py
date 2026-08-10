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

# valores de P_N_OPE que significam chave aberta
ABERTA = {'A', 'ABERTA', 'ABERTO', '0', 'N'}


def gerar(bdgd, ctmts, caminho_chaves, caminho_controles):
    cols = ['COD_ID', 'PAC_1', 'PAC_2', 'CTMT', 'FAS_CON', 'P_N_OPE',
            'COR_NOM', 'TIP_UNID']
    col = bdgd.ler_filtrado('UNSEMT', 'CTMT', ctmts, cols)
    n = len(col['COD_ID'])
    ch = ['! ==========================================================',
          '! CHAVES — geradas de UNSEMT (Line com Switch=Y)',
          '! ==========================================================']
    ct = ['! SwtControl — estado normal de operacao (P_N_OPE)']
    abertas = []
    for i in range(n):
        b1 = no(col['PAC_1'][i])
        b2 = no(col['PAC_2'][i])
        if not b1 or not b2 or b1 == b2:
            continue
        nome = txt(col['COD_ID'][i])
        nd = nos(col['FAS_CON'][i])
        nf = max(1, len([c for c in txt(col['FAS_CON'][i]).upper() if c in 'ABC']))
        ch.append(f'New Line.{nome} Phases={nf} Bus1={b1}{nd} Bus2={b2}{nd} '
                  f'Switch=Y r1=1e-4 x1=1e-4 r0=1e-4 x0=1e-4 normamps=9999')
        estado = 'Open' if txt(col['P_N_OPE'][i]).strip().upper() in ABERTA else 'Closed'
        ct.append(f'New SwtControl.SW_{nome} SwitchedObj=Line.{nome} SwitchedTerm=1 '
                  f'Lock=No Delay=0 State={estado}')
        if estado == 'Open':
            abertas.append(nome)
    open(caminho_chaves, 'w', encoding='utf-8').write('\n'.join(ch) + '\n')
    open(caminho_controles, 'w', encoding='utf-8').write('\n'.join(ct) + '\n')
    return len(ch) - 3, abertas
