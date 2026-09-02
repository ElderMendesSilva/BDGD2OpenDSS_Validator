# -*- coding: utf-8 -*-
"""O diagnóstico das anomalias: não que existem, mas POR QUE existem.

A diferença entre este módulo e o `laudo.py` é a diferença entre um número e
uma explicação. O laudo diz "uma barra fora da faixa (0,0%)"; aqui se diz
**qual** barra, **quanto** ela marca, e **qual elemento do modelo a colocou
ali** — com o nome que a pessoa vai digitar no OpenDSS para ir olhar.

O caso que motivou o módulo: no perfil da subestação 5003305 havia um ponto
solitário em 1,551 pu, entre 6.731 barras todas abaixo de 1,00. Sozinho ele
esticava o eixo e escondia a rede inteira. Perseguido até o fim, era o
transformador 1019552488 com o secundário declarado em **22 kV** onde o normal
é 0,22 kV — o código 61 da tabela TTEN da ANEEL no lugar do código 10. Um
transformador de 75 kVA que a BDGD publica como elevador para 22 kV.

**Isso não é defeito do conversor: é o cadastro.** A tabela TTEN é da ANEEL e
foi seguida à risca; trocar o código na origem trocou a tensão no modelo. E é
exatamente esta a tese do projeto — a ferramenta existe para tornar visível o
que o dado publicado tem, e um ponto solitário num gráfico é uma das formas
mais eficientes de tornar visível.

REGRA DESTE MÓDULO: **nunca afirmar causa que não foi verificada no modelo.**
Cada achado diz o que foi medido e, separadamente, qual a explicação provável.
Quando há mais de uma explicação possível, elas são listadas — inventar
certeza é pior do que admitir duas hipóteses.
"""

# Gravidade, que ordena a lista e escolhe a cor no relatório.
GRAVE, ATENCAO, NOTA = 'grave', 'atencao', 'nota'

# Acima disto a barra não é "tensão alta": é outro nível de tensão entrando na
# conta. 1,05 pu é o limite do PRODIST; 1,15 já não se explica por regulação.
PU_OUTRO_NIVEL = 1.15
# Abaixo disto não é queda de tensão: é rede que não deveria estar energizada
# assim, ou impedância incoerente.
PU_IMPLAUSIVEL = 0.80


def _mil(x):
    try:
        return '{:,.0f}'.format(float(x)).replace(',', '.')
    except (TypeError, ValueError):
        return '—'


def _dec(x, casas=3):
    try:
        return (('%%.%df' % casas) % float(x)).replace('.', ',')
    except (TypeError, ValueError):
        return '—'


def _achado(figura, gravidade, titulo, medido, causa, elementos=None):
    """Um achado. `medido` é fato; `causa` é leitura; nunca se misturam."""
    return {'figura': figura, 'gravidade': gravidade, 'titulo': titulo,
            'medido': medido, 'causa': causa, 'elementos': elementos or []}


# ===========================================================================
#  OS QUE EXIGEM O MODELO ABERTO
# ===========================================================================

def _v(x):
    try:
        return x() if callable(x) else x
    except Exception:                                        # noqa: BLE001
        return None


def do_modelo(dss, limite=6):
    """Percorre o circuito resolvido e devolve a lista de achados.

    `limite` é quantos elementos nomear por achado: a lista existe para alguém
    ir olhar, e trinta nomes numa página não são olhados por ninguém.
    """
    achados = []
    try:
        achados += _tensao_alta(dss, limite)
        achados += _tensao_baixa(dss, limite)
        achados += _barras_mortas(dss, limite)
        achados += _condutor_sobrecarregado(dss, limite)
        achados += _carga_com_tensao_incoerente(dss, limite)
        achados += _coordenadas(dss)
    except Exception:                                        # noqa: BLE001
        # O diagnóstico é um extra: ele nunca pode derrubar o relatório da
        # subestação que ele deveria estar explicando.
        pass
    ordem = {GRAVE: 0, ATENCAO: 1, NOTA: 2}
    achados.sort(key=lambda a: ordem.get(a['gravidade'], 9))
    return achados


def _barras_de_mt(dss):
    """(nome, pu mínimo, kVBase) das barras de média tensão energizadas."""
    saida = []
    for b in _v(dss.Circuit.AllBusNames) or []:
        dss.Circuit.SetActiveBus(b)
        kv = _v(dss.Bus.kVBase) or 0
        if kv <= 1:
            continue
        pus = [p for p in (_v(dss.Bus.puVmagAngle) or [])[0::2] if 0.001 < p < 5]
        if pus:
            saida.append((b, min(pus), max(pus), kv))
    return saida


