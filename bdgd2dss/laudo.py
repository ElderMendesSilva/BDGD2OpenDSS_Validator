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


# ===========================================================================
#  UMA ANALISE POR FIGURA
# ===========================================================================
#
# O PDF nao empilha as figuras no fim com um texto generico antes. Cada figura
# vem com o paragrafo que a LE — o que ela mostra, o que naquele desenho e
# normal, e o que naquele desenho e sintoma.
#
# A diferenca importa: "47% das barras fora da faixa" e um numero; "o perfil
# desce continuamente da fonte ate a ponta, sem degrau, o que e queda ohmica e
# nao ilhamento" e uma leitura. A segunda e o que alguem precisa para decidir o
# que fazer.

def _n(x, casas=2):
    try:
        return ('%%.%df' % casas) % float(x)
    except (TypeError, ValueError):
        return '—'


def analise_da_figura(chave, v, e, g, extra=None):
    """O parágrafo que acompanha UMA figura. Vazio quando não há o que dizer."""
    extra = extra or {}
    vmin, vmed = v.get('V_MT_min'), v.get('V_MT_mediana')
    fora = extra.get('pct_fora_faixa')
    sob = extra.get('pct_sobrecarga')
    rev = extra.get('passos_reversos')
    pp = e.get('perdas_pct')

    if chave == 'perfil':
        if vmed is None:
            return ''
        t = ('Cada ponto é uma barra de média tensão: a distância elétrica até '
             'a fonte no eixo horizontal, a tensão em pu no vertical. A faixa '
             'verde é o limite adequado do PRODIST (%.2f a %.2f pu).'
             % V_ADEQUADA)
        if vmin is not None and (vmed - vmin) > 0.15:
            t += (' A nuvem desce de %s a %s pu, o que é **queda ao longo do '
                  'tronco**: quanto mais longe da fonte, menor a tensão. Um '
                  'degrau vertical seria regulador ou transformador; um '
                  'patamar horizontal seria rede sem corrente.'
                  % (_n(vmed, 3), _n(vmin, 3)))
        else:
            t += (' A nuvem é compacta: a tensão varia pouco com a distância, '
                  'o que indica rede curta ou bem regulada.')
        return t

    if chave == 'tensao':
        if fora is None:
            return ('Distribuição da tensão nas barras de média tensão, com as '
                    'linhas tracejadas nos limites do PRODIST.')
        t = ('Distribuição da tensão nas barras de média tensão. **%.1f%% '
             'estão fora da faixa adequada.**' % fora)
        if fora > 20:
            t += (' Com mais de um quinto da rede fora do limite, o problema '
                  'não é local: ou o tronco é longo demais para o condutor, ou '
                  'falta regulação, ou há laço de regulador drenando corrente '
                  '(achado 22).')
        elif fora > 0:
            t += (' A fração é pequena e costuma se concentrar nas pontas de '
                  'alimentador — o perfil de tensão mostra se é isso.')
        return t

    if chave == 'mapa':
        t = ('A rede desenhada nas coordenadas da BDGD, com a cor indicando a '
             'tensão de cada barra: verde dentro da faixa, âmbar abaixo de '
             '0,95 pu, vermelho fora do limite.')
        if fora is not None and fora > 20:
            t += (' As manchas vermelhas mostram ONDE a tensão cai — nas '
                  'pontas, é comprimento; em bloco, é um trecho específico.')
        t += (' Coordenada trocada e alimentador que atravessa a concessão '
              'aparecem aqui num segundo, e em nenhuma tabela.')
        return t

    if chave == 'dia':
        if pp is None:
            return ''
        return ('As 24 h em passos de 15 min. A linha escura é a potência que '
                'entra pela subestação, a verde é a geração distribuída e a '
                'vermelha são as perdas. É a única figura que mostra a rede em '
                'OPERAÇÃO, e não num instante — e é o modo `daily` do OpenDSS '
                'que a torna possível.')

    if chave == 'perdas_dia':
        if pp is None:
            return ''
        return ('A perda em percentual, hora a hora. Ela **não é constante**: '
                'cresce com o carregamento, porque perda ôhmica vai com o '
                'quadrado da corrente. O valor único do resumo (%s%%) é a '
                'integral do dia, e ler o pico como se fosse a média '
                'superestima a perda.' % _n(pp))

    if chave == 'gd_fluxo':
        if not (e.get('kWh_gd') or 0):
            return ''
        t = 'A carga total contra a geração distribuída, ao longo do dia.'
        if rev:
            t += (' A faixa vermelha marca os **%d passos (%.1f h) de FLUXO '
                  'REVERSO**, quando a injeção local supera o consumo e o '
                  'alimentador exporta para a subestação. É ali que aparecem '
                  'sobretensão e atuação indevida de regulador — e nada disso '
                  'é visível num estudo de ponta.' % (rev, rev * 0.25))
        else:
            t += (' Não há fluxo reverso: a geração fica sempre abaixo do '
                  'consumo local, então a rede nunca exporta.')
        return t

    if chave == 'gd_cobre':
        if not (e.get('kWh_gd') or 0):
            return ''
        return ('Que fração da carga a geração cobre, passo a passo. A linha '
                'pontilhada marca o **pico de carga**, e o número ali é o que '
                'decide se a GD alivia a rede ou apenas desloca energia: '
                'geração solar tem pico ao meio-dia e a carga tem pico à '
                'noite, e a não-coincidência é a regra.')

    if chave == 'liquido':
        return ('O que a subestação vê: carga menos geração. O **mínimo** '
                'importa tanto quanto o máximo — é quando a rede está mais '
                'descarregada e a tensão mais alta, a condição crítica de '
                'sobretensão por geração distribuída. Valor negativo significa '
                'que a rede exporta naquele instante.')

    if chave == 'condutor':
        if sob is None:
            return ''
        t = ('Corrente sobre a ampacidade declarada, trecho a trecho. A linha '
             'vermelha é 100%: à direita dela o condutor conduz mais do que a '
             'placa dele permite.')
        if sob > SOBRECARGA_PREOCUPA:
            t += (' Com **%.1f%% dos trechos acima do limite**, a leitura mais '
                  'provável não é rede sobrecarregada: é o par (resistência, '
                  'ampacidade) do cadastro não descrevendo o cabo que está no '
                  'poste.' % sob)
        elif sob > 0:
            t += (' %.1f%% dos trechos passam do limite, o que em rede real '
                  'aparece em ponta de alimentador no horário de pico.' % sob)
        else:
            t += ' Nenhum trecho ultrapassa a própria ampacidade.'
        return t

    if chave == 'composicao':
        pt = v.get('perdas_trafos_pct')
        if pt is None:
            return ''
        t = ('Onde a perda acontece. **%.0f%% está nos transformadores** e o '
             'resto nas linhas.' % pt)
        if pt > 60:
            t += (' Com a maior parte no ferro, a perda desta subestação '
                  'depende pouco da carga: existe 24 h por dia. Isso muda a '
                  'comparação com a perda declarada pela distribuidora, que '
                  'costuma reportar só a parcela dependente de carga.')
        return t

    return ''


