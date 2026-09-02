# -*- coding: utf-8 -*-
"""O veredicto final: este modelo serve para quê?

O `validador.py` já dá um veredicto, e ele responde uma pergunta estreita —
**o modelo fecha eletricamente?** Compila nos dois motores, converge, não tem
`NaN`. É uma pergunta de máquina, e um `OK` dela não diz se alguém pode usar o
resultado para decidir alguma coisa.

Este módulo responde a pergunta que a pessoa realmente tem: **posso confiar
nos números deste modelo, e para quê?** Ele julga o modelo contra sete
critérios, cada um com o valor medido e o limite ao lado, e termina dizendo em
que estudo aquele modelo pode entrar e em que estudo não pode.

TRÊS REGRAS QUE ESTE MÓDULO NÃO QUEBRA:

1. **Nenhum critério tem limite escondido.** Cada um carrega o número e de
   onde ele veio. Quando alguém discordar de "perda alta", a linha está a um
   `grep` daqui, e mudá-la muda todos os relatórios de uma vez.

2. **O veredicto julga o MODELO, não a rede.** Uma rede reprovada aqui quase
   sempre é cadastro incompleto, e o texto tem de dizer isso em vez de deixar
   quem lê concluir que a distribuidora opera uma rede ruim. É a tese central
   do projeto.

3. **Reprovar num critério não invalida os outros.** Um modelo com 30% das
   barras sem tensão continua servindo para inspecionar conectividade — ele só
   não serve para medir perda. Dizer "não utilizável" quando o certo é "não
   utilizável PARA ISTO" joga fora trabalho bom.
"""

APROVADO = 'ADEQUADO'
RESSALVAS = 'ADEQUADO COM RESSALVAS'
RESTRITO = 'USO RESTRITO'
REPROVADO = 'NÃO UTILIZÁVEL'
# Faltar medida NAO e passar. A primeira versao deste modulo dava
# «Fecha eletricamente: sim» para uma base em que a etapa de validacao nem
# tinha rodado — o campo vinha vazio, e vazio nao estava na lista de falhas.
# Um relatorio que carimba ADEQUADO por ausencia de dado e pior do que nenhum
# relatorio, porque parece conferido.
INCONCLUSIVO = 'INCONCLUSIVO'

# a cor de cada um, para o relatório
COR = {APROVADO: '#2e7d32', RESSALVAS: '#f9a825',
       RESTRITO: '#ef6c00', REPROVADO: '#c62828',
       INCONCLUSIVO: '#546e7a'}

PASSA, ATENCAO, FALHA, SEM_DADO = 'passa', 'atencao', 'falha', 'sem dado'


# ---------------------------------------------------------------- os limites
#
# Cada um com a origem. Numero solto em codigo vira folclore em duas semanas.

# PRODIST modulo 8. Ate 3% das barras fora da faixa e ponta de alimentador;
# acima de 15% e a rede inteira, e nao a ponta.
FORA_FAIXA = (3.0, 15.0)

# Carga sem tensao. Uma ou outra e ramal mal cadastrado; acima de 5% a perda e
# a energia estao medidas sobre uma rede menor do que a declarada.
SEM_TENSAO = (1.0, 5.0)

# Perda tecnica de MT. A ancora nacional da ANEEL e 7,4% de perda TOTAL, e o
# modelo agregado nao contem a rede secundaria — a parcela que ele ve fica
# abaixo disso. Acima de 10% e sinal de problema de modelagem, nao de rede.
PERDA = (8.0, 15.0)

# Trecho acima da propria ampacidade declarada.
SOBRECARGA = (2.0, 10.0)

# Fator de carga tipico de distribuicao. Acima de 0,85 a curva foi achatada
# por tipologia unica, e a perda de pico sai subestimada.
FATOR_CARGA = (0.80, 0.90)

# Passos do dia que precisam fechar para a energia do dia valer.
PASSOS_MINIMOS = 90


def _classe(valor, limites, invertido=False):
    """PASSA / ATENCAO / FALHA contra um par de limites."""
    if valor is None:
        return SEM_DADO
    baixo, alto = limites
    if invertido:
        if valor >= baixo:
            return PASSA
        return ATENCAO if valor >= alto else FALHA
    if valor <= baixo:
        return PASSA
    return ATENCAO if valor <= alto else FALHA


def _pct(parte, todo):
    return (100.0 * parte / todo) if todo else None


