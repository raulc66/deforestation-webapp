# Create a source zip without local secrets, venvs, or agent artifacts.
# Run from the package root (directory that contains backend/, frontend/, LICENSE).
#
#   powershell -File scripts/create_release.ps1
#   powershell -File scripts/create_release.ps1 -Version v1.0.0
#
# Does not use Git. The working tree is the source of the archive, so clean
# secrets out of the tree before running. Includes tests and Phase 0 goldens.
# Does not rewrite git history and does not create a git tag.

param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExclusionsFile = Join-Path $PSScriptRoot "release-exclusions.txt"
$Dist = Join-Path $Root "dist"
$StageName = "forestwatch-geospatial-intelligence"
$Stage = Join-Path $Dist $StageName

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-Date -Format "yyyyMMdd"
}
$ZipFileName = "forestwatch-source-$Version.zip"
$Zip = Join-Path $Dist $ZipFileName
$ChecksumPath = "$Zip.sha256"

$SkipCopyNames = @(
    "dist", ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".idea", ".vscode", "coverage", ".cache", ".cursor",
    ".emergent"
)

function Convert-Rel([string]$full, [string]$root) {
    return $full.Substring($root.Length).TrimStart("\", "/")
}

function Test-NameRule([string]$rel, [string]$name, [string]$rule) {
    $relWin = $rel.Replace("/", "\")
    $ruleWin = $rule.Replace("/", "\").Trim()
    if (-not $ruleWin) { return $false }

    if ($ruleWin.StartsWith("\")) {
        $rootPat = $ruleWin.TrimStart("\")
        return ($relWin -like $rootPat) -or ($relWin -like "$rootPat\*")
    }

    if ($ruleWin.StartsWith("*.")) {
        return $name -like $ruleWin
    }

    if ($name -eq $ruleWin) { return $true }
    if ($name -like $ruleWin) { return $true }
    if ($relWin -eq $ruleWin) { return $true }
    if ($relWin -like $ruleWin) { return $true }
    if ($relWin -like "*\$ruleWin") { return $true }
    return $false
}

$excludeRules = @()
$keepRules = @()
Get-Content $ExclusionsFile | ForEach-Object {
    $t = $_.Trim()
    if (-not $t -or $t.StartsWith("#")) { return }
    if ($t.StartsWith("!")) {
        $keepRules += $t.Substring(1).Trim()
        return
    }
    $excludeRules += $t
}

function Should-Exclude([string]$rel, [string]$name) {
    foreach ($rule in $keepRules) {
        if (Test-NameRule $rel $name $rule) { return $false }
    }
    foreach ($rule in $excludeRules) {
        if (Test-NameRule $rel $name $rule) { return $true }
    }
    return $false
}

function Copy-ReleaseTree([string]$src, [string]$dst) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Get-ChildItem -Path $src -Force | ForEach-Object {
        if ($_.Name -in $SkipCopyNames) { return }
        $rel = Convert-Rel $_.FullName $Root
        if (Should-Exclude $rel $_.Name) { return }
        $dest = Join-Path $dst $_.Name
        if ($_.PSIsContainer) {
            Copy-ReleaseTree $_.FullName $dest
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        }
    }
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-ReleaseTree $Root $Stage

# Second pass: remove anything the copy filter missed (nested names, globs).
Get-ChildItem -Path $Stage -Recurse -Force |
    Sort-Object { $_.FullName.Length } -Descending |
    ForEach-Object {
        if (-not (Test-Path -LiteralPath $_.FullName)) { return }
        $rel = Convert-Rel $_.FullName $Stage
        if (Should-Exclude $rel $_.Name) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

if (Test-Path $Zip) { Remove-Item -Force $Zip }
if (Test-Path $ChecksumPath) { Remove-Item -Force $ChecksumPath }
Compress-Archive -Path $Stage -DestinationPath $Zip -Force

$hash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $ChecksumPath -Value "$hash  $ZipFileName" -Encoding ascii

Write-Output "Wrote $Zip"
Write-Output "Checksum $ChecksumPath"
Write-Output "Staging directory: $Stage"
Write-Output "SHA256 $hash"
