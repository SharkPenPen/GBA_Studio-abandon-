# -*- coding: utf-8 -*-
"""
launcher.py —— 启动器（项目管理界面）

【界面参考】
照着 Pixel Game Maker MV 的"项目管理界面"做（它的帮助文档 01_03 写得很清楚）：

    ┌──────────────────────────────────────────────┐
    │ 最近的项目 │ 新建项目                     [帮助] │   ← 两个标签页
    ├──────────────────────────────────────────────┤
    │ 搜索项目…                                     │   ← 搜索框
    ├──────────────────────────────────────────────┤
    │ 魔女与少女                        ┌────────┐  │
    │ 最后修改 2026/10/09 18:01         │ 缩略图 │  │   ← 一行一个项目
    │ D:\\...\\魔女与少女.gbastudio        └────────┘  │
    └──────────────────────────────────────────────┘

**为什么要有这一层**：以前双击就进编辑器，哪怕是来看一眼也得先对着
一个空工程 ✗ 有了启动器之后：
    · 打开程序先看到"我有哪些项目"
    · 双击某一行才进编辑器（和 PGMMV 一样）
    · 新建项目在同一个窗口的第二个标签页里，不用再弹对话框

【缩略图怎么来的】不是让用户自己传图，而是**用工程自己渲染一张**：
拿第一幕 + 第一张背景，走和编辑器预览同一套渲染器（core.preview）。
所以缩略图 = 这个项目现在长什么样，改完剧情它会跟着变。
渲染结果缓存在工程目录下的 .thumb.png，按 .gbastudio 的修改时间判断要不要重做。
"""
import json
import os
import time

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QColor, QFont, QAction
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QLineEdit, QListWidget,
                               QListWidgetItem, QTabWidget, QFileDialog,
                               QMessageBox, QCheckBox, QFormLayout, QScrollArea,
                               QSizePolicy, QFrame)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 最近项目列表存哪：和编辑器设置同一个地方（%APPDATA%\GBAStudio）
def _appdata_dir():
    base = os.environ.get('GBASTUDIO_SETTINGS_DIR')
    if base:
        return base
    appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(appdata, 'GBAStudio')


RECENT_PATH = os.path.join(_appdata_dir(), 'recent.json')
RECENT_MAX = 20


class RecentStore:
    """最近打开的项目清单（名字/路径/上次打开时间/缩略图）"""

    def __init__(self, path=RECENT_PATH):
        self.path = path
        self.items = []
        self.load()

    def load(self):
        try:
            with open(self.path, encoding='utf-8') as f:
                d = json.load(f)
            self.items = [x for x in d.get('items', []) if isinstance(x, dict)]
        except Exception:                                  # noqa: BLE001
            self.items = []

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({'items': self.items[:RECENT_MAX]}, f, ensure_ascii=False, indent=2)

    def touch(self, proj_path, name=''):
        """打开/新建之后调一次：把它挪到最前面"""
        proj_path = os.path.abspath(proj_path)
        self.items = [x for x in self.items if os.path.abspath(x.get('path', '')) != proj_path]
        self.items.insert(0, {
            'path': proj_path,
            'name': name or os.path.splitext(os.path.basename(proj_path))[0],
            'opened': int(time.time()),
        })
        self.items = self.items[:RECENT_MAX]
        self.save()

    def forget(self, proj_path):
        proj_path = os.path.abspath(proj_path)
        self.items = [x for x in self.items if os.path.abspath(x.get('path', '')) != proj_path]
        self.save()


# ---------------------------------------------------------------------------
# 缩略图：用工程自己渲染一张（不是让用户传图）
# ---------------------------------------------------------------------------
THUMB_W, THUMB_H = 160, 120


def thumb_path_for(proj_path):
    return os.path.join(os.path.dirname(os.path.abspath(proj_path)), '.thumb.png')


