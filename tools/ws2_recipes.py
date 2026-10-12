#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws2_recipes.py —— 从 .ws2 提取"每一句的图层合成配方"

【和 ws2_scenes.py 的分工】
    ws2_scenes.py   提取：这一句用哪张图、放哪条语音、谁说的   → 挂到时间轴上
    ws2_recipes.py  提取：这一句的**图层叠加关系**（底图+立绘+蒙版+位置）
                          → 交给 compose_scenes.py 合成成一张 240x160

【为什么单独一个工具】
这段逻辑原来是**内联在会话里跑的临时脚本** ✗ 清掉 .tmp 就没了 ✓
而它是整条流水线的一环 ✓ 没有它就没法重建合成图 ✓
——**一次性脚本必须落成工具，否则流水线不可复现** ✓

【配方是什么】
一个 JSON 数组：[底图文件名, [x, y], 立绘[文件名,x,y] 或 null, 蒙版文件名 或 null]
键是**日文原文的指纹**（和 ws2_scenes.py 用同一套算法 ✓）
——不能按消息号 ✗ TSV 是每场景从 0 开始 ✓ ws2 是全局编号 ✓ 对不上 ✓

用法：
    python tools\\ws2_recipes.py --rio "<解包>\\剧本\\Rio" --out .tmp\\scene_recipes.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

TOOLS_3DS = r'D:\GitHud\3DSStudio\tools'
DEFAULT_RIO = r'D:\游戏解包\Nightmare×sisters～淫狱的献祭～\剧本\Rio'


def log(m):
    print('[recipe] ' + m)


def main():
    ap = argparse.ArgumentParser(description='从 .ws2 提取图层合成配方')
    ap.add_argument('--rio', default=DEFAULT_RIO, help='.ws2 所在目录')
    ap.add_argument('--out', default=os.path.join(ROOT, '.tmp', 'scene_recipes.json'))
    a = ap.parse_args()

    if not os.path.isdir(a.rio):
        log('✗ 找不到 .ws2 目录：%s' % a.rio)
        return 1
    if TOOLS_3DS not in sys.path:
        sys.path.insert(0, TOOLS_3DS)
    import ws2_disasm as W
    from ws2_scenes import text_key

    table = W.parse_tables()
    log('操作码参数表：%d 条指令' % len(table))

    def scan(path):
        data = bytes(W.rot_right2(b) for b in open(path, 'rb').read())
        segs, pos, tail = W.parse_script(data, table, 'shift_jis')
        if not segs:
            return None
        layers = {}          # 层名 → [文件名, x, y]
        mask = None
        out = {}
        for it in segs[0][0]:
            if not (isinstance(it, (list, tuple)) and len(it) == 2):
                continue
            op, args = it
            if not isinstance(args, list) or not args:
                continue
            if op == 51 and len(args) >= 2:              # 设图层图片
                layers[str(args[0])] = [str(args[1]), 0.0, 0.0]
            elif op == 70 and len(args) >= 6:            # 图层位置
                ln = str(args[0])
                if ln in layers:
                    try:
                        layers[ln][1] = float(args[3])
                        layers[ln][2] = float(args[4])
                    except Exception:                   # noqa: BLE001
                        pass
            elif op == 102:                              # 蒙版
                mask = str(args[0])
            elif op == 20 and isinstance(args[0], int) and len(args) >= 3:
                # 这一刻的配方 = 底图 + 立绘 + 蒙版 + 位置
                base = None
                basepos = (0, 0)
                spr = None
                for ln in sorted(layers):
                    fn, x, y = layers[ln]
                    if ln.lower().startswith('st'):      # st# = 立绘图层
                        spr = (fn, x, y)
                    elif ln.lower().startswith(('bg', 'ev', 'imb')):
                        base = fn
                        basepos = (x, y)
                out[text_key(args[2])] = json.dumps(
                    [base, basepos, spr, mask], ensure_ascii=False)
        return out

    per_scene = {}
    for f in sorted(os.listdir(a.rio)):
        if not f.lower().endswith('.ws2'):
            continue
        try:
            r = scan(os.path.join(a.rio, f))
        except Exception:                               # noqa: BLE001
            continue
        if r:
            per_scene[os.path.splitext(f)[0]] = r

    keys = set()
    for v in per_scene.values():
        keys |= set(v.values())
    log('场景 %d 个；不同配方 %d 种 ≈ %.1f MB（每张 240x160 16bpp = 75 KB）'
        % (len(per_scene), len(keys), len(keys) * 75 / 1024.0))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(per_scene, fp, ensure_ascii=False)
    log('已写出 %s' % a.out)
    log('接下来：python tools\\compose_scenes.py --recipes "%s" --src "<解包目录>" --out "<工程>\\assets\\bg"'
        % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
