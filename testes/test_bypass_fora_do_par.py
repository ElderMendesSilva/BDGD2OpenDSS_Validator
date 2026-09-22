# -*- coding: utf-8 -*-
"""Bypass de regulador fechado FORA do par de PACs dele — achado 69.

Em campo o regulador fica entre uma chave de entrada e uma de saida, e a
chave de bypass liga as duas pontas por fora, ABERTA com o regulador em
servico. A BDGD a declara fechada. A trava do achado 48
(`test_regulador_em_bypass.py`) so reconhece o bypass que liga os dois PACs
do proprio regulador; este liga os das chaves vizinhas.

Na 5001306 da EQUATORIAL6072 eram seis, com 394 a 2.027 A circulando. A regra
topologica ("a chave que nao toca o regulador") marcou as doze chaves dos seis
lacos, e abri-las derrubou 33 mil nos. O criterio que serve e ELETRICO: dos
candidatos do laco, os que, abertos sozinhos, nao desenergizam no nenhum; deles,
o que poe mais carga no regulador.

A variante `bypass_de_regulador` reproduz o colapso em escala: com o bypass
fechado a fonte entrega 34,7 MW para 2,4 kW de carga.
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
from bdgd2dss import lacos, orientacao                     # noqa: E402

VAZIO = lambda c, t: None                                  # noqa: E731


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


class TestPecas(unittest.TestCase):

    def test_banco_junta_as_fases(self):
        self.assertEqual(lacos.banco('Transformer.REG_5896508_1'),
                         'reg_5896508')
        self.assertEqual(lacos.banco('reg_5896508_3'), 'reg_5896508')

    def test_sem_bypass_o_arquivo_nao_muda(self):
        """Quase toda subestacao do pais: nada a abrir, nada a dizer."""
        self.assertEqual(orientacao.escrever('x', [], 2, (), escreve=VAZIO),
                         orientacao.escrever('x', [], 2, (), escreve=VAZIO,
                                             bypass=(), sem_decisao=()))
        self.assertNotIn('achado 69',
                         orientacao.escrever('x', [], 2, (), escreve=VAZIO))

    def test_elemento_e_controle_saem_juntos_e_antes_da_orientacao(self):
        """`SwtControl State=Closed` fecharia de novo a chave aberta so no
        elemento. E a orientacao foi medida com o bypass ja aberto."""
        t = orientacao.escrever(
            'x', [{'nome': 'RC_X', 'de': 2, 'para': 1, 'kW': 3.0}], 1, (),
            escreve=VAZIO,
            bypass=[{'chave': 'Line.cb', 'controle': 'SwtControl.sw_cb',
                     'regulador': 'reg_x', 'kW': 3.0}])
        self.assertIn('Edit Line.cb enabled=no', t)
        self.assertIn('Edit SwtControl.sw_cb enabled=no', t)
        self.assertLess(t.index('Edit Line.cb'), t.index('RegControl.RC_X'))

    def test_sem_decisao_fica_escrito(self):
        t = orientacao.escrever(
            'x', [], 1, (), escreve=VAZIO,
            sem_decisao=[{'regulador': 'reg_y', 'candidatas': ['line.a'],
                          'motivo': 'nenhuma candidata'}])
        self.assertIn('sem decisao: reg_y', t)
        self.assertNotIn('enabled=no', t)


class TestNaVariante(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='bypass69_')
        gdb = fixture.gerar(os.path.join(cls.tmp, 'b.gdb'),
                            variante='bypass_de_regulador')
        cls.saida = os.path.join(cls.tmp, 'M')
        p = _roda(os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                  '--saida', cls.saida)
        assert p.returncode == 0, p.stderr[-1500:]
        cls.se = os.path.join(cls.saida, 'SE1')
        cls.master = os.path.join(cls.se, 'MASTER-SE1.dss')
        cls.cru = _fonte_kw(cls.master)
        cls.p = cls._etapa()
        cls.arquivo = _le(cls.se, '_REGULADORES.dss')

    @classmethod
    def _etapa(cls):
        return _roda(os.path.join(RAIZ, 'etapas', 'reguladores.py'),
                     cls.saida, '--jobs', '1')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_etapa_roda(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])

    def test_abre_so_o_bypass(self):
        self.assertIn('Edit Line.cb enabled=no', self.arquivo)
        self.assertIn('Edit SwtControl.sw_cb enabled=no', self.arquivo)
        for serie in ('line.ce', 'line.cs'):
            self.assertNotIn(f'Edit {serie} ', self.arquivo.lower())

    def test_o_log_anuncia(self):
        self.assertIn('ACHADO 69: 1 bypass de regulador aberto', self.p.stdout)

    def test_o_json_registra(self):
        with io.open(os.path.join(self.saida, 'reguladores.json'),
                     encoding='utf-8') as fh:
            d = json.load(fh)
        self.assertEqual(d['bypass_abertos'], 1)
        self.assertEqual(d['subestacoes'][0]['bypass_abertos'], ['Line.cb'])

    def test_a_corrente_de_laco_some_sem_apagar_no(self):
        """Com o bypass fechado a fonte entrega milhares de vezes a carga."""
        kw_cru, vivos_cru = self.cru
        kw, vivos = _fonte_kw(self.master)
        self.assertGreater(kw_cru, 1000 * kw)
        self.assertGreater(kw, 0)
        self.assertEqual(vivos, vivos_cru)

    def test_o_laco_sai_do_censo(self):
        r = lacos.lacos_da_se(self.master)
        self.assertEqual(r['com_regulador'], 0)
        self.assertEqual(r['lacos'], 1)          # sobra o CHM1 da minima

    def test_o_master_geral_tambem_aplica(self):
        kw, _ = _fonte_kw(os.path.join(self.saida, 'MASTER-GERAL.dss'))
        self.assertLess(kw, self.cru[0] / 100)

    def test_rodar_de_novo_da_o_mesmo_arquivo(self):
        """A etapa zera o arquivo antes de medir: medir sobre o circuito ja
        corrigido nao acharia laco, e apagaria a correcao."""
        p = self._etapa()
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertEqual(_le(self.se, '_REGULADORES.dss'), self.arquivo)


class TestBypassEmParalelo(unittest.TestCase):
    """Dois bypass em paralelo no mesmo par de barras: abrir um so deixa o
    outro segurando o laco. Ate a V37 isso saia "sem decisao"; na ETR da
    NEOENERGIA47 eram quatro chaves em paralelo e 29 MW circulando. Agora o
    grupo abre junto, como um candidato so."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='bypass69b_')
        gdb = fixture.gerar(os.path.join(cls.tmp, 'b.gdb'),
                            variante='bypass_de_regulador')
        cls.saida = os.path.join(cls.tmp, 'M')
        p = _roda(os.path.join(RAIZ, 'etapas', 'converter.py'), gdb,
                  '--saida', cls.saida)
        assert p.returncode == 0, p.stderr[-1500:]
        se = os.path.join(cls.saida, 'SE1')
        with io.open(os.path.join(se, 'Chaves.dss'), 'a', encoding='utf-8') as fh:
            fh.write('\nNew Line.CB2 Phases=3 Bus1=b3.1.2.3 Bus2=b4.1.2.3 '
                     'Switch=Y r1=1e-4 x1=1e-4 r0=1e-4 x0=1e-4\n')
        with io.open(os.path.join(se, 'Controles.dss'), 'a', encoding='utf-8') as fh:
            fh.write('\nNew SwtControl.SW_CB2 SwitchedObj=Line.CB2 '
                     'SwitchedTerm=1 Lock=No Delay=0 State=Closed\n')
        cls.p = _roda(os.path.join(RAIZ, 'etapas', 'reguladores.py'),
                      cls.saida, '--jobs', '1')
        cls.arquivo = _le(se, '_REGULADORES.dss')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_os_dois_abrem_juntos(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])
        for e in ('Line.cb', 'Line.cb2', 'SwtControl.sw_cb', 'SwtControl.sw_cb2'):
            self.assertIn(f'Edit {e} enabled=no', self.arquivo)
        self.assertIn('2 em paralelo, abertos juntos', self.arquivo)

    def test_as_chaves_em_serie_ficam(self):
        for serie in ('line.ce', 'line.cs'):
            self.assertNotIn(f'edit {serie} ', self.arquivo.lower())

    def test_o_log_conta_as_duas(self):
        self.assertIn('ACHADO 69: 2 bypass de regulador aberto(s), 0 laco(s)',
                      self.p.stdout)


