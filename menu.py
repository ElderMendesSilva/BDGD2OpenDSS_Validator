# -*- coding: utf-8 -*-
"""
MENU — a porta de entrada do projeto
====================================

    python menu.py

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
    ('Converter a BDGD', 'converter.py',
     'Lê o .gdb e gera os modelos OpenDSS — um MASTER por subestação mais o '
     'MASTER-GERAL com a alta tensão.',
     'a BDGD (.gdb). Leva ~50 min para a concessão inteira.'),
    ('Religar a rede sem tensão  (premissa)', 'ligacao.py',
     'PREMISSA DE MODELAGEM: liga a barra de MT da subestação à rede que '
     'ficou desenergizada. INVENTA um elo que a BDGD não declara — escreve '
     'em _LIGACAO.dss, que dá para apagar. Elo que faz divergir é recusado.',
     'os modelos gerados. Rode ANTES da ampacidade: religar muda a corrente.'),
    ('Trocar condutor sobrecarregado  (premissa)', 'ampacidade.py',
     'PREMISSA DE MODELAGEM: troca a resistência do trecho cuja corrente '
     'calculada excede a ampacidade declarada. Escreve em _AMPACIDADE.dss, '
     'que dá para apagar.',
     'os modelos gerados, e a ligação já rodada se for usá-la.'),
    ('Verificar as subestações', 'verifica.py',
     'Compila e resolve cada subestação nos DOIS motores do OpenDSS e aponta '
     'NaN, não convergência e falha de compilação.',
     'os modelos gerados. É o primeiro teste depois de converter.'),
    ('Validar (causa raiz)', 'validador.py',
     'Classifica o que está fora do esperado e separa defeito do conversor '
     'de característica da rede.',
     'os modelos gerados.'),
    ('Energia e perdas do dia', 'energia.py',
     'Roda as 24 h em passos de 15 min e integra energia e perdas por '
     'alimentador. Escreve o energia_dia.json.',
     'os modelos gerados. É o passo mais demorado depois da conversão.'),
    ('Validar as perdas', 'valida_perdas.py',
     'Cruza a perda do modelo com a declarada na CTMT (PERD_A4 + PERD_B + '
     'PERD_A4_B), alimentador a alimentador.',
     'o energia_dia.json (rode antes "Energia e perdas do dia") e a BDGD.'),
    ('Validar o balanço de energia', 'valida_balanco.py',
     'Confronta a perda técnica do modelo com a energia MEDIDA na BDGD — '
     'injetada contra faturada — e separa o modelo impossível da medição '
     'degenerada.',
     'o energia_dia.json e a BDGD.'),
    ('Análise e gráficos (COM)', 'analise_com.py',
     'Resolve um MASTER pelo motor da EPRI e desenha o traçado geográfico, '
     'o perfil de tensão, o carregamento e as perdas.',
     'um arquivo MASTER. Exige pywin32 e matplotlib.'),
    ('Painel da rede', 'painel.py',
     'Janela com todas as subestações listadas: validar uma ou todas, ver as '
     'figuras e abrir o Plot nativo do OpenDSS.',
     'os modelos gerados.'),
    ('Pausar / retomar o ciclo', 'pausa.py',
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
        ttk.Label(cab, text='Escolha a ferramenta. Ela pergunta os parâmetros '
                            'na própria janela e o resultado aparece abaixo.',
                  foreground='#555').pack(anchor='w')

        corpo = ttk.Frame(self, padding=(14, 0, 14, 6))
        corpo.pack(fill='both', expand=True)

        lista = ttk.Frame(corpo)
        lista.pack(fill='x')
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

        barra = ttk.Frame(corpo)
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

        self.log = tk.Text(corpo, wrap='none', height=8, bg='#1e1e1e',
                           fg='#d4d4d4', insertbackground='#d4d4d4',
                           font=('Consolas', 9))
        sb = ttk.Scrollbar(corpo, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)

    # ------------------------------------------------------------- execucao
    def roda(self, script, nome):
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
            [sys.executable, '-u', os.path.join(RAIZ, script)],
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
