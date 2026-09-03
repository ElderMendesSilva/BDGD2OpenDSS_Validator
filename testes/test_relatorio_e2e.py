# -*- coding: utf-8 -*-
"""A CAMADA DE APRESENTAÇÃO roda de ponta a ponta e o PDF é conferido por dentro.

    converter -> validador -> energia -> relatorio

POR QUE ISTO FALTAVA E POR QUE DÓI. A suíte protege o cálculo elétrico muito
melhor do que protege o que o leitor vê. Em 02/09/2026, três defeitos da camada
nova escaparam de 900 testes e só apareceram ao rodar em dado real:

  1. o veredicto **aprovava por ausência de dado** — campo vazio não estava na
     lista de falhas, e a subestação saía `ADEQUADO` sem ter sido medida;
  2. a ficha **sumia em silêncio** — quem a chama engole a exceção para não
     derrubar o relatório, então um nome de atributo errado virava uma página
     em branco que ninguém nota;
  3. `ax.set_title(ax.get_title(), ...)` **apagava o título** com string vazia,
     porque `loc='left'` guarda o título em outro lugar.

OS TRÊS TÊM A MESMA FORMA: produzem saída de aparência perfeitamente válida.
Nenhum levanta exceção, nenhum retorna código de erro, e um teste que só
verificasse "rodou sem quebrar" passaria nos três. Por isso este arquivo afere
CONTEÚDO — o número dentro do PDF, o título dentro do PNG, o selo que a tabela
de critérios sustenta.

O QUE ELE NÃO É: não afere estética nem engenharia. A rede mínima perde 97% de
propósito (ver `test_ciclo_completo`); aqui interessa se o que foi medido
CHEGA à página, e não se o número é bonito.
"""
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
import fixture                                           # noqa: E402


def _roda(script, *args):
    """Como PROCESSO, pelo mesmo motivo do `test_ciclo_completo`."""
    caminho = script if os.path.isabs(script) else os.path.join(RAIZ, script)
    return subprocess.run([sys.executable, '-u', caminho] + list(args),
                          cwd=RAIZ, capture_output=True, text=True, timeout=900)


def _um(caminho):
    """O primeiro registro de um JSON que pode ser lista ou dicionario."""
    with open(caminho, encoding='utf-8') as fh:
        d = json.load(fh)
    return d[0] if isinstance(d, list) else list(d.values())[0]


def _texto_do_pdf(caminho):
    """Todo o texto do PDF, ou None se não houver como ler.

    A leitura é opcional de propósito: `pypdf` não está no `requirements.txt`,
    e um teste que exige dependência extra vira um teste que ninguém roda. Sem
    ela, as asserções sobre o conteúdo do PDF são puladas — as dos PNG e as do
    veredicto continuam valendo.
    """
    try:
        from pypdf import PdfReader
    except Exception:                                        # noqa: BLE001
        return None
    try:
        return '\n'.join((p.extract_text() or '') for p in
                         PdfReader(caminho).pages)
    except Exception:                                        # noqa: BLE001
        return None


