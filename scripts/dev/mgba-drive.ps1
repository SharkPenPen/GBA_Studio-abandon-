#requires -Version 5.1
<#
  mgba-drive.ps1 —— 驱动 mGBA 做自动化交互测试（发按键 + 截图）

  【为什么需要它】
    GBA 的交互只能靠"按键 → 看画面"来验证，而手工在模拟器里点几十次
    既慢又没法复现。这个脚本把 mGBA 窗口顶到前台，用 Windows 的按键注入
    模拟手柄按键，并在指定时刻截图，于是整个流程可以重复执行、逐帧比对。

  【mGBA 的默认按键映射】（来自它自己的 config.toml）
    手柄 A → 键盘 A      手柄 B → 键盘 S
    START  → 回车        SELECT → 退格
    方向键 → 键盘方向键

  【步骤语法】用分号分隔
    wait:2          等 2 秒
    key:A           按一下 A（可用 A B START SELECT UP DOWN LEFT RIGHT）
    keys:A+A        连续按多个键
    shot:01-title   截一张图，存成 <OutDir>\01-title.png

  用法：
    .\scripts\dev\mgba-drive.ps1 -Steps "wait:3;shot:01-title;key:DOWN;shot:02"
    .\scripts\dev\mgba-drive.ps1 -Rom .\gba_ai.gba -Steps "..." -KeepOpen
#>
[CmdletBinding()]
param(
    [string] $Rom = '',
    [string] $OutDir = '',
    [string] $Steps = 'wait:3;shot:01-title',
    [string] $WindowTitleMatch = 'GBA AI DEMO',
    [string] $Emulator = '',
    [switch] $KeepOpen
)

