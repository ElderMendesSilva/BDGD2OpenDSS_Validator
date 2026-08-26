# -*- coding: utf-8 -*-
"""O coletor que publica `resultados/<sufixo>/` — o canal de dados entre as
duas maquinas.

POR QUE ELE EXISTE. `logs/` e `MODELOS*/` estao no `.gitignore`, e devem
estar: sao gigabytes e se refazem do `.gdb`. Mas a maquina que nao alcanca o
cluster fica sem numero nenhum — le no diario que a Cemig viola 11,12% e nao
consegue perguntar QUAIS alimentadores. O `auditoria.py` colhe a rodada e
grava o que **entra no git**: kilobytes que nao se refazem sem o cluster.

MEDIDO na V19 local, as sete bases:

    base    SEs   sadias  nao conv   viola   %viola     KB
    CMIG    413      408         5      15    0,82%    164
    CPFL    265      265         0      13    0,86%    102
    ENCE    129      129         0       1    0,15%     50
    EQPA    119      119         0       1    0,16%     47
    LT       94       92         0       1    0,07%     38
    RR       20       20         0       3    3,75%     10
    SP      155      155         0      43    2,73%     66

**478 KB para as sete bases inteiras**, contra os gigabytes de `MODELOS_*`.

E as 77 violacoes, classificadas: 32 `no limite`, 27 `perda modelada absurda`,
6 `medida quase sem perda`, **12 `a investigar`**. Doze e uma lista que uma
pessoa trabalha; setenta e sete nao e.

O QUE ESTES TESTES TRANCAM

1. **O `motivo` classifica, e a ORDEM dos ramos e a classificacao.** Uma linha
   que e ao mesmo tempo `modelo > 15%` e `razao < 1,2` tem de sair como `no
   limite`: modelo a 11% do total medido descreve um alimentador que perde
   muito de verdade, e chamar isso de perda absurda manda alguem caçar defeito
   que nao existe.

2. **Rodada incompleta nao derruba o coletor.** Ele roda DEPOIS de uma rodada
   de cluster, e rodada de cluster morre no meio — as 90 bases que morreram no
   minuto 1 em 25/08 sao o precedente. Faltar `validacao_balanco.json` tem de
   dar base sem violacao, e nao um traceback.

3. **O teto de tamanho avisa.** O desenho inteiro e "cabe em kilobytes"; se um
   arquivo passa de 1 MB, a granularidade esta errada e isso tem de aparecer,
   nao ser gravado em silencio.

4. **A ordem das colunas do CSV e estavel.** E o que permite `diff` entre duas
   rodadas. Derivar do dicionario deixaria a ordem ao acaso.
"""
import csv
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import auditoria as au        # noqa: E402


