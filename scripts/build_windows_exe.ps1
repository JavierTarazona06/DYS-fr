param(
    [switch]$Clean,
    [string]$PythonExe = "python",
    [string]$PythonVersion = "",
    [switch]$UsePyLauncher
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Remove-PathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path $PathValue)) {
        return
    }

    try {
        Remove-Item $PathValue -Recurse -Force -ErrorAction Stop
    }
    catch {
        Write-Warning "Could not remove '$PathValue' (likely locked by another process). Continuing..."
    }
}

function Resolve-PythonCommand {
    if ($UsePyLauncher -and $PythonVersion -and (Get-Command py -ErrorAction SilentlyContinue)) {
        return @("py", "-$PythonVersion")
    }

    # If a virtual environment is active, always prefer its interpreter.
    if ($env:VIRTUAL_ENV) {
        $venvPython = Join-Path $env:VIRTUAL_ENV "Scripts\\python.exe"
        if (Test-Path $venvPython) {
            return @($venvPython)
        }
    }

    # If a local project venv exists, prefer it even if activation is missing.
    $localVenvPython = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path ".venv\\Scripts\\python.exe"
    if (Test-Path $localVenvPython) {
        return @($localVenvPython)
    }
    return @($PythonExe)
}

$PythonCommand = @(Resolve-PythonCommand)
$PythonDisplay = ($PythonCommand -join " ")

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if ($PythonCommand.Length -gt 1) {
        & $PythonCommand[0] $PythonCommand[1..($PythonCommand.Length - 1)] @Arguments
    }
    else {
        & $PythonCommand[0] @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed ($LASTEXITCODE): $PythonDisplay $($Arguments -join ' ')"
    }
}

function Copy-DirectorySafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    if (Test-Path $DestinationPath) {
        try {
            Remove-Item $DestinationPath -Recurse -Force -ErrorAction Stop
        }
        catch {
            throw "Could not replace '$DestinationPath'. Close any running DYS-fr.exe process and retry."
        }
    }
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Copy-Item -Path (Join-Path $SourcePath "*") -Destination $DestinationPath -Recurse -Force
}

# Resolve project root from this script location.
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($Clean) {
    Write-Host "Cleaning previous build artifacts..."
    Remove-PathSafe -PathValue "build"
    Remove-PathSafe -PathValue "dist"
}

Write-Host "Ensuring PyInstaller is installed..."
Write-Host ("Using Python command: " + $PythonDisplay)
if ($PythonCommand.Length -gt 1) {
    & $PythonCommand[0] $PythonCommand[1..($PythonCommand.Length - 1)] -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)" *> $null
}
else {
    & $PythonCommand[0] -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)" *> $null
}

if ($LASTEXITCODE -ne 0) {
    Invoke-Python -Arguments @("-m", "pip", "install", "--upgrade", "pyinstaller")
}

Write-Host "Building Windows executable with PyInstaller..."
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$localBuildRoot = Join-Path $env:TEMP "dysfr-pyinstaller"
$workPath = Join-Path $localBuildRoot ("work-" + $timestamp)
$distPath = Join-Path $localBuildRoot ("dist-" + $timestamp)

if (Test-Path $workPath) { Remove-PathSafe -PathValue $workPath }
if (Test-Path $distPath) { Remove-PathSafe -PathValue $distPath }

Invoke-Python -Arguments @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--distpath", $distPath,
    "--workpath", $workPath,
    "packaging/windows/build.spec"
)

$localAppDist = Join-Path $distPath "DYS-fr"
$projectDistRoot = Join-Path $ProjectRoot "dist"
$projectAppDist = Join-Path $projectDistRoot "DYS-fr"
$finalAppDist = $projectAppDist

if (-not (Test-Path $localAppDist)) {
    throw "Build completed but output folder was not found at: $localAppDist"
}

if (-not (Test-Path $projectDistRoot)) {
    New-Item -ItemType Directory -Path $projectDistRoot -Force | Out-Null
}

try {
    Copy-DirectorySafe -SourcePath $localAppDist -DestinationPath $projectAppDist
}
catch {
    $fallbackDist = Join-Path $projectDistRoot ("DYS-fr-" + $timestamp)
    Write-Warning "Default output folder is locked. Writing build to: $fallbackDist"
    Copy-DirectorySafe -SourcePath $localAppDist -DestinationPath $fallbackDist
    $finalAppDist = $fallbackDist
}

$finalExe = Join-Path $finalAppDist "DYS-fr.exe"

Write-Host ""
Write-Host "Build finished."
Write-Host ("Executable: " + $finalExe)
