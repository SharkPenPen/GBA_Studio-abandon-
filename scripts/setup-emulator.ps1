#requires -Version 5.1
<#
  setup-emulator.ps1 —— 安装 GBA 模拟器（免安装、免管理员权限）

  实测结论（本机，2026-10）：
    ✅ mGBA 0.10.5        —— 正常运行，标题栏显示 "GBA AI DEMO (60.3 fps)"，
                             截图确认画面正确。这是本脚本默认安装的模拟器。
    ❌ NanoBoyAdvance 1.8.3 —— 加载 ROM 时崩溃（0xc000041d / 0xc0000005）
    ❌ SkyEmu v5           —— 启动即崩溃（0xc0000005）
    后两个已排除 ROM、运行库、杀软、显卡因素（本机为 RTX 4070 Ti SUPER），
    疑似与本机系统环境有关，故不作为默认。

  为什么解压 mGBA 需要额外一步：
    mGBA 的 Windows 版只有 .7z 便携包和需要提权的安装器，没有 .zip。
    * Windows 自带的 tar.exe（libarchive）不支持 7z 的 LZMA 编码；
    * Python 的 py7zr 不支持该包使用的 BCJ2 滤波器；
    * 所以这里下载 7-Zip 官方的独立解压器 7zr.exe（约 600KB，7-zip.org 可直连）
      来完成解压。它只解压，不改系统。

  关于完整性校验的说明（如实告知）：
    * 7zr.exe：7-zip.org 官方直连 HTTPS 下载，但官方未提供 SHA256，且文件未数字签名。
    * mGBA 7z：GitHub API 对该 release 未提供摘要字段（digest 为 null），
      因此只能校验字节数（14,156,919）与解压是否成功。
      解压后可通过 mGBA 自带菜单「帮助 → 关于」核对版本号。

  产物位置：.toolchain\mgba\mGBA-0.10.5-win64\
            其中 mGBA.exe 是 Qt 界面版，mgba-sdl.exe 是 SDL 版（界面版出问题时的备用）

  用法：
    .\scripts\setup-emulator.ps1
    .\scripts\setup-emulator.ps1 -Force
#>
[CmdletBinding()]
param(
    [string] $ProjectDir = '',
    [string] $ToolchainDir = '',
    [string[]] $Proxies = @(
        'https://ghfast.top/',
        'https://ghproxy.net/',
        'https://gh-proxy.com/'
    ),
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Curl = Join-Path $env:SystemRoot 'System32\curl.exe'
if (-not (Test-Path -LiteralPath $Curl)) { $Curl = 'curl.exe' }

function Say([string] $m) { Write-Host ('[emulator] {0}' -f $m) }

function Invoke-Native {
    param([string] $Exe, [string[]] $Arguments)
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    return [pscustomobject]@{ ExitCode = $code; Output = ($output | ForEach-Object { $_.ToString() }) }
}

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
if ([string]::IsNullOrWhiteSpace($ToolchainDir)) { $ToolchainDir = Join-Path $ProjectDir '.toolchain' }

$downloadDir = Join-Path $ProjectDir '.tools'
$mgbaDir     = Join-Path $ToolchainDir 'mgba'
foreach ($d in @($downloadDir, $ToolchainDir)) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

# ------------------------------------------------------------------ 已装好？
$mgbaExe = Get-ChildItem -LiteralPath $mgbaDir -Filter 'mGBA.exe' -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($mgbaExe -and -not $Force) {
    Say ('已存在：{0}' -f $mgbaExe.FullName)
    exit 0
}

# ------------------------------------------------------------------ 经代理下载
function Save-FromProxy {
    param([string] $Url, [string] $OutFile, [long] $ExpectedSize = 0, [switch] $Direct)
    $targets = if ($Direct) { @('') } else { $Proxies }
    foreach ($proxy in $targets) {
        $full = if ($proxy) { $proxy.TrimEnd('/') + '/' + $Url } else { $Url }
        $label = if ($proxy) { ([uri]$proxy).Host } else { '直连' }
        if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force }
        Say ('  经 {0} 下载...' -f $label)
        $r = Invoke-Native -Exe $Curl -Arguments @(
            '--fail', '--location', '--silent', '--show-error',
            '--connect-timeout', '20', '--max-time', '1800',
            '-A', 'Mozilla/5.0',
            '-o', $OutFile, $full
        )
        if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $OutFile)) {
            Say ('    失败：{0}' -f ($r.Output -join ' '))
            continue
        }
        if ($ExpectedSize -gt 0 -and (Get-Item -LiteralPath $OutFile).Length -ne $ExpectedSize) {
            Say ('    大小不符（应为 {0}，实际 {1}）' -f $ExpectedSize, (Get-Item -LiteralPath $OutFile).Length)
            continue
        }
        return $true
    }
    return $false
}

