#requires -Version 5.1
<#
  build.ps1 —— 一键把 source/ 里的 C 代码编译成能玩的 GBA ROM

  日常工作流就三步：
      1.  改 source\main.c
      2.  .\build.ps1
      3.  .\build.ps1 -Run         （构建完自动用 mGBA 打开）

  为什么不直接用 make：
    官方模板依赖 devkitARM 提供的一整套 Unix 工具链（make / rm / mkdir / gba_rules），
    而 devkitARM 的官方下载源在国内网络下不可达。本工程改用「普通 ARM GCC 直接编译」
    的方案（gbadev.net 推荐的 gba-bootstrap 路线），构建流程由这个脚本负责，
    你不需要装 make，也不需要 MSYS2。

  参数：
    -Clean          删掉 build\ 与旧 ROM，全部重新编译
    -Run            构建成功后自动启动 mGBA 试玩
    -ToolchainDir   工具链目录（默认 .toolchain）
#>
[CmdletBinding()]
param(
    [switch] $Clean,
    [switch] $Run,
    [string] $ToolchainDir = '',

    # 输出文件名（不含 .gba）。留空则用下面配置块里的 $RomName。
    # 用途：编测试版 ROM，例如自动演示版，不覆盖正在玩的那份。
    [string] $OutputName = '',

    # 额外的编译宏，多个用分号分隔，例如 -Define "GAL_AUTOPLAY"
    [string] $Define = '',

    # 要构建哪个工程（.gbastudio）。给了就先导出它、再生成资源、再编译。
    # 引擎本身不绑任何工程 ✓ 所以"构建什么"永远由调用方说 ✓
    [string] $Project = ''
)

$ErrorActionPreference = 'Stop'

# 指定了工程就先导出 + 生成资源（一条命令从工程到 ROM）
# 引擎本身不绑任何工程 ✓ 所以这一步是**可选的**：不指定就沿用现有导出 ✓
if (-not [string]::IsNullOrWhiteSpace($Project)) {
    Write-Host ('[build] 先构建资源：{0}' -f $Project)
    & (Join-Path $PSScriptRoot 'scripts\build-assets.ps1') -Project $Project
    if ($LASTEXITCODE -ne 0) { throw ('资源生成失败（退出码 {0}）' -f $LASTEXITCODE) }
}

# ======================================================================
#  想改游戏信息，改这四行就够了
# ======================================================================
$RomName   = 'gba_ai'            # 输出文件名：<RomName>.gba
$GameTitle = 'GBA AI DEMO'       # 标题，最多 12 个字符（显示在模拟器/烧录卡里）
$GameCode  = 'GBAI'              # 游戏代码，4 个字符
$MakerCode = '01'                # 厂商代码，2 个字符
# ======================================================================

if (-not [string]::IsNullOrWhiteSpace($OutputName)) { $RomName = $OutputName }

$ProjectDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ToolchainDir)) { $ToolchainDir = Join-Path $ProjectDir '.toolchain' }

# ----------------------------------------------------------------------
# 把编译器的临时目录指到工程内部。
#
# 为什么必须这么做：链接器（collect2/ld）需要建临时文件，默认用系统的 TEMP。
# 在受限/沙箱环境里，系统 TEMP 常常不可写，于是链接会以
#     Cannot create temporary file in C:\Users\...\Temp\: Permission denied
# 失败——而且报错信息完全看不出和构建脚本有关。
#
# 注意放在 .tmp 而不是 build\tmp：-Clean 会删掉整个 build\ 目录，
# 临时目录要是放在里面就会一起消失（我第一次就踩了这个坑）。
# ----------------------------------------------------------------------
$tmpDir = Join-Path $ProjectDir '.tmp'
if (-not (Test-Path -LiteralPath $tmpDir)) { New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null }
$env:TMP  = $tmpDir
$env:TEMP = $tmpDir

$sourceDir = Join-Path $ProjectDir 'source'
$inclDir   = Join-Path $ProjectDir 'include'
$buildDir  = Join-Path $ProjectDir 'build'
$sysDir    = Join-Path $sourceDir 'sys'
$bootSys   = Join-Path $ToolchainDir 'gba-bootstrap\template_c\source\sys'
$libtoncInc = Join-Path $ToolchainDir 'libtonc\include'
$libtoncLib = Join-Path $ToolchainDir 'lib\libtonc.a'
$libDir     = Join-Path $ToolchainDir 'lib'
$gccDir     = Join-Path $ToolchainDir 'arm-none-eabi-gcc\bin'
$gcc        = Join-Path $gccDir 'arm-none-eabi-gcc.exe'
$objcopy    = Join-Path $gccDir 'arm-none-eabi-objcopy.exe'
$sizeTool   = Join-Path $gccDir 'arm-none-eabi-size.exe'

