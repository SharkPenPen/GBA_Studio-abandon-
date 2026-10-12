#requires -Version 5.1
<#
  install-devkitpro.ps1

  兼容 Windows PowerShell 5.1（本机默认 shell）与 PowerShell 7+。
  在 Windows 上以尽量无人值守的方式安装 devkitPro 工具链，并安装 GBA 开发包 (gba-dev)。

  为什么需要"放宽权限"运行：
    - 安装目标 C:\devkitPro 在工作区之外，沙箱默认只允许写工作区；
    - 安装过程需要访问网络下载官方安装器与软件包。

  这个脚本只做三件事（外加一次自检输出）：
    1. 从 devkitPro 官方 GitHub release 下载安装器；
    2. 以静默方式安装到 -InstallDir；
    3. 在 devkitPro 自带的 pacman 环境里安装 gba-dev（含 devkitARM / libtonc / grit / gbafix）。

  不在任何地方修改系统 PATH 之外的东西；所有下载都放在 -DownloadDir 里，可随时删除。
#>
[CmdletBinding()]
param(
    [string] $InstallDir    = 'C:\devkitPro',
    [string] $DownloadDir   = (Join-Path $PSScriptRoot '..\.tools'),
    [int]    $InstallTimeoutMinutes = 20,
    [switch] $SkipPackages
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# Windows PowerShell 5.1 默认可能仍协商 TLS 1.0，GitHub 会直接拒绝连接。
# devkitPro 与 pacman 都要求 TLS 1.2。
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
    Write-Warning ('无法显式启用 TLS 1.2：{0}' -f $_.Exception.Message)
}

function Say([string] $Message) {
    Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Section([string] $Title) {
    Write-Host ''
    Write-Host ('=== {0} ===' -f $Title)
}

# ---------------------------------------------------------------- 0. 环境自检
Section '环境自检'

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin   = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Say ('当前用户        : {0}' -f $identity.Name)
Say ('已提升为管理员  : {0}' -f $isAdmin)
Say ('目标安装目录    : {0}' -f $InstallDir)
Say ('下载缓存目录    : {0}' -f $DownloadDir)
Say ('PowerShell 版本 : {0}' -f $PSVersionTable.PSVersion)

if (Test-Path -LiteralPath $InstallDir) {
    Say ('注意：{0} 已存在，本次将执行"更新/补齐"而非全新安装。' -f $InstallDir)
}

# 目录可写性预检：宁可在下载前失败，也不要装到一半失败
$downloadFull = [System.IO.Path]::GetFullPath($DownloadDir)
if (-not (Test-Path -LiteralPath $downloadFull)) {
    New-Item -ItemType Directory -Force -Path $downloadFull | Out-Null
}
$probe = Join-Path $downloadFull '.write-probe'
Set-Content -LiteralPath $probe -Value 'ok' -Encoding utf8
Remove-Item -LiteralPath $probe -Force
Say ('下载目录可写    : 是')

# ---------------------------------------------------------------- 1. 下载安装器
Section '下载 devkitPro 安装器'

$installerUrl = 'https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe'
$installer    = Join-Path $downloadFull 'devkitProUpdater-3.0.3.exe'

if ((Test-Path -LiteralPath $installer) -and (Get-Item -LiteralPath $installer).Length -gt 100000) {
    Say ('已存在，跳过下载：{0} ({1} 字节)' -f $installer, (Get-Item -LiteralPath $installer).Length)
} else {
    Say ('下载 {0}' -f $installerUrl)
    Invoke-WebRequest -Uri $installerUrl -OutFile $installer -UseBasicParsing -TimeoutSec 600
    Say ('下载完成：{0} 字节' -f (Get-Item -LiteralPath $installer).Length)
}

# ---------------------------------------------------------------- 2. 静默安装
Section '静默安装 devkitPro 基础环境'

# NSIS 约定：/S 静默，/D= 指定目录，且 /D 必须是最后一个参数、不能加引号（路径不能含空格）。
$nsisArgs = @('/S', "/D=$InstallDir")
Say ('执行："{0}" {1}' -f $installer, ($nsisArgs -join ' '))

$proc = Start-Process -FilePath $installer -ArgumentList $nsisArgs -PassThru
$exited = $proc.WaitForExit($InstallTimeoutMinutes * 60 * 1000)

if (-not $exited) {
    Say ('安装器在 {0} 分钟内没有退出，可能有窗口在等待点击（例如 UAC 提权或图形界面）。' -f $InstallTimeoutMinutes)
    Say ('进程仍在运行，PID={0}。稍后可用 Stop-Process -Id {0} 结束它。' -f $proc.Id)
} else {
    Say ('安装器退出码 = {0}' -f $proc.ExitCode)
}

Section '安装目录现状'
if (Test-Path -LiteralPath $InstallDir) {
    Get-ChildItem -LiteralPath $InstallDir -Force |
        Select-Object Mode, Name |
        Format-Table -AutoSize | Out-String | Write-Host
} else {
    Say ('{0} 不存在 —— 安装没有成功。' -f $InstallDir)
}

# ---------------------------------------------------------------- 3. 安装 gba-dev
Section '安装 gba-dev（devkitARM + libtonc + grit + gbafix）'

$bashCandidates = @(
    (Join-Path $InstallDir 'msys2\usr\bin\bash.exe'),
    (Join-Path $InstallDir 'msys2\bash.exe')
)
$bash = $bashCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if ($SkipPackages) {
    Say '已指定 -SkipPackages，跳过软件包安装。'
} elseif (-not $bash) {
    Say '找不到 devkitPro 自带的 bash，无法自动安装软件包。'
    Say ('候选路径：{0}' -f ($bashCandidates -join '; '))
} else {
    Say ('使用 bash：{0}' -f $bash)
    $pacmanCmd = 'pacman --noconfirm --needed -Sy gba-dev'
    Say ('执行：{0} -lc "{1}"' -f $bash, $pacmanCmd)

    & $bash -lc $pacmanCmd 2>&1 | ForEach-Object { Write-Host ('  | ' + $_) }
    Say ('pacman 退出码 = {0}' -f $LASTEXITCODE)
}

# ---------------------------------------------------------------- 4. 结果核对
Section '结果核对'

$expect = @(
    @{ Name = 'devkitARM 的 gcc'; Path = (Join-Path $InstallDir 'devkitARM\bin\arm-none-eabi-gcc.exe') },
    @{ Name = 'libtonc 头文件';   Path = (Join-Path $InstallDir 'libtonc\include\tonc.h') },
    @{ Name = 'libtonc 库文件';   Path = (Join-Path $InstallDir 'libtonc\lib\libtonc.a') },
    @{ Name = 'grit (图形转换)';  Path = (Join-Path $InstallDir 'tools\bin\grit.exe') },
    @{ Name = 'gbafix (ROM 头)';  Path = (Join-Path $InstallDir 'tools\bin\gbafix.exe') },
    @{ Name = 'msys2 bash';       Path = (Join-Path $InstallDir 'msys2\usr\bin\bash.exe') }
)

$missing = 0
foreach ($item in $expect) {
    $ok = Test-Path -LiteralPath $item.Path
    if (-not $ok) { $missing++ }
    Say ('{0,-22} {1}  {2}' -f $item.Name, $(if ($ok) { 'OK  ' } else { '缺失' }), $item.Path)
}

Section '总结'
if ($missing -eq 0) {
    Say 'devkitPro 工具链看起来已就绪。下一步：编译示例工程生成 .gba ROM。'
} else {
    Say ('有 {0} 项缺失。请把上面的核对结果发回给助手判断下一步。' -f $missing)
}

exit 0
