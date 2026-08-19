# -*- coding: utf-8 -*-
"""Rodar no cluster tem de dar o mesmo resultado que rodar no laptop.

O risco real da portabilidade nao e o codigo nao rodar em Linux — isso aparece
no primeiro segundo. E ele rodar e produzir arquivos DIFERENTES, sem que
nenhuma conta tenha mudado, porque `open(x, 'w')` traduz o fim de linha para o
padrao do sistema. A prova de invariancia do projeto e a comparacao byte a
byte entre geracoes; no dia em que uma rodasse no cluster e a outra no laptop,
tudo apareceria como diferente e o metodo pararia de valer.

Por isso o teste mais importante daqui e um que le o CODIGO-FONTE: escrita de
texto sem `newline=` e o defeito, e ele nao aparece em nenhuma execucao feita
no Windows.
"""
import ast
import glob
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from bdgd2dss import escrita, plataforma              # noqa: E402

# Modulos que geram ou leem artefato comparado byte a byte. As interfaces
# graficas ficam de fora: o que elas escrevem e para o olho, nao para o diff.
VIGIADOS = sorted(glob.glob(os.path.join(RAIZ, 'bdgd2dss', '*.py'))) + [
    os.path.join(RAIZ, n) for n in
    ('converter.py', 'energia.py', 'verifica.py', 'validador.py', 'ligacao.py',
     'ampacidade.py', 'valida_perdas.py', 'valida_balanco.py',
     'regerar_v10.py')]


def _escritas_sem_fim_de_linha(caminho):
    """Chamadas `open(..., 'w'|'a', encoding=...)` sem `newline=`."""
    with open(caminho, encoding='utf-8') as fh:
        arvore = ast.parse(fh.read().lstrip('﻿'))
    ruins = []
    for n in ast.walk(arvore):
        if not (isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'open'):
            continue
        modo = ''
        if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
            modo = str(n.args[1].value)
        chaves = {k.arg for k in n.keywords}
        if 'mode' in chaves:                # modo por nome: olhar o valor
            for k in n.keywords:
                if k.arg == 'mode' and isinstance(k.value, ast.Constant):
                    modo = str(k.value.value)
        if 'w' not in modo and 'a' not in modo:
            continue
        if 'b' in modo:                     # binario nao traduz nada
            continue
        if 'newline' not in chaves:
            ruins.append(n.lineno)
    return ruins


