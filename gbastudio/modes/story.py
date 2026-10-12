# -*- coding: utf-8 -*-
"""
story.py —— 剧情模式（时间轴）

定义了**模式接口**（其他模式照抄这个结构就行）：
    title / icon
    build_panels()   建自己的面板，返回 {位置: (标题, 控件)}
    on_activate()    切到这个模式时刷新
    on_selection()   时间轴选中片段时刷新属性
    on_delete_clip() 删除选中片段（Edit 菜单和 Delete 键会调）
    reload_scenes()  场景列表变化时刷新下拉框
"""
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QLineEdit, QPlainTextEdit, QCheckBox, QDoubleSpinBox,
                               QFormLayout, QScrollArea, QPushButton, QFrame, QMenu,
                               QToolBar, QSizePolicy,
                               QMessageBox, QInputDialog)

from modes.common import clear_layout
from core.project import (TRACK_TYPES, FONT_SIZES, MIN_DUR, Clip, Scene,
                          Character, Asset)

# 各轨道的"新片段"默认长度（秒）。语音片段会用真实音频时长覆盖
DEFAULT_DUR = {'text': 3.0, 'voice': 2.0, 'bg': 6.0, 'bgm': 20.0, 'se': 0.5,
               'fx': 0.5, 'char1': 6.0, 'char2': 6.0, 'char3': 6.0}

# 按钮 → 加哪种轨道
ADD_BUTTONS = [('＋台词', 'text'), ('＋立绘', 'char1'), ('＋语音', 'voice'),
               ('＋背景', 'bg'), ('＋音乐', 'bgm'), ('＋特效', 'fx'),
               ('＋切模式', 'fx', 'mode')]      # 第三个元素 = 想要的片段 kind



def prop_specs(track, project):
    """属性注册表：属性的控件全部由它生成，加属性不用改界面代码"""
    char_opts = [(c.id, c.name) for c in project.characters] or [('', '（无角色）')]
    bg_opts = [(a.path, a.path.split('/')[-1]) for a in project.assets_of('bg')] or [('', '（无背景）')]
    bgm_opts = [(a.path, a.path.split('/')[-1]) for a in project.assets_of('bgm')] or [('', '（无音乐）')]
    voice_opts = [(a.path, a.path.split('/')[-1]) for a in project.assets_of('voice')] or [('', '（无语音）')]
    se_opts = [(a.path, a.path.split('/')[-1]) for a in project.assets_of('se')] or [('', '（无音效）')]

    text_specs = [
        {'key': 'text', 'label': '内容', 'type': 'multiline', 'default': ''},
        {'key': 'voice', 'label': '语音（自动配对）', 'type': 'combo',
         'options': [('auto', '自动（按命名约定找）'), ('', '（无语音）')] + voice_opts,
         'default': 'auto'},
        {'key': 'wait', 'label': '推进方式', 'type': 'combo',
         'options': [('key', '等按键'), ('voice', '等语音结束'),
                     ('voice_or_key', '语音结束或按键'), ('time', '固定时长')],
         'default': 'voice_or_key'},
        {'key': 'style', 'label': '显示方式', 'type': 'combo',
         'options': [('say', '对话'), ('think', '心里想'), ('narrate', '旁白')], 'default': 'say'},
    ]
    return {
        'text':  [{'key': 'char', 'label': '角色', 'type': 'combo',
                   'options': [('', '（旁白）')] + char_opts, 'default': ''}] + text_specs,
        'char1': _char_specs(char_opts, 'left'),
        'char2': _char_specs(char_opts, 'right'),
        'char3': _char_specs(char_opts, 'center'),
        'bg':    [{'key': 'asset', 'label': '背景图', 'type': 'combo',
                   'options': bg_opts, 'default': bg_opts[0][0]},
                  {'key': 'trans', 'label': '切换方式', 'type': 'combo',
                   'options': [('cut', '硬切'), ('fade', '淡入')], 'default': 'fade'},
                  {'key': 'fade', 'label': '淡入时长(秒)', 'type': 'float', 'default': 0.4}],
        'voice': [{'key': 'asset', 'label': '语音文件', 'type': 'combo',
                   'options': voice_opts, 'default': voice_opts[0][0]},
                  {'key': 'auto', 'label': '自动匹配台词', 'type': 'check', 'default': True},
                  {'key': 'volume', 'label': '音量', 'type': 'float', 'default': 1.0}],
        'bgm':   [{'key': 'asset', 'label': '音乐文件', 'type': 'combo',
                   'options': bgm_opts, 'default': bgm_opts[0][0]},
                  {'key': 'loop', 'label': '循环', 'type': 'check', 'default': True},
                  {'key': 'fade', 'label': '淡入时长(秒)', 'type': 'float', 'default': 1.0}],
        'se':    [{'key': 'asset', 'label': '音效文件', 'type': 'combo',
                   'options': se_opts, 'default': se_opts[0][0]},
                  {'key': 'volume', 'label': '音量', 'type': 'float', 'default': 1.0}],
        'fx':    [{'key': 'kind', 'label': '类型', 'type': 'combo',
                   'options': [('fade', '淡入淡出'), ('shake', '震屏'), ('flash', '闪白'),
                               ('mode', '★ 切到关卡模式')],
                   'default': 'fade'},
                  {'key': 'mode', 'label': '方向', 'type': 'combo',
                   'options': [('in', '淡入'), ('out', '淡出')], 'default': 'in'},
                  {'key': 'color', 'label': '颜色', 'type': 'text', 'default': '#000000'}],
    }.get(track, [])