def analise_da_concessao(chave, ag):
    """O parágrafo que acompanha cada figura da concessão."""
    n = ag.get('ses') or 0
    ok = ag.get('ok') or 0
    med = ag.get('perda_mediana')

    if chave == 'veredictos':
        p = _pct(ok, n) or 0
        t = ('Quantas subestações passam nos critérios de aceite: **%d de %d '
             '(%.1f%%)**. Passar significa compilar nos dois motores do '
             'OpenDSS, convergir, não ter barra com potência indefinida e '
             'manter a tensão mediana da média tensão dentro do plausível.'
             % (ok, n, p))
        if p < 100:
            t += (' As barras vermelhas são os motivos de reprovação. A altura '
                  'delas diz se o problema está espalhado pela concessão ou '
                  'concentrado em poucas subestações — e, na prática, costuma '
                  'ser concentrado.')
        return t

    if chave == 'perdas_hist':
        t = ('Como a perda técnica se distribui entre as subestações. Cada '
             'barra conta quantas subestações caem naquela faixa de perda.')
        if med is not None:
            t += (' A mediana da concessão é **%.2f%%**. A linha tracejada '
                  'marca 10%%: o que está à direita dela não se explica por '
                  'uma rede de média tensão, e merece diagnóstico individual.'
                  % med)
        return t

    if chave == 'perdas_rank':
        return ('As subestações de maior perda, em vermelho as que passam de '
                '10%. Esta figura existe porque o valor agregado esconde quem '
                'domina: é comum um punhado de subestações responder pela '
                'maior parte da perda de toda a concessão, e trabalhar sobre a '
                'média seria tratar o sintoma errado.')

    if chave == 'dia':
        return ('A curva de carga somada de todas as subestações, em passos de '
                '15 minutos. É o perfil da concessão inteira ao longo do dia — '
                'aproximadamente o que a soma dos medidores de fronteira da '
                'distribuidora deveria registrar.')

    if chave == 'gd_fluxo':
        return ('Carga e geração distribuída somadas. No nível da concessão o '
                'fluxo reverso é raro mesmo quando existe em alimentadores '
                'individuais, porque a soma dilui o efeito: um alimentador '
                'exportando some dentro de dezenas que importam. Por isso esta '
                'figura **não substitui** a análise por subestação.')

    if chave == 'gd_cobre':
        return ('Que fração do consumo da concessão a geração distribuída '
                'cobre ao longo do dia. A linha pontilhada marca o pico de '
                'carga, e a distância entre ele e o pico de geração é o que '
                'decide se a GD alivia a rede ou apenas desloca energia no '
                'tempo.')

    if chave == 'tensao_hist':
        return ('A tensão **mínima** de cada subestação. A linha tracejada é o '
                'limite inferior do PRODIST (0,93 pu): cada barra à esquerda '
                'dela é uma subestação com pelo menos um ponto fora da faixa '
                'adequada. Uma subestação pode aparecer aqui e ainda assim '
                'estar sadia — o mínimo é uma ponta, não a rede toda.')

    if chave == 'km_rank':
        return ('As maiores redes da concessão, em quilômetros de média '
                'tensão. Serve de denominador para as outras figuras: perda '
                'alta numa rede de 2.000 km significa uma coisa, e a mesma '
                'perda numa de 50 km significa outra bem diferente.')

    if chave == 'perda_km':
        return ('Perda contra tamanho, uma subestação por ponto. Se a perda '
                'fosse explicada pelo comprimento da rede, os pontos subiriam '
                'em diagonal. **Dispersão sem tendência significa que o que '
                'domina é outra coisa** — condutor incoerente, carregamento, '
                'ou defeito de modelagem.')

    if chave == 'composicao':
        lin = ag.get('perdas_linhas_kW') or 0
        tra = ag.get('perdas_trafos_kW') or 0
        pt = _pct(tra, lin + tra)
        if pt is None:
            return ''
        return ('A perda da concessão inteira, separada entre linhas e '
                'transformadores: **%.0f%% está nos transformadores** e %.0f%% '
                'nas linhas. A parcela dos transformadores é perda a vazio — '
                'existe 24 horas por dia, com ou sem carga, e depende do '
                'número de transformadores e não de quilômetros. É justamente '
                'essa parcela que a perda declarada pela distribuidora costuma '
                'não contemplar, e é aí que mora o achado 13 deste projeto.'
                % (pt, 100 - pt))

    if chave == 'resumo':
        return ('Os números da concessão em uma tabela, para consulta rápida '
                'sem precisar voltar às figuras.')

    if chave == 'energia':
        return ('A energia do dia somada, e uma nota sobre por que a série de '
                '96 passos importa: é ela que permite o modo diário do '
                'OpenDSS, e é o modo diário que torna a geração distribuída '
                'analisável.')

    return ''
