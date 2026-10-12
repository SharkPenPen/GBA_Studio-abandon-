#requires -Version 5.1
<#
  setup-toolchain-china.ps1
  ---------------------------------------------------------------------------
  在国内网络下搭建 GBA 开发工具链（绕开被封锁的 devkitPro 与 GitHub 下载域名）。

  背景（都是本机实测结论）：
    * github.com / raw.githubusercontent.com / objects.githubusercontent.com
      / codeload.github.com 直连全部超时；
    * devkitpro.org 整个域名被 Cloudflare 拦截（"Sorry, you have been blocked"），
      所以官方安装器即使下载成功也取不到软件包；
    * 可达：api.github.com（直连）、若干 GitHub 加速代理、清华/中科大镜像。

  本脚本的取件策略：
    1. 编译器：经加速代理下载 xPack GNU Arm Embedded GCC 的 Windows x64 zip。
       官方 API 提供 SHA256，下载后逐字节校验 —— 代理无法篡改。
    2. libtonc / gba-bootstrap 的源码：tarball 走的 codeload 被代理拒绝，
       因此改为「先用 api.github.com 取完整文件清单（含每个文件的 git blob SHA1），
       再逐文件经代理下载 raw 内容，最后逐个校验 SHA1 与字节数」。
       api.github.com 是直连的，所以校验基准本身不经过代理，可信。
    3. 模拟器：转交给 scripts\setup-emulator.ps1（用 7zr 解开 mGBA 的免安装 7z 包）。

  所有产物都落在工程目录内（.toolchain / .tools），不写注册表，不需要管理员权限，
  整个工具链是可移植、可随时删除的。

  用法：
    .\scripts\setup-toolchain-china.ps1
    .\scripts\setup-toolchain-china.ps1 -SkipEmulator
    .\scripts\setup-toolchain-china.ps1 -ForceDownload
#>
[CmdletBinding()]
param(
    [string] $ProjectDir = '',
    [string] $ToolchainDir = '',
    [string] $DownloadDir = '',
    [string[]] $Proxies = @(
        'https://ghfast.top/',
        'https://ghproxy.net/',
        'https://gh-proxy.com/'
    ),
    [switch] $SkipEmulator,
    [switch] $ForceDownload
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Curl = Join-Path $env:SystemRoot 'System32\curl.exe'
if (-not (Test-Path -LiteralPath $Curl)) { $Curl = 'curl.exe' }
$Tar  = Join-Path $env:SystemRoot 'System32\tar.exe'

function Say([string] $m) { Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) }
function Section([string] $t) { Write-Host ''; Write-Host ('===== {0} =====' -f $t) }

# 原生命令（curl）会把进度/错误写到 stderr。PowerShell 在
# $ErrorActionPreference='Stop' 时会把「原生命令的 stderr」当成致命错误而中止脚本，
# 所以调用原生命令前后必须临时改成 Continue。
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
    return [pscustomobject]@{
        ExitCode = $code
        Output   = ($output | ForEach-Object { $_.ToString() })
    }
}

# 计算 git blob 的 SHA1：sha1("blob <长度>\0" + 内容)
# GitHub API 文件树里每个 blob 的 sha 就是这个值，可用于内容校验。
function Get-GitBlobSha1 {
    param([byte[]] $Bytes)

    $header = [Text.Encoding]::ASCII.GetBytes(('blob {0}' -f $Bytes.Length) + [char]0)
    $all    = New-Object byte[] ($header.Length + $Bytes.Length)
    [Array]::Copy($header, 0, $all, 0, $header.Length)
    [Array]::Copy($Bytes,  0, $all, $header.Length, $Bytes.Length)

    $sha1 = [Security.Cryptography.SHA1]::Create()
    try {
        return (($sha1.ComputeHash($all) | ForEach-Object { $_.ToString('x2') }) -join '')
    } finally {
        $sha1.Dispose()
    }
}

# ------------------------------------------------------------------ 路径准备
if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

if ([string]::IsNullOrWhiteSpace($ToolchainDir)) { $ToolchainDir = Join-Path $ProjectDir '.toolchain' }
if ([string]::IsNullOrWhiteSpace($DownloadDir))  { $DownloadDir  = Join-Path $ProjectDir '.tools' }

foreach ($d in @($ToolchainDir, $DownloadDir)) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

Say ('工程目录    : {0}' -f $ProjectDir)
Say ('工具链目录  : {0}' -f $ToolchainDir)
Say ('下载缓存    : {0}' -f $DownloadDir)
Say ('加速代理    : {0}' -f ($Proxies -join ', '))