# ------------------------------------------------------------------ 1. 7zr.exe
Say '第 1 步：准备 7-Zip 独立解压器 7zr.exe'
$sevenZr = Join-Path $downloadDir '7zr.exe'
$sevenZrSize = 602624

if (-not (Test-Path -LiteralPath $sevenZr) -or (Get-Item -LiteralPath $sevenZr).Length -ne $sevenZrSize -or $Force) {
    # 7-zip.org 在国内可直连，无需代理
    if (-not (Save-FromProxy -Url 'https://www.7-zip.org/a/7zr.exe' -OutFile $sevenZr -ExpectedSize $sevenZrSize -Direct)) {
        Say '  7zr.exe 下载失败（7-zip.org 不可达？）'
        exit 1
    }
}
Say ('  就绪：{0} ({1} 字节)' -f $sevenZr, (Get-Item -LiteralPath $sevenZr).Length)

# ------------------------------------------------------------------ 2. mGBA 7z
Say '第 2 步：下载 mGBA 0.10.5 便携包（约 14 MB）'
$archive     = Join-Path $downloadDir 'mGBA-0.10.5-win64.7z'
$archiveUrl  = 'https://github.com/mgba-emu/mgba/releases/download/0.10.5/mGBA-0.10.5-win64.7z'
$archiveSize = 14156919

if (-not (Test-Path -LiteralPath $archive) -or (Get-Item -LiteralPath $archive).Length -ne $archiveSize -or $Force) {
    if (-not (Save-FromProxy -Url $archiveUrl -OutFile $archive -ExpectedSize $archiveSize)) {
        Say '  下载失败：所有加速代理都不可用。'
        exit 1
    }
}
Say ('  就绪：{0} ({1} 字节)' -f $archive, (Get-Item -LiteralPath $archive).Length)
Say '  注意：mGBA 该 release 未发布官方校验值，只能校验字节数；解压成功即为格式正确。'

# ------------------------------------------------------------------ 3. 解压
Say '第 3 步：用 7zr 解压'
if (Test-Path -LiteralPath $mgbaDir) { Remove-Item -LiteralPath $mgbaDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $mgbaDir | Out-Null

$r = Invoke-Native -Exe $sevenZr -Arguments @('x', $archive, ('-o' + $mgbaDir), '-y')
if ($r.ExitCode -ne 0) {
    Say ('  解压失败：{0}' -f ($r.Output -join ' '))
    exit 1
}
$r.Output | Where-Object { $_ -match 'Everything is Ok|Files:|Folders:' } | ForEach-Object { Say ('  ' + $_) }

# ------------------------------------------------------------------ 4. 核对
Say '第 4 步：核对结果'
$found = @(Get-ChildItem -LiteralPath $mgbaDir -Filter '*.exe' -Recurse -File -ErrorAction SilentlyContinue)
foreach ($exe in $found) { Say ('  {0}  ({1:N1} MB)' -f $exe.FullName, ($exe.Length / 1MB)) }

if ($found.Count -eq 0) {
    Say '  没找到可执行文件，安装失败。'
    exit 1
}

Say ''
Say '试玩方式：'
Say '    双击工程根目录的 play.cmd'
Say '    或执行： .\build.ps1 -Run'
Say ''
Say '关于另外两个模拟器：NanoBoyAdvance 与 SkyEmu 曾下载并测试过，'
Say '但两者在本机加载 ROM 时都会崩溃（已排除 ROM、运行库、杀软、显卡因素），'
Say '且它们的包在本机解不开/用不了，已在整理磁盘时删除以回收 62 MB。'
Say '换机器后想再试，可以手动下载（都是 zip / 单文件，无需安装）。'
Say ''
Say '调试用（自带 GDB 远程调试）：mGBA 的「工具 → 启动 GDB 服务器」，'
Say '或参考 docs\04-学习路线.md 里的 mGBA + GDB 用法。'

exit 0
