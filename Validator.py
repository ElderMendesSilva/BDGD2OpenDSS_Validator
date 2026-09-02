# -*- coding: utf-8 -*-
"""
MENU — a porta de entrada do projeto
====================================

    python Validator.py

Uma janela com as sete ferramentas na ordem em que se usa, cada uma com o
que faz e o que ela exige que ja exista. Clicar abre a ferramenta num
processo proprio: ela pergunta os parametros na propria janelinha e o que
ela imprime aparece aqui, ao vivo.

Por que num processo separado, e nao importando o modulo: o OpenDSS via COM
e apartment-threaded e o Compile TROCA o diretorio de trabalho do processo.
Rodar tudo no mesmo interpretador ja fez uma ferramenta corromper o caminho
da seguinte. Processo proprio isola isso de graca — e permite matar uma
rodada travada sem derrubar o menu.

A ordem da lista e a ordem do trabalho:

    converter -> verifica -> validador -> energia -> valida_perdas
                                            \\-> analise_com / painel
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

# nome, script, o que faz, o que precisa existir antes
FERRAMENTAS = [
    ('Converter a BDGD', 'etapas/converter.py',
     'Lê o .gdb e gera os modelos OpenDSS — um MASTER por subestação mais o '
     'MASTER-GERAL com a alta tensão.',
     'a BDGD (.gdb). Leva ~50 min para a concessão inteira.'),
    ('Religar a rede sem tensão  (premissa)', 'etapas/ligacao.py',
     'PREMISSA DE MODELAGEM: liga a barra de MT da subestação à rede que '
     'ficou desenergizada. INVENTA um elo que a BDGD não declara — escreve '
     'em _LIGACAO.dss, que dá para apagar. Elo que faz divergir é recusado.',
     'os modelos gerados. Rode ANTES da ampacidade: religar muda a corrente.'),
    ('Trocar condutor sobrecarregado  (premissa)', 'etapas/ampacidade.py',
     'PREMISSA DE MODELAGEM: troca a resistência do trecho cuja corrente '
     'calculada excede a ampacidade declarada. Escreve em _AMPACIDADE.dss, '
     'que dá para apagar.',
     'os modelos gerados, e a ligação já rodada se for usá-la.'),
    ('Verificar as subestações', 'etapas/verifica.py',
     'Compila e resolve cada subestação nos DOIS motores do OpenDSS e aponta '
     'NaN, não convergência e falha de compilação.',
     'os modelos gerados. É o primeiro teste depois de converter.'),
    ('Validar (causa raiz)', 'etapas/validador.py',
     'Classifica o que está fora do esperado e separa defeito do conversor '
     'de característica da rede.',
     'os modelos gerados.'),
    ('Energia e perdas do dia', 'etapas/energia.py',
     'Roda as 24 h em passos de 15 min e integra energia e perdas por '
     'alimentador. Escreve o energia_dia.json.',
     'os modelos gerados. É o passo mais demorado depois da conversão.'),
    ('Validar as perdas', 'etapas/valida_perdas.py',
     'Cruza a perda do modelo com a declarada na CTMT (PERD_A4 + PERD_B + '
     'PERD_A4_B), alimentador a alimentador.',
     'o energia_dia.json (rode antes "Energia e perdas do dia") e a BDGD.'),
    ('Validar o balanço de energia', 'etapas/valida_balanco.py',
     'Confronta a perda técnica do modelo com a energia MEDIDA na BDGD — '
     'injetada contra faturada — e separa o modelo impossível da medição '
     'degenerada.',
     'o energia_dia.json e a BDGD.'),
    ('Análise e gráficos (COM)', 'etapas/analise_com.py',
     'Resolve um MASTER pelo motor da EPRI e desenha o traçado geográfico, '
     'o perfil de tensão, o carregamento e as perdas.',
     'um arquivo MASTER. Exige pywin32 e matplotlib.'),
    ('Painel da rede', 'painel.py',
     'Janela com todas as subestações listadas: validar uma ou todas, ver as '
     'figuras e abrir o Plot nativo do OpenDSS.',
     'os modelos gerados.'),
    ('Pausar / retomar o ciclo', 'etapas/pausa.py',
     'Segura um ciclo em andamento sem cancelar nada: as subestações em '
     'andamento terminam, nenhuma nova começa, e retomar continua de onde '
     'parou. Serve para quando a máquina for necessária para outra coisa.',
     'um ciclo rodando — ou nada, se for só para ver o estado.'),
    ('CICLO COMPLETO de todas as bases', 'regerar_v10.py',
     'Roda tudo acima, na ordem, para TODAS as .gdb encontradas na pasta — '
     'hoje 99 distribuidoras: converter, as duas premissas, verificar, '
     'energia, validador, as duas validações e o relatório visual. Retoma de '
     'onde parou e grava o resumo por base.',
     'as .gdb no disco. É o ciclo de horas — deixe rodando.'),
]


def _sufixo_novo():
    """Um nome de rodada que nao existe ainda.

    A saida vai para `MODELOS_<BASE>_<SUFIXO>`, e gravar por cima da rodada
    anterior apaga a unica coisa com que comparar. No modo simples ninguem
    quer pensar nisso, entao o proximo livre e escolhido aqui.
    """
    import glob
    usados = set()
    for d in glob.glob(os.path.join(RAIZ, 'MODELOS_*')):
        parte = os.path.basename(d).rsplit('_', 1)[-1]
        if parte.upper().startswith('V') and parte[1:].isdigit():
            usados.add(int(parte[1:]))
    return 'V%d' % ((max(usados) + 1) if usados else 1)


def _pasta_das_bases():
    """Onde procurar a `.gdb` — a mesma lista que o `regerar` usa."""
    v = os.environ.get('BDGD2DSS_BASES')
    if v:
        for p in v.split(os.pathsep):
            if os.path.isdir(p):
                return p
    return os.path.expanduser('~')


class Menu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BDGD → OpenDSS')
        # os sete cartoes pedem ~700 px; abrir menor do que a soma deles com o
        # log espremeria justamente o log, que e o ultimo a ser empacotado
        self.geometry('1040x900')
        self.minsize(880, 620)
        self.fila = queue.Queue()
        self.proc = None
        self._monta()
        self.after(120, self._drena)

    def _monta(self):
        cab = ttk.Frame(self, padding=(14, 12, 14, 6))
        cab.pack(fill='x')
        ttk.Label(cab, text='BDGD → OpenDSS',
                  font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(cab, text='Escolha a .gdb e clique em Rodar. O resto é para '
                            'quando a pergunta for técnica.',
                  foreground='#555').pack(anchor='w')

        # ------------------------------------------------- AREA COM ROLAGEM
        # OS DOZE CARTOES NAO CABEM NA TELA, e sem rolagem o log — que fica
        # abaixo deles — era inalcancavel: a janela mostrava as ferramentas e
        # escondia justamente a resposta do que se mandou rodar.
        #
        # O `Canvas` e o unico jeito de rolar um conjunto de widgets no Tk. A
        # roda do mouse NAO vem de graca: precisa de `bind` explicito, e o
        # nome do evento muda entre Windows (`<MouseWheel>`) e Linux
        # (`<Button-4>`/`<Button-5>`).
        fora = ttk.Frame(self)
        fora.pack(fill='both', expand=True)
        tela = tk.Canvas(fora, highlightthickness=0)
        rolagem = ttk.Scrollbar(fora, orient='vertical', command=tela.yview)
        tela.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side='right', fill='y')
        tela.pack(side='left', fill='both', expand=True)

        corpo = ttk.Frame(tela, padding=(14, 0, 14, 6))
        janela = tela.create_window((0, 0), window=corpo, anchor='nw')

        def _ajusta(_=None):
            tela.configure(scrollregion=tela.bbox('all'))
            tela.itemconfigure(janela, width=tela.winfo_width())

        corpo.bind('<Configure>', _ajusta)
        tela.bind('<Configure>', _ajusta)

        def _roda_mouse(ev):
            if ev.num == 4:
                tela.yview_scroll(-3, 'units')
            elif ev.num == 5:
                tela.yview_scroll(3, 'units')
            else:
                tela.yview_scroll(int(-1 * (ev.delta / 40)), 'units')

        for ev in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.bind_all(ev, _roda_mouse)

        # ------------------------------------------------------------ SIMPLES
        # A PORTA DE ENTRADA E UMA SO PERGUNTA: qual .gdb. Ate 02/09/2026 esta
        # tela abria com doze cartoes tecnicos e nenhuma indicacao de por onde
        # comecar — quem so queria rodar uma base tinha de saber que "CICLO
        # COMPLETO" era o decimo segundo, e que os onze acima sao etapas DELE.
        simples = ttk.LabelFrame(corpo, text=' O CAMINHO NORMAL ', padding=14)
        simples.pack(fill='x', pady=(0, 12))
        ttk.Label(simples, text='Escolha a .gdb. O resto é automático.',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(simples,
                  text='Converte, religa a rede sem tensão, troca condutor '
                       'sobrecarregado, verifica nos dois motores, roda as '
                       '24 h em passos de 15 min, valida e grava o relatório '
                       '— figuras e PDF — dentro da pasta de cada subestação.',
                  wraplength=940, justify='left',
                  foreground='#444').pack(anchor='w', pady=(4, 10))
        linha = ttk.Frame(simples)
        linha.pack(fill='x')
        self.gdb = tk.StringVar()
        ttk.Label(linha, text='Arquivo .gdb:').pack(side='left')
        ttk.Entry(linha, textvariable=self.gdb, width=72).pack(
            side='left', padx=6, fill='x', expand=True)
        ttk.Button(linha, text='Procurar…', width=12,
                   command=self._escolhe_gdb).pack(side='left', padx=(0, 6))
        b = ttk.Button(linha, text='RODAR TUDO', width=18,
                       command=self._roda_simples)
        b.pack(side='left')
        ttk.Label(simples,
                  text='Sem escolher arquivo, roda TODAS as .gdb encontradas '
                       'na pasta de bases — são horas.',
                  foreground='#888', font=('Segoe UI', 8)).pack(anchor='w',
                                                               pady=(6, 0))

        # ----------------------------------------------------------- AVANCADO
        self.avancado_aberto = tk.BooleanVar(value=False)
        self.b_avancado = ttk.Button(
            corpo, text='▸  Avançado — as %d etapas, uma a uma'
                        % len(FERRAMENTAS),
            command=self._alterna_avancado)
        self.b_avancado.pack(anchor='w', pady=(0, 6))

        self.lista = ttk.Frame(corpo)
        lista = self.lista
        for i, (nome, script, faz, precisa) in enumerate(FERRAMENTAS):
            cx = ttk.Frame(lista, relief='groove', borderwidth=1, padding=8)
            cx.grid(row=i // 2, column=i % 2, sticky='nsew', padx=4, pady=4)
            ttk.Label(cx, text=f'{i+1}. {nome}',
                      font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            ttk.Label(cx, text=faz, wraplength=420, justify='left',
                      foreground='#444').pack(anchor='w', pady=(2, 0))
            ttk.Label(cx, text='precisa de: ' + precisa, wraplength=420,
                      justify='left', foreground='#888',
                      font=('Segoe UI', 8)).pack(anchor='w', pady=(2, 4))
            ttk.Button(cx, text='Abrir', width=12,
                       command=lambda s=script, n=nome: self.roda(s, n)
                       ).pack(anchor='w')
        lista.columnconfigure(0, weight=1)
        lista.columnconfigure(1, weight=1)

        # O LOG FICA FORA DA AREA ROLAVEL, com altura propria: dentro dela
        # ele rolaria junto com os cartoes e sumiria da vista justamente
        # quando comecasse a imprimir.
        rodape = ttk.Frame(self, padding=(14, 0, 14, 8))
        rodape.pack(fill='both', side='bottom')
        barra = ttk.Frame(rodape)
        barra.pack(fill='x', pady=(8, 2))
        self.b_parar = ttk.Button(barra, text='Interromper', width=14,
                                  command=self.parar, state='disabled')
        self.b_parar.pack(side='left')
        ttk.Button(barra, text='Limpar', width=10,
                   command=lambda: self.log.delete('1.0', 'end')).pack(side='left', padx=6)
        ttk.Button(barra, text='Abrir a pasta do projeto',
                   command=lambda: os.startfile(RAIZ)).pack(side='left')
        self.status = ttk.Label(barra, text='pronto', foreground='#666')
        self.status.pack(side='right')

        # 8 LINHAS NAO DAVAM PARA LER: uma conversao imprime uma linha por
        # subestacao, e o que interessa some antes de ser lido. 22 linhas
        # mostram uma base pequena inteira sem rolar.
        self.log = tk.Text(rodape, wrap='none', height=14, bg='#1e1e1e',
                           fg='#d4d4d4', insertbackground='#d4d4d4',
                           font=('Consolas', 9))
        sb = ttk.Scrollbar(rodape, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)

    # ------------------------------------------------------------- execucao
    def escreve(self, txt):
        """Uma linha no log, do lado de quem clicou."""
        self._diz(txt.rstrip())

    def _escolhe_gdb(self):
        """A `.gdb` e uma PASTA, e nao um arquivo — quem procura por arquivo
        nao acha nada e conclui que o programa esta quebrado."""
        from tkinter import filedialog
        d = filedialog.askdirectory(
            title='Escolha a .gdb (é uma pasta)',
            initialdir=_pasta_das_bases(), mustexist=True)
        if d:
            self.gdb.set(d)

    def _roda_simples(self):
        """Uma base, ou todas, com os padroes medidos."""
        alvo = self.gdb.get().strip()
        args = ['--sufixo', _sufixo_novo()]
        if alvo:
            if not os.path.isdir(alvo):
                self.escreve('\nEssa pasta .gdb nao existe: %s\n' % alvo)
                return
            # `--so` espera a TAG, e o `regerar` a deriva do nome do arquivo
            import regerar_v10 as rg
            tag = rg._sigla(alvo)[0]
            args += ['--so', tag]
            self.escreve('\nRodando %s (%s)\n'
                         % (tag, os.path.basename(alvo)))
        else:
            self.escreve('\nRodando TODAS as bases encontradas — sao horas.\n')
        self.roda('regerar_v10.py', 'Ciclo completo', args)

    def _alterna_avancado(self):
        aberto = not self.avancado_aberto.get()
        self.avancado_aberto.set(aberto)
        if aberto:
            self.lista.pack(fill='x', before=self.b_avancado)
            self.b_avancado.config(text='▾  Avançado — ocultar as etapas')
        else:
            self.lista.pack_forget()
            self.b_avancado.config(
                text='▸  Avançado — as %d etapas, uma a uma' % len(FERRAMENTAS))

    def roda(self, script, nome, args=None):
        if self.proc and self.proc.poll() is None:
            self._diz('!! já há uma ferramenta rodando — interrompa antes.')
            return
        self._diz(f'\n===== {nome}  ({script}) =====')
        env = dict(os.environ)
        # sem isto, acento impresso pelo filho vira UnicodeEncodeError quando
        # a saida e um cano em vez do console
        env['PYTHONIOENCODING'] = 'utf-8'
        # -u: sem buffer, senao a saida so aparece quando o script termina e a
        # janela parece travada durante uma hora de conversao
        self.proc = subprocess.Popen(
            [sys.executable, '-u', os.path.join(RAIZ, script)] + list(args or []),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=RAIZ, env=env, text=True, encoding='utf-8', errors='replace')
        self.b_parar.configure(state='normal')
        self.status.configure(text=f'{nome} rodando...')
        threading.Thread(target=self._le, args=(self.proc, nome),
                         daemon=True).start()

    def _le(self, p, nome):
        for linha in p.stdout:
            self.fila.put(linha.rstrip('\n'))
        p.wait()
        self.fila.put(f'===== {nome}: fim (código {p.returncode}) =====')
        self.fila.put('__FIM__')

    def parar(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._diz('-- interrompido --')

    def _diz(self, s):
        self.fila.put(s)

    def _drena(self):
        try:
            while True:
                s = self.fila.get_nowait()
                if s == '__FIM__':
                    self.b_parar.configure(state='disabled')
                    self.status.configure(text='pronto')
                else:
                    self.log.insert('end', s + '\n')
                    self.log.see('end')
        except queue.Empty:
            pass
        self.after(120, self._drena)


if __name__ == '__main__':
    Menu().mainloop()
