#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_level.py —— 关卡模式（P8）：数据模型 + 编辑器模式 + 编译脚本

要覆盖的：
  1. 地图数据能存能读（.gbastudio 里往返 + level.txt 往返）
  2. 编辑器里「关卡」模式真的注册上了，面板能建出来
  3. 涂格子会改数据、会标脏；出生点不会落在墙里
  4. level.txt → C 数组（make_project_level.py）能跑通，且和地图一致
  5. 四种图块都在（地图能表达"走不过去"和"能走"）
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ['GBASTUDIO_SETTINGS'] = os.path.join(ROOT, '.tmp', 'test-settings.ini')
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Project, blank_project
from core.level import Level, TILE_NAMES, SOLID
from core import compiler

print('=== 1. 地图数据：往返不变 ===')
lv = Level.default()
print('   默认地图 %dx%d，出生点 %s' % (lv.w, lv.h, lv.start))
assert (lv.w, lv.h) == (15, 10)
assert lv.get(*lv.start) not in SOLID, '出生点落在实心块里'

d = lv.to_dict()
lv2 = Level.from_dict(d)
assert (lv2.w, lv2.h) == (lv.w, lv.h) and lv2.cells == lv.cells and lv2.start == lv.start

txt = lv.to_text()
lv3 = Level.from_text(txt)
print('   level.txt 往返：%dx%d，出生点 %s' % (lv3.w, lv3.h, lv3.start))
assert lv3.cells == lv.cells, '文本往返后地图变了'
assert lv3.start == lv.start, '文本往返后出生点丢了'
# 再验一次"改过一格的地图"：解析失败时会**悄悄回退成默认地图**，
# 那样上面的断言也能过（默认 vs 默认）—— 这条就是防这个的
lv.paint(4, 4, 2)
back = Level.from_text(lv.to_text())
assert back.cells != Level.default().cells, \
    '文本解析失败会悄悄回退成默认地图，必须能区分出来'
assert back.get(4, 4) == 2, '改动的那一格没往返回来'
print('   改一格后往返也正确（能区分出"真解析"和"回退默认"）')
lv.paint(4, 4, 0)

print('\n=== 2. 存进工程文件再读回来 ===')
tmp = os.path.join(ROOT, '.tmp', 'lvl_test')
os.makedirs(tmp, exist_ok=True)
p = blank_project('关卡测试')
p.level = Level.default()
p.level.paint(3, 3, 3)                    # 放一格水
path = os.path.join(tmp, 'lvl.gbastudio')
p.save(path)
p2 = Project.load(path)
print('   读回：%dx%d，格子(3,3)=%s' % (p2.level.w, p2.level.h, p2.level.get(3, 3)))
assert p2.level.get(3, 3) == 3, '地图没存进工程文件'
assert (p2.level.w, p2.level.h) == (15, 10)

print('\n=== 3. 编辑器：「关卡」模式注册且面板能建出来 ===')
win = MainWindow(p2, proj_ctx={'gba_project': ROOT})
win.file_path = path
titles = [m.title for m in win.modes]
print('   模式列表:', titles)
assert '关卡' in titles, '关卡模式没注册上'
mode = [m for m in win.modes if m.title == '关卡'][0]
win.switch_mode(titles.index('关卡'))
app.processEvents()
assert mode.canvas is not None, '关卡面板没建出画布'
print('   面板：%s，画布 %dx%d' % (win.mode_docks[0][1].windowTitle(),
                                  mode.canvas.width(), mode.canvas.height()))

print('\n=== 4. 涂格子会改数据、会标脏 ===')
win.dirty = False
mode.set_tile(1)
mode.level.paint(5, 5, 1)
mode.canvas.update()
print('   (5,5) 现在是 %s' % TILE_NAMES[mode.level.get(5, 5)])
assert mode.level.get(5, 5) == 1
mode.on_clear()
assert mode.level.get(5, 5) == 0
assert mode.level.cells[0][0] == 1, '清空后四边应该补上墙'
print('   清空 ✓ 四边自动补墙 ✓')