def _trafo_da_barra(dss, barra):
    """O transformador ligado a esta barra, e o kV que ele declara ali.

    É o que transforma "esta barra está em 1,55 pu" em "o transformador X
    declara 22 kV nesta barra" — a frase que alguém consegue usar.
    """
    alvo = barra.split('.')[0].lower()
    i = _v(dss.Transformers.First)
    while i:
        nome = _v(dss.Transformers.Name)
        dss.Circuit.SetActiveElement('Transformer.' + nome)
        barras = [x.split('.')[0].lower() for x in (_v(dss.CktElement.BusNames) or [])]
        if alvo in barras:
            enrolamento = barras.index(alvo) + 1
            try:
                dss.Transformers.Wdg(enrolamento)
                return nome, _v(dss.Transformers.kV)
            except Exception:                                # noqa: BLE001
                return nome, None
        i = _v(dss.Transformers.Next)
    return None, None


def _tensao_alta(dss, limite):
    """Barra acima de 1,15 pu quase nunca é sobretensão: é outro nível de
    tensão declarado onde não devia."""
    altas = [(pu_max, b, kv) for b, _pu, pu_max, kv in _barras_de_mt(dss)
             if pu_max > PU_OUTRO_NIVEL]
    if not altas:
        return []
    altas.sort(reverse=True)
    nomes = []
    explicacoes = set()
    for pu, b, kv in altas[:limite]:
        trafo, kv_decl = _trafo_da_barra(dss, b)
        if trafo and kv_decl and kv_decl > 1.0:
            nomes.append('%s: %s pu — Transformer.%s declara %s kV nesta barra, '
                         'contra a base de %s kV'
                         % (b, _dec(pu), trafo, _dec(kv_decl, 4),
                            _dec(kv * (3 ** 0.5), 2)))
            explicacoes.add('tensao_declarada')
        else:
            nomes.append('%s: %s pu (base %s kV)' % (b, _dec(pu), _dec(kv, 4)))
            explicacoes.add('outra')

    if 'tensao_declarada' in explicacoes:
        causa = (
            'A explicação verificada é **tensão declarada errada no cadastro**, '
            'e não sobretensão da rede. O transformador nomeado acima declara, '
            'no lado de baixa, uma tensão de média tensão — o padrão nacional é '
            '0,22 kV ou 0,11 kV, e o valor declarado é cem vezes maior. Na '
            'tabela TTEN da ANEEL o código 61 (22 kV) fica ao lado do código 10 '
            '(220 V), e trocar um pelo outro na origem produz exatamente isto. '
            'O conversor seguiu o código publicado: **o defeito está no dado, '
            'não no modelo**. Corrigir exige corrigir a BDGD; enquanto isso, a '
            'barra sobe no gráfico e é assim que ela é encontrada.')
    else:
        causa = (
            'Sobretensão acima de 1,15 pu não se explica por regulação. As '
            'causas conhecidas, em ordem de frequência: nível de tensão '
            'declarado errado no transformador desta barra, tap de regulador '
            'travado no máximo, e geração distribuída injetando em ponta de '
            'alimentador muito descarregado.')

    return [_achado(
        'perfil', ATENCAO if len(altas) < 5 else GRAVE,
        'Barras acima de %s pu' % _dec(PU_OUTRO_NIVEL, 2),
        '**%s de %s barras** de média tensão passam de %s pu; a maior marca '
        '**%s pu**.' % (_mil(len(altas)), _mil(len(_barras_de_mt(dss))),
                        _dec(PU_OUTRO_NIVEL, 2), _dec(altas[0][0])),
        causa, nomes)]


