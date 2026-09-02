# -*- coding: utf-8 -*-
"""
PAINEL DA REDE — interface COM do OpenDSS, sem linha de comando.

    python painel.py
    python painel.py MODELOS_V3

Uma janela com a lista das subestacoes geradas. Para cada uma:

    Validar          compila, resolve e diz a CAUSA se houver problema
    Analisar         roda a analise COM e gera os graficos
    Plot no OpenDSS  abre o Plot Circuit nativo, com as coordenadas da BDGD
    Perfil           Plot profile do alimentador
    Abrir pasta      no Explorador

E ha o botao "Validar TODAS", que varre a pasta inteira e preenche a coluna
de causa — e a lista do que ainda precisa ser depurado.

Por que tkinter e nao Qt/Dear PyGui/Streamlit
---------------------------------------------
Esta janela faz tres coisas: listar, disparar e mostrar imagem. Para isso:

  tkinter    ja vem no Python, zero instalacao, e o matplotlib tem backend
             nativo (TkAgg). O projeto ja o usa em app.py.
  PySide6    fica visualmente melhor e tem tabela/dock de verdade, mas sao
             ~120 MB de dependencia para ganho estetico.
  DearPyGui  rapido, porem com sistema de graficos proprio: obrigaria a
             reescrever todos os graficos do analise_com.py.
  Streamlit  seria o mais rapido de escrever, mas sobe um servidor web e
             complica o objeto COM (que e apartment-threaded).

O gargalo real nao e o widget e sim desenhar 30 mil segmentos: por isso o
grafico e renderizado em PNG numa thread e exibido como imagem, e a
exploracao interativa fica a cargo do proprio OpenDSS.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

CORES = {
    'OK': '#1a7f37',
    'MODELO_QUEBRADO': '#b3261e',
    'TENSAO_BAIXA': '#b35c00',
    'CARGA_ALTA': '#b35c00',
    'SEM_MEDIDA': '#b3261e',
    'REDE_EXTENSA': '#5b5bd6',
    'REGULADOR_SATURADO': '#5b5bd6',
}

EXPLICA = {
    'OK': 'dentro do esperado',
    'MODELO_QUEBRADO': 'defeito do conversor — acionavel aqui',
    'TENSAO_BAIXA': 'subtensao sem causa identificada — investigar',
    'CARGA_ALTA': 'demanda acima da capacidade instalada',
    'SEM_MEDIDA': 'nenhuma barra de MT com tensao valida',
    'REDE_EXTENSA': 'alimentador muito longo — queda fisicamente correta',
    'REGULADOR_SATURADO': 'reguladores no tape maximo — falta ajuste de campo',
}


class Painel(tk.Tk):
    def __init__(self, pasta=None):
        super().__init__()
        self.title('Rede Enel SP — painel OpenDSS')
        self.geometry('1180x740')
        self.fila = queue.Queue()
        self.pasta = tk.StringVar(value=pasta or '')
        self.dss = None
        self._monta()
        if pasta:
            self.carregar()
        self.after(120, self._drena)

    # ------------------------------------------------------------- layout
    def _monta(self):
        pad = dict(padx=8, pady=6)

        top = ttk.Frame(self)
        top.pack(fill='x', **pad)
        ttk.Label(top, text='Pasta dos modelos:').pack(side='left')
        ttk.Entry(top, textvariable=self.pasta).pack(side='left', fill='x',
                                                     expand=True, padx=6)
        ttk.Button(top, text='Procurar...', command=self._escolher).pack(side='left')
        ttk.Button(top, text='Carregar', command=self.carregar).pack(side='left', padx=4)

        corpo = ttk.Panedwindow(self, orient='horizontal')
        corpo.pack(fill='both', expand=True, **pad)

        esq = ttk.Frame(corpo)
        corpo.add(esq, weight=3)
        cols = ('se', 'alim', 'vmed', 'perdas', 'causa', 'detalhe')
        self.tv = ttk.Treeview(esq, columns=cols, show='headings', height=22)
        for c, t, w in [('se', 'SE', 70), ('alim', 'alim', 50), ('vmed', 'V med', 60),
                        ('perdas', 'perdas %', 70), ('causa', 'causa', 150),
                        ('detalhe', 'detalhe', 330)]:
            self.tv.heading(c, text=t, command=lambda cc=c: self._ordenar(cc))
            self.tv.column(c, width=w, anchor='w')
        self.tv.pack(side='left', fill='both', expand=True)
        self.tv.bind('<<TreeviewSelect>>', self._ao_selecionar)
        sb = ttk.Scrollbar(esq, orient='vertical', command=self.tv.yview)
        sb.pack(side='left', fill='y')
        self.tv.configure(yscrollcommand=sb.set)
        for k, cor in CORES.items():
            self.tv.tag_configure(k, foreground=cor)

        dir_ = ttk.Frame(corpo)
        corpo.add(dir_, weight=2)

        acoes = ttk.LabelFrame(dir_, text='Subestacao selecionada')
        acoes.pack(fill='x', pady=(0, 6))
        for txt, cmd in [('Validar', self.validar_uma),
                         ('Analisar (graficos)', self.analisar),
                         ('Plot Circuit no OpenDSS', self.plot_dss),
                         ('Perfil de tensao no OpenDSS', self.perfil_dss),
                         ('Abrir pasta', self.abrir_pasta)]:
            ttk.Button(acoes, text=txt, command=cmd).pack(fill='x', padx=6, pady=3)

        lote = ttk.LabelFrame(dir_, text='Toda a pasta')
        lote.pack(fill='x', pady=(0, 6))
        ttk.Button(lote, text='Validar TODAS as subestacoes',
                   command=self.validar_todas).pack(fill='x', padx=6, pady=3)
        ttk.Button(lote, text='Analisar TODAS (graficos)',
                   command=self.analisar_todas).pack(fill='x', padx=6, pady=3)
        ttk.Button(lote, text='Exportar diagnostico (CSV)',
                   command=self.exportar).pack(fill='x', padx=6, pady=3)

        val = ttk.LabelFrame(dir_, text='Validacao contra a BDGD')
        val.pack(fill='x', pady=(0, 6))
        ttk.Label(val, text='Energia MEDIDA (injetada − faturada) é o que '
                            'valida. A perda declarada é saída de modelo da '
                            'distribuidora — cruza, não valida.',
                  foreground='#666', wraplength=300, justify='left',
                  font=('Segoe UI', 8)).pack(anchor='w', padx=6, pady=(2, 4))
        ttk.Button(val, text='Balanço de energia  (medição)',
                   command=lambda: self.validar_bdgd('etapas/valida_balanco.py')
                   ).pack(fill='x', padx=6, pady=3)
        ttk.Button(val, text='Perda declarada PERD_*  (cruzamento)',
                   command=lambda: self.validar_bdgd('etapas/valida_perdas.py')
                   ).pack(fill='x', padx=6, pady=3)

        self.abas = ttk.Notebook(dir_)
        self.abas.pack(fill='both', expand=True)

        aba_r = ttk.Frame(self.abas)
        self.abas.add(aba_r, text='Resumo')
        self.resumo = tk.Text(aba_r, wrap='word', bg='#f7f7f7')
        self.resumo.pack(fill='both', expand=True)

        aba_l = ttk.Frame(self.abas)
        self.abas.add(aba_l, text='Log')
        self.log = tk.Text(aba_l, wrap='word', bg='#111', fg='#ddd')
        self.log.pack(fill='both', expand=True)

        # aba com as figuras da analise_com, navegaveis
        aba_f = ttk.Frame(self.abas)
        self.abas.add(aba_f, text='Analise')
        barra = ttk.Frame(aba_f)
        barra.pack(fill='x')
        self.v_fig = tk.StringVar()
        self.cb_fig = ttk.Combobox(barra, textvariable=self.v_fig, state='readonly')
        self.cb_fig.pack(side='left', fill='x', expand=True, padx=4, pady=4)
        self.cb_fig.bind('<<ComboboxSelected>>', lambda e: self._mostra_fig())
        ttk.Button(barra, text='<', width=3,
                   command=lambda: self._passa(-1)).pack(side='left')
        ttk.Button(barra, text='>', width=3,
                   command=lambda: self._passa(1)).pack(side='left', padx=(0, 4))
        ttk.Button(barra, text='Tamanho real',
                   command=self._abrir_fig).pack(side='left', padx=4)
        self.canvas_fig = tk.Label(
            aba_f, background='#fff',
            text='Selecione uma subestacao e clique em "Analisar (graficos)".')
        self.canvas_fig.pack(fill='both', expand=True)
        self.canvas_fig.bind('<Configure>', lambda e: self._mostra_fig())
        self._figs = []
        self._img = None

        self.status = ttk.Label(self, text='pronto', anchor='w')
        self.status.pack(fill='x', side='bottom')

    def _ao_selecionar(self, _=None):
        sel = self.tv.selection()
        if sel:
            self.carregar_figs(self.tv.item(sel[0], 'values')[0])

    # ------------------------------------------------------------ utilidades
    def _escolher(self):
        d = filedialog.askdirectory(title='Pasta com os modelos (MODELOS_V3, ...)')
        if d:
            self.pasta.set(d)
            self.carregar()

    def _diz(self, txt):
        self.fila.put(('log', txt))

    def _drena(self):
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == 'log':
                    self.log.insert('end', dado + '\n')
                    self.log.see('end')
                elif tipo == 'status':
                    self.status.config(text=dado)
                elif tipo == 'linha':
                    self._por_linha(dado)
                elif tipo == 'figs':
                    self.carregar_figs(dado)
                    self.abas.select(2)
                elif tipo == 'resumo':
                    self.resumo.delete('1.0', 'end')
                    self.resumo.insert('1.0', dado)
        except queue.Empty:
            pass
        self.after(120, self._drena)

    def _fundo(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _sel(self):
        s = self.tv.selection()
        if not s:
            messagebox.showinfo('Selecione', 'Escolha uma subestacao na lista.',
                                parent=self)
            return None
        return self.tv.item(s[0], 'values')[0]

    def _master(self, se):
        return os.path.join(self.pasta.get(), se, f'MASTER-{se}.dss')

    def _ordenar(self, col):
        itens = [(self.tv.set(k, col), k) for k in self.tv.get_children('')]
        try:
            itens.sort(key=lambda x: float(x[0]))
        except ValueError:
            itens.sort()
        for i, (_, k) in enumerate(itens):
            self.tv.move(k, '', i)

    # -------------------------------------------------------------- carregar
    def carregar(self):
        p = self.pasta.get()
        if not os.path.isdir(p):
            messagebox.showerror('Pasta', 'Pasta inexistente.', parent=self)
            return
        self.tv.delete(*self.tv.get_children())
        ses = sorted(d for d in os.listdir(p)
                     if os.path.isdir(os.path.join(p, d)) and not d.startswith('_')
                     and os.path.exists(os.path.join(p, d, f'MASTER-{d}.dss')))
        val = {}
        fv = os.path.join(p, 'validacao.json')
        if os.path.exists(fv):
            for enc in ('utf-8', 'latin-1'):
                try:
                    val = {r['modelo']: r for r in json.load(open(fv, encoding=enc))}
                    break
                except Exception:
                    continue
        for se in ses:
            v = val.get(se, {})
            res = {}
            fr = os.path.join(p, se, 'resumo.json')
            if os.path.exists(fr):
                try:
                    res = json.load(open(fr, encoding='utf-8'))
                except Exception:
                    pass
            causa = v.get('causa', '')
            self.tv.insert('', 'end', values=(
                se, res.get('alimentadores', ''), v.get('V_MT_mediana', ''),
                v.get('perdas_pct', ''), causa, v.get('causa_detalhe', '')),
                tags=(causa,) if causa in CORES else ())
        if not ses:
            messagebox.showwarning(
                'Nenhum modelo',
                f'A pasta existe, mas nao contem subestacoes com MASTER-*.dss.\n\n'
                f'Esperado: pasta de MODELOS (ex.: MODELOS_V13), nao a .gdb.\n\n'
                f'Caminho: {p}',
                parent=self)
        self._diz(f'{len(ses)} subestacoes em {p}')
        self._sumario()

    def _sumario(self):
        import collections
        c = collections.Counter(self.tv.set(k, 'causa') or '(nao validada)'
                                for k in self.tv.get_children(''))
        linhas = [f'{sum(c.values())} subestacoes\n']
        for k, v in c.most_common():
            linhas.append(f'  {v:4d}  {k:20s} {EXPLICA.get(k, "")}')
        self.fila.put(('resumo', '\n'.join(linhas)))

    def _por_linha(self, r):
        for k in self.tv.get_children(''):
            if self.tv.set(k, 'se') == r['modelo']:
                self.tv.item(k, values=(
                    r['modelo'], self.tv.set(k, 'alim'),
                    r.get('V_MT_mediana', ''), r.get('perdas_pct', ''),
                    r.get('causa', ''), r.get('causa_detalhe', '')),
                    tags=(r.get('causa', ''),))
                return

    # ------------------------------------------------------------- figuras
    def carregar_figs(self, se):
        """Popula o combo com as figuras que a analise_com gerou."""
        d = os.path.join(self.pasta.get(), se, 'analise')
        self._figs = []
        if os.path.isdir(d):
            self._figs = [os.path.join(d, f) for f in sorted(os.listdir(d))
                          if f.lower().endswith('.png')]
        self.cb_fig['values'] = [os.path.basename(f) for f in self._figs]
        if self._figs:
            self.cb_fig.current(0)
            self._mostra_fig()
        else:
            self.canvas_fig.config(image='',
                                   text='sem figuras — clique em "Analisar (graficos)"')

    def _passa(self, d):
        if not self._figs:
            return
        i = max(0, min(len(self._figs) - 1, self.cb_fig.current() + d))
        self.cb_fig.current(i)
        self._mostra_fig()

    def _mostra_fig(self):
        """Exibe a figura ajustada ao painel.

        Usa PhotoImage.subsample porque o tkinter nao redimensiona sozinho e
        o Pillow nao e dependencia do projeto. subsample so reduz por fator
        inteiro, o que basta para pre-visualizacao — o tamanho real fica no
        botao ao lado, que abre no visualizador do sistema.
        """
        if not self._figs:
            return
        i = self.cb_fig.current()
        if i < 0:
            return
        try:
            img = tk.PhotoImage(file=self._figs[i])
            lw = max(self.canvas_fig.winfo_width(), 200)
            lh = max(self.canvas_fig.winfo_height(), 200)
            fator = max(1, -(-img.width() // lw), -(-img.height() // lh))
            if fator > 1:
                img = img.subsample(fator, fator)
            self._img = img                       # segura a referencia
            self.canvas_fig.config(image=img, text='')
        except Exception as e:
            self.canvas_fig.config(image='', text=f'nao consegui exibir: {e}')

    def _abrir_fig(self):
        if self._figs and self.cb_fig.current() >= 0:
            try:
                os.startfile(self._figs[self.cb_fig.current()])
            except Exception as e:
                self._diz(str(e))

    # -------------------------------------------------------------- acoes
    def validar_uma(self):
        se = self._sel()
        if not se:
            return

        def tarefa():
            import validador
            self.fila.put(('status', f'validando {se}...'))
            r = validador.valida(os.path.join(self.pasta.get(), se))
            if r:
                self._diz(f"{se}: {r.get('causa')} — {r.get('causa_detalhe','')}")
                self._diz(f"   Vmed={r.get('V_MT_mediana')} perdas={r.get('perdas_pct')}% "
                          f"barras={r.get('n_barras')} sobrecarga={r.get('linhas_acima_ampacidade')}")
                self.fila.put(('linha', r))
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    def validar_todas(self):
        def tarefa():
            import validador
            p = self.pasta.get()
            ses = [self.tv.set(k, 'se') for k in self.tv.get_children('')]
            out = []
            for i, se in enumerate(ses, 1):
                self.fila.put(('status', f'validando {se}  ({i}/{len(ses)})'))
                r = validador.valida(os.path.join(p, se))
                if r:
                    out.append(r)
                    self.fila.put(('linha', r))
                    if r.get('acionavel'):
                        self._diz(f"  {se:8s} {r.get('causa','')} — {r.get('causa_detalhe','')[:60]}")
            json.dump(out, open(os.path.join(p, 'validacao.json'), 'w',
                                encoding='utf-8'), indent=1, ensure_ascii=False)
            acion = [r for r in out if r.get('acionavel')]
            self._diz(f'\n{len(out)} validadas | {len(acion)} precisam de acao nossa')
            self._sumario()
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    def validar_bdgd(self, script):
        """Cruza os resultados da pasta com a BDGD de origem.

        Precisa do `energia_dia.json` (vem do energia.py) e do caminho da
        .gdb. O .gdb e pedido uma vez e lembrado pelo `interativo`, para nao
        perguntar a cada clique.
        """
        from bdgd2dss import interativo
        p = self.pasta.get()
        if not os.path.exists(os.path.join(p, 'energia_dia.json')):
            messagebox.showwarning(
                'Falta o energia_dia.json',
                'Este cruzamento compara a energia do dia simulado com a da '
                'BDGD.\n\nRode antes:\n    python energia.py '
                f'"{os.path.basename(p)}"',
                parent=self)
            return
        v = interativo.formulario('painel_bdgd', 'BDGD de origem', [
            {'chave': 'gdb', 'tipo': 'pasta', 'rotulo': 'BDGD (.gdb)',
             'padrao': interativo.bdgd_recente(),
             'dica': 'a mesma base que gerou estes modelos'}],
            ajuda='De onde saem a energia injetada e a faturada.')
        if not v or not v.get('gdb'):
            return

        def tarefa():
            self.fila.put(('status', f'{script} — lendo a BDGD...'))
            r = subprocess.run(
                [sys.executable, '-u', os.path.join(RAIZ, script), p, v['gdb']],
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', cwd=RAIZ)
            saida = (r.stdout or '') + (r.stderr or '')
            for l in saida.splitlines():
                self._diz('  ' + l)
            self.fila.put(('resumo', saida[-4000:]))
            self.abas.select(0)
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    def analisar(self):
        se = self._sel()
        if not se:
            return

        def tarefa():
            self.fila.put(('status', f'analisando {se} (COM)...'))
            m = self._master(se)
            r = subprocess.run([sys.executable, os.path.join(RAIZ, 'etapas/analise_com.py'), m],
                               capture_output=True, text=True, cwd=RAIZ)
            for l in (r.stdout or '').splitlines():
                self._diz('  ' + l)
            if r.returncode:
                self._diz('ERRO: ' + (r.stderr or '')[-600:])
            else:
                self._diz(f"figuras em {os.path.join(os.path.dirname(m), 'analise')}")
                self.fila.put(('figs', se))
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    def analisar_todas(self):
        def tarefa():
            ses = [self.tv.set(k, 'se') for k in self.tv.get_children('')]
            for i, se in enumerate(ses, 1):
                self.fila.put(('status', f'analisando {se} ({i}/{len(ses)})'))
                r = subprocess.run(
                    [sys.executable, os.path.join(RAIZ, 'etapas/analise_com.py'),
                     self._master(se)], capture_output=True, text=True, cwd=RAIZ)
                self._diz(f"  {se}: {'ok' if not r.returncode else 'ERRO'}")
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    # --------------------------------------------------- plot nativo OpenDSS
    def _com(self):
        """Motor COM persistente — o Plot nativo so existe por ele."""
        if self.dss is None:
            import win32com.client
            self.dss = win32com.client.Dispatch('OpenDSSEngine.DSS')
            self.dss.Start(0)
            try:
                self.dss.AllowForms = True      # necessario para abrir a janela
            except Exception:
                pass
        return self.dss

    def _plot(self, se, comando, rotulo):
        def tarefa():
            try:
                d = self._com()
                self.fila.put(('status', f'{rotulo} de {se}...'))
                d.Text.Command = 'Clear'
                d.Text.Command = f'Compile "{self._master(se)}"'
                d.Text.Command = comando
                self._diz(f'{se}: {comando}')
                self._diz('  (a janela do OpenDSS abre por cima; feche-a para continuar)')
            except Exception as e:
                self._diz(f'ERRO no plot: {e}')
            self.fila.put(('status', 'pronto'))
        self._fundo(tarefa)

    def plot_dss(self):
        se = self._sel()
        if se:
            self._plot(se, 'Plot Circuit Power max=2000 dots=n labels=n C1=Blue',
                       'Plot Circuit')

    def perfil_dss(self):
        se = self._sel()
        if se:
            self._plot(se, 'Plot profile phases=all', 'Perfil')

    def abrir_pasta(self):
        se = self._sel()
        if se:
            try:
                os.startfile(os.path.join(self.pasta.get(), se))
            except Exception as e:
                self._diz(str(e))

    def exportar(self):
        import csv
        p = self.pasta.get()
        dest = os.path.join(p, 'diagnostico_por_se.csv')
        cols = ['se', 'alim', 'vmed', 'perdas', 'causa', 'detalhe']
        with open(dest, 'w', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh, delimiter=';')
            w.writerow(['SE', 'alimentadores', 'V_mediana', 'perdas_%', 'causa', 'detalhe'])
            for k in self.tv.get_children(''):
                w.writerow([self.tv.set(k, c) for c in cols])
        self._diz(f'-> {dest}')
        try:
            os.startfile(p)
        except Exception:
            pass


if __name__ == '__main__':
    # A lista fixa de pastas envelhecia a cada regeracao (parou na V3 e o
    # painel abria vazio com a V8 no disco). Agora a escolha e a pasta de
    # modelos mais recente que de fato tem MASTER dentro.
    inicial = sys.argv[1] if len(sys.argv) > 1 else None
    if not inicial:
        from bdgd2dss import interativo
        p = interativo.modelos_recentes(RAIZ)
        inicial = p if os.path.isdir(p) else None
    Painel(inicial).mainloop()
