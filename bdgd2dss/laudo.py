# -*- coding: utf-8 -*-
"""O texto do relatório, escrito a partir dos números.

POR QUE REGRAS E NÃO UM MODELO DE LINGUAGEM. Um LLM escreveria um texto mais
solto, e traria três coisas que este projeto não pode aceitar: o mesmo modelo
gera texto diferente a cada execução, o que quebra a comparação entre rodadas;
depende de rede e de chave de API, o que trava o cluster; e não tem rastro de
procedência — hoje cada número carrega o commit e a versão do motor que o
produziu, e um parágrafo gerado por LLM não carrega nada.

Aqui o critério está no código, visível e discutível. Quando alguém discordar
de "perda alta", a linha que define o corte está a um `grep` de distância — e
mudar o corte muda todos os relatórios de uma vez, de forma consistente.

O QUE ESTE MÓDULO NÃO FAZ: não decide se a rede real é boa. Ele julga o
MODELO contra faixas de referência, e diz de onde vem cada faixa. Rede que
parece ruim aqui pode ser cadastro incompleto — é a tese central do projeto, e
o texto tem de dizer isso em vez de escondê-lo.
"""

# --------------------------------------------------------------- referências
#
# Toda faixa aqui tem origem declarada. Número solto em código é a forma mais
# fácil de um critério virar folclore.

# PRODIST módulo 8: faixa adequada de tensão em regime permanente.
V_ADEQUADA = (0.93, 1.05)

# Perda técnica de MT. A âncora nacional da ANEEL é 7,4% de perda técnica
# TOTAL, e o modelo agregado não contém a rede secundária — então a parcela
# que ele vê fica abaixo disso. Acima de 10% num modelo de MT é sinal de
# problema, e não de rede ruim: quase sempre condutor incoerente, rede longa
# demais ou laço de regulador (achado 22).
PERDA_ALTA = 10.0
PERDA_TIPICA = (2.0, 8.0)

# Carga sem tensão. Uma ou outra é ponta de rede mal cadastrada; acima de 1%
# do total é rede que não fecha.
MORTAS_PREOCUPA = 1.0

# Trecho conduzindo acima da própria ampacidade declarada. O `ampacidade.py`
# corrige os casos claros; o que sobra é incoerência de cadastro (achado 34).
SOBRECARGA_PREOCUPA = 5.0


def _pct(parte, todo):
    return (100.0 * parte / todo) if todo else None


def _frase(condicao, sim, nao=None):
    return sim if condicao else (nao or '')


