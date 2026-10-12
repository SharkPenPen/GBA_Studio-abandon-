#requires -Version 5.1
<#
  build-libtonc.ps1 —— 用我们自己的 arm-none-eabi-gcc 编译 libtonc，产出 libtonc.a

  为什么要自己编：
    官方 libtonc 的 Makefile 依赖 devkitARM（含 gba_rules、make、Unix 工具），
    而 devkitARM 的官方源在国内不可达。libtonc 本质上就是一个普通静态库，
    用标准 arm-none-eabi-gcc 编译 src/ 与 asm/ 下的源文件、再用 ar 打包即可。

  编译参数出处：libtonc 官方 Makefile
    CBASE   = -Wall -fno-strict-aliasing -O2
    RCFLAGS = CBASE + (-mthumb-interwork -mthumb)
    ASFLAGS = -Wa,--warn + (-mthumb -mthumb-interwork)
  这里额外显式加了 -mcpu=arm7tdmi -mtune=arm7tdmi（GBA 的 CPU 型号），
  避免不同 GCC 版本的默认目标架构不一致。

  用法：
    .\scripts\build-libtonc.ps1
    .\scripts\build-libtonc.ps1 -Force      # 忽略缓存，全部重编
#>
[CmdletBinding()]
param(
    [string] $ProjectDir = '',
    [string] $ToolchainDir = '',
    [switch] $Force,
    [switch] $Quiet
)

$ErrorActionPreference = 'Stop'

function Say([string] $m) { if (-not $Quiet) { Write-Host ('[libtonc] {0}' -f $m) } }

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
if ([string]::IsNullOrWhiteSpace($ToolchainDir)) { $ToolchainDir = Join-Path $ProjectDir '.toolchain' }

$gccDir  = Join-Path $ToolchainDir 'arm-none-eabi-gcc\bin'
$gcc     = Join-Path $gccDir 'arm-none-eabi-gcc.exe'
$ar      = Join-Path $gccDir 'arm-none-eabi-ar.exe'
$nm      = Join-Path $gccDir 'arm-none-eabi-nm.exe'
$srcDir  = Join-Path $ToolchainDir 'libtonc'
$incDir  = Join-Path $srcDir 'include'
$objDir  = Join-Path $ToolchainDir 'build\libtonc'
$libDir  = Join-Path $ToolchainDir 'lib'
$libFile = Join-Path $libDir 'libtonc.a'

foreach ($p in @($gcc, $ar)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('找不到 {0}。请先运行 scripts\setup-toolchain-china.ps1 安装工具链。' -f $p)
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $srcDir 'include\tonc.h'))) {
    throw ('找不到 libtonc 源码：{0}。请先运行 scripts\setup-toolchain-china.ps1。' -f $srcDir)
}

foreach ($d in @($objDir, $libDir)) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

# 编译器的临时目录指向工程内部：受限环境下系统 TEMP 常常不可写，
# 会导致链接/汇编以 "Cannot create temporary file" 失败（见 build.ps1 里的同样处理）。
# 放在 .tmp 而不是 build\tmp，避免被 -Clean 一起删掉。
$tmpDir = Join-Path $ProjectDir '.tmp'
if (-not (Test-Path -LiteralPath $tmpDir)) { New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null }
$env:TMP  = $tmpDir
$env:TEMP = $tmpDir

# ------------------------------------------------------------------ 原始命令封装
function Invoke-Tool {
    param([string] $Exe, [string[]] $Arguments)

    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    return [pscustomobject]@{
        ExitCode = $code
        Output   = ($output | ForEach-Object { $_.ToString() })
    }
}

# ------------------------------------------------------------------ 收集源文件
# 与官方 Makefile 的 SRCDIRS 一致：asm src src/font src/tte src/pre1.3
#
# 排除项：src/tte/tte_iohook.c
#   它 #include <sys/iosupport.h> 并操作 devoptab —— 那是 devkitPro 定制版 newlib
#   专有的 stdio 重定向机制（让 printf 直接输出到 GBA 屏幕）。标准 Arm GNU 工具链的
#   newlib 没有这个头文件。它只提供 tte_init_con()/tte_cmd_vt100() 两个入口，
#   库内没有任何其它文件引用它们，因此排除后不影响 TTE 的其它功能。
#   影响：不能用 tte_init_con() 自动接管 printf；要用屏幕文字请直接调用 tte_write()，
#   或自己在 source\sys\syscalls.c 里实现 _write() 把输出接到 tte_write()。
$excludeFiles = @('src\tte\tte_iohook.c')

$cSources   = @()
$asmSources = @()
foreach ($dir in @('src', 'src\tte', 'src\pre1.3')) {
    $full = Join-Path $srcDir $dir
    if (Test-Path -LiteralPath $full) {
        $cSources += @(Get-ChildItem -LiteralPath $full -Filter '*.c' -File)
    }
}
foreach ($dir in @('asm', 'src\font', 'src\tte')) {
    $full = Join-Path $srcDir $dir
    if (Test-Path -LiteralPath $full) {
        $asmSources += @(Get-ChildItem -LiteralPath $full -Filter '*.s' -File)
    }
}

