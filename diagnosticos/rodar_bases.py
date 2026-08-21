# -*- coding: utf-8 -*-
"""Roda o levantamento completo nas bases restantes, uma de cada vez.

Para cada base: extrai (se preciso) -> sonda -> converte -> verifica ->
energia -> valida_perdas. Uma falha nao derruba as demais: registra e segue.

Uma de cada vez de proposito — duas conversoes simultaneas disputam memoria e
a maior delas (Cemig-D) sozinha ja e o caso pesado.
"""
import json
import os
import subprocess
import sys
import time
import zipfile

P = r'D:\Elder\Elder\ENEL\ENEL 2025\BDGD\ENEL 2024 - OUTUBRO\Criticidades\BDGD2OpenDSS'
ZIPS = r'D:\Elder\Elder\BDGDs'
SCR = r'C:\Users\Elder\AppData\Local\Temp\claude\D--Elder-Elder-ENEL\2e25c970-4f70-4b8e-ad77-4fe774181dcc\scratchpad'
PY = r'C:\Users\Elder\AppData\Local\Programs\Python\Python314\python.exe'

BASES = [
    ('Equatorial_PA_371_2024-12-31_V11_20250911-0946', 'EQPA'),
    ('CPFL_Paulista_63_2024-12-31_V11_20250731-1036', 'CPFL'),
    ('Enel_CE_39_2024-12-31_V11_20250822-1151', 'ENCE'),
    ('Cemig-D_4950_2024-12-31_V11_20250929-1522', 'CMIG'),
]

os.environ['BDGD_SEM_JANELA'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
resumo = []


def passo(rot, cmd, log, limite=None):
    """Roda um comando, joga a saida no log e devolve (ok, segundos, cauda)."""
    t0 = time.time()
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(f'\n{"="*70}\n== {rot}\n== {" ".join(cmd)}\n{"="*70}\n')
        fh.flush()
        try:
            r = subprocess.run(cmd, cwd=P, stdout=fh, stderr=subprocess.STDOUT,
                               timeout=limite)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            fh.write('\n*** ESTOUROU O TEMPO LIMITE ***\n')
            ok = False
    dt = time.time() - t0
    cauda = ''
    try:
        with open(log, encoding='utf-8', errors='replace') as fh:
            cauda = ''.join(fh.readlines()[-4:]).strip()
    except Exception:
        pass
    print(f'   {rot:16s} {"ok " if ok else "FALHOU"} {dt/60:6.1f} min', flush=True)
    return ok, dt, cauda


for nome, tag in BASES:
    print(f'\n{"#"*70}\n# {tag} — {nome}\n{"#"*70}', flush=True)
    gdb = os.path.join(ZIPS, nome + '.gdb')
    z = gdb + '.zip'
    log = os.path.join(SCR, f'log_{tag}.txt')
    reg = {'tag': tag, 'base': nome}

    # --- extrair
    if not os.path.isdir(gdb):
        if not os.path.exists(z):
            print(f'   zip ausente: {z}', flush=True)
            reg['erro'] = 'zip ausente'
            resumo.append(reg)
            continue
        t0 = time.time()
        with zipfile.ZipFile(z) as a:
            a.extractall(ZIPS)
        print(f'   {"extrair":16s} ok  {(time.time()-t0)/60:6.1f} min', flush=True)
    reg['gdb'] = os.path.isdir(gdb)
    if not reg['gdb']:
        reg['erro'] = 'gdb nao apareceu apos extrair'
        resumo.append(reg)
        continue

    saida = f'MODELOS_{tag}'
    ok, dt, _ = passo('sonda', [PY, os.path.join(SCR, 'sonda_bdgd.py'), gdb], log)
    reg['sonda_ok'] = ok

    ok, dt, _ = passo('converter', [PY, '-u', 'converter.py', gdb,
                                    '--saida', saida], log, limite=6 * 3600)
    reg['converter_ok'], reg['min_converter'] = ok, round(dt / 60, 1)
    if not ok:
        resumo.append(reg)
        continue

    ok, dt, _ = passo('verifica', [PY, '-u', 'verifica.py', saida], log,
                      limite=4 * 3600)
    reg['verifica_ok'], reg['min_verifica'] = ok, round(dt / 60, 1)

    ok, dt, _ = passo('energia', [PY, '-u', 'energia.py', saida], log,
                      limite=6 * 3600)
    reg['energia_ok'], reg['min_energia'] = ok, round(dt / 60, 1)

    ok, dt, _ = passo('valida_perdas', [PY, '-u', 'valida_perdas.py', saida, gdb],
                      log, limite=2 * 3600)
    reg['perdas_ok'] = ok

    # colhe os numeros que interessam
    try:
        v = json.load(open(os.path.join(P, saida, 'verificacao.json'), encoding='utf-8'))
        reg['subestacoes'] = len(v)
        reg['sadias'] = sum(1 for x in v if x['veredicto'] == 'OK')
    except Exception:
        pass
    try:
        import statistics
        p = json.load(open(os.path.join(P, saida, 'validacao_perdas.json'),
                           encoding='utf-8'))
        # lista ate a V17, dicionario depois — ver valida_perdas
        p = p if isinstance(p, list) else (p.get('alimentadores') or [])
        r = [x['razao'] for x in p if x['razao']]
        reg['alim_comparados'] = len(p)
        reg['modelo_pct'] = round(statistics.median([x['modelo_pct'] for x in p]), 2)
        reg['declarado_pct'] = round(statistics.median([x['declarado_pct'] for x in p]), 2)
        reg['razao_mediana'] = round(statistics.median(r), 2)
    except Exception:
        pass
    resumo.append(reg)
    json.dump(resumo, open(os.path.join(SCR, 'resumo_bases.json'), 'w',
                           encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'   -> {reg.get("sadias","?")}/{reg.get("subestacoes","?")} sadias, '
          f'razao {reg.get("razao_mediana","?")}x', flush=True)

json.dump(resumo, open(os.path.join(SCR, 'resumo_bases.json'), 'w',
                       encoding='utf-8'), indent=1, ensure_ascii=False)
print('\n\n==================== RESUMO ====================')
for r in resumo:
    print(f'{r["tag"]:6s} sadias={r.get("sadias","—")}/{r.get("subestacoes","—"):<5} '
          f'modelo={r.get("modelo_pct","—")}% declarado={r.get("declarado_pct","—")}% '
          f'razao={r.get("razao_mediana","—")}x  '
          f'conv={r.get("min_converter","—")}min')
