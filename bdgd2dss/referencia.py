# -*- coding: utf-8 -*-
"""A ancora de FORA da BDGD, para a perda modelada bater contra o mundo.

POR QUE EXISTE. Ate aqui o projeto validava a perda do modelo contra o
`PERD_A4` da CTMT — que sai do MESMO arquivo que o modelo le. Isso e
autoconsistencia, e nao validacao: um conversor que lesse a BDGD errado dos
dois lados passaria. O artigo precisa poder afirmar que o modelo concorda com
a REDE, e nao que concorda com o cadastro.

A REFERENCIA, E DE ONDE ELA SAI
-------------------------------
ANEEL, Superintendencia de Gestao Tarifaria e Regulacao Economica (SGT/STR),
"Perdas de Energia Eletrica na Distribuicao 2025/2024".

    Figura 3, pagina 4 — "As perdas totais sobre a energia injetada
    representam cerca de 14,0% da energia injetada em 2024, sendo
    aproximadamente 7,4% (44,6 TWh) de perdas tecnicas e 6,6% (40,2 TWh) de
    perdas nao tecnicas."

    Figura 6, pagina 5 — "as perdas tecnicas regulatorias sobre a energia
    injetada em 2024 das concessionarias de distribuicao, cuja media foi de
    7,4%."

A safra bate com a das sete bases: BDGD V11, 2024-12-31.

O QUE ESTE MODULO NAO TEM, E POR QUE
------------------------------------
O valor POR DISTRIBUIDORA existe — e a Figura 6 —, mas no PDF ele e imagem, e
transcrever numero de grafico a olho para dentro de um artigo nao e leitura,
e chute. Entao a tabela por distribuidora comeca VAZIA e e carregada de
`dados/perdas_aneel.csv`, que sai do portal:

    https://portalrelatorios.aneel.gov.br/luznatarifa/perdasenergias

Sem esse arquivo, a comparacao roda so contra a media nacional e DIZ que esta
rodando so contra ela. Ver `por_distribuidora`.

O TESTE E DE UM LADO SO, E ISSO E DE PROPOSITO
----------------------------------------------
Os 7,4% cobrem o sistema de distribuicao INTEIRO: alta, media, baixa e os
transformadores. O nosso modelo, com `--bt agregado`, nao tem a rede de BT —
a carga da BT entra agregada no secundario do trafo, e a perda dos ramais
dela nao existe no modelo. Logo o modelo TEM de ficar ABAIXO dos 7,4%.

Ficar acima e impossivel, e por isso vira REPROVACAO. Ficar abaixo e
esperado, e por isso NAO vira aprovacao automatica: para cravar um piso seria
preciso a decomposicao por segmento do Modulo 7, que o relatorio nao publica.
Um teste de um lado so que se sabe de um lado so vale mais que um de dois
lados inventado.

MEDIDO NA V18, perda do modelo em % da energia injetada:

    Roraima       9,83%   REPROVA — acima do sistema inteiro do pais
    CPFL          8,75%   REPROVA
    Enel SP       4,39%
    Enel CE       3,50%
    Cemig-D       2,68%
    Light         1,27%
    Equatorial    0,88%

Roraima e CPFL modelam mais perda em MEDIA tensao do que o Brasil inteiro
perde em toda a distribuicao. Nenhuma leitura da rede explica isso; e defeito.
A CPFL ja tem causa — o achado 48, chave fechada em paralelo com regulador.
"""

# Media nacional, energia injetada, 2024. Ver o cabecalho para a fonte.
ANEEL_2024 = {
    'ano': 2024,
    'total_pct': 14.0,
    'tecnica_pct': 7.4,
    'tecnica_twh': 44.6,
    'nao_tecnica_pct': 6.6,
    'nao_tecnica_twh': 40.2,
    'fonte': ('ANEEL SGT/STR, "Perdas de Energia Eletrica na Distribuicao '
              '2025/2024", Figura 3 (p.4) e Figura 6 (p.5)'),
    'url': 'https://portalrelatorios.aneel.gov.br/luznatarifa/perdasenergias',
}

