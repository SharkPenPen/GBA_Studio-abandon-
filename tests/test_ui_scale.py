#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ui_scale.py —— 界面字体调节 + 面板尺寸可自由修改

覆盖三件事：
  1. 字体档位能切换，改完**立刻生效**（不用重启）
  2. 时间轴尺寸跟着字体走（否则字一大，轨道名和标签就挤在一起）
  3. 面板没有被人为设死的最小/最大尺寸（能自由拖大拖小）
  4. 选择会被记住（下次启动还是这个字号）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

# 设置写到工程内（不碰用户目录，测试可重复、不污染系统）
os.environ['GBASTUDIO_SETTINGS'] = os.path.join(ROOT, '.tmp', 'test-settings.ini')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui import settings as S
from ui.mainwindow import MainWindow
import ui.timeline as T

S.load()
from core.project import Project
from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
proj = Project.load(SAMPLE) if os.path.isfile(SAMPLE) else None
win = MainWindow(proj, proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE if proj else ''
win.resize(1200, 800)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()

print('=== 1. 字体档位切换，立刻生效 ===')
sizes = []
for label, pt in S.FONT_CHOICES:
    win.set_ui_font(pt)
    app.processEvents()
    f = QApplication.instance().font()
    s = T.apply_ui_scale  # 只是取个引用，避免 lint 误判
    sizes.append((label, pt, f.pointSize(), T.ROW_H, T.LEFT_W))
    print('   %-4s %2d 号 → 应用字体 %2d 号, 轨道行高 %2d, 列宽 %2d'
          % (label, pt, f.pointSize(), T.ROW_H, T.LEFT_W))

# 字号必须真的变了
assert len(set(x[2] for x in sizes)) == len(S.FONT_CHOICES), '字体没有逐档生效'
# 时间轴尺寸必须跟着变（这就是"调大字体后界面更难看"的根源）
assert len(set(x[3] for x in sizes)) >= 2, '轨道行高没跟着字号变'
assert sizes[-1][3] > sizes[0][3], '字体调大后行高反而没变大'
assert sizes[-1][4] > sizes[0][4], '字体调大后轨道名列宽没变大'
print('   ✓ 字体与时间轴尺寸都跟着变了')

print('\n=== 2. 面板尺寸没有被写死 ===')
from PySide6.QtWidgets import QDockWidget
loose = []
for title, d in win.all_docks:
    lo, hi = d.minimumWidth(), d.maximumWidth()
    loose.append((title, lo, hi))
    print('   %-14s 最小宽 %4d  最大宽 %8d' % (title, lo, hi))
# 最大宽不该被限制（否则拖不大）
for title, lo, hi in loose:
    assert hi >= 10000, '面板「%s」的最大宽度被限制成 %d，拖不大' % (title, hi)
# 预览面板（中央控件）不该有大的最小宽度
cw = win.centralWidget()
print('   中央预览面板: 最小 %dx%d' % (cw.minimumWidth(), cw.minimumHeight()))
assert cw.minimumWidth() <= 120, '中央面板最小宽度被设成 %d，缩不小' % cw.minimumWidth()
# 时间轴能被缩得很小
print('   时间轴最小高度: %d' % win.timeline.minimumHeight())
assert win.timeline.minimumHeight() <= 80, '时间轴最小高度被设死成 %d' % win.timeline.minimumHeight()
print('   ✓ 面板可自由缩放')

print('\n=== 3. 拖小面板后预览能自适应 ===')
win.resizeDocks([win.dock_assets], [160], Qt.Horizontal)
app.processEvents()
print('   资源库宽度收到 %d' % win.dock_assets.width())
assert win.dock_assets.width() < 300, '没能把面板拖小'
if win.zoom_combo.currentData() == 'fit':
    pm = win.preview_label.pixmap()
    print('   预览当前 %dx%d（适应窗口会自动取整数倍）' % (pm.width(), pm.height()))
    assert pm.width() % 240 == 0 and pm.width() > 0

print('\n=== 4. 选择被记住（模拟重启读取） ===')
win.set_ui_font(11)
app.processEvents()
pt, z = S.load()
print('   重新读取设置: 字体 %d 号, 预览缩放 %r' % (pt, z))
assert pt == 11, '字号没存住'
assert z == win.zoom_combo.currentData(), '预览缩放没存住'

print('\n=== 5. 恢复到标准字号 ===')
win.set_ui_font(S.DEFAULT_FONT_PT)
app.processEvents()
print('   已恢复 %d 号' % S.DEFAULT_FONT_PT)

print('\n✅ 界面缩放验收通过')