def _char_specs(char_opts, default_pos):
    return [
        {'key': 'char', 'label': '角色', 'type': 'combo', 'options': char_opts,
         'default': char_opts[0][0]},
        {'key': 'pose', 'label': '表情', 'type': 'text', 'default': 'normal'},
        {'key': 'pos', 'label': '位置', 'type': 'combo',
         'options': [('left', '左'), ('right', '右'), ('center', '中')], 'default': default_pos},
        {'key': 'action', 'label': '动作', 'type': 'combo',
         'options': [('show', '显示'), ('hide', '隐藏'), ('move', '移动')], 'default': 'show'},
    ]


class StoryMode:
    title = '剧情'
    icon = '💬'

    def __init__(self, win):
        self.win = win
        self.project = win.project
        self.selected = None
        self.scene_combo = None

    # ------------------------------------------------------------ 面板
    def build_panels(self):
        return {'timeline': ('时间轴', self._build_timeline_panel())}

    def _build_timeline_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)

        # 工具条用 QToolBar 而不是一排 QPushButton：
        #   一排按钮会把整个面板的**最小宽度**撑到 1200 多像素，
        #   于是时间轴面板根本拖不小（用户反馈的"小组件不能随意改大小"就是这个）。
        #   QToolBar 宽度不够时会自动收进右侧的 » 溢出菜单，最小宽度很小。
        bar = QToolBar()
        bar.setMovable(False)
        bar.setIconSize(QSize(16, 16))
        bar.addWidget(QLabel(' 场景 '))
        self.scene_combo = QComboBox()
        self.scene_combo.setMinimumWidth(120)
        self.scene_combo.currentIndexChanged.connect(self._scene_changed)
        bar.addWidget(self.scene_combo)

        def act(text, slot, tip):
            a = QAction(text, self.win)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            bar.addAction(a)
            return a

        act('＋', self.win.on_add_scene, '新建场景')
        act('－', lambda: self.win.on_del_scene(self.current_scene().name)
            if self.current_scene() else None, '删除当前场景')
        bar.addSeparator()
        for btn in ADD_BUTTONS:
            txt, track = btn[0], btn[1]
            want = btn[2] if len(btn) > 2 else None
            act(txt, lambda _=False, t=track, w=want: self.add_clip(t, w),
                '在播放头位置加一个「%s」片段（加到该类型的最后一条轨道）'
                % TRACK_TYPES.get(track, {}).get('title', track))
        bar.addSeparator()
        # ---- 建轨道：一个按钮，建的时候**给它起名字** ✗ ----
        # 用户的要求："这一行改成轨道名称增加的按钮"
        # ——原来只有"＋轨道"（选类型，名字是自动的 ✓）
        #   现在要点开就能填名字 ✓ 因为排一场戏会有好几条同类轨道 ✓
        #   全叫"背景""背景_2"根本分不清哪条是远山、哪条是云 ✓
        act('＋ 轨道', self.add_track_dialog, '新建一条轨道，并给它起个名字（远山 / 云 / 地面…）')
        # "－轨道"挪到时间轴右键菜单里 ✓
        # 工具条上留一排"加素材"的按钮就够了 ✓ 删除是低频且危险的操作 ✓
        # （删轨道会连片段一起删 ✓ 不该和"加"并排放在最容易误点的位置）

        # 信息标签也放进工具条，面板变窄时不会挤掉按钮
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        self.info = QLabel('')
        self.info.setStyleSheet('color:#8a8a99;')
        # 这行也是变长的（轨道数/片段数…），别让它把时间轴面板撑宽
        self.info.setMinimumWidth(1)
        bar.addWidget(self.info)
        lay.addWidget(bar)

        tv = self.win.timeline
        tv.setContextMenuPolicy(Qt.CustomContextMenu)
        tv.customContextMenuRequested.connect(self._timeline_menu)
        # 时间轴上点图层头 → 地图窗口跟着选中同一层（两边同步，不然会看串）
        tv.layerClicked.connect(self._on_timeline_layer_clicked)
        # 素材从资源库拖到轨道上 → 在这里变成片段
        tv.assetDropped.connect(self._on_asset_dropped)
        if not getattr(tv, '_story_connected', False):
            tv.clipSelected.connect(self.on_selection)      # 早先漏了这句，属性一直不跟着走
            tv.clipChanged.connect(self._on_clip_changed)
            tv._story_connected = True
        lay.addWidget(tv, 1)
        self.reload_scenes()
        return w

    # ------------------------------------------------------------ 生命周期
    def reload_scenes(self):
        if self.scene_combo is None:
            return
        cur = self.scene_combo.currentData()
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        for s in self.project.scenes:
            self.scene_combo.addItem('%s（%s）' % (s.name, s.kind), s.id)
        i = self.scene_combo.findData(cur)
        self.scene_combo.setCurrentIndex(max(0, i))
        self.scene_combo.blockSignals(False)
        self._refresh_timeline()

    def on_activate(self):
        self.project = self.win.project
        self.reload_scenes()
        self.build_inspector(None)

    def current_scene(self):
        if not self.project.scenes:
            return None
        if self.scene_combo is None:
            return self.project.scenes[0]
        sid = self.scene_combo.currentData()
        return self.project.scene(sid) or self.project.scenes[0]

    def _scene_changed(self):
        self._refresh_timeline()

    # ------------------------------------------------------- 从素材库拖进来
    def _on_asset_dropped(self, track_id, tsec, path):
        """把素材库里的素材放到轨道上 → 生一个片段

        【为什么"落到哪条轨道"很重要】
        素材类型和轨道类型必须对得上 ✗
            背景 → 背景轨 ✓   立绘 → 立绘轨 ✓   语音/BGM/音效 → 各自的音频轨 ✓
        放错了不能默默接受 ✓ 要告诉用户"这个该放哪" ✓
        ——不然会出现"拖了没反应"这种最难查的体验 ✓
        """
        import os as _os
        s = self.current_scene()
        if not s:
            return
        tk = s.track(track_id)
        if tk is None:
            return
        p = self.project
        name = _os.path.basename(path)
        # 素材在工程里的相对路径（拖过来的就是相对路径；兼容绝对路径）
        rel = path
        if _os.path.isabs(rel):
            try:
                rel = _os.path.relpath(rel, _os.path.dirname(self.win.file_path)).replace('\\', '/')
            except Exception:                               # noqa: BLE001
                rel = path
        a = p.find_asset(rel) or p.find_asset(path)
        kind = a.kind if a else ''

        # ---- 类型对不对得上 ----
        want_kind = {'bg': 'bg', 'voice': 'voice', 'bgm': 'bgm', 'se': 'se'}
        if tk.kind in want_kind:
            need = want_kind[tk.kind]
            if kind and kind != need:
                QMessageBox.information(
                    self.win, '放错轨道了',
                    '「%s」是%s素材，要放到「%s」轨道上。\n\n'
                    '（轨道类型是固定的：背景轨放背景、音频轨放音频，'
                    '立绘轨放立绘）'
                    % (name, kind, TRACK_TYPES.get(need, {}).get('title', need)))
                return
            if not kind:
                # 库里没登记过这个文件：按轨道类型硬塞（用户可能拖的是工程外的东西）
                self.win._status('这个素材不在资源库里，已按轨道类型放上去')
        elif tk.kind.startswith('char'):
            if kind and kind != 'char':
                QMessageBox.information(self.win, '放错轨道了',
                                        '「%s」不是立绘素材' % name)
                return
        elif tk.kind == 'fx':
            pass                                            # 特效轨什么都可能放
        else:
            QMessageBox.information(self.win, '这条轨道放不了素材',
                                    '「%s」轨道不接受从资源库拖进来的素材' % tk.name)
            return

        # ---- 造片段 ----
        props, ref, ckind = {}, '', ''
        dur = getattr(a, 'dur', 0.0) or 0.0
        if tk.kind == 'bg':
            props = {'trans': 'fade', 'fade': 0.4}
            ref = rel
            ckind = 'show'
            dur = dur or 5.0
        elif tk.kind.startswith('char'):
            # 立绘片段的 ref 存的是**角色 id** ✗ 不是文件路径 ✓
            # 路径长这样：assets/char/<角色名>/<表情>.png → 按名字找角色 ✓
            pose = 'normal'
            parts = rel.replace('\\', '/').split('/')
            cname = parts[-2] if len(parts) >= 2 else ''
            if parts:
                pose = parts[-1].rsplit('.', 1)[0] or 'normal'
            ch = None
            for c in p.characters:
                if c.name == cname or c.id == cname:
                    ch = c
                    break
            if ch is None and p.characters:
                ch = p.characters[0]
                self.win._status('这个立绘的目录名（%s）对不上角色表，先按「%s」放上去了'
                                 % (cname, ch.name))
            if ch is None:
                QMessageBox.information(self.win, '还没有角色',
                                        '先在「资源库 → 角色表」里加一个角色，再拖立绘')
                return
            pos = {'char1': 'left', 'char2': 'right', 'char3': 'center'}.get(tk.kind, 'left')
            props = {'pose': pose, 'pos': pos, 'action': 'show'}
            ref = ch.id
            ckind = 'show'
            dur = 5.0
        else:
            ref = rel
            ckind = 'play'
            dur = dur or 2.0

        c = Clip(tk.id, max(0.0, tsec), max(0.4, dur), ckind, ref, props)
        s.clips.append(c)
        s.duration = max(s.duration, c.start + c.dur + 1.0)
        self.win.dirty = True
        self._refresh_timeline()
        self.win.refresh_preview()
        self.win._status('把「%s」放到「%s」轨道的 %.2f 秒处' % (name, tk.name, c.start))

    def _on_timeline_layer_clicked(self, lid):
        """时间轴点了图层头 → 地图窗口选中它"""
        lp = getattr(self.win, 'layers_panel', None)
        if lp is None or lp.scene is not self.current_scene():
            return
        for i in range(lp.tree.topLevelItemCount()):
            from PySide6.QtCore import Qt as _Qt
            if lp.tree.topLevelItem(i).data(0, _Qt.UserRole) == lid:
                lp.tree.setCurrentItem(lp.tree.topLevelItem(i))
                break

    def _refresh_timeline(self):
        self.win.timeline.set_project(self.project, self.current_scene())
        self._refresh_info()
        self.win.refresh_preview()

    def _refresh_info(self):
        s = self.current_scene()
        if not s:
            self.info.setText('还没有场景')
            return
        # 报"有多少东西"，不报秒数 —— 作者关心的是句子数，不是时长
        lines = len([c for c in s.clips if self._kind(c) == 'text'])
        voiced = len([c for c in s.clips if self._kind(c) == 'voice'])
        tracks = len(s.tracks)
        self.info.setText('%d 条轨道 · %d 个片段 · 台词 %d 句 · 语音 %d 条'
                          % (tracks, len(s.clips), lines, voiced))

    def _kind(self, clip):
        s = self.current_scene()
        tk = s.track(clip.track) if s else None
        return tk.kind if tk else ''

    def _on_clip_changed(self):
        self.sync_voices()          # 台词动了 → 语音跟着走；语音被拖了 → 解除自动
        self.win.mark_dirty()
        self._refresh_info()
        self.win.refresh_preview()

    # ------------------------------------------------------------ 轨道
    def add_track_dialog(self):
        """新建一条轨道，并给它起名字

        ⚠ 类型还是要选的 ✗ 名字只是给人看的 ✓
          —— 轨道类型决定"能往上面放什么" ✓ 名字决定"人能不能看懂" ✓
        """
        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                                       QLineEdit, QComboBox)
        d = QDialog(self.win)
        d.setWindowTitle('新建轨道')
        d.setMinimumWidth(340)
        form = QFormLayout(d)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText('比如 远山 / 云 / 地面 / 前景 / 笑声')
        form.addRow('轨道名称', name_edit)
        kind_combo = QComboBox()
        for kind, meta in TRACK_TYPES.items():
            kind_combo.addItem(meta['title'], kind)
        form.addRow('类型', kind_combo)
        tip = QLabel('类型决定这条轨道能放什么素材；名字只给你自己看。\n'
                     '同一条轨道上的片段按先后顺序播；多条同类轨道可以同时演。')
        tip.setStyleSheet('color:#8a8a99; font-size:11px;')
        tip.setWordWrap(True)
        tip.setMinimumWidth(1)
        form.addRow('', tip)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        name_edit.setFocus()
        if d.exec() != QDialog.Accepted:
            return
        kind = kind_combo.currentData()
        name = name_edit.text().strip()
        self.add_track(kind, name=name)

    def add_track_menu(self):
        m = QMenu(self.win)
        for kind, meta in TRACK_TYPES.items():
            m.addAction('加一条「%s」轨道' % meta['title'],
                        lambda _=False, k=kind: self.add_track(k))
        m.exec(self.win.mapToGlobal(self.win.rect().center()))

    def add_track(self, kind, name=''):
        s = self.current_scene()
        if not s:
            return
        t = s.add_track(kind)
        if name:
            t.name = name
        # **新轨道要归到某一层** ✗
        # 不归层它就成了"野轨道" ✓ 时间轴靠兜底逻辑也能画出来 ✓
        # 但打包时说不清它在哪一层 ✓ ——所以建的时候就定下来：
        # 优先放进预览角上**当前选中的那一层** ✓ 没有就放第一层 ✓
        lid = None
        pk = getattr(self.win, 'layer_picker', None)
        L = pk.current_layer() if pk is not None else None
        if L is not None:
            lid = L.id
        elif getattr(s, 'layers', None):
            lid = s.layers[0].id
        if lid:
            s.assign_track(t.id, lid)
        self._refresh_timeline()
        self.win.mark_dirty()
        self.win._status('已新建轨道「%s」（%s，在图层 %s）'
                         % (t.name, t.id, s.layer(lid).name if lid else '—'))

    def remove_track(self):
        s = self.current_scene()
        if not s or not self.selected:
            self.win._status('先在时间轴上点一个片段，再删它所在的轨道')
            return
        tid = self.selected.track
        tk = s.track(tid)
        n = len([c for c in s.clips if c.track == tid])
        if QMessageBox.question(self.win, '删除轨道',
                                '删除轨道「%s」及其上的 %d 个片段？' % (tk.name if tk else tid, n)
                                ) != QMessageBox.Yes:
            return
        if not s.remove_track(tid):
            QMessageBox.warning(self.win, '不能删', '至少要留一条轨道')
            return
        self.selected = None
        self._refresh_timeline()
        self.build_inspector(None)
        self.win.mark_dirty()
        self.win._status('已删除轨道')

    # ------------------------------------------------------------ 增删片段
    def add_clip(self, kind, want=None):
        """
        在当前播放头位置加一个片段。

        want：想要的片段 kind。'fx' 轨道上有两种片段（特效 / 切模式），
        光看轨道分不出来，所以工具栏按钮可以指定一个。
        """
        s = self.current_scene()
        if not s:
            QMessageBox.information(self.win, '没有场景', '先新建一个场景')
            return
        tk = s.first_track(kind) or s.add_track(kind)
        t = self.win.timeline.playhead
        dur = DEFAULT_DUR.get(kind, 3.0)
        props, ref, ckind = {}, '', want or ''
        p = self.project

        if kind == 'text':
            c = p.characters[0] if p.characters else None
            props = {'text': '（新台词）', 'voice': 'auto', 'wait': 'voice_or_key', 'style': 'say'}
            ref = c.id if c else ''
        elif kind.startswith('char'):
            c = p.characters[0] if p.characters else None
            pos = {'char1': 'left', 'char2': 'right', 'char3': 'center'}.get(kind, 'left')
            props = {'pose': 'normal', 'pos': pos, 'action': 'show'}
            ref = c.id if c else ''
        elif kind == 'bg':
            a = p.assets_of('bg')
            props = {'trans': 'fade', 'fade': 0.4}
            ref = a[0].path if a else ''
        elif kind == 'voice':
            a = p.assets_of('voice')
            props = {'auto': True, 'volume': 1.0}
            ref = a[0].path if a else ''
            if a and a[0].dur > 0:
                dur = a[0].dur
        elif kind == 'bgm':
            a = p.assets_of('bgm')
            props = {'loop': True, 'fade': 1.0}
            ref = a[0].path if a else ''
            # 音乐默认铺到"内容末尾"，不然会出现一条比整段剧情还长的音乐条
            end = max([c.start + c.dur for c in s.clips] + [0.0])
            dur = max(6.0, end - t) if end > t else 10.0
        elif kind == 'se':
            a = p.assets_of('se')
            props = {'volume': 1.0}
            ref = a[0].path if a else ''
            dur = max(0.3, a[0].dur if a else 0.5)
        elif kind == 'fx':
            if want == 'mode':
                # P10：切玩法。放在 fx 轨上 —— 它本来就是"非画面事件"的轨道，
                # 触发方式（到时间就执行）和特效一样，没必要单开一条。
                props = {'kind': 'mode', 'to': 'level'}
                dur = 0.2
            else:
                props = {'kind': 'fade', 'mode': 'in', 'color': '#000000'}

        clip = Clip(tk.id, round(t, 2), dur, ckind, ref, props)
        s.clips.append(clip)
        s.duration = max(s.duration, clip.start + clip.dur + 1)
        self._refresh_timeline()
        self.on_selection(clip)
        self.win.mark_dirty()
        self.win._status('已在 %.2f 秒给轨道「%s」加了片段，拖边缘可改长度' % (t, tk.name))

    def on_delete_clip(self):
        if not self.selected:
            self.win._status('先在时间轴上点一个片段')
            return
        s = self.current_scene()
        # 删台词时，它**自动生成的**语音片段一起删；手动放的语音不动
        kids = [c.id for c in s.clips if c.props.get('for') == self.selected.id]
        s.clips = [c for c in s.clips
                   if c.id != self.selected.id and c.id not in kids]
        self.selected = None
        self._refresh_timeline()
        self.win.timeline.rebuild()
        self.build_inspector(None)
        self.win.mark_dirty()
        self.win._status('已删除片段%s' % ('（连同 %d 条关联语音）' % len(kids) if kids else ''))

    def cut_clip(self):
        """在播放头处切开选中的片段 —— 剪辑软件里最常用的操作之一"""
        c = self.selected
        if not c:
            self.win._status('先选中一个片段')
            return
        t = self.win.timeline.playhead
        if not (c.start < t < c.start + c.dur):
            self.win._status('播放头不在这个片段里，先把播放头拖到片段中间')
            return
        left = Clip(c.track, c.start, t - c.start, c.kind, c.ref, dict(c.props))
        right = Clip(c.track, t, c.start + c.dur - t, c.kind, c.ref, dict(c.props))
        s = self.current_scene()
        s.clips = [x for x in s.clips if x.id != c.id] + [left, right]
        self.selected = right
        self._refresh_timeline()
        self.win.timeline.rebuild()
        self.on_selection(right)
        self.win.mark_dirty()
        self.win._status('已在 %.2f 秒切开' % t)

    def duplicate_clip(self):
        c = self.selected
        if not c:
            return
        s = self.current_scene()
        n = Clip(c.track, c.start + c.dur, c.dur, c.kind, c.ref, dict(c.props))
        s.clips.append(n)
        s.duration = max(s.duration, n.start + n.dur + 1)
        self._refresh_timeline()
        self.win.timeline.rebuild()
        self.on_selection(n)
        self.win.mark_dirty()

    def _timeline_menu(self, pos):
        tv = self.win.timeline
        item = tv.itemAt(pos)
        m = QMenu(self.win)
        if item is not None and hasattr(item, 'clip'):
            self.on_selection(item.clip)
            tv.scene_.clearSelection()
            item.setSelected(True)
            m.addAction('删除片段', self.on_delete_clip)
            m.addAction('复制一份', self.duplicate_clip)
            m.addAction('在播放头处切开', self.cut_clip)
            m.addSeparator()
            # 删轨道挪到这里了：它危险且低频，不该待在工具条上最容易误点的位置
            m.addAction('删除这条轨道（连同上面的片段）', self.remove_track)
        else:
            for txt, track in ADD_BUTTONS:
                m.addAction('在此处加%s' % txt.replace('＋', ''), 
                            lambda _=False, t=track: self.add_clip(t))
            m.addSeparator()
            m.addAction('新建轨道…（起名字）', self.add_track_dialog)
        m.exec(tv.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ 属性
    def on_selection(self, clip):
        self.selected = clip
        self.build_inspector(clip)

    def kind_of(self, clip):
        """片段所在轨道的类型（bg / text / voice …）"""
        s = self.current_scene()
        tk = s.track(clip.track) if s else None
        return tk.kind if tk else 'text'

    # ------------------------------------------------------------ 语音联动
    #
    #  一条台词 ↔ 一条语音。在属性里给台词选语音，时间轴上**自动**生成
    #  一条对齐的语音片段，台词移动它跟着走 —— 不用手动对时间。
    #
    #  怎么区分"台词动了"和"语音被手动拖了"：
    #  语音片段上记一个 sync_start（上次同步时台词的起点）。
    #      voice.start == sync_start  → 台词动了 → 把语音拉过去
    #      voice.start != sync_start  → 用户手动拖了语音 → 解除自动，不再跟随
    #  这是"自动为主、手动可用"的关键，不然一拖就被拉回去。
    # ------------------------------------------------------------
    def _voice_track(self):
        s = self.current_scene()
        if not s:
            return None
        tk = s.first_track('voice')
        if tk is None:
            tk = s.add_track('voice')
        return tk

    def linked_voice(self, text_clip):
        """找这条台词关联的语音片段"""
        s = self.current_scene()
        if not s:
            return None
        for c in s.clips:
            if self.kind_of(c) == 'voice' and c.props.get('for') == text_clip.id:
                return c
        return None

    def _auto_voice_for(self, text_clip):
        """
        '自动'模式：按命名约定给台词找一条语音。
        约定见文档：语音文件名以角色的 voice_prefix 开头（如 witch_0101）
        """
        s = self.current_scene()
        if not s:
            return None
        ch = self.project.character(text_clip.ref)
        if ch is None:
            return None
        used = {c.ref for c in s.clips if self.kind_of(c) == 'voice'}
        pref = ch.voice_prefix or (ch.id + '_')
        for a in self.project.assets_of('voice'):
            base = os.path.basename(a.path)
            if base.startswith(pref) and a.path not in used:
                return a
        return None

    def apply_voice(self, text_clip, value):
        """
        台词属性里"语音"那一栏变了 → 同步时间轴。
        value: 'auto'（按命名约定找）/ ''（取消）/ 语音文件的相对路径
        """
        s = self.current_scene()
        if not s:
            return
        tk = self._voice_track()
        cur = self.linked_voice(text_clip)
        asset = None

        if value == 'auto':
            asset = self._auto_voice_for(text_clip)
            if asset is None and cur is None:
                ch = self.project.character(text_clip.ref)
                self.win._status('自动匹配：没找到以「%s」开头的语音文件'
                                 % (ch.voice_prefix if ch else '?'))
                return
        elif value:
            asset = self.project.find_asset(value) or Asset('voice', value, '', 0, 0, 0.0)

        if asset is None:                       # 选成空 → 删掉关联的语音片段
            if cur is not None:
                s.clips = [c for c in s.clips if c.id != cur.id]
                self.win._status('已移除这条台词关联的语音片段')
                self._refresh_timeline()
            return

        dur = asset.dur if asset.dur > 0 else max(0.4, text_clip.dur)
        if cur is None:
            cur = Clip(tk.id, text_clip.start, dur, 'play', asset.path,
                       {'auto': True, 'volume': 1.0})
            s.clips.append(cur)
            self.win._status('已在时间轴生成语音片段「%s」（%.1f 秒）'
                             % (os.path.basename(asset.path), dur))
        else:
            cur.ref = asset.path
            cur.start = text_clip.start
            cur.dur = dur
            self.win._status('语音已换成「%s」' % os.path.basename(asset.path))
        cur.props['for'] = text_clip.id
        cur.props['sync_start'] = text_clip.start
        text_clip.props['voice'] = value
        s.duration = max(s.duration, cur.start + cur.dur + 1)
        self._refresh_timeline()

    def sync_voices(self):
        """
        台词动了 → 关联的语音跟着走；语音被手动拖了 → 解除自动。
        （时间轴每次有改动都会调一次）
        """
        s = self.current_scene()
        if not s:
            return
        changed = False
        for c in list(s.clips):
            if self.kind_of(c) != 'voice' or not c.props.get('for'):
                continue
            parent = next((t for t in s.clips if t.id == c.props['for']), None)
            if parent is None:                  # 台词被删了：语音留着，转为手动
                c.props.pop('for')
                c.props.pop('sync_start', None)
                changed = True
                continue
            if abs(c.start - c.props.get('sync_start', c.start)) > 0.01:
                # 用户手动拖过语音 → 解除自动，尊重他的调整
                c.props.pop('for')
                c.props.pop('sync_start', None)
                changed = True
                self.win._status('语音片段被手动调整过，已解除自动跟随')
            elif abs(c.start - parent.start) > 0.01:
                c.start = parent.start          # 台词动了，把语音拉过去
                c.props['sync_start'] = parent.start
                changed = True
        if changed:
            self._refresh_timeline()

    def build_inspector(self, clip):
        body = self.win.inspector_body
        # 清空旧的属性。
        # 注意要**递归**清理：属性表是嵌套的 QFormLayout（body.addLayout(form)），
        # 只处理 it.widget() 的话，布局和它里面的控件会留在原地，
        # 于是每切一次片段就叠一层 —— 用户看到的"右上文字重叠"就是这个。
        clear_layout(body)

        if clip is None:
            lab = QLabel('在时间轴上点一个片段就能改它的属性。\n\n'
                         '· 「＋台词 / ＋立绘 / ＋语音」在播放头处加片段\n'
                         '· 拖片段左右**边缘**可以直接改长度\n'
                         '· 拖片段移动位置，会**自动吸附**到其它片段的首尾\n'
                         '· 点最上面那条可以移动播放头\n'
                         '· 右键片段：删除 / 复制 / 切开\n'
                         '· Ctrl+滚轮 缩放时间轴')
            lab.setStyleSheet('color:#8a8a99;')
            lab.setWordWrap(True)
            body.addWidget(lab)
            body.addStretch(1)
            return

        kind = self.kind_of(clip)
        s = self.current_scene()
        tk = s.track(clip.track) if s else None
        ordn = 0
        if kind == 'text':
            marks = [t for _, t in self.win.timeline.dialogue_marks()]
            for i, t0 in enumerate(marks):
                if abs(t0 - clip.start) < 1e-6:
                    ordn = i + 1
                    break
        head = QLabel('%s%s · %s' % (('第 %d 句 · ' % ordn) if ordn else '',
                                     tk.name if tk else kind, clip.id))
        head.setStyleSheet('color:#ffd166; font-weight:bold;')
        body.addWidget(head)
        sub = QLabel('轨道 %s　（下面这些是排布用，不用管秒数）' % clip.track)
        sub.setStyleSheet('color:#8a8a99;')
        body.addWidget(sub)
        # 这两行文字长度会变（id、轨道名），**不能让它们决定面板的最小宽度** ——
        # QLabel 默认的最小宽 = 整行文字宽，结果属性栏就缩不到 300 像素以下，
        # 往左拖的时候布局就乱了（用户反馈的"左右拖动显示会出错"）。
        # 自动换行 + 把最小宽压到 1 像素，文字长了就换行，面板爱多窄就多窄。
        for lab in (head, sub):
            lab.setWordWrap(True)
            lab.setMinimumWidth(1)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        body.addWidget(line)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        # 面板拖窄时，标签自动挪到输入框**上方**（而不是硬撑着把面板顶宽）
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for spec in prop_specs(kind, self.project):
            wdg = self._make_widget(spec, clip)
            if wdg:
                form.addRow(spec['label'], wdg)
        body.addLayout(form)

        sp = QDoubleSpinBox()
        sp.setRange(MIN_DUR, 999)
        sp.setSingleStep(0.1)
        sp.setValue(clip.dur)
        sp.valueChanged.connect(lambda v: self._set_dur(clip, v))
        f2 = QFormLayout()
        f2.setRowWrapPolicy(QFormLayout.WrapLongRows)
        f2.addRow('时长(秒)', sp)
        body.addLayout(f2)
        body.addStretch(1)

    def _set_dur(self, clip, v):
        clip.dur = float(v)
        self._refresh_timeline()
        self.win.timeline.rebuild()
        self.win.mark_dirty()

    def _make_widget(self, spec, clip):
        key, kind = spec['key'], spec['type']
        val = clip.props.get(key, spec.get('default'))
        if kind == 'combo':
            cb = QComboBox()
            for v, label in spec['options']:
                cb.addItem(label, v)
            cb.setCurrentIndex(max(0, cb.findData(val)))
            # 下拉框默认的**最小宽度 = 最长选项的宽度** —— 语音文件名一长，
            # 属性栏就被撑到缩不小（往左拖会乱）。改成"按 8 个字符算最小宽度"，
            # 选项太长时它会自己截断显示，面板想多窄就多窄。
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(8)
            cb.currentIndexChanged.connect(
                lambda _=0, k=key, c=cb: self._set(clip, k, c.currentData()))
            return cb
        if kind == 'multiline':
            te = QPlainTextEdit(str(val or ''))
            te.setFixedHeight(64)
            te.textChanged.connect(lambda k=key, t=te: self._set(clip, k, t.toPlainText()))
            return te
        if kind == 'check':
            chk = QCheckBox()
            chk.setChecked(bool(val))
            chk.toggled.connect(lambda v, k=key: self._set(clip, k, v))
            return chk
        if kind == 'float':
            sp = QDoubleSpinBox()
            sp.setRange(0, 999)
            sp.setSingleStep(0.1)
            sp.setDecimals(2)
            sp.setValue(float(val or 0))
            sp.valueChanged.connect(lambda v, k=key: self._set(clip, k, v))
            return sp
        ed = QLineEdit(str(val or ''))
        ed.textChanged.connect(lambda t, k=key: self._set(clip, k, t))
        return ed

    def _set(self, clip, key, value):
        # 台词的"语音"这一栏要**同步时间轴**：自动生成 / 更新 / 删除关联的语音片段。
        # 其余属性只是记个值，改完重画就行。
        if key == 'voice' and self.kind_of(clip) == 'text':
            self.apply_voice(clip, value)
            self.win.timeline.rebuild()
            self.build_inspector(clip)      # 重建，让下拉框显示**实际选中**的文件
            self._refresh_info()            # （"自动"匹配到的文件也要看得见）
            self.win.mark_dirty()
            return
        clip.props[key] = value
        self.win.timeline.rebuild()
        self._refresh_info()
        self.win.mark_dirty()
