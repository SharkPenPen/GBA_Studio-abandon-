#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_project_anim.py —— 把精灵动画编译成引擎认识的 C 表（P9）

输入：工程文件里的 animations（编辑器「精灵」模式编的）
输出：source/assets/anim_data.c / include/anim_data.h

结构（平坦数组，查表就是一次下标）：

    anim_frames[]  所有动画的帧，按顺序排在一起：精灵下标
    anim_durs[]    每帧停多少帧，和上面对齐
    anim_defs[]    每个动画一条：从第几帧开始、共几帧、是否循环

为什么不用结构体数组套结构体数组（可读性更好）：
    GBA 上静态初始化**不能含运行期计算**，嵌套结构要写一大堆花括号，
    错一个就静默错位。平坦数组 + 偏移量最不容易出错，ROM 里也更省。

帧对应的精灵下标从哪来：工程的素材清单里 kind == 'sprite' 的条目，
按顺序编号 —— 和 tools/make_project_assets.py 生成的 gfx_sprites[] 同一套顺序。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_project(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def sprite_index(mani, path):
    """
    素材源路径 → 精灵下标（只数清单里 flat 那一组）。

    顺序必须和 tools/make_project_assets.py 一致：那边把 flat **排在最前面**，
    占住 gfx_sprites[] 的 0..N-1。两边都按同一份清单的同一顺序数，才对得上。
    """
    for i, e in enumerate(mani.get('flat', [])):
        if os.path.normcase(e.get('src', '')) == os.path.normcase(path):
            return i
    return -1


def find_manifest(repo):
    p = os.path.join(repo, 'scenario', 'assets.json')
    return p if os.path.isfile(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', help='资源清单 scenario/assets.json（默认就是它）')
    ap.add_argument('--out-c', default=os.path.join(ROOT, 'source', 'assets', 'anim_data.c'))
    ap.add_argument('--out-h', default=os.path.join(ROOT, 'include', 'anim_data.h'))
    a = ap.parse_args()

    mp = a.manifest or find_manifest(ROOT)
    proj = None
    if mp and os.path.isfile(mp):
        proj = load_project(mp)
        anims = proj.get('animations', []) or []
        print('  [anim] %s：%d 个动画，%d 个精灵'
              % (os.path.relpath(mp, ROOT), len(anims), len(proj.get('flat', []))))
    else:
        proj, anims = None, []
        print('  [anim] 没有资源清单，生成空动画表（引擎要求符号一定存在）')

    frames, durs, defs, missing = [], [], [], []
    for an in anims:
        first = len(frames)
        for fr in an.get('frames', []):
            ix = sprite_index(proj, fr.get('src', ''))
            if ix < 0:
                missing.append(fr.get('src', ''))
                continue
            frames.append(ix)
            durs.append(max(1, int(fr.get('dur', 6))))
        n = len(frames) - first
        if n == 0:
            continue                     # 一帧都没解析出来的动画跳过
        defs.append((first, n, 1 if an.get('loop', True) else 0))
        print('    %-8s %d 帧，%s，共 %d 个游戏帧（%.1f 秒）'
              % (an.get('name', '?'), n, '循环' if an.get('loop', True) else '播一次',
                 sum(durs[first:first + n]), sum(durs[first:first + n]) / 60.0))

    if missing:
        print('  [anim] ⚠ 有 %d 帧找不到对应的「精灵」素材（要先在资源库归类）：' % len(missing))
        for p in missing[:6]:
            print('      %s' % p)

    # ---------------- 写 .h ----------------
    with open(a.out_h, 'w', encoding='utf-8', newline='') as f:
        f.write('''/* =====================================================================
 *  anim_data.h —— 精灵动画表（**自动生成，不要手改**）
 *
 *  生成者：tools/make_project_anim.py
 *  数据来源：工程文件里的 animations（编辑器「精灵」模式编的）
 * ===================================================================== */
#ifndef ANIM_DATA_H
#define ANIM_DATA_H

#include <tonc.h>

#define ANIM_N       %d
#define ANIM_FRAME_N %d

/* 每个动画一条：从 anim_frames 的第几项开始、共几帧、是否循环 */
typedef struct {
    u8 first;
    u8 n;
    u8 loop;
} AnimDef;

extern const AnimDef anim_defs[ANIM_N ? ANIM_N : 1];
extern const u8 anim_frames[ANIM_FRAME_N ? ANIM_FRAME_N : 1];   /* 精灵下标 */
extern const u8 anim_durs[ANIM_FRAME_N ? ANIM_FRAME_N : 1];     /* 每帧停几帧 */

#endif /* ANIM_DATA_H */
''' % (len(defs), len(frames)))

    # ---------------- 写 .c ----------------
    def arr(name, vals, per=16):
        out = ['const u8 %s[] = {' % name]
        for i in range(0, len(vals), per):
            out.append('    ' + ', '.join('%d' % v for v in vals[i:i + per]) + ',')
        if not vals:
            out.append('    0,')
        out.append('};')
        return out

    lines = ['/* =====================================================================',
             ' *  anim_data.c —— 精灵动画表（**自动生成，不要手改**）',
             ' *',
             ' *  生成者：tools/make_project_anim.py',
             ' * ===================================================================== */',
             '#include "anim_data.h"',
             '']
    lines += arr('anim_frames', frames)
    lines.append('')
    lines += arr('anim_durs', durs)
    lines.append('')
    lines.append('const AnimDef anim_defs[ANIM_N ? ANIM_N : 1] = {')
    if defs:
        for i, (first, n, loop) in enumerate(defs):
            lines.append('    { %3d, %3d, %d },' % (first, n, loop))
    else:
        lines.append('    { 0, 0, 0 },')
    lines.append('};')
    lines.append('')

    os.makedirs(os.path.dirname(a.out_c), exist_ok=True)
    with open(a.out_c, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines))
    print('  [anim] 写出 %s（%d 个动画 / %d 帧）'
          % (os.path.relpath(a.out_c, ROOT), len(defs), len(frames)))


if __name__ == '__main__':
    main()