class OFimDeLinhaNaoPodeDependerDoSistema(unittest.TestCase):

    def test_nenhuma_escrita_de_texto_sem_newline(self):
        faltando = {}
        for caminho in VIGIADOS:
            if not os.path.exists(caminho):
                continue
            r = _escritas_sem_fim_de_linha(caminho)
            if r:
                faltando[os.path.relpath(caminho, RAIZ)] = r
        self.assertEqual(faltando, {},
                         'escrita de texto sem `newline=`: no Linux sairia LF '
                         'e no Windows CRLF, e os modelos das duas maquinas '
                         'deixariam de ser comparaveis. Use '
                         '`newline=escrita.FIM_DE_LINHA`')

    def test_o_fim_de_linha_e_crlf(self):
        """CRLF e nao LF porque e o que as sete bases ja geradas tem. Trocar
        invalidaria 1.195 subestacoes sem mudar um numero."""
        self.assertEqual(escrita.FIM_DE_LINHA, '\r\n')

    def test_escreve_grava_crlf_em_qualquer_sistema(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = escrita.escreve_linhas(os.path.join(d, 'x.dss'), ['a', 'b'])
        with open(p, 'rb') as fh:
            self.assertEqual(fh.read(), b'a\r\nb\r\n')


class OModo(unittest.TestCase):

    def setUp(self):
        self.antes = os.environ.get('BDGD2DSS_MODO')
        plataforma._forcado = None

    def tearDown(self):
        plataforma._forcado = None
        if self.antes is None:
            os.environ.pop('BDGD2DSS_MODO', None)
        else:
            os.environ['BDGD2DSS_MODO'] = self.antes

    def test_fixar_manda_mais_que_o_ambiente(self):
        os.environ['BDGD2DSS_MODO'] = 'pessoal'
        self.assertEqual(plataforma.fixar('cluster'), 'cluster')
        self.assertTrue(plataforma.no_cluster())

    def test_valor_sem_sentido_e_ignorado(self):
        plataforma.fixar('banana')
        self.assertIn(plataforma.modo(), (plataforma.CLUSTER,
                                          plataforma.PESSOAL))

    def test_o_modo_viaja_para_os_processos_filhos(self):
        """O `regerar` dispara cada etapa como processo novo. Um cluster que
        virasse pessoal na segunda etapa seria pior que nao ter modo."""
        plataforma.fixar('cluster')
        self.assertEqual(os.environ.get('BDGD2DSS_MODO'), 'cluster')

    def test_no_pessoal_deixa_folga_e_respeita_o_teto(self):
        plataforma.fixar('pessoal')
        n = plataforma.nucleos()
        self.assertLessEqual(n, plataforma.TETO_PESSOAL)
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, max(1, (os.cpu_count() or 4)
                                    - plataforma.FOLGA_PESSOAL))

    def test_no_cluster_o_limite_e_o_menor_entre_nucleo_e_memoria(self):
        """Nao e "usa tudo". Um no de 128 nucleos e 256 GB comporta ~85
        processos de 3 GB, e pedir 128 faz a maquina paginar — fica mais lenta
        do que com metade."""
        plataforma.fixar('cluster')
        n = plataforma.nucleos()
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, os.cpu_count() or 4)
        gb = plataforma.memoria_livre_gb()
        if gb:
            self.assertLessEqual(
                n, max(1, int(gb // plataforma.GB_POR_PROCESSO)),
                'passou do que a memoria comporta')

    def _com_ambiente(self, **vars):
        import contextlib

        @contextlib.contextmanager
        def ctx():
            antes = {k: os.environ.get(k) for k in vars}
            os.environ.update({k: str(v) for k, v in vars.items()})
            try:
                yield
            finally:
                for k, v in antes.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        return ctx()

    def test_a_fatia_da_fila_manda_mais_que_a_maquina(self):
        """O que o PBS deu, e nao o que a maquina tem.

        `os.cpu_count()` num no de 128 nucleos devolve 128 mesmo quando o PBS
        reservou 32 — usar os 128 e disputar com o vizinho de fila.
        """
        plataforma.fixar('cluster')
        with self._com_ambiente(PBS_NP=2):
            self.assertLessEqual(plataforma.nucleos(), 2)
        with self._com_ambiente(SLURM_CPUS_PER_TASK=2):
            self.assertLessEqual(plataforma.nucleos(), 2)

    def test_o_nodefile_serve_de_reserva(self):
        """Quando `PBS_NP` nao vem, o `PBS_NODEFILE` tem uma linha por nucleo
        alocado."""
        import tempfile
        d = tempfile.mkdtemp()
        arq = os.path.join(d, 'nodes')
        with open(arq, 'w', encoding='utf-8') as fh:
            fh.write('no01\nno01\nno01\n')
        plataforma.fixar('cluster')
        with self._com_ambiente(PBS_NODEFILE=arq):
            self.assertLessEqual(plataforma.nucleos(), 3)

    def test_o_pbs_sozinho_ja_indica_cluster(self):
        """Um job do Ubiratan nao tem tela nem alguem na frente."""
        plataforma._forcado = None
        with self._com_ambiente(PBS_JOBID='123.bira'):
            os.environ.pop('BDGD2DSS_MODO', None)
            self.assertEqual(plataforma.modo(), plataforma.CLUSTER)

    def test_no_cluster_nao_ha_tela(self):
        plataforma.fixar('cluster')
        self.assertFalse(plataforma.tem_tela())

    def test_o_com_da_epri_so_existe_no_windows(self):
        if sys.platform != 'win32':
            self.assertFalse(plataforma.tem_com())

    def test_resumo_diz_tudo_numa_linha(self):
        plataforma.fixar('cluster')
        r = plataforma.resumo()
        for pedaco in ('modo=', 'nucleos=', 'tela=', 'COM='):
            self.assertIn(pedaco, r)


if __name__ == '__main__':
    unittest.main()
