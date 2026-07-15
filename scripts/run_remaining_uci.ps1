param(
    [switch]$DryRun,
    [switch]$StopAfterCurrent
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Runner = Join-Path $PSScriptRoot 'run_uci_experiment.py'
$ResultRoot = Join-Path $Root 'results\overnight-20260712'
$DataRoot = Join-Path $Root 'data\kitsune'
$Control = Join-Path $ResultRoot 'orchestrator-status.json'
$LogRoot = Join-Path $ResultRoot 'orchestrator-logs'
$Attacks = @('os_scan','fuzzing','ssl_renegotiation','arp_mitm','syn_dos','active_wiretap','ssdp_flood','video_injection')

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
function Save-Control([string]$Status, [string]$Attack, [string]$Phase, [string]$Message) {
    @{ status=$Status; attack=$Attack; phase=$Phase; pid=$PID; updated=(Get-Date).ToUniversalTime().ToString('o'); message=$Message } |
        ConvertTo-Json | Set-Content -LiteralPath $Control -Encoding utf8
}
function Find-File([string]$Dir, [string]$Needle) {
    # Prefer the largest candidate: incomplete browser extractions are smaller
    # than their complete source archive/CSV counterparts.
    Get-ChildItem -LiteralPath $Dir -File | Where-Object { $_.Name -match $Needle -and $_.Name -match '\.csv(\.gz)?$' } | Sort-Object Length -Descending | Select-Object -First 1
}
function Disk-Ready {
    # Gzip is streamed by the runner; keep a 20 GiB safety reserve for RMSE/log artifacts.
    (Get-PSDrive -Name D).Free -ge 20GB
}

if (!(Test-Path -LiteralPath $Python)) { throw "project venv missing: $Python" }
if (!(Test-Path -LiteralPath $Runner)) { throw "runner missing: $Runner" }
Save-Control 'running' '' '' 'orchestrator started'

foreach ($Attack in $Attacks) {
    $Dir = Join-Path $DataRoot $Attack
    $Feature = Find-File $Dir 'dataset'
    $Labels = Find-File $Dir 'label'
    if (!$Feature -or !$Labels) {
        Save-Control 'blocked' $Attack '' 'dataset or labels file missing'; continue
    }
    foreach ($Phase in @('smoke-1000','smoke-10000','full')) {
        $StatusFile = Join-Path $ResultRoot "uci\$Attack\$Phase\status.json"
        if (Test-Path -LiteralPath $StatusFile) {
            $Existing = Get-Content -LiteralPath $StatusFile -Raw | ConvertFrom-Json
            if ($Existing.status -in @('smoke_passed','completed')) { continue }
        }
        if (!(Disk-Ready)) { Save-Control 'blocked' $Attack $Phase 'less than 20 GiB free'; break }
        Save-Control 'running' $Attack $Phase 'starting phase'
        $Log = Join-Path $LogRoot "$Attack-$Phase.log"
        $Args = @($Runner,'--attack',$Attack,'--feature',$Feature.FullName,'--labels',$Labels.FullName,'--phase',$Phase,'--output-dir',$ResultRoot,'--no-overwrite')
        if ($DryRun) { "DRY RUN: $Python $($Args -join ' ')" | Tee-Object -FilePath $Log -Append; continue }
        & $Python @Args *>&1 | Tee-Object -FilePath $Log -Append
        if ($LASTEXITCODE -ne 0) { Save-Control 'failed' $Attack $Phase "runner exit code $LASTEXITCODE"; break }
        if (!(Test-Path -LiteralPath $StatusFile)) { Save-Control 'failed' $Attack $Phase 'runner did not write status.json'; break }
        $Actual = (Get-Content -LiteralPath $StatusFile -Raw | ConvertFrom-Json).status
        $Expected = if ($Phase -eq 'full') { 'completed' } else { 'smoke_passed' }
        if ($Actual -ne $Expected) { Save-Control 'failed' $Attack $Phase "unexpected status $Actual"; break }
        Save-Control 'running' $Attack $Phase 'phase verified'
    }
    if ($StopAfterCurrent) { break }
}
Save-Control 'finished' '' '' 'orchestrator reached end of queue'
