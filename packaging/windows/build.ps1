param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$JreDir = $env:DYS_FR_JRE_DIR,
    [string]$AppVersion = "0.1.0",
    [string]$StageRoot = "build\staging\basic",
    [string]$DistPath = "build\pyinstaller-dist",
    [string]$WorkPath = "build\pyinstaller-work",
    [string]$InstallerOutputDir = "build\installer",
    [string]$IsccExe = "",
    [switch]$IncludeHybrid
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Resolve-ProjectPath([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $projectRoot $PathValue))
}

$pythonPath = Resolve-ProjectPath $PythonExe
$stageScript = Join-Path $projectRoot "packaging\windows\stage_assets.py"
$specPath = Join-Path $projectRoot "packaging\windows\dys_fr.spec"
$issPath = Join-Path $projectRoot "packaging\windows\installer.iss"
$resolvedStageRoot = Resolve-ProjectPath $StageRoot
$resolvedDistPath = Resolve-ProjectPath $DistPath
$resolvedWorkPath = Resolve-ProjectPath $WorkPath
$resolvedInstallerOutputDir = Resolve-ProjectPath $InstallerOutputDir
$resolvedAppDistDir = Join-Path $resolvedDistPath "DYS-fr"

if (!(Test-Path $pythonPath)) {
    throw "Python interpreter not found at $pythonPath"
}

$previousIncludeHybrid = $env:DYS_FR_INCLUDE_HYBRID
$env:DYS_FR_INCLUDE_HYBRID = if ($IncludeHybrid) { "1" } else { "0" }

try {
    $stageArgs = @($stageScript, "--stage-root", $resolvedStageRoot)
    if ($JreDir) {
        $stageArgs += @("--jre-dir", $JreDir)
    }
    if ($IncludeHybrid) {
        $stageArgs += "--include-hybrid"
    }

    Write-Host "Staging runtime assets..."
    & $pythonPath @stageArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Asset staging failed with exit code $LASTEXITCODE"
    }

    Write-Host "Building PyInstaller bundle..."
    & $pythonPath -m PyInstaller --noconfirm --clean --distpath $resolvedDistPath --workpath $resolvedWorkPath $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }

    if (-not $IsccExe) {
        $isccCandidates = @(
            "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        foreach ($candidate in $isccCandidates) {
            if (Test-Path $candidate) {
                $IsccExe = $candidate
                break
            }
        }
    }

    if ($IsccExe -and (Test-Path $IsccExe)) {
        New-Item -ItemType Directory -Force -Path $resolvedInstallerOutputDir | Out-Null
        Write-Host "Building Inno Setup installer..."
        & $IsccExe "/DAppVersion=$AppVersion" "/DAppDistDir=$resolvedAppDistDir" "/DOutputDir=$resolvedInstallerOutputDir" $issPath
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed with exit code $LASTEXITCODE"
        }
    }
    else {
        Write-Warning "ISCC.exe was not found. The PyInstaller bundle was created, but the installer step was skipped."
    }

    Write-Host "Build complete."
}
finally {
    if ($null -eq $previousIncludeHybrid) {
        Remove-Item Env:DYS_FR_INCLUDE_HYBRID -ErrorAction SilentlyContinue
    }
    else {
        $env:DYS_FR_INCLUDE_HYBRID = $previousIncludeHybrid
    }
}