def criterios(v, e, g, fic=None, fdia=None, extra=None):
    """Os sete critérios, cada um com valor medido, limite e resultado.

    Devolve uma lista de dicionários — a tabela do relatório sai direto daqui,
    e o veredicto também, para que os dois nunca discordem.
    """
    fic, fdia, extra = fic or {}, fdia or {}, extra or {}
    c = []

    # 1 — ELIMINATORIO. Sem isto nenhum numero abaixo vale nada.
    # O `validador.py` NAO escreve um campo chamado `veredicto`: ele escreve
    # `compila`, `converge`, `resolve` e a `causa` classificada. A primeira
    # versao deste modulo procurava `veredicto`, nao achava, e carimbava
    # INCONCLUSIVO uma base que estava inteiramente medida — o defeito espelha
    # o anterior (ausencia lida como aprovacao), so que para o outro lado.
    ver = str(v.get('veredicto') or v.get('causa') or '').split('[')[0].strip()
    compila = v.get('compila')
    converge = v.get('converge')
    resolve = v.get('resolve')
    nan = v.get('barras_nan') or v.get('nos_nan') or 0
    if compila is None and not ver:
        resultado, mostrado = SEM_DADO, 'a etapa de validação não rodou'
    elif compila is False:
        resultado, mostrado = FALHA, 'não compila'
    elif converge is False:
        resultado, mostrado = FALHA, 'não converge'
    elif nan:
        resultado, mostrado = FALHA, '%s barras com potência indefinida' % _mil(nan)
    elif ver in ('NAO_COMPILA', 'NAO_CONVERGE', 'POTENCIA_NAN'):
        resultado, mostrado = FALHA, 'não (%s)' % ver
    else:
        mostrado = 'sim'
        if resolve is not None:
            mostrado += ' (compila, converge e resolve)'
        resultado = PASSA
    c.append({
        'nome': 'Fecha eletricamente',
        'valor': mostrado,
        'limite': 'compila, converge e não tem potência indefinida',
        'resultado': resultado,
        'eliminatorio': True,
        'porque': ('É a condição de entrada: um modelo que o próprio OpenDSS '
                   'não resolve não produz número nenhum que se possa ler.')})

    # 2 — conectividade
    mortas = v.get('cargas_sem_tensao')
    p_mortas = _pct(mortas, v.get('n_cargas'))
    c.append({
        'nome': 'Cargas que recebem tensão',
        'valor': ('%s de %s sem tensão (%s%%)'
                  % (_mil(mortas), _mil(v.get('n_cargas')), _dec(p_mortas, 2))
                  if p_mortas is not None else '—'),
        'limite': 'até %s%% sem tensão' % _dec(SEM_TENSAO[0], 0),
        'resultado': _classe(p_mortas, SEM_TENSAO),
        'eliminatorio': False,
        'porque': ('Carga sem tensão não entra na conta de energia nem de '
                   'perda. Acima do limite, os totais deste modelo estão '
                   'medidos sobre uma rede menor do que a declarada.')})

    # 3 — tensao
    fora = extra.get('pct_fora_faixa')
    if fora is None:
        fora = fic.get('pct_fora_faixa')
    c.append({
        'nome': 'Tensão dentro da faixa do PRODIST',
        'valor': ('%s%% das barras fora de 0,93–1,05 pu' % _dec(fora, 2)
                  if fora is not None else '—'),
        'limite': 'até %s%% fora' % _dec(FORA_FAIXA[0], 0),
        'resultado': _classe(fora, FORA_FAIXA),
        'eliminatorio': False,
        'porque': ('Faixa adequada do PRODIST módulo 8. Poucas barras fora é '
                   'ponta de alimentador; muitas é o tronco inteiro, e aí o '
                   'problema é de condutor, de regulação ou de laço.')})

    # 4 — perda
    perda = e.get('perdas_pct')
    if perda is None:
        perda = fic.get('perdas_pct')
    c.append({
        'nome': 'Perda técnica plausível',
        'valor': '%s%% da energia injetada' % _dec(perda) if perda is not None else '—',
        'limite': 'até %s%%' % _dec(PERDA[0], 0),
        'resultado': _classe(perda, PERDA),
        'eliminatorio': False,
        'porque': ('A âncora nacional da ANEEL é 7,4% de perda técnica TOTAL, '
                   'e este modelo não contém a rede secundária — a parcela que '
                   'ele vê deveria ficar abaixo disso. Acima do limite é sinal '
                   'de problema de modelagem, e não de rede ruim.')})

    # 5 — ampacidade
    sob = extra.get('pct_sobrecarga')
    c.append({
        'nome': 'Condutores dentro da ampacidade',
        'valor': ('%s%% dos trechos acima de 100%%' % _dec(sob, 2)
                  if sob is not None else '—'),
        'limite': 'até %s%% acima' % _dec(SOBRECARGA[0], 0),
        'resultado': _classe(sob, SOBRECARGA),
        'eliminatorio': False,
        'porque': ('Trecho acima da própria ampacidade em rede real aparece em '
                   'ponta, no pico. Em massa é o par (resistência, ampacidade) '
                   'do cadastro não descrevendo o cabo que está no poste.')})

    # 6 — o dia inteiro
    passos = fdia.get('passos_validos')
    c.append({
        'nome': 'O dia resolvido por inteiro',
        'valor': '%s de 96 passos' % _mil(passos) if passos else '—',
        'limite': 'pelo menos %d passos' % PASSOS_MINIMOS,
        'resultado': _classe(passos, (PASSOS_MINIMOS, PASSOS_MINIMOS - 20),
                             invertido=True),
        'eliminatorio': False,
        'porque': ('Passo que não converge sai da integral: a energia do dia '
                   'passa a estar medida sobre menos de 24 horas. É também o '
                   'que habilita analisar geração distribuída.')})

    # 7 — a curva e crivel
    fc = fdia.get('fator_de_carga')
    c.append({
        'nome': 'Curva de carga com forma de rede',
        'valor': 'fator de carga %s' % _dec(fc, 3) if fc is not None else '—',
        'limite': 'abaixo de %s' % _dec(FATOR_CARGA[0], 2),
        'resultado': _classe(fc, FATOR_CARGA),
        'eliminatorio': False,
        'porque': ('Fator de carga alto demais significa a mesma curva '
                   'aplicada a todos os consumidores. A curva achatada '
                   'subestima a perda de pico, que cresce com o quadrado da '
                   'corrente.')})
    return c


