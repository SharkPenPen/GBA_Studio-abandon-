#requires -Version 5.1
<#
  build-assets.ps1 —— 重新生成全部游戏资源

  【顺序不能乱】
    1. build_script.py    剧本 → source\assets\scenario.c（命令数组）+ scenario_charset.txt
    2. make_cjk_font.py   字符集 → 10x10 中文点阵字库 + font_index.bin
    3. make_assets.py     图片 → 16 位色位图数据（背景 / 立绘 / LOGO）

        第 2 步必须排在第 1 步之后：字库是按"游戏里真正会用到的字"生成的，
    剧本是字符集的主要来源。顺序反了就会缺字 —— 屏幕上出现空白，
    而且不报任何错，这是中文 GBA 游戏最难查的问题之一。

  什么时候要重跑：
    - 改了 scenario\scenario.txt（加了新台词 → 可能有新汉字）
    - 改了 C 代码里的界面文字（比如菜单项）
    - 换了 graphics\ 里的素材
    - 改了字号或字体（make_cjk_font.py --size / --font）

  用法：
    .\scripts\build-assets.ps1
    .\scripts\build-assets.ps1 -FontSize 12                 # 直接用 12px 点阵（不缩放）
    .\scripts\build-assets.ps1 -FontSize 10                 # 更小（笔画会损失一些）
    .\scripts\build-assets.ps1 -Python "C:\...\python.exe"

  字号说明（很重要，别直接调小字号）：
    宋体只在 **12px（9 号）** 这一档**内嵌点阵字形**，笔画锐利；
    其它字号走轮廓线缩放 + 抗锯齿，小字号下会糊、会断。
    所以本脚本的做法是：
        -StrikeSize 12  → 用 12px 渲染（命中内嵌点阵）
        -FontSize   11  → 再把点阵面积平均缩到 11px（当前默认）
    实测同一句话的平均亮点：12px 点阵 40.4 → 缩到 11px 36.4（仍然锐利）
    vs 直接渲染 11px 轮廓只有 18.9（9/18 个字笔画断裂）。

  改字号后**必须同步改** source\galgame.c 顶部的布局常量（行距、每行像素预算）。
#>

[CmdletBinding()]
param(
    [string] $ProjectDir = '',
    [string] $Python = '',
    [int]    $FontSize = 11,
    [int]    $StrikeSize = 12,
    [string] $FontFile = '',

    # 要构建哪个工程（.gbastudio 的路径）。留空则用 scenario\ 里**现有的**导出。
    # 用途：引擎本身不该绑死任何工程 —— 示例是"用来测试引擎的"，
    # 不该变成"引擎的构建依赖"。所以谁要构建什么，由调用方指定。
    [string] $Project = ''
)

$ErrorActionPreference = 'Stop'

# ---- 清理上一次的生成物 ----
# 踩过：source\assets 里残留的 .bin（比如做实验留下的 probe_bg.bin）
# 不会被自动删掉，而且会被一起编进 ROM ✗ 换了素材之后更是"旧文件还在" ✗
# 所以每次生成前先清掉**生成物**（只删这几类，别的文件不动）
$assetDir = Join-Path $PSScriptRoot '..\source\assets'
foreach ($pat in @('*.bin', '*.s', '*.c', '*.h', '*.txt')) {
    Get-ChildItem -Path $assetDir -Filter $pat -File -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
Write-Host '[assets] 已清理上一次的生成物'

function Say([string] $m) { Write-Host ('[assets] {0}' -f $m) }

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

# ------------------------------------------------------------------ 找 Python
# 资源脚本需要 Pillow。系统 Python 不一定装了，所以优先用 DSH 自带的运行时
# （它自带 Pillow / numpy），找不到再退回 PATH 里的 python。
function Test-HasPillow([string] $exe) {
    if ([string]::IsNullOrWhiteSpace($exe)) { return $false }
    if (-not (Test-Path -LiteralPath $exe) -and -not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $false }
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $exe -c "import PIL, numpy; print('ok')" 2>&1
        return ($LASTEXITCODE -eq 0 -and ($out -join '') -match 'ok')
    } finally {
        $ErrorActionPreference = $saved
    }
}

