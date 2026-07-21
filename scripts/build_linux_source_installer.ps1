$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Bash = "C:\Program Files\Git\usr\bin\bash.exe"

if (-not (Test-Path -LiteralPath $Bash)) {
    throw "Git for Windows is required. Install it from https://git-scm.com/download/win"
}

Push-Location $ProjectRoot
try {
    & $Bash -c 'export PATH=/usr/bin:/mingw64/bin:$PATH; ./scripts/build_linux_source_installer.sh && ./scripts/verify_linux_source_installer.sh'
    if ($LASTEXITCODE -ne 0) {
        throw "Linux source installer build failed."
    }
}
finally {
    Pop-Location
}
