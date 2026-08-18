# -*- coding: utf-8 -*-
"""
BDGD -> OpenDSS — interface grafica

    python app.py

Selecione a BDGD e a pasta de saida, ajuste as opcoes e clique em Converter.
A conversao roda em thread separada, com log ao vivo e botao de cancelar.

A BDGD pode vir como:
  - pasta .gdb  (formato nativo do File Geodatabase)
  - arquivo .zip / .gdz  (a pasta .gdb compactada — e descompactada automaticamente)
"""
import os, sys, io, time, queue, zipfile, tempfile, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

MESES = ['01 janeiro', '02 fevereiro', '03 marco', '04 abril', '05 maio', '06 junho',
         '07 julho', '08 agosto', '09 setembro', '10 outubro', '11 novembro', '12 dezembro']
DIAS = [('DU', 'Dia util'), ('SA', 'Sabado'), ('DO', 'Domingo')]


class Redirecionador(io.TextIOBase):
    """Manda os print() do conversor para a fila da interface."""

    def __init__(self, fila):
        self.fila = fila

    def write(self, s):
        if s.strip():
            self.fila.put(s.rstrip('\n'))
        return len(s)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BDGD → OpenDSS')
        self.geometry('880x620')
        self.minsize(760, 540)
        self.fila = queue.Queue()
        self.worker = None
        self.cancelar = threading.Event()
        self.tmpdir = None
        self._monta()
        self.after(100, self._drena_fila)

    # ------------------------------------------------------------------ layout
    def _monta(self):
        pad = {'padx': 8, 'pady': 4}

        # --- entrada e saida
        f1 = ttk.LabelFrame(self, text='Arquivos')
        f1.pack(fill='x', **pad)

        ttk.Label(f1, text='BDGD:').grid(row=0, column=0, sticky='w', padx=6, pady=6)
        self.v_gdb = tk.StringVar()
        ttk.Entry(f1, textvariable=self.v_gdb).grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Button(f1, text='Pasta .gdb…', command=self._sel_gdb_pasta, width=13
                   ).grid(row=0, column=2, padx=2)
        ttk.Button(f1, text='Zip / .gdz…', command=self._sel_gdb_zip, width=12
                   ).grid(row=0, column=3, padx=(2, 6))

        ttk.Label(f1, text='Saída:').grid(row=1, column=0, sticky='w', padx=6, pady=6)
        self.v_out = tk.StringVar(value=os.path.join(AQUI, 'MODELOS'))
        ttk.Entry(f1, textvariable=self.v_out).grid(row=1, column=1, sticky='ew', padx=4)
        ttk.Button(f1, text='Escolher…', command=self._sel_saida, width=13
                   ).grid(row=1, column=2, padx=2, pady=(0, 6))
        f1.columnconfigure(1, weight=1)

        # --- opcoes
        f2 = ttk.LabelFrame(self, text='Opções')
        f2.pack(fill='x', **pad)

        ttk.Label(f2, text='Subestações:').grid(row=0, column=0, sticky='w', padx=6, pady=6)
        self.v_se = tk.StringVar()
        e = ttk.Entry(f2, textvariable=self.v_se)
        e.grid(row=0, column=1, columnspan=3, sticky='ew', padx=4)
        ttk.Label(f2, text='vazio = todas   •   ex.: DEMB DGNA DCAM',
                  foreground='#666').grid(row=0, column=4, sticky='w', padx=6)

        ttk.Label(f2, text='Mês:').grid(row=1, column=0, sticky='w', padx=6, pady=6)
        self.v_mes = tk.StringVar(value=MESES[0])
        ttk.Combobox(f2, textvariable=self.v_mes, values=MESES, state='readonly', width=14
                     ).grid(row=1, column=1, sticky='w', padx=4)

        ttk.Label(f2, text='Tipo de dia:').grid(row=1, column=2, sticky='e', padx=6)
        self.v_dia = tk.StringVar(value='DU')
        ttk.Combobox(f2, textvariable=self.v_dia, values=[f'{a} — {b}' for a, b in DIAS],
                     state='readonly', width=16).grid(row=1, column=3, sticky='w', padx=4)
        self.v_dia.set(f'{DIAS[0][0]} — {DIAS[0][1]}')

        ttk.Label(f2, text='Fator de carga:').grid(row=2, column=0, sticky='w', padx=6, pady=6)
        self.v_fator = tk.DoubleVar(value=1.0)
        ttk.Spinbox(f2, from_=0.5, to=3.0, increment=0.1, textvariable=self.v_fator, width=8
                    ).grid(row=2, column=1, sticky='w', padx=4)
        ttk.Label(f2, text='> 1,0 estressa a ampacidade (útil para NSGA-II)',
                  foreground='#666').grid(row=2, column=2, columnspan=3, sticky='w', padx=6)

        ttk.Label(f2, text='Baixa tensão:').grid(row=3, column=0, sticky='w', padx=6, pady=6)
        self.v_bt = tk.StringVar(value='agregado')
        ttk.Combobox(f2, textvariable=self.v_bt, state='readonly', width=14,
                     values=['agregado', 'completo', 'nenhum']
                     ).grid(row=3, column=1, sticky='w', padx=4)
        ttk.Label(f2, text='agregado: carga no secundário do trafo (use este). '
                          'completo: uma carga por UC — só para tensão de atendimento',
                  foreground='#666', wraplength=420, justify='left'
                  ).grid(row=3, column=2, columnspan=3, sticky='w', padx=6)

        self.v_semat = tk.BooleanVar(value=False)
        ttk.Checkbutton(f2, text='Não gerar a alta tensão nem o MASTER-GERAL',
                        variable=self.v_semat).grid(row=4, column=1, columnspan=3,
                                                    sticky='w', padx=4, pady=(0, 8))
        f2.columnconfigure(1, weight=1)

        # --- desempenho
        #
        # Estes dois numeros saíram de medição, não de palpite, e a explicação
        # ao lado de cada um é o que evita que alguém os mexa no escuro.
        f4 = ttk.LabelFrame(self, text='Desempenho')
        f4.pack(fill='x', **pad)

        ttk.Label(f4, text='Alimentadores por leitura:').grid(
            row=0, column=0, sticky='w', padx=6, pady=6)
        self.v_maxctmt = tk.IntVar(value=850)
        ttk.Spinbox(f4, from_=50, to=900, increment=50, width=8,
                    textvariable=self.v_maxctmt).grid(row=0, column=1,
                                                      sticky='w', padx=4)
        ttk.Label(f4, text='a BDGD não tem índice: cada leitura varre a tabela '
                          'inteira, então lê-se muita coisa de uma vez. '
                          'Maior = menos varreduras e mais memória. '
                          'O limite do formato é 900',
                  foreground='#666', wraplength=430, justify='left'
                  ).grid(row=0, column=2, columnspan=3, sticky='w', padx=6)

        ttk.Label(f4, text='Subestações em paralelo:').grid(
            row=1, column=0, sticky='w', padx=6, pady=6)
        self.v_jobs = tk.IntVar(value=8)
        ttk.Spinbox(f4, from_=1, to=32, increment=1, width=8,
                    textvariable=self.v_jobs).grid(row=1, column=1,
                                                   sticky='w', padx=4)
        ttk.Label(f4, text=f'usado na validação e nas premissas, não na '
                           f'conversão. Esta máquina tem {os.cpu_count()} '
                           f'núcleos; medido, o ganho satura perto de 8 '
                           f'porque o custo é ler o modelo do disco, não '
                           f'calcular. Use 1 se for usar o computador junto',
                  foreground='#666', wraplength=430, justify='left'
                  ).grid(row=1, column=2, columnspan=3, sticky='w', padx=6)

        self.v_premissas = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f4, text='Aplicar as premissas de modelagem (religar rede sem '
                     'tensão e trocar condutor sobrecarregado)',
            variable=self.v_premissas).grid(row=2, column=0, columnspan=5,
                                            sticky='w', padx=6, pady=(0, 2))
        ttk.Label(f4, text='desmarcado, o modelo reproduz SÓ o que a BDGD '
                           'declara. As duas premissas mudam o resultado e '
                           'ficam escritas em arquivo separado, que dá para '
                           'apagar depois',
                  foreground='#666', wraplength=560, justify='left'
                  ).grid(row=3, column=0, columnspan=5, sticky='w',
                         padx=24, pady=(0, 8))
        f4.columnconfigure(2, weight=1)

        # --- avancado
        #
        # Fica RECOLHIDO. Sao quinze opcoes que quase ninguem toca, e deixa-las
        # abertas empurraria o botao Converter para fora da tela. Mas elas
        # existem na linha de comando, entao tem de existir aqui: opcao que so
        # da para usar por comando nao existe para quem usa o painel.
        self.v_avancado = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text='Mostrar opções avançadas',
                        variable=self.v_avancado,
                        command=self._alterna_avancado).pack(anchor='w',
                                                             padx=12)
        self.f5 = ttk.LabelFrame(self, text='Avançado')

        def _lin(r, rot, var, dica, largura=10):
            ttk.Label(self.f5, text=rot).grid(row=r, column=0, sticky='w',
                                              padx=6, pady=4)
            ttk.Entry(self.f5, textvariable=var, width=largura).grid(
                row=r, column=1, sticky='w', padx=4)
            ttk.Label(self.f5, text=dica, foreground='#666', wraplength=430,
                      justify='left').grid(row=r, column=2, sticky='w', padx=6)

        self.v_kvmt = tk.StringVar(value='13.8')
        self.v_kvat = tk.StringVar(value='88')
        _lin(0, 'Tensão de MT (kV):', self.v_kvmt,
             'usada só quando o código TEN_NOM da BDGD é desconhecido')
        _lin(1, 'Tensão de AT (kV):', self.v_kvat, 'idem, para a alta tensão')

        self.v_irrad = tk.StringVar(value='1.0')
        _lin(2, 'Irradiância:', self.v_irrad,
             '0 a 1. 1,0 = meio-dia de céu claro. Para ponta de carga, use 0')
        self.v_gdfp = tk.StringVar(value='1.0')
        _lin(3, 'Fator de potência da GD:', self.v_gdfp,
             '1,0 é como o inversor opera em campo. 0,92 é a capacidade que o '
             'Módulo 3 exige — só para estudo de reativo')

        self.v_regv = tk.StringVar(value='122')
        self.v_regb = tk.StringVar(value='2')
        self.v_regk = tk.StringVar(value='5000')
        _lin(4, 'Regulador — vreg (V):', self.v_regv,
             'ajuste TÍPICO, não de campo: a BDGD não traz o ajuste real')
        _lin(5, 'Regulador — banda (V):', self.v_regb, '')
        _lin(6, 'Regulador — kVA:', self.v_regk, '')

        self.v_excel = tk.StringVar()
        _lin(7, 'Planilhas da ISA:', self.v_excel,
             'pasta com os dados da transmissora. Sem ela, as subestações de '
             'transmissão usam equivalente', largura=30)
        self.v_clima = tk.StringVar()
        _lin(8, 'Clima medido:', self.v_clima,
             'pasta com Irradiancia_Interpolada/ e Temperatura_Interpolado/. '
             'Sem ela, usa perfil sintético', largura=30)
        self.v_climadist = tk.StringVar(value='390')
        _lin(9, 'Distribuidora do clima:', self.v_climadist,
             'código ANEEL de quem o dado de clima pertence')
        self.v_climaforcar = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.f5, text='Usar o clima medido mesmo sendo de '
                        'outra distribuidora (fica registrado na procedência)',
                        variable=self.v_climaforcar).grid(
                            row=10, column=0, columnspan=3, sticky='w', padx=6)

        self.v_lote = tk.StringVar(value='200')
        _lin(11, 'Subestações por lote:', self.v_lote,
             'teto secundário: quem governa é "alimentadores por leitura", '
             'acima')
        self.v_memmax = tk.StringVar(value='0')
        _lin(12, 'Limite de memória (GB):', self.v_memmax,
             '0 = sem limite. Ao passar, o conversor para limpo e diz onde '
             'retomar')
        self.v_cache = tk.StringVar(value='_cache_ucbt.pkl')
        _lin(13, 'Arquivo de cache:', self.v_cache,
             'a agregação da UCBT é reaproveitada entre execuções', largura=24)
        self.v_refazer = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.f5, text='Refazer as subestações já existentes '
                        '(padrão: pula e continua de onde parou)',
                        variable=self.v_refazer).grid(
                            row=14, column=0, columnspan=3, sticky='w',
                            padx=6, pady=(0, 8))
        self.f5.columnconfigure(2, weight=1)

        # --- acoes
        f3 = self.f_acoes = ttk.Frame(self)
        f3.pack(fill='x', **pad)
        self.b_run = ttk.Button(f3, text='Converter', command=self._iniciar, width=16)
        self.b_run.pack(side='left')
        self.b_stop = ttk.Button(f3, text='Cancelar', command=self._parar,
                                 width=12, state='disabled')
        self.b_stop.pack(side='left', padx=6)
        ttk.Button(f3, text='Abrir pasta de saída', command=self._abrir_saida
                   ).pack(side='left', padx=6)
        self.pb = ttk.Progressbar(f3, mode='indeterminate')
        self.pb.pack(side='right', fill='x', expand=True, padx=(12, 0))

        # --- log
        f4 = ttk.LabelFrame(self, text='Andamento')
        f4.pack(fill='both', expand=True, **pad)
        self.txt = tk.Text(f4, wrap='none', height=16, bg='#1e1e1e', fg='#d4d4d4',
                           insertbackground='#d4d4d4', font=('Consolas', 9))
        sb = ttk.Scrollbar(f4, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.status = tk.StringVar(value='Selecione a BDGD para começar.')
        ttk.Label(self, textvariable=self.status, relief='sunken', anchor='w'
                  ).pack(fill='x', side='bottom')

    def _alterna_avancado(self):
        if self.v_avancado.get():
            self.f5.pack(fill='x', padx=12, pady=(0, 8), before=self.f_acoes)
        else:
            self.f5.pack_forget()

    # ------------------------------------------------------------------ selecao
    def _sel_gdb_pasta(self):
        d = filedialog.askdirectory(title='Selecione a pasta .gdb da BDGD')
        if d:
            if not d.lower().endswith('.gdb'):
                messagebox.showwarning(
                    'Atenção',
                    'A pasta escolhida não termina em .gdb.\n\n'
                    'O File Geodatabase é uma PASTA com esse sufixo, contendo '
                    'arquivos .gdbtable. Confirme se selecionou a pasta certa.')
            self.v_gdb.set(d)
            self._log(f'BDGD: {d}')

    def _sel_gdb_zip(self):
        f = filedialog.askopenfilename(
            title='Selecione o arquivo compactado da BDGD',
            filetypes=[('BDGD compactada', '*.zip *.gdz'), ('Todos', '*.*')])
        if f:
            self.v_gdb.set(f)
            self._log(f'BDGD compactada: {f}')

    def _sel_saida(self):
        d = filedialog.askdirectory(title='Onde salvar os modelos')
        if d:
            self.v_out.set(d)

    def _abrir_saida(self):
        d = self.v_out.get()
        if os.path.isdir(d):
            os.startfile(d) if os.name == 'nt' else os.system(f'xdg-open "{d}"')
        else:
            messagebox.showinfo('Pasta de saída', 'A pasta ainda não existe.')

    # ------------------------------------------------------------------ log
    def _log(self, s):
        self.txt.insert('end', s + '\n')
        self.txt.see('end')

    def _drena_fila(self):
        try:
            while True:
                s = self.fila.get_nowait()
                if s == '__FIM__':
                    self._terminou()
                else:
                    self._log(s)
                    self.status.set(s[:120])
        except queue.Empty:
            pass
        self.after(100, self._drena_fila)

    # ------------------------------------------------------------------ execucao
    def _prepara_gdb(self, caminho):
        """Se vier compactada, descompacta e devolve o caminho da .gdb."""
        if os.path.isdir(caminho):
            return caminho
        if not zipfile.is_zipfile(caminho):
            raise ValueError('O arquivo selecionado não é uma pasta .gdb nem um zip válido.')
        self.fila.put('Descompactando a BDGD (pode demorar alguns minutos)...')
        self.tmpdir = tempfile.mkdtemp(prefix='bdgd_')
        with zipfile.ZipFile(caminho) as z:
            z.extractall(self.tmpdir)
        for raiz, dirs, _ in os.walk(self.tmpdir):
            for d in dirs:
                if d.lower().endswith('.gdb'):
                    p = os.path.join(raiz, d)
                    self.fila.put(f'BDGD extraída em {p}')
                    return p
        raise ValueError('Não encontrei nenhuma pasta .gdb dentro do arquivo.')

    def _iniciar(self):
        gdb = self.v_gdb.get().strip()
        out = self.v_out.get().strip()
        if not gdb:
            messagebox.showerror('Falta a BDGD', 'Selecione a pasta .gdb ou o arquivo compactado.')
            return
        if not out:
            messagebox.showerror('Falta a saída', 'Escolha onde salvar os modelos.')
            return
        self.txt.delete('1.0', 'end')
        self.cancelar.clear()
        self.b_run.configure(state='disabled')
        self.b_stop.configure(state='normal')
        self.pb.start(12)
        self.worker = threading.Thread(target=self._rodar, args=(gdb, out), daemon=True)
        self.worker.start()

    def _parar(self):
        self.cancelar.set()
        self.fila.put('Cancelamento pedido — encerrando após a subestação atual...')

    def _rodar(self, gdb, out):
        t0 = time.time()
        antigo = sys.stdout
        sys.stdout = Redirecionador(self.fila)
        try:
            gdb = self._prepara_gdb(gdb)
            argv = [sys.argv[0], gdb, '--saida', out,
                    '--mes', self.v_mes.get().split()[0],
                    '--dia', self.v_dia.get().split()[0],
                    '--fator-carga', str(self.v_fator.get()),
                    '--bt', self.v_bt.get(),
                    '--max-ctmt', str(self.v_maxctmt.get()),
                    '--kv-mt', self.v_kvmt.get(), '--kv-at', self.v_kvat.get(),
                    '--irradiancia', self.v_irrad.get(),
                    '--gd-fp', self.v_gdfp.get(),
                    '--reg-vreg', self.v_regv.get(),
                    '--reg-band', self.v_regb.get(),
                    '--reg-kva', self.v_regk.get(),
                    '--clima-dist', self.v_climadist.get(),
                    '--lote', self.v_lote.get(),
                    '--memoria-max', self.v_memmax.get(),
                    '--cache', self.v_cache.get()]
            if self.v_excel.get().strip():
                argv += ['--excel', self.v_excel.get().strip()]
            if self.v_clima.get().strip():
                argv += ['--clima', self.v_clima.get().strip()]
            if self.v_climaforcar.get():
                argv.append('--clima-forcar')
            if self.v_refazer.get():
                argv.append('--refazer')
            if self.v_semat.get():
                argv.append('--sem-at')
            ses = self.v_se.get().split()
            if ses:
                argv += ['--se'] + ses

            import converter
            converter.CANCELAR = self.cancelar      # o conversor checa entre as SEs
            sys.argv = argv
            converter.main()
            self.fila.put(f'\nConcluído em {(time.time()-t0)/60:.1f} min.')
        except SystemExit as e:
            self.fila.put(f'\n{e}')
        except Exception:
            self.fila.put('\nERRO:\n' + traceback.format_exc())
        finally:
            sys.stdout = antigo
            self.fila.put('__FIM__')

    def _terminou(self):
        self.pb.stop()
        self.b_run.configure(state='normal')
        self.b_stop.configure(state='disabled')
        self.status.set('Pronto.')


if __name__ == '__main__':
    App().mainloop()