if (-not (Test-HasPillow $Python)) {
    $candidates = @(
        (Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'),
        'python'
    )
    foreach ($c in $candidates) {
        if (Test-HasPillow $c) { $Python = $c; break }
    }
}
if (-not (Test-HasPillow $Python)) {
    Say '找不到带 Pillow 的 Python。请用 -Python 指定一个，或先安装：pip install pillow numpy'
    exit 1
}
Say ('Python: {0}' -f $Python)

# Python 输出中文要显式指定编码，否则在 GBK 控制台下会乱码
$env:PYTHONIOENCODING = 'utf-8'

# ---- 指定了工程就先导出 ----
# ⚠ 这一段必须放在**这里** ✗
# 第一版我把它插在文件最前面 ✓ 结果连撞两个"定义在后面"的坑：
#   · 用了 Say   → 那个函数在下面才定义 → "The term 'Say' is not recognized"
#   · 用了 $Python → 那时它还是空的       → "expression after '&' … not valid"
# PowerShell 是**顺序执行**的 ✓ 用到的函数和变量必须先就位 ✓
if (-not [string]::IsNullOrWhiteSpace($Project)) {
    Say ('先导出工程：{0}' -f $Project)
    & $Python (Join-Path $PSScriptRoot '..\tools\export_project.py') --project $Project
    if ($LASTEXITCODE -ne 0) { throw ('导出工程失败（退出码 {0}）' -f $LASTEXITCODE) }
}

function Invoke-Py([string] $script, [string[]] $extra) {
    $path = Join-Path $ProjectDir $script
    if (-not (Test-Path -LiteralPath $path)) { throw ('找不到脚本 {0}' -f $path) }
    $args = @($path) + $extra
    & $Python @args
    if ($LASTEXITCODE -ne 0) { throw ('{0} 执行失败（退出码 {1}）' -f $script, $LASTEXITCODE) }
}

# ------------------------------------------------------------------ 1. 剧本
Say '第 1 步：编译剧本'
Invoke-Py 'tools\build_script.py' @()

# ------------------------------------------------------------------ 2. 字库
Say '第 2 步：生成中文字库'
$fontArgs = @('--size', "$FontSize", '--strike', "$StrikeSize")
if (-not [string]::IsNullOrWhiteSpace($FontFile)) { $fontArgs += @('--font', $FontFile) }
Invoke-Py 'tools\make_cjk_font.py' $fontArgs

# ------------------------------------------------------------------ 3. 图片
Say '第 3 步：转换美术素材'
# 资源：优先用"项目清单"驱动（P5 起引擎认索引表，任意数量背景/立绘）
# 没有清单（旧流程/手写剧本）才退回写死资源的 make_assets.py
if (Test-Path 'scenario\assets.json') {
    Invoke-Py 'tools\make_project_assets.py' @()
} else {
    Invoke-Py 'tools\make_assets.py' @()
}

# ------------------------------------------------------------------ 4. 音频
Say '第 4 步：转换音频'
# 清单里没有音频时也要跑：要生成空的 snd_clips 表，否则引擎链接会失败
Invoke-Py 'tools\make_project_audio.py' @()

# ------------------------------------------------------------------ 5. 关卡
Say '第 5 步：编译关卡地图（P8）'
# 读 scenario\level.txt（编辑器导出时写的）；没有就用默认地图 ——
# 引擎要求 lvl_map 符号一定存在，不然链接就断了。
Invoke-Py 'tools\make_project_level.py' @()

# ------------------------------------------------------------------ 6. 动画
Say '第 6 步：编译精灵动画（P9）'
# 读 scenario\assets.json 里的 animations 段；没有就生成空表（同上，符号必须有）。
# 和背景/立绘/音频走同一条路：编辑器把清单写进 scenario\，这边只认清单。
Invoke-Py 'tools\make_project_anim.py' @()

# ------------------------------------------------------------------ 汇总

Say ''
Say '生成完毕，接下来编译 ROM：'
Say '    .\build.ps1'
$gen = Get-ChildItem -LiteralPath (Join-Path $ProjectDir 'source\assets') -File -ErrorAction SilentlyContinue
$total = ($gen | Measure-Object Length -Sum).Sum
Say ('source\assets\ 共 {0} 个文件，{1:N0} KB（这些会被直接编进 ROM）' -f $gen.Count, ($total / 1KB))
# ---- 产物自检 ----
# 踩过：某一步"悄悄没产出"（比如一张图都没有时 make_project_assets 退出码 1）
# 会让后面几步不跑，最后在**链接期**报一堆 undefined reference ✗
# 那时候根本看不出是哪一步的问题 ✓ 所以这里显式检查关键产物在不在 ✓
$must = @(
    'source\assets\scenario.c',
    'source\assets\gfx_assets.c',
    'source\assets\anim_data.c',
    'source\assets\level_data.c',
    'include\gfx_assets.h',
    'include\font_data.h',
    'include\snd_data.h',
    'include\anim_data.h',
    'include\level_data.h'
)
$missing = @()
foreach ($f in $must) {
    $q = Join-Path $ProjectDir $f
    if (-not (Test-Path -LiteralPath $q)) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Say ('✗ 这些产物没生成：{0}' -f ($missing -join ', '))
    Say '  上面哪一步报错了，就是它的原因（修好那一步再跑）'
    exit 1
}
Say ('产物自检通过（{0} 个关键文件都在）' -f $must.Count)

exit 0