def _tensao_baixa(dss, limite):
    baixas = [(pu, b, kv) for b, pu, _x, kv in _barras_de_mt(dss)
              if pu < PU_IMPLAUSIVEL]
    if not baixas:
        return []
    baixas.sort()
    total = len(_barras_de_mt(dss))
    frac = 100.0 * len(baixas) / total if total else 0
    nomes = ['%s: %s pu' % (b, _dec(pu)) for pu, b, _kv in baixas[:limite]]
    causa = (
        'Tensão abaixo de %s pu não é queda normal de tronco. As três causas '
        'medidas neste projeto, na ordem em que aparecem: **regulador emitido '
        'em paralelo com o trecho** (achado 22), que drena corrente por um laço '
        'e derruba o alimentador inteiro; **resistência de condutor incoerente** '
        'no cadastro, que multiplica a queda sem multiplicar a corrente; e '
        '**tronco longo sem regulador declarado**. A figura do perfil separa as '
        'três: o laço faz a nuvem inteira descer junto, o condutor faz um ramo '
        'descolar dos vizinhos, e o tronco longo faz a queda crescer com a '
        'distância.' % _dec(PU_IMPLAUSIVEL, 2))
    return [_achado('perfil', GRAVE if frac > 5 else ATENCAO,
                    'Barras abaixo de %s pu' % _dec(PU_IMPLAUSIVEL, 2),
                    '**%s barras (%s%%)** ficam abaixo de %s pu; a menor marca '
                    '**%s pu**.' % (_mil(len(baixas)), _dec(frac, 1),
                                    _dec(PU_IMPLAUSIVEL, 2), _dec(baixas[0][0])),
                    causa, nomes)]


def _barras_mortas(dss, limite):
    """Barra sem tensão nenhuma: não chega à fonte."""
    mortas = []
    for b in _v(dss.Circuit.AllBusNames) or []:
        dss.Circuit.SetActiveBus(b)
        if (_v(dss.Bus.kVBase) or 0) <= 1:
            continue
        pus = [p for p in (_v(dss.Bus.puVmagAngle) or [])[0::2]]
        if not pus or max(pus) < 0.001:
            mortas.append(b)
    if not mortas:
        return []
    total = len(_barras_de_mt(dss)) + len(mortas)
    frac = 100.0 * len(mortas) / total if total else 0
    causa = (
        'Barra sem tensão nenhuma não é tensão baixa: é barra que a matriz de '
        'admitância não liga a fonte alguma. O caminho elétrico até a '
        'subestação está interrompido no dado — trecho de ligação não '
        'declarado, chave aberta que na rede real está fechada, ou ramal '
        'órfão. **Toda perda e toda energia deste modelo estão medidas sobre a '
        'rede que sobrou**, e não sobre a rede declarada. Cerca de 7% dos '
        'trechos de média tensão do país estão nesta situação (achados 21 e '
        '23), então a presença aqui é esperada; a fração é que diz se esta '
        'subestação é típica.')
    return [_achado('perfil', GRAVE if frac > 10 else ATENCAO,
                    'Barras que não recebem tensão',
                    '**%s de %s barras** de média tensão (%s%%) ficam sem '
                    'tensão nenhuma.' % (_mil(len(mortas)), _mil(total),
                                         _dec(frac, 1)),
                    causa, mortas[:limite])]


def _condutor_sobrecarregado(dss, limite):
    piores = []
    i = _v(dss.Lines.First)
    n = 0
    while i:
        nome = _v(dss.Lines.Name)
        nom = _v(dss.Lines.NormAmps) or 0
        dss.Circuit.SetActiveElement('Line.' + nome)
        c = (_v(dss.CktElement.CurrentsMagAng) or [])[0::2]
        if nom and c:
            n += 1
            pct = 100.0 * max(c[:3]) / nom
            if pct > 100:
                piores.append((pct, nome, max(c[:3]), nom))
        i = _v(dss.Lines.Next)
    if not piores:
        return []
    piores.sort(reverse=True)
    frac = 100.0 * len(piores) / n if n else 0
    nomes = ['Line.%s: %s%% (%s A num condutor de %s A)'
             % (nome, _dec(pct, 0), _dec(amp, 0), _dec(nom, 0))
             for pct, nome, amp, nom in piores[:limite]]
    if piores[0][0] > 500:
        causa = (
            'Um trecho conduzindo **mais de cinco vezes** a própria ampacidade '
            'não é rede sobrecarregada — nenhum condutor real sobrevive a isso. '
            'É corrente de laço: dois caminhos em paralelo entre as mesmas '
            'barras, com o regulador ou a chave fechando o anel. Foi assim que '
            'o achado 22 apareceu, com 2.506 A num cabo de 145 A.')
    else:
        causa = (
            'Corrente acima da ampacidade declarada tem duas leituras, e a '
            'fração decide qual: poucos trechos, em ponta de alimentador, é '
            'carregamento real de ponta; **%s%% dos trechos**, como aqui, quase '
            'sempre é o par (resistência, ampacidade) do cadastro não '
            'descrevendo o cabo que está no poste — a bitola declarada é menor '
            'que a instalada.' % _dec(frac, 1))
    return [_achado('condutor', GRAVE if frac > 5 else ATENCAO,
                    'Trechos acima da própria ampacidade',
                    '**%s de %s trechos (%s%%)** conduzem acima da ampacidade '
                    'declarada; o pior chega a **%s%%**.'
                    % (_mil(len(piores)), _mil(n), _dec(frac, 1),
                       _dec(piores[0][0], 0)),
                    causa, nomes)]


