# -*- coding: utf-8 -*-
"""O recorte por subestação parte a rede? Mede na BDGD, sem simular.

    python diagnosticos/recorte.py --bases $BDGD2DSS_BASES \\
        --so LT CEREJ5352 --saida-json medicoes/recorte.json

POR QUE A PERGUNTA. O achado 12 mostrou que a fragmentação é característica POR
DISTRIBUIDORA — 40 de 76 bases com mediana ZERO de ramos isolados por km, e a
Light com 45,8. O conversor é o mesmo para as 97, então o gatilho está no dado
ou na interação dele com uma premissa nossa.

A PREMISSA SUSPEITA é o recorte. O `converter.py` monta um modelo POR
SUBESTAÇÃO e filtra a SSDMT pelos CTMTs daquela SE
(`ler_filtrado('SSDMT', 'CTMT', ctmts, ...)`). Um trecho cujo CTMT pertence a
outra subestação fica de fora — e se ele era o caminho de ligação, o que estava
depois dele vira ramo isolado.

O TESTE, e ele não precisa de OpenDSS: um PAC (ponto de conexão) tocado por
trechos de DUAS subestações diferentes é um ponto de corte. Ali o recorte
separa o que a rede declara junto. Contá-los por base diz se o mecanismo
explica a diferença entre a Light e uma base limpa.

O QUE ESTE NÚMERO NÃO É: prova de defeito. Rede de distribuição tem pontos de
transferência entre subestações por projeto, normalmente com chave aberta. O
que interessa é a MAGNITUDE comparada entre bases — dezenas é operação normal,
dezenas de milhares é outra coisa.
"""
import argparse
import collections
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bdgd2dss import escrita                            # noqa: E402
from bdgd2dss.leitor import BDGD, txt                    # noqa: E402


