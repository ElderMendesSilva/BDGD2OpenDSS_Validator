# -*- coding: utf-8 -*-
"""A CADEIA INTEIRA roda, de ponta a ponta, sobre uma .gdb de verdade.

    converter -> verifica -> validador

POR QUE ISTO FALTAVA E POR QUE DOI. Os outros testes sao de unidade e de
modulo: cada peca provada isolada, com a BDGD falsa em memoria. Nenhum
exercitava o `converter.py` de verdade — e a `.gdb` minima nem tinha `CRVCRG`,
entao o caminho de producao nunca era percorrido por teste nenhum.

O CUSTO DE NAO TER: a safra 2025-12-31 da ANEEL saiu. Sem este teste, uma
camada que mudou de esquema so apareceria depois de 130 GB baixados e horas de
cluster gastas. Com ele, aparece em tres segundos.

E ELE JA SE PAGOU ANTES DE EXISTIR. Montando o fixture ate o ciclo fechar,
apareceu um defeito real do produto: `complementos.reguladores` devolvia `0`
quando faltava `UNREMT` e `(n, pendurados)` no caminho normal, e o chamador
desempacota. Base sem regulador derrubava a conversao inteira com `TypeError`.
Nao aparecia nas 97 porque as 97 tem `UNREMT` — apareceria na primeira que nao
tivesse.

O QUE ESTE TESTE NAO E: nao afere numero fisico. A rede minima tem 500 km num
condutor de 31 A e perde 97% de propósito — ela existe para exercitar CAMINHO,
nao para medir engenharia. Quem afere grandeza e a suite de modulo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))
sys.path.insert(0, AQUI)
import fixture                                           # noqa: E402


def _roda(script, *args):
    """Executa como PROCESSO, e nao por import.

    Chamar `main()` no mesmo interpretador esconde tres classes de defeito que
    so aparecem de fora: codigo de retorno descartado, estado global vazando
    entre etapas e o proprio `if __name__ == '__main__'`. O `regerar_v10` saia
    0 mesmo recusando a rodada por causa disso.
    """
    # OS EXECUTAVEIS MORAM EM `etapas/` desde 02/09/2026. O caminho e montado
    # aqui, e nao no chamador, para que este teste seja o primeiro a quebrar se
    # alguem mover de novo — que e exatamente o que ele existe para pegar.
    return subprocess.run([sys.executable, '-u', os.path.join(RAIZ, 'etapas', script)]
                          + list(args), cwd=RAIZ, capture_output=True,
                          text=True, timeout=600)


def _um(caminho):
    """O primeiro registro de um JSON que pode ser lista ou dicionario."""
    with open(caminho, encoding='utf-8') as fh:
        d = json.load(fh)
    return d[0] if isinstance(d, list) else list(d.values())[0]


class OCicloFechaSobreUmaGdbDeVerdade(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.gdb = fixture.garantir()
        cls.saida = tempfile.mkdtemp(prefix='ciclo_')
        cls.passos = {}
        for nome, args in (('converter', (cls.gdb, '--saida', cls.saida)),
                           ('verifica', (cls.saida,)),
                           ('validador', (cls.saida,))):
            cls.passos[nome] = _roda(nome + '.py', *args)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.saida, ignore_errors=True)

    def _ok(self, nome):
        r = self.passos[nome]
        self.assertEqual(r.returncode, 0,
                         '%s saiu %d:\n%s' % (nome, r.returncode,
                                              (r.stdout or '')[-2000:]))

    def test_o_conversor_termina_bem(self):
        self._ok('converter')

    def test_o_conversor_escreve_os_MASTER(self):
        """Sair 0 nao e ter produzido: ver o coletor que publicou vazio."""
        for arq in ('MASTER-GERAL.dss', 'MASTER-AT.dss',
                    'relatorio_rede.json'):
            self.assertTrue(os.path.exists(os.path.join(self.saida, arq)),
                            arq + ' nao foi escrito')

    def test_a_subestacao_ganha_pasta_e_rede(self):
        d = os.path.join(self.saida, 'SE1')
        self.assertTrue(os.path.isdir(d), 'a pasta da SE1 nao existe')
        self.assertTrue(os.path.exists(os.path.join(d, 'REDE-SE1.dss')))

    def test_o_verifica_termina_bem_e_aprova(self):
        self._ok('verifica')
        v = _um(os.path.join(self.saida, 'verificacao.json'))
        self.assertEqual(v.get('veredicto'), 'OK', v)

    def test_o_validador_termina_bem(self):
        self._ok('validador')

    def test_o_modelo_COMPILA_CONVERGE_e_nao_tem_NaN(self):
        """Os tres criterios de aceite do `PLANO.md`, medidos no artefato."""
        v = _um(os.path.join(self.saida, 'validacao.json'))
        self.assertTrue(v.get('compila'), 'nao compila')
        self.assertTrue(v.get('converge'), 'nao converge')
        self.assertEqual(v.get('nos_nan'), 0, 'tem no com NaN')

    def test_a_rede_nao_sai_vazia(self):
        """Modelo que compila com zero elemento tambem "compila"."""
        v = _um(os.path.join(self.saida, 'validacao.json'))
        self.assertGreater(v.get('n_linhas') or 0, 0)
        self.assertGreater(v.get('n_cargas') or 0, 0)

    def test_a_rede_minima_e_CONEXA(self):
        """Zero ramo isolado. A chave da UNSEMT costura B2-B3, e sem ela o
        proprio fixture reproduziria o achado 16 em miniatura."""
        v = _um(os.path.join(self.saida, 'validacao.json'))
        self.assertEqual(v.get('ramos_isolados'), 0)


class AGdbMinimaTemOQueOConversorEXIGE(unittest.TestCase):
    """As camadas lidas SEM `try` — faltando uma, nao ha conversao.

    Este teste e o mapa: quando a safra seguinte mudar um esquema, ele diz
    exatamente qual camada sumiu, em vez de deixar o erro estourar no meio de
    um `pyogrio.raw.read`.
    """

    OBRIGATORIAS = ('BAR', 'CTMT', 'SEGCON', 'SSDMT', 'UNTRMT', 'EQTRMT',
                    'UCBT_tab', 'UCMT_tab', 'CRVCRG', 'UNSEMT',
                    'SSDAT', 'UNSEAT', 'CTAT', 'UNTRAT')

    def test_todas_as_obrigatorias_estao_no_fixture(self):
        import pyogrio
        tem = set(pyogrio.list_layers(fixture.garantir())[:, 0])
        faltam = [c for c in self.OBRIGATORIAS if c not in tem]
        self.assertEqual(faltam, [], 'camada obrigatoria fora do fixture')


if __name__ == '__main__':
    unittest.main()
