# -*- coding: utf-8 -*-
"""O pré-voo é a porta da rodada nacional.

Não é um achado, e por isso não tem número: achado é situação encontrada
numa BDGD. Isto é infraestrutura — a trava que impede gastar o cluster com
código que já se sabe quebrado.

POR QUE EXISTE. Uma rodada nacional custa 99 jobs e horas de cluster, e três
regressões silenciosas passaram por ela em setembro de 2026:

- a **V33** gastou 99 jobs para descobrir um `NameError` de uma linha, que só
  era alcançado por base com GD implausível;
- a **V29** e a primeira **V30** rodaram inteiras sem chamar o
  `reguladores.py` — o `regerar_v10` listava a etapa em `ETAPAS` e o laço de
  execução nunca a invocava;
- o caminho do `de_para_mnemonicos.csv` estava quebrado desde a reorganização
  de 02/09, e `carregar_depara()` devolvia `{}` sem reclamar.

Nenhuma delas quebrava um teste. Todas mudavam o RESULTADO — e é isso que o
pré-voo compara: o ciclo inteiro sobre as fixtures, contra números gravados.

O QUE ESTE TESTE PROVA. Que a porta existe e está trancada: que o
`submeter_todas.sh` recusa submeter sem selo do commit corrente, que o selo é
por commit, e que a comparação acusa diferença em vez de engolir. Não roda o
pré-voo inteiro (são seis ciclos de conversão) — quem faz isso é o job PBS.
"""
import io
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

import prevoo                                              # noqa: E402

SUBMETER = os.path.join(RAIZ, 'cluster', 'submeter_todas.sh')
PBS = os.path.join(RAIZ, 'cluster', 'prevoo.pbs')


class TestAComparacao(unittest.TestCase):
    """A comparação tem de ACUSAR. Uma que só sabe aprovar não é porta."""

    def setUp(self):
        self.ref = {'minima': {'converter_rc': 0, 'achados': [59],
                               'ses': {'SE1': {'causa': 'OK',
                                               'perdas_pct': 8.69}}}}

    def test_igual_nao_acusa_nada(self):
        self.assertEqual(prevoo.compara(self.ref, self.ref), [])

    def test_numero_que_mudou_aparece_com_os_dois_valores(self):
        """Quem lê tem de ver de quanto para quanto — sem isso não dá para
        decidir se a mudança era pretendida."""
        atual = {'minima': {'converter_rc': 0, 'achados': [59],
                            'ses': {'SE1': {'causa': 'OK',
                                            'perdas_pct': 53.72}}}}
        fora = prevoo.compara(atual, self.ref)
        self.assertEqual(len(fora), 1)
        self.assertIn('8.69', fora[0])
        self.assertIn('53.72', fora[0])

    def test_achado_que_parou_de_disparar_e_acusado(self):
        """O caso do `reguladores.py`: a etapa sumiu do ciclo e nenhum número
        de teste mudou. O que muda é a lista de achados anunciados."""
        atual = {'minima': dict(self.ref['minima'], achados=[])}
        fora = prevoo.compara(atual, self.ref)
        self.assertTrue(any('achados' in f for f in fora), fora)

    def test_conversao_que_passou_a_falhar_e_acusada(self):
        """O `NameError` da V33 aparece aqui: `converter_rc` 0 -> 1."""
        atual = {'minima': dict(self.ref['minima'], converter_rc=1)}
        fora = prevoo.compara(atual, self.ref)
        self.assertTrue(any('converter_rc' in f for f in fora), fora)

    def test_caso_que_sumiu_e_caso_novo_aparecem(self):
        self.assertTrue(prevoo.compara({}, self.ref))
        self.assertTrue(prevoo.compara(self.ref, {}))


class TestALeituraDosAchados(unittest.TestCase):
    """Quais achados o ciclo ANUNCIOU, lido do log das etapas."""

    def test_pega_o_numero_depois_da_palavra(self):
        self.assertEqual(prevoo._achados_no_log(
            '  ACHADO 61: 1 unidade(s) de GD com energia acima'), [61])

    def test_varios_na_mesma_rodada_saem_ordenados(self):
        self.assertEqual(prevoo._achados_no_log(
            'ACHADO 63: usina\nblah\nACHADO 54: trafos\nACHADO 63: de novo'),
            [54, 63])

    def test_texto_sem_numero_nao_vira_achado(self):
        self.assertEqual(prevoo._achados_no_log('ver ACHADO no documento'), [])


