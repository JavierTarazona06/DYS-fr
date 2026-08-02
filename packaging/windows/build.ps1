param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$JreDir = $env:DYS_FR_JRE_DIR,
    [string]$AppVersion = "0.1.0",
    [string]$StageRoot = "",
    [string]$DistPath = "build\pyinstaller-dist",
    [string]$RuntimeDistPath = "build\pyinstaller-runtime",
    [string]$WorkPath = "build\pyinstaller-work",
    [string]$PortableWorkDir = "build\portable",
    [string]$InstallerOutputDir = "build\installer",
    [string]$IsccExe = "",
    [string]$GccExe = "gcc",
    [string]$RuntimeManifestUrl = "",
    [string]$ReleaseBaseUrl = "",
    [string]$MistralUrl = "https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
    [switch]$IncludeAiRuntime,
    [switch]$IncludeMistralModel,
    [switch]$IncludeHybrid,
    [ValidateSet('installer', 'portable', 'both')]
    [string]$Channel = 'installer',
    [string]$SignToolExe = "",
    [string]$SignCertThumbprint = "",
    [string]$SignTimestampUrl = "http://timestamp.digicert.com",
    [switch]$FastCompression
)

$ErrorActionPreference = "Stop"

# -IncludeHybrid conflated two orthogonal things: bundling the local-LLM runtime
# (llama_cpp/ollama, read by dys_fr.spec) and staging the 4.1 GB GGUF (stage_assets.py).
# Kept as an alias for both so documented invocations keep working.
if ($IncludeHybrid) {
    Write-Warning "-IncludeHybrid is deprecated. Use -IncludeAiRuntime and/or -IncludeMistralModel."
    $IncludeAiRuntime = $true
    $IncludeMistralModel = $true
}
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