def julgar(crits, anom=None):
    """A classificação final, a partir dos critérios e dos achados graves."""
    if any(x['eliminatorio'] and x['resultado'] == FALHA for x in crits):
        return REPROVADO
    # AUSENCIA DE MEDIDA NAO E APROVACAO. Sem o eliminatorio, ou com metade dos
    # criterios sem dado, nao ha o que julgar — e dizer isso e mais util do que
    # um selo verde que ninguem pode conferir.
    if any(x['eliminatorio'] and x['resultado'] == SEM_DADO for x in crits):
        return INCONCLUSIVO
    if sum(1 for x in crits if x['resultado'] == SEM_DADO) >= 3:
        return INCONCLUSIVO
    falhas = sum(1 for x in crits if x['resultado'] == FALHA)
    atencoes = sum(1 for x in crits if x['resultado'] == ATENCAO)
    graves = sum(1 for a in (anom or []) if a.get('gravidade') == 'grave')
    if falhas or graves >= 2:
        return RESTRITO
    if atencoes >= 2 or graves:
        return RESSALVAS
    if atencoes:
        return RESSALVAS
    return APROVADO


# ===========================================================================
#  PARA QUE SERVE, E PARA QUE NAO SERVE
# ===========================================================================
#
# A parte mais util do veredicto, e a que nao existia em lugar nenhum. Um
# modelo com 30% das barras sem tensao continua servindo para INSPECIONAR
# CONECTIVIDADE — ele so nao serve para medir perda. Carimba-lo de "ruim" joga
# fora trabalho bom, e carimba-lo de "OK" faz alguem publicar um numero que
# nao vale.

