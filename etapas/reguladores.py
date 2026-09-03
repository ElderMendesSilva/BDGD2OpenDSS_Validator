# -*- coding: utf-8 -*-
"""
ORIENTACAO DOS REGULADORES DE TENSAO — achado 30
================================================

    python reguladores.py MODELOS_CMIG_V30
    python reguladores.py MODELOS_CMIG_V30 --se 1726536 --jobs 1

Roda DEPOIS do `converter.py` e ANTES do `ampacidade.py`, porque o criterio e
eletrico e porque a ordem importa: corrigir a orientacao muda a tensao em cerca
de 0,09 pu, e a tensao muda a corrente que o `ampacidade` mede.

O QUE ELE FAZ. Resolve o modelo, mede a direcao do fluxo em cada regulador e
escreve `_REGULADORES.dss` com um `RegControl.X.winding=N` para os que estao
com o controle no lado da FONTE. O arquivo e legivel, conta quantos foram, e
apagar o `redirect _REGULADORES.dss` do MASTER devolve o modelo ao que a BDGD
declara.

POR QUE NAO DA PARA DECIDIR NA CONVERSAO. A BDGD nao declara qual PAC do
UNREMT e o lado da fonte, e a resposta depende da topologia resolvida — a
mesma razao pela qual o `ligacao.py` tambem roda depois. Ver
`bdgd2dss/orientacao.py` para o criterio e para as duas medicoes erradas que
precederam a certa.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import orientacao, pausa, plataforma            # noqa: E402
from bdgd2dss import escrita                                     # noqa: E402

try:
    import opendssdirect as dss
except Exception as e:                                 # pragma: no cover
    raise SystemExit(f'opendssdirect indisponivel: {e}')


def quais():
    """Nome, enrolamento controlado e transformador de cada RegControl.

    SO A IDENTIFICACAO, e nao a medida. O iterador do OpenDSS **pula elemento
    desabilitado**, e o passo desabilita os controles antes de medir o fluxo —
    juntar as duas coisas na mesma funcao devolvia lista VAZIA e a etapa
    reportava zero regulador numa subestacao com seis.
    """
    saida = []
    i = dss.RegControls.First()
    while i:
        saida.append({'nome': dss.RegControls.Name(),
                      'winding': dss.RegControls.Winding(),
                      'transformador': dss.RegControls.Transformer()})
        i = dss.RegControls.Next()
    return saida


def fluxos(regs):
    """Preenche `p_terminais` lendo os TRANSFORMADORES, que seguem ativos.

    A potencia vem por condutor e intercalada com o reativo; somar o ativo de
    cada terminal e o que da a direcao. Pegar so a primeira fase erraria em
    regulador trifasico desequilibrado.
    """
    for r in regs:
        dss.Circuit.SetActiveElement('Transformer.' + r['transformador'])
        p = dss.CktElement.Powers() or []
        n = dss.CktElement.NumConductors() or 1
        term = []
        for t in range(2):
            a, b = 2 * n * t, 2 * n * (t + 1)
            term.append(sum(p[a:b:2]) if len(p) >= b else 0.0)
        r['p_terminais'] = term
    return regs


def uma(pasta, se):
    pausa.espera()
    d = os.path.join(pasta, se)
    master = os.path.join(d, f'MASTER-{se}.dss')
    if not os.path.exists(master):
        return None
    cwd = os.getcwd()
    os.chdir(d)
    try:
        # IDEMPOTENCIA, e aqui ela e mais delicada que no `ampacidade`: o
        # MASTER redireciona este arquivo, e medir com a correcao anterior
        # aplicada mediria o fluxo de um circuito JA corrigido. Zera-se antes.
        orientacao.escrever('_REGULADORES.dss', [], 0, ())
        dss.Text.Command('Clear')
        dss.Text.Command(f'Redirect MASTER-{se}.dss')
        if not dss.Solution.Converged():
            return {'se': se, 'erro': 'nao convergiu'}

        # O TAPE VOLTA AO NEUTRO ANTES DE MEDIR. O `Solve` embutido no MASTER
        # ja correu o tape ao limite, e o tape mexe na tensao dos dois lados —
        # medir sobre ele foi o primeiro erro desta investigacao. A DIRECAO do
        # fluxo nao muda com o tape, mas zerar torna a medida legivel e
        # protege contra o caso em que o tape saturado inverte o sinal.
        regs = quais()
        for r in regs:
            dss.Text.Command('Transformer.%s.wdg=2' % r['transformador'])
            dss.Text.Command('Transformer.%s.tap=1.0' % r['transformador'])
            dss.Text.Command('RegControl.%s.enabled=no' % r['nome'])
        if regs:
            dss.Text.Command('Solve')
            fluxos(regs)

        corr, sem = orientacao.corrigir(regs)
        orientacao.escrever('_REGULADORES.dss', corr, len(regs), sem)

        # CONFERE NO PROPRIO MOTOR: o arquivo vale o que ele faz. Recompila do
        # zero, porque acima os controles ficaram desabilitados.
        dss.Text.Command('Clear')
        dss.Text.Command(f'Redirect MASTER-{se}.dss')
        v = sorted(x for x in dss.Circuit.AllBusMagPu() if x > 1e-6)
        sat = 0
        i = dss.RegControls.First()
        while i:
            dss.Transformers.Name(dss.RegControls.Transformer())
            if dss.Transformers.Tap() >= dss.Transformers.MaxTap() - 1e-6:
                sat += 1
            i = dss.RegControls.Next()
        return {'se': se, 'reguladores': len(regs), 'corrigidos': len(corr),
                'sem_fluxo': len(sem), 'saturados_depois': sat,
                'V_mediana_depois': round(v[len(v) // 2], 4) if v else None,
                'convergiu': bool(dss.Solution.Converged())}
    except Exception as e:
        # UMA SUBESTACAO NAO PODE DERRUBAR A ETAPA — a licao da 1726671.
        return {'se': se, 'erro': f'{type(e).__name__}: {str(e)[:200]}'}
    finally:
        os.chdir(cwd)


def _painel():
    """Sem argumento, pergunta na janela — o `Validator.py` conta com isso."""
    if not plataforma.tem_janela():
        return False
    from bdgd2dss import interativo
    v = interativo.pedir('Orientacao dos reguladores', [
        {'chave': 'pasta', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
         'padrao': ''},
        {'chave': 'jobs', 'tipo': 'inteiro',
         'rotulo': 'Subestacoes em paralelo', 'padrao': 8}])
    if not v:
        return False
    sys.argv += [v['pasta'], '--jobs', str(v['jobs'])]
    return True


def main():
    if len(sys.argv) == 1 and not _painel():
        return

    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('pasta', help='pasta do modelo (MODELOS_*)')
    ap.add_argument('--jobs', type=int, default=8,
                    help='subestacoes em paralelo (padrao 8)')
    ap.add_argument('--se', nargs='+', help='apenas estas subestacoes')
    a = ap.parse_args()

    # O CAMINHO RELATIVO E CONTRA A RAIZ DO PROJETO, e nao contra `etapas/` —
    # a licao da mudanca de 02/09/2026, que quebrou duas etapas assim.
    raiz = (a.pasta if os.path.isabs(a.pasta)
            else os.path.join(os.path.dirname(AQUI), a.pasta))
    if not os.path.isdir(raiz):
        raise SystemExit(f'pasta nao encontrada: {raiz}')
    ses = a.se or sorted(x for x in os.listdir(raiz)
                         if os.path.isdir(os.path.join(raiz, x))
                         and not x.startswith('_'))

    print('ORIENTACAO DOS REGULADORES — achado 30')
    print(f'{len(ses)} subestacoes | o criterio e a direcao do fluxo\n',
          flush=True)
    print(f'{"SE":14s} {"regs":>6s} {"corrig":>7s} {"sem flx":>8s} '
          f'{"satur":>6s} {"V med":>8s}', flush=True)
    t0 = time.time()
    por_se = {}

    def _linha(r):
        if r.get('erro'):
            print(f'{r["se"]:14s} {r["erro"]}', flush=True)
            return
        print(f'{r["se"]:14s} {r.get("reguladores",0):6d} '
              f'{r.get("corrigidos",0):7d} {r.get("sem_fluxo",0):8d} '
              f'{r.get("saturados_depois",0):6d} '
              f'{(r.get("V_mediana_depois") or 0):8.4f}', flush=True)

    def grava():
        """No disco o que ja terminou, na ordem de `ses`.

        DENTRO do `with` do pool: sair dele e `shutdown(wait=True)`, e essa
        espera nao tem prazo — ver `test_grava_antes_de_esperar.py`.
        """
        s_ = [por_se[k] for k in ses if k in por_se]
        n = sum(x.get('corrigidos') or 0 for x in s_)
        tot = sum(x.get('reguladores') or 0 for x in s_)
        sem = sum(x.get('sem_fluxo') or 0 for x in s_)
        with open(os.path.join(raiz, 'reguladores.json'), 'w',
                  encoding='utf-8', newline=escrita.FIM_DE_LINHA) as fh:
            json.dump({'corrigidos': n, 'reguladores': tot,
                       'sem_fluxo': sem, 'subestacoes': s_}, fh,
                      indent=1, ensure_ascii=False)
        return s_

    if a.jobs > 1 and len(ses) > 1:
        import concurrent.futures as cf
        import multiprocessing as mp
        ctx = mp.get_context('spawn')
        with cf.ProcessPoolExecutor(max_workers=a.jobs,
                                    mp_context=ctx) as ex:
            fut = {ex.submit(uma, raiz, s_): s_ for s_ in ses}
            for f in cf.as_completed(fut):
                r = f.result()
                if r:
                    por_se[r['se']] = r
                    _linha(r)
            saida = grava()
    else:
        for s_ in ses:
            r = uma(raiz, s_)
            if r:
                por_se[r['se']] = r
                _linha(r)
        saida = grava()

    n = sum(r.get('corrigidos') or 0 for r in saida)
    tot = sum(r.get('reguladores') or 0 for r in saida)
    sem = sum(r.get('sem_fluxo') or 0 for r in saida)
    afetadas = sum(1 for r in saida if (r.get('corrigidos') or 0))
    print(f'\n{n:,} de {tot:,} reguladores corrigidos em {afetadas} '
          f'subestacoes ({sem:,} sem fluxo, {time.time()-t0:.0f} s)')
    print('detalhe em %s' % os.path.join(raiz, 'reguladores.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
