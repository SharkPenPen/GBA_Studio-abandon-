#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
layers_panel.py —— 地图窗口（左侧的图层列表）

【它是什么】
这是"这个关卡有哪几层"的窗口 ✗ 也是以后**地图绘制**的地方 ✓

【为什么图层不能增删】
图层数 = **显示模式给的硬件层数** ✓
    模式 0 → BG0 BG1 BG2 BG3 + OBJ
    模式 1 → BG0 BG1 BG2(仿射) + OBJ
    模式 2 → BG2 BG3(仿射) + OBJ
    模式 3/4/5 → BG2(位图) + OBJ
这是**硬件事实** ✓ 不是软件限制 ✓ 所以界面上**没有"加图层"按钮** ✓
能改的是：**用途名**（"远山""云""地面"…）、可见性、滚动速度（视差）

【和轨道的关系】
图层里装**轨道** ✓ 轨道想加多少加多少 ✓
同一图层里的多条轨道 → **打包时重叠成一张画面** ✓ 上下顺序 = 重叠顺序
——所以这个窗口只负责"层"，"层里有什么"在时间轴上看 ✓
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTreeWidget, QTreeWidgetItem, QPushButton,
                               QLineEdit, QCheckBox)


class LayersPanel(QWidget):
    """地图窗口：列出当前场景的图层"""

    layer_selected = Signal(str)          # 选中了哪一层（layer id）
    layer_renamed = Signal(str, str)      # (layer id, 新名字)
    layer_visible = Signal(str, bool)     # (layer id, 可见)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.scene = None
        self._loading = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # ---- 顶栏：说明 + 模式 ----
        top = QHBoxLayout()
        self.title = QLabel('地图')
        self.title.setStyleSheet('color:#f0f0f6; font-weight:600;')
        top.addWidget(self.title)
        top.addStretch(1)
        self.mode_label = QLabel('')
        self.mode_label.setStyleSheet('color:#8a8a99; font-size:11px;')
        top.addWidget(self.mode_label)
        lay.addLayout(top)

        self.hint = QLabel('')
        self.hint.setStyleSheet('color:#6f6f7f; font-size:11px;')
        self.hint.setWordWrap(True)
        self.hint.setMinimumWidth(1)
        lay.addWidget(self.hint)

        # ---- 图层树 ----
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['图层', '类型', '轨道'])
        self.tree.setColumnWidth(0, 130)
        self.tree.setColumnWidth(1, 66)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setStyleSheet("""
            QTreeWidget { background:#14141a; color:#c8c8d4; alternate-background-color:#191920; }
            QTreeWidget::item { padding:3px; }
            QTreeWidget::item:selected { background:#33291a; color:#ffd166; }
        """)
        self.tree.setAlternatingRowColors(True)
        self.tree.currentItemChanged.connect(self._on_current)
        self.tree.itemDoubleClicked.connect(self._on_double)
        lay.addWidget(self.tree, 1)

        # ---- 底栏：改用途名（图层不能增删，只能改名） ----
        bot = QHBoxLayout()
        bot.addWidget(QLabel('用途名'))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('比如 远山 / 云 / 地面 / 前景')
        self.name_edit.setMinimumWidth(1)
        self.name_edit.editingFinished.connect(self._on_rename)
        bot.addWidget(self.name_edit, 1)
        lay.addLayout(bot)

        self.foot = QLabel('')
        self.foot.setStyleSheet('color:#6f6f7f; font-size:11px;')
        self.foot.setWordWrap(True)
        self.foot.setMinimumWidth(1)
        lay.addWidget(self.foot)

    # ------------------------------------------------------------------ 数据
    def set_project(self, project, scene=None):
        self.project = project
        self.scene = scene
        self.reload()

    def reload(self):
        """按当前场景的图层重建列表"""
        self._loading = True
        self.tree.clear()
        s = self.scene
        if s is None or not getattr(s, 'layers', None):
            self.mode_label.setText('')
            self.hint.setText('这个场景没有图层（只有剧情场景才有时间轴和图层）')
            self.foot.setText('')
            self._loading = False
            return

        mode = 3
        if self.project is not None:
            mode = int(self.project.settings.get('video_mode', 3))
        n_bg = len([L for L in s.layers if L.kind != 'obj'])
        self.mode_label.setText('模式 %d · %d 层' % (mode, n_bg))
        self.hint.setText('图层数由显示模式决定（硬件就是这么多层），不能增删；'
                          '能改的是用途名、可见性、滚动速度。')

        for L in s.layers:
            it = QTreeWidgetItem(['%s  %s' % ('●' if L.visible else '○', L.name),
                                  L.kind_title, str(len(L.tracks))])
            it.setData(0, Qt.UserRole, L.id)
            it.setToolTip(0, '图层 %s —— 里面装着 %d 条轨道；'
                             '同层轨道在打包时会重叠成一张画面'
                          % (L.name, len(L.tracks)))
            if not L.visible:
                it.setForeground(0, Qt.gray)
            self.tree.addTopLevelItem(it)

        # 记住上次选中的层
        want = getattr(self, '_selected', None)
        row = 0
        for i in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(i).data(0, Qt.UserRole) == want:
                row = i
                break
        self.tree.setCurrentItem(self.tree.topLevelItem(row))
        self._loading = False
        self._sync_name_edit()

    # ------------------------------------------------------------------ 交互
    def current_layer(self):
        it = self.tree.currentItem()
        if it is None:
            return None
        lid = it.data(0, Qt.UserRole)
        return self.scene.layer(lid) if self.scene else None

    def _sync_name_edit(self):
        L = self.current_layer()
        self.name_edit.setText(L.name if L else '')
        self.name_edit.setEnabled(L is not None)
        if L is not None:
            self.foot.setText('「%s」是%s，装着 %d 条轨道。'
                              % (L.name, L.kind_title, len(L.tracks)))
        else:
            self.foot.setText('')

    def _on_current(self, cur, prev):
        if self._loading or cur is None:
            return
        self._selected = cur.data(0, Qt.UserRole)
        self._sync_name_edit()
        self.layer_selected.emit(self._selected)

    def _on_double(self, it, col):
        """双击可见性那一列 → 切换显示/隐藏（和剪辑软件一致）"""
        if col != 0:
            return
        L = self.current_layer()
        if L is None:
            return
        L.visible = not L.visible
        self.layer_visible.emit(L.id, L.visible)
        self.reload()

    def _on_rename(self):
        """改用途名（只改显示名，不改图层数）"""
        L = self.current_layer()
        if L is None:
            return
        new = self.name_edit.text().strip()
        if not new or new == L.name:
            return
        L.name = new
        self.reload()
        self.layer_renamed.emit(L.id, new)