def usos(crits, anom=None):
    """Devolve (serve_para, nao_serve_para), duas listas de frases."""
    por_nome = {x['nome']: x['resultado'] for x in crits}
    ruim = (FALHA, ATENCAO)
    serve, nao = [], []

    if por_nome.get('Fecha eletricamente') == SEM_DADO:
        return (['**auditar a qualidade do dado publicado**',
                 '**localizar os elementos problemáticos** pelo nome, na seção '
                 'de diagnóstico'],
                ['**qualquer conclusão sobre a aptidão deste modelo** — falta '
                 'medida. Rode as etapas que faltam (o caminho normal do '
                 '`Validator.py` roda todas) e o veredicto se completa'])
    if por_nome.get('Fecha eletricamente') == FALHA:
        return ([], ['qualquer uso quantitativo — o modelo não resolve; o que '
                     'serve aqui é o diagnóstico da causa, na seção de '
                     'anomalias'])

    conect = por_nome.get('Cargas que recebem tensão')
    perda = por_nome.get('Perda técnica plausível')
    tensao = por_nome.get('Tensão dentro da faixa do PRODIST')
    amp = por_nome.get('Condutores dentro da ampacidade')
    dia = por_nome.get('O dia resolvido por inteiro')
    curva = por_nome.get('Curva de carga com forma de rede')

    # sempre vale
    serve.append('**auditar a qualidade do dado publicado** — é para isto que '
                 'a ferramenta existe, e um modelo que reprova é um resultado '
                 'de auditoria, não um fracasso')
    serve.append('**localizar os elementos problemáticos** pelo nome, na seção '
                 'de diagnóstico')

    if conect == PASSA and perda == PASSA:
        serve.append('**estimar perda técnica de média tensão**, com a ressalva '
                     'permanente de que a rede secundária não está no modelo')
    elif conect in ruim:
        nao.append('**medir perda ou energia** — parte da rede não chega à '
                   'fonte, e os totais estão calculados sobre o que sobrou')
    elif perda in ruim:
        nao.append('**publicar a perda** — o valor está fora do plausível para '
                   'uma rede de média tensão, e a causa precisa ser diagnosticada '
                   'antes de o número sair daqui')

    if tensao == PASSA:
        serve.append('**estudo de perfil de tensão e de regulação**')
    else:
        nao.append('**dimensionar regulação de tensão** — o perfil deste modelo '
                   'ainda carrega o efeito do que está fora da faixa, e '
                   'corrigi-lo muda o dimensionamento')

    if amp == PASSA:
        serve.append('**verificação de carregamento de condutor**')
    else:
        nao.append('**concluir sobre carregamento de condutor** — a ampacidade '
                   'declarada não é coerente com a corrente calculada em parte '
                   'da rede')

    if dia == PASSA and curva == PASSA:
        serve.append('**estudo de geração distribuída no tempo** — fluxo '
                     'reverso, coincidência com a ponta e sobretensão de '
                     'injeção, que é o que a série de 96 passos habilita')
    elif curva in ruim:
        nao.append('**dimensionar pela ponta** — a curva de carga está achatada '
                   'por tipologia única e o pico verdadeiro está diluído')
    elif dia in ruim:
        nao.append('**usar a energia do dia** — parte dos 96 passos não fechou')

    if not nao:
        nao.append('nada foi identificado que restrinja o uso deste modelo '
                   'dentro do escopo da ferramenta — o que **não** significa '
                   'que a rede real seja assim: significa que o dado publicado '
                   'é coerente consigo mesmo')
    return serve, nao


def frase_do_veredicto(classe, crits, anom=None):
    """O parágrafo que abre o relatório."""
    falhas = [x['nome'] for x in crits if x['resultado'] == FALHA]
    aten = [x['nome'] for x in crits if x['resultado'] == ATENCAO]
    graves = sum(1 for a in (anom or []) if a.get('gravidade') == 'grave')

    if classe == INCONCLUSIVO:
        faltando = [x['nome'] for x in crits if x['resultado'] == SEM_DADO]
        return ('**Não há veredicto**: faltam medidas para julgar este modelo '
                '(%s). Isto não é reprovação nem aprovação — é a ausência das '
                'etapas que produzem esses números. Rodar o ciclo completo '
                'preenche a tabela abaixo.' % _lista(faltando))
    if classe == APROVADO:
        t = ('Este modelo **passa nos sete critérios**. Os números que ele '
             'produz podem ser usados dentro do escopo da ferramenta, e as '
             'ressalvas que restam são as do projeto inteiro, não desta '
             'subestação.')
    elif classe == RESSALVAS:
        t = ('Este modelo **fecha e é utilizável**, com ressalvas. Nenhum '
             'critério reprovou; %s ficou em atenção%s.'
             % (_lista(aten) or 'nenhum',
                ' e há %d achado grave no diagnóstico' % graves if graves else ''))
    elif classe == RESTRITO:
        t = ('Este modelo **resolve, mas não serve para tudo**. Reprovou em %s.'
             % (_lista(falhas) or 'nenhum critério, mas acumula achados graves'))
        t += (' Isso **não quer dizer que a rede seja ruim**: na esmagadora '
              'maioria dos casos medidos neste projeto a causa é lacuna do '
              'cadastro publicado, e a seção de diagnóstico nomeia os '
              'elementos envolvidos.')
    else:
        t = ('Este modelo **não fecha eletricamente** e nenhum número abaixo '
             'deve ser usado. O que vale nesta página é o diagnóstico da '
             'causa.')
    return t


def _lista(nomes):
    if not nomes:
        return ''
    nomes = ['«%s»' % n for n in nomes]
    if len(nomes) == 1:
        return nomes[0]
    return ', '.join(nomes[:-1]) + ' e ' + nomes[-1]


def _mil(x):
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return '—'


def _dec(x, casas=2):
    try:
        return (('%%.%df' % casas) % float(x)).replace('.', ',')
    except (TypeError, ValueError):
        return '—'


def completo(v, e, g, fic=None, fdia=None, extra=None, anom=None):
    """Tudo de uma vez: (classe, critérios, frase, serve, não serve)."""
    c = criterios(v, e, g, fic, fdia, extra)
    classe = julgar(c, anom)
    serve, nao = usos(c, anom)
    return classe, c, frase_do_veredicto(classe, c, anom), serve, nao