$elfFile = Join-Path $buildDir ($RomName + '.elf')
$mapFile = Join-Path $buildDir ($RomName + '.map')
$romFile = Join-Path $ProjectDir ($RomName + '.gba')

function Say([string] $m) { Write-Host ('[build] {0}' -f $m) }
function Section([string] $t) { Write-Host ''; Write-Host ('--- {0} ---' -f $t) }

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

# ------------------------------------------------------------------ 检查工具链
foreach ($tool in @($gcc, $objcopy)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        Say ('找不到工具：{0}' -f $tool)
        Say '请先运行： .\scripts\setup-toolchain-china.ps1'
        exit 1
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $libtoncInc 'tonc.h'))) {
    Say ('找不到 libtonc：{0}' -f $libtoncInc)
    Say '请先运行： .\scripts\setup-toolchain-china.ps1'
    exit 1
}
if (-not (Test-Path -LiteralPath $libtoncLib)) {
    Say 'libtonc 还没编译，正在自动编译（只需一次）...'
    & (Join-Path $ProjectDir 'scripts\build-libtonc.ps1') -ProjectDir $ProjectDir -ToolchainDir $ToolchainDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $libtoncLib)) {
        Say 'libtonc 编译失败，中止。'
        exit 1
    }
}

# ------------------------------------------------------------------ 准备启动代码
# crt0（开机初始化）、链接脚本、newlib 桩函数来自 gba-bootstrap（CC0 许可，可自由使用）。
# 第一次构建时自动复制到 source\sys\ 下，之后你可以自由修改它们。
if (-not (Test-Path -LiteralPath $sysDir)) { New-Item -ItemType Directory -Force -Path $sysDir | Out-Null }

foreach ($f in @('gba_crt0.s', 'gba_cart.ld', 'syscalls.c')) {
    $dst = Join-Path $sysDir $f
    if (-not (Test-Path -LiteralPath $dst)) {
        $src = Join-Path $bootSys $f
        if (-not (Test-Path -LiteralPath $src)) {
            Say ('缺少 {0}，且工具链里也没有副本：{1}' -f $f, $src)
            Say '请重新运行： .\scripts\setup-toolchain-china.ps1'
            exit 1
        }
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Say ('已从 gba-bootstrap 复制启动文件：source\sys\{0}' -f $f)
    }
}

# ------------------------------------------------------------------ 清理
if ($Clean) {
    if (Test-Path -LiteralPath $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }
    if (Test-Path -LiteralPath $romFile)  { Remove-Item -LiteralPath $romFile -Force }
    Say '已清理 build\ 与旧 ROM'
}
if (-not (Test-Path -LiteralPath $buildDir)) { New-Item -ItemType Directory -Force -Path $buildDir | Out-Null }

# ------------------------------------------------------------------ 编译宏变化检测
# 增量编译只看"源文件与 .o 的时间戳"，**不知道编译宏变了**。
# 后果很隐蔽：先编自动演示版（-Define GAL_AUTOPLAY），再不加 -Clean 编正式版，
# build\ 里的 .o 仍是带宏的版本，正式版 ROM 就混进了测试代码 ——
# 表现为两份 ROM 大小一模一样。所以把宏记进标记文件，变了就自动全量重编。
$stampFile = Join-Path $buildDir 'build-flags.stamp'
$flagSig   = ('DEFINES=' + $Define + "`n")
if (Test-Path -LiteralPath $stampFile) {
    $prev = [IO.File]::ReadAllText($stampFile)
    if ($prev -ne $flagSig) {
        Say '编译宏与上次不同，自动全量重编（避免混入上次的测试代码）'
        Remove-Item -LiteralPath $buildDir -Recurse -Force
        New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
    }
} else {
    # 没有标记文件、但 build\ 里已有目标文件：这是旧版本构建留下的，
    # 不知道当初用了什么宏，保守起见先全量重编一次。
    $staleObjs = @(Get-ChildItem -LiteralPath $buildDir -Filter '*.o' -Recurse -ErrorAction SilentlyContinue).Count
    if ($staleObjs -gt 0) {
        Say ('build\ 里有 {0} 个来源不明的目标文件（无宏标记），先全量重编一次' -f $staleObjs)
        Remove-Item -LiteralPath $buildDir -Recurse -Force
        New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
    }
}
[IO.File]::WriteAllText($stampFile, $flagSig)

