param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace
)

$ErrorActionPreference = "Stop"
$WorkspacePath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Workspace))
if (-not (Test-Path -LiteralPath $WorkspacePath -PathType Container)) {
    throw "Workspace does not exist: $WorkspacePath"
}

$RequiredPaths = @(
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX_REVIEWER.md",
    "project.yaml",
    "TASK_BOARD.md",
    "CHANGELOG.md",
    "governance/privacy-checklist.md",
    "tasks/TASK-TEMPLATE.yaml",
    "provenance/RUN-TEMPLATE.yaml",
    "inventory/assets.csv",
    "mechanism/elements.csv",
    "mechanism/relations.csv",
    "mechanism/evidence-check.csv",
    "presentations/storyboard.csv",
    "server/slurm-job.sh",
    "data/raw",
    "data/metadata",
    "data/interim",
    "data/processed",
    "literature",
    "scripts",
    "results",
    "figures",
    "review",
    "final-package"
)

$ExpectedHeaders = @{
    "inventory/assets.csv" = "asset_id,type,path_or_identifier,source,owner,version,sha256,sensitivity,license,status,related_task,notes"
    "mechanism/elements.csv" = "element_id,label,element_type,context,canonical_identifier,evidence_source,notes"
    "mechanism/relations.csv" = "relation_id,source_element,target_element,relation_type,direction,context,evidence_id,evidence_level,visual_style,status"
    "mechanism/evidence-check.csv" = "evidence_id,relation_id,citation_id,source_location,quoted_evidence,evidence_type,direct_support,reviewer,decision,notes"
    "presentations/storyboard.csv" = "slide_number,section,slide_title,single_message,evidence_artifacts,visual_type,speaker_notes,claim_status,review_status"
}

$Errors = [System.Collections.Generic.List[string]]::new()
$Warnings = [System.Collections.Generic.List[string]]::new()

foreach ($RelativePath in $RequiredPaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $WorkspacePath $RelativePath))) {
        $Errors.Add("Missing required path: $RelativePath")
    }
}

foreach ($RelativePath in $ExpectedHeaders.Keys) {
    $Path = Join-Path $WorkspacePath $RelativePath
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $Header = Get-Content -LiteralPath $Path -TotalCount 1
        if ($Header -ne $ExpectedHeaders[$RelativePath]) {
            $Errors.Add("Unexpected CSV header: $RelativePath")
        }
    }
}

$ProjectFile = Join-Path $WorkspacePath "project.yaml"
if (Test-Path -LiteralPath $ProjectFile -PathType Leaf) {
    $ProjectContent = Get-Content -Raw -LiteralPath $ProjectFile
    if ($ProjectContent.Contains("{{PROJECT_TITLE}}") -or $ProjectContent.Contains("{{CREATED_DATE}}")) {
        $Errors.Add("Unresolved template token in project.yaml")
    }
    if ($ProjectContent -match 'sensitivity:\s*"unknown"') {
        $Warnings.Add("Data sensitivity is still unknown")
    }
    if ($ProjectContent -match 'owner:\s*"TBD"') {
        $Warnings.Add("Project owner is still TBD")
    }
}

$PrivacyFile = Join-Path $WorkspacePath "governance/privacy-checklist.md"
if (Test-Path -LiteralPath $PrivacyFile -PathType Leaf) {
    $PrivacyContent = Get-Content -Raw -LiteralPath $PrivacyFile
    if ($PrivacyContent -match 'Decision:\s*`BLOCKED`') {
        $Warnings.Add("External data transfer remains blocked until privacy review is approved")
    }
}

foreach ($Warning in $Warnings) {
    Write-Warning $Warning
}

if ($Errors.Count -gt 0) {
    foreach ($Item in $Errors) {
        Write-Error $Item -ErrorAction Continue
    }
    exit 1
}

Write-Host "Workspace structure is valid: $WorkspacePath"
Write-Host "Warnings: $($Warnings.Count)"