# ------------------------------------------------------------------ 文件下载
function Save-FromProxy {
    <#
      经代理下载一个 URL 到文件：依次尝试各代理；给了 ExpectedSize 就校验字节数。
      返回 $true / $false。
    #>
    param(
        [string] $Url,
        [string] $OutFile,
        [long]   $ExpectedSize = 0,
        [string] $Label = ''
    )

    $dir = Split-Path -Parent $OutFile
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

    if ((Test-Path -LiteralPath $OutFile) -and -not $ForceDownload) {
        $len = (Get-Item -LiteralPath $OutFile).Length
        if (($ExpectedSize -eq 0) -or ($len -eq $ExpectedSize)) { return $true }
        Remove-Item -LiteralPath $OutFile -Force
    }

    foreach ($proxy in $Proxies) {
        $full = $proxy.TrimEnd('/') + '/' + $Url
        if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force }

        $r = Invoke-Native -Exe $Curl -Arguments @(
            '--fail', '--location', '--silent', '--show-error',
            '--connect-timeout', '20', '--max-time', '3600',
            '--retry', '1', '--retry-delay', '2',
            '-o', $OutFile,
            '-w', 'http=%{http_code} size=%{size_download}',
            $full
        )

        if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $OutFile)) {
            if ($Label) { Say ('    {0} : {1} 失败（{2}）' -f $Label, ([uri]$proxy).Host, ($r.Output -join ' ')) }
            continue
        }
        if ($ExpectedSize -gt 0 -and (Get-Item -LiteralPath $OutFile).Length -ne $ExpectedSize) {
            if ($Label) { Say ('    {0} : {1} 大小不符' -f $Label, ([uri]$proxy).Host) }
            continue
        }
        return $true
    }
    return $false
}

# ------------------------------------------------------------------ 同步 GitHub 仓库文件
function Sync-GithubRepo {
    <#
      以 api.github.com 的文件清单为基准（直连取得，不经代理），逐文件经代理下载并校验：
        * 字节数一致
        * git blob SHA1 一致（等于 GitHub 记录的 sha）
    #>
    param(
        [string]   $Owner,
        [string]   $Repo,
        [string]   $Ref,
        [string]   $DestDir,
        [string[]] $IncludeRegex,
        [switch]   $SkipExisting
    )

    $apiUrl = 'https://api.github.com/repos/{0}/{1}/git/trees/{2}?recursive=1' -f $Owner, $Repo, $Ref
    Say ('  读取文件清单：{0}' -f $apiUrl)

    $tree = Invoke-RestMethod -Uri $apiUrl -Headers @{ 'User-Agent' = 'gba-ai-toolchain-setup' } -TimeoutSec 90
    if (-not $tree.tree) { throw ('无法读取 {0}/{1} 的文件树' -f $Owner, $Repo) }

    $wanted = @()
    foreach ($node in $tree.tree) {
        if ($node.type -ne 'blob') { continue }
        foreach ($rx in $IncludeRegex) {
            if ($node.path -match $rx) { $wanted += $node; break }
        }
    }

    Say ('  需要 {0} 个文件（仓库共 {1} 个对象）' -f $wanted.Count, $tree.tree.Count)

    $ok = 0
    $failed = @()
    $i = 0
    foreach ($node in $wanted) {
        $i++
        $rel  = $node.path -replace '/', '\'
        $dest = Join-Path $DestDir $rel

        if ($SkipExisting -and (Test-Path -LiteralPath $dest) -and -not $ForceDownload) {
            if ((Get-Item -LiteralPath $dest).Length -eq $node.size) { $ok++; continue }
        }

        $rawUrl = 'https://raw.githubusercontent.com/{0}/{1}/{2}/{3}' -f $Owner, $Repo, $Ref, $node.path
        if (-not (Save-FromProxy -Url $rawUrl -OutFile $dest -ExpectedSize $node.size -Label ('[{0}/{1}] {2}' -f $i, $wanted.Count, $node.path))) {
            $failed += $node.path
            continue
        }

        $bytes   = [System.IO.File]::ReadAllBytes($dest)
        $blobSha = Get-GitBlobSha1 -Bytes $bytes
        if ($blobSha -ne $node.sha) {
            Say ('    SHA1 不匹配：{0}（GitHub {1}，实际 {2}）—— 已删除' -f $node.path, $node.sha, $blobSha)
            Remove-Item -LiteralPath $dest -Force
            $failed += $node.path
            continue
        }
        $ok++
    }

    Say ('  校验通过 {0}/{1} 个文件' -f $ok, $wanted.Count)
    if ($failed.Count -gt 0) {
        Say ('  失败文件：{0}' -f ($failed -join ', '))
        return $false
    }
    return $true
}

