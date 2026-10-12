# -*- coding: utf-8 -*-
"""
modes/level.py —— 「关卡」模式（P8）

左边没有时间轴，而是一张**格子地图**：选一种图块，在格子上按住鼠标涂。
涂完保存工程，导出时地图会写成 level.txt 交给编译脚本。

这个模式的作用不只是"多个功能"，它是**验证多模式架构成不成立**：
    · 它没有时间轴、没有片段、没有轨道 —— 和剧情模式的数据完全不同
    · 它复用主窗口的停靠面板系统（build_panels 返回自己的面板）
    · 加它只改了 modes/__init__.py 里的一行

如果当初没做 P7 那次分层，这里就得回到主窗口里加一堆 if。
"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QAction
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                               QToolBar, QSizePolicy, QInputDialog, QMessageBox)

from modes.common import clear_layout
from core.level import Level, TILE_NAMES, TILE_COLORS, SOLID

CELL = 16                   # 一格画多大（像素）—— 和引擎里的图块尺寸一致，
                            # 15x10 格正好 240x160，一屏放得下不用滚动


class MapCanvas(QWidget):
    """格子画布：左键涂当前图块，右键设出生点"""

    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setToolTip('左键涂图块 · 右键设出生点 · 按住拖动可以连着涂')
        self.sync_size()

    def sync_size(self):
        """画布大小 = 地图大小 × 格子尺寸（不滚动，一屏看全）"""
        lv = self.mode.level
        self.setFixedSize(lv.w * CELL + 2, lv.h * CELL + 2)

    def paintEvent(self, ev):
        lv = self.mode.level
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#16161c'))
        for ty in range(lv.h):
            for tx in range(lv.w):
                t = lv.cells[ty][tx]
                r = QRect(tx * CELL, ty * CELL, CELL - 1, CELL - 1)
                p.fillRect(r, QColor(TILE_COLORS.get(t, '#2a2a30')))
                if t in SOLID:
                    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
                    p.drawRect(r)
        # 出生点：画个黄框
        sx, sy = lv.start
        p.setPen(QPen(QColor('#ffd166'), 2))
        p.drawRect(QRect(sx * CELL + 1, sy * CELL + 1, CELL - 3, CELL - 3))
        p.setPen(QPen(QColor('#8a8a99'), 1))
        p.drawRect(QRect(0, 0, lv.w * CELL, lv.h * CELL))

    def _cell(self, pos):
        return pos.x() // CELL, pos.y() // CELL

    def mousePressEvent(self, ev):
        tx, ty = self._cell(ev.position().toPoint())
        lv = self.mode.level
        if not lv.in_range(tx, ty):
            return
        if ev.button() == Qt.RightButton:
            if lv.get(tx, ty) in SOLID:
                self.mode.win._status('出生点不能放在墙或水里')
                return
            lv.start = (tx, ty)
            self.mode.win.mark_dirty()
        else:
            lv.paint(tx, ty, self.mode.current_tile)
            self.mode.win.mark_dirty()
        self.update()
        self.mode.refresh_info()

    def mouseMoveEvent(self, ev):
        if not (ev.buttons() & Qt.LeftButton):
            return
        tx, ty = self._cell(ev.position().toPoint())
        lv = self.mode.level
        if lv.in_range(tx, ty) and lv.cells[ty][tx] != self.mode.current_tile:
            lv.paint(tx, ty, self.mode.current_tile)
            self.update()
            self.mode.win.mark_dirty()
            self.mode.refresh_info()


class LevelMode:
    title = '关卡'
    icon = '🗺'

    def __init__(self, win):
        self.win = win
        self.current_tile = 1          # 默认拿墙开始涂
        self.canvas = None
        self.info = None

    # ------------------------------------------------------------ 面板
    def build_panels(self):
        # **地图不再是浮窗/停靠面板了** ✗
        # 用户的原话："关卡地图小组件放图层选择位置和预览并列不要浮窗了"
        # ——它现在挂在中央左侧那个槽里（和预览并排）✓ 见 side_widget() ✓
        return {}

    def side_widget(self):
        """中央左侧放什么 —— 关卡工作区放地图 ✓

        主窗口在切换工作区时会问一遍 ✓ 由工作区自己决定 ✓
        返回 None = 这一格空着（预览占满）✓
        """
        if not hasattr(self, '_side'):
            self._side = self._build_panel()
        return self._side

    def _build_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)

        bar = QToolBar()
        bar.setMovable(False)
        bar.addWidget(QLabel(' 画笔 '))
        self._tile_acts = []
        for t, name in sorted(TILE_NAMES.items()):
            a = QAction(name, self.win)
            a.setCheckable(True)
            a.setToolTip('涂「%s」%s' % (name, '（走不过去）' if t in SOLID else ''))
            a.triggered.connect(lambda _=False, k=t: self.set_tile(k))
            bar.addAction(a)
            self._tile_acts.append((t, a))
        bar.addSeparator()

        def act(text, slot, tip):
            a = QAction(text, self.win)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            bar.addAction(a)
            return a

        act('清空', self.on_clear, '整张地图清成地板（四边会重新补上墙）')
        act('改尺寸…', self.on_resize, '改地图大小（引擎目前只支持一屏，最大 15x10）')
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        self.info = QLabel('')
        self.info.setStyleSheet('color:#8a8a99;')
        self.info.setMinimumWidth(1)
        bar.addWidget(self.info)
        lay.addWidget(bar)

        self.canvas = MapCanvas(self)
        lay.addWidget(self.canvas, 0, Qt.AlignHCenter)
        hint = QLabel('左键涂图块 · 右键设出生点（黄框）· 地图存进工程，'
                      '导出时写成 level.txt 交给编译脚本')
        hint.setStyleSheet('color:#8a8a99;')
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch(1)
        self.set_tile(self.current_tile)
        self.refresh_info()
        return w

    # ------------------------------------------------------------ 操作
    def set_tile(self, t):
        self.current_tile = t
        for k, a in self._tile_acts:
            a.setChecked(k == t)

    def on_clear(self):
        lv = self.level
        lv.clear(0)
        for tx in range(lv.w):
            lv.cells[0][tx] = 1
            lv.cells[lv.h - 1][tx] = 1
        for ty in range(lv.h):
            lv.cells[ty][0] = 1
            lv.cells[ty][lv.w - 1] = 1
        lv.move_start_to_free()
        self.canvas.update()
        self.refresh_info()
        self.win.mark_dirty()

    def on_resize(self):
        lv = self.level
        n, ok = QInputDialog.getInt(self.win, '改地图大小', '宽（格子，5~15）',
                                    lv.w, 5, 15)
        if not ok:
            return
        m, ok = QInputDialog.getInt(self.win, '改地图大小', '高（格子，5~10）',
                                    lv.h, 5, 10)
        if not ok:
            return
        if n * CELL > 15 * CELL or m * CELL > 10 * CELL:
            QMessageBox.information(self.win, '先这样',
                                    '引擎目前只画一屏（15x10 格），\n'
                                    '更大的地图要等做完镜头滚动。')
        lv.resize(n, m)
        self.canvas.sync_size()
        self.canvas.update()
        self.build_inspector()
        self.refresh_info()
        self.win.mark_dirty()

    def refresh_info(self):
        lv = self.level
        counts = {}
        for ty in range(lv.h):
            for tx in range(lv.w):
                counts[lv.cells[ty][tx]] = counts.get(lv.cells[ty][tx], 0) + 1
        if self.info:
            self.info.setText('%d×%d · 出生点 %d,%d · %s'
                              % (lv.w, lv.h, lv.start[0], lv.start[1],
                                 '  '.join('%s %d' % (TILE_NAMES.get(k, k), v)
                                           for k, v in sorted(counts.items()))))

    # ------------------------------------------------------------ 生命周期
    @property
    def level(self):
        return self.win.project.level

    def on_activate(self):
        """切到这个模式时：画布尺寸对齐地图，右边属性栏换成关卡自己的说明"""
        if self.canvas:
            self.canvas.sync_size()
            self.canvas.update()
            self.refresh_info()
        self.build_inspector()

    def build_inspector(self):
        """
        关卡模式没有"选中的片段"，右边就放**说明 + 地图概况**。

        每个模式自己决定属性栏显示什么 —— 主窗口不用知道谁是谁。
        """
        from PySide6.QtWidgets import QFormLayout
        body = self.win.inspector_body
        clear_layout(body)

        lv = self.level
        title = QLabel('%s · %d×%d' % ('关卡地图', lv.w, lv.h))
        title.setStyleSheet('color:#ffd166; font-weight:bold;')
        title.setWordWrap(True)
        title.setMinimumWidth(1)
        body.addWidget(title)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.addRow('出生点', QLabel('%d, %d' % lv.start))
        for t, name in sorted(TILE_NAMES.items()):
            form.addRow(name, QLabel('走不过去' if t in SOLID else '可以走'))
        body.addLayout(form)

        hint = QLabel('\n左键涂图块，右键设出生点。\n'
                      '地图存在工程文件里，导出时写成 level.txt，\n'
                      '编译脚本再转成引擎认识的 C 数组。')
        hint.setStyleSheet('color:#8a8a99;')
        hint.setWordWrap(True)
        hint.setMinimumWidth(1)
        body.addWidget(hint)
        body.addStretch(1)
