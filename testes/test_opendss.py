# -*- coding: utf-8 -*-
"""O caminho do OpenDSS — o que a suite nao alcancava.

Ate aqui todos os testes paravam antes do motor: liam a BDGD, montavam
texto, conferiam numero. Mas o produto e um modelo que tem de COMPILAR e
RESOLVER, e ha uma classe inteira de defeito que so aparece do outro lado —
sintaxe recusada, parametro com nome errado, e sobretudo UNIDADE.

A unidade de comprimento me enganou duas vezes durante o levantamento. O
`Lines.Length()` devolve o comprimento NA UNIDADE DA PROPRIA LINHA, e a
conversao escreve `Units=m` com `LineCode` em `units=km`. Ler 120,84 e
concluir "120,84 km" produziu um achado inteiro que depois teve de ser
retirado. Um teste que fixa isso vale mais do que a lembranca de ter errado.

O que este arquivo cobre:
  1. os LineCodes gerados de uma BDGD de verdade compilam sem erro;
  2. a resistencia efetiva e r1 x comprimento CONVERTIDO para km;
  3. `Lines.Length()` devolve metros quando a linha esta em metros;
  4. o circuito resolve, converge e nao produz NaN.
"""
import math
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import fixture                                    # noqa: E402
from bdgd2dss import linecodes                    # noqa: E402
from bdgd2dss.leitor import BDGD                  # noqa: E402

try:
    import opendssdirect as dss
except ImportError:                               # pragma: no cover
    dss = None

GDB = None

KV = 13.8               # tensao de linha da fonte
R1 = 0.5                # ohm/km declarados no LineCode do teste analitico
METROS = 120.0          # comprimento da linha, em METROS
KW = 1000.0             # carga trifasica equilibrada, fator de potencia 1


def setUpModule():
    global GDB
    GDB = fixture.garantir()


def _limpa():
    dss.Text.Command('Clear')
    dss.Text.Command(f'New Circuit.T basekv={KV} pu=1.0 phases=3 '
                     f'bus1=fonte MVAsc3=100000 MVAsc1=100000')
    dss.Text.Command(f'Set Voltagebases=[{KV}]')


@unittest.skipUnless(dss is not None, 'opendssdirect nao instalado')
class LineCodesGeradosCompilam(unittest.TestCase):
    """O arquivo que o conversor escreve, lido pelo motor que vai usa-lo."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.arq = os.path.join(cls.dir, 'LineCodes.dss')
        cls.mapa, cls.n, _ = linecodes.gerar(BDGD(GDB, verbose=False), cls.arq)

    def setUp(self):
        _limpa()
        dss.Text.Command(f'Redirect "{self.arq}"')

    def test_sem_erro_de_sintaxe(self):
        self.assertEqual(dss.Error.Number(), 0, dss.Error.Description())

    def test_um_linecode_por_condutor_e_por_numero_de_fases(self):
        """4 condutores x 3 fases, mais o generico e o ideal, tambem x 3."""
        self.assertEqual(dss.LineCodes.Count(), self.n * 3 + 6)

    def test_a_ampacidade_declarada_chega_ao_motor(self):
        """normamps e o que a verificacao de sobrecarga do passo 5 vai ler.
        O condutor C4 do fixture e o caso do 593: 31 A."""
        dss.LineCodes.Name(self.mapa['C4'][3])
        self.assertAlmostEqual(dss.LineCodes.NormAmps(), 31.0, places=1)
        self.assertAlmostEqual(dss.LineCodes.R1(), 8.232, places=3)

    def test_o_generico_e_o_ideal_existem(self):
        """Trecho sem TIP_CND valido cai no generico; chave cai no ideal.
        Se algum sumir, a conversao quebra numa base que os use."""
        nomes = {x.lower() for x in dss.LineCodes.AllNames()}
        for nf in (1, 2, 3):
            self.assertIn(f'cnd_generico_{nf}f', nomes)
            self.assertIn(f'cnd_ideal_{nf}f', nomes)


@unittest.skipUnless(dss is not None, 'opendssdirect nao instalado')
class UnidadeDeComprimento(unittest.TestCase):
    """A armadilha que me pegou duas vezes.

    `LineCode` em ohm/km, `Line` com `Units=m`. A resistencia efetiva e
    r1 x (metros/1000) — e `Lines.Length()` devolve METROS, nao km.
    """

    def setUp(self):
        _limpa()
        dss.Text.Command(f'New LineCode.TESTE nphases=3 basefreq=60 units=km '
                         f'r1={R1} x1=0 r0={R1} x0=0 c1=0 c0=0 '
                         f'normamps=200 emergamps=240')
        dss.Text.Command(f'New Line.L1 Bus1=fonte.1.2.3 Bus2=carga.1.2.3 '
                         f'LineCode=TESTE Length={METROS} Units=m')
        dss.Text.Command(f'New Load.C1 Bus1=carga.1.2.3 Phases=3 Conn=delta '
                         f'Model=1 kV={KV} kW={KW} pf=1.0')
        dss.Text.Command('Set mode=snap')
        dss.Solution.Solve()
        self.assertTrue(dss.Solution.Converged(), 'o circuito tem de resolver')

    def test_length_devolve_a_unidade_da_propria_linha(self):
        """O erro concreto: ler 120,84 e anotar "120,84 km" quando eram
        120,84 m. Um fator de mil, e o resultado ainda parece plausivel."""
        dss.Lines.Name('L1')
        self.assertAlmostEqual(dss.Lines.Length(), METROS, places=3)
        self.assertNotAlmostEqual(dss.Lines.Length(), METROS / 1000.0,
                                  places=3)

    def test_a_perda_bate_com_r1_vezes_o_comprimento_em_km(self):
        """3 R I^2 com R = r1 x km. Se a conversao de unidade estivesse
        errada em qualquer ponto da cadeia, a perda erraria por fator 1.000.
        """
        dss.Circuit.SetActiveElement('Line.L1')
        i = dss.CktElement.CurrentsMagAng()[:6:2]      # modulo das 3 fases
        corrente = sum(i) / 3.0
        r_ohm = R1 * METROS / 1000.0
        analitica = 3.0 * r_ohm * corrente ** 2        # em W
        medida = dss.CktElement.Losses()[0]            # em W
        self.assertAlmostEqual(medida / analitica, 1.0, delta=0.01,
                               msg=f'{medida:.1f} W medidos contra '
                                   f'{analitica:.1f} W analiticos '
                                   f'(I={corrente:.2f} A, R={r_ohm:.4f} ohm)')

    def test_a_corrente_e_a_esperada_da_carga(self):
        """Controle do teste acima: se a corrente nao for a da carga, a
        coincidencia de perdas nao provaria a unidade."""
        dss.Circuit.SetActiveElement('Line.L1')
        corrente = sum(dss.CktElement.CurrentsMagAng()[:6:2]) / 3.0
        self.assertAlmostEqual(corrente, KW * 1000 / (math.sqrt(3) * KV * 1000),
                               delta=1.0)

    def test_nao_ha_nan_nas_tensoes(self):
        """`verifica.py` reprova a subestacao inteira quando aparece NaN.
        Aqui o caso trivial, para que o teste falhe cedo se o motor mudar."""
        for v in dss.Circuit.AllBusMagPu():
            self.assertEqual(v, v, 'NaN na tensao de barra')
            self.assertGreater(v, 0.5)


if __name__ == '__main__':
    unittest.main()
