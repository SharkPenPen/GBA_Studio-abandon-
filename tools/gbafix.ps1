#requires -Version 5.1
<#
  gbafix.ps1 —— 修复 GBA ROM 头（用 PowerShell 重写 gbafix 的功能）

  为什么必须修：
    GBA 实机的 BIOS 在开机时会检查 ROM 开头的 192 字节头部：
      * 0x04~0x9F 必须是任天堂 Logo 位图，不匹配就直接白屏；
      * 0xBD 是头部校验和，不对同样拒绝启动。
    链接器脚本（gba_cart.ld / gba_crt0.s）只预留了位置并填 0，
    所以编出来的 .gba 必须经过这一步才能上实机。

  这个脚本做四件事：
    1. 写入 156 字节的任天堂 Logo（必要的硬件兼容数据）；
    2. 写入 0xB2 = 0x96 固定标记，清零 unit/device 字段；
    3. 按 GBATEK 规则计算并写入 0xBD 处的头部校验和；
    4. 可选：写入游戏标题(12 字节)、游戏代码(4 字节)、厂商代码(2 字节)。

  用法：
    .\tools\gbafix.ps1 -RomPath game.gba -Title "MY GAME" -GameCode "GBAI"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $RomPath,

    # 最多 12 个字符，会以 ASCII 写入 ROM 头 0xA0 处
    [string] $Title = '',

    # 4 个字符，例如 "GBAI"
    [string] $GameCode = '',

    # 2 个字符，例如 "01"
    [string] $MakerCode = ''
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $RomPath)) {
    throw ('找不到 ROM 文件：{0}' -f $RomPath)
}

# 任天堂 Logo 位图，156 字节（0x04~0x9F）。
# 出处：devkitPro gbafix 的 good_header 数据；实机 BIOS 逐字节比对这段数据。
$logo = [byte[]]@(
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

function Write-AsciiField {
    param([byte[]] $Buffer, [int] $Offset, [int] $Length, [string] $Value, [string] $FieldName)

    if ($Value.Length -gt $Length) {
        throw ('{0} 最多 {1} 个字符，你给了 {2} 个：" {3}"' -f $FieldName, $Length, $Value.Length, $Value)
    }
    foreach ($ch in $Value.ToCharArray()) {
        $code = [int][char]$ch
        if ($code -lt 0x20 -or $code -gt 0x7E) {
            throw ('{0} 只能用可见 ASCII 字符，" {1}" 不合法' -f $FieldName, $ch)
        }
    }
    for ($i = 0; $i -lt $Length; $i++) {
        $Buffer[$Offset + $i] = if ($i -lt $Value.Length) { [byte][char]$Value[$i] } else { [byte]0 }
    }
}

$bytes = [System.IO.File]::ReadAllBytes($RomPath)
if ($bytes.Length -lt 0xC0) {
    throw ('文件太小（{0} 字节），不像一个 GBA ROM。' -f $bytes.Length)
}
if ($logo.Length -ne 156) {
    throw ('内部错误：Logo 数据应为 156 字节，实际 {0} 字节。' -f $logo.Length)
}

# 1) Logo
[Array]::Copy($logo, 0, $bytes, 0x04, 156)

# 2) 可选文本字段
if ($Title)     { Write-AsciiField -Buffer $bytes -Offset 0xA0 -Length 12 -Value $Title     -FieldName '游戏标题' }
if ($GameCode)  { Write-AsciiField -Buffer $bytes -Offset 0xAC -Length 4  -Value $GameCode  -FieldName '游戏代码' }
if ($MakerCode) { Write-AsciiField -Buffer $bytes -Offset 0xB0 -Length 2  -Value $MakerCode -FieldName '厂商代码' }

# 3) 固定字段
$bytes[0xB2] = 0x96   # 固定标记，BIOS 会检查
$bytes[0xB3] = 0x00   # main unit code
$bytes[0xB4] = 0x00   # device type

# 4) 头部校验和：把 0xA0~0xBC 求和，取补码
$sum = 0
for ($i = 0xA0; $i -le 0xBC; $i++) { $sum += $bytes[$i] }
$checksum = (-(0x19 + $sum)) -band 0xFF
$bytes[0xBD] = [byte]$checksum

# 0xBE~0xBF 是保留的全局校验和字段，必须为 0
$bytes[0xBE] = 0
$bytes[0xBF] = 0

[System.IO.File]::WriteAllBytes($RomPath, $bytes)

$titleShown = -join ($bytes[0xA0..0xAB] | ForEach-Object { if ($_ -ge 32 -and $_ -le 126) { [char]$_ } else { '.' } })
Write-Host ('[gbafix] 已修复 ROM 头：{0}' -f (Split-Path -Leaf $RomPath))
Write-Host ('[gbafix]   标题   : "{0}"' -f $titleShown.TrimEnd('.'))
Write-Host ('[gbafix]   游戏代码: {0}' -f (-join ($bytes[0xAC..0xAF] | ForEach-Object { [char]$_ })))
Write-Host ('[gbafix]   校验和 : 0x{0:X2}' -f $checksum)
exit 0
