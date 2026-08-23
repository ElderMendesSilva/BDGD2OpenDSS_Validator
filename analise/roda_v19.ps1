# Dispara a V19 as 21:00, sem ninguem na frente da maquina.
#
# O ciclo sao ~9 h: V16 levou 614 min, V17 551 e V18 543. Comecando as 21:00,
# fecha entre 06:00 e 07:00.
#
# O `regerar_v10` RETOMA de onde parou: base que ja tem `validacao_balanco.json`
# e pulada. Entao rodar isto duas vezes por engano nao refaz nada, e se a
# maquina reiniciar no meio basta chamar de novo.

$ErrorActionPreference = 'Continue'
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

$log = Join-Path $raiz 'logs\v19_console.log'
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null

# Marca de largada num arquivo proprio: se o python nem chegar a subir, e aqui
# que se descobre. O `_console.log` sozinho ficaria vazio e nao diria se o
# problema foi a tarefa agendada ou o programa.
$partida = Join-Path $raiz 'logs\v19_partida.log'
"$(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')  tarefa disparada" | Add-Content $partida
"cwd: $raiz" | Add-Content $partida

$py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" }
"python: $py" | Add-Content $partida

# --- IMPEDIR QUE A MAQUINA DURMA NO MEIO DA RODADA ------------------------
# Medido em 23/08/2026: esta maquina suspende E hiberna apos 3.600 s ociosa na
# tomada (STANDBYIDLE e HIBERNATEIDLE = 0x00000e10). O contador de ocioso do
# Windows olha ENTRADA DO USUARIO, nao uso de CPU — processo ocupado nao
# segura a maquina acordada. Com ninguem em casa, a V19 comecaria as 21:00 e
# dormiria por volta das 22:00, na primeira base.
#
# `SetThreadExecutionState` resolve pelo caminho certo: vale so enquanto ESTE
# processo viver, e some sozinho quando ele terminar. Mexer no esquema de
# energia da maquina resolveria tambem, mas seria mudar uma configuracao do
# computador do Elder para sempre, por causa de uma noite.
Add-Type -Namespace Win32 -Name Sono -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
# 2147483648 em decimal, e nao 0x80000000: o PowerShell 5.1 le o literal hexa
# como Int32 com sinal, vira -2147483648, e o [uint32] recusa com "Valor era
# muito grande ou muito pequeno". O script seguiria com $ErrorActionPreference
# = 'Continue', a chamada nao aconteceria, e a maquina dormiria as 22:00 sem
# nada no log dizendo por que.
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1
$ES_AWAYMODE_REQUIRED = [uint32]64
$r = [Win32.Sono]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED)
if ($r -eq 0) {
  # away mode nao existe em toda maquina; sem ele, o basico ainda segura
  $r = [Win32.Sono]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
}
"sono bloqueado: $(if ($r -ne 0) { 'sim' } else { 'FALHOU — a maquina pode dormir' })" | Add-Content $partida

# `git` pode nao estar no PATH da tarefa agendada; o regerar so o usa para
# carimbar o commit no cabecalho, e ja trata a ausencia.
& $py -u regerar_v10.py --sufixo V19 --jobs 8 *>&1 | Out-File -FilePath $log -Encoding utf8

"$(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')  tarefa terminou (exit $LASTEXITCODE)" | Add-Content $partida

# devolve o controle do sono ao Windows
try { [Win32.Sono]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null } catch {}
