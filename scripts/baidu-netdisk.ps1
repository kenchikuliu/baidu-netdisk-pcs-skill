[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = 'Stop'

$toolRoot = Join-Path $env:USERPROFILE '.codex\tools\baidupcs-py'
$pythonMarker = Join-Path $toolRoot 'python-path.txt'
$runner = Join-Path $PSScriptRoot 'baidu_netdisk.py'

if (-not (Test-Path -LiteralPath (Join-Path $toolRoot 'installed-commit.txt')) -or
    -not (Test-Path -LiteralPath $pythonMarker)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1') | Out-Host
}

$python = (Get-Content -LiteralPath $pythonMarker -Raw).Trim()
if (-not (Test-Path -LiteralPath $python)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1') | Out-Host
    $python = (Get-Content -LiteralPath $pythonMarker -Raw).Trim()
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'A compatible Python interpreter was not found after bootstrap.'
}

$env:PYTHONPATH = Join-Path $toolRoot 'src'
$env:PYTHONWARNINGS = 'ignore'
& $python $runner @RemainingArgs
exit $LASTEXITCODE
