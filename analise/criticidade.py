# -*- coding: utf-8 -*-
"""
ESTUDO DE CRITICIDADE — todos os alimentadores da Enel SP (BDGD 2024-12-31 V11)
==============================================================================

    python analise/criticidade.py                    abre o painel e pergunta
    python analise/criticidade.py --dados dados\\extraido_bdgd --saida dados\\resultados

Metodo analitico, sem OpenDSS: a demanda de ponta de cada alimentador e obtida
da energia mensal das unidades consumidoras (UCBT_tab + UCMT_tab) aplicada ao
fator de ponta da curva de carga correspondente (CRVCRG), e comparada com a
ampacidade do tronco trifasico de saida (SSDMT x SEGCON).

Indice de estabilidade combina quatro dimensoes:
  carregamento, margem de reserva, crescimento anual e qualidade (DIC e GD).

Entra o que os extratores deixaram na pasta de dados; sai o
`criticidade_geral.json` e o `ranking_alimentadores.csv` na pasta de resultados.
"""
import argparse
import csv
import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                 # a raiz do projeto, onde esta o interativo.py
sys.path.insert(0, RAIZ)

# Tudo relativo a este arquivo, e nao ao diretorio de onde se chamou: o script
# roda igual sendo chamado da raiz ou de dentro da propria pasta analise.
ENTRADA = os.path.join(RAIZ, 'dados', 'extraido_bdgd')
RESULTADOS = os.path.join(RAIZ, 'dados', 'resultados')

# quem gera cada entrada, para o erro dizer o que fazer em vez de so reclamar
DE_ONDE = {
    'bt_todos.json': 'python analise/extrai_bt.py',
    'mt_todos.json': 'python analise/extrai_mt.py',
    'gd_todos.json': 'python analise/extrai_mt.py',
    'amp_todos.json': 'python analise/extrai_ampacidade.py',
    'crvcrg.json': 'vem com a extracao da BDGD (CRVCRG)',
    'ctmt_info.json': 'vem com a extracao da BDGD (CTMT)',
}

FP = 0.92          # fator de potencia adotado
HORAS = 730.0      # horas no mes


