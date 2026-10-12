#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_audio_data.py —— 音频数据是否完整、正确地进了 ROM

这是 P6 的**静态验证**：我听不见声音，但能证明"数据对了"。
（运行时的验证见 tools\\diag3.py：连 mGBA 读音频硬件寄存器。）

检查三件事：
  1. 转换产物（aud_0.bin）在 ROM 里**逐字节**找得到
  2. 数据不是静音（峰值 / RMS）
  3. 时长和源 WAV 一致（重采样没把长度搞错）
"""
import os
import struct
import sys
import wave

# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ROM = os.path.join(ROOT, 'gba_ai.gba')
BIN = os.path.join(ROOT, 'source', 'assets', 'aud_0.bin')       # 第一条：BGM
SRC = os.path.join(ROOT, 'assets_src', 'test', 'test_bgm.wav')

for p in (ROM, BIN):
    if not os.path.isfile(p):
        print('  ❌ 缺文件：%s（先跑 tests\\test_export.py 出 ROM）' % p)
        sys.exit(1)

rom = open(ROM, 'rb').read()
data = open(BIN, 'rb').read()
print('  转换产物 aud_0.bin: %d 字节' % len(data))

i = rom.find(data)
print('  在 ROM 里的位置: %s' % ('0x%X' % i if i >= 0 else '没找到 ✗'))
assert i >= 0, '音频数据没进 ROM'
print('  ✅ 音频数据完整进了 ROM（逐字节匹配）')

s = struct.unpack('<%db' % len(data), data)
peak = max(abs(v) for v in s)
rms = (sum(v * v for v in s) / len(s)) ** 0.5
print('  峰值 %d / 127，RMS %.1f（不是静音）' % (peak, rms))
assert peak > 20 and rms > 3, '数据接近静音，转换可能有问题'

if os.path.isfile(SRC):
    with wave.open(SRC) as w:
        n, rate = w.getnframes(), w.getframerate()
    print('  源 WAV: %.2f 秒 @ %d Hz → 转换后 %.2f 秒 @ 11025 Hz'
          % (n / rate, rate, len(data) / 11025))
    assert abs(n / rate - len(data) / 11025) < 0.05, '时长对不上，重采样有问题'
else:
    print('  （没找到源 WAV，跳过时长比对）')

print()
print('✅ 音频数据验证通过')
