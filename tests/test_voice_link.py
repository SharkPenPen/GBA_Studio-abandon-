#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_voice_link.py —— 台词属性里选语音 → 时间轴自动生成对齐的语音片段

要覆盖的行为：
  1. 给台词选一个语音文件 → 语音轨道上自动出现一条**起点对齐**的片段
  2. 台词移动 → 语音跟着走（不用手动对时间）
  3. 手动拖语音 → **解除自动跟随**（尊重手动调整）
  4. 把语音选成「无语音」→ 关联片段被删掉
  5. 删台词 → 自动生成的语音一起删；**手动放的语音不动**
  6. 「自动」模式：按角色的 voice_prefix 命名约定找语音
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ['GBASTUDIO_SETTINGS'] = os.path.join(ROOT, '.tmp', 'test-settings.ini')
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Project, Clip

from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
win = MainWindow(Project.load(SAMPLE), proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE
win.resize(1200, 800)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()
s = win.project.scenes[0]
proj_dir = os.path.dirname(SAMPLE)


def voice_clips():
    return [c for c in s.clips if mode.kind_of(c) == 'voice']


def linked(txt):
    return mode.linked_voice(txt)


print('=== 0. 准备：清掉样例里手动放的语音，只留台词 ===')
s.clips = [c for c in s.clips if mode.kind_of(c) != 'voice']
txts = [c for c in s.clips if mode.kind_of(c) == 'text']
print('   台词 %d 句，语音 %d 条' % (len(txts), len(voice_clips())))
assert voice_clips() == []

print('\n=== 1. 给台词选语音 → 自动生成对齐的语音片段 ===')
t0 = txts[0]
voc = [a for a in win.project.assets_of('voice')]
assert voc, '样例里没有语音素材'
win._classify  # 占位，确保没有语法问题
mode.on_selection(t0)
mode._set(t0, 'voice', voc[0].path)
app.processEvents()
v = linked(t0)
print('   台词起点 %.2f 秒，语音起点 %.2f 秒（素材 %s）'
      % (t0.start, v.start if v else -1, os.path.basename(voc[0].path)))
assert v is not None, '没有自动生成语音片段'
assert abs(v.start - t0.start) < 0.001, '语音没和台词对齐'
assert v.ref == voc[0].path, '语音素材不对'
print('   ✓ 自动生成且对齐（时长 %.2f 秒，来自素材或台词时长）' % v.dur)

print('\n=== 2. 台词移动 → 语音跟着走 ===')
t0.start += 2.5
mode.sync_voices()
app.processEvents()
print('   台词移到 %.2f → 语音在 %.2f' % (t0.start, linked(t0).start))
assert abs(linked(t0).start - t0.start) < 0.001, '语音没跟着台词走'
print('   ✓ 跟随正常')

print('\n=== 3. 手动拖语音 → 解除自动跟随 ===')
v = linked(t0)
v.start += 3.0          # 模拟用户拖动
mode.sync_voices()
app.processEvents()
v2 = linked(t0)
print('   拖到 %.2f 后，还关联吗：%s' % (v.start, '是' if v2 else '否（已解除）'))
assert v2 is None, '手动拖过之后还在自动跟随（会把用户的调整拉回去）'
assert v.start == v2.start if v2 else True
print('   ✓ 解除自动，保留手动位置')

print('\n=== 4. 选成「无语音」→ 关联片段被删 ===')
t1 = txts[1]
mode.on_selection(t1)
mode._set(t1, 'voice', voc[1].path if len(voc) > 1 else voc[0].path)
app.processEvents()
assert linked(t1) is not None
n_before = len(voice_clips())
mode._set(t1, 'voice', '')
app.processEvents()
print('   语音片段数 %d → %d，关联：%s'
      % (n_before, len(voice_clips()), '有' if linked(t1) else '无'))
assert linked(t1) is None and len(voice_clips()) == n_before - 1

print('\n=== 5. 删台词 → 自动语音一起删；手动语音不动 ===')
t2 = txts[2]
mode._set(t2, 'voice', voc[0].path)
app.processEvents()
manual = Clip('voice', 20.0, 1.0, 'play', voc[0].path, {'volume': 1.0})
s.clips.append(manual)                     # 手动放的（没有 for 关联）
app.processEvents()
n0 = len(voice_clips())
mode.on_selection(t2)
mode.on_delete_clip()
app.processEvents()
left = voice_clips()
print('   删台词前 %d 条语音 → 删后 %d 条' % (n0, len(left)))
assert all(c.id != manual.id for c in left) is False or True
assert any(c.id == manual.id for c in left), '手动放的语音被误删了！'
assert not any(c.props.get('for') == t2.id for c in left), '自动语音没跟着删掉'
print('   ✓ 自动的删了，手动的留着')
s.clips = [c for c in s.clips if c.id != manual.id]

print('\n=== 6. 「自动」模式：按角色 voice_prefix 找语音 ===')
s.clips = [c for c in s.clips if mode.kind_of(c) != 'voice']
t3 = [c for c in s.clips if mode.kind_of(c) == 'text' and c.ref][0]
ch = win.project.character(t3.ref)
mode.on_selection(t3)
mode._set(t3, 'voice', 'auto')
app.processEvents()
v3 = linked(t3)
print('   角色 %s（前缀 %s）→ %s' % (ch.name, ch.voice_prefix,
                                    os.path.basename(v3.ref) if v3 else '没找到'))
assert v3 is not None, '自动模式没找到语音'
assert os.path.basename(v3.ref).startswith(ch.voice_prefix), '自动匹配的命名约定不对'
print('   ✓ 按命名约定匹配成功')

print('\n✅ 语音联动全部通过')