# ------------------------------------------------------------------ 收集源文件
$cSources   = @(Get-ChildItem -LiteralPath $sourceDir -Filter '*.c' -File -Recurse)
$asmSources = @(Get-ChildItem -LiteralPath $sourceDir -Filter '*.s' -File -Recurse)

if ($cSources.Count -eq 0) {
    Say ('source\ 下没有 .c 文件：{0}' -f $sourceDir)
    exit 1
}

# ------------------------------------------------------------------ 编译参数
$assetsDir = Join-Path $sourceDir 'assets'
$commonFlags = @(
    '-mcpu=arm7tdmi', '-mtune=arm7tdmi',
    '-mthumb', '-mthumb-interwork',
    '-D__GBA__',
    '-I', $sourceDir,
    '-I', $inclDir,
    # 生成的资源目录：C 代码要 #include 生成的头文件，
    # 汇编里的 .incbin 也靠这条 -I 找到 .bin 文件（GAS 会在 -I 路径里找 .incbin）
    '-I', $assetsDir,
    '-I', $libtoncInc,
    '-ffunction-sections', '-fdata-sections',
    '-g'
)
$cflags = @('-std=gnu11', '-Wall', '-O3') + $commonFlags
$sflags = @('-x', 'assembler-with-cpp') + $commonFlags

# 额外的编译宏（-Define "A;B"）
if (-not [string]::IsNullOrWhiteSpace($Define)) {
    foreach ($d in ($Define -split '[;,]')) {
        $d = $d.Trim()
        if ($d) {
            $cflags += ('-D' + $d)
            $sflags += ('-D' + $d)
            Say ('额外宏: -D{0}' -f $d)
        }
    }
}

# ------------------------------------------------------------------ 编译
Section '编译'

$objects  = @()
$failures = @()
$index    = 0
$total    = $cSources.Count + $asmSources.Count

$jobs = @()
foreach ($f in $cSources)   { $jobs += [pscustomobject]@{ File = $f; Flags = $cflags } }
foreach ($f in $asmSources) { $jobs += [pscustomobject]@{ File = $f; Flags = $sflags } }

foreach ($job in $jobs) {
    $index++
    $rel = $job.File.FullName.Substring($sourceDir.Length).TrimStart('\')
    $obj = Join-Path $buildDir ($rel + '.o')
    $objParent = Split-Path -Parent $obj
    if (-not (Test-Path -LiteralPath $objParent)) { New-Item -ItemType Directory -Force -Path $objParent | Out-Null }

    $needBuild = $true
    if (Test-Path -LiteralPath $obj) {
        if ((Get-Item -LiteralPath $obj).LastWriteTime -gt $job.File.LastWriteTime) { $needBuild = $false }
    }

    if (-not $needBuild) {
        $objects += $obj
        continue
    }

    Write-Host ('  CC  {0}' -f $rel)
    $r = Invoke-Tool -Exe $gcc -Arguments (@() + $job.Flags + @('-c', $job.File.FullName, '-o', $obj))

    foreach ($line in $r.Output) {
        if ($line -match 'warning:|error:|note:') { Write-Host ('      ' + $line) }
    }

    if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $obj)) {
        $failures += $rel
        foreach ($line in $r.Output) {
            if ($line -notmatch 'warning:|error:|note:') { Write-Host ('      ' + $line) }
        }
        continue
    }
    $objects += $obj
}

if ($failures.Count -gt 0) {
    Say ('编译失败：{0}' -f ($failures -join ', '))
    Say '上面带 error: 的行就是原因，把它发给我即可。'
    exit 1
}
Say ('编译通过（{0} 个源文件）' -f $total)

# ------------------------------------------------------------------ 链接
Section '链接'

$ldFlags = @(
    '-mcpu=arm7tdmi', '-mtune=arm7tdmi',
    '-mthumb', '-mthumb-interwork',
    '-L', $libDir,
    # 注意这里的括号：PowerShell 的逗号运算符优先级高于 +，
    # 写成  '-Wl,-Map,' + $mapFile  会被拆成两个数组元素，
    # 导致链接器收到一个没有参数的 -Map 和一个被当成输入文件的路径。
    ('-Wl,-Map,' + $mapFile),
    '-Wl,--gc-sections',
    '-specs=nano.specs',
    '-T', (Join-Path $sysDir 'gba_cart.ld'),
    '-Wl,--start-group', '-ltonc', '-lc', '-Wl,--end-group'
)