def laudo_da_subestacao(v, e, g, extra=None):
    """Uma lista de (título, parágrafo) sobre uma subestação.

    `v` vem do `validacao.json`, `e` do `energia_dia.json`, `g` do
    `resumo_geral.json`. `extra` traz o que só o modelo aberto sabe —
    carregamento dos condutores e tensões — e pode faltar.
    """
    extra = extra or {}
    secoes = []
    ver = str(v.get('veredicto') or '').split('[')[0]

    # ---------------------------------------------------------- o veredicto
    if ver == 'OK':
        cabeca = ('O modelo desta subestação **passa** nos critérios de '
                  'aceite: compila nos dois motores, o fluxo converge, não há '
                  'barra com potência indefinida e a tensão mediana da média '
                  'tensão está na faixa esperada.')
    elif ver in ('NAO_COMPILA', 'NAO_CONVERGE', 'POTENCIA_NAN'):
        cabeca = ('O modelo **não fecha** (%s). Os números abaixo, quando '
                  'existem, vêm de uma solução que o próprio OpenDSS não '
                  'considera válida e não devem ser usados.' % ver)
    elif ver == 'TENSAO_IMPLAUSIVEL':
        cabeca = ('O modelo resolve, mas a tensão da média tensão fica muito '
                  'abaixo do plausível. Isso não costuma ser rede ruim: as '
                  'causas conhecidas são condutor com resistência incoerente, '
                  'tronco longo sem regulador, e regulador emitido em paralelo '
                  'com o trecho (achado 22).')
    else:
        cabeca = 'Veredicto não reconhecido (%s).' % (ver or '—')
    secoes.append(('Situação geral', cabeca))

    # ------------------------------------------------------- conectividade
    mortas = v.get('cargas_sem_tensao') or 0
    total = v.get('n_cargas') or 0
    p = _pct(mortas, total)
    if not total:
        txt = 'A contagem de cargas não está disponível neste modelo.'
    elif mortas == 0:
        txt = ('**Todas as %s cargas recebem tensão.** Não há trecho ilhado '
               'com consumidor pendurado.' % f'{total:,}'.replace(',', '.'))
    elif p is not None and p < MORTAS_PREOCUPA:
        txt = ('%d de %s cargas ficam sem tensão (%.2f%%). É pouco, e o padrão '
               'nesses casos é ponta de rede mal cadastrada — um ramal cujo '
               'trecho de ligação não foi declarado.'
               % (mortas, f'{total:,}'.replace(',', '.'), p))
    else:
        txt = ('**%d de %s cargas ficam sem tensão (%.1f%%).** Acima de 1%% a '
               'explicação deixa de ser ponta solta: há parte da rede que não '
               'chega à fonte, e a perda e a energia desta subestação estão '
               'medidas sobre uma rede menor do que a declarada.'
               % (mortas, f'{total:,}'.replace(',', '.'), p))
    sem_v = v.get('ramos_sem_tensao')
    nl = v.get('n_linhas') or 0
    if sem_v is not None and nl:
        pl = _pct(sem_v, nl)
        txt += (' Em trechos, %s de %s estão sem tensão (%.2f%%).'
                % (f'{sem_v:,}'.replace(',', '.'),
                   f'{nl:,}'.replace(',', '.'), pl))
    secoes.append(('Conectividade: o que não recebe tensão', txt))

    # --------------------------------------------------------------- tensão
    vmin, vmed = v.get('V_MT_min'), v.get('V_MT_mediana')
    fora = extra.get('pct_fora_faixa')
    if vmed is None:
        txt = 'Não há medida de tensão de média tensão neste modelo.'
    else:
        txt = ('A tensão mediana das barras de média tensão é **%.3f pu** e a '
               'mínima é %.3f pu.' % (vmed, vmin if vmin is not None else 0))
        if vmed < V_ADEQUADA[0]:
            txt += (' A mediana está **abaixo da faixa adequada** do PRODIST '
                    '(%.2f a %.2f pu), o que significa que mais da metade da '
                    'rede opera fora do limite regulatório — não é um ponto '
                    'ruim no fim de um ramal, é a rede inteira.'
                    % V_ADEQUADA)
        elif vmin is not None and vmin < V_ADEQUADA[0]:
            txt += (' A mediana está na faixa adequada, e o mínimo abaixo dela '
                    'aponta para pontas de rede específicas — o perfil de '
                    'tensão mostra onde.')
        else:
            txt += ' Toda a média tensão fica dentro da faixa adequada.'
        if fora is not None:
            txt += (' No total, %.1f%% das barras estão fora da faixa.' % fora)
    secoes.append(('Perfil de tensão', txt))

    # --------------------------------------------------------------- perdas
    pp = e.get('perdas_pct')
    if pp is None:
        txt = 'A energia do dia não foi medida nesta subestação.'
    else:
        if pp > PERDA_ALTA:
            juizo = ('**acima do que uma rede de média tensão explica**. '
                     'Perda desta ordem num modelo sem rede secundária é '
                     'sintoma, não característica: as causas medidas neste '
                     'projeto são condutor com resistência incoerente com a '
                     'ampacidade, tronco muito longo, e regulador em paralelo '
                     'com o trecho')
        elif pp < PERDA_TIPICA[0]:
            juizo = ('**abaixo do típico**, o que costuma indicar rede '
                     'faltando — trechos que a BDGD não declarou, deixando as '
                     'cargas eletricamente perto da fonte')
        else:
            juizo = 'dentro da faixa típica de uma rede de média tensão'
        txt = ('A perda técnica integrada nas 24 h é de **%.2f%%** da energia '
               'injetada, %s.' % (pp, juizo))
    pt = v.get('perdas_trafos_pct')
    if pt is not None:
        txt += (' Dessa perda, **%.0f%% está nos transformadores** e o resto '
                'nas linhas. A parcela dos transformadores é perda a vazio: '
                'existe 24 h por dia e não depende de carga.' % pt)
    secoes.append(('Perdas', txt))

    # ---------------------------------------------------------- carregamento
    sob = extra.get('pct_sobrecarga')
    if sob is None:
        txt = ('O carregamento dos condutores exige abrir o modelo e não foi '
               'medido neste relatório.')
    elif sob == 0:
        txt = 'Nenhum trecho conduz acima da ampacidade declarada.'
    elif sob < SOBRECARGA_PREOCUPA:
        txt = ('%.1f%% dos trechos conduzem acima da ampacidade declarada. '
               'Em rede real isso aparece em ponta de alimentador no horário '
               'de pico.' % sob)
    else:
        txt = ('**%.1f%% dos trechos conduzem acima da própria ampacidade.** '
               'Acima de 5%% a leitura mais provável não é rede sobrecarregada, '
               'e sim incoerência entre o condutor declarado e o uso — o par '
               '(resistência, ampacidade) do cadastro não descreve o cabo que '
               'está no poste.' % sob)
    secoes.append(('Carregamento dos condutores', txt))

    # ------------------------------------------------------ geração distribuída
    gd = e.get('kWh_gd') or 0
    inj = e.get('kWh_injetado') or 0
    if not gd:
        txt = 'Não há geração distribuída declarada nesta subestação.'
    else:
        cob = _pct(gd, inj + gd)
        txt = ('A geração distribuída injeta **%s kWh no dia**, cobrindo %.1f%% '
               'da energia consumida.'
               % (f'{gd:,.0f}'.replace(',', '.'), cob or 0))
        rev = extra.get('passos_reversos')
        if rev:
            txt += (' Em **%d passos de 15 min (%.1f h)** a injeção supera o '
                    'consumo e o fluxo se inverte — é quando aparecem '
                    'sobretensão e atuação indevida de regulador, e é a '
                    'condição que um estudo de ponta nunca vê.'
                    % (rev, rev * 0.25))
        else:
            txt += (' Não há inversão de fluxo: a geração nunca supera o '
                    'consumo local.')
    secoes.append(('Geração distribuída', txt))

    # ------------------------------------------------------------- anomalias
    # SINGULAR E PLURAL, porque "5 regulador" num relatorio institucional
    # denuncia texto gerado sem cuidado e derruba a confianca no resto.
    itens = []
    for chave, um, varios in (
            ('reguladores_pendurados',
             'regulador com um PAC que não existe na rede — compila e não '
             'regula nada',
             'reguladores com um PAC que não existe na rede — compilam e não '
             'regulam nada'),
            ('chaves_ilhadas',
             'chave que não toca a rede em ponta nenhuma',
             'chaves que não tocam a rede em ponta nenhuma'),
            ('trafos_pac_invertido',
             'transformador com primário e secundário trocados no cadastro',
             'transformadores com primário e secundário trocados no cadastro')):
        n = g.get(chave) or 0
        if n:
            itens.append('**%d %s**' % (n, um if n == 1 else varios))
    txt = ('; '.join(itens) + '.') if itens else \
        'Nenhuma anomalia de cadastro registrada nesta subestação.'
    secoes.append(('Anomalias de cadastro', txt))

    return secoes


