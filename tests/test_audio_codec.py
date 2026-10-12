#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频转码：任意格式 → GBA 的 8 位 PCM

守护的东西：
  · 转码器认得出 OGG/MP3/FLAC（而不是像以前那样只认 WAV）
  · 转出来的**体积对得上**（这是容量决策的依据，不能悄悄变）
  · 缓存真的生效（导出时不重复解码 —— 1488 条语音差几十秒）
  · 解码能力缺失时，报错信息里**带着该跑的命令**（而不是让人猜）
  · 编译器的音频关卡不再写死 .wav

【为什么这些断言值得写】
"能不能放语音"是这个项目最硬的约束 ✗
如果哪天转码器的采样率或位深被改动，容量账就全错了 ✗
而那种改动是**静默**的（程序不会报错，只是 ROM 变大或变小）✓
所以把"每秒占多少字节"钉在测试里 ✓
"""
import os
import sys
import wave
import struct
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

TMP = os.path.join(ROOT, '.tmp', 'audio-codec-test')

# 用户素材里的一条真实语音（存在才测 OGG 相关的部分）
SAMPLE_OGG = r"D:\游戏解包\Nightmare×sisters～淫狱的献祭～\音频\语音\SET0001.ogg"


def _wav(path, seconds=1.0, rate=11025):
    """造一个测试用 WAV（441Hz 正弦，避开静音触发的归一化特例）"""
    n = int(seconds * rate)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b''.join(struct.pack('<h', int(12000 * ((i * 7) % 100 - 50) / 50))
                          for i in range(n))
        w.writeframes(frames)


def test_gba_rates_and_sizes():
    """每秒占多少字节必须钉死 —— 这是容量决策的依据"""
    import audio_codec as AC
    assert AC.DEFAULT_RATE == 11025, '默认采样率变了？容量账要重算'
    # 8 位单声道 = 每秒 采样率 个字节
    data = AC.to_s8([0.0] * 1000)
    assert len(data) == 1000, '8 位单声道：1 样本 = 1 字节'
    assert all(-128 <= (b if b < 128 else b - 256) <= 127 for b in data), '超出 8 位有符号范围'


def test_wav_always_works():
    """WAV 必须**永远**能读（内置 wave 后端，不依赖任何第三方库）"""
    import audio_codec as AC
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, 'sine.wav')
    _wav(p, 1.0)
    assert AC.can_decode(p), 'WAV 应该永远可读'
    vals, rate = AC.load_any(p)
    assert rate == 11025 and len(vals) > 10000, '读出来不对：%d 样本 @ %d' % (len(vals), rate)
    data, r, dur, note = AC.convert(p, 11025, use_cache=False)
    assert abs(dur - 1.0) < 0.05, '一秒的 WAV 转出来应该是 1 秒，实际 %.2f' % dur
    assert abs(len(data) - 11025) < 200, '应该约 11025 字节，实际 %d' % len(data)


def test_cache_avoids_redecoding():
    """缓存要真的生效 —— 导出 1488 条语音时这就是几十秒的差别"""
    import audio_codec as AC
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, 'cache.wav')
    _wav(p, 0.3)
    d1, _, _, note1 = AC.convert(p, 11025, use_cache=True)
    d2, _, _, note2 = AC.convert(p, 11025, use_cache=True)
    assert d1 == d2, '缓存前后数据必须一致'
    assert '缓存' in (note2 or ''), '第二次应该是缓存命中，实际说明=%r' % note2
    # 源文件一变，缓存必须失效（否则改了素材还听老的）
    _wav(p, 0.4)
    d3, _, _, note3 = AC.convert(p, 11025, use_cache=True)
    assert len(d3) > len(d1), '源文件改长之后缓存应该失效'


def test_ogg_is_accepted_when_decoder_present():
    """有解码器时 OGG 必须能转；没有时提示里要带"该跑哪条命令"

    这条测试守的是用户实际会遇到的两种状态 —— 而不是断言"一定能解 OGG"
    （换台没装解码库的机器，这条也要能通过，只是走另一个分支）
    """
    import audio_codec as AC
    if not os.path.isfile(SAMPLE_OGG):
        print('     （没有样本 OGG，跳过）')
        return
    b = AC.backend()
    if not AC.can_decode(SAMPLE_OGG):
        h = AC.hint()
        assert 'setup-audio-codec' in h, '解不了 OGG 时，提示里要写清楚跑哪条命令：%r' % h
        print('     （后端 %s 解不了 OGG，提示信息正确）' % b)
        return
    data, rate, dur, note = AC.convert(SAMPLE_OGG, 11025, use_cache=False)
    # 8 位单声道：字节数 ≈ 秒数 × 采样率
    assert abs(len(data) - dur * rate) < rate * 0.1, \
        '体积和时长对不上：%d 字节 / %.2f 秒' % (len(data), dur)
    assert 3.0 < dur < 12.0, '这条样本语音大约 5.6 秒，实际 %.2f' % dur
    print('     后端 %s：%.2f 秒 → %d 字节（%.1f KB/秒）'
          % (b, dur, len(data), rate / 1024.0))


def test_compiler_accepts_non_wav():
    """编译器的音频关卡不能再写死 .wav

    注意：**只看代码行，不看注释** ✗
    （第一版就是因为匹配到了注释里那句"以前这里写死 ext != '.wav'"而误报 ✗
      —— 断言写得太粗，会把"说明历史"当成"又犯错了"）
    """
    src = open(os.path.join(ROOT, 'gbastudio', 'core', 'compiler.py'),
               encoding='utf-8').read()
    code = [ln.split('#')[0] for ln in src.splitlines()]
    bad = [ln.strip() for ln in code if "!= '.wav'" in ln]
    assert not bad, \
        "编译器的音频收集又写死 .wav 了 —— 那样 OGG 素材会被静默跳过：%s" % bad
    assert 'can_decode' in src, '编译器应该问转码器"这个格式能不能读"'


def main():
    tests = [
        ('采样率与体积', test_gba_rates_and_sizes),
        ('WAV 永远可读', test_wav_always_works),
        ('缓存生效且会失效', test_cache_avoids_redecoding),
        ('OGG 可转/提示明确', test_ogg_is_accepted_when_decoder_present),
        ('编译器不再写死 WAV', test_compiler_accepts_non_wav),
    ]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print('    %-22s 通过' % name)
        except AssertionError as e:
            print('    %-22s 失败：%s' % (name, e))
            bad += 1
        except Exception as e:                          # noqa: BLE001
            print('    %-22s 出错：%s: %s' % (name, type(e).__name__, e))
            bad += 1
    print()
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 音频转码：体积账、缓存、OGG、编译器关卡都对得上')
    return 0


if __name__ == '__main__':
    sys.exit(main())
