# -*- coding: utf-8 -*-
"""
CLASSIFICACAO DE CAUSA RAIZ, subestacao por subestacao.

O validador diz QUE esta ruim. Este modulo diz POR QUE, e principalmente
separa o que e defeito do conversor do que e caracteristica da rede — os
dois exigem acoes opostas e confundi-los faz perder tempo.

As causas, na ordem em que sao testadas:

  MODELO_QUEBRADO   nao compila, nao converge, tem carga sem tensao, ou tem
                    no com NaN. E defeito nosso: sempre acionavel.

                    O NaN merece atencao especial porque os dois motores do
                    OpenDSS discordam dele. Na DALP, o mesmo arquivo dava 36
                    nos NaN no DSS C-API (opendssdirect, usado aqui) e 49.857
                    no motor oficial da EPRI (COM v11) — o C-API contem o NaN
                    na ilha que o gerou, o da EPRI propaga pela fatoracao e
                    derruba a rede inteira. Um punhado de nos NaN aqui e um
                    modelo inutilizavel no OpenDSS que o usuario abre. Por
                    isso qualquer NaN e MODELO_QUEBRADO, nao ressalva.

  REDE_EXTENSA      alimentador muito acima do normal da concessao (a
                    mediana e 8,9 km; sete alimentadores passam de 100 km, e
                    dois deles, na DREG, tem 440 e 335 km). Nesses casos a
                    queda de tensao e fisicamente correta e nao ha o que
                    corrigir sem o ajuste de campo dos reguladores.

  REGULADOR_SATURADO  ha regulador na subestacao e todos estao no tape
                    maximo. O modelo esta pedindo mais reforco do que um
                    regulador entrega. Sem o ajuste real (vreg, banda,
                    escalonamento), nao ha como melhorar honestamente.

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
        return ('MODELO_QUEBRADO', f'nao converge em {v.get("iteracoes")} iteracoes', True)
    if v.get('nos_nan'):
        return ('MODELO_QUEBRADO',
                f'{v["nos_nan"]} nos com NaN em {v.get("barras_nan", "?")} barras '
                f'— ilha sem fonte; no motor da EPRI contamina a rede toda', True)
    if v.get('cargas_sem_tensao'):
        return ('MODELO_QUEBRADO',
                f'{v["cargas_sem_tensao"]} cargas sem tensao — trecho sem ligacao', True)

    if vmed is None:
        return ('SEM_MEDIDA', 'nenhuma barra de MT com tensao valida', True)

    if vmed >= V_BAIXA and v.get('perdas_pct', 0) < PERDAS_ALTA:
        return ('OK', '', False)

    if uso and uso > USO_ALTO:
        return ('CARGA_ALTA',
                f'{kw/1000:.1f} MW sobre {mva:.0f} MVA instalados ({uso:.0f}%)', True)

    if km_alim > km_alto:
        origem = (f'mediana desta base: {med_base:.1f} km' if med_base
                  else 'sem censo desta base; limiar da Enel SP, 60 km')
        return ('REDE_EXTENSA',
                f'{km_alim:.0f} km por alimentador ({origem})', False)

    if extra.get('reg_total') and extra.get('reg_saturados') == extra.get('reg_total'):
        return ('REGULADOR_SATURADO',
                f'{extra["reg_total"]} reguladores, todos no tape maximo', False)

    return ('TENSAO_BAIXA',
            f'Vmed={vmed:.3f} perdas={v.get("perdas_pct",0):.1f}% '
            f'com {km_alim:.0f} km/alim' + (f' e {uso:.0f}% de uso' if uso else ''), True)


ACIONAVEL = {'MODELO_QUEBRADO', 'CARGA_ALTA', 'TENSAO_BAIXA', 'SEM_MEDIDA'}