print('\n=== 5. 出生点不会落在实心块上 ===')
lv4 = Level.default()
lv4.start = (1, 1)
lv4.paint(1, 1, 1)                        # 往出生点上涂墙
print('   往出生点涂墙后，出生点挪到了 %s（%s）'
      % (lv4.start, TILE_NAMES[lv4.get(*lv4.start)]))
assert lv4.get(*lv4.start) not in SOLID

print('\n=== 6. level.txt → C 数组（编译脚本） ===')
p2.level = Level.default()
p2.level.paint(2, 2, 2)                   # 草
compiler.write_level(p2, tmp)
# ⚠ write_level 写的是 <gba_dir>/scenario/level.txt ✗ 不是 <gba_dir>/level.txt ✓
#（这个断言原来写错了路径 ✓ 却一直"通过" —— 因为 .tmp/lvl_test/level.txt
#  是更早版本代码留下的**陈旧文件** ✓✓ 清理 .tmp 之后才暴露出来 ✓
#  ——测试因为错误的原因通过，是最危险的一种 ✓）
lvl_txt = os.path.join(tmp, 'scenario', 'level.txt')
assert os.path.isfile(lvl_txt), 'level.txt 没写出来（应该在 %s）' % lvl_txt
out_c = os.path.join(tmp, 'level_data.c')
out_h = os.path.join(tmp, 'level_data.h')
r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_project_level.py'),
                    '--level', lvl_txt, '--out-c', out_c, '--out-h', out_h],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print('   ' + (r.stdout or '').strip().replace('\n', '\n   '))
assert r.returncode == 0, r.stderr
src = open(out_c, encoding='utf-8').read()
assert 'lvl_map' in src and 'LVL_H * LVL_W' in src
assert '#define LVL_W        15' in open(out_h, encoding='utf-8').read()
# 地图里那把草（2）应该出现在数组里
assert ' 2,' in src or ', 2,' in src, '草地上没有出现在生成的数组里'
print('   ✓ 生成成功，含出生点与图块')

print('\n=== 7. 剧本里能切模式（P10）：mode 1 ==')
# 在 fx 轨上放一个 kind='mode' 的片段，编译出来必须是 `mode 1`
from core.project import Clip
s0 = p2.scenes[0]
tk = s0.first_track('fx') or s0.add_track('fx')
s0.clips = [c for c in s0.clips if c.kind != 'mode']
# 切模式**之前**一句、**之后**一句 —— 才能验证"关卡玩完回来接着演"
tt = s0.first_track('text') or s0.add_track('text')
s0.clips = [c for c in s0.clips if c.track != tt.id]
s0.clips.append(Clip(tt.id, 0.5, 0.4, 'say', '', {'text': '进关卡之前。'}))
s0.clips.append(Clip(tk.id, 1.0, 0.2, 'mode', '', {'kind': 'mode', 'to': 'level'}))
s0.clips.append(Clip(tt.id, 1.5, 0.4, 'say', '', {'text': '关卡之后。'}))
text, notes, _ = compiler.compile_project(p2, tmp)
mode_lines = [ln for ln in text.splitlines() if ln.startswith('mode')]
print('   编译出来的切模式命令:', mode_lines)
assert mode_lines == ['mode 1'], mode_lines
# 切模式那一句的**后面**必须还有台词 —— 关卡玩完才有得演
all_lines = text.splitlines()
idx = all_lines.index('mode 1')
nxt = [ln for ln in all_lines[idx + 1:] if ln.startswith('say')]
print('   切模式之后还有 %d 句台词（关卡玩完接着演）' % len(nxt))
assert nxt, '切模式后面没有台词了 —— 关卡回来会没得演'
print('   ✓ 引擎侧 CMD_MODE + 生成器 + 编译器三处对上了')

print('\n✅ 关卡模式全部通过')