def make_thumb(proj_path, log=None):
    """渲染并缓存缩略图，返回图片路径（失败返回 ''）。

    为什么要按修改时间判断缓存：渲染一次要解码立绘/背景（几百毫秒），
    启动器每次打开都重渲染会明显卡 ✗ 只在工程比缩略图新的时候重做。
    """
    thumb = thumb_path_for(proj_path)
    try:
        if os.path.isfile(thumb) and os.path.getmtime(thumb) >= os.path.getmtime(proj_path):
            return thumb
    except OSError:
        pass
    try:
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
        from core.project import Project
        from core.preview import PreviewRenderer
        p = Project.load(proj_path)
        if not p.scenes:
            return ''
        r = PreviewRenderer(p, os.path.dirname(os.path.abspath(proj_path)))
        scene = p.scenes[0]
        # 取"这一幕中间"的时刻：一般已经有一张背景、可能还有立绘，
        # 比 t=0 更能代表这个项目
        t = 1.0
        for c in sorted(scene.clips, key=lambda x: x.start):
            tk = scene.track(c.track)
            if tk and tk.kind == 'text':
                t = max(t, c.start + 0.6)
                break
        img = r.render(scene, t)
        img.save(thumb)
        return thumb
    except Exception as e:                                 # noqa: BLE001
        if log:
            log('缩略图生成失败（不影响打开）：%s' % e)
        return ''


# ---------------------------------------------------------------------------
# 项目行：一行 = 一个项目（名字 / 最后修改 / 路径 / 缩略图）
# ---------------------------------------------------------------------------
class ProjectRow(QWidget):
    def __init__(self, path, name='', opened=0, missing=False, parent=None):
        super().__init__(parent)
        self.proj_path = path
        self.setObjectName('projectRow')

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(2)

        title = QLabel(name or os.path.splitext(os.path.basename(path))[0])
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet('color:#f0f0f6;')
        col.addWidget(title)

        if missing:
            sub = QLabel('找不到这个文件（可能被移动或删掉了）')
            sub.setStyleSheet('color:#e07a7a;')
        else:
            try:
                mt = time.strftime('%Y/%m/%d %H:%M', time.localtime(os.path.getmtime(path)))
            except OSError:
                mt = '—'
            sub = QLabel('最后修改 %s' % mt)
            sub.setStyleSheet('color:#9a9aa8;')
        col.addWidget(sub)

        p = QLabel(path)
        p.setStyleSheet('color:#7a7a88; font-size:11px;')
        p.setToolTip(path)
        col.addWidget(p)
        lay.addLayout(col, 1)

        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setStyleSheet('background:#0b0b10; border:1px solid #33333f;')
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setText('' if missing else '…')
        lay.addWidget(self.thumb)

    def set_thumb(self, path):
        if path and os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self.thumb.setPixmap(pm.scaled(self.thumb.size(), Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation))
                self.thumb.setText('')
                return
        self.thumb.setText('无缩略图')
        self.thumb.setStyleSheet('background:#0b0b10; border:1px solid #33333f;'
                                 ' color:#5a5a68; font-size:11px;')


