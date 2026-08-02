param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [Parameter(Mandatory = $true)]
    [string]$ProjectTitle
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TemplateRoot = Join-Path $ProjectRoot "workspace-template"
$DestinationPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Destination))

if (-not (Test-Path -LiteralPath $TemplateRoot -PathType Container)) {
    throw "Workspace template is missing: $TemplateRoot"
}

if (Test-Path -LiteralPath $DestinationPath) {
    $Existing = @(Get-ChildItem -LiteralPath $DestinationPath -Force)
    if ($Existing.Count -gt 0) {
        throw "Destination already exists and is not empty: $DestinationPath"
    }
} else {
    New-Item -ItemType Directory -Path $DestinationPath | Out-Null
}

Get-ChildItem -LiteralPath $TemplateRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $DestinationPath -Recurse
}

$Tokens = @{
    "{{PROJECT_TITLE}}" = $ProjectTitle
    "{{CREATED_DATE}}" = (Get-Date -Format "yyyy-MM-dd")
}
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

Get-ChildItem -LiteralPath $DestinationPath -Recurse -File | Where-Object {
    $_.Extension -in ".md", ".yaml", ".yml", ".csv", ".sh", ".txt"
} | ForEach-Object {
    $Content = [System.IO.File]::ReadAllText($_.FullName)
    foreach ($Token in $Tokens.Keys) {
        $Content = $Content.Replace($Token, $Tokens[$Token])
    }
    [System.IO.File]::WriteAllText($_.FullName, $Content, $Utf8NoBom)
}

Write-Host "Research workspace created: $DestinationPath"
Write-Host "Next: complete project.yaml and governance/privacy-checklist.md"

