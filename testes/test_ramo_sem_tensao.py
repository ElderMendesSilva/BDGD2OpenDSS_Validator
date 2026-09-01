# -*- coding: utf-8 -*-
"""Ramo isolado se mede por TENSAO, nao pela topologia do OpenDSS.

`Topology.AllIsolatedBranches()` percorre a arvore a partir de UMA fonte. Todo
modelo com mais de uma — e a subestacao com duas barras de MT e comum — reporta
como isolada a rede inteira alimentada pelas demais, que esta energizada e
funcionando.

O projeto JA SABIA DISSO para as cargas: o `validador` tem, desde antes, o
comentario explicando que `AllIsolatedLoads` da falso positivo em massa, e por
isso mantem `cargas_sem_tensao` como a medida boa. `AllIsolatedBranches` tem
exatamente o mesmo defeito e foi usado como medida real ate 01/09/2026 — o que
custou tres achados publicados (12, 16 e 20).

MEDIDO, e por isso este teste existe:

    Light, subestacao 18520353, duas barras de MT
      Topology.AllIsolatedBranches   36.695 de 45.868 linhas   (80%)
      linhas sem tensao                 155 de 45.868          (0,34%)

    300 de 300 linhas "isoladas" tinham 1,02 pu, e so morreram quando a
    segunda fonte foi desligada.

    Nas 4.189 subestacoes da V25: mediana de 0,86% de "isolado" nas de UMA
    fonte, contra 68,88% nas de duas ou mais. Oitenta vezes.

Este teste roda OpenDSS de verdade, sobre um circuito minusculo escrito aqui:
duas fontes, dois trechos vivos e um trecho realmente morto.
"""
import os
import tempfile
import unittest


def _circuito(caminho, com_segunda_fonte):
    """Duas barras de MT, dois trechos vivos, um trecho MORTO de verdade."""
    linhas = [
        'clear',
        'New Circuit.T basekV=13.8 bus1=b0 phases=3 pu=1.0',
        'New Linecode.lc nphases=3 r1=0.3 x1=0.4 units=km',
        'New Line.VIVA1 bus1=b0 bus2=b1 linecode=lc length=1 units=km',
    ]
    if com_segunda_fonte:
        linhas.append('New Vsource.F2 bus1=c0 basekV=13.8 phases=3 pu=1.0')
        linhas.append('New Line.VIVA2 bus1=c0 bus2=c1 linecode=lc length=1 '
                      'units=km')
    # o trecho morto de verdade: nao toca fonte nenhuma
    linhas.append('New Line.MORTA bus1=z0 bus2=z1 linecode=lc length=1 '
                  'units=km')
    linhas += ['set voltagebases=[13.8]', 'calcvoltagebases', 'solve']
    with open(caminho, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(linhas) + '\n')
    return caminho


def _mede(com_segunda_fonte):
    import opendssdirect as dss
    d = tempfile.mkdtemp()
    arq = _circuito(os.path.join(d, 'm.dss'), com_segunda_fonte)
    dss.Text.Command('compile "%s"' % arq)
    # o OpenDSS devolve uma entrada VAZIA junto; contar sem filtrar inflaria
    # a medida velha em um, e o teste mediria o artefato em vez do defeito.
    topo = [x for x in dss.Topology.AllIsolatedBranches() if x.strip()]
    mortas = set()
    for b in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(b)
        v = dss.Bus.VMagAngle()[0::2]
        if not v or max(v) < 1.0:
            mortas.add(b.lower())
    sem_v = 0
    i = dss.Lines.First()
    while i:
        if dss.Lines.Bus1().split('.')[0].lower() in mortas:
            sem_v += 1
        i = dss.Lines.Next()
    return topo, sem_v


class ATopologiaMenteQuandoHaMaisDeUmaFonte(unittest.TestCase):

    def test_com_UMA_fonte_as_duas_medidas_concordam(self):
        """A linha de base: sem segunda fonte, o defeito nao aparece."""
        topo, sem_v = _mede(com_segunda_fonte=False)
        self.assertEqual(sem_v, 1, 'so a MORTA esta sem tensao')
        self.assertEqual([x.lower() for x in topo], ['line.morta'],
                         'com uma fonte, a topologia concorda')

    def test_com_DUAS_fontes_a_topologia_acusa_rede_VIVA(self):
        """O defeito, em miniatura: `VIVA2` esta energizada pela segunda fonte
        e mesmo assim entra em `AllIsolatedBranches`."""
        topo, sem_v = _mede(com_segunda_fonte=True)
        self.assertEqual(sem_v, 1, 'eletricamente, so a MORTA esta morta')
        baixo = sorted(x.lower() for x in topo)
        self.assertEqual(baixo, ['line.morta', 'line.viva2'],
                         'VIVA2 esta energizada e mesmo assim entra na lista')

    def test_a_medida_eletrica_nao_muda_com_a_segunda_fonte(self):
        """O que torna a medida confiavel: ela independe de quantas fontes o
        modelo tem, que e exatamente onde a outra falha."""
        _, sem_uma = _mede(com_segunda_fonte=False)
        _, sem_duas = _mede(com_segunda_fonte=True)
        self.assertEqual(sem_uma, sem_duas)


if __name__ == '__main__':
    unittest.main()
