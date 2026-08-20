# -*- coding: utf-8 -*-
"""Quanto da carga o modelo energiza — em kW, e nao so em contagem.

POR QUE EXISTE. A ferramenta vinha reportando "carga energizada" contando
cargas, o que trata uma padaria e uma fabrica como um. Medido nas 119
subestacoes da Equatorial PA da V16, sobre exatamente o mesmo modelo:

    por contagem   81,1%   (316.054 de 389.688 cargas)
    em kW          66,5%   (754 de 1.134 MW)

A carga que fica no escuro nao tem o tamanho da media: ela e 1,77x maior.
Reportar so a contagem exagera a cobertura, e exagera MAIS justamente na base
pior. As duas medidas ficam, e a de kW e a que vale no artigo; a discordancia
entre elas e resultado, e nao ruido.

CUIDADO COM O QUE ESTE NUMERO NAO E. Aqui se mede kW ATRAS DE BARRA VIVA, pelo
mesmo criterio do `ligacao` (`V < 1 volt` na carga). Nao e a mesma coisa que
carga ENTREGUE: carga em barra viva mas com tensao baixa entrega menos que o
nominal e ainda assim conta como energizada. Pela medida de entrega — energia
injetada menos perdas, sobre o nominal — a mesma EQPA da 61,6%. As duas sao
legitimas e nao se somam nem se substituem; confundi-las ja produziu uma razao
errada num relatorio.

E AMOSTRA NAO SERVE. Em quatro subestacoes escolhidas por terem muita carga
morta, a medida de kW da 64,2% contra 55,1% da contagem — a ordem INVERTE em
relacao a base inteira. O numero que vale e o da base.

Uma funcao so, usada pelo `ligacao.py` e pelo `regerar_v10.py`, para que o
numero do rodape e o numero do resumo nao possam divergir.
"""


def energizada(ses):
    """Agrega os registros por subestacao do `ligacao.json`.

    `ses` sao os registros SEM erro — subestacao que falhou nao tem carga
    medida, e conta-la como energizada ou como morta mentiria nas duas
    direcoes.

    Devolve um dicionario com as duas medidas, e `None` no lugar da que nao
    puder ser calculada. Base antiga, gerada antes de `kW_nominal` existir,
    devolve `kW_pct=None` em vez de zero: nao medir nao e medir zero.
    """
    n = sum(x.get('cargas', 0) for x in ses)
    d = sum(x.get('mortas_depois', 0) for x in ses)
    kwt = sum(x.get('kW_nominal', 0.0) for x in ses)
    kwm = sum(x.get('kW_morto', 0.0) for x in ses)
    return {
        'cargas': n,
        'mortas': d,
        'cont_pct': round(100.0 * (n - d) / n, 1) if n else None,
        'MW_nominal': round(kwt / 1000.0, 1) if kwt > 0 else None,
        'MW_morto': round(kwm / 1000.0, 1) if kwt > 0 else None,
        'kW_pct': round(100.0 * (kwt - kwm) / kwt, 1) if kwt > 0 else None,
    }


def linha(c):
    """Uma linha de rodape com as duas medidas, ou '' se nao houver o que dizer."""
    if c.get('kW_pct') is None and c.get('cont_pct') is None:
        return ''
    if c.get('kW_pct') is None:
        return (f'carga energizada: {c["cont_pct"]:.1f}% em contagem '
                f'({c["cargas"] - c["mortas"]:,} de {c["cargas"]:,}) — '
                f'sem kW nesta base, gerada antes da medida existir')
    return (f'carga energizada: {c["kW_pct"]:.1f}% em kW '
            f'({c["MW_nominal"] - c["MW_morto"]:,.0f} de '
            f'{c["MW_nominal"]:,.0f} MW)  |  {c["cont_pct"]:.1f}% em contagem '
            f'({c["cargas"] - c["mortas"]:,} de {c["cargas"]:,})')
