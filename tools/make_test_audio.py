#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_test_audio.py —— 造几个测试音频（验证 P6）

用纯音调而不是真实语音，理由和测试图片一样：**一听就知道对不对**。
    test_voice_1.wav   三声上行短音（模拟"一句台词"）
    test_voice_2.wav   两声下行短音
    test_bgm.wav       8 秒循环旋律（低音铺底 + 简单主旋律）
    test_se.wav        一声短促的"叮"
"""
import argparse
import math
import os
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATE = 22050          # 源文件用 22kHz，转换时再降（留出余量）


def write_wav(path, samples, rate=RATE):
    """写 16 位单声道 WAV"""
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h', max(-32767, min(32767, int(s * 32767))))
                               for s in samples))


def tone(freq, dur, rate=RATE, vol=0.6, fade=0.01):
    """一个带淡入淡出的正弦音，避免爆音（爆音在 GBA 上是"咔"一声，很出戏）"""
    n = int(dur * rate)
    nf = max(1, int(fade * rate))
    out = []
    for i in range(n):
        env = min(1.0, i / nf, (n - i) / nf)
        out.append(vol * env * math.sin(2 * math.pi * freq * i / rate))
    return out


def silence(dur, rate=RATE):
    return [0.0] * int(dur * rate)


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    peak = max(1e-6, max(abs(v) for v in out))
    return [v / peak * 0.85 for v in out]


def voice_1():
    """三声上行：听起来像"一句短台词" """
    return (tone(440, 0.35) + silence(0.06) + tone(554, 0.35) + silence(0.06)
            + tone(659, 0.5))


def voice_2():
    return tone(659, 0.3) + silence(0.05) + tone(494, 0.6)


def bgm():
    """8 秒循环：低音铺底 + 五声音阶主旋律"""
    scale = [262, 294, 330, 392, 440, 392, 330, 294]      # C D E G A 五声
    mel = []
    for k in range(8):
        f = scale[k % len(scale)]
        mel += tone(f, 0.35, vol=0.45)
        mel += tone(f * 2, 0.15, vol=0.15)                # 泛音
    bass = []
    for k in range(8):
        bass += tone(131 if k % 2 == 0 else 165, 0.5, vol=0.5)
        bass += silence(0.0)
    # 对齐长度再混音
    n = max(len(mel), len(bass))
    mel += [0.0] * (n - len(mel))
    bass += [0.0] * (n - len(bass))
    return mix(mel, bass)


def se():
    """短促"叮"：高频 + 快速衰减"""
    n = int(0.18 * RATE)
    out = []
    for i in range(n):
        env = math.exp(-i / (RATE * 0.045))
        out.append(0.7 * env * (math.sin(2 * math.pi * 1319 * i / RATE)
                                + 0.4 * math.sin(2 * math.pi * 2637 * i / RATE)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, 'assets_src', 'test'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name, samples in (('test_voice_1.wav', voice_1()),
                          ('test_voice_2.wav', voice_2()),
                          ('test_bgm.wav', bgm()),
                          ('test_se.wav', se())):
        p = os.path.join(a.out, name)
        write_wav(p, samples)
        print('  %-20s %5.2f 秒  %s' % (name, len(samples) / RATE,
                                        '%.0f KB' % (os.path.getsize(p) / 1024)))


if __name__ == '__main__':
    main()
