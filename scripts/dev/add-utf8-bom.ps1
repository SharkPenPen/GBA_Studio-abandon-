#requires -Version 5.1
<#
  add-utf8-bom.ps1  (ASCII-only on purpose: safe to run before it has a BOM itself)

  WHY THIS EXISTS
    Windows PowerShell 5.1 (the default shell on this machine) reads a .ps1 file
    as ANSI/GBK unless the file starts with a UTF-8 BOM. For a script containing
    Chinese comments that means mojibake, and worse: a mis-decoded multi-byte
    character can swallow the following newline, so the comment "eats" the next
    line and the parser reports bogus syntax errors.

    The reliable test is the raw byte order mark, not a decoded string:
    File.ReadAllText() strips the BOM, so checking the decoded text cannot tell
    you whether the file has one.

  USAGE
    .\scripts\dev\add-utf8-bom.ps1 -Path 'D:\GitHud\GBA_AI\scripts'
    .\scripts\dev\add-utf8-bom.ps1 -Path .\scripts -Recurse -CheckSyntax
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]] $Path,

    [switch] $Recurse,

    # Also run the PowerShell parser over each file and report syntax errors.
    [switch] $CheckSyntax
)

$ErrorActionPreference = 'Stop'

$utf8Bom = New-Object System.Text.UTF8Encoding($true)
$utf8Raw = New-Object System.Text.UTF8Encoding($false)

function Test-HasBom([string] $File) {
    $b = [System.IO.File]::ReadAllBytes($File)
    return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
}

$files = @()
foreach ($one in $Path) {
    if (-not (Test-Path -LiteralPath $one)) {
        Write-Host ('[bom] path not found, skipped: {0}' -f $one)
        continue
    }
    $item = Get-Item -LiteralPath $one
    if ($item.PSIsContainer) {
        $files += @(Get-ChildItem -LiteralPath $item.FullName -Filter '*.ps1' -File -Recurse:$Recurse)
    } else {
        $files += @($item)
    }
}

if (-not $files -or $files.Count -eq 0) {
    Write-Host ('[bom] no .ps1 file found under: {0}' -f ($Path -join ', '))
    exit 0
}

$added = 0
$already = 0
$syntaxBad = 0

foreach ($f in $files) {
    if (Test-HasBom $f.FullName) {
        Write-Host ('[bom] has BOM : {0}' -f $f.Name)
        $already++
    } else {
        # Decode as UTF-8 (no BOM present), then rewrite WITH a BOM.
        $text = [System.IO.File]::ReadAllText($f.FullName, $utf8Raw)
        [System.IO.File]::WriteAllText($f.FullName, $text, $utf8Bom)
        Write-Host ('[bom] BOM added: {0}' -f $f.Name)
        $added++
    }

    if ($CheckSyntax) {
        $errors = $null
        $tokens = $null
        [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errors) | Out-Null
        if ($errors -and $errors.Count -gt 0) {
            $syntaxBad++
            foreach ($e in $errors) {
                Write-Host ('[bom]   SYNTAX ERROR line {0}: {1}' -f $e.Extent.StartLineNumber, $e.Message)
            }
        } else {
            Write-Host ('[bom]   syntax OK')
        }
    }
}

Write-Host ('[bom] done: {0} added, {1} already had BOM, {2} file(s) with syntax errors' -f $added, $already, $syntaxBad)
if ($syntaxBad -gt 0) { exit 1 }
exit 0