class OMotivoClassifica(unittest.TestCase):

    def test_faturado_maior_que_injetado_vem_primeiro(self):
        m = au.motivo_da_violacao({'faturado_maior_que_injetado': True,
                                   'medida_degenerada': True,
                                   'pct_tecnica_modelo': 90.0,
                                   'pct_total_medido': 1.0})
        self.assertIn('invertida', m)

    def test_degenerada_antes_de_julgar_o_modelo(self):
        m = au.motivo_da_violacao({'medida_degenerada': True,
                                   'pct_tecnica_modelo': 90.0,
                                   'pct_total_medido': 1.0})
        self.assertEqual(m, 'medida degenerada')

    def test_denominador_minusculo(self):
        m = au.motivo_da_violacao({'GWh_injetado': 0.01,
                                   'pct_tecnica_modelo': 50.0,
                                   'pct_total_medido': 5.0})
        self.assertIn('denominador minusculo', m)

    def test_no_limite_ganha_de_perda_absurda(self):
        """O caso que a ordem existe para resolver: modelo 20% contra medido
        18% e um alimentador que perde muito, e nao um modelo quebrado."""
        m = au.motivo_da_violacao({'GWh_injetado': 20.0,
                                   'pct_tecnica_modelo': 20.0,
                                   'pct_total_medido': 18.0})
        self.assertTrue(m.startswith('no limite'), m)

    def test_perda_absurda_quando_a_razao_e_grande(self):
        m = au.motivo_da_violacao({'GWh_injetado': 20.0,
                                   'pct_tecnica_modelo': 51.5,
                                   'pct_total_medido': 6.8})
        self.assertTrue(m.startswith('perda modelada absurda'), m)

    def test_medida_quase_sem_perda(self):
        m = au.motivo_da_violacao({'GWh_injetado': 20.0,
                                   'pct_tecnica_modelo': 11.7,
                                   'pct_total_medido': 2.0})
        self.assertTrue(m.startswith('medida quase sem perda'), m)

    def test_a_investigar_e_o_que_sobra(self):
        """O rotulo que se quer POUCO — foram 12 das 77 na V19."""
        m = au.motivo_da_violacao({'GWh_injetado': 20.0,
                                   'pct_tecnica_modelo': 4.18,
                                   'pct_total_medido': 3.28})
        self.assertEqual(m, 'a investigar')

    def test_campo_ausente_nao_derruba(self):
        for v in ({}, {'pct_tecnica_modelo': None},
                  {'pct_total_medido': 'x', 'GWh_injetado': ''},
                  {'pct_total_medido': 0.0, 'pct_tecnica_modelo': 5.0}):
            self.assertIsInstance(au.motivo_da_violacao(v), str)


class _Rodada:
    """Uma rodada minima em disco: a pasta MODELOS_<TAG>_<SUFIXO>."""

    def __init__(self, tag='XX', sufixo='TESTE', **arquivos):
        self.raiz = tempfile.mkdtemp()
        self.pasta = os.path.join(self.raiz, f'MODELOS_{tag}_{sufixo}')
        os.makedirs(self.pasta)
        for nome, dado in arquivos.items():
            with open(os.path.join(self.pasta, nome + '.json'), 'w',
                      encoding='utf-8') as fh:
                json.dump(dado, fh)


def _balanco(ctmt, sub='S1', **kw):
    d = {'ctmt': ctmt, 'sub': sub, 'GWh_injetado': 20.0, 'GWh_faturado': 18.0,
         'ucs': 100, 'pct_total_medido': 5.0, 'pct_tecnica_modelo': 30.0,
         'pct_nao_tecnica_implicita': -25.0, 'cobertura': 600.0,
         'viola_limite': True, 'medida_degenerada': False,
         'faturado_maior_que_injetado': False, 'viola_de_verdade': True}
    d.update(kw)
    return d


