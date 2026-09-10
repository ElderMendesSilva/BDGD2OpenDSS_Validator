# -*- coding: utf-8 -*-
"""
CLASSIFICACAO DE CAUSA RAIZ, subestacao por subestacao.

O validador diz QUE esta ruim. Este modulo diz POR QUE, e principalmente
separa o que e defeito do conversor do que e caracteristica da rede — os
dois exigem acoes opostas e confundi-los faz perder tempo.

As causas, na ordem em que sao testadas:

  MODELO_QUEBRADO   nao compila, nao converge, ou tem no com NaN. E defeito
                    nosso: sempre acionavel.

                    ATE 02/09/2026 ELE INCLUIA "TEM CARGA SEM TENSAO", e essa
                    linha sozinha respondia por 96,7% da classe — 1.209 de
                    1.250 subestacoes da safra 2025 (achado 25). Falha de
                    modelo de verdade eram 41, ou 1,0% do pais. Pior: 650
                    daquelas 1.209 perdiam MENOS DE 1% da carga e mesmo assim
                    recebiam um rotulo afirmando que o modelo estava quebrado.

                    Carga sem tensao e um FATO DO CADASTRO (achados 21 e 23),
                    nao defeito do conversor, e a gravidade dela varia por tres
                    ordens de grandeza. Por isso ela saiu daqui e virou tres
                    classes proprias, abaixo.

  SUBESTACAO_ILHADA  praticamente TODA a carga sem tensao. A rede existe, a
                    fonte existe, e as duas nao se tocam: o fluxo converge em
                    duas iteracoes porque nao ha carga ligada. Sao 8 na safra
                    2025, e o achado 25 mostrou que a causa era nossa — o
                    limiar de `ligacao.py` descartava a componente. Acionavel.

  REDE_PARCIAL      mais de 10% da carga sem tensao. Parte relevante da rede
                    nao chega a fonte, e toda perda e energia da subestacao
                    estao medidas sobre o que sobrou. Acionavel.

  RAMAIS_SOLTOS     de 1% a 10% da carga sem tensao. Padrao de ramal cujo
                    trecho de ligacao nao foi declarado. Nao invalida o
                    modelo; entra como ressalva quantificada.

                    Abaixo de 1% nao vira causa NENHUMA: a subestacao segue
                    para os testes seguintes e pode terminar `OK`. O numero
                    continua no `validacao.json`, em `cargas_sem_tensao` — o
                    que muda e parar de chamar de quebrado um modelo que
                    perde uma carga em mil.

                    O NaN merece atencao especial porque os dois motores do
                    OpenDSS discordam dele. Na DALP, o mesmo arquivo dava 36
                    nos NaN no DSS C-API (opendssdirect, usado aqui) e 49.857
                    no motor oficial da EPRI (COM v11) — o C-API contem o NaN
                    na ilha que o gerou, o da EPRI propaga pela fatoracao e
                    derruba a rede inteira. Um punhado de nos NaN aqui e um
                    modelo inutilizavel no OpenDSS que o usuario abre. Por
                    isso qualquer NaN e MODELO_QUEBRADO, nao ressalva.

  TENSAO_IMPLAUSIVEL  tensao mediana abaixo de meio pu. Nao e subtensao: e
                    solucao fora da bacia de operacao, em que a carga de
                    potencia constante puxa corrente muito acima da nominal e
                    a perda medida e a da propria subtensao. Vem ANTES de
                    CARGA_ALTA, REDE_EXTENSA e REGULADOR_SATURADO porque os
                    tres podem ser verdade ao mesmo tempo e descrevem o
                    sintoma, nao a doenca (achados 1, 60 e 61). Acionavel: a
                    acao e nao publicar o numero.

  REDE_EXTENSA      alimentador muito acima do normal da concessao (a
                    mediana e 8,9 km; sete alimentadores passam de 100 km, e
                    dois deles, na DREG, tem 440 e 335 km). Nesses casos a
                    queda de tensao e fisicamente correta e nao ha o que
                    corrigir sem o ajuste de campo dos reguladores.

                    SO VALE COM A TENSAO RUIM (achado 62-B). Alimentador
                    longo com a tensao adequada nao tem problema de tensao a
                    explicar — a NEOENERGIA47/SBC levava este rotulo com
                    1,036 pu, ACIMA da nominal.

  REGULADOR_SATURADO  ha regulador na subestacao e todos estao no tape
                    maximo. O modelo esta pedindo mais reforco do que um
                    regulador entrega. Sem o ajuste real (vreg, banda,
                    escalonamento), nao ha como melhorar honestamente.

                    SO VALE COM A TENSAO RUIM, pelo mesmo motivo: com a
                    tensao ja adequada o tape no fim e fato verdadeiro e
                    irrelevante, e o rotulo pertence ao teste que reprovou.

  CARGA_ALTA        a demanda supera a capacidade instalada declarada. Pode
                    ser dado inconsistente da BDGD — a propria base tem ~3%
                    de alimentadores com energia incompativel com a rede.

  TENSAO_BAIXA      subtensao sem nenhuma das explicacoes acima. E o que
                    merece investigacao manual.

  OK                dentro do esperado.

A distincao importa: MODELO_QUEBRADO e CARGA_ALTA sao acionaveis aqui;
REDE_EXTENSA e REGULADOR_SATURADO dependem de dado que a BDGD nao tem e
viram item de solicitacao a distribuidora.
"""

