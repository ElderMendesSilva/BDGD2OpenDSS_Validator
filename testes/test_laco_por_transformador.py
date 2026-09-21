# -*- coding: utf-8 -*-
"""Laco fechado atraves de transformador — achado 70.

Na 5001306 da EQUATORIAL6072, com os seis bypass de regulador ja abertos
(achado 69), a perda seguia em 64,5%. Um laco de 42 elementos ligava por
chaves de MT os dois lados do abaixador `MCG-D-TRF-TR1` (34,5/13,8 kV); abri-lo
levou a perda a 11,6%, sem desligar no. Os outros 31 lacos, todos na mesma
tensao, nao mudavam nada.

O que faz mal nao e o laco: e o laco atravessar uma mudanca de tensao. A
variante `laco_por_transformador` reproduz a forma em escala, e a minima ja
traz um laco na mesma tensao (CHM1) que tem de ficar fechado.
"""
import io
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
sys.path.insert(0, AQUI)

import fixture                                             # noqa: E402
from bdgd2dss import lacos                                 # noqa: E402


def _roda(*args):
    return subprocess.run([sys.executable, '-u'] + list(args), cwd=RAIZ,
                          capture_output=True, text=True, timeout=600)


def _le(*partes):
    with io.open(os.path.join(*partes), encoding='utf-8') as fh:
        return fh.read()


def _fonte_kw(master):
    import opendssdirect as dss
    dss.Text.Command('Clear')
    dss.Text.Command(f'Redirect "{master}"')
    vivos = sum(1 for v in dss.Circuit.AllBusMagPu() if v > 1e-3)
    return -dss.Circuit.TotalPower()[0], vivos