def cortes_da_base(caminho, por_se=False):
    """Quantos PACs a divisão por subestação separa.

    Devolve o dicionário do resultado. `pacs_multi_se` é a medida principal:
    pontos de conexão tocados por trechos de mais de uma subestação.
    """
    b = BDGD(caminho, verbose=False)

    # CTMT -> SUB, que é o mapa que define o recorte
    c = b.ler('CTMT', ['COD_ID', 'SUB', 'PAC_INI'])
    de_ctmt = {}
    cabeca_de = {}
    for i in range(len(c['COD_ID'])):
        cod = txt(c['COD_ID'][i])
        de_ctmt[cod] = txt(c['SUB'][i])
        # A CABECEIRA DO ALIMENTADOR, que e o que torna a medida robusta.
        # Ver `alcance` mais abaixo e o achado 19.
        cabeca_de[cod] = txt(c['PAC_INI'][i])

    m = b.ler('SSDMT', ['PAC_1', 'PAC_2', 'CTMT'])
    por_pac = collections.defaultdict(set)
    sem_ctmt = 0
    n = len(m['CTMT'])
    for i in range(n):
        se = de_ctmt.get(txt(m['CTMT'][i]))
        if not se:
            sem_ctmt += 1
            continue
        for campo in ('PAC_1', 'PAC_2'):
            p = txt(m[campo][i])
            if p:
                por_pac[p].add(se)

    multi = sum(1 for v in por_pac.values() if len(v) > 1)

    # COMPONENTES CONEXAS DENTRO DE CADA SUBESTACAO. As duas primeiras
    # hipoteses cairam: o recorte por SE nao corta (92 de 97 bases com ZERO
    # PACs multi-SE, e a Light com zero) e trecho orfao tampouco (82 de 97 com
    # zero, e a Light com zero). Sobra a possibilidade de que os PACs
    # simplesmente NAO ENCADEIEM dentro da propria subestacao.
    #
    # Uma SE radial sadia tem UMA componente. Duas ou tres podem ser rede
    # operada em anel aberto. Milhares significam que a BDGD declara pedacos
    # que nao se tocam — e ai o ramo isolado nao e efeito do nosso recorte, e
    # sim do que esta escrito na tabela.
    #
    # Union-find sem recursao: as maiores bases tem milhoes de trechos, e uma
    # busca em profundidade estouraria a pilha.
    pai = {}

    def raiz(x):
        r = x
        while pai[r] != r:
            r = pai[r]
        while pai[x] != r:                     # compressao de caminho
            pai[x], x = r, pai[x]
        return r

    # A REDE NAO E SO A SSDMT, e medir so ela mente. A primeira execucao deu
    # 384 componentes por subestacao na mediana nacional — e a CEREJ5352, que
    # tem ZERO ramos isolados no modelo, apareceu com 42. O modelo emitido pelo
    # `converter` inclui CHAVES (UNSEMT) e REGULADORES (UNREMT), que tambem tem
    # PAC_1/PAC_2 e costuram trechos. Contar sem eles mede uma rede que nunca
    # foi construida.
    def liga(camada, cols=('PAC_1', 'PAC_2', 'CTMT')):
        try:
            return b.ler(camada, list(cols))
        except Exception:                                # noqa: BLE001
            return None

    camadas = [('SSDMT', m)]
    for nome in ('UNSEMT', 'UNREMT', 'UNTRMT'):
        c2 = liga(nome)
        if c2:
            camadas.append((nome, c2))

    comp_por_se = collections.defaultdict(int)
    por_camada = {}
    for nome, col2 in camadas:
        usados = 0
        for i in range(len(col2.get('CTMT', []))):
            se = de_ctmt.get(txt(col2['CTMT'][i]))
            if not se:
                continue
            a, b_ = txt(col2['PAC_1'][i]), txt(col2['PAC_2'][i])
            if not a or not b_ or a == b_:
                continue
            usados += 1
            for p in (a, b_):
                chave = (se, p)
                pai.setdefault(chave, chave)
            ra, rb = raiz((se, a)), raiz((se, b_))
            if ra != rb:
                pai[ra] = rb
        por_camada[nome] = usados
    vistos = collections.defaultdict(set)
    for (se, p) in pai:
        vistos[se].add(raiz((se, p)))
    for se, r in vistos.items():
        comp_por_se[se] = len(r)

    # ------------------------------------------------- ALCANCE POR ALIMENTADOR
    # A MEDIDA QUE NAO DEPENDE DO ROTULO. `componentes por subestacao` mede a
    # rede E o criterio de agrupamento juntos: quando uma base funde 24
    # subestacoes em uma (CELETRO5343, safra 2025), as 24 redes que nunca se
    # tocaram viram 24 componentes da mesma SE e a fragmentacao "salta" de 1
    # para 21 sem que um metro de rede tenha mudado. E o achado 19.
    #
    # O alimentador nao tem esse problema: ele tem UMA cabeceira declarada, o
    # `CTMT.PAC_INI`, e a pergunta "que fracao dos trechos deste alimentador se
    # alcanca a partir dela" independe de como a base agrupa subestacoes.
    #
    # Cada alimentador vira seu proprio grafo, com as mesmas quatro camadas.
    viz = collections.defaultdict(lambda: collections.defaultdict(set))
    tot_ali = collections.Counter()
    for nome, col2 in camadas:
        for i in range(len(col2.get('CTMT', []))):
            ali = txt(col2['CTMT'][i])
            if ali not in de_ctmt:
                continue
            a2, b2 = txt(col2['PAC_1'][i]), txt(col2['PAC_2'][i])
            if not a2 or not b2 or a2 == b2:
                continue
            tot_ali[ali] += 1
            viz[ali][a2].add(b2)
            viz[ali][b2].add(a2)

    alcance = []
    sem_cabeca = 0
    cabeca_fora = 0
    for ali, g in viz.items():
        raizp = cabeca_de.get(ali)
        if not raizp:
            sem_cabeca += 1
            continue
        if raizp not in g:
            # A cabeceira declarada nao aparece entre os PACs do proprio
            # alimentador. Nao e alcance zero por rede partida: e cabeceira que
            # nao existe no dado, e misturar as duas coisas mentiria.
            cabeca_fora += 1
            continue
        # Busca em LARGURA com pilha explicita: recursao estoura em alimentador
        # de dezenas de milhares de PACs.
        visto = {raizp}
        pilha = [raizp]
        while pilha:
            x = pilha.pop()
            for y in g[x]:
                if y not in visto:
                    visto.add(y)
                    pilha.append(y)
        # Trechos alcancados: os que tem AO MENOS UMA ponta no alcance da
        # cabeceira. Contar pelos PACs bastaria para a fracao, mas o trecho e a
        # unidade que o modelo emite.
        alcancados = sum(1 for x in visto for y in g[x] if y in visto) // 2
        alcance.append(100.0 * alcancados / tot_ali[ali] if tot_ali[ali] else 0.0)

    alcance.sort()
    comps = sorted(comp_por_se.values())
    ses_n = len(comps) or 1
    return {
        'trechos_mt': n,
        'trechos_sem_ctmt_conhecido': sem_ctmt,
        'pacs': len(por_pac),
        'pacs_multi_se': multi,
        'pct_pacs_multi_se': round(100.0 * multi / max(1, len(por_pac)), 3),
        'subestacoes_no_ctmt': len(set(de_ctmt.values())),
        'ses_medidas': len(comps),
        'componentes_total': sum(comps),
        'componentes_por_se_mediana': comps[len(comps) // 2] if comps else 0,
        'componentes_por_se_max': max(comps) if comps else 0,
        'ses_com_uma_componente': sum(1 for c in comps if c == 1),
        'pct_ses_fragmentadas': round(
            100.0 * sum(1 for c in comps if c > 1) / ses_n, 1),
        'ligacoes_por_camada': por_camada,
        # A MEDIDA ROBUSTA (achado 19): independe de como a base agrupa SEs.
        'alimentadores_medidos': len(alcance),
        'alimentadores_sem_cabeceira': sem_cabeca,
        'alimentadores_cabeceira_fora_da_rede': cabeca_fora,
        'alcance_mediano_pct': (round(alcance[len(alcance) // 2], 2)
                                if alcance else None),
        'alcance_medio_pct': (round(sum(alcance) / len(alcance), 2)
                              if alcance else None),
        'pct_alimentadores_integros': (
            round(100.0 * sum(1 for x in alcance if x >= 99.0) / len(alcance), 1)
            if alcance else None),
        # A DISTRIBUICAO, e nao so a mediana. A Cemig tem mediana 5 e MAXIMO
        # 1.844: poucas subestacoes catastroficas ao lado de muitas trataveis.
        # Como o `converter` aceita `--se`, a pergunta util nao e "a base
        # aguenta BT completa?" e sim "QUAIS subestacoes aguentam?" — e essa so
        # a lista por SE responde.
        'por_se': (sorted(({'se': k, 'componentes': v}
                           for k, v in comp_por_se.items()),
                          key=lambda x: (x['componentes'], x['se']))
                   if por_se else None),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES', ''))
    ap.add_argument('--so', nargs='*', default=None, help='tags')
    ap.add_argument('--saida-json', default=os.path.join('medicoes',
                                                         'recorte.json'))
    ap.add_argument('--por-se', action='store_true',
                    help='inclui a lista de componentes POR subestacao')
    ap.add_argument('--elegiveis', type=int, default=None, metavar='N',
                    help='imprime as SEs com ate N componentes, prontas para '
                         'colar em `converter.py --se`')
    ap.add_argument('--elegiveis-dir', default=None, metavar='DIR',
                    help='alem de imprimir, grava DIR/<base>.txt com um nome '
                         'por linha — o formato que `SES_ARQUIVO` espera')
    a = ap.parse_args(argv)

    import regerar_v10 as rg
    so = set(a.so) if a.so else None
    bases = [(t, c) for t, c, _ in rg.descobrir(a.bases) if not so or t in so]
    if not bases:
        print('nenhuma .gdb encontrada', file=sys.stderr)
        return 1

    saida, erros = [], 0
    print('%-20s %10s %12s %10s %10s' %
          ('base', 'trechos', 'PACs multi-SE', 'comp/SE', 'SEs frag%'))
    for tag, cam in bases:
        try:
            d = cortes_da_base(cam, por_se=(a.por_se or a.elegiveis))
        except Exception as e:                          # noqa: BLE001
            print('%-20s ERRO: %s' % (tag, str(e)[:70]), flush=True)
            erros += 1
            continue
        d['base'] = tag
        saida.append(d)
        print('%-20s %10s %12s %10s %9.1f%%'
              % (tag, f"{d['trechos_mt']:,}", f"{d['pacs_multi_se']:,}",
                 f"{d['componentes_por_se_mediana']:,}",
                 d['pct_ses_fragmentadas']), flush=True)

    # O CRITERIO DE ENTRADA DO ACHADO 16, em forma de comando. Sem isto o
    # usuario tem de abrir o JSON e filtrar a mao, e a barreira faz com que a
    # BT completa continue sendo tentada na base inteira — que e o que nao
    # funciona.
    if a.elegiveis:
        print()
        for d in saida:
            ok = [x['se'] for x in (d.get('por_se') or [])
                  if x['componentes'] <= a.elegiveis]
            print('# %s: %d de %d subestacoes com ate %d componentes'
                  % (d['base'], len(ok), d['ses_medidas'], a.elegiveis))
            if ok:
                print('--se ' + ' '.join(ok))
            # UM NOME POR LINHA, porque a lista da Enel SP tem 150 nomes e nao
            # cabe no `-v` do qsub. O job le o arquivo; ninguem cola 150 nomes
            # a mao sem errar um.
            if a.elegiveis_dir and ok:
                os.makedirs(a.elegiveis_dir, exist_ok=True)
                alvo = os.path.join(a.elegiveis_dir, d['base'] + '.txt')
                with open(alvo, 'w', encoding='utf-8',
                          newline=escrita.FIM_DE_LINHA) as fh:
                    fh.write('\n'.join(ok) + '\n')
                print('# -> %s' % alvo)

    os.makedirs(os.path.dirname(a.saida_json) or '.', exist_ok=True)
    with open(a.saida_json, 'w', encoding='utf-8',
              newline=escrita.FIM_DE_LINHA) as fh:
        json.dump({'bases': saida}, fh, ensure_ascii=False, indent=1)
    print('\n%d bases medidas, %d com erro  ->  %s'
          % (len(saida), erros, a.saida_json))
    # Medir nada nao e medir — ver `diagnosticos/ferro.py`, mesmo defeito.
    if not saida:
        print('nenhuma base medida: veja os erros acima', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
