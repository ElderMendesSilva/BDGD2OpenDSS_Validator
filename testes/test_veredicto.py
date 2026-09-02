# -*- coding: utf-8 -*-
"""O veredicto final de cada subestação.

O que estes testes protegem é a honestidade do selo. Um relatório que carimba
ADEQUADO por ausência de dado é pior do que nenhum relatório, porque parece
conferido — e foi exatamente o que a primeira versão deste módulo fez.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdgd2dss import veredicto as vd                       # noqa: E402


def _bom(**troca):
    """Uma subestação sadia, para variar um campo por vez."""
    v = {'compila': True, 'converge': True, 'resolve': True, 'causa': 'OK',
         'cargas_sem_tensao': 0, 'n_cargas': 1000}
    e = {'perdas_pct': 3.5}
    fdia = {'passos_validos': 96, 'fator_de_carga': 0.6}
    extra = {'pct_fora_faixa': 0.5, 'pct_sobrecarga': 0.0}
    onde = {'v_': v, 'e_': e, 'fdia_': fdia, 'extra_': extra}
    for k, x in troca.items():
        onde[k].update(x)
    return v, e, {}, {}, fdia, extra


class TestClassificacao(unittest.TestCase):

    def test_tudo_passa_da_adequado(self):
        v, e, g, fic, fdia, extra = _bom()
        classe, crits, _f, _s, _n = vd.completo(v, e, g, fic, fdia, extra)
        self.assertEqual(classe, vd.APROVADO)
        self.assertTrue(all(x['resultado'] == vd.PASSA for x in crits))

    def test_nao_converge_reprova_tudo(self):
        v, e, g, fic, fdia, extra = _bom(v_={'converge': False})
        classe, _c, _f, serve, nao = vd.completo(v, e, g, fic, fdia, extra)
        self.assertEqual(classe, vd.REPROVADO)
        self.assertEqual(serve, [])
        self.assertIn('não resolve', ' '.join(nao))

    def test_ausencia_de_medida_nao_e_aprovacao(self):
        """Dois defeitos reais, um em cada direção, moram neste teste.

        O primeiro: campo vazio não estava na lista de falhas, e «Fecha
        eletricamente» dizia «sim» numa base em que a etapa nem rodou. O
        segundo: o módulo procurava um campo `veredicto` que o `validador.py`
        nunca escreveu — ele escreve `compila`, `converge`, `resolve` e
        `causa` — e por isso carimbava INCONCLUSIVO uma base inteiramente
        medida. Ausência de dado e ausência de LEITURA do dado produzem o
        mesmo sintoma e são erros opostos."""
        v, e, g, fic, fdia, extra = _bom()
        for k in ('compila', 'converge', 'resolve', 'causa'):
            v.pop(k, None)
        classe, crits, frase, _s, nao = vd.completo(v, e, g, fic, fdia, extra)
        self.assertEqual(classe, vd.INCONCLUSIVO)
        self.assertEqual(crits[0]['resultado'], vd.SEM_DADO)
        self.assertIn('Não há veredicto', frase)
        self.assertIn('falta medida', ' '.join(nao))

    def test_inconclusivo_nao_e_reprovacao(self):
        """A distinção importa: reprovado é um resultado, inconclusivo é a
        ausência de um."""
        v, e, g, fic, fdia, extra = _bom()
        for k in ('compila', 'converge', 'resolve', 'causa'):
            v.pop(k, None)
        frase = vd.completo(v, e, g, fic, fdia, extra)[2]
        self.assertIn('nem', frase)          # "não é reprovação nem aprovação"

    def test_metade_dos_criterios_sem_dado_tambem_e_inconclusivo(self):
        c = vd.criterios({'compila': True, 'converge': True}, {}, {}, {}, {}, {})
        self.assertEqual(vd.julgar(c), vd.INCONCLUSIVO)

    def test_uma_atencao_da_ressalvas_e_nao_reprova(self):
        v, e, g, fic, fdia, extra = _bom(e_={'perdas_pct': 10.0})
        self.assertEqual(vd.completo(v, e, g, fic, fdia, extra)[0], vd.RESSALVAS)

    def test_falha_num_criterio_nao_eliminatorio_da_uso_restrito(self):
        v, e, g, fic, fdia, extra = _bom(e_={'perdas_pct': 22.0})
        self.assertEqual(vd.completo(v, e, g, fic, fdia, extra)[0], vd.RESTRITO)

    def test_dois_achados_graves_restringem_o_uso(self):
        v, e, g, fic, fdia, extra = _bom()
        anom = [{'gravidade': 'grave'}, {'gravidade': 'grave'}]
        self.assertEqual(
            vd.completo(v, e, g, fic, fdia, extra, anom)[0], vd.RESTRITO)


class TestParaQueServe(unittest.TestCase):

    def test_reprovar_num_criterio_nao_invalida_os_outros(self):
        """Modelo com rede desconectada não serve para medir perda, e continua
        servindo para inspecionar conectividade. Carimbá-lo de inútil joga fora
        trabalho bom."""
        v, e, g, fic, fdia, extra = _bom(
            v_={'cargas_sem_tensao': 300, 'n_cargas': 1000})
        _c, _cr, _f, serve, nao = vd.completo(v, e, g, fic, fdia, extra)
        self.assertTrue(any('auditar' in x for x in serve))
        self.assertTrue(any('perda ou energia' in x for x in nao))

    def test_curva_achatada_proibe_dimensionar_pela_ponta(self):
        v, e, g, fic, fdia, extra = _bom(fdia_={'fator_de_carga': 0.97})
        nao = vd.completo(v, e, g, fic, fdia, extra)[4]
        self.assertTrue(any('ponta' in x for x in nao))

    def test_modelo_sadio_diz_que_nada_restringe_sem_prometer_a_rede(self):
        """A frase tem de separar «o dado é coerente» de «a rede é boa» — é a
        tese do projeto, e é onde um relatório descuidado engana."""
        v, e, g, fic, fdia, extra = _bom()
        nao = vd.completo(v, e, g, fic, fdia, extra)[4]
        self.assertIn('significa que a rede real', ' '.join(nao))

    def test_o_diagnostico_e_sempre_um_uso_valido(self):
        for troca in ({}, {'v_': {'compila': False}}, {'v_': {'converge': False}}):
            v, e, g, fic, fdia, extra = _bom(**troca)
            serve, nao = vd.completo(v, e, g, fic, fdia, extra)[3:]
            self.assertTrue(any('diagnóstico' in x for x in serve + nao))


class TestLimites(unittest.TestCase):

    def test_cada_criterio_publica_o_proprio_limite(self):
        """Sem o limite ao lado, o valor medido não diz se passou, e quem lê
        tem de confiar no selo em vez de conferir."""
        v, e, g, fic, fdia, extra = _bom()
        for x in vd.criterios(v, e, g, fic, fdia, extra):
            self.assertTrue(x['limite'])
            self.assertTrue(x['porque'])

    def test_criterio_invertido_conta_para_o_lado_certo(self):
        # passos: MAIS é melhor, ao contrário de todos os outros
        self.assertEqual(vd._classe(96, (90, 70), invertido=True), vd.PASSA)
        self.assertEqual(vd._classe(80, (90, 70), invertido=True), vd.ATENCAO)
        self.assertEqual(vd._classe(50, (90, 70), invertido=True), vd.FALHA)

    def test_le_os_campos_que_o_validador_escreve_de_verdade(self):
        """Trava o contrato com o `validador.py`. Se ele renomear um campo, é
        aqui que se descobre — e não num PDF carimbado INCONCLUSIVO."""
        c = vd.criterios({'compila': True, 'converge': True, 'resolve': True,
                          'causa': 'OK'}, {}, {}, {}, {}, {})
        self.assertEqual(c[0]['resultado'], vd.PASSA)
        for campo, esperado in (('compila', 'não compila'),
                                ('converge', 'não converge')):
            base = {'compila': True, 'converge': True, 'resolve': True}
            base[campo] = False
            c = vd.criterios(base, {}, {}, {}, {}, {})
            self.assertEqual(c[0]['resultado'], vd.FALHA)
            self.assertEqual(c[0]['valor'], esperado)

    def test_barra_com_nan_reprova_mesmo_convergindo(self):
        c = vd.criterios({'compila': True, 'converge': True, 'barras_nan': 36},
                         {}, {}, {}, {}, {})
        self.assertEqual(c[0]['resultado'], vd.FALHA)
        self.assertIn('36', c[0]['valor'])

    def test_toda_classe_tem_cor(self):
        for c in (vd.APROVADO, vd.RESSALVAS, vd.RESTRITO, vd.REPROVADO,
                  vd.INCONCLUSIVO):
            self.assertIn(c, vd.COR)


if __name__ == '__main__':
    unittest.main()
