param()
$Root = Split-Path -Parent $PSScriptRoot
$Control = Join-Path $Root 'results\overnight-20260712\orchestrator-status.json'
$ResultRoot = Join-Path $Root 'results\overnight-20260712\uci'
if (!(Test-Path -LiteralPath $Control)) { throw 'orchestrator control file is missing' }
$State = Get-Content -LiteralPath $Control -Raw | ConvertFrom-Json
$Process = if ($State.pid) { Get-Process -Id $State.pid -ErrorAction SilentlyContinue } else { $null }
$Recent = Get-ChildItem -LiteralPath $ResultRoot -Recurse -Filter status.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
[pscustomobject]@{
    orchestrator_status = $State.status; attack = $State.attack; phase = $State.phase
    updated = $State.updated; pid_alive = [bool]$Process
    latest_run_status = if ($Recent) { (Get-Content $Recent.FullName -Raw | ConvertFrom-Json).status } else { $null }
    latest_status_file = if ($Recent) { $Recent.FullName.Replace($Root,'<PROJECT_ROOT>') } else { $null }
} | ConvertTo-Json -Depth 3
