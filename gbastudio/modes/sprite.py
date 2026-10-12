# -*- coding: utf-8 -*-
"""
modes/sprite.py —— 「精灵」模式（P9）

左边一列是动画，中间是帧序列，右边（属性栏）是这一帧停几帧。
点「▶ 预览」会**按真实速度播一遍** —— 这是这个模式存在的理由：
动画对不对，看着播一遍就知道，看数字看不出来。

和数据的关系：
    帧的来源是资源库里 kind == 'sprite' 的素材（右键归类为「精灵」）
    动画存在工程文件里 → 导出时进 assets.json → 生成 anim_data.c
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon, QAction, QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QComboBox, QSpinBox,
                               QToolBar, QSizePolicy, QPushButton, QFormLayout,
                               QLineEdit, QCheckBox, QInputDialog, QMessageBox)

from modes.common import clear_layout
from core.anim import Animation
from core.project import new_id

PREVIEW_SCALE = 6           # 预览放大倍数（16x24 的精灵放到 96x144，看得清）


class SpritePreview(QLabel):
    """按真实速度播放当前动画的小窗口"""

    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet('background:#101014;')
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.step = 0
        self.left = 0
        self.pix = []
        self.setText('（点「▶ 预览」播放）')
        self.setStyleSheet('background:#101014; color:#8a8a99;')

    def set_anim(self, an):
        """换动画：把每一帧的图读出来（按工程目录解析相对路径）"""
        self.timer.stop()
        self.pix = []
        self.step = 0
        self.left = 0
        if not an or not an.frames:
            self.setText('（这个动画还没有帧）')
            return
        base = self.mode.proj_dir
        for fr in an.frames:
            p = fr.path if base is None else __import__('os').path.join(base, fr.path)
            pm = QPixmap(p)
            if pm.isNull():
                pm = QPixmap(16, 24)
                pm.fill(QColor('#3a3a44'))
            self.pix.append(pm.scaled(pm.width() * PREVIEW_SCALE,
                                      pm.height() * PREVIEW_SCALE,
                                      Qt.KeepAspectRatio, Qt.FastTransformation))
        self.show_step(0)
        self.setText('')

    def show_step(self, i):
        if not self.pix:
            return
        self.step = i % len(self.pix)
        self.setPixmap(self.pix[self.step])
        self.left = max(1, self.mode_cur_dur())

    def mode_cur_dur(self):
        an = self.mode.current()
        if not an or not an.frames:
            return 6
        return max(1, an.frames[self.step % len(an.frames)].dur)

    def play(self):
        an = self.mode.current()
        if not an or not an.frames:
            self.setText('（这个动画还没有帧）')
            return
        self.set_anim(an)
        self.left = max(1, self.mode_cur_dur())
        self.timer.start(1000 // 60)       # 60 帧/秒，和实机一样

    def stop(self):
        self.timer.stop()

    def on_tick(self):
        """按"这一帧停几帧"倒计时 —— 和引擎里的逻辑一模一样"""
        self.left -= 1
        if self.left > 0:
            return
        an = self.mode.current()
        if not an or not an.frames:
            self.timer.stop()
            return
        nxt = self.step + 1
        if nxt >= len(an.frames):
            if not an.loop:
                self.timer.stop()
                return
            nxt = 0
        self.show_step(nxt)


class SpriteMode:
    title = '精灵'
    icon = '👤'

    def __init__(self, win):
        self.win = win
        self.preview = None
        self.anim_list = None
        self.frame_list = None
        self.asset_combo = None

    # ------------------------------------------------------------ 工具
    @property
    def proj_dir(self):
        fp = getattr(self.win, 'file_path', '')
        return __import__('os').path.dirname(fp) if fp else None

    def animations(self):
        return self.win.project.animations

    def current(self):
        i = self.anim_list.currentRow() if self.anim_list else -1
        a = self.animations()
        return a[i] if 0 <= i < len(a) else None

    def sprite_assets(self):
        return [a for a in self.win.project.assets if a.kind == 'sprite']

    # ------------------------------------------------------------ 面板
    def build_panels(self):
        return {'timeline': ('精灵动画', self._build_panel())}

    def _build_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)

        bar = QToolBar()
        bar.setMovable(False)

        def act(text, slot, tip):
            a = QAction(text, self.win)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            bar.addAction(a)
            return a

        act('＋动画', self.on_add_anim, '新建一个动画（比如"走路""攻击""受伤"）')
        act('－动画', self.on_del_anim, '删掉当前动画')
        act('重命名', self.on_rename_anim, '给动画改个名字（名字只是给人看的）')
        self.loop_box = QCheckBox('循环')
        self.loop_box.setToolTip('勾上：播完最后一帧回到第一帧')
        self.loop_box.stateChanged.connect(self.on_loop_changed)
        bar.addWidget(self.loop_box)
        bar.addSeparator()
        self.play_btn = QPushButton('▶ 预览')
        self.play_btn.setToolTip('按真实速度（60 帧/秒）播一遍')
        self.play_btn.clicked.connect(self.on_play)
        bar.addWidget(self.play_btn)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        self.info = QLabel('')
        self.info.setStyleSheet('color:#8a8a99;')
        self.info.setMinimumWidth(1)
        bar.addWidget(self.info)
        lay.addWidget(bar)

        row = QHBoxLayout()
        # 左：动画列表
        left = QVBoxLayout()
        left.addWidget(QLabel('动画'))
        self.anim_list = QListWidget()
        self.anim_list.setMaximumWidth(160)
        self.anim_list.currentRowChanged.connect(self.on_pick_anim)
        left.addWidget(self.anim_list)
        row.addLayout(left)

        # 中：帧序列
        mid = QVBoxLayout()
        mid.addWidget(QLabel('帧（从上到下播放）'))
        self.frame_list = QListWidget()
        self.frame_list.setViewMode(QListWidget.IconMode)
        self.frame_list.setIconSize(QPixmap(16, 24).size() * 2)
        self.frame_list.setResizeMode(QListWidget.Adjust)
        self.frame_list.setSpacing(4)
        self.frame_list.currentRowChanged.connect(self.on_pick_frame)
        self.frame_list.setToolTip('每张图下面写的是"停几帧"（60 帧 = 1 秒）')
        mid.addWidget(self.frame_list, 1)
        fbar = QHBoxLayout()
        self.asset_combo = QComboBox()
        self.asset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.asset_combo.setMinimumContentsLength(8)
        self.asset_combo.setToolTip('从资源库里的「精灵」素材里挑一帧加进来')
        fbar.addWidget(self.asset_combo, 1)
        b = QPushButton('＋帧')
        b.clicked.connect(self.on_add_frame)
        fbar.addWidget(b)
        b = QPushButton('－帧')
        b.clicked.connect(self.on_del_frame)
        fbar.addWidget(b)
        b = QPushButton('←')
        b.setToolTip('往前挪一格（调顺序）')
        b.clicked.connect(lambda: self.on_move_frame(-1))
        fbar.addWidget(b)
        b = QPushButton('→')
        b.setToolTip('往后挪一格')
        b.clicked.connect(lambda: self.on_move_frame(1))
        fbar.addWidget(b)
        mid.addLayout(fbar)
        row.addLayout(mid, 1)

        # 右：预览
        right = QVBoxLayout()
        right.addWidget(QLabel('预览（60 帧/秒）'))
        self.preview = SpritePreview(self)
        right.addWidget(self.preview)
        right.addStretch(1)
        row.addLayout(right)

        lay.addLayout(row, 1)
        self.reload()
        return w

    # ------------------------------------------------------------ 刷新
    def reload(self):
        if not self.anim_list:
            return
        keep = self.anim_list.currentRow()
        self.anim_list.blockSignals(True)
        self.anim_list.clear()
        for an in self.animations():
            self.anim_list.addItem('%s（%d 帧）' % (an.name, len(an.frames)))
        self.anim_list.blockSignals(False)
        if self.animations():
            self.anim_list.setCurrentRow(max(0, min(keep, len(self.animations()) - 1)))
        self.refresh_frames()
        self.refresh_assets()

    def refresh_assets(self):
        if not self.asset_combo:
            return
        self.asset_combo.clear()
        for a in self.sprite_assets():
            self.asset_combo.addItem(__import__('os').path.basename(a.path), a.path)
        if self.asset_combo.count() == 0:
            self.asset_combo.addItem('（资源库里还没有「精灵」素材）', '')

    def refresh_frames(self):
        an = self.current()
        if self.loop_box:
            self.loop_box.blockSignals(True)
            self.loop_box.setChecked(bool(an.loop) if an else False)
            self.loop_box.blockSignals(False)
        if self.frame_list:
            keep = self.frame_list.currentRow()
            self.frame_list.clear()
            if an:
                base = self.proj_dir
                import os
                for i, fr in enumerate(an.frames):
                    p = fr.path if base is None else os.path.join(base, fr.path)
                    pm = QPixmap(p)
                    icon = QIcon(pm) if not pm.isNull() else QIcon()
                    it = QListWidgetItem(icon, '%d帧' % fr.dur)
                    it.setToolTip('%s\n停 %d 帧（%.2f 秒）'
                                  % (os.path.basename(fr.path), fr.dur, fr.dur / 60.0))
                    self.frame_list.addItem(it)
                if an.frames:
                    self.frame_list.setCurrentRow(max(0, min(keep, len(an.frames) - 1)))
        if self.preview:
            self.preview.set_anim(an)
        self.refresh_info()

    def refresh_info(self):
        an = self.current()
        if not self.info:
            return
        if not an:
            self.info.setText('还没有动画 —— 点「＋动画」新建一个')
            return
        self.info.setText('%d 帧 · 一轮 %.2f 秒 · %s'
                          % (len(an.frames), an.total_frames() / 60.0,
                             '循环' if an.loop else '播一次'))

    # ------------------------------------------------------------ 操作
    def on_pick_anim(self, _row=None):
        self.refresh_frames()

    def on_pick_frame(self, row):
        an = self.current()
        if an and 0 <= row < len(an.frames) and self.preview:
            self.preview.show_step(row)
        self.build_inspector()

    def on_play(self):
        if self.preview:
            if self.preview.timer.isActive():
                self.preview.stop()
                self.play_btn.setText('▶ 预览')
            else:
                self.preview.play()
                self.play_btn.setText('■ 停止')

    def on_add_anim(self):
        name, ok = QInputDialog.getText(self.win, '新建动画', '名字', text='新动画')
        if not ok or not name.strip():
            return
        # 新动画：把当前选中的精灵素材当第一帧，省得建完是空的
        path = self.asset_combo.currentData() if self.asset_combo else ''
        an = Animation(name.strip(), loop=True, aid=new_id('a'))
        if path:
            an.add_frame(path, 6)
        self.animations().append(an)
        self.win.mark_dirty()
        self.reload()
        self.anim_list.setCurrentRow(len(self.animations()) - 1)

    def on_del_anim(self):
        an = self.current()
        if not an:
            return
        if QMessageBox.question(self.win, '删掉动画', '删掉「%s」？' % an.name) != QMessageBox.Yes:
            return
        self.animations().remove(an)
        self.win.mark_dirty()
        self.reload()

    def on_rename_anim(self):
        an = self.current()
        if not an:
            return
        name, ok = QInputDialog.getText(self.win, '重命名', '名字', text=an.name)
        if ok and name.strip():
            an.name = name.strip()
            self.win.mark_dirty()
            self.reload()

    def on_loop_changed(self, st):
        an = self.current()
        if an:
            an.loop = bool(st)
            self.win.mark_dirty()
            self.refresh_info()
            if self.preview:
                self.preview.set_anim(an)

    def on_add_frame(self):
        an = self.current()
        if not an:
            self.win._status('先新建一个动画')
            return
        path = self.asset_combo.currentData() if self.asset_combo else ''
        if not path:
            self.win._status('资源库里还没有「精灵」素材：先导入图片，右键归类为「精灵」')
            return
        an.add_frame(path, 6)
        self.win.mark_dirty()
        self.refresh_frames()
        self.frame_list.setCurrentRow(len(an.frames) - 1)

    def on_del_frame(self):
        an = self.current()
        r = self.frame_list.currentRow() if self.frame_list else -1
        if an and r >= 0:
            an.remove_frame(r)
            self.win.mark_dirty()
            self.refresh_frames()

    def on_move_frame(self, delta):
        an = self.current()
        r = self.frame_list.currentRow() if self.frame_list else -1
        if an and r >= 0 and an.move_frame(r, delta):
            self.win.mark_dirty()
            self.refresh_frames()
            self.frame_list.setCurrentRow(r + delta)

    # ------------------------------------------------------------ 属性栏
    def on_activate(self):
        self.reload()
        self.build_inspector()

    def build_inspector(self):
        """属性栏：当前帧停几帧（这是唯一需要敲数字的地方）"""
        body = self.win.inspector_body
        clear_layout(body)

        an = self.current()
        t = QLabel('精灵动画')
        t.setStyleSheet('color:#ffd166; font-weight:bold;')
        t.setWordWrap(True)
        t.setMinimumWidth(1)
        body.addWidget(t)

        if not an:
            lab = QLabel('左边点「＋动画」新建一个。\n\n'
                         '帧从资源库里的「精灵」素材里挑 ——\n'
                         '先「导入素材」，再右键归类为「精灵」。')
            lab.setStyleSheet('color:#8a8a99;')
            lab.setWordWrap(True)
            lab.setMinimumWidth(1)
            body.addWidget(lab)
            body.addStretch(1)
            return

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        ed = QLineEdit(an.name)
        ed.editingFinished.connect(lambda: self._rename_from(ed.text()))
        form.addRow('名字', ed)

        r = self.frame_list.currentRow() if self.frame_list else -1
        if 0 <= r < len(an.frames):
            sp = QSpinBox()
            sp.setRange(1, 600)
            sp.setValue(max(1, an.frames[r].dur))
            sp.setSuffix(' 帧')
            sp.setToolTip('这一帧停多少游戏帧（60 帧 = 1 秒）')
            sp.valueChanged.connect(lambda v, i=r: self._set_dur(i, v))
            form.addRow('第 %d 帧停' % (r + 1), sp)
        body.addLayout(form)

        hint = QLabel('\n「▶ 预览」按 60 帧/秒播一遍，和实机速度一致。\n'
                      '导出时动画会进 assets.json，编译脚本再生成 anim_data.c。')
        hint.setStyleSheet('color:#8a8a99;')
        hint.setWordWrap(True)
        hint.setMinimumWidth(1)
        body.addWidget(hint)
        body.addStretch(1)

    def _rename_from(self, name):
        an = self.current()
        if an and name.strip() and name.strip() != an.name:
            an.name = name.strip()
            self.win.mark_dirty()
            self.reload()

    def _set_dur(self, i, v):
        an = self.current()
        if an and 0 <= i < len(an.frames):
            an.frames[i].dur = int(v)
            self.win.mark_dirty()
            self.refresh_frames()
            self.frame_list.setCurrentRow(i)
