# -*- coding: utf-8 -*-
"""Transforma o painel de perdas da ANEEL em `dados/perdas_aneel.csv`.

    python etapas/importar_perdas_aneel.py <exportacao.xlsx>
    python etapas/importar_perdas_aneel.py <exportacao.xlsx> --saida outro.csv

DE ONDE VEM O ARQUIVO DE ENTRADA
--------------------------------
Do painel publico da ANEEL, que e onde o valor POR DISTRIBUIDORA existe como
dado — no relatorio em PDF ele e imagem, e o repositorio oficial recusa
acesso automatizado:

    https://portalrelatorios.aneel.gov.br/luznatarifa/perdasenergias
    -> "Perdas Totais sobre Energia Injetada - Ano Civil"
    -> filtro Ano = <safra>
    -> visual "Perdas Totais sobre Energia Injetada por Distribuidora"
    -> "..." -> Exportar dados -> **Dados subjacentes** -> .xlsx

Tem de ser SUBJACENTES, e nao resumidos: so eles trazem a energia injetada e
a perda em MWh (`EnegiaInj`, `PTecReg`), que deixam recalcular o percentual e
somar o pais. E trazem `idagente`, que e o MESMO codigo que a BDGD usa no nome
do arquivo e em `BASE.DIST` — o casamento sai direto, sem tabela de nomes.

Exportado em 16/09/2026, ano 2025: 51 concessionarias, 614,1 TWh injetados,
45,33 TWh de perda tecnica regulatoria, **7,38%**.

O QUE O ARQUIVO NAO TRAZ
------------------------
**Permissionarias.** A exportacao sai filtrada para concessionarias, e o
filtro e do relatorio, nao do painel. Das 99 bases da safra 2025, 49 sao
permissionarias — cooperativas, em sua maioria — e ficam sem referencia
propria. Em ENERGIA elas pesam pouco; em numero de agentes, sao metade.

POR QUE O CODIGO CORRIGIDO, E OS TRES AGRUPADOS
-----------------------------------------------
`idagente` e o codigo historico; `IdAgenteCorrigido` e o de hoje, que e o da
BDGD (Cemig-D: 49 -> 4950; Energisa Minas Rio: 50 -> 6585). Tres
concessionarias vem AGRUPADAS pela ANEEL com um codigo sintetico, porque sao
concessoes que se fundiram. A BDGD 2025 ja e a concessao unificada, entao o
par e legitimo — conferido por nome e UF, e nao por suposicao.
"""
import argparse
import csv
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join(RAIZ, 'dados', 'perdas_aneel.csv')

# Codigo sintetico da ANEEL -> codigo da BDGD. Ver o cabecalho.
AGRUPADAS = {
    '1000041': ('69', 'CPFL Santa Cruz', 'SP'),
    '1000040': ('5216', 'Energisa Sul-Sudeste', 'SP'),
    '1000042': ('396', 'RGE', 'RS'),
}

_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def ler_xlsx(caminho):
    """As linhas da primeira aba, como listas de texto.

    Biblioteca padrao e nada mais: `.xlsx` e um zip de XML, e o projeto nao
    precisa de `openpyxl` para ler uma planilha por safra.
    """
    z = zipfile.ZipFile(caminho)
    comp = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(_NS + 'si'):
            comp.append(''.join(t.text or '' for t in si.iter(_NS + 't')))
    abas = sorted(n for n in z.namelist()
                  if re.match(r'xl/worksheets/sheet\d+\.xml$', n))
    linhas = []
    for row in ET.fromstring(z.read(abas[0])).iter(_NS + 'row'):
        vals = []
        for c in row.iter(_NS + 'c'):
            v = c.find(_NS + 'v')
            if c.get('t') == 's' and v is not None:
                vals.append(comp[int(v.text)])
            elif c.get('t') == 'inlineStr':
                vals.append(''.join(t.text or '' for t in c.iter(_NS + 't')))
            else:
                vals.append(v.text if v is not None else None)
        linhas.append(vals)
    return linhas


def registros(linhas):
    """As linhas de dado como dicionarios, achando o cabecalho pelo conteudo.

    A exportacao do Power BI poe um bloco de "Filtros aplicados" antes do
    cabecalho; a posicao dele nao e contrato.
    """
    i = next((k for k, l in enumerate(linhas)
              if l and 'EnegiaInj' in l and 'PTecReg' in l), None)
    if i is None:
        raise SystemExit('cabecalho nao encontrado: a exportacao precisa ser '
                         'de DADOS SUBJACENTES (EnegiaInj, PTecReg)')
    cab = linhas[i]
    return [dict(zip(cab, l)) for l in linhas[i + 1:] if l and l[0]]


def tabela(regs):
    """Uma linha por distribuidora, com o codigo da BDGD e o percentual."""
    out = []
    for r in regs:
        inj = float(r['EnegiaInj'] or 0)
        tec = float(r['PTecReg'] or 0)
        if inj <= 0:
            continue
        ide = str(r.get('IdAgenteCorrigido') or r['idagente']).strip()
        nome = r.get("'PwrBI codigosDist'[Distribuidora]") or ''
        uf = r.get('UF') or ''
        if ide in AGRUPADAS:
            ide, nome_esperado, uf_esperada = AGRUPADAS[ide]
            if uf != uf_esperada:
                raise SystemExit(f'agrupada {nome!r} veio com UF {uf}, e o '
                                 f'mapa diz {uf_esperada}: confira AGRUPADAS')
        out.append({
            'agente': ide,
            # EM PORCENTO, como o `referencia.TETO` e o `pct_modelo`.
            'pct': round(100.0 * tec / inj, 4),
            'distribuidora': nome,
            'uf': uf,
            'ano': r.get('Ano') or '',
            'energia_injetada_mwh': round(inj, 3),
            'perda_tecnica_mwh': round(tec, 3),
            'id_aneel': str(r['idagente']).strip(),
        })
    return sorted(out, key=lambda x: int(x['agente']))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('xlsx', help='exportacao de DADOS SUBJACENTES do painel')
    ap.add_argument('--saida', default=SAIDA)
    a = ap.parse_args()

    regs = registros(ler_xlsx(a.xlsx))
    anos = sorted({str(r.get('Ano')) for r in regs})
    if len(anos) != 1:
        raise SystemExit(f'a exportacao mistura anos {anos}: filtre UM ano no '
                         f'painel antes de exportar')
    tab = tabela(regs)
    repetidos = {t['agente'] for t in tab
                 if sum(1 for u in tab if u['agente'] == t['agente']) > 1}
    if repetidos:
        raise SystemExit(f'codigo repetido: {sorted(repetidos)}')

    inj = sum(t['energia_injetada_mwh'] for t in tab)
    tec = sum(t['perda_tecnica_mwh'] for t in tab)
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    with open(a.saida, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(tab[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(tab)
    print(f'{len(tab)} distribuidoras, ano {anos[0]}: '
          f'{inj/1e6:.1f} TWh injetados, {tec/1e6:.2f} TWh de perda tecnica '
          f'regulatoria, {100*tec/inj:.2f}%')
    print(f'-> {os.path.relpath(a.saida, RAIZ)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