$before = $cSources.Count
$cSources = @($cSources | Where-Object {
    $rel = $_.FullName.Substring($srcDir.Length).TrimStart('\')
    -not ($excludeFiles -contains $rel)
})
if ($before -ne $cSources.Count) {
    Say ('已排除 {0} 个依赖 devkitPro 专有头文件的源文件：{1}' -f ($before - $cSources.Count), ($excludeFiles -join ', '))
}

Say ('源文件：{0} 个 C，{1} 个汇编' -f $cSources.Count, $asmSources.Count)
if (($cSources.Count + $asmSources.Count) -eq 0) { throw '没有找到任何 libtonc 源文件。' }

# ------------------------------------------------------------------ 编译
$cflags = @(
    '-I', $incDir,
    '-Wall', '-fno-strict-aliasing', '-O2',
    '-mthumb', '-mthumb-interwork',
    '-mcpu=arm7tdmi', '-mtune=arm7tdmi'
)
$sflags = @(
    '-I', $incDir,
    '-Wa,--warn',
    '-mthumb', '-mthumb-interwork',
    '-mcpu=arm7tdmi', '-mtune=arm7tdmi',
    '-x', 'assembler-with-cpp'
)

$objects  = @()
$compiled = 0
$skipped  = 0
$failures = @()

function Get-ObjectPath {
    param([System.IO.FileInfo] $File)
    $rel = $File.FullName.Substring($srcDir.Length).TrimStart('\')
    return (Join-Path $objDir ($rel + '.o'))
}

$all = @()
foreach ($f in $cSources)   { $all += [pscustomobject]@{ File = $f; Flags = $cflags } }
foreach ($f in $asmSources) { $all += [pscustomobject]@{ File = $f; Flags = $sflags } }

$index = 0
foreach ($item in $all) {
    $index++
    $obj = Get-ObjectPath -File $item.File
    $objParent = Split-Path -Parent $obj
    if (-not (Test-Path -LiteralPath $objParent)) { New-Item -ItemType Directory -Force -Path $objParent | Out-Null }

    if (-not $Force -and (Test-Path -LiteralPath $obj)) {
        if ((Get-Item -LiteralPath $obj).LastWriteTime -gt $item.File.LastWriteTime) {
            $objects += $obj
            $skipped++
            continue
        }
    }

    # 变量名不能叫 $args（PowerShell 自动变量）
    $compileArgs = @() + $item.Flags + @('-c', $item.File.FullName, '-o', $obj)
    $r = Invoke-Tool -Exe $gcc -Arguments $compileArgs

    if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $obj)) {
        $failures += $item.File.FullName
        Write-Host ('[libtonc] 编译失败：{0}' -f $item.File.FullName)
        foreach ($line in $r.Output) { Write-Host ('    ' + $line) }
        continue
    }
    # libtonc 自带大量警告，这里只在 -Quiet 之外汇总显示数量，不刷屏
    $objects += $obj
    $compiled++
    if ($index % 20 -eq 0) { Say ('  进度 {0}/{1}' -f $index, $all.Count) }
}

Say ('编译完成：新编 {0}，缓存命中 {1}，失败 {2}' -f $compiled, $skipped, $failures.Count)
if ($failures.Count -gt 0) {
    throw ('有 {0} 个文件编译失败，请把上面的错误发回给助手。' -f $failures.Count)
}

# ------------------------------------------------------------------ 打包
Say ('打包 {0}' -f $libFile)
if (Test-Path -LiteralPath $libFile) { Remove-Item -LiteralPath $libFile -Force }

$r = Invoke-Tool -Exe $ar -Arguments (@('-crs', $libFile) + $objects)
if ($r.ExitCode -ne 0) {
    foreach ($line in $r.Output) { Write-Host ('    ' + $line) }
    throw 'ar 打包失败。'
}

$size = (Get-Item -LiteralPath $libFile).Length
Say ('libtonc.a 大小：{0:N0} 字节' -f $size)

# ------------------------------------------------------------------ 校验
# 确认几个我们一定会用到的符号确实在库里
$symbolCheck = @('vid_vsync', 'key_poll', 'key_hit', 'irq_init')
$nmResult = Invoke-Tool -Exe $nm -Arguments @('--defined-only', $libFile)
$nmText = $nmResult.Output -join "`n"
$missingSymbols = @()
foreach ($sym in $symbolCheck) {
    if ($nmText -notmatch ('\b' + [regex]::Escape($sym) + '\b')) { $missingSymbols += $sym }
}

if ($missingSymbols.Count -gt 0) {
    Say ('警告：库里没找到这些符号：{0}（可能名字不同，也可能编译有问题）' -f ($missingSymbols -join ', '))
} else {
    Say ('符号校验通过：{0}' -f ($symbolCheck -join ', '))
}

Say 'libtonc 编译完成。'
exit 0