class OQueSaiEmDisco(unittest.TestCase):

    def _colhe(self, r, tag='XX', sufixo='TESTE'):
        saida = os.path.join(r.raiz, 'resultados')
        au.main(['--sufixo', sufixo, '--raiz', r.raiz, '--saida', saida])
        d = os.path.join(saida, sufixo.lower())
        return d

    def test_tres_arquivos_por_rodada(self):
        r = _Rodada(validacao_balanco=[_balanco('A1')],
                    resumo_geral=[{'SE': 'S1', 'trafos': 10}],
                    validacao=[{'modelo': 'S1', 'converge': True}])
        d = self._colhe(r)
        for f in ('XX.json', 'XX_violacoes.csv', '_indice.json'):
            self.assertTrue(os.path.exists(os.path.join(d, f)), f)

    def test_so_o_que_viola_de_verdade_entra_no_csv(self):
        """`viola_limite` sozinho nao basta: medida degenerada produz violacao
        falsa, e foi por isso que o `valida_balanco` separou os dois."""
        r = _Rodada(validacao_balanco=[
            _balanco('VIOLA'),
            _balanco('SO_LIMITE', viola_de_verdade=False),
            _balanco('LIMPO', viola_limite=False, viola_de_verdade=False)])
        with open(os.path.join(self._colhe(r), 'XX_violacoes.csv'),
                  encoding='utf-8') as fh:
            linhas = list(csv.DictReader(fh))
        self.assertEqual([x['ctmt'] for x in linhas], ['VIOLA'])

    def test_o_pior_caso_vem_primeiro(self):
        """Quem abre o CSV quer o pior na primeira linha, e nao a ordem em que
        a rodada calhou de gravar."""
        r = _Rodada(validacao_balanco=[
            _balanco('MEDIO', pct_tecnica_modelo=20.0),
            _balanco('PIOR', pct_tecnica_modelo=51.5),
            _balanco('MENOR', pct_tecnica_modelo=8.0)])
        with open(os.path.join(self._colhe(r), 'XX_violacoes.csv'),
                  encoding='utf-8') as fh:
            linhas = list(csv.DictReader(fh))
        self.assertEqual([x['ctmt'] for x in linhas],
                         ['PIOR', 'MEDIO', 'MENOR'])

    def test_a_ordem_das_colunas_e_estavel(self):
        r = _Rodada(validacao_balanco=[_balanco('A1')])
        with open(os.path.join(self._colhe(r), 'XX_violacoes.csv'),
                  encoding='utf-8') as fh:
            cab = next(csv.reader(fh))
        self.assertEqual(cab, au.COLUNAS)
        self.assertEqual(cab[:4], ['base', 'sub', 'ctmt', 'motivo'],
                         'as quatro que identificam a linha vem primeiro')

    def test_rodada_incompleta_nao_derruba(self):
        """As 90 bases que morreram no minuto 1 em 25/08 sao o precedente: o
        coletor roda DEPOIS, e pode nao achar metade dos arquivos."""
        r = _Rodada()                       # pasta vazia, nenhum JSON
        d = self._colhe(r)
        resumo = json.load(open(os.path.join(d, 'XX.json'), encoding='utf-8'))
        self.assertEqual(resumo['balanco']['viola_de_verdade'], 0)
        self.assertEqual(resumo['rollup']['ses'], 0)
        self.assertIsNone(resumo['balanco']['pct_viola'])

    def test_json_quebrado_e_tratado_como_ausente(self):
        r = _Rodada(validacao_balanco=[_balanco('A1')])
        with open(os.path.join(r.pasta, 'validacao.json'), 'w',
                  encoding='utf-8') as fh:
            fh.write('{isto nao e json')
        d = self._colhe(r)
        self.assertTrue(os.path.exists(os.path.join(d, 'XX.json')))

    def test_o_rollup_soma_os_achados_da_rede(self):
        """`chaves_ilhadas`, `reguladores_pendurados` e
        `trafos_pac_invertido` sao o que a outra maquina procura sem ter o
        modelo. Se nao subirem para o rollup, ela nao os ve."""
        r = _Rodada(resumo_geral=[
            {'SE': 'S1', 'chaves_ilhadas': 2, 'reguladores_pendurados': 3,
             'trafos_pac_invertido': 9, 'trafos': 100},
            {'SE': 'S2', 'chaves_ilhadas': 1, 'reguladores_pendurados': 0,
             'trafos_pac_invertido': 4, 'trafos': 50}])
        resumo = json.load(open(os.path.join(self._colhe(r), 'XX.json'),
                                encoding='utf-8'))
        rol = resumo['rollup']
        self.assertEqual(rol['chaves_ilhadas'], 3)
        self.assertEqual(rol['reguladores_pendurados'], 3)
        self.assertEqual(rol['trafos_pac_invertido'], 13)
        self.assertEqual(rol['trafos'], 150)

    def test_o_indice_lista_as_bases(self):
        r = _Rodada(validacao_balanco=[_balanco('A1')])
        i = json.load(open(os.path.join(self._colhe(r), '_indice.json'),
                           encoding='utf-8'))
        self.assertEqual(i['sufixo'], 'TESTE')
        self.assertEqual([b['base'] for b in i['bases']], ['XX'])

    def test_por_motivo_conta_por_CLASSE(self):
        """`denominador minusculo: 0,003 GWh` e `... 0,014 GWh` sao o mesmo
        motivo. Contar pelo texto inteiro faria cada linha virar sua propria
        categoria, e o resumo nao resumiria nada."""
        r = _Rodada(validacao_balanco=[
            _balanco('A', pct_tecnica_modelo=51.5, pct_total_medido=6.8),
            _balanco('B', pct_tecnica_modelo=23.7, pct_total_medido=2.3)])
        resumo = json.load(open(os.path.join(self._colhe(r), 'XX.json'),
                                encoding='utf-8'))
        self.assertEqual(sum(resumo['balanco']['por_motivo'].values()), 2)
        for chave in resumo['balanco']['por_motivo']:
            self.assertNotIn(':', chave, 'contou pelo texto com o numero')