def _carga_com_tensao_incoerente(dss, limite):
    """Carga cuja tensão declarada não é a da barra onde ela está."""
    ruins = []
    i = _v(dss.Loads.First)
    n = 0
    while i:
        nome = _v(dss.Loads.Name)
        kv = _v(dss.Loads.kV) or 0
        dss.Circuit.SetActiveElement('Load.' + nome)
        barras = _v(dss.CktElement.BusNames) or ['']
        b = barras[0].split('.')[0]
        dss.Circuit.SetActiveBus(b)
        base = _v(dss.Bus.kVBase) or 0
        n += 1
        # Comparação por ordem de grandeza: fase-neutro contra fase-fase já dá
        # fator 1,73 legitimamente, então só um fator 10 ou mais é anomalia.
        if kv and base and (kv / base > 5 or base / kv > 5):
            ruins.append((nome, kv, base, b))
        i = _v(dss.Loads.Next)
    if not ruins:
        return []
    nomes = ['Load.%s em %s: declara %s kV numa barra de base %s kV'
             % (nome, b, _dec(kv, 4), _dec(base, 4))
             for nome, kv, base, b in ruins[:limite]]
    return [_achado('perfil', ATENCAO, 'Cargas com tensão incoerente com a barra',
                    '**%s de %s cargas** declaram uma tensão que difere da base '
                    'da própria barra por mais de cinco vezes.'
                    % (_mil(len(ruins)), _mil(n)),
                    'Carga com tensão declarada muito acima da barra tem '
                    'impedância equivalente grande demais e **quase não puxa '
                    'corrente**: ela existe no modelo e não aparece na conta de '
                    'energia. Vem do mesmo código de tensão trocado que desloca '
                    'a barra no perfil, e é por isso que os dois achados '
                    'costumam aparecer juntos.', nomes)]


def _coordenadas(dss):
    """Sem coordenada não há mapa, e o mapa é a figura que denuncia geometria."""
    try:
        n = 0
        total = 0
        for b in _v(dss.Circuit.AllBusNames) or []:
            dss.Circuit.SetActiveBus(b)
            total += 1
            if _v(dss.Bus.Coorddefined):
                n += 1
    except Exception:                                        # noqa: BLE001
        return []
    if not total or n == total:
        return []
    frac = 100.0 * (total - n) / total
    if frac < 1:
        return []
    return [_achado('mapa', NOTA, 'Barras sem coordenada',
                    '**%s de %s barras (%s%%)** não têm coordenada.'
                    % (_mil(total - n), _mil(total), _dec(frac, 1)),
                    'Coordenada ausente não afeta nenhum resultado elétrico — o '
                    'leitor trabalha sem geometria. Afeta só o mapa, que desenha '
                    'a parte que tem coordenada e omite o resto, então a figura '
                    'mostra menos rede do que o modelo contém.')]


# ===========================================================================
#  OS QUE SAEM DA SERIE DO DIA
# ===========================================================================

