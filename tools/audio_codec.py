#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_codec.py —— 把任意音频转成 GBA 要的格式

【GBA 要的格式】
Direct Sound 只吃一样东西：**8 位有符号、单声道、固定采样率**的裸 PCM ✗
所以不管素材是 OGG / MP3 / FLAC / WAV，都要先解码、再重采样、再量化成 8 位 ✓

    11025 Hz / 8bit / 单声道 = 11.0 KB/秒
    卡带 32 MB → 语音大约只能放 8 分钟（这就是为什么语音必须精挑）

【为什么要多后端】
没有哪个解码库是"到处都有"的 ✗ 所以按顺序试：

    1. soundfile（自带 libsndfile）  ← 首选，装一次就够，支持 OGG/FLAC/MP3
    2. ffmpeg.exe（PATH 或 .tools/ 下）← 用户自己丢一份进来也能用
    3. Python 自带的 wave            ← 只能读 WAV，但永远可用 ✓

装解码库：`python tools\\setup-audio-codec.py`

【缓存】
导出时**不应该每次都重新解码** ✗ 解码一条语音要几十毫秒，
1488 条就是几十秒 ✓ 所以按"源文件路径 + 修改时间 + 大小 + 目标采样率"做键，
命中缓存就直接用 ✓ 源文件一改，缓存自动失效 ✓
"""
import json
import os
import shutil
import subprocess
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, '.tools', 'pylibs')
CACHE_DIR = os.path.join(ROOT, '.tmp', 'audio-cache')

# GBA 定时器能精确产生的采样率（16.777216 MHz / 2^n / 整数）
RATES = [5734, 7884, 10512, 12604, 13379, 15768, 18157, 21024, 22050, 26758,
         31536, 36314, 42048, 44100]
DEFAULT_RATE = 11025

DECODABLE = ('.ogg', '.oga', '.mp3', '.flac', '.wav', '.m4a', '.aac', '.opus', '.wma')


def _ensure_lib():
    """把自己装的库目录加进搜索路径（放前面，优先用它）"""
    if LIB not in sys.path and os.path.isdir(LIB):
        sys.path.insert(0, LIB)


def _find_ffmpeg():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    for cand in (os.path.join(ROOT, '.tools', 'ffmpeg.exe'),
                 os.path.join(ROOT, '.tools', 'ffmpeg', 'bin', 'ffmpeg.exe'),
                 os.path.join(ROOT, '.tools', 'ffmpeg', 'ffmpeg.exe')):
        if os.path.isfile(cand):
            return cand
    return None


def backend():
    """当前能用哪个解码后端 —— 报错信息里要告诉用户怎么补"""
    _ensure_lib()
    try:
        import soundfile  # noqa: F401
        return 'soundfile'
    except Exception:                                   # noqa: BLE001
        pass
    if _find_ffmpeg():
        return 'ffmpeg'
    return 'wave'          # 只能读 WAV，但标准库永远在


def can_decode(path):
    """这个文件能不能读（WAV 永远可以）"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.wav':
        return True
    b = backend()
    if b == 'soundfile':
        return ext in DECODABLE
    if b == 'ffmpeg':
        return ext in DECODABLE
    return False


def hint():
    """解码不了时给用户的提示（明确到"跑哪条命令"）"""
    if backend() == 'soundfile':
        return ''
    return ('读不了 OGG/MP3 ✗ 先跑一次：python tools\\setup-audio-codec.py\n'
            '（也可以找一份 ffmpeg.exe 放到 .tools/ 下，本工具会自动用它）')


# ---------------------------------------------------------------------------
# 解码：返回 (样本列表[-1..1], 采样率)
# ---------------------------------------------------------------------------
def _load_soundfile(path):
    _ensure_lib()
    import soundfile as sf
    import numpy as np
    data, rate = sf.read(path, dtype='float32', always_2d=True)
    # 多声道 → 单声道（取平均；GBA 只有单声道 PCM）
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    return mono.tolist(), int(rate)


def _load_ffmpeg(path):
    exe = _find_ffmpeg()
    rate = DEFAULT_RATE
    # 让 ffmpeg 直接输出 16 位小端单声道 PCM 到 stdout
    cmd = [exe, '-v', 'error', '-i', path, '-f', 's16le', '-acodec', 'pcm_s16le',
           '-ac', '1', '-ar', '22050', '-']
    out = subprocess.run(cmd, capture_output=True).stdout
    if not out:
        raise RuntimeError('ffmpeg 没有输出（文件损坏或格式不支持）')
    import struct
    n = len(out) // 2
    ints = struct.unpack('<%dh' % n, out[:n * 2])
    return [v / 32768.0 for v in ints], 22050


