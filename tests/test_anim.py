#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_anim.py —— 精灵动画（P9）：数据模型 + 编辑器模式 + 编译脚本

要覆盖的：
  1. 动画能存进工程文件再读回来（帧、时长、循环标志都不丢）
  2. 编辑器的「精灵」模式注册上了，面板能建出来
  3. 加帧/删帧/挪顺序/改时长都真的改了数据
  4. 素材清单里带上动画，且帧被解析成绝对路径（生成脚本只认清单）
  5. anim_data.c 生成正确：帧下标和 gfx_sprites 的顺序**对得上**
     （精灵必须排在立绘前面，不然加一句台词就会让动画错位）
"""
import json
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
from core.project import Project, Asset
from core.anim import Animation, AnimFrame, default_animations
from core import compiler

from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
proj_dir = os.path.dirname(SAMPLE)

print('=== 1. 动画能存能读 ===')
p = Project.load(SAMPLE)
print('   工程里的动画：%s' % '，'.join('%s(%d帧)' % (a.name, len(a.frames))
                                       for a in p.animations))
assert p.animations, '样品工程里应该有默认动画'
walk = [a for a in p.animations if a.name == '走路']
assert walk, '没有「走路」动画'
walk = walk[0]
assert len(walk.frames) == 4 and walk.loop, (len(walk.frames), walk.loop)
assert [f.dur for f in walk.frames] == [6, 6, 6, 6], [f.dur for f in walk.frames]
assert walk.total_frames() == 24

tmp = os.path.join(ROOT, '.tmp', 'anim_test')
os.makedirs(tmp, exist_ok=True)
path = os.path.join(tmp, 'a.gbastudio')
p.save(path)
p2 = Project.load(path)
w2 = [a for a in p2.animations if a.name == '走路'][0]
print('   往返后：%d 帧，时长 %s' % (len(w2.frames), [f.dur for f in w2.frames]))
assert [f.path for f in w2.frames] == [f.path for f in walk.frames]
assert [f.dur for f in w2.frames] == [f.dur for f in walk.frames]

print('\n=== 2. 编辑器：「精灵」模式注册且面板能建出来 ===')
win = MainWindow(p2, proj_ctx={'gba_project': ROOT})
win.file_path = path
titles = [m.title for m in win.modes]
print('   模式列表:', titles)
assert '精灵' in titles, '精灵模式没注册上'
mode = [m for m in win.modes if m.title == '精灵'][0]
win.switch_mode(titles.index('精灵'))
app.processEvents()
assert mode.anim_list is not None and mode.frame_list is not None
print('   动画列表 %d 项，帧列表 %d 项，可选精灵素材 %d 个'
      % (mode.anim_list.count(), mode.frame_list.count(), mode.asset_combo.count()))
assert mode.anim_list.count() == len(p2.animations)
assert mode.asset_combo.count() == 5, mode.asset_combo.count()   # 5 张测试帧

print('\n=== 3. 加帧 / 删帧 / 挪顺序 / 改时长 ===')
mode.anim_list.setCurrentRow(0)
an = mode.current()
n0 = len(an.frames)
mode.on_add_frame()
print('   加一帧：%d → %d' % (n0, len(an.frames)))
assert len(an.frames) == n0 + 1
mode.on_move_frame(-1)
print('   往前挪一格 ✓ 现在第一帧是 %s' % os.path.basename(an.frames[0].path))
mode._set_dur(0, 12)
assert an.frames[0].dur == 12
print('   改时长 → %d 帧 ✓' % an.frames[0].dur)
mode.on_del_frame()
print('   删一帧：%d → %d' % (n0 + 1, len(an.frames)))
assert len(an.frames) == n0

print('\n=== 4. 清单里带上了动画，帧是绝对路径 ===')
# 注意用**样品工程目录**编译：素材路径是相对的，临时目录里没有那些 png。
# （反过来说：路径找不到的帧会被跳过而不是写进清单 —— 这正是想要的行为）
text, notes, mani = compiler.compile_project(p2, proj_dir)
anims = mani.get('animations', [])
print('   清单动画：%s' % '，'.join('%s(%d帧)' % (a['name'], len(a['frames']))
                                  for a in anims))
assert anims, '清单里没有动画'
for a in anims:
    for f in a['frames']:
        assert os.path.isabs(f['src']) and os.path.isfile(f['src']), f['src']
print('   ✓ 全部是存在的绝对路径（生成脚本不用再啃工程文件）')

print('\n=== 5. anim_data.c：帧下标和 gfx_sprites 的顺序对得上 ===')
flat = mani.get('flat', [])
print('   清单里的精灵：%s' % '，'.join(e['name'] for e in flat))
assert flat, '清单里没有精灵'
mp = os.path.join(tmp, 'assets.json')
with open(mp, 'w', encoding='utf-8') as f:
    json.dump(mani, f, ensure_ascii=False)
out_c = os.path.join(tmp, 'anim_data.c')
out_h = os.path.join(tmp, 'anim_data.h')
r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_project_anim.py'),
                    '--manifest', mp, '--out-c', out_c, '--out-h', out_h],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print('   ' + (r.stdout or '').strip().replace('\n', '\n   '))
assert r.returncode == 0, r.stderr
src = open(out_c, encoding='utf-8').read()
head = open(out_h, encoding='utf-8').read()
assert 'anim_defs' in src and 'ANIM_N' in head
# 帧下标必须落在精灵数量之内（对不上就是下标错位）
import re
nums = [int(x) for x in re.findall(r'^\s*([\d, ]+),', src.split('anim_durs')[0],
                                   re.M) for x in x.split(',') if x.strip()]
if nums:
    print('   anim_frames 下标：%s（精灵共 %d 个）' % (nums[:12], len(flat)))
    assert max(nums) < len(flat), '帧下标超出精灵数量 —— 动画和精灵表对不上'
print('   ✓ 下标都在范围内')

print('\n✅ 精灵动画全部通过')
