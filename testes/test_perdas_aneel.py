# -*- coding: utf-8 -*-
"""A referencia externa por distribuidora: o arquivo, e como ele se le.

POR QUE EXISTE. Desde a V18 o projeto tinha o encaixe para comparar a perda
do modelo com a perda tecnica regulatoria DA PROPRIA distribuidora, e o
arquivo nunca existiu. Toda comparacao rodava contra a media nacional, que so
consegue reprovar — e o vies de 1,42x entre a nossa perda e a declarada
ficava sem dono.

Em 16/09/2026 o arquivo passou a existir, exportado dos DADOS SUBJACENTES do
painel publico da ANEEL: 51 concessionarias, safra 2025, 7,38% de perda
tecnica sobre 614,1 TWh injetados. 50 das 99 bases tem referencia propria; as
49 restantes sao permissionarias, que a exportacao nao traz.
"""
import csv
import io
import os
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))

from bdgd2dss import referencia as ref                     # noqa: E402
import importar_perdas_aneel as imp                        # noqa: E402

CSV = os.path.join(RAIZ, 'dados', 'perdas_aneel.csv')


def _linhas():
    with open(CSV, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


class TestOArquivo(unittest.TestCase):

    def test_existe_e_tem_as_concessionarias(self):
        self.assertTrue(os.path.exists(CSV), 'dados/perdas_aneel.csv sumiu')
        self.assertEqual(len(_linhas()), 51)

    def test_um_codigo_por_linha(self):
        cods = [l['agente'] for l in _linhas()]
        self.assertEqual(len(cods), len(set(cods)))

    def test_o_percentual_e_a_razao_dos_mwh(self):
        """O `pct` nao e copiado de um grafico: sai da perda sobre a energia
        injetada, que estao na mesma linha."""
        for l in _linhas():
            inj = float(l['energia_injetada_mwh'])
            tec = float(l['perda_tecnica_mwh'])
            self.assertAlmostEqual(float(l['pct']), 100 * tec / inj,
                                   places=3, msg=l['distribuidora'])

    def test_o_pais_soma_os_738(self):
        ls = _linhas()
        inj = sum(float(l['energia_injetada_mwh']) for l in ls)
        tec = sum(float(l['perda_tecnica_mwh']) for l in ls)
        self.assertAlmostEqual(100 * tec / inj, ref.ANEEL_2025['tecnica_pct'],
                               places=2)

    def test_o_percentual_e_plausivel(self):
        """Perda tecnica de distribuidora fica entre poucos % e ~15%. Fora
        disso, o arquivo foi exportado ou lido errado."""
        for l in _linhas():
            self.assertGreater(float(l['pct']), 2.0, l['distribuidora'])
            self.assertLess(float(l['pct']), 16.0, l['distribuidora'])

    def test_as_tres_agrupadas_viram_o_codigo_da_bdgd(self):
        t = ref.por_distribuidora(CSV)
        for cod in ('69', '5216', '396'):
            self.assertIn(cod, t, f'agrupada {cod} sem par')
        for sintetico in imp.AGRUPADAS:
            self.assertNotIn(sintetico, t)

    def test_o_codigo_e_o_corrigido_e_nao_o_historico(self):
        """Cemig-D e 49 no historico e 4950 na BDGD."""
        t = ref.por_distribuidora(CSV)
        self.assertIn('4950', t)
        self.assertNotIn('49', t)


class TestALeituraPorSafra(unittest.TestCase):

    def test_o_ano_do_arquivo_passa(self):
        self.assertEqual(len(ref.por_distribuidora(CSV, ano=2025)), 51)

    def test_outro_ano_nao_passa(self):
        """Comparar a safra 2024 com a perda de 2025 mede o ano, e nao o
        modelo."""
        self.assertEqual(ref.por_distribuidora(CSV, ano=2024), {})

    def test_a_distribuidora_vence_a_media(self):
        c = ref.comparar(6.0, agente='390', ano=2025)
        self.assertTrue(c['de_agente'])
        self.assertAlmostEqual(c['referencia_pct'], 5.0521, places=3)
        self.assertTrue(c['reprova'], 'Enel SP perde 5,05%; 6% em MT reprova')

    def test_agente_sem_linha_cai_na_media_da_safra(self):
        c = ref.comparar(6.0, agente='5381', ano=2025)   # Cedrap, permissionaria
        self.assertFalse(c['de_agente'])
        self.assertEqual(c['referencia_pct'], ref.ANEEL_2025['tecnica_pct'])

    def test_a_ancora_segue_a_safra(self):
        self.assertEqual(ref.ancora(2024)['tecnica_pct'], 7.4)
        self.assertEqual(ref.ancora('2025')['tecnica_pct'], 7.38)
        self.assertEqual(ref.ancora(None)['ano'], ref.SAFRA)
        self.assertEqual(ref.ancora(1999)['ano'], ref.SAFRA)


def _xlsx(linhas):
    """Uma planilha minima no formato da exportacao do Power BI."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'x.xlsx')
    comp, idx = [], {}

    def s(v):
        if v not in idx:
            idx[v] = len(comp)
            comp.append(v)
        return idx[v]

    rows = []
    for i, l in enumerate(linhas, 1):
        cs = ''.join(f'<c t="s"><v>{s(str(v))}</v></c>' for v in l)
        rows.append(f'<row r="{i}">{cs}</row>')
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('xl/sharedStrings.xml',
                   f'<sst xmlns="{ns}">' + ''.join(
                       f'<si><t>{v}</t></si>' for v in comp) + '</sst>')
        z.writestr('xl/worksheets/sheet1.xml',
                   f'<worksheet xmlns="{ns}"><sheetData>{"".join(rows)}'
                   f'</sheetData></worksheet>')
    return p


CAB = ["'PwrBI codigosDist'[Distribuidora]", 'idagente', 'UF', 'Ano',
       'EnegiaInj', 'PTecReg', 'IdAgenteCorrigido']


class TestOImportador(unittest.TestCase):

    def test_acha_o_cabecalho_depois_dos_filtros(self):
        p = _xlsx([['Filtros aplicados: Ano 2025'], [''], CAB,
                   ['Cemig-D', '49', 'MG', '2025', '1000', '80', '4950']])
        regs = imp.registros(imp.ler_xlsx(p))
        t = imp.tabela(regs)
        self.assertEqual(t[0]['agente'], '4950')
        self.assertAlmostEqual(t[0]['pct'], 8.0)

    def test_recusa_exportacao_resumida(self):
        """Sem `EnegiaInj` e `PTecReg` nao ha como recalcular — e o
        percentual resumido do visual e o que se recusa a copiar."""
        p = _xlsx([['Distribuidora', 'Perda Tecnica'], ['X', '0.08']])
        with self.assertRaises(SystemExit):
            imp.registros(imp.ler_xlsx(p))

    def test_agrupada_com_uf_trocada_para(self):
        p = _xlsx([CAB, ['RGE (agrupada)', '1000042', 'SP', '2025', '10',
                         '1', '1000042']])
        with self.assertRaises(SystemExit):
            imp.tabela(imp.registros(imp.ler_xlsx(p)))

    def test_distribuidora_sem_energia_fica_de_fora(self):
        p = _xlsx([CAB, ['X', '1', 'SP', '2025', '0', '0', '1']])
        self.assertEqual(imp.tabela(imp.registros(imp.ler_xlsx(p))), [])


if __name__ == '__main__':
    unittest.main()
