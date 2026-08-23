# Resfria a maquina antes da V19: mata tudo o que nao for preciso.
#
# POR QUE EXISTE. Em 23/08/2026 havia SETE processos zumbis vivos ao mesmo
# tempo aqui: quatro `tail -f` vigiando logs de rodadas encerradas dias antes,
# dois `until grep "FIM"` esperando uma palavra que o script nunca escreve, e
# um `amostrador.py` de 17/08 que queimou 50.888 s de CPU gravando zeros.
#
# E o aperto nao era so de CPU: as 11:32 daquele dia sobravam 3,44 GB livres
# de 15,79 GB, com Opera (2,0 GB em 20 processos), Claude (2,0 GB), Osmium
# (1,5 GB), Discord (1,0 GB) e uma VM (789 MB) segurando o resto. A V19 roda
# 9 h sozinha e a Cemig-D ja derrubou a rodada tres vezes; ela merece a
# maquina inteira.
#
# A REGRA E LISTA DE QUEM FICA, e nao lista de quem morre. Lista de quem
# morre envelhece: aplicativo novo instalado no mes que vem nao estaria nela e
# sobreviveria calado. Lista de quem fica erra para o lado seguro — no maximo
# sobra um processo, nunca falta um que o Windows precisava.
#
# FICA DE PE:
#   * o nucleo do Windows, a sessao grafica e o Explorer;
#   * o antivirus — derruba-lo e mexer em seguranca, e nao em desempenho;
#   * o Claude Code (node/claude) e o PowerShell que executa este script;
#   * qualquer processo cuja linha de comando mencione V19.

$ErrorActionPreference = 'SilentlyContinue'
$log = Join-Path $PSScriptRoot '..\logs\resfria_v19.log'
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null
function Diz($m) {
  $t = (Get-Date).ToString('dd/MM HH:mm:ss')
  "$t  $m" | Tee-Object -FilePath $log -Append
}

# --- quem sobrevive -------------------------------------------------------
$FICA = @(
  # nucleo do sistema: sem estes o Windows nao roda
  'System','Idle','Registry','Secure System','smss','csrss','wininit','winlogon',
  'services','lsass','fontdrvhost','dwm','LsaIso','MemCompression',
  'Memory Compression','svchost','spoolsv','audiodg','WUDFHost','WmiPrvSE',
  'dllhost','sihost','taskhostw','ctfmon','conhost','RuntimeBroker',
  # sessao grafica: sem estes some a area de trabalho
  'explorer','StartMenuExperienceHost','ShellExperienceHost','SearchHost',
  'TextInputHost','ApplicationFrameHost','SystemSettings','UserOOBEBroker',
  # seguranca
  'MsMpEng','NisSrv','SecurityHealthService','SecurityHealthSystray',
  'MpDefenderCoreService',
  # agendador que dispara este script, e o proprio script
  'taskeng','taskhost','powershell','pwsh',
  # Claude Code
  'claude','node'
)

# ACESSO REMOTO, VM E VPN MORREM TAMBEM. Eu levantei os tres riscos, e o
# Elder decidiu duas vezes: primeiro "pode matar tbm", e depois, ja sabendo
# que nao estaria em casa as 21:00, "nao quero olhar nada, pode matar".
# Ficam anotados porque a consequencia e real e alguem vai reler isto:
#
#   * sem AnyDesk, a rodada de 9 h corre sem ninguem podendo olhar — e essa
#     e a escolha, nao um esquecimento. O relatorio esta em logs/ pela manha;
#   * sem VPN, a rota de rede da maquina muda as 20:45;
#   * a VM some — e por isso ela e a unica que NAO morre a forca. Ver abaixo.

Diz '--- resfriando para a V19 ---'
$m0 = Get-CimInstance Win32_OperatingSystem
Diz ("antes: {0:N2} GB livres de {1:N2} GB" -f ($m0.FreePhysicalMemory/1MB), ($m0.TotalVisibleMemorySize/1MB))

$eu = $PID
$mortos = 0
$poupados = @{}

# --- a VM sai por dentro, e nao no tapa ------------------------------------
# `vmmem` e o processo que SEGURA a memoria da VM; mata-lo e o equivalente a
# arrancar a tomada, e o disco virtual pode ficar inconsistente. Desligar por
# dentro leva alguns segundos e chega no mesmo lugar: a memoria e devolvida e
# o `vmmem` some sozinho. Se algum sobreviver, a varredura abaixo pega — mas
# ai ja foi tentado o caminho limpo.
try {
  if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    Diz 'desligando o WSL por dentro (wsl --shutdown)'
    & wsl.exe --shutdown 2>&1 | Out-Null
  }
} catch { Diz "WSL nao respondeu: $_" }
try {
  $vms = Get-VM -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Running' }
  foreach ($vm in $vms) {
    Diz "desligando a VM '$($vm.Name)' por dentro (Stop-VM)"
    Stop-VM -Name $vm.Name -Force -ErrorAction SilentlyContinue
  }
} catch { Diz "Hyper-V nao respondeu: $_" }
if ((Get-Process vmmem -ErrorAction SilentlyContinue) -or $vms) { Start-Sleep -Seconds 20 }

Get-CimInstance Win32_Process | ForEach-Object {
  $p = $_
  $nome = ($p.Name -replace '\.exe$','')
  if ($FICA -contains $nome) { $poupados[$nome] = 1; return }
  if ($p.ProcessId -eq $eu -or $p.ProcessId -le 4) { return }
  if ($p.CommandLine -and $p.CommandLine -like '*V19*') {
    Diz "poupado (V19): $($p.ProcessId) $nome"; return
  }
  $mb = 0
  try { $mb = [int]((Get-Process -Id $p.ProcessId).WorkingSet64 / 1MB) } catch {}
  Diz "matando $nome ($($p.ProcessId), $mb MB)"
  Stop-Process -Id $p.ProcessId -Force
  $script:mortos++
}

Start-Sleep -Seconds 5
$m1 = Get-CimInstance Win32_OperatingSystem
Diz "mortos: $mortos"
Diz ("depois: {0:N2} GB livres de {1:N2} GB" -f ($m1.FreePhysicalMemory/1MB), ($m1.TotalVisibleMemorySize/1MB))
Diz ("ganho: {0:N2} GB" -f (($m1.FreePhysicalMemory - $m0.FreePhysicalMemory)/1MB))
Diz "poupados por nome: $(($poupados.Keys | Sort-Object) -join ', ')"
Diz '--- pronto para a V19 ---'
