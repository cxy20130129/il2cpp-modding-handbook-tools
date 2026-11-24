[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$results = @()

function Add-Result {
    param(
        [string]$Name,
        [bool]$Ok,
        [bool]$Required,
        [string]$Detail
    )
    $script:results += [pscustomobject]@{
        Tool     = $Name
        Status   = if ($Ok) { "OK" } else { "MISSING" }
        Required = if ($Required) { "yes" } else { "no" }
        Detail   = $Detail
    }
}

# Python
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $version = ((& python --version) -join " ").Trim()
    $pyOk = $false
    if ($version -match "Python\s+(\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        $pyOk = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
    }
    if ($pyOk) {
        Add-Result "Python" $true $true $version
    } else {
        Add-Result "Python" $false $true "$version (need 3.10+)"
    }
} else {
    Add-Result "Python" $false $true "install Python 3.10+ and add it to PATH"
}

# .NET SDK
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if ($dotnet) {
    $version = ((& dotnet --version) -join " ").Trim()
    Add-Result ".NET SDK" $true $true $version
} else {
    Add-Result ".NET SDK" $false $true "install .NET SDK 6/8+"
}

# Git
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    $version = ((& git --version) -join " ").Trim()
    Add-Result "Git" $true $false $version
} else {
    Add-Result "Git" $false $false "optional, needed to clone this repo"
}

# Il2CppDumper
$dumperCandidates = @()
if ($env:IL2CPP_DUMPER) { $dumperCandidates += $env:IL2CPP_DUMPER }
$dumperCandidates += @(
    ".\tools\Il2CppDumper-v39\Il2CppDumper\bin\Release\net8.0\Il2CppDumper.dll",
    ".\tools\Il2CppDumper\Il2CppDumper.exe",
    ".\tools\Il2CppDumper\Il2CppDumper.dll"
)
$dumper = $dumperCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if ($dumper) {
    Add-Result "Il2CppDumper" $true $true (Resolve-Path -LiteralPath $dumper).Path
} else {
    Add-Result "Il2CppDumper" $false $true "download a release, put it in .\tools\Il2CppDumper, or set IL2CPP_DUMPER"
}

# MelonLoader (optional; only needed for templates/melonloader-mod)
$melonDir = $env:MELONLOADER_DIR
if (-not $melonDir) { $melonDir = ".\tools\MelonLoader" }
if (Test-Path -LiteralPath (Join-Path $melonDir "MelonLoader.dll")) {
    Add-Result "MelonLoader" $true $false (Resolve-Path -LiteralPath $melonDir).Path
} else {
    Add-Result "MelonLoader" $false $false "set MELONLOADER_DIR to the MelonLoader folder inside your game"
}

# BepInEx 6 (optional; Iron Nest uses this instead of MelonLoader)
$bepDir = $env:BEPINEX_DIR
if (-not $bepDir -and $env:IRON_NEST_DIR) { $bepDir = Join-Path $env:IRON_NEST_DIR "BepInEx" }
if ($bepDir -and (Test-Path -LiteralPath (Join-Path $bepDir "core\BepInEx.Core.dll")) -and (Test-Path -LiteralPath (Join-Path $bepDir "interop\Assembly-CSharp.dll"))) {
    Add-Result "BepInEx 6" $true $false (Resolve-Path -LiteralPath $bepDir).Path
} else {
    Add-Result "BepInEx 6" $false $false "set BEPINEX_DIR (or IRON_NEST_DIR) and launch the game once to generate interop assemblies"
}

# 7-Zip (optional)
$sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
if ($sevenZip) {
    Add-Result "7-Zip" $true $false $sevenZip.Source
} else {
    Add-Result "7-Zip" $false $false "optional, useful for unpacking releases"
}

$results | ForEach-Object {
    Write-Host ("{0,-14} {1,-8} {2,-9} {3}" -f $_.Tool, $_.Status, $_.Required, $_.Detail)
}

$missingRequired = $results | Where-Object { $_.Required -eq "yes" -and $_.Status -ne "OK" }
if ($missingRequired) {
    Write-Host ""
    Write-Host "Required tools are missing. Fix the rows marked MISSING before dumping." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Required tools are present." -ForegroundColor Green
exit 0
