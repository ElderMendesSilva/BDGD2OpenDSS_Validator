# -*- coding: utf-8 -*-
"""O censo de lacos conta so laco de verdade — o que conduz.

Na EQUATORIAL6072, abrir os lacos das duas piores subestacoes levou a perda
de 77% para 11,5% e de 67% para 14,6%. A primeira medida errou duas vezes
antes de acertar: contou barras em vez de fases, e contou chave aberta como se
fechasse o anel. Este teste trava as duas licoes.

A REDE MINIMA JA TEM UM LACO, de proposito: a chave CHM1 fecha B2-B3 em
paralelo com o trecho S2 (ver `testes/fixture.py`). Os testes medem a partir
dela.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'diagnosticos'))
sys.path.insert(0, AQUI)

import fixture                                             # noqa: E402
import lacos                                               # noqa: E402


class TestOCenso(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        gdb = fixture.garantir()
        cls.saida = os.path.join(cls.tmp, 'MODELOS_MIN_T')
        p = subprocess.run([sys.executable, '-u',
                            os.path.join(RAIZ, 'etapas', 'converter.py'),
                            gdb, '--saida', cls.saida],
                           cwd=RAIZ, capture_output=True, text=True, timeout=600)
        assert p.returncode == 0, p.stderr[-800:]
        cls.master = os.path.join(cls.saida, 'SE1', 'MASTER-SE1.dss')
        cls.base = lacos.lacos_da_se(cls.master)['lacos']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _com(self, *linhas):
        """O MASTER com elementos a mais, antes do `Set mode`."""
        with open(self.master, encoding='utf-8') as fh:
            txt = fh.read()
        extra = '\n'.join(linhas)
        alvo = self.master.replace('.dss', '_x.dss')
        with open(alvo, 'w', encoding='utf-8') as fh:
            fh.write(txt.replace('Set mode=snap', extra + '\nSet mode=snap', 1))
        return alvo

    def test_a_chave_em_paralelo_da_minima_e_um_laco(self):
        self.assertEqual(self.base, 1)

    def test_um_trecho_paralelo_e_um_laco(self):
        m = self._com('New Line.EXTRA_LACO phases=3 Bus1=b1.1.2.3 '
                      'Bus2=b2.1.2.3 r1=0.1 x1=0.1 length=0.1')
        self.assertEqual(lacos.lacos_da_se(m)['lacos'], self.base + 1)

    def test_fases_diferentes_nao_fecham_laco(self):
        """Um ramo so na fase B entre barras ligadas por um ramo so na fase A:
        nenhum anel conduz. O primeiro grafo, por barra, contava isso."""
        m = self._com('New Line.SO_A phases=1 Bus1=b10.1 Bus2=xa.1 '
                      'r1=0.1 x1=0.1 length=0.1',
                      'New Line.SO_B phases=1 Bus1=b10.2 Bus2=xa.2 '
                      'r1=0.1 x1=0.1 length=0.1')
        self.assertEqual(lacos.lacos_da_se(m)['lacos'], self.base)

    def test_chave_aberta_nao_conta(self):
        """Chave normalmente aberta nao conduz, e o laco que ela "fecharia"
        nao existe — foi o segundo erro da primeira medida. Ela mora no
        `Chaves.dss` e o estado no `Controles.dss`, como no modelo real — e
        nessa ordem, porque o controle precisa da chave ja criada."""
        pasta = os.path.dirname(self.master)
        arqs = {n: os.path.join(pasta, n) for n in ('Chaves.dss', 'Controles.dss')}
        originais = {}
        for n, p in arqs.items():
            with open(p, encoding='utf-8') as fh:
                originais[n] = fh.read()
        try:
            with open(arqs['Chaves.dss'], 'a', encoding='utf-8') as fh:
                fh.write('\nNew Line.CH_NA phases=3 Bus1=b1.1.2.3 '
                         'Bus2=b2.1.2.3 Switch=Y r1=1e-4 x1=1e-4\n')
            with open(arqs['Controles.dss'], 'a', encoding='utf-8') as fh:
                fh.write('\nNew SwtControl.SW_CH_NA SwitchedObj=Line.CH_NA '
                         'SwitchedTerm=1 Lock=No Delay=0 State=Open\n')
            self.assertEqual(lacos.lacos_da_se(self.master)['lacos'], self.base)
        finally:
            for n, p in arqs.items():
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(originais[n])

    def test_a_mesma_chave_fechada_conta(self):
        """O controle do teste acima: sem o `State=Open`, e laco."""
        m = self._com('New Line.CH_NF phases=3 Bus1=b1.1.2.3 Bus2=b2.1.2.3 '
                      'Switch=Y r1=1e-4 x1=1e-4')
        self.assertEqual(lacos.lacos_da_se(m)['lacos'], self.base + 1)

    def test_elo_nosso_e_separado(self):
        m = self._com('New Line.VAO_EXTRA_1 phases=3 Bus1=b1.1.2.3 '
                      'Bus2=b2.1.2.3 Switch=y r1=0.0001')
        r = lacos.lacos_da_se(m)
        self.assertEqual(r['lacos'], self.base + 1)
        self.assertEqual(r['por_elo_nosso'], 1)


if __name__ == '__main__':
    unittest.main()