# Teto do modelo: o sistema de distribuicao inteiro do pais. Nao e um alvo,
# e um impossivel — ver o cabecalho.
TETO = ANEEL_2024['tecnica_pct']


def por_distribuidora(caminho=None):
    """A perda tecnica regulatoria de cada distribuidora, se o CSV existir.

    Formato esperado, com cabecalho: `agente,pct`. `agente` e o codigo da
    distribuidora na BDGD (`BASE.DIST`), que e o unico identificador estavel
    — o nome muda com incorporacao e o carimbo muda a cada safra, como ja
    aprendemos em `regerar_v10._sigla`.

    Devolve `{}` quando o arquivo nao existe: a ausencia e normal e nao e
    erro, mas quem chama tem de DIZER que rodou sem ele.
    """
    import csv
    import os
    if caminho is None:
        caminho = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'dados', 'perdas_aneel.csv')
    if not os.path.exists(caminho):
        return {}
    out = {}
    with open(caminho, encoding='utf-8-sig', newline='') as fh:
        for linha in csv.DictReader(fh):
            ag = (linha.get('agente') or '').strip()
            try:
                v = float((linha.get('pct') or '').replace(',', '.'))
            except ValueError:
                continue
            if ag:
                out[ag] = v
    return out


def comparar(pct_modelo, agente=None, tabela=None, teto=TETO):
    """A perda do modelo contra a referencia de fora.

    `pct_modelo` e a perda modelada em % da energia INJETADA — o
    `pct_modelo` do `concordancia.agregado`, e nao a mediana de razoes.

    `agente` e o codigo da distribuidora; se ele estiver no CSV, a referencia
    passa a ser a dela e nao a media do pais.
    """
    tabela = por_distribuidora() if tabela is None else tabela
    ref = tabela.get(agente) if agente else None
    alvo = ref if ref is not None else teto
    if pct_modelo is None:
        return {'pct_modelo': None, 'referencia_pct': alvo, 'razao': None,
                'reprova': False, 'de_agente': ref is not None,
                'motivo': 'o modelo nao produziu perda agregada'}
    return {
        'pct_modelo': pct_modelo,
        'referencia_pct': alvo,
        'razao': pct_modelo / alvo if alvo else None,
        # Um lado so: acima e impossivel, abaixo e esperado. Ver o cabecalho.
        'reprova': pct_modelo > alvo,
        'de_agente': ref is not None,
        'motivo': ('o modelo perde em MT mais do que o sistema de '
                   'distribuicao inteiro' if pct_modelo > alvo else ''),
        'fonte': ANEEL_2024['fonte'],
    }


def linhas(cmp_):
    """A comparacao em texto, para o rodape de quem chama."""
    if not cmp_ or cmp_.get('pct_modelo') is None:
        return [f'referencia externa: sem perda agregada para comparar '
                f'({(cmp_ or {}).get("motivo", "")})']
    origem = ('a propria distribuidora' if cmp_['de_agente']
              else 'a MEDIA NACIONAL — sem o dado por distribuidora, '
                   'carregue dados/perdas_aneel.csv')
    out = [f'referencia EXTERNA (ANEEL {ANEEL_2024["ano"]}): modelo '
           f'{cmp_["pct_modelo"]:.2f}% contra {cmp_["referencia_pct"]:.1f}% '
           f'de perda tecnica sobre energia injetada — {cmp_["razao"]:.2f}x, '
           f'referencia de {origem}']
    if cmp_['reprova']:
        out.append(f'REPROVA na referencia externa: {cmp_["motivo"]}. O modelo '
                   f'com --bt agregado nao tem a rede de BT, entao ele TEM de '
                   f'ficar abaixo. Acima e defeito, nao e leitura da rede.')
    out.append(f'  fonte: {ANEEL_2024["fonte"]}')
    return out
