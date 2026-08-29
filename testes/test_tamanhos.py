# -*- coding: utf-8 -*-
"""O no de acesso nao mede `.gdb`, e a recusa tem de ser do codigo.

28/08/2026: o administrador do Ubiratan avisou que o head node nao pode mais
ser usado para processar. A primeira versao da protecao era um cache: media uma
vez e reusava. Mas cache e conveniencia, nao garantia — apagar o arquivo, ou
baixar base nova, fazia a varredura de ~20 mil `stat` voltar ao no de acesso
sem ninguem perceber.

Aqui se exige o contrario: fora de um job da fila, faltar base no cache e ERRO
com instrucao, nunca medicao silenciosa.
"""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from bdgd2dss import tamanhos as tm                    # noqa: E402


class _ComPasta(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cache = os.path.join(self.dir, 'medicoes', 'tam.json')

    def _gdb(self, nome, bytes_=2048):
        p = os.path.join(self.dir, nome)
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, 'a.gdbtable'), 'wb') as fh:
            fh.write(b'x' * bytes_)
        return p

    def _escrever_cache(self, d):
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, 'w', encoding='utf-8') as fh:
            json.dump(d, fh)


class ForaDoJobNaoMede(_ComPasta):

    def test_base_fora_do_cache_levanta_em_vez_de_varrer(self):
        g = self._gdb('nova.gdb')
        with self.assertRaises(tm.PrecisaDeNo):
            tm.tamanhos([g], self.cache, pode_medir=False)

    def test_o_erro_diz_como_resolver(self):
        g = self._gdb('nova.gdb')
        with self.assertRaises(tm.PrecisaDeNo) as e:
            tm.tamanhos([g], self.cache, pode_medir=False)
        self.assertIn('--medir', str(e.exception))
        self.assertIn('nova.gdb', str(e.exception))

    def test_nao_grava_cache_ao_recusar(self):
        """Recusar tem de ser inerte: nada de arquivo pela metade."""
        g = self._gdb('nova.gdb')
        with self.assertRaises(tm.PrecisaDeNo):
            tm.tamanhos([g], self.cache, pode_medir=False)
        self.assertFalse(os.path.exists(self.cache))

    def test_tudo_no_cache_dispensa_o_no(self):
        """O caso comum: o no de acesso planeja lendo o cache, sem medir."""
        g = self._gdb('velha.gdb')
        self._escrever_cache({g: 3.5})
        tam, novas = tm.tamanhos([g], self.cache, pode_medir=False)
        self.assertEqual((tam[g], novas), (3.5, 0))

    def test_uma_faltando_entre_muitas_ja_barra(self):
        """Nao vale medir 'so a que falta': e justamente a varredura proibida."""
        a, b = self._gdb('a.gdb'), self._gdb('b.gdb')
        self._escrever_cache({a: 1.0})
        with self.assertRaises(tm.PrecisaDeNo):
            tm.tamanhos([a, b], self.cache, pode_medir=False)


class DentroDoJobMede(_ComPasta):

    def test_mede_e_grava(self):
        g = self._gdb('nova.gdb', 2 ** 20)
        tam, novas = tm.tamanhos([g], self.cache, pode_medir=True)
        self.assertEqual(novas, 1)
        self.assertAlmostEqual(tam[g], 1 / 1024, places=4)
        self.assertIn(g, tm.carregar(self.cache))

    def test_so_mede_o_que_falta(self):
        a, b = self._gdb('a.gdb'), self._gdb('b.gdb')
        self._escrever_cache({a: 99.0})
        tam, novas = tm.tamanhos([a, b], self.cache, pode_medir=True)
        self.assertEqual(novas, 1, 'a que ja estava no cache nao se remede')
        self.assertEqual(tam[a], 99.0, 'e o valor do cache prevalece')

    def test_devolve_so_o_que_foi_pedido(self):
        """O cache guarda o historico todo; a rodada usa o seu recorte."""
        a, b = self._gdb('a.gdb'), self._gdb('b.gdb')
        self._escrever_cache({a: 1.0, b: 2.0, '/base/aposentada': 9.0})
        tam, _ = tm.tamanhos([a], self.cache, pode_medir=False)
        self.assertEqual(list(tam), [a])


class CacheQuebradoNaoDerruba(_ComPasta):

    def test_json_truncado_vale_como_vazio(self):
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, 'w', encoding='utf-8') as fh:
            fh.write('{ isto nao e json')
        self.assertEqual(tm.carregar(self.cache), {})

    def test_cache_ausente_vale_como_vazio(self):
        self.assertEqual(tm.carregar(self.cache), {})

    def test_json_que_nao_e_objeto_vale_como_vazio(self):
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, 'w', encoding='utf-8') as fh:
            fh.write('[1, 2, 3]')
        self.assertEqual(tm.carregar(self.cache), {})

    def test_cache_quebrado_fora_do_job_barra_em_vez_de_remedir(self):
        """O modo de falha que importa: cache ilegivel no no de acesso NAO
        pode virar licenca para varrer tudo de novo."""
        g = self._gdb('a.gdb')
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, 'w', encoding='utf-8') as fh:
            fh.write('{ truncado')
        with self.assertRaises(tm.PrecisaDeNo):
            tm.tamanhos([g], self.cache, pode_medir=False)


class DeteccaoDeJob(unittest.TestCase):

    VARS = ('PBS_ENVIRONMENT', 'PBS_JOBID', 'SLURM_JOB_ID')

    def setUp(self):
        self.antes = {v: os.environ.pop(v, None) for v in self.VARS}

    def tearDown(self):
        for v, x in self.antes.items():
            if x is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = x

    def test_sem_variavel_nenhuma_e_no_de_acesso(self):
        self.assertFalse(tm.dentro_de_job())

    def test_pbs_environment_marca_job(self):
        os.environ['PBS_ENVIRONMENT'] = 'PBS_BATCH'
        self.assertTrue(tm.dentro_de_job())

    def test_slurm_tambem(self):
        os.environ['SLURM_JOB_ID'] = '123'
        self.assertTrue(tm.dentro_de_job())

    def test_variavel_vazia_nao_conta(self):
        """`export PBS_JOBID=` no perfil nao pode liberar o no de acesso."""
        os.environ['PBS_JOBID'] = '   '
        self.assertFalse(tm.dentro_de_job())


if __name__ == '__main__':
    unittest.main()