class TestOArquivo(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.arq = os.path.join(self.tmp, '_LACOS.dss')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_vazio_diz_que_rodou(self):
        t = lacos.escrever(self.arq)
        self.assertIn('achado 70', t)
        self.assertNotIn('enabled=no', t)
        self.assertTrue(os.path.exists(self.arq))

    def test_elemento_e_controle_saem_juntos(self):
        t = lacos.escrever(self.arq, [{
            'chave': 'Line.ct', 'controle': 'SwtControl.sw_ct',
            'transformadores': ['ta'], 'razao': 2.0, 'perda_kW': 0.0,
            'equivalentes': 3}])
        self.assertIn('Edit Line.ct enabled=no', t)
        self.assertIn('Edit SwtControl.sw_ct enabled=no', t)
        self.assertIn('3 chaves equivalentes', t)

    def test_razao_proxima_de_um_nao_e_incoerente(self):
        self.assertFalse(lacos.incoerente({'razao': 1.02}))
        self.assertTrue(lacos.incoerente({'razao': 0.4}))
        self.assertTrue(lacos.incoerente({'razao': 2.5}))


class _DssFalso:
    """So o que `lacos.compilar` e `lacos.resolver` tocam."""

    def __init__(self, erro, elementos):
        erro_, n = erro, elementos

        class Text:
            @staticmethod
            def Command(cmd):
                if erro_ and cmd != 'Clear':
                    raise RuntimeError(erro_)

        class Circuit:
            @staticmethod
            def NumCktElements():
                return n

        self.Text, self.Circuit = Text, Circuit


class TestAvisoDeSolucao(unittest.TestCase):
    """O `Max Control Iterations Exceeded` (#485) sobe do `Solve` no fim do
    MASTER, com o circuito ja montado. Ate 21/09/2026 a etapa desistia da
    subestacao por ele — sete na EQUATORIAL6072, justamente as que nao
    convergem. Na 5001232, tratada, a perda foi de 82,7% para 11,5%."""

    MAX = '(#485) Warning Max Control Iterations Exceeded.\nTip: Show Eventlog'
    DUP = '(#266) Warning: Duplicate new element definition: "Line.50870".'

    def test_sem_erro_devolve_none(self):
        self.assertIsNone(lacos.compilar(_DssFalso(None, 10), 'M.dss'))
        self.assertTrue(lacos.resolver(_DssFalso(None, 10)))

    def test_485_com_circuito_montado_e_aviso(self):
        aviso = lacos.compilar(_DssFalso(self.MAX, 10), 'M.dss')
        self.assertIn('#485', aviso)
        self.assertNotIn('\n', aviso)
        self.assertFalse(lacos.resolver(_DssFalso(self.MAX, 10)))

    def test_485_sem_circuito_sobe(self):
        with self.assertRaises(RuntimeError):
            lacos.compilar(_DssFalso(self.MAX, 0), 'M.dss')

    def test_duplicata_continua_erro(self):
        """O #266 aborta a montagem no meio: censo e decisao sobre meio
        circuito mentiriam."""
        with self.assertRaises(RuntimeError):
            lacos.compilar(_DssFalso(self.DUP, 10), 'M.dss')
        with self.assertRaises(RuntimeError):
            lacos.resolver(_DssFalso(self.DUP, 10))


class TestNaVariante(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='laco70_')
        gdb = fixture.gerar(os.path.join(cls.tmp, 'b.gdb'),
                            variante='laco_por_transformador')
        cls.saida = os.path.join(cls.tmp, 'M')
        p = _roda(os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                  '--saida', cls.saida)
        assert p.returncode == 0, p.stderr[-1500:]
        cls.se = os.path.join(cls.saida, 'SE1')
        cls.master = os.path.join(cls.se, 'MASTER-SE1.dss')
        cls.vazio = _le(cls.se, '_LACOS.dss')
        cls.cru = _fonte_kw(cls.master)
        cls.p = cls._etapa()
        cls.arquivo = _le(cls.se, '_LACOS.dss')

    @classmethod
    def _etapa(cls):
        return _roda(os.path.join(RAIZ, 'etapas', 'reguladores.py'),
                     cls.saida, '--jobs', '1')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_o_conversor_escreve_o_arquivo_e_o_redirect(self):
        """`redirect` de arquivo ausente aborta a subestacao inteira."""
        self.assertIn('achado 70', self.vazio)
        self.assertIn('redirect _LACOS.dss', _le(self.master))
        self.assertIn('SE1/_LACOS.dss',
                      _le(self.saida, 'MASTER-GERAL.dss'))

    def test_a_etapa_roda(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])

    def test_abre_a_chave_do_laco_do_abaixador(self):
        self.assertIn('Edit Line.ct enabled=no', self.arquivo)
        self.assertIn('Edit SwtControl.sw_ct enabled=no', self.arquivo)

    def test_o_laco_na_mesma_tensao_fica(self):
        self.assertNotIn('chm1', self.arquivo.lower())
        r = lacos.lacos_da_se(self.master)
        self.assertEqual(r['lacos'], 1)
        self.assertEqual(r['atraves_de_transformador'], 0)

    def test_o_log_anuncia(self):
        self.assertIn('ACHADO 70: 1 laco(s) atraves de transformador',
                      self.p.stdout)

    def test_o_json_registra(self):
        with io.open(os.path.join(self.saida, 'reguladores.json'),
                     encoding='utf-8') as fh:
            d = json.load(fh)
        self.assertEqual(d['lacos_abertos'], 1)
        self.assertEqual(d['subestacoes'][0]['lacos_abertos'], ['Line.ct'])

    def test_a_circulacao_some_sem_apagar_no(self):
        kw_cru, vivos_cru = self.cru
        kw, vivos = _fonte_kw(self.master)
        self.assertGreater(kw_cru, 100 * kw)
        self.assertGreater(kw, 0)
        self.assertEqual(vivos, vivos_cru)

    def test_rodar_de_novo_da_o_mesmo_arquivo(self):
        p = self._etapa()
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertEqual(_le(self.se, '_LACOS.dss'), self.arquivo)


class TestModeloAnterior(unittest.TestCase):
    """MASTER sem o `redirect _LACOS.dss` (rodada anterior ao achado 70):
    a etapa nao decide nada que nao teria efeito, e segue com o resto."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='laco70v_')
        gdb = fixture.gerar(os.path.join(cls.tmp, 'b.gdb'),
                            variante='laco_por_transformador')
        cls.saida = os.path.join(cls.tmp, 'M')
        p = _roda(os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                  '--saida', cls.saida)
        assert p.returncode == 0, p.stderr[-1500:]
        se = os.path.join(cls.saida, 'SE1')
        m = os.path.join(se, 'MASTER-SE1.dss')
        txt = _le(m).replace('redirect _LACOS.dss', '! (anterior)')
        with io.open(m, 'w', encoding='utf-8') as fh:
            fh.write(txt)
        cls.antes = _le(se, '_LACOS.dss')
        cls.p = _roda(os.path.join(RAIZ, 'etapas', 'reguladores.py'),
                      cls.saida, '--jobs', '1')
        cls.depois = _le(se, '_LACOS.dss')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_segue_sem_erro_e_sem_decidir(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])
        self.assertNotIn('ACHADO 70', self.p.stdout)
        self.assertEqual(self.antes, self.depois)


if __name__ == '__main__':
    unittest.main()
