# -*- coding: utf-8 -*-
"""«Não compila» é pergunta para o motor, e não para a ausência de mensagem.

O `MASTER-*.dss` termina com `Set mode=snap / Solve / CalcVoltagebases /
Solve`, então o `Compile` **executa** essas soluções. Qualquer aviso emitido
ali sobe como exceção — e `Max Control Iterations Exceeded` (#485) é aviso de
SOLUÇÃO, não de montagem.

Medido na safra 2025: das 16 subestações classificadas como «não compila»,
**14 tinham compilado sem problema nenhum**. O rótulo mandava depurar sintaxe
de `.dss` onde o que havia era regulador caçando tape.

O teste certo é se existe circuito. Estes testes fabricam os dois casos — o
modelo que só avisa e o que de fato não monta — e travam a distinção.
"""
import os
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'etapas'))

try:
    import opendssdirect as _dss
except Exception:                                            # noqa: BLE001
    _dss = None


def _escreve(pasta, nome, texto):
    caminho = os.path.join(pasta, nome)
    with open(caminho, 'w', encoding='utf-8') as fh:
        fh.write(texto)
    return caminho


@unittest.skipIf(_dss is None, 'sem opendssdirect')
class OAvisoNaoEFalhaDeCompilacao(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='compila_')
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.d, ignore_errors=True)

    def _valida(self):
        import validador
        return validador.valida(self.d)

    def test_o_modelo_que_so_AVISA_conta_como_compilado(self):
        """Um regulador com banda estreita demais caça tape e estoura as
        iterações de controle. O circuito está inteiro; o aviso é da solução.
        """
        _escreve(self.d, 'MASTER-AVISO.dss', '\n'.join([
            'clear',
            'New Circuit.AVISO basekV=13.8 pu=1.0 phases=3 bus1=fonte',
            '~ MVAsc3=2500 MVAsc1=2000',
            'New Line.L1 bus1=fonte bus2=meio phases=3 r1=0.3 x1=0.4 '
            'length=8 units=km',
            'New Transformer.REG phases=3 windings=2 xhl=0.01 '
            '%loadloss=0.01',
            '~ wdg=1 bus=meio kv=13.8 kva=5000',
            '~ wdg=2 bus=saida kv=13.8 kva=5000',
            # banda absurdamente estreita: o controle nunca assenta
            'New RegControl.RC transformer=REG winding=2 vreg=122 band=0.01 '
            'ptratio=60 delay=1',
            'New Line.L2 bus1=saida bus2=ponta phases=3 r1=0.4 x1=0.5 '
            'length=20 units=km',
            'New Load.C1 bus1=ponta phases=3 kv=13.8 kw=3000 pf=0.92',
            'Set maxcontroliter=3',          # força o estouro
            'Set mode=snap',
            'Solve',
            'CalcVoltagebases',
            'Solve',
            '']))
        r = self._valida()
        self.assertIsNotNone(r)
        self.assertTrue(r.get('compila'),
                        'modelo que apenas avisa foi marcado como «não compila»')
        # e a validação SEGUIU: os campos de medida existem
        self.assertIsNotNone(r.get('n_barras'))
        self.assertGreater(r.get('n_linhas') or 0, 0)

    def test_o_aviso_nao_se_perde(self):
        """Ele é o que explica um `converge=False` logo abaixo — engoli-lo em
        nome de «compila=True» trocaria um rótulo errado por um silêncio."""
        _escreve(self.d, 'MASTER-AVISO2.dss', '\n'.join([
            'clear',
            'New Circuit.AVISO2 basekV=13.8 pu=1.0 phases=3 bus1=fonte',
            'New Line.L1 bus1=fonte bus2=b2 phases=3 r1=0.3 x1=0.4 '
            'length=5 units=km',
            # id repetido: (#266) Duplicate new element definition
            'New Line.L1 bus1=b2 bus2=b3 phases=3 r1=0.3 x1=0.4 '
            'length=5 units=km',
            'New Load.C1 bus1=b2 phases=3 kv=13.8 kw=500 pf=0.92',
            'Set mode=snap',
            'Solve',
            '']))
        r = self._valida()
        self.assertTrue(r.get('compila'),
                        'o modelo abortou ANTES do Solve e por isso reporta '
                        'zero barras — mas tem elementos, e compilou')
        self.assertIn('aviso_compile', r, 'o aviso sumiu')
        self.assertIn('Duplicate', r['aviso_compile'])

    def test_zero_barras_nao_significa_zero_circuito(self):
        """A armadilha que quase entrou na correção.

        `NumBuses` só é preenchido no `Solve`/`MakeBusList`. Um circuito
        inteiro que abortou antes de solucionar reporta ZERO barras — medido:
        o caso do `Line` duplicado dá `NumBuses=0` com `NumCktElements=2`.
        Tivesse eu usado barras, a correção condenaria justamente o modelo que
        para cedo, que é o que mais precisa ser distinguido.
        """
        _escreve(self.d, 'MASTER-CEDO.dss', '\n'.join([
            'clear',
            'New Circuit.CEDO basekV=13.8 pu=1.0 phases=3 bus1=fonte',
            'New Line.LX bus1=fonte bus2=b2 phases=3 r1=0.3 x1=0.4 '
            'length=5 units=km',
            'New Line.LX bus1=b2 bus2=b3 phases=3 r1=0.3 x1=0.4 '
            'length=5 units=km',
            '']))
        r = self._valida()
        self.assertTrue(r.get('compila'))

    def test_o_modelo_que_NAO_MONTA_continua_reprovando(self):
        """A correção não pode virar uma anistia: sem circuito, «não compila»
        continua sendo a resposta certa."""
        _escreve(self.d, 'MASTER-RUIM.dss', '\n'.join([
            'clear',
            'isto nao e um comando de OpenDSS',
            'New Circuit.',                # declaração truncada
            '']))
        r = self._valida()
        self.assertIsNotNone(r)
        self.assertFalse(r.get('compila'),
                         'modelo sem circuito passou como compilado')
        self.assertEqual(r.get('causa'), 'MODELO_QUEBRADO')
        self.assertIn('nao compila', r.get('causa_detalhe', ''))

    def test_o_diretorio_de_trabalho_volta_nos_dois_caminhos(self):
        """O `Compile` faz `chdir`. Já quebrou a rodada inteira duas vezes —
        e o caminho novo (compilou-mas-avisou) é mais um lugar onde esquecer."""
        antes = os.getcwd()
        _escreve(self.d, 'MASTER-RUIM2.dss', 'clear\nlixo\n')
        self._valida()
        self.assertEqual(os.getcwd(), antes)


if __name__ == '__main__':
    unittest.main()
