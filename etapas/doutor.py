# -*- coding: utf-8 -*-
"""AUTOTESTE DA MAQUINA — roda ANTES de submeter e diz o que falta.

    python doutor.py
    python doutor.py --bases /scratch/elder/bdgds

Existe por causa de um modo de falha especifico do cluster: a tarefa entra na
fila, espera, comeca de madrugada, e morre no minuto 2 porque faltava uma
biblioteca ou o caminho das bases estava errado. O prejuizo nao e o minuto — e
a fila inteira, mais o tempo ate alguem olhar.

Cada item e uma pergunta que ja custou tempo em algum lugar. O que ele NAO faz
e converter nada: quem quer prova de conversao roda a Roraima, que leva menos
de um minuto e esta escrita no fim do relatorio.
"""
import argparse
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
# A RAIZ E O PAI, desde a mudanca de 02/09/2026: estes executaveis
# sairam da raiz para `etapas/`, e `AQUI` deixou de ser onde mora o
# pacote `bdgd2dss`.
sys.path.insert(0, os.path.dirname(AQUI))

OK, AVISO, ERRO = 'ok', 'aviso', 'ERRO'
_cores = {OK: '  ok  ', AVISO: ' aviso', ERRO: ' ERRO '}


def _linha(estado, titulo, detalhe=''):
    print(f'[{_cores[estado]}] {titulo}' + (f'\n{" " * 9}{detalhe}' if detalhe
                                            else ''), flush=True)
    return estado


def python_novo():
    v = sys.version_info
    if v < (3, 9):
        return _linha(ERRO, f'Python {v.major}.{v.minor}',
                      'o projeto usa sintaxe de 3.9 em diante')
    return _linha(OK, f'Python {v.major}.{v.minor}.{v.micro}')


def bibliotecas():
    falta, achadas = [], []
    for nome, para_que in (('numpy', 'contas'),
                           ('pyogrio', 'ler a .gdb'),
                           ('opendssdirect', 'o motor eletrico')):
        try:
            m = __import__(nome)
            achadas.append(f'{nome} {getattr(m, "__version__", "")}'.strip())
        except Exception as e:
            falta.append(f'{nome} ({para_que}): {type(e).__name__}')
    if falta:
        return _linha(ERRO, 'bibliotecas obrigatorias',
                      '; '.join(falta) + '\n         pip install -r requirements.txt')
    estado = OK
    try:
        __import__('matplotlib')
    except Exception:
        estado = _linha(AVISO, 'matplotlib ausente — as figuras nao saem, o '
                               'resto roda')
    _linha(OK, 'bibliotecas', ', '.join(achadas))
    return estado if estado == AVISO else OK


def motor_eletrico():
    """Compila um circuito de tres linhas. Se o motor nao resolve isto, nao
    vai resolver 100 mil."""
    try:
        import opendssdirect as dss
        dss.Text.Command('Clear')
        dss.Text.Command('New Circuit.T basekv=13.8 phases=3 bus1=f')
        dss.Text.Command('New Linecode.lc nphases=3 r1=0.5 x1=0.4 units=km')
        dss.Text.Command('New Line.l1 bus1=f bus2=b linecode=lc length=0.1 '
                         'units=km')
        dss.Text.Command('New Load.c1 bus1=b phases=3 kV=13.8 kW=100')
        dss.Text.Command('Set Voltagebases=[13.8]')
        dss.Text.Command('Calcvoltagebases')
        dss.Text.Command('Solve')
        if not dss.Solution.Converged():
            return _linha(ERRO, 'OpenDSS compila mas nao converge')
        return _linha(OK, f'OpenDSS resolve', dss.Basic.Version()[:60])
    except Exception as e:
        return _linha(ERRO, 'OpenDSS nao funciona', f'{type(e).__name__}: {e}')


def interface_grafica():
    """O painel e o menu, que sao a porta de entrada do projeto.

    `tkinter` e da biblioteca padrao, mas em Linux o `tk` do sistema costuma
    vir num pacote a parte (`python3-tk`) — entao o import falha num Python
    que, fora isso, esta perfeito. Num no COM tela isso importa: e a diferenca
    entre usar o painel e ter de decorar linha de comando.
    """
    from bdgd2dss import plataforma
    try:
        import tkinter                                  # noqa: F401
    except Exception as e:
        return _linha(AVISO, 'tkinter ausente — sem painel, so linha de comando',
                      f'{type(e).__name__}: instale python3-tk, ou use o '
                      f'Python do micromamba, que ja traz o tk')
    if not os.environ.get('DISPLAY') and sys.platform.startswith('linux'):
        return _linha(OK, 'tkinter presente; sem DISPLAY agora',
                      'o painel funciona numa sessao com tela ou com ssh -X')
    return _linha(OK, f'painel disponivel (modo {plataforma.modo()})')


