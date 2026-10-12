#requires -Version 5.1
<#
  shot-window.ps1 —— 给任意窗口截图（不需要窗口在前台）

  用 PrintWindow(PW_RENDERFULLCONTENT) 让窗口把自己渲染到内存位图里，
  所以即使窗口被别的程序挡着、或者你正在用电脑，也能拿到画面，
  而且**不会抢你的焦点**（这个原则在 docs/05 里说明过）。

  用法：
    .\scripts\dev\shot-window.ps1 -Title 'GBA Studio' -Out .tmp\studio.png
    .\scripts\dev\shot-window.ps1 -Process python -Title 'Studio' -Out x.png
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Title,
    [Parameter(Mandatory = $true)][string] $Out,
    [string] $Process = '',
    [int]    $WaitSeconds = 30
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

# 必须显式引用 System.Drawing，否则 Add-Type 编译 C# 时找不到 Bitmap/Graphics
Add-Type -ReferencedAssemblies 'System.Drawing' -TypeDefinition @"
using System;
using System.Text;
using System.Drawing;
using System.Runtime.InteropServices;
public class WinShot {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public delegate bool EnumProc(IntPtr h, IntPtr p);

    public static IntPtr Found = IntPtr.Zero;
    public static string FoundTitle = "";

    public static IntPtr Find(string needle, string procName) {
        Found = IntPtr.Zero; FoundTitle = "";
        EnumWindows((h, p) => {
            if (!IsWindowVisible(h)) return true;
            var sb = new StringBuilder(512); GetWindowTextW(h, sb, 512);
            string t = sb.ToString();
            if (t.Length == 0 || !t.Contains(needle)) return true;
            if (procName.Length > 0) {
                uint pid; GetWindowThreadProcessId(h, out pid);
                try { if (System.Diagnostics.Process.GetProcessById((int)pid).ProcessName != procName) return true; }
                catch { return true; }
            }
            Found = h; FoundTitle = t; return false;
        }, IntPtr.Zero);
        return Found;
    }

    // ---- 自检：这张图里到底有没有一个"真的游戏画面" ----
    //
    // 找 240x160 的整数倍区域（1x / 2x / 3x），要求：
    //   · 完全落在图内
    //   · 区域内有足够多的不同颜色（纯色 = 空白/被挡，不是画面）
    // 返回找到的位置和缩放倍数；找不到返回 false。
    //
    // 为什么需要它：这个脚本曾经安静地抓到桌面、抓到 160x28 的碎片 ✗
    // 不报错的结果就是"错图被当成证据"，进而得出错误结论。
    public static bool FindGameArea(Bitmap bmp, out int gx, out int gy, out int scale) {
        gx = 0; gy = 0; scale = 0;
        int W = bmp.Width, H = bmp.Height;
        for (int s = 1; s <= 4; s++) {
            int gw = 240 * s, gh = 160 * s;
            if (gw > W || gh > H) continue;
            // 沿窗口四边留出的空白里扫一遍（步长 4 像素，够用且快）
            for (int y = 0; y + gh <= H; y += 4) {
                for (int x = 0; x + gw <= W; x += 4) {
                    if (RegionLooksLikeScreen(bmp, x, y, gw, gh, s)) {
                        gx = x; gy = y; scale = s;
                        return true;
                    }
                }
            }
        }
        return false;
    }

    // 抽样判断：颜色种类够多就算"像画面"，纯色/渐变边框就不算
    static bool RegionLooksLikeScreen(Bitmap bmp, int x0, int y0, int gw, int gh, int s) {
        System.Collections.Generic.HashSet<int> seen =
            new System.Collections.Generic.HashSet<int>();
        int step = 8 * s;
        for (int y = y0 + s; y < y0 + gh - s; y += step) {
            for (int x = x0 + s; x < x0 + gw - s; x += step) {
                seen.Add(bmp.GetPixel(x, y).ToArgb());
                if (seen.Count >= 24) return true;   // 颜色够杂，是画面
            }
        }
        return seen.Count >= 24;
    }

