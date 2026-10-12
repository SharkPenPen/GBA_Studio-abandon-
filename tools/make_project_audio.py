#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_project_audio.py —— 项目音频 → GBA 能播的 8 位 PCM（P6）

GBA 的 Direct Sound 要的是：**8 位有符号、单声道、固定采样率**的裸 PCM。
这个工具把 WAV 转成那个格式，并生成索引表。

为什么要压缩到 8 位 / 11kHz：
    8bit 11kHz ≈ **11 KB/秒**。一句话 3 秒 = 33 KB，一首 2 分钟 BGM = 1.3 MB。
    卡带最大 32 MB，所以采样率是"音质 vs 容量"的直接取舍。
    本工具默认 11025Hz，可用 --rate 调（支持的档位见 RATES）。

OGG/MP3 怎么办：Python 标准库解不了这两种格式。先用别的工具转成 WAV 再导入，
（或者以后接 ffmpeg）。这里**明确报错**，不做"静默跳过"。

生成的表：
    const SndClip snd_clips[] = { { data, len, rate }, … };
    CMD_VOICE/CMD_BGM/CMD_SE 的编号就是这张表的下标。
"""
import argparse
import json
import os
import struct
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GBA 定时器能精确产生的采样率（16.777216 MHz / 2^n / 整数）
RATES = [5734, 7884, 10512, 12604, 13379, 15768, 18157, 21024, 22050, 26758,
         31536, 36314, 40137, 42048, 44100]
DEFAULT_RATE = 11025      # 不在上表里也没关系：定时器取最接近的整数值

# **自动转码**：OGG/MP3/FLAC 现在也能直接用了 ✗
# 解码交给 tools/audio_codec.py（多后端：soundfile / ffmpeg / 内置 wave）
# 它还会按源文件的时间戳做缓存 —— 导出时不重复解码（1488 条语音差几十秒）
import audio_codec as AC


def log(m):
    print('[audio] ' + m)




def read_wav(path):
    """读 WAV，返回 (样本列表[-1..1], 原采样率)"""
    with wave.open(path, 'rb') as w:
        nch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 1:                       # 8 位 WAV 是无符号的
        vals = [(b - 128) / 128.0 for b in raw]
    elif width == 2:
        cnt = len(raw) // 2
        vals = [v / 32768.0 for v in struct.unpack('<%dh' % cnt, raw[:cnt * 2])]
    elif width == 3:
        cnt = len(raw) // 3
        vals = []
        for i in range(cnt):
            b = raw[i * 3:i * 3 + 3]
            v = int.from_bytes(b, 'little', signed=True)
            vals.append(v / 8388608.0)
    else:
        raise RuntimeError('不支持的位深：%d 位' % (width * 8))
    if nch > 1:                          # 多声道降混成单声道
        vals = [sum(vals[i:i + nch]) / nch for i in range(0, len(vals) - nch + 1, nch)]
    return vals, rate


def resample(vals, src_rate, dst_rate):
    """线性重采样（够用；音质损失远小于 8bit 量化本身）"""
    if src_rate == dst_rate or not vals:
        return vals
    ratio = dst_rate / src_rate
    n = max(1, int(len(vals) * ratio))
    out = []
    for i in range(n):
        x = i / ratio
        i0 = int(x)
        i1 = min(i0 + 1, len(vals) - 1)
        t = x - i0
        out.append(vals[i0] * (1 - t) + vals[i1] * t)
    return out


def normalize(vals, target=0.89):
    peak = max((abs(v) for v in vals), default=0.0)
    if peak < 1e-6:
        return vals, 0.0
    k = target / peak
    return [v * k for v in vals], peak


def to_s8(vals):
    """转 8 位有符号"""
    out = bytearray()
    for v in vals:
        q = int(round(v * 127.0))
        out.append(max(-128, min(127, q)) & 0xFF)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=os.path.join(ROOT, 'scenario', 'assets.json'))
    ap.add_argument('--assets-dir', default=os.path.join(ROOT, 'source', 'assets'))
    ap.add_argument('--include-dir', default=os.path.join(ROOT, 'include'))
    ap.add_argument('--rate', type=int, default=DEFAULT_RATE)
    ap.add_argument('--no-normalize', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    global log
    if a.quiet:
        log = lambda m: None

    if not os.path.isfile(a.manifest):
        log('没有清单文件，跳过音频')
        return 0
    with open(a.manifest, encoding='utf-8') as f:
        mani = json.load(f)
    audios = mani.get('audio', [])
    if not audios:
        log('清单里没有音频')
        # 仍然生成空表，否则引擎链接会失败
        write_outputs(a, [], 0)
        return 0

    os.makedirs(a.assets_dir, exist_ok=True)
    if a.rate not in RATES:
        log('提示：%d Hz 不在 GBA 常用档位里，定时器会用最接近的整数值（音高会略偏）'
            % a.rate)

    entries, total, skipped = [], 0, []
    for i, e in enumerate(audios):
        src = e['src']
        if not os.path.isfile(src):
            skipped.append('%s（文件不存在）' % e.get('name', src))
            continue
        # **交给转码器**：OGG/MP3/FLAC/WAV 都能读 ✗
        # 以前这里写死"只认 WAV"，用户得先自己转 —— 现在导出时自动转 ✓
        if not AC.can_decode(src):
            skipped.append('%s（%s 格式读不了。%s）'
                           % (e.get('name', src),
                              os.path.splitext(src)[1].lower() or '?', AC.hint()))
            continue
        try:
            data, rate, dur, note = AC.convert(src, a.rate,
                                               normalize_audio=not a.no_normalize)
        except Exception as ex:
            skipped.append('%s（转码失败：%s）' % (e.get('name', src), ex))
            continue
        name = 'aud_%d' % i
        with open(os.path.join(a.assets_dir, name + '.bin'), 'wb') as f:
            f.write(data)
        total += len(data)
        entries.append({'sym': name, 'len': len(data), 'rate': rate,
                        'kind': e.get('kind', ''), 'name': e.get('name', '')})
        log('%-8s #%d  %-22s %5.2f 秒  %6d 字节  %s'
            % (e.get('kind', 'audio'), i, e.get('name', ''), dur,
               len(data), note or ''))

    for s in skipped:
        log('⚠ 跳过 %s' % s)
    write_outputs(a, entries, total)
    log('音频 %d 条，共 %.1f KB（%d Hz / 8bit 单声道）'
        % (len(entries), total / 1024, a.rate))
    if total > 8 * 1024 * 1024:
        log('⚠ 音频 %.1f MB，接近卡带容量上限，建议降采样率' % (total / 1024 / 1024))
    return 0


def write_outputs(a, entries, total):
    # **先建目录** ✗ 以前直接写文件，目录不存在就 FileNotFoundError ✗
    #（实测踩过：--include-dir 指到还没建的目录）
    os.makedirs(a.assets_dir, exist_ok=True)
    os.makedirs(a.include_dir, exist_ok=True)
    """
    生成：snd_data.s（incbin 数据）+ snd_data.h（声明）+ snd_table.c（**表定义**）

    踩过：一开始只生成了声明没生成定义，编译能过、**链接报
    "undefined reference to snd_clips"**。表和计数必须有人定义。
    没有音频时也要生成一张空表 —— 引擎是无条件引用 snd_clips_count 的。
    """
    with open(os.path.join(a.assets_dir, 'snd_data.s'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('/* 由 tools/make_project_audio.py 自动生成，请勿手工修改 */\n')
        f.write('    .section .rodata\n\n')
        for e in entries:
            f.write('    .global snd_%s\n    .align 2\nsnd_%s:\n    .incbin "%s.bin"\n\n'
                    % (e['sym'], e['sym'], e['sym']))

    hdr = os.path.join(a.include_dir, 'snd_data.h')
    with open(hdr, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_project_audio.py 自动生成，请勿手工修改 */\n')
        f.write('#ifndef SND_DATA_H\n#define SND_DATA_H\n\n#include <tonc.h>\n\n')
        f.write('/* 一段音频：8 位有符号 PCM 裸数据。\n'
                ' * loop 只是"这条素材的建议值"，实际循环与否由 CMD_BGM 的 b 字段决定。 */\n')
        f.write('typedef struct {\n    const s8 *data;\n    u32 len;\n    u16 rate;\n'
                '    u16 loop;\n} SndClip;\n\n')
        f.write('extern const SndClip snd_clips[];\n')
        f.write('extern const int snd_clips_count;\n\n')
        for e in entries:
            f.write('extern const s8 snd_%s[];\n' % e['sym'])
        f.write('\n#endif /* SND_DATA_H */\n')

    # ---- 表定义（必须有，否则链接不过）----
    tbl = os.path.join(a.assets_dir, 'snd_table.c')
    with open(tbl, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_project_audio.py 自动生成，请勿手工修改 */\n')
        f.write('#include "snd_data.h"\n\n')
        if entries:
            for e in entries:
                f.write('extern const s8 snd_%s[];\n' % e['sym'])
            f.write('\nconst SndClip snd_clips[] = {\n')
            for e in entries:
                loop = 1 if e['kind'] == 'bgm' else 0
                f.write('    { snd_%s, %d, %d, %d },   /* %s %s */\n'
                        % (e['sym'], e['len'], e['rate'], loop, e['kind'], e['name']))
            f.write('};\nconst int snd_clips_count = %d;\n' % len(entries))
        else:
            f.write('/* 本项目没有音频：给一张空表，引擎可以无条件引用 */\n')
            f.write('const SndClip snd_clips[1] = { { 0, 0, 0, 0 } };\n')
            f.write('const int snd_clips_count = 0;\n')
    log('生成 snd_data.s / snd_data.h / snd_table.c')


if __name__ == '__main__':
    sys.exit(main())