def leitura_de_gdb(pasta):
    """Uma .gdb aberta de verdade. E o passo que depende do GDAL, que e a
    dependencia mais chata de instalar em Linux."""
    if not pasta or not os.path.isdir(pasta):
        return _linha(AVISO, 'bases nao encontradas',
                      f'{pasta or "(nao informado)"} — use --bases ou '
                      f'BDGD2DSS_BASES')
    gdbs = sorted(x for x in os.listdir(pasta) if x.endswith('.gdb'))
    if not gdbs:
        return _linha(ERRO, 'nenhuma .gdb na pasta', pasta)
    try:
        import pyogrio
        cam = os.path.join(pasta, gdbs[0])
        camadas = pyogrio.list_layers(cam)
        return _linha(OK, f'{len(gdbs)} bases; a primeira abre',
                      f'{gdbs[0]}: {len(camadas)} camadas')
    except Exception as e:
        return _linha(ERRO, 'a .gdb nao abre (GDAL?)',
                      f'{type(e).__name__}: {e}')


def paralelismo():
    from bdgd2dss import plataforma
    metodo = plataforma.prepara_processos()
    if metodo != 'spawn':
        return _linha(AVISO, f'multiprocessing em `{metodo}`',
                      'o esperado e `spawn`: com `fork` o filho herda a DLL '
                      'do OpenDSS ja carregada')
    return _linha(OK, 'processos por `spawn`', plataforma.resumo())


def memoria_por_processo():
    """A conta que decide `--jobs` no cluster. As subestacoes maiores pedem
    ~3 GB; com nucleos demais e RAM de menos a maquina pagina e fica MAIS
    lenta do que com metade."""
    from bdgd2dss import plataforma
    gb = None
    try:                                        # Linux
        with open('/proc/meminfo') as fh:
            for l in fh:
                if l.startswith('MemAvailable:'):
                    gb = int(l.split()[1]) / 1024 / 1024
                    break
    except OSError:
        try:                                    # Windows
            import ctypes

            class M(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong),
                            ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong),
                            ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong),
                            ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = M()
            m.dwLength = ctypes.sizeof(M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            gb = m.ullAvailPhys / 2 ** 30
        except Exception:
            pass
    n = plataforma.nucleos()
    if gb is None:
        return _linha(AVISO, f'memoria livre desconhecida; jobs={n}')
    cabe = max(1, int(gb // plataforma.GB_POR_PROCESSO))
    if cabe < n:
        return _linha(AVISO, f'{gb:.0f} GB livres para {n} processos',
                      f'cabem ~{cabe}; use --jobs {cabe} ou a maquina pagina')
    return _linha(OK, f'{gb:.0f} GB livres, {n} processos '
                      f'(~{plataforma.GB_POR_PROCESSO:g} GB cada)')


def escrita_de_arquivo():
    """O fim de linha nao pode depender do sistema, senao os modelos gerados
    aqui e no laptop deixam de ser comparaveis byte a byte."""
    import tempfile
    from bdgd2dss import escrita
    p = escrita.escreve_linhas(os.path.join(tempfile.mkdtemp(), 'x.dss'), ['a'])
    with open(p, 'rb') as fh:
        bruto = fh.read()
    if bruto != b'a\r\n':
        return _linha(ERRO, 'fim de linha errado', repr(bruto))
    return _linha(OK, 'arquivos saem com CRLF em qualquer sistema')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--bases', default=os.environ.get('BDGD2DSS_BASES'),
                    help='pasta com as .gdb (ou BDGD2DSS_BASES)')
    a = ap.parse_args()

    print(f'\nAUTOTESTE — {sys.platform}, {os.cpu_count()} nucleos\n')
    estados = [python_novo(), bibliotecas(), motor_eletrico(),
               escrita_de_arquivo(), paralelismo(), memoria_por_processo(),
               interface_grafica(), leitura_de_gdb(a.bases)]
    erros = estados.count(ERRO)
    avisos = estados.count(AVISO)
    print()
    if erros:
        print(f'{erros} problema(s) que IMPEDEM rodar. Resolva antes de '
              f'submeter.')
        return 1
    if avisos:
        print(f'Sem impedimento; {avisos} aviso(s) acima merecem olhada.')
    else:
        print('Tudo pronto.')
    print('\nProva real, menos de um minuto:\n'
          '  python converter.py <bases>/Roraima_*.gdb --saida TESTE_RR\n'
          '  python validador.py TESTE_RR --ses --jobs 4')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
