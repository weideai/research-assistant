param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = (Resolve-Path (Join-Path $ProjectRoot $Python)).Path
$BuildRoot = Join-Path $ProjectRoot "build\windows"
$DistRoot = Join-Path $ProjectRoot "dist\windows"
$AppDist = Join-Path $DistRoot "app"
$AppBundle = Join-Path $AppDist "ResearchAssistant"
$Templates = Join-Path $ProjectRoot "app\templates"
$StaticFiles = Join-Path $ProjectRoot "app\static"
$Migrations = Join-Path $ProjectRoot "migrations"
$PresentationScript = Join-Path $ProjectRoot "scripts\build_weekly_presentation.mjs"
$DesktopLauncher = Join-Path $ProjectRoot "desktop_launcher.py"
$InstallerSource = Join-Path $ProjectRoot "packaging\windows\installer.py"

Push-Location $ProjectRoot
try {
    & $PythonPath -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is missing. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
    }

    Remove-Item -LiteralPath $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $DistRoot -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $BuildRoot,$AppDist -Force | Out-Null

    $appArgs = @(
        "--noconfirm", "--clean", "--windowed",
        "--name", "ResearchAssistant",
        "--distpath", $AppDist,
        "--workpath", (Join-Path $BuildRoot "app"),
        "--specpath", (Join-Path $BuildRoot "spec"),
        "--add-data", "$Templates;app\templates",
        "--add-data", "$StaticFiles;app\static",
        "--add-data", "$Migrations;migrations",
        "--add-data", "$PresentationScript;scripts",
        "--hidden-import", "app.admin",
        "--hidden-import", "app.auth",
        "--hidden-import", "app.commands",
        "--hidden-import", "app.main",
        "--hidden-import", "app.models",
        "--hidden-import", "app.presentation_service",
        "--hidden-import", "logging.config",
        $DesktopLauncher
    )
    & $PythonPath -m PyInstaller @appArgs
    if ($LASTEXITCODE -ne 0) { throw "ResearchAssistant.exe build failed." }

    $installerArgs = @(
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "ResearchAssistant-Setup",
        "--distpath", $DistRoot,
        "--workpath", (Join-Path $BuildRoot "installer"),
        "--specpath", (Join-Path $BuildRoot "spec"),
        "--add-data", "$AppBundle;payload\ResearchAssistant",
        $InstallerSource
    )
    & $PythonPath -m PyInstaller @installerArgs
    if ($LASTEXITCODE -ne 0) { throw "ResearchAssistant-Setup.exe build failed." }

    $SetupPath = Join-Path $DistRoot "ResearchAssistant-Setup.exe"
    Write-Host "Installer created: $SetupPath"
    Get-Item -LiteralPath $SetupPath | Select-Object FullName,Length,LastWriteTime
}
finally {
    Pop-Location
}
