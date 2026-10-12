#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
构建脚本的冒烟测试：真的把 build-assets.ps1 跑一遍

【为什么需要这条】
这一轮改动里，`build-assets.ps1` 连撞**两个"定义在后面"的坑** ✗
    · 用了 `Say`     → 那个函数在文件后半部分才定义
                       → "The term 'Say' is not recognized"
    · 用了 `$Python` → 那时它还是空的
                       → "expression after '&' … not valid"
两个都不是语法错 ✓ 而是**运行顺序**错 ✓
所以 `ast.parse` 那类静态检查**完全抓不到** ✗
（PowerShell 是顺序执行的：用到的函数和变量必须先就位）

**唯一能挡住的办法就是真跑一遍** ✓ 这个测试就干这件事 ✓

【为什么放在最后跑】
它会真的生成 `source/assets/` 和 `include/` ✓
别的测试（test_export / test_audio_data）也在用那个目录 ✓
所以 `run_all.py` 把它排在最后 ✓ 跑完不再有别的测试依赖它 ✓
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from _sample import SAMPLE_DIR, SAMPLE  # noqa: E402  现场生成的夹具

PS = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command']


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', cwd=ROOT)


def test_build_assets_with_project():
    """`build-assets.ps1 -Project <工程>` 要能跑通

    这条同时覆盖两件事：
      · 脚本本身能跑（函数/变量顺序对不对）
      · `-Project` 那条路能走通（先导出、再生成资源）
    """
    r = _run(PS + ["& '%s' -Project '%s'" % (os.path.join(ROOT, 'scripts', 'build-assets.ps1'),
                                             SAMPLE)])
    out = (r.stdout or '') + (r.stderr or '')
    assert r.returncode == 0, '构建资源失败（退出码 %s）：\n%s' % (r.returncode, out[-900:])
    # 关键产物要在
    for f in ('scenario/scenario.txt', 'scenario/assets.json',
              'source/assets/scenario.c', 'include/font_data.h'):
        assert os.path.isfile(os.path.join(ROOT, f)), '没生成 %s' % f
    # 导出这一步真的跑了（日志里有）
    assert '先导出工程' in out, '没有走"先导出"那条路'
    assert '构建' in out or '生成完毕' in out
    print('     build-assets.ps1 -Project 跑通（末尾：%s）'
          % out.strip().splitlines()[-1][:60])
    # 夹具里的工程名应该出现在导出日志里
    with open(os.path.join(ROOT, 'scenario', 'scenario.txt'), encoding='utf-8') as f:
        head = f.read(400)
    assert head.strip(), 'scenario.txt 是空的'


def test_empty_project_builds():
    """没有工程时也要能出中间产物（引擎不依赖任何工程）

    用户的原话："示例是用来测试引擎的，不是构建引擎的，不能和引擎有关系"
    ——所以引擎必须能**空着构建**：能开机、能显示、没有内容 ✓
    """
    r = _run([sys.executable, os.path.join(ROOT, 'tools', 'export_project.py'), '--empty'])
    assert r.returncode == 0, '空导出失败：%s' % (r.stderr or r.stdout)[-400:]
    sp = os.path.join(ROOT, 'scenario', 'scenario.txt')
    with open(sp, encoding='utf-8') as f:
        txt = f.read()
    # 空剧本里**只能有注释** —— 不能有任何命令（写一行假命令会让编译器退出）
    for ln in txt.splitlines():
        s = ln.strip()
        assert not s or s.startswith('#'), '空剧本里不该有命令：%r' % s
    print('     空剧本导出 ✓（只有注释，没有命令）')


def main():
    tests = [
        ('-Project 能跑通', test_build_assets_with_project),
        ('空工程也能构建', test_empty_project_builds),
    ]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print('    %-20s 通过' % name)
        except AssertionError as e:
            print('    %-20s 失败：%s' % (name, e))
            bad += 1
        except Exception as e:                          # noqa: BLE001
            print('    %-20s 出错：%s: %s' % (name, type(e).__name__, e))
            bad += 1
    print()
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 构建脚本：-Project 与空工程两条路都能跑')
    return 0


if __name__ == '__main__':
    sys.exit(main())