def laudo_da_concessao(resumo):
    """O texto da concessão, a partir do agregado já calculado."""
    secoes = []
    n = resumo.get('ses') or 0
    ok = resumo.get('ok') or 0
    p = _pct(ok, n)
    if not n:
        return [('Sem dados', 'Nenhuma subestação medida nesta pasta.')]

    txt = ('A concessão tem **%d subestações modeladas**, das quais **%d '
           'passam** nos critérios de aceite (%.1f%%).' % (n, ok, p or 0))
    if p is not None and p >= 95:
        txt += (' A conversão cobre a concessão de forma consistente; o que '
                'falha está concentrado e classificado.')
    elif p is not None and p >= 80:
        txt += (' A maior parte converte, e o que falha merece diagnóstico por '
                'causa — costuma se concentrar em poucas subestações.')
    else:
        txt += (' A taxa de aprovação é baixa o bastante para que o problema '
                'seja sistemático, e não caso a caso.')
    secoes.append(('Cobertura da conversão', txt))

    mort = resumo.get('cargas_sem_tensao') or 0
    if mort:
        secoes.append((
            'Cargas sem tensão',
            'Somadas todas as subestações, **%s cargas não recebem tensão**. '
            'Elas não entram na energia nem na perda, então os dois números '
            'falam de uma rede menor do que a declarada.'
            % f'{mort:,}'.replace(',', '.')))

    med = resumo.get('perda_mediana')
    if med is not None:
        txt = ('A perda mediana entre subestações é de **%.2f%%**.' % med)
        if med > PERDA_ALTA:
            txt += (' Acima de %g%% a mediana indica problema sistemático, e '
                    'não subestações ruins isoladas.' % PERDA_ALTA)
        secoes.append(('Perdas na concessão', txt))

    lin = resumo.get('perdas_linhas_kW') or 0
    tra = resumo.get('perdas_trafos_kW') or 0
    if lin or tra:
        pt = _pct(tra, lin + tra)
        secoes.append((
            'Onde a perda acontece',
            'Na soma da concessão, **%.0f%% da perda está nos '
            'transformadores** e %.0f%% nas linhas. A parcela dos '
            'transformadores é perda a vazio — independe de carga, e é o que '
            'a comparação com a perda declarada pela distribuidora costuma '
            'não contemplar.' % (pt or 0, 100 - (pt or 0))))

    secoes.append((
        'O que este relatório não afirma',
        'Os números acima descrevem o MODELO, e o modelo reproduz o que a '
        'BDGD declara. Rede que aparece ruim aqui pode ser cadastro '
        'incompleto: trecho não declarado, condutor com parâmetro incoerente '
        'ou perda publicada que não fecha com o próprio parque de '
        'transformadores. Separar as duas coisas exige referência externa à '
        'BDGD, que este relatório não tem.'))
    return secoes