class TestAReferencia(unittest.TestCase):

    def test_a_referencia_esta_versionada(self):
        """Referência que não está no repositório não compara nada entre
        máquinas — e o pré-voo roda no cluster, não aqui."""
        self.assertTrue(os.path.exists(prevoo.REFERENCIA),
                        'dados/referencia_prevoo.json sumiu')
        # O NO DE CALCULO NAO TEM GIT — e la que o pre-voo roda. Sem esta
        # guarda o proprio pre-voo reprovava por causa deste teste, que e
        # sobre o repositorio e nao sobre o produto.
        if not shutil.which('git'):
            self.skipTest('sem git nesta maquina')
        p = subprocess.run(['git', 'ls-files', '--error-unmatch',
                            os.path.relpath(prevoo.REFERENCIA, RAIZ)],
                           cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, 'a referencia nao esta no git')

    def test_cobre_todas_as_fixtures(self):
        sys.path.insert(0, os.path.join(RAIZ, 'testes'))
        import fixture                                      # noqa: PLC0415
        import json                                         # noqa: PLC0415
        ref = json.load(open(prevoo.REFERENCIA, encoding='utf-8'))
        esperado = {'minima'} | set(fixture.VARIANTES)
        self.assertEqual(set(ref), esperado,
                         'fixture nova sem referencia: rode --gravar')

    def test_a_variante_do_achado_65_falha_de_proposito(self):
        """`sem_subestacao` tem de sair com código 2 — se um dia sair 0, a
        recusa do achado 65 caiu e a referência é quem avisa."""
        import json                                         # noqa: PLC0415
        ref = json.load(open(prevoo.REFERENCIA, encoding='utf-8'))
        self.assertEqual(ref['sem_subestacao']['converter_rc'], 2)


class TestAPorta(unittest.TestCase):
    """O `submeter_todas.sh` recusa sem selo. Lido do fonte: rodá-lo exige
    cluster, PBS e as `.gdb` — nada disso existe aqui."""

    def setUp(self):
        self.fonte = io.open(SUBMETER, encoding='utf-8').read()

    def test_existe_o_modo_prevoo(self):
        self.assertIn('--prevoo', self.fonte)
        self.assertIn('cluster/prevoo.pbs', self.fonte)

    def test_a_porta_confere_o_selo_do_COMMIT(self):
        self.assertIn('SELO="logs/prevoo/${COMMIT}.ok"', self.fonte,
                      'o selo tem de ser por commit, senao vale para codigo velho')

    def test_recusa_quando_falta_o_selo(self):
        self.assertRegex(
            self.fonte,
            r'if \[\[ ! -f "\$SELO" \][^\n]*\n(?:.*\n)*?\s*exit 1',
            'a porta nao recusa quando falta o selo')

    def test_a_porta_so_vale_na_submissao_de_verdade(self):
        """`bash submeter_todas.sh` sem `--rodar` só mostra o plano, e tem de
        continuar funcionando sem selo nenhum."""
        self.assertIn('if [[ $RODAR == sim && "${PREVOO:-}" != "ignorar" ]]',
                      self.fonte)

    def test_a_porta_vem_depois_do_COMMIT(self):
        self.assertLess(self.fonte.index('COMMIT=$(git rev-parse HEAD'),
                        self.fonte.index('SELO="logs/prevoo/'),
                        'a porta usa $COMMIT antes de ele existir')

    def test_pular_a_porta_e_possivel_mas_GRITA(self):
        """Repetir uma safra com commit já provado é legítimo; fazê-lo em
        silêncio não é."""
        self.assertIn('PREVOO=ignorar', self.fonte)
        self.assertIn('PRE-VOO IGNORADO', self.fonte)

    def test_o_pbs_grava_o_selo_e_propaga_o_codigo(self):
        pbs = io.open(PBS, encoding='utf-8').read()
        self.assertIn('--selo logs/prevoo', pbs)
        self.assertIn('exit $rc', pbs,
                      'o job tem de reprovar quando o pre-voo reprova')

    def test_o_pbs_nao_roda_no_head_node(self):
        pbs = io.open(PBS, encoding='utf-8').read()
        self.assertIn('PBS_O_WORKDIR', pbs)


class TestOSelo(unittest.TestCase):
    """O selo é escrito só quando passa, e só quando identifica um código."""

    def setUp(self):
        self.fonte = io.open(os.path.join(RAIZ, 'etapas', 'prevoo.py'),
                             encoding='utf-8').read()

    def test_o_commit_vem_do_carimbo_e_nao_de_git_direto(self):
        """O NÓ DE CÁLCULO NÃO TEM GIT. A primeira execução real no cluster
        gravou `sem_commit.ok` — um arquivo que a porta, que lê o commit no nó
        de acesso, jamais acharia. O `carimbo` cai para `BDGD2DSS_COMMIT`."""
        self.assertIn('carimbo.commit(curto=False)', self.fonte)
        self.assertIn("commit + '.ok'", self.fonte)

    def test_sem_commit_nenhum_selo_e_gravado(self):
        """Selo que não identifica código não vale como porta."""
        self.assertLess(self.fonte.index('if not commit:'),
                        self.fonte.index("alvo = os.path.join(a.selo,"),
                        'o selo e montado antes de conferir se ha commit')

    def test_o_selo_so_sai_depois_da_COMPARACAO(self):
        """Reprovar na comparação tem de acontecer antes de qualquer selo."""
        self.assertLess(self.fonte.index('    if fora:'),
                        self.fonte.index('    if a.selo:'),
                        'o selo sairia mesmo com diferenca contra a referencia')

    def test_a_suite_reprovada_para_antes_de_tudo(self):
        self.assertLess(self.fonte.index('a suite reprovou'),
                        self.fonte.index('    if a.selo:'))


if __name__ == '__main__':
    unittest.main()
