

# -*- coding: utf-8 -*-
"""验证三处修复：属性不残留（含嵌套布局）/ 轨道名贴边居中 / 时间轴长度跟随内容"""
import os
import sys
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Project, Clip, Scene

# 显式加载样品工程（启动时给的是空工程，测试需要真实内容）
from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
_proj = Project.load(SAMPLE) if os.path.isfile(SAMPLE) else None
win = MainWindow(_proj, proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE if _proj else ''
win.resize(1300, 800)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()
s = win.project.scenes[0]


def all_widgets(lay):
    """递归收集布局里的所有控件（旧测试只看一层，漏掉了嵌套的 QFormLayout）"""
    out = []
    for i in range(lay.count()):
        it = lay.itemAt(i)
        if it.widget():
            out.append(it.widget())
        if it.layout():
            out += all_widgets(it.layout())
    return out


print('=== 1. 属性：反复切换片段不留残影（递归检查） ===')
texts = [c for c in s.clips if c.track == 'text']
bg = [c for c in s.clips if c.track == 'bg'][0]
seq = [texts[0], bg, texts[1], bg, None, texts[2], bg]
counts, stray = [], 0
for c in seq:
    mode.on_selection(c)
    app.processEvents()
    ws = all_widgets(win.inspector_body)
    counts.append(len(ws))
    # 检查有没有"孤儿"：把布局里的控件及其所有后代都算作"合法"，
    # 剩下还挂在 holder 下面且可见的才算残留（控件自己内部的子控件不算）
    holder = win.inspector_body.parentWidget()
    legit = set()
    for w in ws:
        legit.add(id(w))
        for sub in w.findChildren(QWidget):
            legit.add(id(sub))
    for w in holder.findChildren(QWidget):
        if w.isVisible() and id(w) not in legit:
            stray += 1
print('   每次切换后的控件数:', counts)
print('   累计残留控件:', stray, '（应为 0）')
assert stray == 0, '有控件留在原地没被清掉'
assert counts[0] == counts[2] == counts[5] and counts[1] == counts[3] == counts[6], counts  # 同类片段控件数必须一致

print('\n=== 2. 轨道名：右对齐贴住分界线，垂直居中 ===')
tv = win.timeline
tv.rebuild()
named = []
for it in tv.scene_.items():
    if it.__class__.__name__ == 'QGraphicsSimpleTextItem':
        named.append(it)
track_names = set(t.name for t in s.tracks) | {'句'}
hits = [t for t in named if t.text() in track_names and t.text() != '句']
print('   找到轨道名文本 %d 个' % len(hits))
assert hits, '没找到轨道名'
bad_right, bad_v = 0, 0
for t in hits:
    br = t.boundingRect()
    right_gap = tv.LEFT_W if hasattr(tv, 'LEFT_W') else 84
    # 右边缘距分界线应为 8 左右
    gap = 84 - (t.pos().x() + br.width())
    if not (2 <= gap <= 12):
        bad_right += 1
    # 垂直位置：行内居中（行高 24，容差 3 像素）
    y = t.pos().y()
    row = (y - tv.RULER_H if hasattr(tv, 'RULER_H') else y) % 24
    if not (2 <= row <= 22):
        bad_v += 1
print('   右对齐异常 %d 个，垂直异常 %d 个（都应为 0）' % (bad_right, bad_v))
assert bad_right == 0 and bad_v == 0

print('\n=== 3. 时间轴长度跟随内容 ===')
tv.set_project(win.project, s)
end = max(c.start + c.dur for c in s.clips)
d = tv.duration()
print('   内容末尾 %.1f 秒 → 时间轴长 %.1f 秒（内容 + 2）' % (end, d))
assert abs(d - (end + 2)) < 0.01, (end, d)
# 加一个很靠后的片段，长度要跟着变
s.clips.append(Clip('bg_2', 40.0, 3.0, 'show', 'x.png', {}))
tv.rebuild()
d2 = tv.duration()
print('   末尾加到 43 秒后 → 时间轴长 %.1f 秒' % d2)
assert abs(d2 - 45.0) < 0.01, d2
# 空场景不应塌成 0
empty = Scene('空场景', 'story')
tv.set_project(win.project, empty)
print('   空场景 → 时间轴长 %.1f 秒（有最小长度）' % tv.duration())
assert tv.duration() >= 12.0

print('\n=== 4. 新建音乐片段默认铺到内容末尾（不会比剧情还长） ===')
mode.on_selection(None)
before = len(s.clips)
mode.add_clip('bgm')
last = s.clips[-1]
end2 = max(c.start + c.dur for c in s.clips if c is not last)
print('   新音乐片段: 起点 %.1f 时长 %.1f（当前内容末尾 %.1f）' % (last.start, last.dur, end2))
assert abs(last.start + last.dur - end2) < 0.01, (last.start + last.dur, end2)  # 正好铺到末尾

print('\n=== 5. 属性栏能自由拖窄（选中任何片段时都不该被文字撑住）===')
# 用户反馈："选中文本后属性栏左右拖动显示会出错"。
# 根因是几处文字的**最小宽度**把面板顶住了：
#   · 标题那两行（"第 1 句 · 台词 · c99478563_4" / "轨道 text（下面这些…）"）
#   · 下拉框（Qt 默认最小宽 = 最长选项宽，语音文件名一长就撑开）
#   · 表单标签列
from PySide6.QtCore import Qt
cases = [('未选中', None)]
for want in ('text', 'bg', 'voice', 'char1', 'bgm'):
    hit = next((c for c in s.clips if mode.kind_of(c) == want), None)
    if hit:
        cases.append((want, hit))
for tag, sel in cases:
    mode.on_selection(sel)
    app.processEvents()
    holder = win.inspector_body.parentWidget()
    mn = holder.minimumSizeHint().width()
    print('   [%-8s] 属性栏最小宽 = %3d px' % (tag, mn))
    assert mn <= 200, '选中 %s 时属性栏最小宽被撑到 %d，拖不窄' % (tag, mn)
    # 真拖一遍，确认能到 150 像素
    win.resizeDocks([win.dock_inspector], [150], Qt.Horizontal)
    app.processEvents()
    assert win.dock_inspector.width() <= 220, \
        '选中 %s 时属性栏拖不到 220 以下（实际 %d）' % (tag, win.dock_inspector.width())
print('   ✓ 各种片段都能拖窄（原来选中文本时最小宽 290）')

print('\n✅ 全部通过')