# ---------------------------------------------------------------------------
# REDE_EXTENSA: o limiar tem de sair da BASE, nao da Enel SP — achado 3
# ---------------------------------------------------------------------------
# Estes numeros vieram do censo da Enel SP: mediana de 8,9 km por alimentador,
# p99 de 68 km. Aplicados a Roraima, onde os alimentadores tem 288 a 424 km,
# 4 das 20 subestacoes cairam em REDE_EXTENSA — e a mensagem informava
# "mediana da concessao: 8,9 km", que e falso para aquela base.
#
# A classificacao em si continua defensavel (queda de tensao em alimentador
# de 400 km e fisicamente real e nao e acionavel aqui). O que estava errado
# era comparar uma concessao com a mediana de OUTRA.
#
# Agora `referencia` traz a mediana e o limiar da propria base, calculados em
# `referencia_de`. Os valores abaixo ficam so como piso para quem chamar sem
# referencia — e a mensagem passa a dizer de qual mediana esta falando.
KM_ALIM_ALTO = 60.0
V_BAIXA = 0.90
PERDAS_ALTA = 15.0
USO_ALTO = 90.0

# ---------------------------------------------------------------------------
# TENSAO_IMPLAUSIVEL: o corte de 0,5 pu — achados 1 e 60
# ---------------------------------------------------------------------------
# Este veredicto existia no achado 1 (28/08/2026), sumiu quando o classificador
# graduado dos achados 25 e 29 substituiu o codigo antigo, e voltou em
# 08/09/2026 porque a falta dele foi medida: das 18 subestacoes que continuavam
# `REGULADOR_SATURADO` na V31, cinco tinham tensao mediana ABAIXO de 0,5 pu — a
# pior em 0,109 — e levavam o mesmo rotulo de uma subestacao em 0,90 pu. Um
# rotulo que nao distingue 0,109 de 0,90 nao serve para decidir onde olhar.
#
# A FISICA, que e o que sustenta o corte: carga de potencia constante a 0,08 pu
# puxa ~12x a corrente nominal e a perda joule sobe ~150x. Medido na
# EQUATORIAL6072/5002404 (achado 60): perdas de 12,7 MW sobre 5,1 MW de carga,
# 2,5x. Nao e perda de rede, e uma solucao fora da bacia de operacao — o numero
# dela nao pode entrar em agregado nenhum.
#
# RESSALVA HERDADA DO ACHADO 1, e ela continua valendo: o 0,5 foi calibrado no
# histograma do MINIMO, que e bimodal com vale em 0,45-0,55, e e aplicado sobre
# a MEDIANA, cuja distribuicao nao tem vale. Hoje o corte se defende pela
# fisica, nao pelos dados, e falta o estudo de sensibilidade antes de virar
# numero de artigo.
V_IMPLAUSIVEL = 0.50

# Quantas vezes a mediana da propria base um alimentador precisa ter para ser
# considerado extenso. 60/8,9 = 6,7 na Enel SP, que e de onde sai o fator.
FATOR_EXTENSA = 6.7