class AcharAsPastasDaRodada(unittest.TestCase):

    def test_casa_sem_diferenciar_maiuscula(self):
        """A rodada do cluster grava `V1_cluster` e o resumo dela ja usa
        minuscula. Exigir igualdade exata faria o coletor nao achar a propria
        rodada."""
        r = _Rodada(tag='CMIG', sufixo='V1_cluster')
        for pedido in ('V1_cluster', 'v1_cluster', 'V1_CLUSTER'):
            achadas = au.pastas_da_rodada(pedido, r.raiz)
            self.assertEqual([t for t, _ in achadas], ['CMIG'], pedido)

    def test_nao_confunde_sufixos_diferentes(self):
        """`V1` nao pode arrastar `V19`, senao duas rodadas viram uma."""
        r = _Rodada(tag='RR', sufixo='V19')
        os.makedirs(os.path.join(r.raiz, 'MODELOS_RR_V1'))
        self.assertEqual([t for t, _ in au.pastas_da_rodada('V1', r.raiz)],
                         ['RR'])
        self.assertEqual(len(au.pastas_da_rodada('V19', r.raiz)), 1)

    def test_tag_com_underline_no_nome(self):
        """`MODELOS_<TAG>_<SUFIXO>` com TAG contendo `_` — o regex e guloso do
        lado errado se nao for cuidadoso."""
        r = _Rodada(tag='EQ_PA', sufixo='V1_cluster')
        self.assertEqual([t for t, _ in au.pastas_da_rodada('V1_cluster',
                                                            r.raiz)],
                         ['EQ_PA'])

    def test_sufixo_inexistente_devolve_vazio(self):
        r = _Rodada(tag='RR', sufixo='V19')
        self.assertEqual(au.pastas_da_rodada('V99', r.raiz), [])


class OTetoDeTamanho(unittest.TestCase):
    """O desenho inteiro e "cabe em kilobytes". As sete bases da V19 deram
    478 KB somadas; se algo passar de 1 MB, a granularidade esta errada."""

    def test_o_teto_existe_e_e_de_um_mega(self):
        self.assertEqual(au.TETO_MB, 1.0)

    def test_arquivo_grande_gera_aviso(self):
        avisos = []
        tmp = tempfile.mkdtemp()
        gordo = {'x': ['a' * 1000 for _ in range(1200)]}
        au._grava_json(os.path.join(tmp, 'g.json'), gordo, avisos)
        self.assertEqual(len(avisos), 1)
        self.assertIn('granularidade', avisos[0])

    def test_arquivo_pequeno_nao_gera_aviso(self):
        avisos = []
        tmp = tempfile.mkdtemp()
        au._grava_json(os.path.join(tmp, 'p.json'), {'x': 1}, avisos)
        self.assertEqual(avisos, [])


if __name__ == '__main__':
    unittest.main()
