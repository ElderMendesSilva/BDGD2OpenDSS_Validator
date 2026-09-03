# -*- coding: utf-8 -*-
"""A graduação da carga sem tensão — achado 25.

Até 02/09/2026 uma única carga sem tensão carimbava a subestação como
`MODELO_QUEBRADO`, um rótulo que afirma que o modelo está quebrado. Isso
respondia por 96,7% da classe, e 650 das 1.209 afetadas perdiam menos de 1% da
carga.

O que estes testes protegem é a **proporcionalidade**: o rótulo tem de dizer o
que é verdade sobre aquela subestação, e a ação que ele sugere tem de ser a
ação certa. Nomear de quebrado um modelo que perde uma carga em mil manda
alguém depurar o conversor quando o que existe é um ramal não declarado.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import diagnostico as d                      # noqa: E402


def classificar(mortas=0, n_cargas=1000, **troca):
    v = {'compila': True, 'converge': True, 'V_MT_mediana': 1.0,
         'perdas_pct': 2.0, 'cargas_sem_tensao': mortas, 'n_cargas': n_cargas}
    v.update(troca)
    return d.classificar(v, {'alimentadores': 1, 'km_MT': 10})


class TestGraduacao(unittest.TestCase):

    def test_toda_a_carga_morta_e_subestacao_ilhada(self):
        """A rede existe, a fonte existe, e as duas não se tocam."""
        causa, det, acionavel = classificar(1000, 1000)
        self.assertEqual(causa, 'SUBESTACAO_ILHADA')
        self.assertIn('fonte nao alcanca', det)
        self.assertTrue(acionavel)

    def test_acima_de_dez_por_cento_e_rede_parcial(self):
        causa, det, _ = classificar(500, 1000)
        self.assertEqual(causa, 'REDE_PARCIAL')
        self.assertIn('sobrou', det)

    def test_entre_um_e_dez_por_cento_sao_ramais_soltos(self):
        self.assertEqual(classificar(50, 1000)[0], 'RAMAIS_SOLTOS')

    def test_abaixo_de_um_por_cento_nao_vira_causa(self):
        """A subestação segue para os testes seguintes e pode terminar `OK`.

        O número não some — continua em `cargas_sem_tensao` no
        `validacao.json`. O que muda é parar de chamar de quebrado um modelo
        que perde uma carga em mil.
        """
        self.assertEqual(classificar(5, 1000)[0], 'OK')
        self.assertEqual(classificar(1, 5000)[0], 'OK')

    def test_uma_carga_em_dez_nao_escapa_por_ser_pouca_em_absoluto(self):
        """1 de 10 é 10%: o absoluto é minúsculo e a fração é grave.

        É a mesma armadilha do achado 25 ao contrário — lá o denominador
        faltava para não descartar demais, aqui falta para não absolver demais.
        """
        self.assertEqual(classificar(1, 10)[0], 'REDE_PARCIAL')


class TestOsLimitesDaGraduacao(unittest.TestCase):

    def test_os_cortes_sao_os_declarados(self):
        self.assertEqual(d.SEM_TENSAO_RESSALVA, 0.01)
        self.assertEqual(d.SEM_TENSAO_PARCIAL, 0.10)
        self.assertEqual(d.SEM_TENSAO_ILHADA, 0.99)

    def test_exatamente_no_corte_cai_na_classe_mais_grave(self):
        """Fronteira fechada por baixo, e declarada: sem isto o
        comportamento no corte fica dependendo de arredondamento."""
        self.assertEqual(classificar(10, 1000)[0], 'RAMAIS_SOLTOS')    # 1,0%
        self.assertEqual(classificar(100, 1000)[0], 'REDE_PARCIAL')    # 10,0%
        self.assertEqual(classificar(990, 1000)[0], 'SUBESTACAO_ILHADA')  # 99%

    def test_a_fracao_aparece_no_detalhe(self):
        """Quem lê o veredicto tem de ver o número que o produziu, senão o
        rótulo é uma opinião."""
        for m, n in ((50, 1000), (500, 1000), (1000, 1000)):
            self.assertIn('%d de %d' % (m, n), classificar(m, n)[1])


class TestOQueNaoMudou(unittest.TestCase):

    def test_modelo_quebrado_guarda_as_falhas_de_verdade(self):
        """41 subestações do país, e nenhuma delas por carga sem tensão."""
        self.assertEqual(classificar(compila=False)[0], 'MODELO_QUEBRADO')
        self.assertEqual(classificar(converge=False)[0], 'MODELO_QUEBRADO')
        self.assertEqual(classificar(nos_nan=36)[0], 'MODELO_QUEBRADO')

    def test_falha_de_modelo_tem_precedencia_sobre_a_graduacao(self):
        """Não converge com metade da carga morta é «não converge»: os
        números de um fluxo que não fechou não sustentam classificação."""
        self.assertEqual(classificar(500, 1000, converge=False)[0],
                         'MODELO_QUEBRADO')

    def test_sem_o_denominador_volta_ao_rotulo_pessimista(self):
        """Sem `n_cargas` não dá para graduar, e uma classe pessimista é
        melhor do que uma inventada."""
        causa, det, _ = classificar(3, None)
        self.assertEqual(causa, 'MODELO_QUEBRADO')
        self.assertIn('sem contagem total', det)

    def test_as_novas_classes_sao_acionaveis(self):
        for c in ('SUBESTACAO_ILHADA', 'REDE_PARCIAL', 'RAMAIS_SOLTOS'):
            self.assertIn(c, d.ACIONAVEL)

    def test_o_conjunto_de_migracao_esta_declarado(self):
        """Quem comparar uma rodada velha com uma nova precisa somar estas
        quatro para reproduzir a contagem antiga — a realidade não mudou, a
        régua mudou, e isso tem de estar no código e não numa lembrança."""
        self.assertEqual(d.SEM_TENSAO,
                         {'SUBESTACAO_ILHADA', 'REDE_PARCIAL', 'RAMAIS_SOLTOS'})



class TestNaoConvergeComGD(unittest.TestCase):
    """Achado 26: o instantâneo põe TODA a geração no máximo junto com a carga
    de pico, e essa combinação não ocorre no dia.

    Medido em três subestações de três distribuidoras: desligar os PVSystem faz
    o fluxo fechar em 44 a 59 iterações, e **duas delas resolvem os 96 passos
    do dia** no mesmo modelo. Reprovar pelo instantâneo condena rede que roda.
    """

    def _nc(self, **troca):
        v = {'compila': True, 'converge': False, 'iteracoes': 500,
             'V_MT_mediana': 1.0}
        v.update(troca)
        return d.classificar(v, {'alimentadores': 1, 'km_MT': 10})

    def test_sem_a_sonda_continua_sendo_modelo_quebrado(self):
        """A classe nova exige EVIDÊNCIA. Sem a medida sem-GD não há o que
        afirmar, e o rótulo conservador é o certo."""
        self.assertEqual(self._nc()[0], 'MODELO_QUEBRADO')

    def test_com_a_sonda_positiva_vira_classe_propria(self):
        causa, det, acionavel = self._nc(converge_sem_gd=True,
                                         iteracoes_sem_gd=54, n_gd=1237)
        self.assertEqual(causa, 'NAO_CONVERGE_COM_GD')
        self.assertIn('54', det)
        self.assertIn('1237', det)
        self.assertTrue(acionavel)

    def test_sonda_negativa_nao_absolve(self):
        """Se nem sem GD converge, o problema é outro e o rótulo antigo vale."""
        self.assertEqual(self._nc(converge_sem_gd=False, n_gd=1237)[0],
                         'MODELO_QUEBRADO')

    def test_o_detalhe_manda_julgar_pelo_dia(self):
        """A frase é o produto: sem ela o rótulo novo seria só um sinônimo."""
        self.assertIn('julgar pelo dia',
                      self._nc(converge_sem_gd=True, iteracoes_sem_gd=59,
                               n_gd=603)[1])

    def test_a_classe_nova_e_acionavel(self):
        self.assertIn('NAO_CONVERGE_COM_GD', d.ACIONAVEL)

if __name__ == '__main__':
    unittest.main()
