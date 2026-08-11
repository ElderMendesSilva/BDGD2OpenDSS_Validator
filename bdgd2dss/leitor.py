# -*- coding: utf-8 -*-
"""
Acesso a BDGD (File Geodatabase) com leitura em fatias.

Le tabelas grandes (UCBT_tab com milhoes de registros) sem estourar memoria,
usando skip_features/max_features do GDAL, que faz seek posicional no .gdb.
"""
import os
import numpy as np

try:
    import pyogrio
except Exception as _e:                                 # pragma: no cover
    import sys
    raise SystemExit(
        f'Falha ao importar pyogrio ({type(_e).__name__}): {_e}\n'
        f'Python em uso: {sys.executable}\n'
        f'Versao: {sys.version}\n\n'
        'Se o pyogrio esta instalado, o interpretador que roda este script pode\n'
        'ser outro. Rode com o mesmo que instalou:  py -m pip install pyogrio\n'
        'ou crie um ambiente isolado:\n'
        '    py -3.12 -m venv .venv\n'
        '    .venv\\Scripts\\activate\n'
        '    pip install pyogrio numpy opendssdirect.py')


def pertence(coluna, valores):
    """`np.isin` a prova de dtype — devolve a mascara de quem esta em `valores`.

    O `np.isin` cru quebra quando os dois lados sao string de LARGURA
    diferente. Medido na Cemig-D, subestacao 266 de 413, depois de 4h15 de
    conversao:

        ufunc 'minimum' did not contain a loop with signature matching
        types (dtype('<U7'), dtype('<U')) -> None

    Nao e caso exotico: a largura do `<U` sai do conteudo lido, entao basta uma
    fatia em que todos os codigos tenham 7 caracteres e a lista de alvos venha
    de outra fatia com largura diferente. As bases da Enel SP, Roraima, Light,
    Equatorial e CPFL passaram por sorte de conteudo.

    A correcao promove os dois lados a uma largura comum antes de comparar —
    nunca truncando, que geraria casamento errado em silencio, pior que o erro.
    """
    coluna = np.asarray(coluna)
    alvos = list(valores)
    if not len(coluna) or not alvos:
        return np.zeros(len(coluna), dtype=bool)
    if coluna.dtype.kind in 'US' or any(isinstance(v, str) for v in alvos):
        larg_col = (coluna.dtype.itemsize // 4
                    if coluna.dtype.kind == 'U' else coluna.dtype.itemsize)
        larg = max(larg_col, max(len(str(v)) for v in alvos), 1)
        tipo = f'<U{larg}'
        return np.isin(coluna.astype(tipo), np.asarray(alvos, dtype=tipo))
    return np.isin(coluna, np.asarray(alvos))


