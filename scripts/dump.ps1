[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameAssembly,

    [Parameter(Mandatory = $true)]
    [string]$Metadata,

    [string]$OutDir = ".\dumps",

    [string]$Dumper = "",

    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $GameAssembly -PathType Leaf)) {
    Fail "GameAssembly.dll not found: $GameAssembly"
}
if (-not (Test-Path -LiteralPath $Metadata -PathType Leaf)) {
    Fail "global-metadata.dat not found: $Metadata"
}

$gamePath = (Resolve-Path -LiteralPath $GameAssembly).Path
$metaPath = (Resolve-Path -LiteralPath $Metadata).Path

if (Test-Path -LiteralPath $OutDir) {
    $existing = Get-ChildItem -LiteralPath $OutDir -Force | Select-Object -First 1
    if ($existing -and -not $Force) {
        Fail "output directory is not empty: $OutDir (pass -Force to reuse it)"
    }
} else {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
$outPath = (Resolve-Path -LiteralPath $OutDir).Path

if (-not $Dumper) {
    $candidates = @()
    if ($env:IL2CPP_DUMPER) { $candidates += $env:IL2CPP_DUMPER }
    $candidates += @(
        ".\tools\Il2CppDumper-v39\Il2CppDumper\bin\Release\net8.0\Il2CppDumper.dll",
        ".\tools\Il2CppDumper\Il2CppDumper.exe",
        ".\tools\Il2CppDumper\Il2CppDumper.dll"
    )
    $Dumper = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}

if (-not $Dumper -or -not (Test-Path -LiteralPath $Dumper -PathType Leaf)) {
    Fail "Il2CppDumper not found. Pass -Dumper <path>, set IL2CPP_DUMPER, or put it in .\tools\Il2CppDumper."
}

$dumperPath = (Resolve-Path -LiteralPath $Dumper).Path
$dumperDir = Split-Path -Parent $dumperPath
$ext = [System.IO.Path]::GetExtension($dumperPath)

# Metadata v39 (Unity 6000.x) needs the v39 fork built for net8.0.
# Roll forward so it also runs when only newer .NET runtimes are installed.
$env:DOTNET_ROLL_FORWARD = "LatestMajor"

# A fresh Il2CppDumper clone waits for a key press and hangs unattended runs.
# The config can live next to the DLL, or at the project root of a source build
# (e.g. bin/Release/net8.0 -> ../../../config.json). Search both, then fall
# back to piping a newline into the process.
$configCandidates = @(
    (Join-Path $dumperDir "config.json"),
    (Join-Path (Split-Path -Parent $dumperDir) "config.json"),
    (Join-Path (Split-Path -Parent (Split-Path -Parent $dumperDir)) "config.json"),
    (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $dumperDir))) "config.json")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique

$configFixed = $false
foreach ($configPath in $configCandidates) {
    try {
        $raw = Get-Content -LiteralPath $configPath -Raw
        $config = $raw | ConvertFrom-Json
        if (-not ($config.PSObject.Properties["RequireAnyKey"] -and $config.RequireAnyKey)) {
            continue
        }
        $config.RequireAnyKey = $false
        $config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $configPath -Encoding UTF8
        Write-Host "Set RequireAnyKey=false in $configPath" -ForegroundColor Yellow
        $configFixed = $true
    } catch {
        Write-Warning "Could not update $configPath : $($_.Exception.Message)"
    }
}
if (-not $configFixed) {
    Write-Warning "RequireAnyKey config not found or already false; feeding a newline to stdin as fallback."
}

Write-Host "GameAssembly : $gamePath"
Write-Host "Metadata     : $metaPath"
Write-Host "Output       : $outPath"
Write-Host "Dumper       : $dumperPath"
Write-Host ""

Push-Location $dumperDir
try {
    # A single newline satisfies "Press any key" when the config fix did not
    # apply. Harmless when RequireAnyKey is already false.
    if ($ext -ieq ".dll") {
        "" | & dotnet $dumperPath $gamePath $metaPath $outPath
    } else {
        "" | & $dumperPath $gamePath $metaPath $outPath
    }
} finally {
    Pop-Location
}

if ($LASTEXITCODE -ne 0) {
    Fail "Il2CppDumper exited with code $LASTEXITCODE"
}

$dumpFile = Join-Path $outPath "dump.cs"
if (-not (Test-Path -LiteralPath $dumpFile -PathType Leaf)) {
    Fail "dump.cs was not produced. Check the Il2CppDumper version and the game files."
}

Write-Host ""
Write-Host "Output files:" -ForegroundColor Green
Get-ChildItem -LiteralPath $outPath |
    Sort-Object Name |
    Select-Object Name, @{ Name = "SizeMB"; Expression = { "{0:N2}" -f ($_.Length / 1MB) } } |
    Format-Table -AutoSize

Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  python .\scripts\find_type.py `"$dumpFile`" <ClassName> --kind class"