def referencia_de(resumos):
    """Mediana e limiar de km por alimentador, medidos NESTA base.

    `resumos` sao os resumo.json das subestacoes. Devolve o dicionario que
    `classificar` espera em `referencia`.
    """
    import statistics
    km = []
    for r in resumos or []:
        alim = max((r or {}).get('alimentadores', 0), 0)
        if alim and (r or {}).get('km_MT'):
            km.append(r['km_MT'] / alim)
    if len(km) < 5:
        return {'km_alim_mediana': None, 'km_alim_alto': KM_ALIM_ALTO,
                'n': len(km)}
    med = statistics.median(km)
    return {'km_alim_mediana': med,
            'km_alim_alto': max(med * FATOR_EXTENSA, 20.0),
            'n': len(km)}


# Fracao da carga sem tensao que separa as tres classes. Os cortes saem da
# distribuicao medida na safra 2025 (achado 25), e nao de gosto: abaixo de 1%
# estao 650 das 1.209 subestacoes afetadas, e acima de 10% estao 269 — os dois
# extremos da mesma cauda, com tratamentos opostos.
SEM_TENSAO_RESSALVA = 0.01    # abaixo disto nao e causa, e nota de rodape
SEM_TENSAO_PARCIAL = 0.10     # acima disto falta parte relevante da rede
SEM_TENSAO_ILHADA = 0.99      # praticamente tudo: a fonte nao alcanca a rede


