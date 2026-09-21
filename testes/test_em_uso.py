# -*- coding: utf-8 -*-
"""O orcamento do cluster desconta o que ja esta na fila — `cluster/em_uso.py`.

Ate 21/09/2026 o `submeter_todas.sh` somava os nucleos com `qstat -u $USER -f`,
e neste PBS o `-u` faz o `-f` ser ignorado: a soma dava ZERO em toda rodada. O
plano da V37 dizia "0 comprometidos" com 48 nucleos rodando. Lido do `qstat -f`
real naquela hora, o script novo soma 128 nucleos e 384 GB.
"""
import os
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'cluster'))
import em_uso                                              # noqa: E402

# o formato do `qstat -f` do Ubiratan, com a linha de continuacao que o
# Variable_List quebra — ela tem `=` e nao pode virar campo
AMOSTRA = """Job Id: 36735.ubiratan
    Job_Name = lacos
    job_state = R
    Resource_List.mem = 50331648kb
    Resource_List.ncpus = 16
    Resource_List.nodes = 1:ppn=16
    Variable_List = PBS_O_HOME=/home/teste,PBS_O_LANG=en_US.UTF-8,
\tPBS_O_WORKDIR=/home/teste/elder/BDGD2OpenDSS_Validator,

Job Id: 36738.ubiratan
    Job_Name = b_CMIG
    job_state = R
    Resource_List.mem = 96gb
    Resource_List.ncpus = 32

Job Id: 36739.ubiratan
    Job_Name = b_ENCE
    job_state = W
    Resource_List.mem = 24576mb
    Resource_List.ncpus = 8

Job Id: 36740.ubiratan
    Job_Name = b_NEOENERGIA5160
    job_state = H
    Resource_List.mem = 25165824kb
    Resource_List.ncpus = 8

Job Id: 36741.ubiratan
    Job_Name = b_RR
    job_state = Q
    Resource_List.mem = 12gb
    Resource_List.ncpus = 4
"""


class TestSoma(unittest.TestCase):

    def test_r_q_w_contam_e_h_nao(self):
        """H e a proxima base de uma corrente: soma-la contaria a mesma
        corrente varias vezes."""
        self.assertEqual(em_uso.somar(AMOSTRA), (16 + 32 + 8 + 4, 48 + 96 + 24 + 12))

    def test_unidades_de_memoria(self):
        self.assertAlmostEqual(em_uso._gb('50331648kb'), 48.0)
        self.assertAlmostEqual(em_uso._gb('24576mb'), 24.0)
        self.assertAlmostEqual(em_uso._gb('96gb'), 96.0)
        self.assertEqual(em_uso._gb('lixo'), 0.0)

    def test_saida_curta_da_zero_e_nao_quebra(self):
        """A tabela curta — o que o `qstat -u -f` devolvia — nao tem campo
        nenhum. Da zero, e e por isso que o script pede os ids primeiro."""
        curta = ("Job ID          Username Queue    Jobname\n"
                 "36735.ubiratan  teste    BIRA_Q3  lacos\n")
        self.assertEqual(em_uso.somar(curta), (0, 0))

    def test_linha_de_comando(self):
        p = subprocess.run([sys.executable, os.path.join(RAIZ, 'cluster', 'em_uso.py')],
                           input=AMOSTRA, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.split(), ['60', '180'])


class TestOScriptUsa(unittest.TestCase):

    def test_nao_volta_o_u_com_f(self):
        with open(os.path.join(RAIZ, 'cluster', 'submeter_todas.sh'),
                  encoding='utf-8') as fh:
            sh = fh.read()
        self.assertNotIn('qstat -u "$USER" -f', sh)
        self.assertIn('cluster/em_uso.py', sh)
        self.assertIn('DISPONIVEL_GB', sh)


if __name__ == '__main__':
    unittest.main()
