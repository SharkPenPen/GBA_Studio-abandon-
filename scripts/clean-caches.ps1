#requires -Version 5.1
<#
  clean-caches.ps1 —— 精简工程占用（只删"可以重新得到"的东西）

  这个工程里有两类文件：必须留的（工具链本体、源码、文档）和可再生的（下载缓存、
  编译中间产物）。脚本只碰第二类，删之前会逐项列出大小。

  ┌──────────────────────────────────────────┬─────────┬──────────────────────────────┐
  │ 内容                                     │ 约占用  │ 删掉之后                     │
  ├──────────────────────────────────────────┼─────────┼──────────────────────────────┤
  │ .tools\ 里的 *.zip / *.7z（下载缓存）     │ 350 MB  │ 重装工具链时重新下载         │
  │ .tmp\ 里的临时文件                       │ 很小    │ 自动重建                     │
  │ build\ 与 .toolchain\build\（中间产物）   │ 几 MB   │ 下次编译重建（首次稍慢）     │
  │ .toolchain\emulator\、.toolchain\skyemu\  │ 61 MB   │ 本机加载 ROM 会崩的两个模拟器│
  └──────────────────────────────────────────┴─────────┴──────────────────────────────┘

  不删的东西（这些删了就要重新下载 1.4 GB，而且它们是能用的）：
      .toolchain\arm-none-eabi-gcc\   编译器本体
      .toolchain\libtonc\ + lib\      库源码与编译好的 libtonc.a
      .toolchain\gba-bootstrap\       启动代码与链接脚本
      .toolchain\mgba\                能正常运行的 mGBA
      .tools\7zr.exe                  解压 mGBA 用的官方工具（600 KB，留着省事）

  用法：
    .\scripts\clean-caches.ps1                          # 删缓存 + 临时文件 + 编译中间产物
    .\scripts\clean-caches.ps1 -KeepBuild               # 保留编译中间产物（下次编译更快）
    .\scripts\clean-caches.ps1 -IncludeUnusedEmulators  # 连两个用不了的模拟器一起删
    .\scripts\clean-caches.ps1 -Preview                 # 只预览，不真删
#>
[CmdletBinding()]
param(
    [string] $ProjectDir = '',

    # 保留 build\ 与 .toolchain\build\（编译中间产物），下次编译更快
    [switch] $KeepBuild,

    # 一并删除本机用不了的两个模拟器（NanoBoyAdvance / SkyEmu）
    [switch] $IncludeUnusedEmulators,

    # 只显示会删什么，不实际删除
    [switch] $Preview
)

$ErrorActionPreference = 'Stop'

function Say([string] $m) { Write-Host ('[clean] {0}' -f $m) }

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

# ------------------------------------------------------------------ 组装目标清单
$targets = @()   # 每项: @{ Path; Label; Kind }  Kind = File | Tree

# 1) 下载缓存：.tools 下的压缩包
#    例外：7zr.exe 是个 600KB 的小工具（用来解 mGBA 的 7z），留着省得再下，不删。
$toolsDir = Join-Path $ProjectDir '.tools'
if (Test-Path -LiteralPath $toolsDir) {
    foreach ($f in Get-ChildItem -LiteralPath $toolsDir -File -Force -ErrorAction SilentlyContinue) {
        if ($f.Name -eq '7zr.exe') { continue }
        if ($f.Extension -in @('.zip', '.7z', '.exe')) {
            $targets += [pscustomobject]@{ Path = $f.FullName; Label = ('.tools\' + $f.Name); Kind = 'File' }
        }
    }
}

# 2) 编译临时文件（目录保留，编译器的 TMP/TEMP 指向它）
$tmpDir = Join-Path $ProjectDir '.tmp'
if (Test-Path -LiteralPath $tmpDir) {
    foreach ($f in Get-ChildItem -LiteralPath $tmpDir -File -Force -ErrorAction SilentlyContinue) {
        $targets += [pscustomobject]@{ Path = $f.FullName; Label = ('.tmp\' + $f.Name); Kind = 'File' }
    }
}

# 3) 编译中间产物
if (-not $KeepBuild) {
    foreach ($d in @('build', '.toolchain\build')) {
        $p = Join-Path $ProjectDir $d
        if (Test-Path -LiteralPath $p) {
            $targets += [pscustomobject]@{ Path = $p; Label = ($d + '\'); Kind = 'Tree' }
        }
    }
}

# 4) 可选：本机跑不了的两个模拟器
if ($IncludeUnusedEmulators) {
    foreach ($d in @('.toolchain\emulator', '.toolchain\skyemu')) {
        $p = Join-Path $ProjectDir $d
        if (Test-Path -LiteralPath $p) {
            $targets += [pscustomobject]@{ Path = $p; Label = ($d + '\'); Kind = 'Tree' }
        }
    }
}

if ($targets.Count -eq 0) {
    Say '没有需要清理的东西。'
    exit 0
}

# ------------------------------------------------------------------ 预览/统计
function Get-Size([string] $p) {
    $item = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
    if (-not $item) { return 0 }
    if ($item.PSIsContainer) {
        return [double]((Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue |
                         Measure-Object Length -Sum).Sum)
    }
    return [double]$item.Length
}

Say ('工程目录：{0}' -f $ProjectDir)
Say ''
$total = 0.0
foreach ($t in $targets) {
    $size = Get-Size $t.Path
    $total += $size
    Say ('  {0,-52} {1,9:N1} MB' -f $t.Label, ($size / 1MB))
}
Say ''
Say ('合计可释放：{0:N1} MB' -f ($total / 1MB))

if ($Preview) {
    Say '（-Preview 模式，没有删除任何东西）'
    exit 0
}

# ------------------------------------------------------------------ 删除
Say ''
$removed = 0.0
$failed  = @()
foreach ($t in $targets) {
    # 安全检查：只删工程目录内的东西
    if (-not $t.Path.StartsWith($ProjectDir + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Say ('  跳过（不在工程目录内）：{0}' -f $t.Path)
        continue
    }
    $size = Get-Size $t.Path
    try {
        Remove-Item -LiteralPath $t.Path -Recurse -Force -ErrorAction Stop
        $removed += $size
    } catch {
        $failed += $t.Label
    }
}
Say ('已释放 {0:N1} MB' -f ($removed / 1MB))
if ($failed.Count -gt 0) {
    Say ('以下项目删除失败（通常是权限条目挡住，见 README 常见问题）：{0}' -f ($failed -join ', '))
}

# 重新创建 .tmp（编译器要用）
if (-not (Test-Path -LiteralPath $tmpDir)) { New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null }

$left = Get-ChildItem -LiteralPath $ProjectDir -Recurse -File -Force -ErrorAction SilentlyContinue |
        Measure-Object Length -Sum
Say ('工程当前占用：{0:N0} MB' -f ($left.Sum / 1MB))
exit 0