def classificar(v, resumo, extra=None, referencia=None):
    """`v` = registro do validador; `resumo` = resumo.json da subestacao.

    `referencia` vem de `referencia_de` e carrega a estatistica da base em
    conversao. Sem ela, valem os numeros da Enel SP — e a mensagem diz isso.

    Devolve (causa, detalhe, acionavel)."""
    extra = extra or {}
    ref = referencia or {}
    km_alto = ref.get('km_alim_alto') or KM_ALIM_ALTO
    med_base = ref.get('km_alim_mediana')
    alim = max(resumo.get('alimentadores', 1), 1)
    km_alim = resumo.get('km_MT', 0) / alim
    kw = resumo.get('kW_BT', 0) + resumo.get('kW_MT', 0)
    mva = extra.get('mva_instalado') or 0
    uso = 100 * (kw / 1000) / mva if mva else None
    vmed = v.get('V_MT_mediana')

    if not v.get('compila'):
        return ('MODELO_QUEBRADO', 'nao compila: ' + str(v.get('erro', ''))[:120], True)
    if not v.get('converge'):
        # O QUE A SONDA DO VALIDADOR DESCOBRIU. Ver achado 26: quando o fluxo
        # so fecha com a geracao desligada, o modelo nao esta quebrado — ele
        # esta sendo julgado no instantaneo, que poe toda a GD no maximo junto
        # com a carga de pico. Duas das tres subestacoes examinadas resolvem
        # os 96 passos do dia nesse mesmo modelo.
        if v.get('converge_sem_gd'):
            return ('NAO_CONVERGE_COM_GD',
                    'nao converge em %s iteracoes com a geracao no maximo, e '
                    'converge em %s sem ela (%s geradores) — julgar pelo dia, '
                    'e nao pelo instantaneo'
                    % (v.get('iteracoes'), v.get('iteracoes_sem_gd'),
                       v.get('n_gd')), True)
        return ('MODELO_QUEBRADO', f'nao converge em {v.get("iteracoes")} iteracoes', True)
    if v.get('nos_nan'):
        return ('MODELO_QUEBRADO',
                f'{v["nos_nan"]} nos com NaN em {v.get("barras_nan", "?")} barras '
                f'— ilha sem fonte; no motor da EPRI contamina a rede toda', True)
    # CARGA SEM TENSAO, GRADUADA PELA FRACAO. Ver a doutrina no topo: o numero
    # absoluto nao diz nada sem o denominador — uma carga em dez mil e ramal
    # solto, metade da subestacao e rede que nao fecha, e as duas recebiam o
    # mesmo rotulo.
    mortas = v.get('cargas_sem_tensao') or 0
    n_cargas = v.get('n_cargas') or 0
    if mortas and n_cargas:
        f = mortas / n_cargas
        quanto = f'{mortas} de {n_cargas} cargas sem tensao ({100*f:.2f}%)'
        if f >= SEM_TENSAO_ILHADA:
            return ('SUBESTACAO_ILHADA',
                    f'{quanto} — a fonte nao alcanca a rede', True)
        if f >= SEM_TENSAO_PARCIAL:
            return ('REDE_PARCIAL',
                    f'{quanto} — perda e energia medidas sobre o que sobrou',
                    True)
        if f >= SEM_TENSAO_RESSALVA:
            return ('RAMAIS_SOLTOS',
                    f'{quanto} — trechos de ligacao nao declarados', True)
        # abaixo de 1%: segue para os testes seguintes, sem virar causa
    elif mortas:
        # sem o denominador nao da para graduar, e o conservador e o rotulo
        # antigo — melhor uma classe pessimista do que uma inventada.
        return ('MODELO_QUEBRADO',
                f'{mortas} cargas sem tensao — trecho sem ligacao '
                '(sem contagem total para graduar)', True)

    if vmed is None:
        return ('SEM_MEDIDA', 'nenhuma barra de MT com tensao valida', True)

    # A PERDA QUE VALE E A DO DIA — achado 29. Ver `_perda_do_dia` no
    # `validador.py`: o instantaneo poe toda carga no pico e a perda ohmica vai
    # com o quadrado da corrente, entao ele fica proximo do maximo do dia.
    # Quando a etapa de energia nao rodou, sobra o instantaneo e a mensagem diz
    # de onde o numero veio.
    perda_dia = v.get('perdas_pct_dia')
    perda = perda_dia if perda_dia is not None else v.get('perdas_pct', 0)
    de_onde = 'no dia' if perda_dia is not None else 'no instantaneo'

    if vmed >= V_BAIXA and perda < PERDAS_ALTA:
        return ('OK', '', False)

    # TENSAO IMPLAUSIVEL VEM ANTES DE TUDO O QUE ELA EXPLICA — achados 1 e 60.
    # Abaixo de meio pu a solucao saiu da bacia de operacao: a carga de
    # potencia constante puxa corrente demais, a perda cresce com o quadrado
    # dela, e nenhum numero desta subestacao — perda, energia, carregamento —
    # significa coisa alguma. Vem na frente de CARGA_ALTA, REDE_EXTENSA e
    # REGULADOR_SATURADO de proposito: os tres SAO verdade nesses casos, e os
    # tres descrevem o sintoma no lugar da doenca. Na V31 eram cinco
    # subestacoes rotuladas `REGULADOR_SATURADO` com a tensao entre 0,109 e
    # 0,454 pu, indistinguiveis, pelo rotulo, de uma em 0,90.
    if vmed < V_IMPLAUSIVEL:
        return ('TENSAO_IMPLAUSIVEL',
                f'Vmed={vmed:.3f} pu — abaixo de {V_IMPLAUSIVEL:g} pu a '
                f'carga de potencia constante puxa corrente muito acima da '
                f'nominal e a perda ({perda:.1f}% {de_onde}) mede a propria '
                f'subtensao, nao a rede: nenhum numero desta subestacao entra '
                f'em agregado', True)

    if uso and uso > USO_ALTO:
        return ('CARGA_ALTA',
                f'{kw/1000:.1f} MW sobre {mva:.0f} MVA instalados ({uso:.0f}%)', True)

    # OS DOIS TESTES ABAIXO SO VALEM COM A TENSAO RUIM — achado 62-B.
    #
    # `REDE_EXTENSA` e `REGULADOR_SATURADO` se justificam, os dois, por queda
    # de tensao: um diz que "a queda e fisicamente correta num alimentador
    # desse tamanho", o outro que "o modelo pede mais reforco do que um
    # regulador entrega". Com a tensao mediana ADEQUADA, nenhum dos dois
    # explica coisa alguma — o alimentador e longo e os reguladores estao no
    # fim do tape, mas a tensao chegou. O que falhou foi a perda, e e ela que
    # tem de nomear a subestacao.
    #
    # Medido na V32: 3 das 11 `REDE_EXTENSA` e 5 das 12 `REGULADOR_SATURADO`
    # tinham tensao acima de 0,90 pu. A NEOENERGIA47/SBC estava em **1,036
    # pu** — acima da nominal — carimbada como rede extensa demais para
    # sustentar tensao. As oito passam a `PERDA_ALTA`, que e o teste que elas
    # de fato reprovam; nenhuma vira `OK`, porque a perda continua alta.
    #
    # `CARGA_ALTA` fica de fora desta trava de proposito: ela afirma algo
    # sobre CAPACIDADE, nao sobre tensao, e demanda acima da instalada explica
    # perda alta por si so.
    if vmed < V_BAIXA and km_alim > km_alto:
        origem = (f'mediana desta base: {med_base:.1f} km' if med_base
                  else 'sem censo desta base; limiar da Enel SP, 60 km')
        return ('REDE_EXTENSA',
                f'{km_alim:.0f} km por alimentador ({origem})', False)

    if (vmed < V_BAIXA and extra.get('reg_total')
            and extra.get('reg_saturados') == extra.get('reg_total')):
        return ('REGULADOR_SATURADO',
                f'{extra["reg_total"]} reguladores, todos no tape maximo', False)

    # TENSAO E PERDA SAO PROBLEMAS DIFERENTES, e ate 03/09/2026 tudo o que
    # falhava no teste de `OK` caia em `TENSAO_BAIXA` — inclusive a subestacao
    # com tensao perfeita e perda alta. Medido na V28: **151 das 262
    # rotuladas `TENSAO_BAIXA` tinham tensao mediana ACIMA de 0,90 pu**, ou
    # seja 58% da classe levava um rotulo que nao descrevia o problema dela.
    if vmed < V_BAIXA:
        return ('TENSAO_BAIXA',
                f'Vmed={vmed:.3f} com {km_alim:.0f} km/alim'
                + (f' e {uso:.0f}% de uso' if uso else ''), True)

    # PERDA ALTA SEM CARGA NAO E PERDA ALTA. Subestacao sem consumidor recebe
    # da fonte apenas o ferro dos transformadores, e ai 100% do que entra e
    # perdido — por definicao, e nao por defeito. Medido na V28: das 13
    # subestacoes com perda de 99% ou mais, **10 tem ZERO cargas**.
    if not (v.get('n_cargas') or 0):
        return ('SEM_CARGA',
                f'perda de {perda:.1f}% {de_onde} sobre ZERO cargas — a '
                f'fonte alimenta so o ferro dos transformadores, e o '
                f'percentual nao tem denominador que signifique alguma coisa',
                False)

    return ('PERDA_ALTA',
            f'perdas de {perda:.1f}% {de_onde} com Vmed={vmed:.3f} e '
            f'{km_alim:.0f} km/alim' + (f', {uso:.0f}% de uso' if uso else ''),
            True)


