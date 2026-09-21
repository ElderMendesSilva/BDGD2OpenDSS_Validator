# -*- coding: utf-8 -*-
"""A perda nao cabe na energia que entra — achado 67.

O QUE CUSTOU. Na V34, a ENERGISA_M405 publicou 26,50% de perda no dia contra
8,78% da ANEEL — tres vezes o que a distribuidora inteira perde. Uma unica
subestacao, a `65`, fazia isso: 3.882 MWh de perda sobre 264 MWh injetados,
1.471%. Sem ela, a base dava 4,16%.

Reproduzido localmente: o instantaneo parou em 500 iteracoes sem convergir, e
o modo diario HERDOU o estado. Cada passo "convergia" em 2 iteracoes sem sair
do lugar — 161.760 kW de perda para 5.349 kW entrando, identicos nos 96 passos
enquanto a GD ia de 0 a 17.842 kW. `Converged()` dizia sim a todos.

O guarda do achado 64 so barrava GD acima da placa. Este e mais geral e nao
tem limiar escolhido: e conservacao de energia. Num passo, o circuito nao
dissipa mais do que a fonte e a GD entregam juntas.

E A SEGUNDA METADE. O `validador` ja recusava dia parcial; o `valida_perdas` e
o `valida_balanco` liam o mesmo arquivo e somavam tudo. A regra passou a
morar num lugar so, `bdgd2dss/dia.py`, e os tres a chamam.
"""
import io
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from bdgd2dss import dia                                   # noqa: E402


def _fonte(*partes):
    return io.open(os.path.join(RAIZ, *partes), encoding='utf-8').read()


class TestOGuardaFisico(unittest.TestCase):

    def setUp(self):
        self.fonte = _fonte('etapas', 'energia.py')

    def test_existe_e_compara_perda_com_a_entrada(self):
        self.assertIn('if L > max(-p + gd, 0.0) + 1e-6:', self.fonte)

    def test_o_passo_e_rejeitado_e_contado(self):
        i = self.fonte.index('if L > max(-p + gd, 0.0) + 1e-6:')
        bloco = self.fonte[i:i + 400]
        self.assertIn('fisica_impossivel.append(k)', bloco)
        self.assertIn('falhos.append(k)', bloco)
        self.assertIn('continue', bloco)
        # achado 71: reprovar sem limpar o estado so adia a falha
        self.assertIn('compila()', bloco)

    def test_vem_antes_de_somar_a_energia(self):
        """Rejeitar DEPOIS de somar nao adianta: o dia ja estaria sujo."""
        self.assertLess(self.fonte.index('if L > max(-p + gd, 0.0) + 1e-6:'),
                        self.fonte.index('ent += (-p + gd) * h_passo'))

    def test_vem_antes_dos_medidores_por_alimentador(self):
        """Sem isso, o alimentador somaria o passo impossivel mesmo com a
        subestacao recusando — e o `valida_perdas` le o alimentador."""
        self.assertLess(self.fonte.index('if L > max(-p + gd, 0.0) + 1e-6:'),
                        self.fonte.index("dss.Text.Command('Reset Meters')"))

    def test_a_contagem_chega_ao_json(self):
        self.assertIn("serie['passos_fisica_impossivel'] = fisica_impossivel",
                      self.fonte)
        self.assertEqual(self.fonte.count("'passos_fisica_impossivel':"), 2,
                         'os dois caminhos que gravam a subestacao')


class TestODiaCompleto(unittest.TestCase):

    def test_todos_os_passos(self):
        self.assertTrue(dia.completo({'passos': 96, 'passos_ok': 96}))

    def test_um_passo_a_menos_ja_nao_e_o_dia(self):
        self.assertFalse(dia.completo({'passos': 96, 'passos_ok': 95}))

    def test_o_caso_da_M405(self):
        """96 passos, todos recusados pelo guarda fisico."""
        self.assertFalse(dia.completo({'passos': 96, 'passos_ok': 0}))

    def test_sem_passos_nao_e_medida(self):
        """`0 >= 0` era verdadeiro na regra antiga do validador."""
        self.assertFalse(dia.completo({'passos': 0, 'passos_ok': 0}))
        self.assertFalse(dia.completo({}))
        self.assertFalse(dia.completo(None))

    def test_medidas_separa_e_conta(self):
        dentro, fora = dia.medidas([
            {'se': 'A', 'passos': 96, 'passos_ok': 96},
            {'se': 'B', 'passos': 96, 'passos_ok': 80},
            {'se': 'C', 'passos': 96, 'passos_ok': 0},
        ])
        self.assertEqual([x['se'] for x in dentro], ['A'])
        self.assertEqual(fora, 2)

    def test_medidas_de_nada(self):
        self.assertEqual(dia.medidas([]), ([], 0))
        self.assertEqual(dia.medidas(None), ([], 0))


class TestOsTresLeitores(unittest.TestCase):
    """A regra mora num lugar so, e os tres a chamam."""

    def test_o_validador(self):
        f = _fonte('etapas', 'validador.py')
        self.assertIn('dia.completo(x)', f)
        self.assertNotIn("completo = (x.get('passos_ok') or 0)", f,
                         'a copia local da regra voltou')

    def test_o_valida_perdas(self):
        f = _fonte('etapas', 'valida_perdas.py')
        self.assertIn('dia.medidas(json.load(', f)

    def test_o_valida_balanco(self):
        f = _fonte('etapas', 'valida_balanco.py')
        self.assertIn('dia.medidas(json.load(', f)

    def test_nenhum_leitor_soma_o_arquivo_cru(self):
        """Quem le `energia_dia.json` para AGREGAR tem de passar pelo filtro."""
        for arq in ('valida_perdas.py', 'valida_balanco.py'):
            f = _fonte('etapas', arq)
            self.assertNotIn("modelo = json.load(open(arq, encoding='utf-8'))",
                             f, arq)


if __name__ == '__main__':
    unittest.main()