$ErrorActionPreference = 'Stop'
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($Rom))      { $Rom = Join-Path $ProjectDir 'gba_ai.gba' }
if ([string]::IsNullOrWhiteSpace($OutDir))   { $OutDir = Join-Path $ProjectDir '.tmp\shots' }
if ([string]::IsNullOrWhiteSpace($Emulator)) {
    $Emulator = Join-Path $ProjectDir '.toolchain\mgba\mGBA-0.10.5-win64\mGBA.exe'
}
if (-not (Test-Path -LiteralPath $Rom))      { throw "找不到 ROM: $Rom" }
if (-not (Test-Path -LiteralPath $Emulator)) { throw "找不到模拟器: $Emulator" }
# 必须转成绝对路径：Start-Process 的参数是按**子进程的工作目录**解析的，
# 而下面把工作目录设成了 mGBA 自己的目录，相对路径会因此找不到 ROM ——
# 现象是模拟器起来了但没加载游戏，窗口标题里没有 ROM 名。
$Rom = (Resolve-Path -LiteralPath $Rom).Path
if (-not (Test-Path -LiteralPath $OutDir))   { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

function Say([string] $m) { Write-Host ('[drive] {0}' -f $m) }

Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinDrv {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public delegate bool EnumProc(IntPtr h, IntPtr p);

    public static IntPtr Find(uint pid, string needle) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, p) => {
            uint id; GetWindowThreadProcessId(h, out id);
            if (id == pid && IsWindowVisible(h)) {
                var sb = new StringBuilder(256); GetWindowTextW(h, sb, 256);
                if (sb.ToString().Contains(needle)) { found = h; return false; }
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
    public static void Key(IntPtr h, byte vk, ushort scan, bool extended) {
        // 把按键消息**直接投递给目标窗口**，不需要它处于前台。
        // 为什么不用 keybd_event（全局注入）：那要求目标窗口是前台窗口，
        // 一旦你切去用别的程序（浏览器、聊天工具），按键就打进那个程序里 ——
        // 既测不到游戏，还会干扰你正在做的事。本次开发中就这么误发过一次。
        uint down = (uint)(1 | (scan << 16) | (extended ? (1 << 24) : 0));
        uint up   = down | 0xC0000000u;        // 补上 transition / previous-state 位
        PostMessage(h, 0x0100, (IntPtr)vk, (IntPtr)down);   // WM_KEYDOWN
        System.Threading.Thread.Sleep(60);
        PostMessage(h, 0x0101, (IntPtr)vk, (IntPtr)up);     // WM_KEYUP
        System.Threading.Thread.Sleep(60);
    }
}
"@

# 手柄键 → (Windows 虚拟键码, 扫描码, 是否扩展键)
#
# 键位**必须照抄 mGBA 自己的配置**（.toolchain\mgba\...\config.ini 里的
# [gba.input.QT_K]），不能凭印象写。实测 mGBA 的默认映射是：
#     A → 键盘 X        B → 键盘 Z
#     START → 回车      SELECT → 退格
#     L → A 键          R → S 键        方向 → 方向键
# （第一版照抄了另一个模拟器的 A/S，结果按键全错 —— 这类"想当然"最费时间。）
$VK = @{
    'A'      = @(0x58, 0x2D, $false)   # X
    'B'      = @(0x5A, 0x2C, $false)   # Z
    'START'  = @(0x0D, 0x1C, $false)
    'SELECT' = @(0x08, 0x0E, $false)
    'UP'     = @(0x26, 0x48, $true)
    'DOWN'   = @(0x28, 0x50, $true)
    'LEFT'   = @(0x25, 0x4B, $true)
    'RIGHT'  = @(0x27, 0x4D, $true)
    'L'      = @(0x41, 0x1E, $false)
    'R'      = @(0x53, 0x1F, $false)
}

# ------------------------------------------------------------------ 启动模拟器
Get-Process mGBA -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
Start-Sleep -Seconds 3
Get-Process mGBA -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Say ('启动 {0}' -f (Split-Path $Emulator -Leaf))
# mGBA 首次启动一个新 ROM 时偶尔会立刻退出（疑似首次建立游戏库、或被杀软扫描打断）。
# play.cmd 里也有同样的重试处理，这里最多重试 3 次。
$proc = $null
$attempt = 0
for ($attempt = 1; $attempt -le 3 -and -not $proc; $attempt++) {
    # 必须重定向子进程的标准输出/错误：否则 mGBA 会继承本脚本的输出管道，
    # 脚本结束后管道仍不关闭，调用方会一直以为脚本还在运行。
    Start-Process -FilePath $Emulator -ArgumentList @('-g', $Rom) `
                  -WorkingDirectory (Split-Path $Emulator) `
                  -RedirectStandardOutput (Join-Path $OutDir '_mgba-out.txt') `
                  -RedirectStandardError  (Join-Path $OutDir '_mgba-err.txt') | Out-Null
    for ($i = 0; $i -lt 15 -and -not $proc; $i++) {
        Start-Sleep -Seconds 1
        $proc = Get-Process mGBA -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $proc) { Say ('  第 {0} 次启动没起来，重试...' -f $attempt) }
}
if (-not $proc) { throw 'mGBA 启动失败（重试 3 次）' }
Say ('  启动成功（第 {0} 次尝试）' -f $attempt)

# mGBA 用 -g 启动，会**停在启动处等调试器** —— 先连一次让它跑起来。
# 同一条通道也是抓帧用的（tools/grab_screen.py 从显存渲染，不截窗口）。
$script:GrabScript = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'tools\grab_screen.py'
$script:GrabOk = $false
if (Test-Path $script:GrabScript) {
    & python $script:GrabScript --wait 0 --probe 2>&1 | Out-Null
    $script:GrabOk = ($LASTEXITCODE -eq 0)
    if ($script:GrabOk) { Say '  已接上调试通道（抓帧将从显存渲染）' }
    else { Say '  ⚠ 接不上调试通道，截图退回窗口截图' }
} else {
    Say '  ⚠ 找不到 tools/grab_screen.py，截图退回窗口截图'
}

$hwnd = [IntPtr]::Zero
for ($i = 0; $i -lt 30; $i++) {
    $hwnd = [WinDrv]::Find([uint32]$proc.Id, $WindowTitleMatch)
    if ($hwnd -ne [IntPtr]::Zero) { break }
    Start-Sleep -Seconds 1
}
if ($hwnd -eq [IntPtr]::Zero) { throw ("没找到标题含 '{0}' 的窗口" -f $WindowTitleMatch) }

$proc.Refresh()
Say ('窗口: {0}' -f $proc.MainWindowTitle)
# 不最大化：保持 mGBA 默认的 2 倍整数缩放，截图更清晰（放大反而会引入模糊）
[WinDrv]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Seconds 1

function Test-Blank([System.Drawing.Bitmap] $bmp) {
    # 采样判断图像是不是"一片纯色"（PrintWindow 抓 OpenGL 窗口时常常返回黑图）
    $w = $bmp.Width; $h = $bmp.Height
    $first = $bmp.GetPixel([int]($w / 2), [int]($h / 2)).ToArgb()
    $diff = 0
    for ($i = 1; $i -le 12; $i++) {
        $x = [int]($w * $i / 13); $y = [int]($h * (($i % 5) + 1) / 6)
        if ($bmp.GetPixel($x, $y).ToArgb() -ne $first) { $diff++ }
    }
    return ($diff -le 1)
}

function Save-Shot([string] $label) {
    $path = Join-Path $OutDir ($label + '.png')

    # ---- 首选：**从显存直接把这一帧渲染出来**（tools/grab_screen.py）----
    #
    # 为什么不截窗口：窗口截图在这台机器上**不稳定** ✗
    #   · 窗口被挡 / 不在前台 → 抓到桌面
    #   · 尺寸算错 → 抓到 160x28 的碎片
    #   · 而且**不报错** —— 错图会被当成证据，进而得出错误结论
    #     （踩过：因此误判过"模式 1 花屏"，其实抓到的是模式切换那一帧）
    #
    # 从显存渲染就没有这些问题：不依赖窗口位置、结果是确定的、
    # 而且会把 DISPCNT / 层开关一起打印出来，出问题直接看到原因。
    # 需要 mGBA 用 -g 启动（脚本已经这么启动），每次抓帧连一次、抓完断开。
    if ($script:GrabOk) {
        $py = & python $script:GrabScript --wait 0 --out $path 2>&1
        if ($LASTEXITCODE -eq 0 -and (Test-Path $path)) {
            $line = ($py | Select-String '已保存' | Select-Object -First 1)
            Say ('  抓帧 {0}  {1}' -f (Split-Path $path -Leaf), $(if ($line) { '（从显存渲染）' } else { '' }))
            return
        }
        Say '  从显存抓帧失败，退回窗口截图'
    }

    $r = New-Object WinDrv+RECT
    [WinDrv]::GetWindowRect($hwnd, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
    if ($w -le 0 -or $h -le 0) { Say "  截图失败：窗口尺寸异常 ${w}x${h}"; return }
    $bmp = New-Object System.Drawing.Bitmap($w, $h)

    # 窗口截图：先 PrintWindow，拿不到就顶到前台截屏
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [WinDrv]::PrintWindow($hwnd, $hdc, 2)   # 2 = PW_RENDERFULLCONTENT
    $g.ReleaseHdc($hdc)
    $g.Dispose()

    if (-not $ok -or (Test-Blank $bmp)) {
        $prev = [WinDrv]::GetForegroundWindow()
        [WinDrv]::SetForegroundWindow($hwnd) | Out-Null
        Start-Sleep -Milliseconds 500
        $g2 = [System.Drawing.Graphics]::FromImage($bmp)
        $g2.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
        $g2.Dispose()
        if ($prev -ne [IntPtr]::Zero -and $prev -ne $hwnd) {
            [WinDrv]::SetForegroundWindow($prev) | Out-Null
        }
    }

    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    # 窗口截图**必须自检**：尺寸对不对、是不是纯色 —— 不对就明确说"这张图不能用"，
    # 而不是安静地交出去。调用方看到 240x160 才能当证据。
    Say ('  截图 {0}  ({1}x{2})  [窗口截图，尺寸不保证 240x160]' -f (Split-Path $path -Leaf), $w, $h)
}

# ------------------------------------------------------------------ 执行步骤
Say '执行步骤序列'
foreach ($step in ($Steps -split ';')) {
    $step = $step.Trim()
    if (-not $step) { continue }
    $parts = $step -split ':', 2
    $verb  = $parts[0].Trim()
    $arg   = if ($parts.Count -gt 1) { $parts[1].Trim() } else { '' }
    switch ($verb.ToLower()) {
        'wait' { Start-Sleep -Seconds ([double]$arg) }
        'key'  {
            $k = $arg.ToUpper()
            if (-not $VK.ContainsKey($k)) { Say "  未知按键 $k"; continue }
            $info = $VK[$k]
            [WinDrv]::Key($hwnd, [byte]$info[0], [uint16]$info[1], [bool]$info[2])
        }
        'keys' {
            foreach ($k in ($arg -split '\+')) {
                $k = $k.Trim().ToUpper()
                if ($VK.ContainsKey($k)) {
                    $info = $VK[$k]
                    [WinDrv]::Key($hwnd, [byte]$info[0], [uint16]$info[1], [bool]$info[2])
                }
            }
        }
        'shot' { Save-Shot $arg }
        default { Say "  未知步骤 $step" }
    }
}

if (-not $KeepOpen) {
    Get-Process mGBA -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
    Start-Sleep -Seconds 2
    Get-Process mGBA -ErrorAction SilentlyContinue | Stop-Process -Force
    Say '模拟器已关闭'
} else {
    Say '模拟器保持打开'
}
Say ('截图目录: {0}' -f $OutDir)
exit 0