function ConvertTo-CStringLiteral([string]$Value, [switch]$Wide) {
    $escaped = $Value.Replace("\", "\\").Replace('"', '\"')
    if ($Wide) {
        return "L`"$escaped`""
    }
    return "`"$escaped`""
}

function Resolve-IsccExe([string]$Explicit) {
    if ($Explicit) {
        if (!(Test-Path $Explicit)) {
            throw "Inno Setup compiler not found at $Explicit"
        }
        return $Explicit
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        # Installing unelevated (winget, for instance) lands here instead.
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $onPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }

    # Deliberately fatal. The previous pipeline warned and continued, which is how the
    # installer silently rotted for five months while the build still reported success.
    throw "Inno Setup 6.3+ is required for -Channel installer. Install it or pass -IsccExe."
}

function Invoke-CodeSign([string]$Path) {
    if (!$SignCertThumbprint) {
        Write-Warning "UNSIGNED: $Path -- SmartScreen will warn end users. See docs/windows_release_checklist.md."
        return
    }

    $signTool = if ($SignToolExe) { $SignToolExe } else { (Get-Command "signtool.exe" -ErrorAction Stop).Source }
    & $signTool sign /sha1 $SignCertThumbprint /fd SHA256 /tr $SignTimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for $Path with exit code $LASTEXITCODE"
    }
}

function Stop-RunningBundleProcesses([string]$BundleRoot) {
    if (!(Test-Path $BundleRoot)) {
        return
    }

    $normalizedBundleRoot = [System.IO.Path]::GetFullPath($BundleRoot)
    $matchingProcesses = Get-Process | Where-Object {
        $_.Path -and ([System.IO.Path]::GetFullPath($_.Path).StartsWith($normalizedBundleRoot, [System.StringComparison]::OrdinalIgnoreCase))
    }

    if (!$matchingProcesses) {
        return
    }

    Write-Warning "Stopping running DYS-fr bundle processes before rebuild..."
    foreach ($process in $matchingProcesses) {
        Write-Host ("  - PID {0}: {1}" -f $process.Id, $process.Path)
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 1
}

$pythonPath = Resolve-ProjectPath $PythonExe
$stageScript = Join-Path $projectRoot "packaging\windows\stage_assets.py"
$specPath = Join-Path $projectRoot "packaging\windows\dys_fr.spec"
$bootstrapSource = Join-Path $projectRoot "packaging\windows\portable_bootstrap.c"
$portablePackager = Join-Path $projectRoot "packaging\windows\package_portable.py"
$flavor = if ($IncludeAiRuntime) { "hybrid" } else { "basic" }
if ([string]::IsNullOrWhiteSpace($StageRoot)) {
    $StageRoot = "build\staging\$flavor"
}

$defaultReleaseBaseUrl = "https://github.com/JavierTarazona06/DYS-fr/releases/download/v$AppVersion"
if ([string]::IsNullOrWhiteSpace($ReleaseBaseUrl)) {
    $ReleaseBaseUrl = $defaultReleaseBaseUrl
}
$componentManifestName = "DYS-fr-components-$AppVersion-$flavor.json"
if ([string]::IsNullOrWhiteSpace($RuntimeManifestUrl)) {
    $RuntimeManifestUrl = "$($ReleaseBaseUrl.TrimEnd('/'))/$componentManifestName"
}

$resolvedStageRoot = Resolve-ProjectPath $StageRoot
$resolvedDistPath = Resolve-ProjectPath $DistPath
$resolvedRuntimeDistPath = Resolve-ProjectPath $RuntimeDistPath
$resolvedWorkPath = Resolve-ProjectPath $WorkPath
$resolvedPortableWorkDir = Resolve-ProjectPath $PortableWorkDir
$resolvedRuntimeBundleDir = Join-Path $resolvedRuntimeDistPath "DYS-fr-runtime"
$resolvedPortableExe = Join-Path $resolvedDistPath "DYS-fr.exe"
$resolvedComponentManifest = Join-Path $resolvedDistPath $componentManifestName
$resolvedLegacyAppDistDir = Join-Path $resolvedDistPath "DYS-fr"
$resolvedBootstrapConfig = Join-Path $resolvedPortableWorkDir "portable_bootstrap_config.h"
$resolvedInstallerOutputDir = Resolve-ProjectPath $InstallerOutputDir
$issPath = Join-Path $projectRoot "packaging\windows\installer.iss"

if (!(Test-Path $pythonPath)) {
    throw "Python interpreter not found at $pythonPath"
}

if ($Channel -in 'portable', 'both') {
    if (!(Get-Command $GccExe -ErrorAction SilentlyContinue)) {
        throw "GCC compiler not found. Install MinGW-w64 or pass -GccExe with a compiler path."
    }
}

$isccExePath = $null
if ($Channel -in 'installer', 'both') {
    $isccExePath = Resolve-IsccExe $IsccExe
    Write-Host "Inno Setup compiler: $isccExePath"
}

$previousIncludeHybrid = $env:DYS_FR_INCLUDE_HYBRID
$previousStageRoot = $env:DYS_FR_STAGE_ROOT
$env:DYS_FR_INCLUDE_HYBRID = if ($IncludeAiRuntime) { "1" } else { "0" }
$env:DYS_FR_STAGE_ROOT = $resolvedStageRoot

try {
    Stop-RunningBundleProcesses -BundleRoot $resolvedRuntimeBundleDir
    Stop-RunningBundleProcesses -BundleRoot $resolvedLegacyAppDistDir

    $stageArgs = @($stageScript, "--stage-root", $resolvedStageRoot)
    if ($JreDir) {
        $stageArgs += @("--jre-dir", $JreDir)
    }
    if ($IncludeMistralModel) {
        $stageArgs += "--include-hybrid"
    }

    Write-Host "Staging $flavor runtime assets..."
    & $pythonPath @stageArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Asset staging failed with exit code $LASTEXITCODE"
    }

    if ($Channel -in 'installer', 'both') {
        $stagedModelsDir = Join-Path $resolvedStageRoot "resources\models"
        if ((Test-Path $stagedModelsDir) -and (Get-ChildItem $stagedModelsDir -File -Recurse -ErrorAction SilentlyContinue)) {
            throw "Stage root contains $stagedModelsDir. The installer channel ships no model; the download happens in-app."
        }
    }

    Write-Host "Building PyInstaller runtime bundle..."
    & $pythonPath -m PyInstaller --noconfirm --clean --distpath $resolvedRuntimeDistPath --workpath $resolvedWorkPath $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }

    New-Item -ItemType Directory -Force -Path $resolvedDistPath | Out-Null

    if (Test-Path $resolvedLegacyAppDistDir) {
        Remove-Item -Recurse -Force $resolvedLegacyAppDistDir
    }

    Invoke-CodeSign (Join-Path $resolvedRuntimeBundleDir "DYS-fr-runtime.exe")

    if ($Channel -in 'portable', 'both') {
        New-Item -ItemType Directory -Force -Path $resolvedPortableWorkDir | Out-Null
        if (Test-Path $resolvedPortableExe) {
            Remove-Item -Force $resolvedPortableExe
        }

        Write-Host "Packaging downloadable runtime components and release manifest..."
        $packagerArgs = @(
            $portablePackager,
            "--runtime-root", $resolvedRuntimeBundleDir,
            "--stage-root", $resolvedStageRoot,
            "--output-dir", $resolvedDistPath,
            "--output-manifest", $resolvedComponentManifest,
            "--app-version", $AppVersion,
            "--flavor", $flavor,
            "--release-base-url", $ReleaseBaseUrl,
            "--mistral-url", $MistralUrl
        )
        & $pythonPath @packagerArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Runtime component generation failed with exit code $LASTEXITCODE"
        }

        $configLines = @(
            ("#define DYS_FR_MANIFEST_URL {0}" -f (ConvertTo-CStringLiteral $RuntimeManifestUrl -Wide)),
            ("#define DYS_FR_APP_VERSION {0}" -f (ConvertTo-CStringLiteral $AppVersion)),
            ("#define DYS_FR_FLAVOR {0}" -f (ConvertTo-CStringLiteral $flavor))
        )
        $configLines | Set-Content -Path $resolvedBootstrapConfig -Encoding ascii

        Write-Host "Compiling lightweight downloader launcher..."
        & $GccExe -O2 -Wall -Wextra -municode -mwindows "-I$resolvedPortableWorkDir" $bootstrapSource -o $resolvedPortableExe -lwinhttp -lbcrypt -lcomctl32
        if ($LASTEXITCODE -ne 0) {
            throw "Launcher compilation failed with exit code $LASTEXITCODE"
        }
    }

    $setupExe = $null
    if ($Channel -in 'installer', 'both') {
        New-Item -ItemType Directory -Force -Path $resolvedInstallerOutputDir | Out-Null

        $isccArgs = @()
        if ($FastCompression) {
            $isccArgs += "/DFastCompression"
            Write-Host "Compiling Inno Setup installer (fast compression, larger output)..."
        }
        else {
            Write-Host "Compiling Inno Setup installer. Maximum solid compression over ~1.1 GB takes HOURS; pass -FastCompression while iterating."
        }

        & $isccExePath @isccArgs `
            "/DAppVersion=$AppVersion" `
            "/DRuntimeDir=$resolvedRuntimeBundleDir" `
            "/DStageDir=$resolvedStageRoot" `
            "/DOutputDir=$resolvedInstallerOutputDir" `
            $issPath
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
        }

        $setupExe = Join-Path $resolvedInstallerOutputDir "DYS-fr-Setup-$AppVersion.exe"
        if (!(Test-Path $setupExe)) {
            throw "Inno Setup reported success but $setupExe is missing."
        }
        Invoke-CodeSign $setupExe
    }

    Write-Host "Build complete."
    if ($setupExe) {
        $setupSizeMb = [math]::Round((Get-Item $setupExe).Length / 1MB, 1)
        $setupHash = (Get-FileHash $setupExe -Algorithm SHA256).Hash
        Write-Host "Installer: $setupExe ($setupSizeMb MB)"
        Write-Host "SHA-256:   $setupHash"
    }
    if ($Channel -in 'portable', 'both') {
        Write-Host "Launcher: $resolvedPortableExe"
        Write-Host "Component manifest: $resolvedComponentManifest"
        Write-Host "Manifest URL compiled into launcher: $RuntimeManifestUrl"
    }
}
finally {
    if ($null -eq $previousIncludeHybrid) {
        Remove-Item Env:DYS_FR_INCLUDE_HYBRID -ErrorAction SilentlyContinue
    }
    else {
        $env:DYS_FR_INCLUDE_HYBRID = $previousIncludeHybrid
    }

    if ($null -eq $previousStageRoot) {
        Remove-Item Env:DYS_FR_STAGE_ROOT -ErrorAction SilentlyContinue
    }
    else {
        $env:DYS_FR_STAGE_ROOT = $previousStageRoot
    }
}