class ORelatorioSaiInteiro(unittest.TestCase):

    SE = 'SE1'

    @classmethod
    def setUpClass(cls):
        cls.gdb = fixture.garantir()
        cls.saida = tempfile.mkdtemp(prefix='relat_')
        cls.passos = {}
        for nome, args in (
                (os.path.join('etapas', 'converter.py'),
                 (cls.gdb, '--saida', cls.saida)),
                (os.path.join('etapas', 'validador.py'), (cls.saida,)),
                # `--jobs 1`: o pool de processos dentro de um teste em
                # subprocesso já custou trava no Windows, e aqui há uma
                # subestação só — não há o que paralelizar.
                (os.path.join('etapas', 'energia.py'),
                 (cls.saida, '--jobs', '1')),
                ('relatorio.py', (cls.saida,))):
            cls.passos[os.path.basename(nome)] = _roda(nome, *args)
        cls.dest = os.path.join(cls.saida, cls.SE, 'RELATORIO')
        cls.pdf = os.path.join(cls.dest, '_PAINEL.pdf')
        cls.texto = _texto_do_pdf(cls.pdf) if os.path.exists(cls.pdf) else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.saida, ignore_errors=True)

    def _ok(self, nome):
        r = self.passos[nome]
        self.assertEqual(r.returncode, 0, '%s saiu %d:\n%s'
                         % (nome, r.returncode, (r.stdout or '')[-2000:]))

    def _precisa_do_pdf(self):
        if self.texto is None:
            self.skipTest('sem pypdf: o conteúdo do PDF não pode ser lido')

    # ------------------------------------------------------------ a cadeia
    def test_as_quatro_etapas_terminam_bem(self):
        for nome in ('converter.py', 'validador.py', 'energia.py',
                     'relatorio.py'):
            self._ok(nome)

    def test_o_relatorio_escreve_o_pdf_e_o_painel(self):
        """Sair 0 não é ter produzido — a lição do coletor que publicou vazio."""
        for arq in ('_PAINEL.pdf', '_PAINEL.png'):
            caminho = os.path.join(self.dest, arq)
            self.assertTrue(os.path.exists(caminho), arq + ' não foi escrito')
            self.assertGreater(os.path.getsize(caminho), 5000,
                               arq + ' saiu pequeno demais para ter conteúdo')

    def test_toda_figura_do_catalogo_vira_arquivo(self):
        """O catálogo é a promessa; os arquivos são a entrega.

        Acrescentar uma figura ao `PLOTS_SE` e esquecer de ligá-la ao
        desenhista produz exatamente nada, sem erro nenhum.
        """
        import relatorio
        faltando = [c for c, _t in relatorio.PLOTS_SE
                    if not os.path.exists(os.path.join(self.dest, c + '.png'))]
        self.assertEqual(faltando, [], 'figuras do catálogo sem arquivo')

    def test_nenhuma_figura_sai_vazia(self):
        """Uma figura que falhou desenha «falhou: …» e ainda assim é um PNG.

        O tamanho separa a figura com dado da figura com uma frase de erro no
        meio do quadro — a segunda pesa uma fração da primeira.
        """
        import relatorio
        magras = []
        for chave, _t in relatorio.PLOTS_SE:
            p = os.path.join(self.dest, chave + '.png')
            if os.path.exists(p) and os.path.getsize(p) < 6000:
                magras.append((chave, os.path.getsize(p)))
        self.assertEqual(magras, [], 'figuras pequenas demais para ter dado')

    # -------------------------------------------- defeito 3: o título sumido
    def test_cada_figura_carrega_o_proprio_titulo(self):
        """`loc='left'` guarda o título em outro lugar, e reescrevê-lo com o
        que `ax.get_title()` devolve o apaga com uma string vazia.

        No PDF o defeito era invisível, porque ali o título é cabeçalho de
        seção. Só a figura solta o denuncia — e é ela que se põe numa
        apresentação.
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from bdgd2dss import graficos

        sem_titulo = []
        casos = {
            'perfil_de_tensao': ([0, 1, 2, 3], [0.99, 0.98, 0.97, 0.96]),
            'histograma_de_tensao': ([0.99, 0.98, 0.97],),
            'duracao_de_tensao': ([0.99, 0.98, 0.97],),
            'carregamento': ([10.0, 20.0, 30.0],),
            'comprimento_dos_trechos': ([0.03, 0.04, 0.05],),
            'curva_do_dia': ([100] * 96,),
            'duracao_de_carga': ([100, 200] * 48,),
        }
        for nome, args in casos.items():
            f, a = plt.subplots()
            try:
                getattr(graficos, nome)(a, *args)
                if not (a.get_title(loc='left') or a.get_title()):
                    sem_titulo.append(nome)
            finally:
                plt.close(f)
        self.assertEqual(sem_titulo, [], 'figuras sem título')

    # ------------------------------------------ defeito 2: a ficha silenciosa
    def test_a_ficha_chega_ao_pdf_com_numeros(self):
        """A ficha é engolida por um `except` para não derrubar o relatório de
        uma subestação quebrada. O preço é que ela some sem avisar."""
        self._precisa_do_pdf()
        self.assertIn('Ficha do circuito', self.texto)
        for rotulo in ('barras', 'trechos de linha', 'cargas'):
            self.assertIn(rotulo, self.texto, 'a ficha saiu sem «%s»' % rotulo)

    def test_a_ficha_do_dia_traz_os_96_passos(self):
        """Se a etapa de energia rodou, a série tem de chegar à página."""
        self._precisa_do_pdf()
        self.assertIn('passos que convergiram', self.texto)

    # ----------------------------- defeito 1: veredicto sem lastro de medida
    def test_o_veredicto_aparece_e_e_uma_classe_conhecida(self):
        self._precisa_do_pdf()
        from bdgd2dss import veredicto
        achou = [c for c in veredicto.COR if c in self.texto]
        self.assertTrue(achou, 'nenhuma classe de veredicto aparece no PDF')

    def test_o_veredicto_nao_e_inconclusivo_com_a_cadeia_inteira_rodada(self):
        """Este teste é o defeito 1 de cabeça para baixo.

        Rodadas `converter`, `validador` e `energia`, não pode faltar medida.
        `INCONCLUSIVO` aqui significa que o relatório deixou de LER algo que
        foi medido — que foi exatamente o segundo defeito do veredicto, ele
        procurando um campo `veredicto` que o `validador.py` nunca escreveu.
        """
        self._precisa_do_pdf()
        from bdgd2dss import veredicto
        self.assertNotIn(veredicto.INCONCLUSIVO, self.texto,
                         'a cadeia inteira rodou e o veredicto não achou os '
                         'números — alguém renomeou um campo?')

    def test_a_tabela_de_criterios_publica_os_limites(self):
        """Sem o limite ao lado, o selo é uma opinião que não se confere."""
        self._precisa_do_pdf()
        self.assertIn('Fecha eletricamente', self.texto)
        self.assertIn('limite', self.texto.lower())

    def test_o_pdf_diz_para_que_o_modelo_serve(self):
        self._precisa_do_pdf()
        self.assertIn('serve para', self.texto)

    # ----------------------------------------------------- o resto da página
    def test_cada_figura_leva_a_propria_analise(self):
        """Figura sem leitura ao lado obriga quem lê a redescobrir sozinho o
        que ela mostra, e a maior parte das pessoas não redescobre."""
        self._precisa_do_pdf()
        import relatorio
        from bdgd2dss import laudo, ficha
        # COM OS DADOS DA RODADA, e nao com dicionarios vazios. A analise de
        # metade das figuras depende do numero — «se `vmed is None`, devolve
        # vazio» — entao chama-la a seco mede a guarda, e nao a analise. A
        # primeira versao deste teste fazia isso e acusava nove figuras
        # inexistentes.
        v = _um(os.path.join(self.saida, 'validacao.json'))
        e = _um(os.path.join(self.saida, 'energia_dia.json'))
        extra = {'dia': ficha.ficha_do_dia(e.get('serie') or {}),
                 'pct_fora_faixa': 0.0, 'pct_sobrecarga': 0.0}
        faltando = [chave for chave, _t in relatorio.PLOTS_SE
                    if os.path.exists(os.path.join(self.dest, chave + '.png'))
                    and not laudo.analise_da_figura(chave, v, e, {}, extra)]
        # DUAS ISENCOES DECLARADAS, e nao uma lista de excecoes que cresce
        # sozinha sempre que o teste incomoda:
        #
        # `resumo` e `energia` sao paineis de TEXTO — a figura ja E a leitura,
        # e um paragrafo explicando uma tabela seria a tabela de novo.
        isentas = {'resumo', 'energia'}
        # as de GD so tem o que dizer quando ha GD, e a `.gdb` minima nao tem.
        # A figura sai (a curva de geracao zero e um resultado), a analise nao
        # — e o PDF pula a pagina, que e o comportamento certo.
        if not (e.get('kWh_gd') or 0):
            isentas |= {'gd_fluxo', 'gd_cobre'}
        faltando = [c for c in faltando if c not in isentas]
        self.assertEqual(faltando, [],
                         'figuras no catálogo sem análise escrita')

    def test_o_pdf_tem_uma_pagina_por_secao_e_nao_uma_so(self):
        """O painelão empilhado foi o formato anterior, e não se lê."""
        if self.texto is None:
            self.skipTest('sem pypdf')
        from pypdf import PdfReader
        self.assertGreater(len(PdfReader(self.pdf).pages), 8)

    def test_o_relatorio_da_concessao_tambem_sai(self):
        d = os.path.join(self.saida, 'RELATORIO')
        self.assertTrue(os.path.exists(os.path.join(d, '_GERAL.pdf')),
                        'o relatório da concessão não foi escrito')

    def test_o_pdf_da_concessao_nao_morre_em_silencio(self):
        """O defeito que este arquivo achou no dia em que nasceu.

        `pdf_da_concessao` recebeu por acidente uma linha do laço da
        subestação — a substituição de texto casou nos DOIS laços, que eram
        idênticos — e passou a morrer com `name 'achados_daqui' is not
        defined`. Morria em SILÊNCIO: a exceção é impressa e engolida para que
        uma concessão problemática não derrube a rodada inteira.

        O `.png` continuava saindo, então a pasta parecia certa.
        """
        d = os.path.join(self.saida, 'RELATORIO')
        self.assertTrue(os.path.exists(os.path.join(d, '_GERAL.pdf')))
        saida = self.passos['relatorio.py'].stdout or ''
        self.assertNotIn('falhou', saida.lower(),
                         'o relatório imprimiu uma falha engolida:\n'
                         + saida[-1500:])

    def test_os_numeros_do_pdf_batem_com_o_validacao_json(self):
        """A prova de que a página mostra o que foi medido, e não um padrão.

        Uma camada de apresentação que erra o campo produz um PDF impecável
        cheio de travessões — ou, pior, de zeros.
        """
        self._precisa_do_pdf()
        with open(os.path.join(self.saida, 'validacao.json'),
                  encoding='utf-8') as fh:
            d = json.load(fh)
        v = d[0] if isinstance(d, list) else list(d.values())[0]
        n = v.get('n_cargas') or 0
        self.assertGreater(n, 0, 'o fixture perdeu as cargas')
        # o mesmo número, na convenção de milhar do relatório
        self.assertIn('{:,}'.format(n).replace(',', '.'), self.texto,
                      'o total de cargas do validador não aparece no PDF')


if __name__ == '__main__':
    unittest.main()
