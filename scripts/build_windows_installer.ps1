param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot $Python
if (Test-Path -LiteralPath $ProjectPython) {
    $PythonPath = (Resolve-Path -LiteralPath $ProjectPython).Path
} else {
    $PythonPath = (Get-Command $Python -ErrorAction Stop).Source
}
$BuildRoot = Join-Path $ProjectRoot "build\windows"
$DistRoot = Join-Path $ProjectRoot "dist\windows"
$AppDist = Join-Path $DistRoot "app"
$AppBundle = Join-Path $AppDist "ResearchAssistant"
$DesktopUi = Join-Path $ProjectRoot "app\desktop_ui"
$DesktopTokens = Join-Path $ProjectRoot "app\static\css\tokens.css"
$LucideIcons = Join-Path $ProjectRoot "app\static\vendor\lucide.min.js"
$Migrations = Join-Path $ProjectRoot "migrations"
$PresentationScript = Join-Path $ProjectRoot "scripts\build_weekly_presentation.mjs"
$DesktopLauncher = Join-Path $ProjectRoot "desktop_main.py"
$InstallerSource = Join-Path $ProjectRoot "packaging\windows\installer.py"
$InstallerVerifier = Join-Path $ProjectRoot "scripts\verify_windows_installer.py"

function Get-RelativeFileList {
    param([string]$Root)
    $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
    return @(
        Get-ChildItem -LiteralPath $ResolvedRoot -Recurse -File |
            ForEach-Object { $_.FullName.Substring($ResolvedRoot.Length + 1) } |
            Sort-Object
    )
}

function Assert-MirroredDirectory {
    param(
        [string]$Source,
        [string]$Bundled,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Bundled -PathType Container)) {
        throw "Bundled $Label directory is missing: $Bundled"
    }
    $Difference = @(
        Compare-Object (Get-RelativeFileList $Source) (Get-RelativeFileList $Bundled)
    )
    if ($Difference.Count -gt 0) {
        $Summary = ($Difference | Select-Object -First 12 | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join "; "
        throw "Bundled $Label files do not match the source directory: $Summary"
    }
}

Push-Location $ProjectRoot
try {
    & $PythonPath -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is missing. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
    }

    & $PythonPath -m py_compile $InstallerVerifier
    if ($LASTEXITCODE -ne 0) { throw "Windows installer verifier has invalid Python syntax." }

    $InstallerQaRoot = Join-Path $ProjectRoot (".qa\installer-build-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $InstallerQaRoot -Force | Out-Null
    & $PythonPath -m pytest --basetemp $InstallerQaRoot -q tests/test_desktop_bridge.py tests/test_desktop_service.py tests/test_desktop_runtime.py tests/test_desktop_complete_mvp.py tests/test_windows_installer_upgrade.py
    if ($LASTEXITCODE -ne 0) { throw "Windows installer upgrade checks failed." }

    Remove-Item -LiteralPath $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $DistRoot -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $BuildRoot,$AppDist -Force | Out-Null

    $appArgs = @(
        "--noconfirm", "--clean", "--windowed",
        "--name", "ResearchAssistant",
        "--distpath", $AppDist,
        "--workpath", (Join-Path $BuildRoot "app"),
        "--specpath", (Join-Path $BuildRoot "spec"),
        "--add-data", "$DesktopTokens;app\static\css",
        "--add-data", "$LucideIcons;app\static\vendor",
        "--add-data", "$DesktopUi;app\desktop_ui",
        "--add-data", "$Migrations;migrations",
        "--add-data", "$PresentationScript;scripts",
        "--hidden-import", "app.admin",
        "--hidden-import", "app.auth",
        "--hidden-import", "app.commands",
        "--hidden-import", "app.export_service",
        "--hidden-import", "app.main",
        "--hidden-import", "app.migration_service",
        "--hidden-import", "app.models",
        "--hidden-import", "app.presentation_service",
        "--hidden-import", "app.project_package",
        "--hidden-import", "app.update_service",
        "--hidden-import", "app.version",
        "--hidden-import", "app.workspace",
        "--hidden-import", "app.desktop.bridge",
        "--hidden-import", "app.desktop.native",
        "--hidden-import", "app.desktop.runtime",
        "--hidden-import", "app.desktop.single_instance",
        "--hidden-import", "app.services.desktop_modules",
        "--hidden-import", "app.services.desktop_workspace",
        "--collect-all", "webview",
        "--collect-all", "reportlab",
        "--hidden-import", "version_info",
        "--hidden-import", "logging.config",
        $DesktopLauncher
    )
    & $PythonPath -m PyInstaller @appArgs
    if ($LASTEXITCODE -ne 0) { throw "ResearchAssistant.exe build failed." }

    $BundleInternal = Join-Path $AppBundle "_internal"
    Assert-MirroredDirectory $DesktopUi (Join-Path $BundleInternal "app\desktop_ui") "desktop UI"
    Assert-MirroredDirectory $Migrations (Join-Path $BundleInternal "migrations") "migrations"
    $RequiredBundleFiles = @(
        (Join-Path $AppBundle "ResearchAssistant.exe"),
        (Join-Path $BundleInternal "app\static\css\tokens.css"),
        (Join-Path $BundleInternal "app\static\vendor\lucide.min.js"),
        (Join-Path $BundleInternal "app\desktop_ui\index.html"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop.css"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop.js"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop_research.js"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop_resources.js"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop_planning.js"),
        (Join-Path $BundleInternal "app\desktop_ui\desktop_system.js"),
        (Join-Path $BundleInternal "migrations\alembic.ini"),
        (Join-Path $BundleInternal "scripts\build_weekly_presentation.mjs")
    )
    $MissingBundleFiles = @($RequiredBundleFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($MissingBundleFiles.Count -gt 0) {
        throw "Required application files are missing from the bundle: $($MissingBundleFiles -join ', ')"
    }
    $BundledDesktop = Get-Content -LiteralPath (Join-Path $BundleInternal "app\desktop_ui\index.html") -Raw -Encoding UTF8
    if ($BundledDesktop -notmatch 'assistant-window' -or $BundledDesktop -notmatch 'project-workbench') {
        throw "The bundled desktop UI does not contain the current workspace assets."
    }

    $installerArgs = @(
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "ResearchAssistant-Setup",
        "--distpath", $DistRoot,
        "--workpath", (Join-Path $BuildRoot "installer"),
        "--specpath", (Join-Path $BuildRoot "spec"),
        "--add-data", "$AppBundle;payload\ResearchAssistant",
        "--paths", $ProjectRoot,
        "--hidden-import", "version_info",
        $InstallerSource
    )
    & $PythonPath -m PyInstaller @installerArgs
    if ($LASTEXITCODE -ne 0) { throw "ResearchAssistant-Setup.exe build failed." }

    $SetupPath = Join-Path $DistRoot "ResearchAssistant-Setup.exe"
    & $PythonPath $InstallerVerifier $SetupPath
    if ($LASTEXITCODE -ne 0) { throw "ResearchAssistant-Setup.exe payload verification failed." }

    $SetupHash = (Get-FileHash -LiteralPath $SetupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$SetupPath.sha256" -Value "$SetupHash *ResearchAssistant-Setup.exe" -Encoding ASCII
    Write-Host "Installer created: $SetupPath"
    Write-Host "SHA256: $SetupHash"
    Get-Item -LiteralPath $SetupPath | Select-Object FullName,Length,LastWriteTime
}
finally {
    Pop-Location
}
