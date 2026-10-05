param(
    [switch]$Aws,
    [ValidateSet('mixed', 'vendor_a', 'vendor_b')][string]$Vendor = 'mixed',
    [ValidateRange(1, 3)][int]$Cycles = 3
)
$ErrorActionPreference = 'Stop'
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvExecutable = if ($uvCommand) { $uvCommand.Source } else {
    Get-ChildItem -Path "$env:LOCALAPPDATA/Microsoft/WinGet/Packages/astral-sh.uv_*/uv.exe" -File |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $uvExecutable) { throw 'uv is missing. Install uv before running the simulator.' }
$repoDirectory = Split-Path $PSScriptRoot -Parent
$replayArguments = @('run', 'python', '-m', 'simulator.transport', '--vendor', $Vendor, '--cycles', "$Cycles")
if ($Aws) { $replayArguments += @('--aws', '--profile', 'default') }
Push-Location $repoDirectory
try {
    & $uvExecutable @replayArguments
    if ($LASTEXITCODE -ne 0) { throw "Alarm replay failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