def _variante_com(prefixo, chaves='', controles='', linhas='', regs=''):
    """Converte a `bypass_de_regulador` e acrescenta elementos ao modelo."""
    tmp = tempfile.mkdtemp(prefix=prefixo)
    gdb = fixture.gerar(os.path.join(tmp, 'b.gdb'), variante='bypass_de_regulador')
    saida = os.path.join(tmp, 'M')
    p = _roda(os.path.join(RAIZ, 'etapas', 'converter.py'), gdb, '--saida', saida)
    assert p.returncode == 0, p.stderr[-1500:]
    se = os.path.join(saida, 'SE1')
    for nome, extra in (('Chaves.dss', chaves), ('Controles.dss', controles),
                        ('Linhas.dss', linhas), ('Reguladores.dss', regs)):
        if extra:
            with io.open(os.path.join(se, nome), 'a', encoding='utf-8') as fh:
                fh.write('\n' + extra + '\n')
    p = _roda(os.path.join(RAIZ, 'etapas', 'reguladores.py'), saida, '--jobs', '1')
    return tmp, p, _le(se, '_REGULADORES.dss')


class TestBypassPorTrecho(unittest.TestCase):
    """O bypass e um TRECHO, e as chaves do laco so tiram o regulador de
    servico. A regra nao pode pular para "sem carga" e abrir uma chave: tem de
    abrir o trecho, que devolve o regulador a carga. Na AGT da NEOENERGIA43
    o laco era so de trechos, com 28 MW circulando."""

    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.p, cls.arquivo = _variante_com(
            'bypass69t_',
            controles='Edit SwtControl.SW_CB State=Open',
            linhas='New Line.TB phases=3 Bus1=b3.1.2.3 Bus2=b4.1.2.3 '
                   'r1=0.001 x1=0.001 length=0.01 units=km')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_abre_o_trecho_e_nao_a_chave(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])
        self.assertIn('Edit Line.tb enabled=no', self.arquivo)
        self.assertIn('TRECHO de linha', self.arquivo)
        for serie in ('line.ce', 'line.cs'):
            self.assertNotIn(f'edit {serie} ', self.arquivo.lower())
        self.assertNotIn('sem carga', self.arquivo)


