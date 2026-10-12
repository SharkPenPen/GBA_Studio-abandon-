#requires -Version 5.1
<#
  build.ps1 —— 一键编译 GBA 工程

  为什么需要这个脚本，而不是直接敲 make？
    因为 devkitARM 的 Makefile 依赖一整套 Unix 工具（make / rm / mkdir），
    在 Windows PowerShell 里直接跑 make 会找不到命令、或者因编码与路径问题失败。
    devkitPro 自带了一个 MSYS2 环境，这个脚本负责把环境变量和路径翻译好，
    再把 make 交给它执行。你只管 `.\scripts\build.ps1`。

  用法：
    .\scripts\build.ps1                 编译
    .\scripts\build.ps1 -Clean          清理后重新编译
    .\scripts\build.ps1 -Jobs 8         指定并行编译线程数
#>
[CmdletBinding()]
param(
    [string] $DevkitPro  = '',
    [string] $ProjectDir = '',
    [int]    $Jobs       = 4,
    [switch] $Clean
)

$ErrorActionPreference = 'Stop'

function Say([string] $Message) {
    Write-Host ('[build] {0}' -f $Message)
}

# ---------------------------------------------------------------- 定位工程
if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    # $PSScriptRoot 是 scripts\ 目录，上一级就是工程根目录
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

$makefile = Join-Path $ProjectDir 'Makefile'
if (-not (Test-Path -LiteralPath $makefile)) {
    throw ('在 {0} 里找不到 Makefile，请确认工程目录是否正确。' -f $ProjectDir)
}

# ---------------------------------------------------------------- 定位工具链
if ([string]::IsNullOrWhiteSpace($DevkitPro)) {
    if (-not [string]::IsNullOrWhiteSpace($env:DEVKITPRO) -and (Test-Path -LiteralPath $env:DEVKITPRO)) {
        $DevkitPro = $env:DEVKITPRO
    } else {
        $DevkitPro = 'C:\devkitPro'
    }
}

if (-not (Test-Path -LiteralPath $DevkitPro)) {
    throw ('找不到 devkitPro：{0}。请先运行 scripts\install-devkitpro.ps1。' -f $DevkitPro)
}

$bash = Join-Path $DevkitPro 'msys2\usr\bin\bash.exe'
if (-not (Test-Path -LiteralPath $bash)) {
    throw ('找不到 devkitPro 自带的 bash：{0}。工具链安装可能不完整。' -f $bash)
}

Say ('工具链: {0}' -f $DevkitPro)
Say ('工程  : {0}' -f $ProjectDir)

# ---------------------------------------------------------------- 路径翻译
# Windows 路径 D:\GitHud\GBA_AI 在 MSYS2 里要写成 /d/GitHud/GBA_AI
function ConvertTo-MsysPath([string] $WindowsPath) {
    $p = $WindowsPath -replace '\\', '/'
    if ($p -match '^([A-Za-z]):(.*)$') {
        return ('/{0}{1}' -f $Matches[1].ToLower(), $Matches[2])
    }
    return $p
}

$unixProject = ConvertTo-MsysPath $ProjectDir
Say ('MSYS 路径: {0}' -f $unixProject)

# ---------------------------------------------------------------- 组装命令
# 说明：
#   -l        以登录方式启动，让它读取 /etc/profile（devkitPro 的环境变量在里面）
#   如果登录后 DEVKITPRO 仍为空，就按常见的 /opt/devkitpro 兜底，再退到 /c/devkitPro
$makeTarget = if ($Clean) { 'clean all' } else { 'all' }

$script = @"
set -e
if [ -z "`$DEVKITPRO" ]; then
    if [ -d /opt/devkitpro ]; then export DEVKITPRO=/opt/devkitpro; else export DEVKITPRO=/c/devkitPro; fi
fi
export DEVKITARM="`$DEVKITPRO/devkitARM"
export PATH="`$DEVKITARM/bin:`$DEVKITPRO/tools/bin:`$PATH"
echo "[build] DEVKITPRO=`$DEVKITPRO"
echo "[build] DEVKITARM=`$DEVKITARM"
if ! command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    echo "[build] 错误：找不到 arm-none-eabi-gcc，工具链没装好" >&2
    exit 127
fi
cd "$unixProject"
make -j$Jobs $makeTarget
"@

Say ('执行 make（{0} 线程，目标：{1}）' -f $Jobs, $makeTarget)
Write-Host ''

# ---------------------------------------------------------------- 执行
& $bash -lc $script
$exitCode = $LASTEXITCODE

Write-Host ''
if ($exitCode -ne 0) {
    Say ('编译失败，退出码 {0}。上面带 error: 的行就是原因，把它发给我即可。' -f $exitCode)
    exit $exitCode
}

# ---------------------------------------------------------------- 报告产物
$rom = Get-ChildItem -LiteralPath $ProjectDir -Filter '*.gba' -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($rom) {
    Say ('编译成功：{0}' -f $rom.FullName)
    Say ('ROM 大小：{0} 字节 ({1:N1} KB)' -f $rom.Length, ($rom.Length / 1KB))

    # 顺手校验 ROM 头，很多"模拟器打不开"其实是头不合法
    $checker = Join-Path $PSScriptRoot 'check-rom.ps1'
    if (Test-Path -LiteralPath $checker) {
        & $checker -RomPath $rom.FullName
    }
} else {
    Say '编译返回成功，但没有找到 .gba 文件，这不正常，请把上面的输出发我。'
    exit 1
}

exit 0
