# -*- coding: utf-8 -*-
"""Preenche `medicoes/tamanho_bases.json` com o tamanho de cada `.gdb`.

Roda DENTRO de um job do PBS — ver `cluster/medir_bases.pbs` e a regra de
28/08/2026 em `bdgd2dss/tamanhos.py`. Fora de um job ele para, porque medir no
no de acesso e exatamente o que a regra proibe.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import regerar_v10 as r                                # noqa: E402
from bdgd2dss import tamanhos as tm                     # noqa: E402


def main():
    bases = r.BASES
    if not bases:
        print('nenhuma .gdb encontrada em BDGD2DSS_BASES', file=sys.stderr)
        return 1
    try:
        tam, novas = tm.tamanhos([c for _, c, _ in bases])
    except tm.PrecisaDeNo as e:
        print('ERRO: %s' % e, file=sys.stderr)
        return 1
    print('bases pedidas : %d' % len(bases))
    print('medidas agora : %d' % novas)
    print('total no cache: %d' % len(tm.carregar()))
    print('cache         : %s' % tm.CACHE)
    for tag, cam, _ in sorted(bases, key=lambda b: -tam.get(b[1], 0))[:5]:
        print('   %-22s %6.1f GB' % (tag, tam[cam]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
