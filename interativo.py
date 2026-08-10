# -*- coding: utf-8 -*-
"""
PAINEL DE PARAMETROS — rodar os scripts sem decorar a linha de comando
======================================================================

Todo script deste projeto tinha o mesmo defeito de uso: rodar sem argumento
devolvia `error: the following arguments are required: master` e nada mais.
Quem nao escreveu o script nao tem como adivinhar o que falta.

Aqui a regra passa a ser uma so:

    com argumento  -> comporta-se exatamente como antes (a linha de comando
                      continua valendo, e o painel.py e o app.py chamam os
                      scripts assim, por subprocess)
    sem argumento  -> abre uma janelinha pedindo o que falta, com o caminho
                      ja preenchido pelo ultimo uso e um botao de procurar

O que a janela devolve e um dicionario simples, que o script converte em
`sys.argv` e entrega ao argparse de sempre. Nao ha caminho de codigo novo
depois do formulario: e o mesmo programa, so que com os argumentos vindos
da tela em vez do terminal.

USO
---
    import interativo

    if len(sys.argv) == 1:
        v = interativo.formulario('energia', 'Energia do dia', [
            {'chave': 'raiz', 'tipo': 'pasta', 'rotulo': 'Pasta dos modelos',
             'padrao': interativo.modelos_recentes()},
            {'chave': 'passos', 'tipo': 'inteiro', 'rotulo': 'Passos no dia',
             'padrao': 96},
        ], ajuda='Roda o dia inteiro e mede perdas por alimentador.')
        if v is None:
            return                       # cancelou
        sys.argv += [v['raiz'], '--passos', str(v['passos'])]

TIPOS DE CAMPO
--------------
    pasta     entrada de texto + "Procurar..." (askdirectory)
    arquivo   entrada de texto + "Procurar..." (askopenfilename); use
              'filtros' para os tipos, ex.: [('MASTER do OpenDSS', '*.dss')]
    texto     entrada livre
    opcao     combo fechado; use 'valores'
    bool      caixa de marcar
    inteiro   spinbox inteiro; use 'minimo'/'maximo'
    decimal   spinbox com casas; use 'minimo'/'maximo'/'passo'

SEM TELA
--------
Se o tkinter nao existir (servidor, SSH) ou a variavel BDGD_SEM_JANELA
estiver definida, o mesmo formulario e perguntado no terminal, com os
padroes entre colchetes. Nenhum script fica preso a existencia de janela.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
_MEMORIA = os.path.join(AQUI, '.ultimos_valores.json')


# ============================================================ memoria de uso
def _carrega():
    try:
        with open(_MEMORIA, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _grava(secao, valores):
    """Guarda o que foi preenchido para ja vir pronto na proxima vez.

    E o que separa "abre uma janela" de "e direto": na segunda execucao o
    caminho da BDGD e o da pasta de modelos ja estao la, e sobra clicar em
    Executar.
    """
    d = _carrega()
    d[secao] = {k: v for k, v in valores.items()
                if isinstance(v, (str, int, float, bool))}
    try:
        with open(_MEMORIA, 'w', encoding='utf-8') as fh:
            json.dump(d, fh, indent=1, ensure_ascii=False)
    except Exception:
        pass                       # memoria e conveniencia, nao pode quebrar nada


# ================================================================== padroes
def modelos_recentes(raiz=AQUI):
    """A pasta de modelos mais recente (MODELOS_V8, MODELOS_V7, ... MODELOS).

    Evita o padrao fixo `MODELOS_V5` espalhado pelos scripts, que envelhece a
    cada regeracao e faz o script apontar para uma pasta que ninguem mais usa.
    """
    cands = []
    for d in os.listdir(raiz) if os.path.isdir(raiz) else []:
        p = os.path.join(raiz, d)
        if d.upper().startswith('MODELOS') and os.path.isdir(p):
            tem = any(os.path.exists(os.path.join(p, s, f'MASTER-{s}.dss'))
                      for s in os.listdir(p)[:400]
                      if os.path.isdir(os.path.join(p, s)))
            if tem:
                cands.append((os.path.getmtime(p), p))
    return max(cands)[1] if cands else os.path.join(raiz, 'MODELOS')


def bdgd_recente(raiz=os.path.dirname(AQUI)):
    """A .gdb mais recente ao lado do projeto — o File Geodatabase e PASTA."""
    cands = [(os.path.getmtime(os.path.join(raiz, d)), os.path.join(raiz, d))
             for d in (os.listdir(raiz) if os.path.isdir(raiz) else [])
             if d.lower().endswith('.gdb') and os.path.isdir(os.path.join(raiz, d))]
    return max(cands)[1] if cands else ''


def tem_janela():
    if os.environ.get('BDGD_SEM_JANELA'):
        return False
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


# ================================================================ formulario
def formulario(secao, titulo, campos, ajuda='', rodar='Executar'):
    """Pede os campos e devolve {chave: valor}, ou None se cancelou."""
    lembrado = _carrega().get(secao, {})
    for c in campos:
        c.setdefault('padrao', '')
        v = lembrado.get(c['chave'])
        if v in (None, ''):
            continue
        if c.get('tipo') in ('pasta', 'arquivo') and not os.path.exists(str(v)):
            continue               # o ultimo caminho sumiu: fica o padrao do script
        c['padrao'] = v
    if not tem_janela():
        return _no_terminal(titulo, campos, ajuda, secao)
    return _na_janela(titulo, campos, ajuda, secao, rodar)


def _na_janela(titulo, campos, ajuda, secao, rodar):
    import tkinter as tk
    from tkinter import ttk, filedialog

    jan = tk.Tk()
    jan.title(titulo)
    jan.resizable(True, False)
    ret = {}

    topo = ttk.Frame(jan, padding=(14, 12, 14, 4))
    topo.pack(fill='x')
    ttk.Label(topo, text=titulo, font=('Segoe UI', 13, 'bold')).pack(anchor='w')
    if ajuda:
        ttk.Label(topo, text=ajuda, foreground='#555', wraplength=620,
                  justify='left').pack(anchor='w', pady=(3, 0))
    ttk.Separator(jan).pack(fill='x', padx=14, pady=8)

    corpo = ttk.Frame(jan, padding=(14, 0, 14, 6))
    corpo.pack(fill='both', expand=True)
    corpo.columnconfigure(1, weight=1)

    vars_ = {}
    lin = 0
    for c in campos:
        tipo = c.get('tipo', 'texto')
        ttk.Label(corpo, text=c['rotulo'] + ':').grid(row=lin, column=0,
                                                      sticky='w', pady=5, padx=(0, 8))
        if tipo == 'bool':
            v = tk.BooleanVar(value=bool(c['padrao']))
            ttk.Checkbutton(corpo, variable=v, text=c.get('dica', '')
                            ).grid(row=lin, column=1, columnspan=2, sticky='w')
            vars_[c['chave']] = (v, tipo)
            lin += 1
            continue

        if tipo == 'opcao':
            v = tk.StringVar(value=str(c['padrao'] or c['valores'][0]))
            ttk.Combobox(corpo, textvariable=v, values=c['valores'],
                         state='readonly', width=22
                         ).grid(row=lin, column=1, sticky='w')
        elif tipo in ('inteiro', 'decimal'):
            v = tk.StringVar(value=str(c['padrao']))
            ttk.Spinbox(corpo, textvariable=v, width=12,
                        from_=c.get('minimo', 0), to=c.get('maximo', 10000),
                        increment=c.get('passo', 1 if tipo == 'inteiro' else 0.1)
                        ).grid(row=lin, column=1, sticky='w')
        else:
            v = tk.StringVar(value=str(c['padrao']))
            ent = ttk.Entry(corpo, textvariable=v)
            ent.grid(row=lin, column=1, sticky='ew')
            if tipo in ('pasta', 'arquivo'):
                # Caminho longo nao cabe na caixa, e o que interessa e o FIM
                # ("...\MODELOS_V8"), nao a raiz do disco. So rolar no
                # after_idle nao adianta: a essa altura a Entry ainda tem
                # largura 1 e o gerenciador de geometria desfaz depois. Por
                # isso o gatilho e o primeiro <Configure>, que e quando ela
                # ganha a largura de verdade — e ai se desliga, para nao
                # atrapalhar quem estiver navegando no texto.
                def ao_dimensionar(_e, w=ent):
                    w.unbind('<Configure>')
                    w.xview_moveto(1.0)
                ent.bind('<Configure>', ao_dimensionar)
                v.trace_add('write',
                            lambda *_, e=ent: e.after_idle(e.xview_moveto, 1.0))

        if tipo in ('pasta', 'arquivo'):
            def procura(var=v, campo=c):
                inicial = var.get() if os.path.exists(var.get() or '') else AQUI
                if campo['tipo'] == 'pasta':
                    d = filedialog.askdirectory(title=campo['rotulo'],
                                                initialdir=inicial)
                else:
                    d = filedialog.askopenfilename(
                        title=campo['rotulo'],
                        initialdir=inicial if os.path.isdir(inicial)
                        else os.path.dirname(inicial),
                        filetypes=campo.get('filtros', []) + [('Todos', '*.*')])
                if d:
                    var.set(os.path.normpath(d))
            ttk.Button(corpo, text='Procurar...', width=12, command=procura
                       ).grid(row=lin, column=2, sticky='w', padx=(6, 0))
        vars_[c['chave']] = (v, tipo)
        if c.get('dica'):
            lin += 1
            ttk.Label(corpo, text=c['dica'], foreground='#777', wraplength=560,
                      justify='left', font=('Segoe UI', 8)
                      ).grid(row=lin, column=1, columnspan=2, sticky='w')
        lin += 1

    pe = ttk.Frame(jan, padding=(14, 4, 14, 12))
    pe.pack(fill='x')

    def ok(_=None):
        for ch, (var, tipo) in vars_.items():
            s = var.get()
            if tipo == 'inteiro':
                ret[ch] = int(float(s or 0))
            elif tipo == 'decimal':
                ret[ch] = float(str(s or 0).replace(',', '.'))
            elif tipo == 'bool':
                ret[ch] = bool(s)
            else:
                ret[ch] = str(s).strip()
        _grava(secao, ret)
        jan.destroy()

    def cancela(_=None):
        ret.clear()
        ret['__cancelado__'] = True
        jan.destroy()

    ttk.Button(pe, text=rodar, command=ok, width=16).pack(side='right')
    ttk.Button(pe, text='Cancelar', command=cancela, width=12
               ).pack(side='right', padx=6)
    ttk.Label(pe, text='Enter executa  •  Esc cancela',
              foreground='#888').pack(side='left')
    jan.bind('<Return>', ok)
    jan.bind('<Escape>', cancela)
    jan.update_idletasks()
    jan.minsize(max(680, jan.winfo_reqwidth()), jan.winfo_reqheight())
    # nasce centralizada: janela pequena no canto superior esquerdo passa
    # despercebida atras do editor e parece que o script travou
    x = (jan.winfo_screenwidth() - jan.winfo_reqwidth()) // 2
    y = (jan.winfo_screenheight() - jan.winfo_reqheight()) // 3
    jan.geometry(f'+{max(0, x)}+{max(0, y)}')
    jan.attributes('-topmost', True)
    jan.after(300, lambda: jan.attributes('-topmost', False))
    jan.mainloop()
    return None if ret.get('__cancelado__') or not ret else ret


def _no_terminal(titulo, campos, ajuda, secao):
    print(f'\n=== {titulo} ===')
    if ajuda:
        print(ajuda)
    ret = {}
    try:
        for c in campos:
            tipo = c.get('tipo', 'texto')
            extra = ''
            if tipo == 'opcao':
                extra = ' (' + '/'.join(map(str, c['valores'])) + ')'
            elif tipo == 'bool':
                extra = ' (s/n)'
            s = input(f'{c["rotulo"]}{extra} [{c["padrao"]}]: ')
            # o BOM aparece quando a entrada vem de um cano em vez do teclado
            # (PowerShell escreve UTF-8 com BOM) e faria o vazio parecer texto
            s = s.strip().lstrip('\N{ZERO WIDTH NO-BREAK SPACE}').strip()
            if not s:
                s = str(c['padrao'])
            if tipo == 'inteiro':
                ret[c['chave']] = int(float(s or 0))
            elif tipo == 'decimal':
                ret[c['chave']] = float(s.replace(',', '.') or 0)
            elif tipo == 'bool':
                ret[c['chave']] = str(s).lower() in ('s', 'sim', 'y', 'true', '1')
            else:
                ret[c['chave']] = s.strip('"').strip()
    except (EOFError, KeyboardInterrupt):
        print('\ncancelado.')
        return None
    _grava(secao, ret)
    return ret


# =================================================================== saidas
def pyplot():
    """pyplot com backend de janela quando da, Agg quando nao da.

    O `matplotlib.use('Agg')` fixo nos scripts salvava PNG e nunca mostrava
    nada — quem rodava tinha de ir cacar o arquivo. Aqui a janela aparece se
    houver tela, e o Agg fica como reserva para uso em lote.
    """
    import matplotlib
    if tem_janela():
        try:
            matplotlib.use('TkAgg')
        except Exception:
            matplotlib.use('Agg')
    else:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return plt


def mostra(plt, png=None):
    """Mostra na tela; se nao houver tela, salva onde `png` indicar."""
    if png:
        plt.savefig(png, dpi=130, bbox_inches='tight')
        print(f'figura em {png}')
    if tem_janela():
        plt.show()
    else:
        plt.close('all')


def abrir(caminho):
    """Abre a pasta ou o arquivo no Explorador, ao fim do trabalho."""
    if not tem_janela():
        return                     # sem ambiente grafico nao ha o que abrir
    try:
        if os.name == 'nt':
            os.startfile(caminho)
        else:
            os.system(f'xdg-open "{caminho}"')
    except Exception:
        pass
