# -*- coding: utf-8 -*-
"""BAIXA AS BDGDs DIRETO DA ANEEL — o acervo inteiro, sem passar por disco local.

    python baixar_bdgds.py --listar
    python baixar_bdgds.py --destino ~/elder/bdgds --safra 2024-12-31
    python baixar_bdgds.py --destino ~/elder/bdgds --mais-recente-de-cada
    python baixar_bdgds.py --destino ~/elder/bdgds --so 370,4950,390

Existe porque subir 31 GB de `.gdb` por `scp` de uma maquina Windows sem
`rsync` e a pior forma de por base no cluster: nao retoma, gasta a banda duas
vezes (portal -> laptop -> no) e exige disco local que ninguem tem. O no tem
internet e 11 TB livres; baixar la e um salto a menos e uma copia a menos.

DE ONDE VEM. As `.gdb` nao estao no CKAN da ANEEL — estao no ArcGIS Hub, como
itens do dono `aneel_aneel` e tipo `File Geodatabase`. O catalogo sai da busca
e o arquivo, de `/sharing/rest/content/items/<id>/data`. Nao ha autenticacao.

O NOME CARREGA A PROCEDENCIA, e por isso ele nao e reescrito:

    <Nome>_<codigo do agente>_<safra>_<versao>_<carimbo>
    Roraima_Energia_370_2024-12-31_V11_20250924-1424

O codigo do agente e o identificador estavel — o nome muda com incorporacao e
o carimbo muda a cada republicacao da mesma safra.

MISTURAR SAFRA TEM CONSEQUENCIA. `--mais-recente-de-cada` traz a base mais
nova de cada distribuidora, e 17 delas nao publicaram 2024. Isso serve para
medir se a ferramenta atravessa safras; NAO serve para comparar perdas entre
bases, que exige safra unica. O manifesto grava a safra de cada uma para que a
analise possa separar as duas coisas em vez de descobrir tarde.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

BUSCA = 'https://www.arcgis.com/sharing/rest/search'
DADO = 'https://www.arcgis.com/sharing/rest/content/items/%s/data'
DONO = 'aneel_aneel'

# <Nome>_<codigo>_<safra>_<versao>_<carimbo>
PADRAO = re.compile(r'^(?P<nome>.+)_(?P<cod>\d+)_(?P<safra>\d{4}-\d{2}-\d{2})'
                    r'_(?P<ver>[A-Z]\d+)_(?P<carimbo>\d{8}-\d{4})$')


def _abre(url, metodo='GET', tentativas=4):
    """Rede de cluster cai. Tenta de novo com espera crescente."""
    erro = None
    for n in range(tentativas):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, method=metodo), timeout=120)
        except Exception as e:                                   # noqa: BLE001
            erro = e
            time.sleep(2 ** n)
    raise erro


def catalogo():
    """Todos os File Geodatabase da ANEEL, ja decompostos pelo nome."""
    itens, comeco = [], 1
    q = 'owner:%s AND type:"File Geodatabase"' % DONO
    while True:
        u = '%s?f=json&num=100&start=%d&q=%s' % (BUSCA, comeco, urllib.parse.quote(q))
        d = json.load(_abre(u))
        itens += d['results']
        if d.get('nextStart', -1) <= 0:
            break
        comeco = d['nextStart']

    bases, fora = [], []
    for i in itens:
        m = PADRAO.match(i['title'].strip())
        if not m:
            fora.append(i['title'])
            continue
        g = m.groupdict()
        g['id'] = i['id']
        g['titulo'] = i['title'].strip()
        bases.append(g)
    return bases, fora


def mais_recente_de_cada(bases):
    """Uma por distribuidora: safra maior; empate, carimbo maior."""
    por = collections.defaultdict(list)
    for b in bases:
        por[b['cod']].append(b)
    return [max(v, key=lambda x: (x['safra'], x['carimbo'])) for v in por.values()]


def _sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for pedaco in iter(lambda: f.read(1 << 20), b''):
            h.update(pedaco)
    return h.hexdigest()


def baixa_uma(b, destino, refazer=False, extrair=True):
    """Baixa, confere o tamanho, extrai e apaga o `.zip`. Devolve o resultado.

    `extrair=False` PARA NO ZIP, e existe por causa da regra do head node.

    Este script e de 25/08/2026, TRES DIAS antes de o administrador proibir
    processamento no no de acesso — e foi escrito para rodar exatamente la,
    porque e o unico ponto do cluster com internet. Baixar e transferir bytes,
    da mesma natureza do `scp` e do `git pull`, que a regra permite; o
    `extractall` de dezenas de GB e que e processamento.

    Separando os dois, o head node so move bytes e a descompactacao vai para um
    job (`cluster/extrair.pbs`). Nao e contorno de regra: e fazer no no de
    calculo a parte que e calculo.
    """
    gdb = os.path.join(destino, b['titulo'] + '.gdb')
    if os.path.isdir(gdb) and not refazer:
        return dict(b, estado='ja tinha', bytes=0, sha256=None)

    zip_ = os.path.join(destino, b['titulo'] + '.zip')
    r = _abre(DADO % b['id'])
    esperado = int(r.headers.get('Content-Length') or 0)
    with open(zip_, 'wb') as f:
        while True:
            pedaco = r.read(1 << 20)
            if not pedaco:
                break
            f.write(pedaco)

    veio = os.path.getsize(zip_)
    # Sem isto, um download cortado pela metade vira `.gdb` truncado e o defeito
    # so aparece horas depois, no meio da conversao, parecendo bug do conversor.
    if esperado and veio != esperado:
        os.remove(zip_)
        return dict(b, estado='TRUNCADO', bytes=0, sha256=None,
                    detalhe='%d de %d bytes' % (veio, esperado))

    soma = _sha256(zip_)
    if not extrair:
        # O `.zip` FICA, e com ele o sha256 no manifesto: quem extrair depois
        # pode conferir que o arquivo e o mesmo que desceu do portal.
        return dict(b, estado='zip', bytes=veio, sha256=soma)
    try:
        with zipfile.ZipFile(zip_) as z:
            z.extractall(destino)
    except zipfile.BadZipFile:
        os.remove(zip_)
        return dict(b, estado='ZIP INVALIDO', bytes=0, sha256=None)
    os.remove(zip_)

    if not os.path.isdir(gdb):
        # Alguns pacotes trazem a `.gdb` com outro nome dentro. Acha e registra.
        achou = [d for d in os.listdir(destino)
                 if d.endswith('.gdb') and os.path.isdir(os.path.join(destino, d))]
        return dict(b, estado='OUTRO NOME', bytes=veio, sha256=soma,
                    detalhe=str(achou[-1:] or '?'))
    return dict(b, estado='ok', bytes=veio, sha256=soma)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--destino', default='bdgds', help='onde gravar as .gdb')
    ap.add_argument('--safra', help='so esta safra, ex.: 2024-12-31')
    ap.add_argument('--safra-mais-nova', action='store_true',
                    help='descobre a safra mais recente do acervo e baixa so ela')
    ap.add_argument('--versao', help='so esta versao do esquema, ex.: V11')
    ap.add_argument('--mais-recente-de-cada', action='store_true',
                    help='a base mais nova de CADA distribuidora, misturando safras')
    ap.add_argument('--so', help='so estes codigos de agente, separados por virgula')
    ap.add_argument('--jobs', type=int, default=4,
                    help='downloads simultaneos (padrao 4; o portal e de terceiros)')
    ap.add_argument('--listar', action='store_true', help='mostra e nao baixa')
    ap.add_argument('--refazer', action='store_true', help='rebaixa o que ja existe')
    ap.add_argument('--sem-extrair', action='store_true',
                    help='para no .zip, sem descompactar. Use no head node, '
                         'onde a regra de 28/08/2026 proibe processamento: '
                         'baixar e mover bytes, extrair e calculo. A extracao '
                         'vai depois por `qsub cluster/extrair.pbs`')
    a = ap.parse_args(argv)

    print('consultando o acervo da ANEEL...', flush=True)
    bases, fora = catalogo()
    print('  %d itens no padrao; %d fora do padrao%s'
          % (len(bases), len(fora), (' %s' % fora[:3]) if fora else ''))

    # O acervo inteiro por safra, ANTES de filtrar. E o que deixa visivel uma
    # safra nova entrando: quando a 2025 comecar a ser publicada ela aparece
    # aqui com poucas distribuidoras, e `--safra-mais-nova` passaria a trazer
    # so essas poucas. Ver o quadro antes evita baixar 3 bases achando que sao
    # todas.
    todas = collections.Counter(b['safra'] for b in bases)
    print('\nacervo por safra (todas as versoes):')
    for s, n in sorted(todas.items(), reverse=True)[:6]:
        print('  %s : %3d' % (s, n))

    if a.safra_mais_nova:
        if a.safra:
            ap.error('--safra e --safra-mais-nova sao a mesma decisao; escolha uma')
        a.safra = max(b['safra'] for b in bases)
        print('\nsafra mais nova do acervo: %s' % a.safra)

    if a.mais_recente_de_cada:
        bases = mais_recente_de_cada(bases)
    if a.safra:
        bases = [b for b in bases if b['safra'] == a.safra]
    if a.versao:
        bases = [b for b in bases if b['ver'] == a.versao]
    if a.so:
        querid = {c.strip() for c in a.so.split(',') if c.strip()}
        bases = [b for b in bases if b['cod'] in querid]
    bases.sort(key=lambda x: x['titulo'])

    if not bases:
        print('nenhuma base bate com os filtros.')
        return 1

    saf = collections.Counter(b['safra'] for b in bases)
    print('\n%d bases selecionadas, por safra:' % len(bases))
    for s, n in sorted(saf.items(), reverse=True):
        print('  %s : %3d' % (s, n))

    if a.listar:
        print()
        for b in bases:
            print('  %s  %-4s %s' % (b['safra'], b['ver'], b['titulo']))
        return 0

    destino = os.path.expanduser(a.destino)
    os.makedirs(destino, exist_ok=True)
    print('\ndestino: %s' % destino)
    print('baixando com %d simultaneos...\n' % a.jobs, flush=True)

    feitos, t0 = [], time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        futuros = {ex.submit(baixa_uma, b, destino, a.refazer, not a.sem_extrair): b for b in bases}
        for n, fut in enumerate(as_completed(futuros), 1):
            r = fut.result()
            feitos.append(r)
            print('[%3d/%d] %-11s %8.1f MB  %s'
                  % (n, len(bases), r['estado'][:11], r['bytes'] / 2 ** 20,
                     r['titulo'][:50]), flush=True)

    man = os.path.join(destino, 'manifesto_bdgd.json')
    antigo = []
    if os.path.exists(man):
        antigo = json.load(io.open(man, encoding='utf-8')).get('bases', [])
    tinha = {b['id'] for b in feitos}
    json.dump({'baixado_em': time.strftime('%Y-%m-%d %H:%M:%S'),
               'fonte': 'ArcGIS Hub / owner:%s' % DONO,
               'bases': sorted([b for b in antigo if b['id'] not in tinha] + feitos,
                               key=lambda x: x['titulo'])},
              io.open(man, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # `zip` E SUCESSO quando foi o que se pediu. Sem isto o `--sem-extrair`
    # baixava certo, gravava o manifesto e ainda assim relatava "0 de 1" e
    # saia com rc=1 — um caminho que funciona se declarando quebrado, que
    # numa corrente do PBS abortaria os jobs seguintes por dependencia.
    OK = ('ok', 'ja tinha', 'zip')
    bons = [f for f in feitos if f['estado'] in OK]
    ruins = [f for f in feitos if f['estado'] not in OK]
    print('\n%d de %d em %.1f min; %.1f GB baixados'
          % (len(bons), len(feitos), (time.time() - t0) / 60,
             sum(f['bytes'] for f in feitos) / 2 ** 30))
    print('manifesto: %s' % man)
    if a.sem_extrair and bons:
        print('\nOS .zip NAO FORAM EXTRAIDOS, por escolha: extrair e '
              'calculo, e calculo nao acontece no no de acesso.')
        print('    qsub -v "PASTA=%s" cluster/extrair.pbs' % destino)
    for f in ruins:
        print('  FALHOU  %-46s %s %s'
              % (f['titulo'][:46], f['estado'], f.get('detalhe', '')))
    return 1 if ruins else 0


if __name__ == '__main__':
    sys.exit(main())