# ------------------------------------------------------------------ 1. 编译器
Section '1. ARM 交叉编译器（xPack GNU Arm Embedded GCC 15.2.1）'

$gccZip    = Join-Path $DownloadDir 'xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip'
$gccUrl    = 'https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v15.2.1-1.1/xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip'
$gccSize   = 335571206
$gccSha256 = 'BAE6A3D1667697CE750C3B13D6D26D80973ECEDC2CC87BF04869E83447FD93EA'

$gotGcc = $false
if ((Test-Path -LiteralPath $gccZip) -and ((Get-Item -LiteralPath $gccZip).Length -eq $gccSize)) {
    $h = (Get-FileHash -LiteralPath $gccZip -Algorithm SHA256).Hash
    if ($h -eq $gccSha256) {
        Say ('  使用已校验的缓存：{0}' -f (Split-Path -Leaf $gccZip))
        $gotGcc = $true
    } else {
        Say '  缓存 SHA256 不符，重新下载'
        Remove-Item -LiteralPath $gccZip -Force
    }
}

if (-not $gotGcc) {
    Say '  下载中（约 320 MB，实测约 7 MB/s）...'
    if (-not (Save-FromProxy -Url $gccUrl -OutFile $gccZip -ExpectedSize $gccSize -Label '编译器')) {
        throw '编译器下载失败：所有代理都不可用。'
    }
    $h = (Get-FileHash -LiteralPath $gccZip -Algorithm SHA256).Hash
    if ($h -ne $gccSha256) {
        Remove-Item -LiteralPath $gccZip -Force
        throw ('编译器 SHA256 校验失败！官方 {0}，实际 {1}。文件已删除。' -f $gccSha256, $h)
    }
    Say ('  SHA256 校验通过：{0}' -f $h)
}

