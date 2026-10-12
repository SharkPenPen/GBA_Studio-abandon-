# -*- coding: utf-8 -*-
"""临时：启动后自动选中一个片段，用于截图确认检查器正常"""
import os
import sys
sys.path.insert(0, r"D:\GitHud\GBA_AI\gbastudio")
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow

win = MainWindow()
win.resize(1360, 860)
win.show()
app.processEvents()

mode = win.modes[0]
mode.on_activate()
s = win.project.scenes[0]
# 选中背景轨的第一个片段（就是用户截图里那个场景）
bg = [c for c in s.clips if c.track == 'bg']
if bg:
    mode.on_selection(bg[0])
    for it in win.timeline._clip_items:
        if it.clip is bg[0]:
            it.setSelected(True)
app.processEvents()

def fix():
    from PySide6.QtCore import Qt
    docks = [d for _, d in win.mode_docks]
    win.resizeDocks(docks + [win.dock_log], [max(340, win.height() // 2)] * len(docks) + [120], Qt.Vertical)
    win.resizeDocks([win.dock_assets, win.dock_inspector], [240, 320], Qt.Horizontal)

from PySide6.QtCore import QTimer
QTimer.singleShot(80, fix)
sys.exit(app.exec())