def do_dia(fdia):
    """Achados que só a série de 96 passos revela."""
    a = []
    if not fdia:
        return a
    fc = fdia.get('fator_de_carga')
    if fc is not None and fc > 0.85:
        a.append(_achado(
            'duracao', ATENCAO, 'Fator de carga alto demais para ser rede',
            'O fator de carga é **%s**, quando o típico de distribuição fica '
            'entre 0,45 e 0,65.' % _dec(fc),
            'Curva de carga achatada assim significa **a mesma curva aplicada a '
            'todos os consumidores**: a BDGD declara a curva por tipologia, e '
            'quando a tipologia não varia dentro da subestação a soma perde o '
            'formato. A consequência prática é que **a perda de pico está '
            'subestimada**, porque perda cresce com o quadrado da corrente e o '
            'pico verdadeiro foi diluído.'))

    rz = fdia.get('razao_perda_pico_vale')
    if rz is not None and rz < 1.5:
        a.append(_achado(
            'perda_carga', NOTA, 'A perda quase não depende da carga',
            'A perda vai de %s kW no vale a %s kW no pico — razão de apenas '
            '**%s×**.' % (_dec(fdia.get('perda_vale_kW'), 1),
                          _dec(fdia.get('perda_pico_kW'), 1), _dec(rz, 2)),
            'Quando a perda mal reage à carga, o que domina é o **ferro dos '
            'transformadores**: perda a vazio, presente 24 horas por dia, '
            'proporcional ao número de transformadores e não a quilômetros nem '
            'a consumo. É a parcela que a perda técnica declarada pela '
            'distribuidora costuma não contemplar, e em 40 de 81 bases a perda '
            'declarada é **menor que esse ferro** (achado 13) — o que torna a '
            'declaração impossível antes de qualquer comparação com o modelo.'))

    co = fdia.get('coincidencia_gd')
    if co is not None and co < 0.2 and fdia.get('kWh_gd'):
        a.append(_achado(
            'gd_cobre', ATENCAO, 'A geração distribuída não alivia a ponta',
            'No instante do pico de carga há **%s kW** de geração disponível, '
            'contra um pico de geração de %s kW — coincidência de **%s%%**.'
            % (_mil(fdia.get('gd_no_pico_kW')), _mil(fdia.get('gd_pico_kW')),
               _dec(100 * co, 1)),
            'O pico da geração é às %s e o da carga às %s. A geração desloca '
            'energia no tempo, mas **não reduz o carregamento de ponta** — '
            'dimensionar condutor ou transformador contando com ela seria erro. '
            'Este é o achado que só existe porque a rede foi resolvida em 96 '
            'passos: um estudo de instante único não visita as duas horas.'
            % (_hora(fdia.get('hora_gd_pico')), _hora(fdia.get('hora_pico')))))

    hr = fdia.get('horas_reverso')
    if hr:
        a.append(_achado(
            'gd_fluxo', ATENCAO, 'A rede exporta em parte do dia',
            'Em **%s horas** o fluxo se inverte e a subestação recebe potência '
            'da rede.' % _dec(hr, 2),
            'Fluxo reverso é onde aparecem **sobretensão** e **atuação indevida '
            'de regulador**, que é ajustado supondo que a corrente sempre desce '
            'do tronco para a ponta. Nenhum desses dois efeitos é visível num '
            'estudo de ponta de carga, e é por isso que a série de 15 minutos '
            'não é luxo neste projeto.'))

    if fdia.get('exporta_no_dia'):
        a.append(_achado(
            'dia', GRAVE, 'A subestação exporta energia no balanço do dia',
            'A fonte entrega **%s kWh** no dia — valor negativo — contra %s kWh '
            'gerados pela geração distribuída.'
            % (_mil(fdia.get('kWh_fonte')), _mil(fdia.get('kWh_gd'))),
            'Somando as 24 horas, esta subestação **devolve mais energia ao '
            'sistema do que recebe**. Isso é possível numa hora do dia, e é o '
            'fluxo reverso; no balanço de um dia inteiro, não é operação — é '
            'declaração. A leitura provável é **geração distribuída cadastrada '
            'sem a carga correspondente**: a unidade consumidora que recebeu o '
            'sistema fotovoltaico está na BDGD, e o consumo dela não está, ou '
            'está registrado sob outra subestação. Enquanto isso não for '
            'reconciliado, a energia, a perda percentual e a penetração desta '
            'subestação não têm significado físico — o denominador delas é uma '
            'carga que o cadastro não declara.'))

    pf = fdia.get('passos_falhos')
    if pf:
        a.append(_achado(
            'dia', ATENCAO, 'Passos do dia que não convergiram',
            '**%d dos 96 passos** não fecharam.' % pf,
            'Passo que não converge vira lacuna na curva e sai da integral de '
            'energia: **os totais do dia estão medidos sobre menos de 24 '
            'horas**. Como cada passo é resolvido do zero, a falha é do ponto '
            'de operação daquele instante e não de uma trajetória degradada — '
            'tipicamente o instante de maior geração ou de menor carga.'))
    return a


def _hora(h):
    try:
        h = float(h)
        return '%dh%02d' % (int(h), round((h - int(h)) * 60))
    except (TypeError, ValueError):
        return '—'


def por_figura(achados):
    """Agrupa por figura, para que cada uma leve o seu diagnóstico junto."""
    d = {}
    for a in achados or []:
        d.setdefault(a['figura'], []).append(a)
    return d