$gccDir = Join-Path $ToolchainDir 'arm-none-eabi-gcc'
$gccExe = Join-Path $gccDir 'bin\arm-none-eabi-gcc.exe'
if (-not (Test-Path -LiteralPath $gccExe)) {
    Say '  解压中...'
    $tmp = Join-Path $ToolchainDir '.tmp-gcc'
    if (Test-Path -LiteralPath $tmp)    { Remove-Item -LiteralPath $tmp -Recurse -Force }
    if (Test-Path -LiteralPath $gccDir) { Remove-Item -LiteralPath $gccDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null

    $r = Invoke-Native -Exe $Tar -Arguments @('-xf', $gccZip, '-C', $tmp)
    if ($r.ExitCode -ne 0) { throw ('解压失败：{0}' -f ($r.Output -join ' ')) }

    $inner = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
    if (-not $inner) { throw '解压后没有找到目录，压缩包可能损坏。' }
    Move-Item -LiteralPath $inner.FullName -Destination $gccDir
    Remove-Item -LiteralPath $tmp -Recurse -Force
    Say ('  已解压到 {0}' -f $gccDir)
} else {
    Say ('  已存在：{0}' -f $gccDir)
}

# ------------------------------------------------------------------ 2. libtonc
Section '2. libtonc 源码（gbadev-org/libtonc）'

# 只需要能编译出 libtonc.a 的文件：头文件、C 源、汇编源（含预生成字体数据），
# 仓库里的 png 与文档不需要。
$libtoncPatterns = @(
    '^include/.*\.h$',
    '^src/.*\.c$',
    '^src/.*\.s$',
    '^asm/.*\.s$',
    '^base\.[ch]$',
    '^license\.txt$',
    '^readme\.md$'
)
$libtoncDir = Join-Path $ToolchainDir 'libtonc'
$libtoncOk  = Sync-GithubRepo -Owner 'gbadev-org' -Repo 'libtonc' -Ref 'master' `
                              -DestDir $libtoncDir -IncludeRegex $libtoncPatterns -SkipExisting

# ------------------------------------------------------------------ 3. gba-bootstrap
Section '3. GBA 启动代码与链接脚本（AntonioND/gba-bootstrap）'

# 这是 gbadev.net 官方推荐的方案：用普通 arm-none-eabi-gcc 也能构建 GBA ROM。
# 只取运行必需的三个文件（crt0 / 链接脚本 / newlib 桩），外加许可证与参考 Makefile。
$bootPatterns = @(
    '^template_c/source/sys/.*$',
    '^template_c/Makefile$',
    '^readme\.rst$',
    '^licenses/.*$'
)
$bootDir = Join-Path $ToolchainDir 'gba-bootstrap'
$bootOk  = Sync-GithubRepo -Owner 'AntonioND' -Repo 'gba-bootstrap' -Ref 'master' `
                           -DestDir $bootDir -IncludeRegex $bootPatterns -SkipExisting

# ------------------------------------------------------------------ 4. 核对
Section '4. 核对安装结果'

$checks = @(
    @{ Label = 'ARM 交叉编译器';        Path = $gccExe },
    @{ Label = 'binutils objcopy';      Path = (Join-Path $gccDir 'bin\arm-none-eabi-objcopy.exe') },
    @{ Label = '归档工具 ar';           Path = (Join-Path $gccDir 'bin\arm-none-eabi-ar.exe') },
    @{ Label = 'libtonc 头文件 tonc.h'; Path = (Join-Path $libtoncDir 'include\tonc.h') },
    @{ Label = 'libtonc 源码 base.c';   Path = (Join-Path $libtoncDir 'base.c') },
    @{ Label = 'libtonc TTE 主文件';    Path = (Join-Path $libtoncDir 'src\tte\tte_main.c') },
    @{ Label = 'libtonc 8x8 字体';      Path = (Join-Path $libtoncDir 'src\font\sys8.s') },
    @{ Label = '启动代码 gba_crt0.s';   Path = (Join-Path $bootDir 'template_c\source\sys\gba_crt0.s') },
    @{ Label = '链接脚本 gba_cart.ld';  Path = (Join-Path $bootDir 'template_c\source\sys\gba_cart.ld') },
    @{ Label = 'newlib 桩 syscalls.c';  Path = (Join-Path $bootDir 'template_c\source\sys\syscalls.c') }
)

$missing = @()
foreach ($ck in $checks) {
    $ok = Test-Path -LiteralPath $ck.Path
    if (-not $ok) { $missing += $ck.Label }
    Say ('{0,-24} {1}' -f $ck.Label, $(if ($ok) { 'OK' } else { '缺失 -> ' + $ck.Path }))
}

if (Test-Path -LiteralPath $gccExe) {
    Say ''
    Say '编译器自检：'
    $v = Invoke-Native -Exe $gccExe -Arguments @('--version')
    Say ('  {0}' -f ($v.Output | Select-Object -First 1))
    $t = Invoke-Native -Exe $gccExe -Arguments @('-dumpmachine')
    Say ('  目标平台: {0}' -f ($t.Output | Select-Object -First 1))
}

# ------------------------------------------------------------------ 5. 模拟器
# 这一步交给 scripts\setup-emulator.ps1（用 7-Zip 官方的 7zr.exe 解开 mGBA 的
# 免安装 7z 包）。早期版本在这里直接下载 mGBA 的安装器并尝试静默安装，
# 但那条路在本环境下必然失败：mGBA 的 Windows 安装器需要管理员提权装到
# Program Files，非交互环境下返回退出码 1。相关逻辑已删除，避免留下重复且
# 不可用的路径 —— 工具链脚本只管编译器与库，模拟器由专门的脚本负责。
if (-not $SkipEmulator) {
    Section '5. 模拟器（转交 setup-emulator.ps1）'
    $emuScript = Join-Path $PSScriptRoot 'setup-emulator.ps1'
    if (Test-Path -LiteralPath $emuScript) {
        & $emuScript -ProjectDir $ProjectDir -ToolchainDir $ToolchainDir
        if ($LASTEXITCODE -ne 0) { Say '  模拟器安装未成功（不影响编译，只影响本机试玩）' }
    } else {
        Say ('  找不到 {0}，跳过。' -f $emuScript)
    }
}

# ------------------------------------------------------------------ 总结
Section '总结'
$problems = @()
if ($missing.Count -gt 0) { $problems += ('缺失组件：' + ($missing -join '、')) }
if (-not $libtoncOk)      { $problems += 'libtonc 有文件下载或校验失败' }
if (-not $bootOk)         { $problems += 'gba-bootstrap 有文件下载或校验失败' }

if ($problems.Count -eq 0) {
    Say '工具链就绪，所有组件均已校验。下一步：编译 libtonc 并构建第一个 ROM。'
    exit 0
}

foreach ($p in $problems) { Say ('问题：{0}' -f $p) }
exit 1