ACIONAVEL = {'MODELO_QUEBRADO', 'SUBESTACAO_ILHADA', 'REDE_PARCIAL',
             'RAMAIS_SOLTOS', 'CARGA_ALTA', 'TENSAO_BAIXA', 'SEM_MEDIDA',
             'NAO_CONVERGE_COM_GD', 'PERDA_ALTA', 'TENSAO_IMPLAUSIVEL'}

# `TENSAO_IMPLAUSIVEL` entra em ACIONAVEL mesmo quando a causa raiz e do
# cadastro (condutor fino demais no achado 60, GD superdimensionada no achado
# 32), e a escolha e deliberada: a acao existe e e NOSSA — nao publicar o
# numero dessa subestacao. `REDE_EXTENSA` fica de fora porque ali a queda e
# fisicamente correta e o numero vale; aqui ele nao vale.

# `SEM_CARGA` fica de fora de proposito: nao ha o que acionar numa subestacao
# que a BDGD declara sem consumidor. E fato do cadastro, e o relatorio o diz.

# As tres classes que nasceram do MODELO_QUEBRADO. Quem comparar uma rodada
# anterior a 02/09/2026 com uma posterior tem de somar estas quatro para
# reproduzir a contagem antiga — a realidade nao mudou, a regua mudou.
SEM_TENSAO = {'SUBESTACAO_ILHADA', 'REDE_PARCIAL', 'RAMAIS_SOLTOS'}