class BDGD:
    """Abre uma BDGD e entrega as tabelas ja filtradas."""

    def __init__(self, caminho, verbose=True):
        if not os.path.exists(caminho):
            raise FileNotFoundError(caminho)
        self.gdb = caminho
        self.verbose = verbose
        self._info = {}
        self._lote = None        # CTMTs do lote corrente, ou None
        self._cache = {}         # (camada, colunas) -> leitura unica do lote

    # ------------------------------------------------------------------ infra
    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def camadas(self):
        return [n for n, _ in pyogrio.list_layers(self.gdb)]

    def info(self, layer):
        if layer not in self._info:
            self._info[layer] = pyogrio.read_info(self.gdb, layer=layer)
        return self._info[layer]

    def campos(self, layer):
        return list(self.info(layer)['fields'])

    def n_registros(self, layer):
        return self.info(layer)['features']

    # ------------------------------------------------------------------ leitura
    def ler(self, layer, colunas=None, where=None):
        """Le a camada inteira de uma vez. Use so em tabelas pequenas."""
        colunas = colunas or self.campos(layer)
        r = pyogrio.raw.read(self.gdb, layer=layer, columns=colunas,
                             read_geometry=False, where=where)
        meta, _, _, data = r
        cs = list(meta['fields'])
        return {c: data[cs.index(c)] for c in cs}

    def ler_em_fatias(self, layer, colunas=None, passo=700_000):
        """Gera dicionarios coluna->array, uma fatia por vez."""
        colunas = colunas or self.campos(layer)
        total = self.n_registros(layer)
        for skip in range(0, total, passo):
            r = pyogrio.raw.read(self.gdb, layer=layer, columns=colunas,
                                 read_geometry=False,
                                 skip_features=skip, max_features=passo)
            meta, _, _, data = r
            cs = list(meta['fields'])
            yield {c: data[cs.index(c)] for c in cs}, min(skip + passo, total), total

    def abrir_lote(self, ctmts):
        """Ativa o modo lote para este conjunto de alimentadores.

        Sem ele cada subestacao dispara uma varredura completa da camada: o
        WHERE do GDAL nao tem indice, entao trazer 49 linhas do SSDMT custa os
        mesmos 13 s que trazer 6.927. Com o lote a camada e lida UMA vez para
        todos os CTMTs do grupo e cada subestacao e servida da memoria — 10
        subestacoes custam 19 s onde 10 leituras separadas custam 135.

        O tamanho do lote e um compromisso: 10 subestacoes sao 106 CTMTs e
        71 mil linhas de SSDMT, memoria irrisoria, e cabem folgadas no limite
        de 900 itens da clausula IN.
        """
        self._lote = {v for v in ctmts if v}
        self._cache = {}

    def fechar_lote(self):
        self._lote = None
        self._cache = {}

    def ler_filtrado(self, layer, chave, valores, colunas=None, passo=700_000,
                     forcar_varredura=False):
        """Devolve so as linhas cuja coluna-chave esteja em `valores`.

        Com lote aberto (`abrir_lote`) e o alvo contido nele, serve da leitura
        unica do grupo. Fora disso vai ao disco por `_ler_do_disco`.
        """
        alvo = [v for v in valores if v]
        colunas = colunas or self.campos(layer)
        if chave not in colunas:
            colunas = list(colunas) + [chave]
        if not alvo:
            return {c: np.array([]) for c in colunas}

        if (self._lote is not None and not forcar_varredura
                and set(alvo) <= self._lote):
            ck = (layer, tuple(colunas))
            if ck not in self._cache:
                self._cache[ck] = self._ler_do_disco(
                    layer, chave, sorted(self._lote), colunas, passo, False)
            col = self._cache[ck]
            if len(col[chave]) == 0:
                return {c: np.array([]) for c in colunas}
            idx = np.nonzero(pertence(col[chave], alvo))[0]
            return {c: col[c][idx] for c in colunas}

        return self._ler_do_disco(layer, chave, alvo, colunas, passo,
                                  forcar_varredura)

    def _ler_do_disco(self, layer, chave, alvo, colunas, passo,
                      forcar_varredura):
        """Le do .gdb. `forcar_varredura=True` troca o WHERE pela varredura em
        fatias, util se a lista de valores nao couber numa clausula SQL."""

        # o SQLite do OpenFileGDB aguenta listas longas, mas nao infinitas
        if not forcar_varredura and len(alvo) <= 900:
            try:
                lista = ','.join("'" + str(v).replace("'", "''") + "'" for v in alvo)
                return self.ler(layer, colunas, where=f'{chave} IN ({lista})')
            except Exception as e:
                self.log(f'    (WHERE falhou em {layer}: {str(e)[:60]} — varrendo)')

        acc = {c: [] for c in colunas}
        conj = set(alvo)
        for col, lido, total in self.ler_em_fatias(layer, colunas, passo):
            idx = np.nonzero(np.isin(col[chave], list(conj)))[0]
            if len(idx):
                for c in colunas:
                    acc[c].append(col[c][idx])
            del col
        return {c: (np.concatenate(v) if v else np.array([])) for c, v in acc.items()}


# Tabela pre-computada para o `no()`: o join caractere a caractere custava
# 4,6x mais, e esta funcao roda em cada PAC de cada linha da BDGD. Acima da
# ASCII o comportamento nao muda — `str.translate` deixa passar o que nao esta
# na tabela, e `isalnum()` ja aceitava esses caracteres.
_TABELA = {c: (chr(c) if (chr(c).isalnum() or chr(c) in '_-') else '_')
           for c in range(128)}


def num(x, padrao=0.0):
    """Converte para float tolerando None, string vazia e NaN."""
    try:
        v = float(x)
        return padrao if v != v else v
    except (TypeError, ValueError):
        return padrao


def txt(x, padrao=''):
    return padrao if x is None else str(x)


def no(x):
    """Nome de barra seguro para o OpenDSS. Devolve '' para campo vazio.

    Duas armadilhas da BDGD que isto resolve, ambas encontradas na pratica:

      ESPACO NO MEIO DO PAC. A DTAM tem um PAC "0008200019A75850L_ 14266371".
      O OpenDSS corta o nome no espaco e le o resto como se fosse o proximo
      parametro — a subestacao inteira deixava de compilar com um erro que
      nao dizia nada ("Could not match enum Connection").

      CAMPO PREENCHIDO COM ESPACO em vez de nulo. Sem o strip, um ' ' virava
      a barra '_', e todos os alimentadores sem BARR declarada acabavam
      ligados a uma mesma barra fantasma, que nao se conecta a fonte alguma.

    Tem de ser o MESMO tratamento em todos os modulos: se a linha sanitiza e
    o transformador nao, os dois deixam de se encontrar na mesma barra.
    """
    s = txt(x).strip()
    if not s:
        return ''
    return s.translate(_TABELA).lower()
