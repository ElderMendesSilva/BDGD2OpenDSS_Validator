# -*- coding: utf-8 -*-
"""
SUBSTITUICAO POR AMPACIDADE INSUFICIENTE — achado 34
====================================================

    python ampacidade.py MODELOS_SP_V13
    python ampacidade.py MODELOS_SP_V13 --margem 1.5 --se DALV DANC

Roda DEPOIS do `converter.py`, porque precisa do fluxo resolvido: o criterio
nao e o registro do condutor, e o USO dele. Para cada subestacao, resolve,
mede a corrente de cada trecho, e escreve `_AMPACIDADE.dss` com um `Edit Line`
por trecho cuja corrente excede a ampacidade declarada.

ISTO E MODELAGEM, NAO CONVERSAO. Sem rodar este script o modelo reproduz a
BDGD como ela e — que continua sendo o padrao. A premissa e explicita, o
arquivo gerado e legivel, e apagar o `redirect _AMPACIDADE.dss` do MASTER
desfaz tudo.

Por que existe: em duas das sete bases a BDGD poe fio fino no tronco. Na Enel
SP, 16,1% da quilometragem carrega 73,6% da resistencia ponderada, e o
condutor 593 — 31 A, 8,232 ohm/km — cobre 2.990 km. Medido: trocar o R1 desses
trechos leva a DALV de 11,85% para 3,05% de perda. Nas outras cinco bases o
script nao troca praticamente nada, e e assim que tem de ser.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
# A RAIZ E O PAI, desde a mudanca de 02/09/2026: estes executaveis
# sairam da raiz para `etapas/`, e `AQUI` deixou de ser onde mora o
# pacote `bdgd2dss`.
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import ampacidade, lote, pausa, plataforma, pool                        # noqa: E402
from bdgd2dss import escrita

try:
    import opendssdirect as dss
except Exception as e:                                  # pragma: no cover
    raise SystemExit(f'opendssdirect indisponivel: {e}')


def catalogo_do_modelo():
    """Le o catalogo de condutores do circuito ja compilado.

    Vem do proprio modelo, e nao da SEGCON: o substituto tem de ser um
    condutor que a base declara possuir E que o modelo saiba montar.
    """
    cat = {}
    i = dss.LineCodes.First()
    while i:
        n = dss.LineCodes.Name()
        cat[n.lower()] = {'cnom': dss.LineCodes.NormAmps(),
                          'r1': dss.LineCodes.R1(), 'x1': dss.LineCodes.X1(),
                          'nfases': dss.LineCodes.Phases()}
        i = dss.LineCodes.Next()
    return cat


def trechos_resolvidos():
    """Um dicionario por linha nao-chave, com a corrente do terminal 1."""
    out = []
    i = dss.Lines.First()
    while i:
        nome = dss.Lines.Name()
        if not dss.Lines.IsSwitch():
            dss.Circuit.SetActiveElement('Line.' + nome)
            c = dss.CktElement.CurrentsMagAng()[0::2]
            nf = max(1, dss.Lines.Phases())
            out.append({'linha': nome,
                        'linecode': (dss.Lines.LineCode() or '').lower(),
                        'km': dss.Lines.Length() / 1000.0,
                        'corrente': max(c[:nf]) if c else 0.0})
        i = dss.Lines.Next()
    return out


def uma(pasta, se, margem):
    # PAUSA: sempre antes de comecar, nunca no meio. Assim o que espera
    # segura poucos MB em vez do circuito inteiro.
    pausa.espera()
    d = os.path.join(pasta, se)
    master = os.path.join(d, f'MASTER-{se}.dss')
    if not os.path.exists(master):
        return None
    cwd = os.getcwd()
    os.chdir(d)
    try:
        # IDEMPOTENCIA. O MASTER redireciona `_AMPACIDADE.dss`, entao rodar
        # duas vezes mediria a linha de base JA substituida e a segunda
        # rodada trocaria em cima da primeira. Zera-se antes de medir, e o
        # ponto de partida volta a ser o que a BDGD declara.
        ampacidade.escrever('_AMPACIDADE.dss', [], {
            'margem': margem, 'trechos': 0, 'trocados': 0,
            'km_total': 0.0, 'km_trocado': 0.0, 'pct_km': 0.0})
        dss.Text.Command('Clear')
        dss.Text.Command(f'Redirect MASTER-{se}.dss')
        if not dss.Solution.Converged():
            return {'se': se, 'erro': 'nao convergiu'}
        antes = dss.Circuit.Losses()[0] / 1000.0
        carga = -dss.Circuit.TotalPower()[0]
        subs, resumo = ampacidade.decidir(trechos_resolvidos(),
                                          catalogo_do_modelo(), margem)
        ampacidade.escrever('_AMPACIDADE.dss', subs, resumo)
        # confere no proprio motor: o arquivo vale o que ele faz
        dss.Text.Command('Redirect _AMPACIDADE.dss')
        dss.Text.Command('Solve')
        depois = dss.Circuit.Losses()[0] / 1000.0
        carga2 = -dss.Circuit.TotalPower()[0]
        return {'se': se, 'trocados': resumo['trocados'],
                'trechos': resumo['trechos'],
                'km_trocado': resumo['km_trocado'],
                'pct_km': resumo['pct_km'],
                'sem_candidato': sum(resumo['sem_candidato'].values()),
                'perdas_pct_antes': round(100 * antes / carga, 3) if carga else None,
                'perdas_pct_depois': round(100 * depois / carga2, 3) if carga2 else None,
                'por_condutor': resumo['por_condutor']}
    except Exception as e:
        # UMA SUBESTACAO NAO PODE DERRUBAR A ETAPA. Ver o caso da 1726671 da
        # Cemig-D na V16: um AVISO do OpenDSS levantado como excecao matou o
        # `ligacao` inteiro e o trabalho das outras 412 subestacoes.
        return {'se': se, 'erro': f'{type(e).__name__}: {str(e)[:200]}'}
    finally:
        os.chdir(cwd)


def _painel():
    """Sem argumento, pergunta na janela — o `Validator.py` conta com isso."""
    from bdgd2dss import interativo
    v = interativo.formulario('ampacidade', 'Substituição por ampacidade', [
        {'chave': 'pasta', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': interativo.modelos_recentes(),
         'dica': 'a pasta que contém uma subpasta por subestação'},
        {'chave': 'margem', 'tipo': 'texto', 'rotulo': 'Margem', 'padrao': '1.0',
         'dica': 'quantas vezes a ampacidade a corrente precisa exceder para '
                 'o condutor ser trocado'},
        {'chave': 'jobs', 'tipo': 'inteiro', 'rotulo': 'Subestações em paralelo',
         'padrao': 8,
         'dica': 'medido: o ganho satura perto de 8. Use 1 se for usar o '
                 'computador junto'},
        {'chave': 'se', 'tipo': 'texto', 'rotulo': 'Subestações', 'padrao': '',
         'dica': 'vazio = todas'},
    ], ajuda='PREMISSA DE MODELAGEM: troca a resistência do trecho cuja '
             'corrente calculada excede a ampacidade declarada, pelo condutor '
             'mais fino do catálogo da própria base que a cobre. Escreve em '
             '_AMPACIDADE.dss, que dá para apagar.')
    if not v:
        return False
    sys.argv += [v['pasta'], '--margem', str(v['margem']),
                 '--jobs', str(v['jobs'])]
    if v['se'].strip():
        sys.argv += ['--se'] + v['se'].split()
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('pasta', help='pasta do modelo (MODELOS_*)')
    ap.add_argument('--margem', type=float, default=ampacidade.MARGEM,
                    help='quantas vezes a ampacidade a corrente precisa '
                         f'exceder (padrao {ampacidade.MARGEM:g})')
    ap.add_argument('--jobs', type=int, default=8,
                    help='subestacoes em paralelo (padrao 8); cada uma custa '
                         'um processo com a sua instancia do OpenDSS')
    ap.add_argument('--se', nargs='+', help='apenas estas subestacoes')
    a = ap.parse_args()

    # O CAMINHO RELATIVO E CONTRA A RAIZ DO PROJETO, e nao contra
    # `etapas/`. Depois da mudanca de 02/09/2026 este arquivo mora um
    # nivel abaixo, e `MODELOS_X` passou a ser procurado dentro de
    # `etapas/` — onde nunca vai estar.
    raiz = (a.pasta if os.path.isabs(a.pasta)
            else os.path.join(os.path.dirname(AQUI), a.pasta))
    if not os.path.isdir(raiz):
        raise SystemExit(f'pasta nao encontrada: {raiz}')
    ses = a.se or sorted(x for x in os.listdir(raiz)
                         if os.path.isdir(os.path.join(raiz, x))
                         and not x.startswith('_'))

    print(f'{len(ses)} subestacoes | margem {a.margem:g}x a ampacidade '
          f'declarada\n', flush=True)
    print(f'{"SE":14s} {"trocados":>9s} {"km":>9s} {"%km":>7s} '
          f'{"perdas antes":>13s} {"depois":>9s}', flush=True)
    t0 = time.time()

    def _linha(r):
        if r.get('erro'):
            print(f'{r["se"]:14s} {r["erro"]}', flush=True)
            return
        print(f'{r["se"]:14s} {r["trocados"]:9,d} {r["km_trocado"]:9,.1f} '
              f'{r["pct_km"]:6.1f}% {r["perdas_pct_antes"]:12.2f}% '
              f'{r["perdas_pct_depois"]:8.2f}%', flush=True)

    # EM PARALELO, mesmo padrao do `energia.py`. Cada subestacao tem modelo
    # proprio e nenhum estado compartilhado; o que impedia rodar junto era o
    # `opendssdirect` guardar circuito e solucao em variaveis globais, e em
    # PROCESSOS separados isso deixa de existir. Cada trabalhador faz
    # exatamente o mesmo trabalho que faria em serie.
    #
    # A ORDEM DO JSON NAO PODE DEPENDER DE QUEM TERMINOU PRIMEIRO: ele sai na
    # ordem de `ses`, que e a da execucao serial. Sem isso o arquivo mudaria a
    # cada rodada sem nenhum numero ter mudado.
    por_se = {}

    def grava():
        """Poe no disco o que ja terminou, e devolve na ordem de `ses`.

        Chamada DENTRO do `with` do pool, e nao depois. Sair do `with` e
        `shutdown(wait=True)`, e essa espera nao tem prazo: na V16 o
        `verifica` da Cemig-D terminou as 413 subestacoes e foi morto pelo
        limite de 6h antes de escrever — ver
        `testes/test_grava_antes_de_esperar.py`.
        """
        s = [por_se[s_] for s_ in ses if s_ in por_se]
        with open(os.path.join(raiz, 'ampacidade.json'), 'w',
                  encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
            json.dump({'margem': a.margem, 'subestacoes': s}, fh,
                      indent=1, ensure_ascii=False)
        return s

    if a.jobs > 1 and len(ses) > 1:
        import concurrent.futures as cf
        # `spawn` nos dois sistemas. No Linux o padrao e `fork`, e o
        # filho nasceria com uma COPIA da DLL do OpenDSS ja carregada,
        # com circuito e solucao dentro — o estado compartilhado que os
        # processos separados existem para evitar.
        plataforma.prepara_processos()
        print(f'{a.jobs} subestacoes em paralelo', flush=True)
        with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            fila = lote.maior_primeiro(
                ses, lambda s_: os.path.join(raiz, s_))
            fut = {ex.submit(uma, raiz, s_, a.margem): s_ for s_ in fila}
            for f_ in cf.as_completed(fut):
                r = f_.result()
                if r is not None:
                    por_se[fut[f_]] = r
                    _linha(r)
            grava()
            # A SEGUNDA DEFESA. Gravar antes de sair do `with` salva o
            # RESULTADO; nao salva as horas de fila que vem depois.
            # Sair do `with` e `shutdown(wait=True)`, sem prazo.
            # Ver `bdgd2dss/pool.py` e o caso da Cemig-D na V16.
            pool.encerrar(ex, log=lambda m: print(m, flush=True))
    else:
        for se in ses:
            r = uma(raiz, se, a.margem)
            if r is not None:
                por_se[se] = r
                _linha(r)
    saida = grava()

    ok = [r for r in saida if not r.get('erro')]
    tr = sum(r['trocados'] for r in ok)
    km = sum(r['km_trocado'] for r in ok)
    print(f'\n{"="*70}')
    print(f'{tr:,} trechos trocados, {km:,.0f} km, em {len(ok)} subestacoes '
          f'({time.time()-t0:.0f} s)')
    if ok:
        import statistics as st
        a_ = [r['perdas_pct_antes'] for r in ok if r['perdas_pct_antes']]
        d_ = [r['perdas_pct_depois'] for r in ok if r['perdas_pct_depois']]
        if a_ and d_:
            print(f'perdas medianas: {st.median(a_):.2f}%  ->  '
                  f'{st.median(d_):.2f}%')
    sc = sum(r.get('sem_candidato', 0) for r in ok)
    if sc:
        print(f'{sc:,} trechos excedem a ampacidade e NAO tem candidato no '
              f'catalogo da base — nada foi trocado neles, e isso e alerta '
              f'de dado, nao de modelo')
    print(f'\ndetalhe em {os.path.join(raiz, "ampacidade.json")}')


if __name__ == '__main__':
    main()