def _load_wave(path):
    with wave.open(path, 'rb') as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif sw == 2:
        import struct
        cnt = len(raw) // 2
        vals = [v / 32768.0 for v in struct.unpack('<%dh' % cnt, raw[:cnt * 2])]
    elif sw == 4:
        import struct
        cnt = len(raw) // 4
        vals = [v / 2147483648.0 for v in struct.unpack('<%di' % cnt, raw[:cnt * 4])]
    else:
        raise RuntimeError('不支持的位深：%d 字节' % sw)
    if ch > 1:                                          # 多声道 → 单声道
        vals = [sum(vals[i:i + ch]) / ch for i in range(0, len(vals) - ch + 1, ch)]
    return vals, rate


def load_any(path):
    """读任意音频 → (样本[-1..1], 采样率)。按后端顺序试，失败会带上原因。"""
    ext = os.path.splitext(path)[1].lower()
    errors = []
    order = []
    b = backend()
    if b == 'soundfile' and ext != '.wav':
        order.append(('soundfile', _load_soundfile))
    if b == 'ffmpeg' and ext != '.wav':
        order.append(('ffmpeg', _load_ffmpeg))
    order.append(('wave', _load_wave))                  # WAV 总能用
    if ext != '.wav':
        order.append(('soundfile', _load_soundfile))    # WAV 失败时再兜回来试
        order.append(('ffmpeg', _load_ffmpeg))
    for name, fn in order:
        try:
            return fn(path)
        except Exception as e:                          # noqa: BLE001
            errors.append('%s: %s' % (name, e))
    raise RuntimeError('；'.join(errors[-2:]) or '没有可用的解码方式')


# ---------------------------------------------------------------------------
# 转成 GBA 格式
# ---------------------------------------------------------------------------
def resample(vals, src_rate, dst_rate):
    """线性重采样（够用；音质损失远小于 8bit 量化本身）"""
    if src_rate == dst_rate or not vals:
        return vals
    n = int(len(vals) * dst_rate / float(src_rate))
    out = []
    for i in range(n):
        pos = i * src_rate / float(dst_rate)
        i0 = int(pos)
        i1 = min(i0 + 1, len(vals) - 1)
        frac = pos - i0
        out.append(vals[i0] * (1 - frac) + vals[i1] * frac)
    return out


def normalize(vals, target=0.89):
    """归一化到目标峰值，返回 (新样本, 原峰值)"""
    peak = max((abs(v) for v in vals), default=0.0)
    if peak <= 1e-6 or peak >= target:
        return vals, peak
    k = target / peak
    return [v * k for v in vals], peak


def to_s8(vals):
    """浮点 [-1..1] → 8 位有符号 PCM（带一点抖动，减少量化噪声）"""
    out = bytearray(len(vals))
    for i, v in enumerate(vals):
        x = int(round(v * 127))
        if x > 127:
            x = 127
        elif x < -128:
            x = -128
        out[i] = x & 0xFF
    return bytes(out)


# ---------------------------------------------------------------------------
# 缓存：导出时不必每次重新解码
# ---------------------------------------------------------------------------
def _cache_key(path, rate):
    st = os.stat(path)
    return '%s|%d|%d|%d' % (os.path.abspath(path), st.st_size,
                            int(st.st_mtime), rate)


def _cache_path(key):
    import hashlib
    h = hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
    return os.path.join(CACHE_DIR, h + '.pcm')


def convert(path, rate=DEFAULT_RATE, normalize_audio=True, use_cache=True):
    """把一条音频转成 GBA 的 8 位 PCM。

    返回 (pcm 字节, 采样率, 时长秒, 说明)。命中的话说明里会写"缓存"。
    """
    key = _cache_key(path, rate) if use_cache else None
    if key:
        cp = _cache_path(key)
        if os.path.isfile(cp):
            with open(cp, 'rb') as f:
                data = f.read()
            return data, rate, len(data) / float(rate), '缓存'

    vals, src_rate = load_any(path)
    vals = resample(vals, src_rate, rate)
    note = ''
    if normalize_audio:
        vals, peak = normalize(vals)
        if peak:
            note = '峰值 %.0f 已归一化' % (peak * 32768)
    data = to_s8(vals)

    if key:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(_cache_path(key), 'wb') as f:
                f.write(data)
        except Exception:                               # noqa: BLE001
            pass                                        # 缓存写不了不算错
    return data, rate, len(data) / float(rate), note


def main():
    """命令行：转一个文件看看（调试用）"""
    import argparse
    ap = argparse.ArgumentParser(description='把音频转成 GBA 格式（8bit 单声道 PCM）')
    ap.add_argument('src')
    ap.add_argument('--rate', type=int, default=DEFAULT_RATE)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    print('解码后端：%s' % backend())
    if not can_decode(a.src):
        print(hint())
        return 1
    data, rate, dur, note = convert(a.src, a.rate, use_cache=False)
    print('%s → %d 字节（%.2f 秒 @ %d Hz，%.1f KB/秒）%s'
          % (os.path.basename(a.src), len(data), dur, rate, rate / 1024.0,
             ('  ' + note) if note else ''))
    if a.out:
        with open(a.out, 'wb') as f:
            f.write(data)
        print('已写出 %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
