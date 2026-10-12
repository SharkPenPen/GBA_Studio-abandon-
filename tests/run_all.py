#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py —— 跑全部回归测试

用法：
    python tests\\run_all.py            跑所有测试
    python tests\\run_all.py -k 预览     只跑名字里有"预览"的
    python tests\\run_all.py -v          打印每个测试的详细输出

测试分三类：
    test_data / test_ui / test_ui_scale / test_tracks / test_ruler / test_inspector
        编辑器逻辑（数据模型、界面结构、界面缩放、时间轴、属性）
    test_voice_link
        台词的语音自动配对（选语音 → 时间轴自动生成对齐的片段）
    test_preview
        P3 验收：预览渲染 + 播放 + 实时刷新
    test_export
        端到端：编译 → 调工具链 → 出 ROM（最慢，约 3~5 秒）
    test_audio_data
        音频数据是否完整进了 ROM
另有独立验收工具（需要先有 mGBA 截图）：
    python tools\\check-preview.py      预览 vs 实机 逐像素对比
    python tools\\diag3.py              连 mGBA 读音频硬件寄存器（需 mGBA -g 在跑）
"""
import argparse
import os
import subprocess
import sys
import time

# **先把 stdout 切到 UTF-8** ✗
# 结论行里有 ✅/❌，而 Windows 中文控制台默认是 GBK ——
# 直接打印会崩：UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'
# （踩过：不带 PYTHONIOENCODING=utf-8 跑一次就复现了）
# 这里自己兜住，用户在任何控制台里跑都不会因为这个报错。
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                     # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ORDER = ['test_data.py', 'test_ui.py', 'test_ui_scale.py', 'test_tracks.py',
         'test_ruler.py', 'test_inspector.py', 'test_voice_link.py', 'test_level.py', 'test_anim.py',
         'test_video_modes.py', 'test_launcher.py',
         'test_audio_codec.py', 'test_script_convert.py',
         # 注意：test_export 必须排在 test_audio_data 之前
         # test_audio_data 读 source/assets/aud_*.bin，那是 test_export 生成的。
         # 以前顺序反着也能过，是因为目录里留着上次的产物；清一次就暴露了。
         'test_layers.py',
         'test_dnd.py',
         'test_preview.py', 'test_export.py', 'test_audio_data.py',
         # 排最后：它会真的跑 build-assets.ps1，改写 source/assets 和 include
         'test_build_scripts.py']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-k', '--filter', default='', help='只跑文件名含该字串的测试')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    files = [f for f in ORDER if os.path.isfile(os.path.join(HERE, f))]
    if a.filter:
        files = [f for f in files if a.filter in f]
    if not files:
        print('没有匹配的测试')
        return 1

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = os.path.join(ROOT, 'gbastudio') + os.pathsep + env.get('PYTHONPATH', '')

    print('跑 %d 个测试…' % len(files))
    print('-' * 52)
    bad = []
    t0 = time.time()
    for f in files:
        t = time.time()
        p = subprocess.run([sys.executable, os.path.join(HERE, f)],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=env, cwd=ROOT)
        out = (p.stdout or '') + (p.stderr or '')
        ok = '✅' in out
        print('  %-20s %s  (%.1f 秒)' % (f, '✅ 通过' if ok else '❌ 失败', time.time() - t))
        if not ok:
            bad.append(f)
            for line in out.strip().splitlines()[-8:]:
                print('      ' + line)
        elif a.verbose:
            for line in out.strip().splitlines():
                print('      ' + line)
    print('-' * 52)
    print('%d 个通过，%d 个失败，共 %.1f 秒'
          % (len(files) - len(bad), len(bad), time.time() - t0))
    if bad:
        print('失败的：%s' % ', '.join(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
