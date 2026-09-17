# -*- coding: utf-8 -*-
"""Transformador de consumidor sai da perda da rede, e so o ferro — achado 68.

`UNTRMT.POS` declara a posse do transformador. `PD` e da distribuidora; `O` e
`CS` sao de consumidor (confirmado pelo Elder em 17/09/2026). O ferro do
transformador do cliente acontece depois da medicao dele e nao e perda da
rede — e no pais sao 24,6% dos kVA e 12,6% do ferro. Na FORCEL83, zerar esse
ferro levou a razao modelo/ANEEL de 1,34 para 1,18.

A premissa e reversivel, como as outras: `_POSSE.dss` redirecionado pelo
MASTER. E o transformador CONTINUA em servico, porque a carga pendurada nele
nao pode sumir junto.
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
sys.path.insert(0, AQUI)

import fixture                                             # noqa: E402
from bdgd2dss import transformadores                       # noqa: E402


class TestOsCodigos(unittest.TestCase):

    def test_so_os_confirmados(self):
        """`CO`, `G`, `OD`, `T` e `A` existem no pais e nao foram
        confirmados: zerar o ferro de um transformador da distribuidora
        apagaria perda de verdade."""
        self.assertEqual(transformadores.POSSE_CONSUMIDOR, {'O', 'CS'})
        self.assertNotIn('PD', transformadores.POSSE_CONSUMIDOR)


class TestAPremissa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.saidas = {}
        for variante in (None, 'trafo_de_consumidor'):
            nome = variante or 'minima'
            gdb = fixture.gerar(os.path.join(cls.tmp, nome + '.gdb'),
                                variante=variante)
            saida = os.path.join(cls.tmp, 'M_' + nome)
            p = subprocess.run([sys.executable, '-u',
                                os.path.join(RAIZ, 'etapas', 'converter.py'),
                                gdb, '--saida', saida],
                               cwd=RAIZ, capture_output=True, text=True,
                               timeout=600)
            cls.saidas[nome] = (saida, p)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _arq(self, nome, *partes):
        saida, p = self.saidas[nome]
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        with io.open(os.path.join(saida, *partes), encoding='utf-8') as fh:
            return fh.read()

    def test_base_sem_posse_escreve_o_arquivo_vazio(self):
        """`redirect` de arquivo ausente aborta a subestacao inteira."""
        corpo = self._arq('minima', 'SE1', '_POSSE.dss')
        self.assertNotIn('Edit Transformer', corpo)

    def test_zera_o_ferro_so_dos_de_consumidor(self):
        corpo = self._arq('trafo_de_consumidor', 'SE1', '_POSSE.dss')
        self.assertIn('Edit Transformer.TR3 %noloadloss=0', corpo)
        self.assertIn('Edit Transformer.TR4 %noloadloss=0', corpo)
        self.assertNotIn('TR1', corpo)
        self.assertNotIn('TR2', corpo)

    def test_nao_desliga_o_transformador(self):
        """A carga pendurada nele continua precisando dele."""
        corpo = self._arq('trafo_de_consumidor', 'SE1', '_POSSE.dss')
        self.assertNotIn('enabled', corpo.lower())

    def test_o_log_anuncia(self):
        _, p = self.saidas['trafo_de_consumidor']
        self.assertIn('ACHADO 68: 2 transformadores de consumidor', p.stdout)

    def test_os_dois_masters_redirecionam(self):
        self.assertIn('redirect _POSSE.dss',
                      self._arq('trafo_de_consumidor', 'SE1', 'MASTER-SE1.dss'))
        self.assertIn('SE1/_POSSE.dss',
                      self._arq('trafo_de_consumidor', 'MASTER-GERAL.dss'))

    def test_o_ferro_some_de_verdade_e_a_carga_fica(self):
        """Compila os dois jeitos: com a premissa, a perda dos TR3/TR4 cai e
        a potencia que eles entregam continua."""
        import opendssdirect as dss
        saida, _ = self.saidas['trafo_de_consumidor']
        master = os.path.join(saida, 'SE1', 'MASTER-SE1.dss')

        def mede(sem_premissa):
            txt = io.open(master, encoding='utf-8').read()
            alvo = master
            if sem_premissa:
                alvo = master.replace('.dss', '_cru.dss')
                io.open(alvo, 'w', encoding='utf-8').write(
                    txt.replace('redirect _POSSE.dss', '! (sem premissa)'))
            dss.Text.Command('Clear')
            dss.Text.Command(f'Redirect "{alvo}"')
            dss.Text.Command('Set mode=snap')
            dss.Solution.Solve()
            out = {}
            for tr in ('TR3', 'TR4'):
                dss.Circuit.SetActiveElement('Transformer.' + tr)
                out[tr] = (dss.CktElement.Losses()[0],
                           abs(sum(dss.CktElement.Powers()[0:6:2])))
            return out

        cru, com = mede(True), mede(False)
        for tr in ('TR3', 'TR4'):
            self.assertLess(com[tr][0], cru[tr][0],
                            f'{tr}: a perda nao caiu com a premissa')
            self.assertGreater(com[tr][1], 0,
                               f'{tr}: o transformador saiu de servico')


if __name__ == '__main__':
    unittest.main()
