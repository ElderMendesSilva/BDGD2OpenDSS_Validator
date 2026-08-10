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

# a concessao tem mediana de 8,9 km por alimentador e p99 de 68 km
KM_ALIM_ALTO = 60.0
V_BAIXA = 0.90
PERDAS_ALTA = 15.0
USO_ALTO = 90.0


def classificar(v, resumo, extra=None):
    """`v` = registro do validador; `resumo` = resumo.json da subestacao.

    Devolve (causa, detalhe, acionavel)."""
    extra = extra or {}
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

    if km_alim > KM_ALIM_ALTO:
        return ('REDE_EXTENSA',
                f'{km_alim:.0f} km por alimentador (mediana da concessao: 8,9 km)', False)

    if extra.get('reg_total') and extra.get('reg_saturados') == extra.get('reg_total'):
        return ('REGULADOR_SATURADO',
                f'{extra["reg_total"]} reguladores, todos no tape maximo', False)

    return ('TENSAO_BAIXA',
            f'Vmed={vmed:.3f} perdas={v.get("perdas_pct",0):.1f}% '
            f'com {km_alim:.0f} km/alim' + (f' e {uso:.0f}% de uso' if uso else ''), True)


ACIONAVEL = {'MODELO_QUEBRADO', 'CARGA_ALTA', 'TENSAO_BAIXA', 'SEM_MEDIDA'}