def carrega(pasta, nome):
    p = os.path.join(pasta, nome)
    if not os.path.exists(p):
        raise SystemExit(f'falta {p}\n  gere com: {DE_ONDE.get(nome, "?")}')
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def norm(x, lo, hi):
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _painel():
    from bdgd2dss import interativo
    v = interativo.formulario('criticidade', 'Estudo de criticidade dos alimentadores', [
        {'chave': 'dados', 'tipo': 'pasta', 'rotulo': 'Dados extraídos da BDGD',
         'padrao': ENTRADA,
         'dica': 'a pasta com bt_todos.json, mt_todos.json, gd_todos.json, '
                 'amp_todos.json, crvcrg.json e ctmt_info.json'},
        {'chave': 'saida', 'tipo': 'pasta', 'rotulo': 'Pasta de saída',
         'padrao': RESULTADOS,
         'dica': 'recebe o criticidade_geral.json e o ranking_alimentadores.csv'},
    ], ajuda='Calcula a demanda de ponta de cada alimentador a partir da '
             'energia das unidades consumidoras e compara com a capacidade do '
             'tronco de saída. É analítico: roda em segundos, sem OpenDSS.')
    if not v:
        return False
    sys.argv += ['--dados', v['dados'], '--saida', v['saida']]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--dados', default=ENTRADA,
                    help='pasta com os JSON extraidos da BDGD')
    ap.add_argument('--saida', default=RESULTADOS,
                    help='pasta que recebe o JSON e o CSV do estudo')
    a = ap.parse_args()

    bt = carrega(a.dados, 'bt_todos.json')
    mt = carrega(a.dados, 'mt_todos.json')
    gd = carrega(a.dados, 'gd_todos.json')
    amp = carrega(a.dados, 'amp_todos.json')
    crv = carrega(a.dados, 'crvcrg.json')
    ctmt = carrega(a.dados, 'ctmt_info.json')
    os.makedirs(a.saida, exist_ok=True)

    def fator_ponta(cod, td='DU'):
        """Razao entre o pico e a media da curva de carga."""
        v = crv.get(f'{cod}|{td}')
        if not v:
            return 1.72                      # mediana das curvas DU
        m = sum(v) / len(v)
        return max(v) / m if m > 0 else 1.72

    res = []
    for cod, info in ctmt.items():
        a_ = amp.get(cod)
        if not a_ or a_['cnom'] <= 0:
            continue
        b = bt.get(cod, {})
        m = mt.get(cod, {})
        g = gd.get(cod, {})
        ene_bt = b.get('ene', [0] * 12)
        ene_mt = m.get('ene', [0] * 12)
        ene = [ene_bt[i] + ene_mt[i] for i in range(12)]
        if sum(ene) <= 0:
            continue
        # demanda media e de ponta no mes mais carregado
        imes = max(range(12), key=lambda i: ene[i])
        dm_bt = ene_bt[imes] / HORAS
        dm_mt = ene_mt[imes] / HORAS
        fp_bt = fator_ponta(b.get('curva') or 'RES-Tipo02')
        fp_mt = fator_ponta('MT-Tipo02')
        ponta = dm_bt * fp_bt + dm_mt * fp_mt
        ten = float(info.get('ten_ope') or 0) * 13.8 if info.get('ten_ope') else 13.8
        kv = 13.8
        corr = ponta / (math.sqrt(3) * kv * FP) if ponta > 0 else 0.0
        carreg = 100 * corr / a_['cnom']
        reserva = a_['cnom'] * math.sqrt(3) * kv * FP - ponta     # kW disponiveis
        # crescimento: regressao simples sobre os 12 meses
        y = ene
        n = len(y); sx = sum(range(n)); sy = sum(y)
        sxy = sum(i * y[i] for i in range(n)); sxx = sum(i * i for i in range(n))
        den = n * sxx - sx * sx
        incl = (n * sxy - sx * sy) / den if den else 0
        media = sy / n
        cresc = 100 * incl * 12 / media if media > 0 else 0      # % ao ano
        nuc = b.get('n_uc', 0) + m.get('n_uc', 0)
        dic = (b.get('dic_total', 0) + m.get('dic_total', 0)) / nuc if nuc else 0
        gd_kw = g.get('kW', 0)
        gd_pct = 100 * gd_kw / ponta if ponta > 0 else 0

        # --- indice de estabilidade (0 = mais estavel, 100 = menos estavel)
        i_car = norm(carreg, 20, 120) * 45        # carregamento: peso 45
        i_res = (1 - norm(reserva, 0, 8000)) * 20  # reserva: peso 20
        i_cre = norm(cresc, 0, 15) * 20            # crescimento: peso 20
        i_qua = (norm(dic, 2, 25) * 0.6 + norm(gd_pct, 0, 60) * 0.4) * 15   # qualidade: peso 15
        indice = i_car + i_res + i_cre + i_qua

        res.append({
            'ctmt': cod, 'sub': info.get('sub'), 'nome': info.get('nome'),
            'mes_ponta': imes + 1, 'n_uc': nuc, 'n_uc_mt': m.get('n_uc', 0),
            'kW_medio': round(dm_bt + dm_mt, 1), 'kW_ponta': round(ponta, 1),
            'I_ponta_A': round(corr, 1), 'Inom_A': a_['cnom'], 'Imax_A': a_['cmax'],
            'carreg_pct': round(carreg, 1),
            'reserva_kW': round(reserva, 1),
            'cresc_pct_ano': round(cresc, 1),
            'dic_medio_h': round(dic, 2), 'gd_kW': round(gd_kw, 1), 'gd_pct': round(gd_pct, 1),
            'km_rede': a_['km'], 'trechos': a_['trechos'],
            'indice': round(indice, 1),
            'i_carreg': round(i_car, 1), 'i_reserva': round(i_res, 1),
            'i_cresc': round(i_cre, 1), 'i_qualidade': round(i_qua, 1)})

    # --- controle de qualidade do dado
    for r in res:
        flags = []
        if r['I_ponta_A'] > 3*r['Imax_A']: flags.append('demanda implausivel')
        if abs(r['cresc_pct_ano'])>60: flags.append('serie mensal erratica')
        if r['n_uc']<10 and r['kW_ponta']>5000: flags.append('poucas UCs, alta energia')
        r['alerta']='; '.join(flags)
        r['confiavel']= not flags
    res.sort(key=lambda r: -r['carreg_pct'])
    p_json = os.path.join(a.saida, 'criticidade_geral.json')
    # utf-8 explicito: sem isso o Windows grava em cp1252 e o acento de um
    # nome de subestacao derruba a escrita inteira
    json.dump(res, open(p_json, 'w', encoding='utf-8'), ensure_ascii=False)
    p_csv = os.path.join(a.saida, 'ranking_alimentadores.csv')
    with open(p_csv,'w',newline='',encoding='utf-8-sig') as fh:
        w=csv.writer(fh, delimiter=';')
        w.writerow(['Posicao','CTMT','Subestacao','Nome','Carregamento_%','kW_ponta','I_ponta_A','Inom_A',
                    'Reserva_kW','Crescimento_%ano','UCs','UCs_MT','DIC_medio_h','GD_kW','GD_%',
                    'km_rede','Indice_instabilidade','Mes_ponta','Alerta_dado'])
        for i,r in enumerate(sorted(res,key=lambda x:-x['carreg_pct']),1):
            w.writerow([i,r['ctmt'],r['sub'],r['nome'],f"{r['carreg_pct']:.1f}".replace('.',','),
                        f"{r['kW_ponta']:.0f}",f"{r['I_ponta_A']:.1f}".replace('.',','),f"{r['Inom_A']:.0f}",
                        f"{r['reserva_kW']:.0f}",f"{r['cresc_pct_ano']:.1f}".replace('.',','),
                        r['n_uc'],r['n_uc_mt'],f"{r['dic_medio_h']:.2f}".replace('.',','),
                        f"{r['gd_kW']:.0f}",f"{r['gd_pct']:.1f}".replace('.',','),
                        f"{r['km_rede']:.1f}".replace('.',','),f"{r['indice']:.1f}".replace('.',','),
                        r['mes_ponta'],r['alerta']])

    ok=[r for r in res if r['confiavel']]
    sus=[r for r in res if not r['confiavel']]
    print(f'alimentadores avaliados: {len(res):,} | consistentes: {len(ok):,} | com alerta de dado: {len(sus):,}')
    faixas = [('>=131%', lambda c: c >= 131), ('121-130%', lambda c: 121 <= c < 131),
              ('111-120%', lambda c: 111 <= c < 121), ('101-110%', lambda c: 101 <= c < 111),
              ('81-100%', lambda c: 81 <= c < 101), ('51-80%', lambda c: 51 <= c < 81),
              ('<=50%', lambda c: c < 51)]
    print()
    print('DISTRIBUICAO POR FAIXA DE CARREGAMENTO')
    for nome, f in faixas:
        q = [r for r in ok if f(r['carreg_pct'])]
        print(f'  {nome:9s} {len(q):5d} alimentadores ({100*len(q)/len(ok):5.1f}%)')
    print()
    print('TOP 15 MAIS CARREGADOS')
    print(f"  {'CTMT':10s} {'SUB':7s} {'carreg':>8s} {'kW ponta':>10s} {'I(A)':>8s} {'Inom':>7s} {'cresc%a':>8s} {'indice':>7s}")
    for r in ok[:15]:
        print(f"  {r['ctmt']:10s} {str(r['sub'])[:6]:7s} {r['carreg_pct']:7.1f}% {r['kW_ponta']:10,.0f} "
              f"{r['I_ponta_A']:8.1f} {r['Inom_A']:7.0f} {r['cresc_pct_ano']:8.1f} {r['indice']:7.1f}")
    print()
    print('saida:', p_json)
    print('       ', p_csv)


if __name__ == '__main__':
    main()