# ---------------------------------------------------------------------------
# 启动器主窗口
# ---------------------------------------------------------------------------
class Launcher(QWidget):
    """项目管理界面：打开项目 → 发 open_project 信号，由 main.py 去建编辑器窗口"""

    open_project = Signal(str)
    new_project = Signal(dict)      # {'name','dir','template','video_mode'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('GBAStudio')
        self.resize(860, 560)
        self.store = RecentStore()
        self._rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 标题条
        head = QWidget()
        head.setObjectName('launcherHead')
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 10, 16, 10)
        logo = QLabel('GBAStudio')
        lf = QFont()
        lf.setPointSize(14)
        lf.setBold(True)
        logo.setFont(lf)
        logo.setStyleSheet('color:#ffb703;')
        hl.addWidget(logo)
        sub = QLabel('做 GBA 游戏的编辑器')
        sub.setStyleSheet('color:#8a8a99;')
        hl.addWidget(sub)
        hl.addStretch(1)
        outer.addWidget(head)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_recent_tab(), '最近的项目')
        self.tabs.addTab(self._build_new_tab(), '新建项目')

        self.setStyleSheet("""
            QWidget { background:#16161d; color:#c8c8d4; }
            #launcherHead { background:#1d1d26; border-bottom:1px solid #2c2c38; }
            QTabWidget::pane { border:1px solid #2c2c38; }
            QTabBar::tab { background:#1d1d26; color:#9a9aa8; padding:7px 18px;
                           border:1px solid #2c2c38; border-bottom:none; }
            QTabBar::tab:selected { background:#2a2a36; color:#f0f0f6; }
            QListWidget { background:#12121a; border:1px solid #2c2c38; }
            QListWidget::item { background:#1b1b24; border:1px solid #2c2c38;
                                margin:3px 6px; }
            QListWidget::item:selected { border:1px solid #ffb703;
                                         background:#26262f; color:#ffd166; }
            QListWidget::item:hover { background:#22222b; }
            QLineEdit { background:#0f0f16; border:1px solid #33333f;
                        padding:5px 8px; color:#e0e0ea;
                        /* **选中色必须显式写** ✗
                           深色底 + 系统默认的浅蓝选中 + 浅色文字 = 糊成一片，
                           看起来就是"光标那里的文字显示有问题"。
                           而且输入框第一次拿到焦点时 Qt 会**全选**，
                           正好每次新建项目都会撞上。 */
                        selection-background-color:#c8892a;
                        selection-color:#1a1a20;
                        /* 占位提示色也要显式写：深色底 + 系统默认灰 = 看不见 */
                        placeholder-text-color:#6f6f7f; }
            QLineEdit:focus { border:1px solid #ffb703; }
            QPushButton { background:#2a2a36; border:1px solid #3a3a48;
                          padding:6px 16px; color:#e0e0ea; }
            QPushButton:hover { background:#34343f; }
            QPushButton#primary { background:#c8892a; border:1px solid #e0a040;
                                  color:#1a1a20; font-weight:600; }
        """)

    # ------------------------------------------------------------ 最近的项目
    def _build_recent_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索项目…')
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)

        self.btn_open = QPushButton('打开')
        self.btn_open.setObjectName('primary')
        self.btn_open.clicked.connect(self._open_selected)
        top.addWidget(self.btn_open)

        btn_rm = QPushButton('从列表移除')
        btn_rm.clicked.connect(self._remove_selected)
        top.addWidget(btn_rm)
        lay.addLayout(top)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _it: self._open_selected())
        lay.addWidget(self.list, 1)

        self.empty_hint = QLabel('还没有项目。切到「新建项目」建一个吧。')
        self.empty_hint.setStyleSheet('color:#7a7a88;')
        self.empty_hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty_hint)

        self.refresh_recent()
        return w

    def refresh_recent(self):
        """把最近项目填进列表（顺手校验文件还在不在）"""
        self.list.clear()
        self._rows = []
        # 拖动时别重绘抖动：先断开布局刷新
        self.list.setUpdatesEnabled(False)
        for it in self.store.items:
            path = it.get('path', '')
            missing = not os.path.isfile(path)
            row = ProjectRow(path, it.get('name', ''), it.get('opened', 0), missing)
            item = QListWidgetItem(self.list)
            item.setSizeHint(QSize(0, THUMB_H + 24))
            item.setData(Qt.UserRole, path)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self._rows.append((item, row))
        self.list.setUpdatesEnabled(True)
        n = self.list.count()
        self.empty_hint.setVisible(n == 0)
        self.list.setVisible(n > 0)
        self._apply_filter(self.search.text())
        self._load_thumbs_async()

    def _apply_filter(self, text):
        text = (text or '').strip().lower()
        for item, row in self._rows:
            hay = (row.proj_path + ' ' + self._name_of(item)).lower()
            item.setHidden(bool(text) and text not in hay)
        self.empty_hint.setVisible(self.list.count() == 0)

    def _name_of(self, item):
        w = self.list.itemWidget(item)
        for lab in w.findChildren(QLabel):
            t = lab.text()
            if t and not t.startswith(('最后修改', '找不到')):
                return t
        return ''

    def _load_thumbs_async(self):
        """缩略图逐个补上（渲染慢，不能卡住窗口显示）"""
        from PySide6.QtCore import QTimer
        self._thumb_queue = [r for _i, r in self._rows]
        self._thumb_timer = QTimer(self)
        self._thumb_timer.timeout.connect(self._next_thumb)
        self._thumb_timer.start(10)

    def _next_thumb(self):
        if not self._thumb_queue:
            self._thumb_timer.stop()
            return
        row = self._thumb_queue.pop(0)
        try:
            if os.path.isfile(row.proj_path):
                row.set_thumb(make_thumb(row.proj_path))
        except Exception:                                   # noqa: BLE001
            pass
        QApplication.processEvents()

    def _selected_path(self):
        it = self.list.currentItem()
        if not it:
            return ''
        return it.data(Qt.UserRole) or ''

    def _open_selected(self):
        path = self._selected_path()
        if not path:
            QMessageBox.information(self, '还没选项目', '先点一行，再点「打开」。')
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, '文件不在了',
                                '这个项目文件找不到了：\n%s\n\n'
                                '可以用「从列表移除」把它清掉。' % path)
            return
        self.open_project.emit(path)

    def _remove_selected(self):
        path = self._selected_path()
        if not path:
            return
        self.store.forget(path)
        self.refresh_recent()

    # ------------------------------------------------------------ 新建项目
    def _build_new_tab(self):
        from ui.video_modes import MODES, ModeCard
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        form = QFormLayout()
        # **不预填文字，用占位提示** ✗
        # 以前预填"我的游戏"：输入框一拿到焦点 Qt 就全选，
        # 加上深色主题没写选中色 → 第一眼是一块看不清的黑色，
        # 非得动一下光标才"恢复"（用户报的就是这个现象）。
        # 改成占位提示之后：没有选中状态、没有预填内容，
        # 第一眼就是一行灰色的提示文字，想用什么名字直接打 ✗
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('我的游戏（留空就用这个名字）')
        form.addRow('项目名称', self.name_edit)

        row = QHBoxLayout()
        self.dir_edit = QLineEdit(os.path.expanduser('~'))
        b = QPushButton('…')
        b.setFixedWidth(36)
        b.clicked.connect(self._pick_dir)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(b)
        form.addRow('保存位置', row)

        from PySide6.QtWidgets import QComboBox
        self.template = QComboBox()
        # **默认必须是"空白"** ✗
        # 以前第一项是"带示例素材"，于是新建项目时不动这个下拉框，
        # 拿到的就是一个装满示例素材的工程 —— 和"新建项目要干净"是矛盾的
        #（用户报的"里面带着默认素材"就是这个）。想看效果的人自己选第二项。
        # 只留「空白项目」✗
        # 以前还有一项「带示例素材」✓ 它指向编辑器内部的一份演示内容 ✓
        # 现在示例整套删掉了 ✓ 新建工程就只有一个干净的起点 ✓
        self.template.addItem('空白项目（干净，不带任何素材）', 'blank')
        form.addRow('起始内容', self.template)
        lay.addLayout(form)

        # 显示模式：不可逆的架构选择，必须说清楚（说明和示意图见 ui/video_modes.py）
        hint = QLabel('显示模式（决定了能用哪些图层和特效，建好之后改起来很麻烦）')
        hint.setStyleSheet('color:#ffb703; font-weight:600; margin-top:6px;')
        lay.addWidget(hint)

        body = QHBoxLayout()
        self.mode_list = QListWidget()
        self.mode_list.setFixedWidth(230)
        short = {0: '四个图块层', 1: '两层图块 + 一层旋转', 2: '两层都能旋转',
                 3: '整屏位图 32768 色', 4: '整屏位图 256 色（可翻页）',
                 5: '小屏位图 160x128'}
        for m in MODES:
            it = QListWidgetItem('模式 %d · %s' % (m.m, short.get(m.m, '')))
            it.setData(Qt.UserRole, m.m)
            self.mode_list.addItem(it)
        default_row = next((i for i, m in enumerate(MODES) if m.m == 3), 0)
        self.mode_list.setCurrentRow(default_row)
        body.addWidget(self.mode_list)

        self.card = ModeCard(MODES[default_row])
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        # **内容必须始终适配宽度**：出现横向滚动条就说明布局宽度算错了，
        # 而那种情况下 QLabel 会被撑开、文字被截断（踩过）。
        # 所以这里直接禁掉横向滚动 —— 有问题就"看得见"，而不是"悄悄截断"。
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(self.card)
        body.addWidget(sc, 1)
        lay.addLayout(body, 1)
        # **切换模式要连文字一起换** ✗
        # 踩过：第一版只调了 card.diagram.set_mode()，右边那堆说明标签原封不动 ——
        # 于是不管点哪个模式，看到的都是同一个模式的介绍（用户报的就是这个）。
        # ModeCard.set_mode() 会同时换示意图和文字。
        self.mode_list.currentRowChanged.connect(self._on_mode_row)

        # 刚显示这一页时：把光标放到末尾、**取消全选** ✗
        # Qt 在输入框第一次拿到焦点时会全选（它以为你要覆盖输入），
        # 而"新建项目"第一眼就看到一坨高亮，很容易被当成显示出问题。
        # 这里主动取消选中：文字正常显示，想改直接敲就行（会插入在末尾）。
        self.tabs.currentChanged.connect(self._on_tab_changed)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        create = QPushButton('创建')
        create.setObjectName('primary')
        create.clicked.connect(self._create)
        bottom.addWidget(create)
        lay.addLayout(bottom)
        return w

    def _on_tab_changed(self, idx):
        if idx == 1:                      # 「新建项目」页
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._tidy_name_field)

    def _tidy_name_field(self):
        """取消输入框里的全选，光标放到末尾，并聚焦进去"""
        ne = self.name_edit
        ne.deselect()
        ne.setCursorPosition(len(ne.text()))
        ne.setFocus()

    def _on_mode_row(self, row):
        """切换模式列表 → **连文字一起换**

        踩过：第一版这里只调了 `card.diagram.set_mode()`，右边那堆说明标签
        原封不动 —— 于是不管点哪个模式，看到的都是同一个模式的介绍 ✗
        用户看到的现象就是"模式解释只有一种"。
        ModeCard.set_mode() 会同时换示意图和全部文字。
        """
        from ui.video_modes import MODES
        if 0 <= row < len(MODES):
            self.card.set_mode(MODES[row])

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, '选择保存位置', self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _create(self):
        name = self.name_edit.text().strip() or '我的游戏'   # 留空就用占位里那个名字
        d = self.dir_edit.text().strip()
        if not d:
            QMessageBox.warning(self, '还差一步', '请选择保存位置')
            return
        row = self.mode_list.currentRow()
        from ui.video_modes import MODES
        mode = MODES[row].m if 0 <= row < len(MODES) else 3
        self.new_project.emit({
            'name': name, 'dir': d,
            'template': self.template.currentData(),
            'video_mode': mode,
        })

    def focus_new_tab(self):
        """切到「新建项目」页，并把光标放进名称框

        用途：编辑器里点「文件 → 新建项目」时，转回启动器这一页 ✓
        （创建界面只留启动器这一套 ✓ 那条路径就是走到这里 ✓）
        """
        if hasattr(self, 'tabs'):
            self.tabs.setCurrentIndex(1)
        if hasattr(self, 'name_edit'):
            self.name_edit.setFocus()
