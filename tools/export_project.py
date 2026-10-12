#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_project.py —— 把一个 .gbastudio 工程导出成引擎要的中间产物

【为什么需要它】
引擎的构建原来是绑死在"当前导出"上的 ✗
而"当前导出"以前就是**示例工程**的导出 ✓
于是出现一个结构性问题：
    **示例本该是"用来测试引擎的"，却变成了"引擎的构建依赖"** ✗

用户的话说得很准：
    "示例是用来测试引擎的，不是构建引擎的，不能和引擎有关系"

所以拆开 ✓：
    · 引擎只认 `scenario/` + `include/` 里的中间产物 ✓ 不认任何工程 ✓
    · **哪个工程**由调用方指定 ✓ 就是这个工具干的事 ✓
    · 没有工程时，`build-assets` 会生成一份**空剧本** ✓ 引擎照样能编 ✓

【产出】
    scenario\\scenario.txt     剧本（命令表）
    scenario\\assets.json     资源清单
    include\\project_video.h  工程设置（显示模式、开场方式）
    include\\scenario.h       剧本索引（由 build_script.py 生成）

用法：
    python tools\\export_project.py --project "<工程.gbastudio>"
    python tools\\export_project.py --empty          # 生成空剧本（搭空壳用）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

EMPTY_SCENARIO = """# 空剧本（由 tools/export_project.py --empty 生成）
#
# 引擎不需要任何工程也能编译、能跑 —— 这一份就是那种状态：
# 「能开机、能显示、但没有内容」。
# 要出内容就导出某个工程：
#     python tools\\export_project.py --project "<工程.gbastudio>"
#
# ⚠ 这里**不能放任何命令** ✗
# 第一版我随手写了一行 "sayskip 0" ✓ 那是编的、脚本编译器不认 ✓
# 于是 build_script.py 直接退出码 1 ✓ 后面几步全不跑 ✓
# 最后在链接期报一堆 undefined reference ✗ —— 一个假的空剧本，
# 换来一屏看不懂的链接错误 ✓
#
# 空就是空：只有注释 ✓ 编译器会生成一张空命令表 ✓
"""


def log(m):
    print('[export] ' + m)


def main():
    ap = argparse.ArgumentParser(description='把工程导出成引擎的中间产物')
    ap.add_argument('--project', default='', help='.gbastudio 工程文件')
    ap.add_argument('--empty', action='store_true', help='生成空剧本（不带任何工程）')
    ap.add_argument('--scenario-dir', default=os.path.join(ROOT, 'scenario'))
    ap.add_argument('--include-dir', default=os.path.join(ROOT, 'include'))
    a = ap.parse_args()

    os.makedirs(a.scenario_dir, exist_ok=True)
    os.makedirs(a.include_dir, exist_ok=True)
    sp = os.path.join(a.scenario_dir, 'scenario.txt')
    ap_ = os.path.join(a.scenario_dir, 'assets.json')

    if a.empty or not a.project:
        with open(sp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(EMPTY_SCENARIO)
        with open(ap_, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'bg': [], 'sprites': [], 'flat': [], 'animations': [],
                       'audio': []}, f, ensure_ascii=False, indent=1)
        # 空工程也要有 project_video.h，否则引擎编不过
        vh = os.path.join(a.include_dir, 'project_video.h')
        with open(vh, 'w', encoding='utf-8', newline='\n') as f:
            f.write('/* 由 tools/export_project.py 写出（空工程）。\n'
                    ' * 没有指定任何工程，用的是默认设置。 */\n'
                    '#ifndef PROJECT_VIDEO_H\n#define PROJECT_VIDEO_H\n\n'
                    '#define GAL_VIDEO_MODE 3\n'
                    '#define GAL_SKIP_TITLE 1\n\n#endif\n')
        log('已生成空剧本（引擎会编出一个"能开机但没内容"的 ROM）')
        log('  %s' % sp)
        return 0

    if not os.path.isfile(a.project):
        log('✗ 找不到工程 %s' % a.project)
        return 1

    from core.project import Project
    from core import compiler
    p = Project.load(a.project)
    proj_dir = os.path.dirname(os.path.abspath(a.project))
    text, notes, mani = compiler.compile_project(p, proj_dir, log=log)
    with open(sp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    with open(ap_, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(mani, f, ensure_ascii=False, indent=1)
    compiler.write_video_mode(p, a.include_dir, log=log)
    log('工程「%s」已导出：剧本 %d 行，bg=%d sprites=%d audio=%d'
        % (p.name, len(text.splitlines()), len(mani.get('bg', [])),
           len(mani.get('sprites', [])), len(mani.get('audio', []))))
    for n in notes[:5]:
        log('  提示：%s' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
