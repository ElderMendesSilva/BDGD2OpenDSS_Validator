# -*- coding: utf-8 -*-
"""Cada variante da BDGD mínima liga UM achado, e o ciclo prova que ligou.

POR QUE ISTO FALTAVA. A `.gdb` mínima é uma rede **sadia**: tem subestação,
não tem geração distribuída, nenhum PAC invertido. Rodar o ciclo nela exercita
o caminho comum — e o caminho comum nunca foi o problema.

Medido, e não suposto: com o ciclo inteiro sob `sys.settrace`, cruzando as
linhas executadas contra os guardas marcados `# ACHADO N` no código, **22 dos
41 achados** tinham ao menos um guarda cujo *corpo* nunca rodava. O `if` era
avaliado, dava falso, e a correção inteira ficava sem prova. Com estas cinco
variantes são 19 — e o `analise/cobertura_achados.py` refaz a conta.

O CUSTO DE NÃO TER: a V33 caiu em **35 das 99 bases** com um `NameError` no
guarda do achado 61, alcançável só por base com GD implausível. A `.gdb`
mínima não tem GD nenhuma, então o teste de fumaça passou verde por não ter o
que testar. Custou uma rodada nacional inteira.

O QUE ESTE TESTE NÃO É: não afere grandeza física. A rede mínima perde 97% de
propósito. Aqui se prova que **o caminho é percorrido** e que a correção
deixou a marca dela — quem afere número é a suíte de módulo.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)
import fixture                                           # noqa: E402


def _converte(variante, *extra):
    """Gera a variante e roda o conversor sobre ela, como PROCESSO.

    Processo, e não `import`: código de retorno descartado e estado global
    vazando entre etapas só aparecem de fora. O achado 65 é justamente um
    código de retorno.
    """
    d = tempfile.mkdtemp(prefix='var_' + variante + '_')
    gdb = fixture.gerar(os.path.join(d, 'b.gdb'), variante=variante)
    saida = os.path.join(d, 'MODELOS')
    p = subprocess.run([sys.executable, '-u',
                        os.path.join(RAIZ, 'etapas', 'converter.py'),
                        gdb, '--saida', saida] + list(extra),
                       cwd=RAIZ, capture_output=True, text=True, timeout=600)
    return d, saida, p


class _Base(unittest.TestCase):
    variante = None
    extra = ()

    @classmethod
    def setUpClass(cls):
        if cls.variante is None:
            raise unittest.SkipTest('classe base')
        cls.tmp, cls.saida, cls.p = _converte(cls.variante, *cls.extra)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'tmp', None):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def rede(self):
        """Todo o .dss da saída, concatenado."""
        txt = []
        for d, _, fs in os.walk(self.saida):
            for f in fs:
                if f.lower().endswith('.dss'):
                    txt.append(open(os.path.join(d, f), encoding='utf-8',
                                    errors='replace').read())
        return '\n'.join(txt)


class TestSemSubestacao(_Base):
    """ACHADO 65 — as 17 cooperativas da safra 2025."""
    variante = 'sem_subestacao'

    def test_o_conversor_FALHA(self):
        self.assertEqual(self.p.returncode, 2,
                         'base sem subestacao alguma tem de falhar, nao seguir')

    def test_diz_quantos_alimentadores_ficaram_de_fora(self):
        self.assertIn('ACHADO 65', self.p.stdout)
        self.assertIn('3 de 3 alimentadores', self.p.stdout)

    def test_nao_deixa_master_de_subestacao_para_tras(self):
        achados = [f for d, _, fs in os.walk(self.saida) for f in fs
                   if f.startswith('MASTER-') and 'GERAL' not in f
                   and 'AT' not in f]
        self.assertEqual(achados, [])


class TestGdNaBt(_Base):
    """ACHADO 30 — o PAC da geração de BT conferido contra a BT."""
    variante = 'gd_na_bt'

    def test_o_conversor_termina_bem(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-2000:])

    def test_a_geracao_vira_PVSystem(self):
        self.assertIn('New PVSystem.', self.rede())

    def test_nenhum_inversor_na_tensao_da_media(self):
        """O defeito do achado 30: inversor de 127 V escrito numa barra de
        7,97 kV, nos nós 1, 2 e 4, que ninguém mais toca — e NaN no resultado.
        Nenhum PVSystem pode sair com kv de média."""
        vistos = 0
        for l in self.rede().splitlines():
            if l.strip().lower().startswith('new pvsystem.'):
                m = re.search(r'\bkv=([0-9.]+)', l, re.I)
                if m:
                    vistos += 1
                    self.assertLess(float(m.group(1)), 1.0,
                                    'inversor de BT com kv de media: ' + l)
        self.assertGreater(vistos, 0, 'nenhum PVSystem com kv para conferir')


class TestGdImplausivel(_Base):
    """ACHADO 61 — a linha que derrubou a V33."""
    variante = 'gd_implausivel'

    def test_o_conversor_termina_bem(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-2000:])

    def test_o_guarda_e_ALCANCADO(self):
        """É o ponto todo: a V33 morreu nesta linha, e nenhum teste chegava
        nela."""
        self.assertIn('ACHADO 61', self.p.stdout)

    def test_escreve_o_arquivo_de_premissa(self):
        alvo = [os.path.join(d, f) for d, _, fs in os.walk(self.saida)
                for f in fs if f == '_GD_IMPLAUSIVEL.dss']
        self.assertTrue(alvo, '_GD_IMPLAUSIVEL.dss nao foi escrito')
        corpo = open(alvo[0], encoding='utf-8').read()
        self.assertIn('enabled=no', corpo,
                      'a premissa existe mas nao desliga nada')

    def test_a_unidade_continua_emitida(self):
        """A premissa é REVERSÍVEL: apagar o redirect devolve o modelo à
        declaração crua. Para isso a unidade tem de estar no modelo."""
        self.assertIn('UG9', self.rede())


class TestGeracaoFirme(_Base):
    """ACHADO 63 — usina firme não se divide pelo fator solar."""
    variante = 'geracao_firme'

    def test_o_conversor_termina_bem(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-2000:])

    def test_o_guarda_e_ALCANCADO(self):
        self.assertIn('ACHADO 63', self.p.stdout)

    def _a_usina(self):
        alvo = [l for l in self.rede().splitlines()
                if 'New Generator.GD_UGF' in l]
        self.assertEqual(len(alvo), 1, 'a usina firme nao saiu como Generator')
        return alvo[0]

    def test_vira_Generator_e_nao_PVSystem(self):
        self.assertNotIn('New PVSystem.GD_UGF', self.rede())
        self._a_usina()

    def test_com_a_curva_plana(self):
        self.assertIn('Daily=GERACAO_FIRME', self._a_usina())

    def test_a_potencia_e_a_media_do_mes(self):
        """365.000 kWh / 730 h = 500 kW, que é a placa. Dividir pelo fator
        solar de 0,286 daria 1.748 kW — 3,5x a placa, o defeito do achado 63.
        Na MOG02 esse fator levava a tensão a 1,864 pu."""
        m = re.search(r'\bkW=([0-9.]+)', self._a_usina(), re.I)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(float(m.group(1)), 500.0, delta=1.0)


class TestPacInvertido(_Base):
    """ACHADO 54 — primário e secundário trocados no cadastro."""
    variante = 'pac_invertido'

    def test_o_conversor_termina_bem(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-2000:])

    def test_o_guarda_e_ALCANCADO(self):
        self.assertIn('ACHADO 54', self.p.stdout)

    def test_os_lados_saem_endireitados(self):
        """O trafo endireitado tem o lado de MAIOR tensão no `wdg=1`.

        O projeto escreve um `~ wdg=N bus=... Kv=...` por enrolamento, e não
        um `kvs=[a b]` — é por linha de enrolamento que se lê.

        Só os trafos da `UNTRMT` (TR1..TR4) entram: o elevador de barra da
        subestação sobe 13,8 para 34,5 kV de propósito, e não é caso deste
        invariante.
        """
        atual, kvs, conferidos = None, [], 0

        def fecha():
            nonlocal conferidos
            if len(kvs) >= 2:
                conferidos += 1
                self.assertGreaterEqual(
                    kvs[0], kvs[1],
                    'primario com tensao menor que o secundario em ' + str(atual))

        for l in self.rede().splitlines():
            t = l.strip()
            if t.lower().startswith('new transformer.'):
                fecha()
                nome = t.split()[1].split('.', 1)[1]
                atual = nome if re.fullmatch(r'TR\d+', nome, re.I) else None
                kvs = []
            elif atual and t.startswith('~') and 'wdg=' in t.lower():
                m = re.search(r'\bkv=([0-9.]+)', t, re.I)
                if m:
                    kvs.append(float(m.group(1)))
        fecha()
        self.assertGreater(conferidos, 0, 'nenhum enrolamento para conferir')


if __name__ == '__main__':
    unittest.main()
