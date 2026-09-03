# -*- coding: utf-8 -*-
"""As subestações em que o MODELO falha de verdade — não compila, não converge,
ou tem `NaN`.

Depois do achado 25, `MODELO_QUEBRADO` deixou de ser uma gaveta de 1.250 e
passou a ser o que o nome diz: **41 subestações da safra 2025, 1,0% do país**.
Número finito, e cada uma provavelmente vira um achado.

O que este script faz é o que a contagem não faz — **agrupa por MENSAGEM**. Um
erro do OpenDSS que aparece em quinze subestações é um defeito só, e nem
sempre a distribuidora é a pista: o mesmo `Illegal character` pode vir de um
campo de texto que quinze bases preenchem do mesmo jeito.

Roda LOCALMENTE sobre os `validacao.json` — ver `v26_x_v27.py` para o comando
que os traz do cluster.

    python analise/falhas_de_modelo.py [sufixo]        (padrão: V27)
"""
import collections
import glob
import io
import json
import os
import re
import sys


def motivo(r):
    """O motivo real, na ordem de precedência do `diagnostico.py`."""
    if not r.get('compila'):
        return 'nao compila'
    if not r.get('converge'):
        return 'nao converge'
    if r.get('nos_nan'):
        return 'nos com NaN'
    return None


def assinatura(texto):
    """A mensagem sem os identificadores, para agrupar erros iguais.

    Sem isto cada erro é único: o OpenDSS carrega o nome do elemento na
    mensagem, então quinze ocorrências do MESMO defeito viram quinze linhas
    diferentes e a repetição — que é a informação — some.
    """
    t = str(texto or '').strip()
    t = re.sub(r'\b\d[\d.,]*\b', '#', t)              # números
    t = re.sub(r'\b[0-9a-f]{8,}\b', '#', t, flags=re.I)   # hashes e códigos
    t = re.sub(r'\s+', ' ', t)
    return t[:160]


def main(sufixo='V27'):
    arquivos = sorted(glob.glob('MODELOS_*_%s/validacao.json' % sufixo))
    if not arquivos:
        print('nenhum MODELOS_*_%s/validacao.json aqui' % sufixo)
        return 2

    casos = []
    total = 0
    for f in arquivos:
        base = os.path.basename(os.path.dirname(f)).replace('MODELOS_', '')
        base = base.rsplit('_' + sufixo, 1)[0]
        try:
            dados = json.load(io.open(f, encoding='utf-8'))
        except Exception:                                    # noqa: BLE001
            continue
        for r in dados:
            total += 1
            m = motivo(r)
            if m:
                casos.append((m, base, r))

    print('subestacoes: %s   falha de MODELO: %d (%.2f%%)'
          % (f'{total:,}', len(casos), 100.0 * len(casos) / total))
    if not casos:
        return 0

    for m in ('nao compila', 'nao converge', 'nos com NaN'):
        deste = [(b, r) for mm, b, r in casos if mm == m]
        if not deste:
            continue
        print()
        print('=' * 74)
        print(' %s — %d subestacoes' % (m.upper(), len(deste)))
        print('=' * 74)

        # AGRUPADO POR MENSAGEM: e a repeticao que diz se ha um defeito ou
        # quinze.
        grupos = collections.defaultdict(list)
        for b, r in deste:
            msg = r.get('erro') or r.get('causa_detalhe') or ''
            grupos[assinatura(msg)].append((b, r))
        for chave, itens in sorted(grupos.items(), key=lambda x: -len(x[1])):
            bases = collections.Counter(b for b, _r in itens)
            print()
            print('  [%d ocorrencia(s)]  %s'
                  % (len(itens), chave or '(sem mensagem registrada)'))
            print('   bases: %s' % ', '.join('%s x%d' % (b, n) if n > 1 else b
                                             for b, n in bases.most_common()))
            for b, r in itens[:4]:
                print('     %-22s %-14s  barras=%-7s linhas=%-7s cargas=%-7s '
                      'iter=%s'
                      % (b, str(r.get('modelo'))[:14],
                         r.get('n_barras'), r.get('n_linhas'),
                         r.get('n_cargas'), r.get('iteracoes')))
                msg = (r.get('erro') or r.get('causa_detalhe') or '').strip()
                if msg:
                    print('       > %s' % msg[:150])
            if len(itens) > 4:
                print('     ... e mais %d' % (len(itens) - 4))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'V27'))
