#requires -Version 5.1
<#
  check-rom.ps1 —— 校验 .gba 文件的头部是否合法

  为什么需要它：
    GBA 实机的 BIOS 在开机时会先检查 ROM 头（0x00~0xBD 这 192 个字节）：
    检查不通过就直接白屏，什么都不做。模拟器有的会宽容一点，有的不会。
    所以"编译成功但打不开"九成是头不对。这个脚本把这些检查自动化。

  校验项：
    - 0xB2 必须等于 0x96（固定标记字节）
    - 0xBD 是头部校验和：把 0xA0~0xBC 逐字节相加，取补码
    - 0xA0 起的 12 字节是游戏标题，应当是可见 ASCII 字符
    - 0x04~0x9F 是任天堂 Logo 位图（实机 BIOS 会核对），对不上只警告不报错
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $RomPath
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $RomPath)) {
    Write-Host ('[check] 找不到文件：{0}' -f $RomPath)
    exit 1
}

$file  = Get-Item -LiteralPath $RomPath
$bytes = [System.IO.File]::ReadAllBytes($file.FullName)

Write-Host ('[check] 文件   : {0}' -f $file.FullName)
Write-Host ('[check] 大小   : {0} 字节 ({1:N1} KB)' -f $bytes.Length, ($bytes.Length / 1KB))

if ($bytes.Length -lt 0xC0) {
    Write-Host '[check] 失败：文件太小，连 ROM 头都不完整。'
    exit 1
}

$problems = @()
$warnings = @()

# ---------------------------------------------------------------- 固定标记字节
$fixed = $bytes[0xB2]
if ($fixed -eq 0x96) {
    Write-Host '[check] 0xB2 固定字节 : 0x96  OK'
} else {
    $problems += ('0xB2 应该是 0x96，实际是 0x{0:X2}' -f $fixed)
}

# ---------------------------------------------------------------- 头部校验和
$sum = 0
for ($i = 0xA0; $i -le 0xBC; $i++) { $sum += $bytes[$i] }
$expected = (-(0x19 + $sum)) -band 0xFF
$actual   = $bytes[0xBD]

if ($expected -eq $actual) {
    Write-Host ('[check] 头部校验和   : 0x{0:X2}  OK' -f $actual)
} else {
    $problems += ('头部校验和应为 0x{0:X2}，实际是 0x{1:X2}（gbafix 没跑或没生效）' -f $expected, $actual)
}

# ---------------------------------------------------------------- 游戏标题
$titleBytes = $bytes[0xA0..0xAB]
$title = -join ($titleBytes | ForEach-Object {
    if ($_ -ge 32 -and $_ -le 126) { [char]$_ } else { '?' }
})
if ($title -match '^[ -~]{12}$') {
    Write-Host ('[check] 游戏标题     : "{0}"  OK' -f $title.Trim())
} else {
    $warnings += ('标题字段含非可见字符："' + $title + '"（不影响运行，但实机菜单里会显示乱码）')
}

# ---------------------------------------------------------------- 游戏代码 / 厂商
$gameCode = -join ($bytes[0xAC..0xAF] | ForEach-Object { [char]$_ })
$maker    = -join ($bytes[0xB0..0xB1] | ForEach-Object { [char]$_ })
Write-Host ('[check] 游戏代码     : {0}   厂商代码: {1}' -f $gameCode, $maker)

# ---------------------------------------------------------------- 入口指令
$entry = ('0x{0:X2}{1:X2}{2:X2}{3:X2}' -f $bytes[0], $bytes[1], $bytes[2], $bytes[3])
Write-Host ('[check] 入口指令     : {0}' -f $entry)
if ($bytes[3] -ne 0xEA) {
    $warnings += ('入口不是 ARM 分支指令（第 4 字节应为 0xEA，实际 0x{0:X2}）' -f $bytes[3])
}

# ---------------------------------------------------------------- 任天堂 Logo
# 完整的 156 字节（0x04~0x9F）。出处：devkitPro gbafix 的 good_header 数据。
# 注意：早期网上流传的版本在第 85 字节之后有出入，这里用的是权威数据。
$logo = @(
    0x24,0xFF,0xAE,0x51,0x69,0x9A,0xA2,0x21,0x3D,0x84,0x82,0x0A,0x84,0xE4,0x09,0xAD,
    0x11,0x24,0x8B,0x98,0xC0,0x81,0x7F,0x21,0xA3,0x52,0xBE,0x19,0x93,0x09,0xCE,0x20,
    0x10,0x46,0x4A,0x4A,0xF8,0x27,0x31,0xEC,0x58,0xC7,0xE8,0x33,0x82,0xE3,0xCE,0xBF,
    0x85,0xF4,0xDF,0x94,0xCE,0x4B,0x09,0xC1,0x94,0x56,0x8A,0xC0,0x13,0x72,0xA7,0xFC,
    0x9F,0x84,0x4D,0x73,0xA3,0xCA,0x9A,0x61,0x58,0x97,0xA3,0x27,0xFC,0x03,0x98,0x76,
    0x23,0x1D,0xC7,0x61,0x03,0x04,0xAE,0x56,0xBF,0x38,0x84,0x00,0x40,0xA7,0x0E,0xFD,
    0xFF,0x52,0xFE,0x03,0x6F,0x95,0x30,0xF1,0x97,0xFB,0xC0,0x85,0x60,0xD6,0x80,0x25,
    0xA9,0x63,0xBE,0x03,0x01,0x4E,0x38,0xE2,0xF9,0xA2,0x34,0xFF,0xBB,0x3E,0x03,0x44,
    0x78,0x00,0x90,0xCB,0x88,0x11,0x3A,0x94,0x65,0xC0,0x7C,0x63,0x87,0xF0,0x3C,0xAF,
    0xD6,0x25,0xE4,0x8B,0x38,0x0A,0xAC,0x72,0x21,0xD4,0xF8,0x07
)
$logoMatch = $true
for ($i = 0; $i -lt $logo.Count; $i++) {
    if ($bytes[0x04 + $i] -ne $logo[$i]) { $logoMatch = $false; break }
}
if ($logoMatch) {
    Write-Host ('[check] 任天堂 Logo   : 匹配  OK（{0} 字节全部一致，实机 BIOS 会放行）' -f $logo.Count)
} else {
    $warnings += '任天堂 Logo 与标准值不一致：实机上会白屏，模拟器通常仍可运行'
}

# ---------------------------------------------------------------- 结论
Write-Host ''
if ($warnings.Count -gt 0) {
    foreach ($w in $warnings) { Write-Host ('[check] 警告：{0}' -f $w) }
}

if ($problems.Count -gt 0) {
    foreach ($p in $problems) { Write-Host ('[check] 失败：{0}' -f $p) }
    Write-Host '[check] 结论：ROM 头不合法。'
    exit 1
}

Write-Host '[check] 结论：ROM 头合法，可以加载到模拟器/烧录卡。'
exit 0
