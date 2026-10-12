#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
layer_picker.py —— 预览左上角那一排图层按钮

【长什么样】
    图层 [BG0][BG1][BG2][OBJ] [●]
    从左到右 = **从底到顶**（和 GBA 的 BG0…BG3 编号一致 ✓）

【为什么用按钮而不是下拉框】
用户的原话："图层选择横排的"、"按照 bg0 去写"
—— 图层的数量是**固定**的（模式给几层就几层 ✓）✓
   而且只有 2~5 个 ✓ 一眼全看得见比"点开下拉再选"快得多 ✓
   还能一眼看出**当前在哪层** ✓（下拉框收起来就看不见了）

【三种操作】
    单击   → 切换到这一层
    双击   → 改用途名（远山 / 云 / 地面…）
    右键   → 显示 / 隐藏这一层
    （右边还有一个眼睛 ✓ 一键切当前层的可见性 ✓ 这个最常用 ✓）
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QToolButton, QLabel,
                               QInputDialog)


class LayerPicker(QWidget):
    """预览左上角的图层选择器：一排小按钮 + 一个眼睛

    ⚠ 它是**浮层**（parent 是预览容器 ✓ 自己绝对定位在左上角 ✓）
      所以不能进任何 layout ✗ 否则会占掉预览的位置 ✓
    """

    layer_selected = Signal(str)
    layer_renamed = Signal(str, str)
    layer_visible = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.scene = None
        self._loading = False
        self._buttons = []              # [(Layer, QToolButton)]
        self._selected = None

        self.setObjectName('layer_picker')
        self.setStyleSheet("""
            QWidget#layer_picker {
                background: rgba(20, 20, 26, 205);
                border: 1px solid #33333f;
                border-radius: 4px;
            }
            QWidget#layer_picker QLabel { color: #9a9aa8; font-size: 11px; }
            QWidget#layer_picker QToolButton {
                background: #22222b; border: 1px solid #3a3a48;
                border-radius: 3px; padding: 1px 7px; color: #c8c8d4;
                font-size: 11px;
            }
            QWidget#layer_picker QToolButton:hover { border-color: #6a6a7c; color: #e6e6ee; }
            QWidget#layer_picker QToolButton:checked {
                background: #33291a; border-color: #c8892a; color: #ffd166;
            }
            QWidget#layer_picker QToolButton#eye {
                background: transparent; border: none; padding: 1px 3px;
                font-size: 13px;
            }
        """)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(5, 2, 4, 2)
        self.lay.setSpacing(3)

        lab = QLabel('图层')
        self.lay.addWidget(lab)
        self._label = lab

        self.eye = QToolButton()
        self.eye.setObjectName('eye')
        self.eye.setText('●')
        self.eye.setToolTip('显示 / 隐藏当前图层（隐藏的层不会出现在预览和导出里）')
        self.eye.clicked.connect(self._on_eye)
        # 眼睛放在最后，等按钮建完再插进去（见 reload）

    # ------------------------------------------------------------------ 数据
    def set_project(self, project, scene=None):
        self.project = project
        self.scene = scene
        self.reload()

    def _clear_buttons(self):
        """拆掉旧按钮

        ⚠ 两件事必须做，少一件都会**崩** ✗✓（踩过：播放时整个进程段错误）
            ① removeEventFilter —— 我在按钮上装了事件过滤器 ✓
               按钮被销毁而过滤器还挂在旧对象上 → 悬空指针 ✓
            ② deleteLater —— 光 setParent(None) 只是"孤儿"✓ 没销毁 ✓
               播放时每秒重建几十次 ✓ 很快就攒出问题 ✓
        """
        for _L, b in self._buttons:
            b.removeEventFilter(self)
            self.lay.removeWidget(b)
            b.setParent(None)
            b.deleteLater()
        self._buttons = []

    def _signature(self):
        """当前该显示成什么样（用来判断"要不要重建"）"""
        s = self.scene
        if s is None or not getattr(s, 'layers', None):
            return None
        return tuple((L.id, L.name, L.kind_title, len(L.tracks), L.visible)
                     for L in s.layers)

    def reload(self):
        """刷新按钮

        ⚠ **没变化就只同步选中态，不重建控件** ✗✓
        踩过：refresh_preview() 每帧都会调到这儿 ✓
        于是播放时每帧都在"销毁按钮 + 新建按钮" ✓
        几十帧之后进程直接段错误（0xC0000005）✓
        ——重建控件是**重操作** ✓ 不能放在每帧都会走的路径上 ✓
        """
        sig = self._signature()
        if sig is not None and sig == getattr(self, '_sig', '#'):
            self._sync()                     # 只是选中态可能变了
            return
        self._sig = sig
        self._loading = True
        self._clear_buttons()
        s = self.scene
        if s is None or not getattr(s, 'layers', None):
            self._label.setText('（无图层）')
            self.eye.setVisible(False)
            self._loading = False
            self.adjustSize()
            return
        self._label.setText('图层')
        self.eye.setVisible(True)
        for L in s.layers:
            b = QToolButton()
            b.setText(L.name)                 # BG0 / BG1 / BG2 / BG3 / OBJ
            b.setCheckable(True)
            b.setToolTip('%s · %s\n%d 条轨道\n单击切换 / 双击改名 / 右键显示隐藏'
                         % (L.name, L.kind_title, len(L.tracks)))
            b.clicked.connect(lambda _=False, lid=L.id: self._pick(lid))
            b.installEventFilter(self)
            b._layer_id = L.id
            self.lay.addWidget(b)
            self._buttons.append((L, b))
        self.lay.addWidget(self.eye)

        # 默认选中最底层（BG0）——排戏大多从背景开始
        want = self._selected
        ids = [L.id for L, _b in self._buttons]
        if want not in ids:
            want = ids[0] if ids else None
        self._selected = want
        self._loading = False
        self._sync()
        self.adjustSize()

    def _sync(self):
        for L, b in self._buttons:
            b.setChecked(L.id == self._selected)
            # 隐藏的层：按钮文字变灰，一眼看得出
            b.setStyleSheet('color:#5a5a68;' if not L.visible else '')
        L = self.current_layer()
        if L is not None:
            self.eye.setText('●' if L.visible else '○')
            self.eye.setStyleSheet('color:#ffd166;' if L.visible else 'color:#6f6f7f;')

    def current_layer(self):
        if self.scene is None or self._selected is None:
            return None
        return self.scene.layer(self._selected)

    def select_layer(self, lid):
        if self.scene is None or self.scene.layer(lid) is None:
            return False
        self._selected = lid
        self._sync()
        return True

    # ------------------------------------------------------------------ 交互
    def _pick(self, lid):
        if self._loading:
            return
        self._selected = lid
        self._sync()
        self.layer_selected.emit(lid)

    def eventFilter(self, obj, ev):
        """双击 = 改名；右键 = 显示/隐藏"""
        lid = getattr(obj, '_layer_id', None)
        if lid and ev.type() == ev.Type.MouseButtonDblClick:
            self._rename(lid)
            return True
        if lid and ev.type() == ev.Type.ContextMenu:
            L = self.scene.layer(lid) if self.scene else None
            if L is not None:
                L.visible = not L.visible
                self._sync()
                self.layer_visible.emit(L.id, L.visible)
            return True
        return super().eventFilter(obj, ev)

    def _rename(self, lid):
        L = self.scene.layer(lid) if self.scene else None
        if L is None:
            return
        txt, ok = QInputDialog.getText(self, '图层用途名',
                                       '给「%s」起个用途名（远山 / 云 / 地面 / 前景…）：'
                                       % L.name,
                                       text='' if L.name == L.id else L.name)
        if not ok:
            return
        name = txt.strip()
        if not name or name == L.name:
            return
        L.name = name
        self.reload()
        self.layer_renamed.emit(L.id, name)

    def _on_eye(self):
        L = self.current_layer()
        if L is None:
            return
        L.visible = not L.visible
        self._sync()
        self.layer_visible.emit(L.id, L.visible)
