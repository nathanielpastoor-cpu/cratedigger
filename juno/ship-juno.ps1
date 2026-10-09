<#
  juno/ship-juno.ps1 - copy CrateDigger's code to Juno and restart the app (run on ROLAND, pwsh 7).

    pwsh juno/ship-juno.ps1            # copy -> restart -> wait for /healthz
    pwsh juno/ship-juno.ps1 -DryRun    # say what would be copied, change nothing
    pwsh juno/ship-juno.ps1 -Force     # allow a dirty tree / non-main branch

  First-time setup (once): create dataset tank/cratedigger owned by 568, then install
  juno/compose.yaml as Custom App "cratedigger" (see the README's "Hosting on Juno").
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$Force, [string]$Url = 'http://100.91.0.35:8082')

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. C:\Dev\HomeServer\Juno-Deploy.ps1
$dest = "$JunoWebShare\_conf\cratedigger"
Set-Location $repo

$dirty = git status --porcelain
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if (($dirty -or $branch -ne 'main') -and -not $Force) {
  throw "Refusing: $(if ($dirty) { 'uncommitted changes' } else { "branch '$branch' is not main" }). Commit first, or pass -Force."
}
$sha = (git rev-parse --short HEAD).Trim()

$xd = @('.git', '.github', '.claude', '__pycache__') | ForEach-Object { Join-Path $repo $_ }
$xf = @('swipe.html', 'crate.html', '*.pyc', '.gitignore')
$rc = @($repo, $dest, '/MIR', '/XD') + $xd + @('/XF') + $xf + @('/NP', '/NDL', '/NJH', '/R:2', '/W:2')
if ($DryRun) { $rc += '/L' }
Write-Host "robocopy -> $dest $(if ($DryRun) { '(dry run)' })" -ForegroundColor Cyan
robocopy @rc | Where-Object { $_ -match '\S' } | Select-Object -Last 15
if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE)." }
if ($DryRun) { return }
Set-Content -Path (Join-Path $dest 'BUILD.txt') -Value "$sha $(Get-Date -Format s)" -Encoding ascii

. C:\Dev\HomeServer\Juno-Api.ps1
try {
  Write-Host "Restarting app 'cratedigger'..." -ForegroundColor Cyan
  $null = Wait-JunoJob (Invoke-Juno 'app.stop' @('cratedigger')) -TimeoutSec 300
  $null = Wait-JunoJob (Invoke-Juno 'app.start' @('cratedigger')) -TimeoutSec 300
} finally { Disconnect-Juno }

$ok = $false
for ($i = 0; $i -lt 20 -and -not $ok; $i++) {
  try { $ok = (Invoke-WebRequest "$Url/healthz" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { Start-Sleep 3 }
}
if (-not $ok) { throw "$Url/healthz is not answering after the restart." }
$st = (Invoke-WebRequest "$Url/status.json" -UseBasicParsing -TimeoutSec 10).Content
Write-Host "Live: $Url is $sha. Last refresh: $st" -ForegroundColor Green