class TestReguladorSemCarga(unittest.TestCase):
    """Entrada e saida do regulador voltam ao mesmo no, e nada depende dele.
    Nenhuma abertura o poe a conduzir — nao ha o que alimentar —, mas o laco
    nao pode operar fechado: na 5000944 da EQUATORIAL6072 circulavam 4,6 kA.
    Abre-se o candidato de menor perda, e o arquivo diz por que."""

    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.p, cls.arquivo = _variante_com(
            'bypass69s_',
            chaves='New Line.X1 Phases=3 Bus1=b5.1.2.3 Bus2=q1.1.2.3 Switch=Y '
                   'r1=1e-4 x1=1e-4 r0=1e-4 x0=1e-4\n'
                   'New Line.X2 Phases=1 Bus1=q2.1 Bus2=q1.1 Switch=Y '
                   'r1=1e-4 x1=1e-4 r0=1e-4 x0=1e-4',
            regs='New Transformer.REG_Q_1 phases=1 windings=2 XHL=0.04\n'
                 '~ buses=[q1.1 q2.1] conns=[wye wye] kVs=[7.9674 7.9674] '
                 'kVAs=[5000 5000] %Rs=[0.01 0.01] maxtap=1.10 mintap=0.90 '
                 'numtaps=32\n'
                 'New RegControl.RC_REG_Q_1 transformer=REG_Q_1 winding=2 '
                 'vreg=125 band=2 ptratio=66.4 delay=15 maxtapchange=1')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_abre_e_diz_por_que(self):
        self.assertEqual(self.p.returncode, 0, self.p.stderr[-1500:])
        self.assertIn('Edit Line.x2 enabled=no', self.arquivo)
        self.assertIn('regulador sem carga a jusante', self.arquivo)
        self.assertNotIn('edit line.x1 ', self.arquivo.lower())

    def test_o_bypass_de_campo_continua_certo(self):
        """O outro regulador da variante segue com a decisao de sempre."""
        self.assertIn('Edit Line.cb enabled=no', self.arquivo)


if __name__ == '__main__':
    unittest.main()
