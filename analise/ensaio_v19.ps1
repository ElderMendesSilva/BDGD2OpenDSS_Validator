# Ensaio da tarefa agendada: faz tudo o que a V19 fara, menos rodar a V19.
#
# POR QUE EXISTE. Uma tarefa do Agendador roda num ambiente que NAO e o do
# terminal: outro diretorio de trabalho, outro PATH, outra politica de
# execucao. Descobrir isso as 21:05, com ninguem em casa, custa a noite.
#
# Confere, na ordem em que cada coisa mataria a rodada:
#   1. o PowerShell sobe com a politica de execucao permitida;
#   2. o diretorio de trabalho cai na raiz do repositorio;
#   3. o python.exe e encontrado pelo PATH da TAREFA, que nao e o meu;
#   4. o log e gravavel;
#   5. o bloqueio de sono funciona (foi o que quase falhou calado);
#   6. o python consegue importar o projeto inteiro.

$ErrorActionPreference = 'Continue'
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz
$out = Join-Path $raiz 'logs\ensaio_v19.log'
New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
Remove-Item $out -ErrorAction SilentlyContinue

function Diz($m) { "$(Get-Date -Format 'HH:mm:ss')  $m" | Add-Content $out }

Diz "1. politica de execucao: $(Get-ExecutionPolicy)"
Diz "2. diretorio de trabalho: $(Get-Location)"
Diz "   regerar_v10.py existe: $(Test-Path (Join-Path $raiz 'regerar_v10.py'))"

$py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" }
Diz "3. python: $py  (existe: $(Test-Path $py))"

Diz "4. log gravavel: sim, esta linha e a prova"

Add-Type -Namespace Ens -Name Sono -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$C = [uint32]2147483648; $SR = [uint32]1; $AW = [uint32]64
$r = [Ens.Sono]::SetThreadExecutionState($C -bor $SR -bor $AW)
Diz "5. bloqueio de sono: $r  ($(if ($r -ne 0) { 'OK' } else { 'FALHOU' }))"
[Ens.Sono]::SetThreadExecutionState($C) | Out-Null

$v = & $py -c "import sys, os; sys.path.insert(0, os.getcwd()); import regerar_v10, converter, verifica, ligacao, ampacidade, validador, valida_perdas, valida_balanco, energia; print('imports ok |', len(regerar_v10.descobrir()), 'bases visiveis')" 2>&1
Diz "6. python importa o projeto: $v"
Diz 'ensaio terminado'
