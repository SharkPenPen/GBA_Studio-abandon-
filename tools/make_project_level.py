#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_project_level.py —— 把关卡地图编译成引擎认识的 C 数据

输入：工程目录里的 level.txt（编辑器「关卡」模式画出来的）
输出：source/assets/level_data.c  ——  一张 u8 数组

地图文件格式（纯文本，方便肉眼检查、也方便手改）：

    ; 出生点 2 3
    ###############
    #.............#
    #....##..~~~..#
    ...
    ###############

    字符对应： '.' 地板   '#' 墙   'g' 草   '~' 水
    注释用 ';' 开头 —— 千万不能用 '#'，因为 '#' 就是墙，
    用它当注释符会把每一行地图都当成注释跳掉（踩过这个坑，
    结果解析出空地图、悄悄回退到默认地图，测试还"通过"了）。

为什么要变成 C 数组而不是让引擎读文本：
    GBA 卡带的 ROM 是只读的，读文本要现场解析 UTF-8/ASCII、还要处理换行，
    属于"运行期做编译期该做的事"。编译成数组后，引擎里就是一次下标访问。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 字符 → 图块编号（要和 level.c 里的 T_* 对上）
CHAR2TILE = {'.': 0, '#': 1, 'g': 2, '~': 3, ' ': 0}

TILE_NAME = {0: '地板', 1: '墙', 2: '草', 3: '水'}


def parse(path):
    """读 level.txt → (w, h, cells, start)"""
    start = (1, 1)
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.rstrip('\n').rstrip('\r')
            if s.startswith(';'):
                # ';' 开头是注释（**不能用 '#'**：'#' 是墙的字符）
                if '出生点' in s or 'start' in s.lower():
                    nums = [int(x) for x in s.replace('出生点', ' ')
                            .replace('start', ' ').replace(':', ' ').split()
                            if x.isdigit()]
                    if len(nums) >= 2:
                        start = (nums[0], nums[1])
                continue
            if not s:
                continue
            rows.append(s)

    if not rows:
        raise SystemExit('  level.txt 里没有地图内容')

    w = max(len(r) for r in rows)
    h = len(rows)
    cells = []
    for r in rows:
        r = r.ljust(w, '.')
        cells.append([CHAR2TILE.get(c, 0) for c in r])

    sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h):
        sx, sy = 1, 1
    if cells[sy][sx] != 0:
        # 出生点被压在实心块里就换一个空位，免得一进关卡就卡死
        for ty in range(h):
            for tx in range(w):
                if cells[ty][tx] == 0:
                    sx, sy = tx, ty
                    break
            else:
                continue
            break
    return w, h, cells, (sx, sy)


def default_map():
    """工程里还没有 level.txt 时用的默认地图（和仓库里那份一致）"""
    rows = [
        '###############',
        '#.............#',
        '#....##.......#',
        '#....##..~~~..#',
        '#........~~~..#',
        '#..gg....~~~..#',
        '#..gg.........#',
        '#....##.......#',
        '#....##.......#',
        '###############',
    ]
    return len(rows[0]), len(rows), [[CHAR2TILE[c] for c in r] for r in rows], (1, 1)


def emit(w, h, cells, start, out_c, out_h):
    lines = []
    lines.append('/* =====================================================================')
    lines.append(' *  level_data.c —— 关卡地图数据（**自动生成，不要手改**）')
    lines.append(' *')
    lines.append(' *  生成者：tools/make_project_level.py')
    lines.append(' *  数据来源：工程里的 level.txt')
    lines.append(' * ===================================================================== */')
    lines.append('#include "level_data.h"')
    lines.append('')
    lines.append('const u8 lvl_map[LVL_H * LVL_W] = {')
    lines.append('/*      %s */' % ' '.join('%2d' % x for x in range(w)))
    for ty in range(h):
        row = ', '.join('%d' % cells[ty][tx] for tx in range(w))
        lines.append('/* %2d */ %s,' % (ty, row))
    lines.append('};')
    lines.append('')

    os.makedirs(os.path.dirname(out_c), exist_ok=True)
    with open(out_c, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines))

    with open(out_h, 'w', encoding='utf-8', newline='') as f:
        f.write('''/* =====================================================================
 *  level_data.h —— 关卡地图数据（**自动生成，不要手改**）
 *
 *  生成者：tools/make_project_level.py
 *  数据来源：工程里的 level.txt（编辑器「关卡」模式画笔刷出来的）
 *
 *  地图是一维数组，按行优先存：lvl_map[ty * LVL_W + tx]
 *  图块编号：0=地板 1=墙 2=草 3=水（墙和水不可通行）
 * ===================================================================== */
#ifndef LEVEL_DATA_H
#define LEVEL_DATA_H

#include <tonc.h>

#define LVL_W        %d
#define LVL_H        %d
#define LVL_START_X  %d        /* 出生点（格子坐标）*/
#define LVL_START_Y  %d
#define TILE_KIND_N   4        /* 图块类型数 */

extern const u8 lvl_map[LVL_H * LVL_W];

#endif /* LEVEL_DATA_H */
''' % (w, h, start[0], start[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', help='游戏工程目录（找里面的 level.txt）')
    ap.add_argument('--level', default=os.path.join(ROOT, 'scenario', 'level.txt'),
                    help='level.txt 的路径（默认 scenario\\level.txt）')
    ap.add_argument('--out-c', default=os.path.join(ROOT, 'source', 'assets', 'level_data.c'))
    ap.add_argument('--out-h', default=os.path.join(ROOT, 'include', 'level_data.h'))
    a = ap.parse_args()

    src = None
    if a.project:
        cand = os.path.join(a.project, 'level.txt')
        src = cand if os.path.isfile(cand) else None
    if src is None and os.path.isfile(a.level):
        src = a.level
    # 编辑器导出时会把 level.txt 放进引擎仓库的 scenario\ —— 和 assets.json 一起
    if src is None:
        repo_copy = os.path.join(ROOT, 'scenario', 'level.txt')
        src = repo_copy if os.path.isfile(repo_copy) else None

    if src and os.path.isfile(src):
        w, h, cells, start = parse(src)
        print('  [level] 读到 %s（%dx%d，出生点 %d,%d）' % (src, w, h, start[0], start[1]))
    else:
        w, h, cells, start = default_map()
        print('  [level] 没有 level.txt，用默认地图（%dx%d）' % (w, h))

    emit(w, h, cells, start, a.out_c, a.out_h)

    counts = {}
    for ty in range(h):
        for tx in range(w):
            counts[cells[ty][tx]] = counts.get(cells[ty][tx], 0) + 1
    print('  [level] 图块统计：' +
          '，'.join('%s %d' % (TILE_NAME.get(k, k), v) for k, v in sorted(counts.items())))
    print('  [level] 写出 %s' % os.path.relpath(a.out_c, ROOT))
    print('  [level] 写出 %s' % os.path.relpath(a.out_h, ROOT))


if __name__ == '__main__':
    main()