$r = Invoke-Tool -Exe $gcc -Arguments (@('-o', $elfFile) + $objects + $ldFlags)
if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $elfFile)) {
    Say '链接失败，原始输出如下：'
    foreach ($line in $r.Output) { Write-Host ('      ' + $line) }
    exit 1
}
Say ('已生成 {0}' -f (Split-Path -Leaf $elfFile))

# 内存占用报告（ROM 与 RAM 的用量，GBA 的 RAM 很小，这个数字值得看）
if (Test-Path -LiteralPath $sizeTool) {
    $s = Invoke-Tool -Exe $sizeTool -Arguments @($elfFile)
    Say '内存占用（text=ROM 中的代码/常量, data=占 ROM 也占 RAM, bss=只占 RAM）：'
    foreach ($line in $s.Output) { Write-Host ('      ' + $line) }
}

# ------------------------------------------------------------------ 生成 ROM
Section '生成 ROM'

$r = Invoke-Tool -Exe $objcopy -Arguments @('-O', 'binary', $elfFile, $romFile)
if ($r.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $romFile)) {
    Say 'objcopy 生成 ROM 失败：'
    foreach ($line in $r.Output) { Write-Host ('      ' + $line) }
    exit 1
}

# 修 ROM 头：写任天堂 Logo + 头部校验和，否则实机 BIOS 拒绝启动
& (Join-Path $ProjectDir 'tools\gbafix.ps1') -RomPath $romFile -Title $GameTitle -GameCode $GameCode -MakerCode $MakerCode
if ($LASTEXITCODE -ne 0) { Say 'gbafix 失败'; exit 1 }

# 校验 ROM 头
& (Join-Path $ProjectDir 'scripts\check-rom.ps1') -RomPath $romFile
$romOk = ($LASTEXITCODE -eq 0)

Section '结果'
$romSize = (Get-Item -LiteralPath $romFile).Length
Say ('ROM ：{0}' -f $romFile)
Say ('大小：{0:N0} 字节 ({1:N1} KB)' -f $romSize, ($romSize / 1KB))
Say ('地图：{0}' -f $mapFile)

if (-not $romOk) {
    Say 'ROM 头校验未通过，请把上面的 [check] 输出发给我。'
    exit 1
}

if ($Run) {
    # 首选 mGBA：本机实测可用（标题栏确认 60 fps、截图确认画面正确）。
    # 其余模拟器（NanoBoyAdvance / SkyEmu）已下载，但在本机加载 ROM 时会崩溃，
    # 实测结论记录在 scripts\setup-emulator.ps1 里。
    $candidates = @()

    $mgbaDir = Join-Path $ToolchainDir 'mgba'
    if (Test-Path -LiteralPath $mgbaDir) {
        # 显式优先 Qt 界面版 mGBA.exe（不要用排序，'mgba-sdl.exe' 会排在它前面）
        $preferred = Get-ChildItem -LiteralPath $mgbaDir -Filter 'mGBA.exe' -Recurse -File -ErrorAction SilentlyContinue |
                     Select-Object -First 1
        if ($preferred) { $candidates += $preferred.FullName }
        $candidates += @(Get-ChildItem -LiteralPath $mgbaDir -Filter '*.exe' -Recurse -File -ErrorAction SilentlyContinue |
                         ForEach-Object { $_.FullName })
    }
    $candidates += @( (Join-Path ${env:ProgramFiles} 'mGBA\mGBA.exe') )

    $emuDir = Join-Path $ToolchainDir 'emulator'
    if (Test-Path -LiteralPath $emuDir) {
        $candidates += @(Get-ChildItem -LiteralPath $emuDir -Filter '*.exe' -Recurse -File -ErrorAction SilentlyContinue |
                         ForEach-Object { $_.FullName })
    }

    $emulator = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

    if ($emulator) {
        Say ('启动模拟器试玩：{0}' -f $emulator)
        Start-Process -FilePath $emulator -ArgumentList @($romFile) | Out-Null
    } else {
        Say '没找到模拟器。先运行 .\scripts\setup-emulator.ps1 安装，'
        Say '或手动用任意 GBA 模拟器打开上面的 .gba 文件。'
    }
}

Say '构建成功。'
exit 0