    public static Bitmap Capture(IntPtr h, out int w, out int hh) {        RECT r; GetWindowRect(h, out r);
        w = r.Right - r.Left; hh = r.Bottom - r.Top;
        if (w <= 0 || hh <= 0) return null;
        Bitmap bmp = new Bitmap(w, hh);
        using (Graphics g = Graphics.FromImage(bmp)) {
            IntPtr hdc = g.GetHdc();
            PrintWindow(h, hdc, 2);
            g.ReleaseHdc(hdc);
        }
        // PrintWindow 有时拿到全黑图（OpenGL/Qt 窗口），退路：临时切前台截屏再把焦点还回去
        bool blank = true;
        Color first = bmp.GetPixel(w/2, hh/2);
        for (int i = 1; i <= 10 && blank; i++) {
            Color c = bmp.GetPixel((int)(w * i / 11.0), (int)(hh * ((i % 4) + 1) / 5.0));
            if (c.ToArgb() != first.ToArgb()) blank = false;
        }
        if (blank) {
            IntPtr prev = GetForegroundWindow();
            SetForegroundWindow(h);
            System.Threading.Thread.Sleep(400);
            using (Graphics g2 = Graphics.FromImage(bmp)) {
                g2.CopyFromScreen(r.Left, r.Top, 0, 0, new Size(w, hh));
            }
            if (prev != IntPtr.Zero && prev != h) SetForegroundWindow(prev);
        }
        return bmp;
    }
}
"@

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$hwnd = [IntPtr]::Zero
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) {
    $hwnd = [WinShot]::Find($Title, $Process)
    if ($hwnd -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 700 }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Host "[shot] 找不到标题含 '$Title' 的窗口"; exit 1 }

Write-Host ("[shot] 窗口: {0}" -f [WinShot]::FoundTitle)
Start-Sleep -Milliseconds 1200      # 等界面画完

# ---- 抓图 + **自检**：抓不到有效画面就重试，重试完还不行就报错退出 ----
#
# 为什么要自检：这个脚本曾经安静地抓到过桌面、抓到过 160x28 的碎片 ✗
# 而且**不报错** —— 调用方会把错图当证据，进而得出错误结论
#（踩过：因此误判"模式 1 花屏"，其实抓到的是模式切换那一帧）。
#
# 现在的规矩：抓完先验证"图里真的有一个 240x160（或它的整数倍）的游戏区域，
# 而且它不是一片纯色"；不满足就重抓，全部失败则以**非零退出码**失败，
# 让调用方立刻知道"这张图不能用"，而不是拿去当证据。
$Retries = 3
$ok = $false
$bmp = $null
for ($try = 1; $try -le $Retries -and -not $ok; $try++) {
    $w = 0; $h = 0
    $bmp = [WinShot]::Capture($hwnd, [ref]$w, [ref]$h)
    if (-not $bmp) { Write-Host "[shot] 第 $try 次捕获失败"; continue }
    $gx = 0; $gy = 0; $scale = 0
    $ok = [WinShot]::FindGameArea($bmp, [ref]$gx, [ref]$gy, [ref]$scale)
    if ($ok) {
        Write-Host "[shot] 第 $try 次有效：${w}x${h}，游戏区在 (${gx},${gy}) 缩放 ${scale}x"
    } else {
        Write-Host "[shot] 第 $try 次无效：${w}x${h} 里找不到有效的 240x160 游戏区域（可能被挡/抓错窗口）"
        $bmp.Dispose(); $bmp = $null
        Start-Sleep -Milliseconds 800
    }
}
if (-not $ok) {
    Write-Host "[shot] 抓不到有效画面，$Retries 次都失败 —— **这张图不能当证据用**" -ForegroundColor Red
    exit 2
}

$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host ("[shot] 已保存 {0}  ({1}x{2})" -f $Out, $w, $h)
exit 0
