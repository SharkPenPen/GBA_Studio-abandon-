# -*- coding: utf-8 -*-
"""
mainwindow.py —— 主窗口：菜单 + 停靠面板 + 模式切换

布局照剪辑软件/Godot 那套：
    左：资源库    中：预览(240×160)   右：属性
    下：时间轴（常驻） + 日志（窄条）

**视图菜单**里每个面板都有开关，关掉了能再呼回来；还有「重置面板布局」。
（这是上一版最容易踩的坑：面板一关就再也找不回来了。）

模式专属的面板由各模式自己提供（见 modes/story.py），加新模式不用动这个文件。
"""
import os
import queue
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QImage, QPixmap, QPainter, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QWidget, QSizePolicy,
                               QSplitter,
                               QVBoxLayout, QHBoxLayout,
                               QLabel, QTreeWidget, QTreeWidgetItem, QTabWidget, QTextEdit,
                               QToolBar, QPushButton, QScrollArea, QFileDialog, QMessageBox,
                               QStatusBar, QComboBox, QMenu, QInputDialog)

from core.project import (Project, new_project, blank_project, demo_project,
                          FONT_SIZES, Scene)
from core import assets as A
from ui import settings as S
from ui.layer_picker import LayerPicker
from ui.timeline import TimelineView, apply_ui_scale
from ui.dialogs import ImportAssetsDialog
from modes import MODES, PLANNED_MODES, create_modes

APP_TITLE = 'GBAStudio'


class AssetTree(QTreeWidget):
    """资源树：**接外面的文件拖进来** + **把库里的素材拖出去**

    两个方向都要支持 ✗
        拖进来：从资源管理器拖图片/音频 → 导入工程 ✓（原来就有）
        拖出去：从库里拖一个素材 → 丢到时间轴轨道上变成一个片段 ✓（新加）
               ——这是最顺手的用法 ✓ 比"先选中轨道、再点按钮、再去属性里挑文件"快得多
    """

    ASSET_MIME = 'application/x-gbastudio-asset'   # 自定义类型：只有本程序认

    def __init__(self, on_drop, parent=None):
        super().__init__(parent)
        self.on_drop = on_drop
        self.setAcceptDrops(True)
        # DragDrop = 既能接受外面的拖入，也能把自己拖出去
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, actions):
        """把选中的素材打包出去（路径 + 类型）

        用自定义 MIME 而不是纯文本 ✗
        ——纯文本会被别的程序当成"一段文字"接走 ✓ 而我们要的是"这个素材" ✓
        """
        it = self.currentItem()
        if it is None:
            return
        data = it.data(0, Qt.UserRole)
        if not data:
            return                                  # 分组节点，不是素材
        path = data if isinstance(data, str) else (data[0] if data else '')
        if not path:
            return
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setData(self.ASSET_MIME, str(path).encode('utf-8'))
        md.setText(str(path))                       # 顺带给一份纯文本，方便调试
        from PySide6.QtGui import QDrag
        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec(Qt.CopyAction)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        paths = [u.toLocalFile() for u in ev.mimeData().urls()]
        if paths:
            self.on_drop(paths)
            ev.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, project=None, proj_ctx=None):
        super().__init__()
        self.project = project or blank_project()
        self.proj_ctx = proj_ctx or {}
        self.dirty = False
        self.file_path = ''
        self.issues = []
        self.all_docks = []
        self.logq = queue.Queue()      # 后台线程往这里丢日志，主线程取
        self.busy = False
        self._rend = None              # 预览渲染器（懒加载）
        self._rend_dir = ''
        self._playing = False
        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.PreciseTimer)
        self._play_timer.timeout.connect(self._play_tick)

        self.setWindowTitle(APP_TITLE)
        self.resize(1380, 900)
        # 底部两个角落归底部区域，这样时间轴和日志能横跨整窗宽度
        # （不设的话 Qt 会把它们塞到右边，和属性挤在一起）
        self.setCorner(Qt.BottomLeftCorner, Qt.BottomDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.BottomDockWidgetArea)
        self.timeline = TimelineView()
        self.timeline.playheadMoved.connect(lambda _t: self.refresh_preview())
        self.modes = create_modes(self)
        self.mode_idx = 0

        self._build_docks()
        self._build_toolbar()
        self._build_menus()
        self.setStatusBar(QStatusBar())
        apply_ui_scale(S.ui_scale())     # 时间轴尺寸跟着界面字号（启动时先算一次）
        self.switch_mode(0)
        self.timeline.setMinimumHeight(70)   # 能缩得很小，但别缩到看不见
        self.refresh_assets()
        self._log('欢迎使用 %s' % APP_TITLE)
        self._log('这是空工程：把图片/音频拖进左边的资源库，再点「＋台词」开始排剧情')
        self._log('想看完整例子：打开一个已有的工程，或按「帮助」看文档')
        self._status('就绪')
        # 空工程没什么可检查的，跑一次只会刷一屏"没素材"的提示，没必要
        if self.project.assets or self.file_path:
            self.run_checks()
        self._restore_layout()
        self._poll_events()      # 启动后台日志轮询

    # ================================================================= 面板
    def _make_dock(self, title, widget, area):
        d = QDockWidget(title, self)
        d.setObjectName('dock_' + title)      # saveState 需要 objectName
        d.setWidget(widget)
        self.addDockWidget(area, d)
        self.all_docks.append((title, d))
        return d

    def _build_docks(self):
        # 中央 = **地图窗口（左）+ 预览（右）** ✗
        # 为什么这么摆：地图窗口是"要编辑的东西"，预览是"看结果"
        # ——编辑在左、结果在右，和大多数创作软件一致 ✓
        # 用 QSplitter 而不是固定宽度：中间的分隔条可以拖 ✓
        self.split_center = QSplitter(Qt.Horizontal)
        self.split_center.setChildrenCollapsible(False)

        # ---- 左：**当前工作区自己的小组件**（默认没有，占位空着）----
        # 为什么做成"可换的槽"：剧情工作区用不着它 ✓ 关卡工作区要放地图 ✓
        # 让工作区自己决定往这里塞什么 ✓ 主窗口不猜 ✓
        self.side_holder = QWidget()
        self.side_holder.setMinimumWidth(0)
        sl = QVBoxLayout(self.side_holder)
        sl.setContentsMargins(0, 0, 0, 0)
        self.side_lay = sl
        self.side_widget = None
        self.split_center.addWidget(self.side_holder)

        # ---- 右：预览（和剪辑软件的监视器同位置）----
        pw = QWidget()
        pl = QVBoxLayout(pw)
        pl.setContentsMargins(6, 4, 6, 4)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet('background:#101014;')
        # **关键**：预览是"监视器"，它显示多大由面板决定，不该反过来要求尺寸。
        # 默认的 QLabel 会把**图片尺寸**当成自己的推荐尺寸 —— 于是"适应窗口"
        # 模式下越显示越大、越要求更多高度，最后把下面的时间轴挤成一条缝。
        # 设成 Ignored 之后它就老老实实填满给它的空间。
        self.preview_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.preview_label.setMinimumSize(64, 48)      # 但别小到看不见
        self.preview_label.installEventFilter(self)    # 面板一变大就重新适应
        pl.addWidget(self.preview_label, 1)
        row = QHBoxLayout()
        self.play_btn = QPushButton('▶ 播放')
        self.play_btn.setToolTip('播放/暂停（空格）—— 用真实渲染器按时间轴走一遍')
        self.play_btn.setShortcut(QKeySequence(Qt.Key_Space))
        self.play_btn.clicked.connect(self.toggle_play)
        row.addWidget(self.play_btn)
        row.addWidget(QLabel('预览缩放'))
        self.zoom_combo = QComboBox()
        for label, val in S.ZOOM_CHOICES:
            self.zoom_combo.addItem(label, val)
        i = self.zoom_combo.findData(S.zoom)
        self.zoom_combo.setCurrentIndex(max(0, i))
        self.zoom_combo.currentIndexChanged.connect(self._zoom_changed)
        self.zoom_combo.setToolTip('也可以把鼠标放在预览上按 Ctrl+滚轮缩放')
        row.addWidget(self.zoom_combo)
        row.addStretch(1)
        self.preview_info = QLabel('')
        self.preview_info.setStyleSheet('color:#8a8a99;')
        # 这行文字长度是变的（第几句 / 背景名 / 立绘数…），别让它撑住面板宽度
        self.preview_info.setMinimumWidth(1)
        row.addWidget(self.preview_info)
        pl.addLayout(row)

        # ---- 预览左上角：图层选择器（浮层，很小）----
        # 用户要的："图层选择改到预览左上角，很小就行"
        # 浮层 = 直接挂在预览容器上、自己绝对定位 ✓ 不进 layout ✓
        self.layer_picker = LayerPicker(pw)
        self.layer_picker.layer_selected.connect(self._on_layer_selected)
        self.layer_picker.layer_renamed.connect(lambda *_: self._project_touched('改了图层名'))
        self.layer_picker.layer_visible.connect(lambda *_: self._on_layer_visible())
        self.layer_picker.move(6, 6)
        self.layer_picker.raise_()

        self.preview_holder = pw            # 浮层要跟着预览一起缩放
        pw.installEventFilter(self)         # 已有的 eventFilter 里顺带重新摆放

        self.split_center.addWidget(pw)
        self.split_center.setStretchFactor(0, 0)      # 左侧小组件：够用就行
        self.split_center.setStretchFactor(1, 1)      # 预览：占满剩下的
        self.split_center.setSizes([0, 1100])         # 默认收起（剧情工作区不需要它）
        self.setCentralWidget(self.split_center)

        # 左：资源库（支持拖放导入）
        tabs = QTabWidget()
        self.asset_tree = AssetTree(self._on_files_dropped)
        self.asset_tree.setHeaderLabels(['资源', '说明'])
        self.asset_tree.setColumnWidth(0, 150)
        self.asset_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_tree.customContextMenuRequested.connect(self._asset_menu)
        self.asset_tree.itemDoubleClicked.connect(self._asset_double_clicked)
        tabs.addTab(self.asset_tree, '素材')
        self.char_tree = QTreeWidget()
        self.char_tree.setHeaderLabels(['角色', '表情 / 语音前缀'])
        self.char_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.char_tree.customContextMenuRequested.connect(self._char_menu)
        tabs.addTab(self.char_tree, '角色表')
        self.dock_assets = self._make_dock('资源库', tabs, Qt.LeftDockWidgetArea)

        # 右：属性
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.inspector_body = QVBoxLayout(holder)
        self.inspector_body.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(holder)
        self.dock_inspector = self._make_dock('属性', scroll, Qt.RightDockWidgetArea)

        # 下：模式专属面板
        self.mode_docks = []
        for mode in self.modes:
            for area, (title, widget) in mode.build_panels().items():
                d = self._make_dock(title, widget, Qt.BottomDockWidgetArea)
                d.hide()
                self.mode_docks.append((mode, d))

        # 下：日志
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet('background:#14141a; color:#c8c8d4;')
        self.dock_log = self._make_dock('日志 / 合规检查', self.log_box,
                                        Qt.BottomDockWidgetArea)

    def _build_toolbar(self):
        """工具栏**整条去掉**，只在菜单栏右上角留一个「导出 GBA」

        【为什么连工作区切换也不要了】
        用户的原话："工作区 剧情/关卡/精灵/逻辑 整条删掉不需要这一栏
                     导出gba可以保留"
        —— 那一栏占着一整行高度 ✓ 却只有四五个按钮 ✓ 不值 ✗

        【那工作区怎么切】
        挪进菜单栏：「工作区」菜单 ✓ 外加 Ctrl+1~4 ✓
        —— 切工作区是低频操作（一次会话切几次 ✓）
          不该为它常驻一整行 ✓

        【导出 GBA 为什么还留着】
        它是这个编辑器里**最终目的**那一下 ✓ 高频且要有存在感 ✓
        用 `setCornerWidget` 钉在菜单栏右端 → 位置和原来一模一样 ✓
        但**不占额外的一行** ✓
        """
        # 先让它是个空工具栏（别的地方可能还引用 self.toolbar）
        tb = QToolBar('工具栏')
        tb.setObjectName('main_toolbar')
        tb.setVisible(False)
        self.addToolBar(tb)
        self.toolbar = tb

        self.export_btn = QPushButton('导出 GBA')
        self.export_btn.setObjectName('primary')
        self.export_btn.setToolTip('编译成 .gba（F5）——完整的文件操作在「文件」菜单里')
        self.export_btn.clicked.connect(self.on_export)
        self.export_btn.setStyleSheet("""
            QPushButton#primary {
                background: #c8892a; border: none; border-radius: 3px;
                padding: 4px 14px; color: #1a1a20; font-weight: 600;
                margin: 2px 6px 2px 0;
            }
            QPushButton#primary:hover { background: #d99a3a; }
        """)
        self.menuBar().setCornerWidget(self.export_btn, Qt.TopRightCorner)

    def _build_menus(self):
        mb = self.menuBar()

        # ---------------- 文件 ----------------
        m = mb.addMenu('文件(&F)')
        m.addAction('新建项目…', self.on_new_project, 'Ctrl+N')
        m.addAction('打开项目…', self.on_open, 'Ctrl+O')
        m.addSeparator()
        m.addAction('保存', self.on_save, 'Ctrl+S')
        m.addAction('另存为…', self.on_save_as, 'Ctrl+Shift+S')
        m.addSeparator()
        m.addAction('导入素材…', lambda: self.on_import_assets(), 'Ctrl+I')
        m.addAction('导出素材…', self.on_export_assets)
        m.addSeparator()
        m.addAction('打开项目文件夹', self._open_project_folder)
        m.addSeparator()
        m.addAction('退出', self.close, 'Alt+F4')

        # ---------------- 编辑 ----------------
        m = mb.addMenu('编辑(&E)')
        m.addAction('删除选中片段', lambda: self.mode.on_delete_clip()
                    if hasattr(self.mode, 'on_delete_clip') else None, 'Delete')
        m.addAction('场景管理…', self.on_scene_manager)

        # ---------------- 工作区（原来的工具栏按钮挪到这里） ----------------
        m = mb.addMenu('工作区(&W)')
        self.mode_buttons = []
        for i, mode in enumerate(self.modes):
            a = QAction('%s %s' % (mode.icon, mode.title), self, checkable=True)
            a.setShortcut(QKeySequence('Ctrl+%d' % (i + 1)))
            a.setToolTip('%s（Ctrl+%d）' % (mode.title, i + 1))
            a.triggered.connect(lambda _=False, i=i: self.switch_mode(i))
            m.addAction(a)
            self.mode_buttons.append(a)
        m.addSeparator()
        for _key, title, tip in PLANNED_MODES:
            a = QAction(title, self)
            a.setEnabled(False)
            a.setToolTip('%s（计划中）' % tip)
            m.addAction(a)

        # ---------------- 视图（关键：关掉的面板能呼回来） ----------------
        self.view_menu = mb.addMenu('视图(&V)')
        for title, d in self.all_docks:
            self.view_menu.addAction(d.toggleViewAction())     # Qt 自带开关动作
        self.view_menu.addSeparator()

        # 界面字体：改完立刻生效，并落盘记住
        fm = self.view_menu.addMenu('界面字体')
        self.font_actions = []
        for label, pt in S.FONT_CHOICES:
            a = QAction('%s（%d 号）' % (label, pt), self, checkable=True)
            a.setChecked(pt == S.font_pt)
            a.triggered.connect(lambda _=False, p=pt: self.set_ui_font(p))
            fm.addAction(a)
            self.font_actions.append((pt, a))
        fm.addSeparator()
        fm.addAction('把面板大小恢复默认', self.reset_layout)

        self.view_menu.addAction('重置面板布局', self.reset_layout, 'Ctrl+0')
        self.view_menu.addSeparator()
        # （原来这里有一条"显示工作区栏" ✓ 那一栏已经删掉了 ✓ 开关也就没意义了）

        # ---------------- 帮助 ----------------
        m = mb.addMenu('帮助(&H)')
        m.addAction('快捷键', self._show_shortcuts)
        m.addAction('关于', self._show_about)

    # ================================================================= 模式
    def switch_mode(self, idx):
        self.mode_idx = idx
        for i, b in enumerate(self.mode_buttons):
            b.setChecked(i == idx)
        for mode, dock in self.mode_docks:
            show = (mode is self.modes[idx])
            dock.setVisible(show)
            if show:
                dock.raise_()
                mode.on_activate()
        # 中央左侧那一格：由**工作区自己**决定放什么 ✗
        #   关卡工作区 → 地图（和预览并排 ✓ 不再是浮窗）
        #   剧情工作区 → 空着（图层选择已经挪到预览左上角了）
        m = self.modes[idx]
        self.set_side_widget(m.side_widget() if hasattr(m, 'side_widget') else None)
        self.refresh_layers()
        self.refresh_preview()

    @property
    def mode(self):
        return self.modes[self.mode_idx]

    # ================================================================= 反馈
    def _status(self, msg, ms=6000):
        """状态栏提示：所有操作都要有反馈，这是基础体验"""
        self.statusBar().showMessage(msg, ms)

    def _log(self, text):
        self.log_box.append(str(text))
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    def _done(self, title, lines, popup=False):
        """完成一件事后的统一反馈：**写日志 + 状态栏**。

        **默认不弹窗** ✗ 以前每做成一件事（新建/导入/导出）都弹一个
        information 框，用户点一次烦一次 —— 而且信息其实已经在
        左下角的日志面板里了，弹窗只是重复一遍 ✗

        真要弹（比如"导出成功，ROM 在这儿"这种需要用户立刻知道的），
        调用时显式写 popup=True —— 反过来，默认必须是不打扰。
        """
        for ln in lines:
            self._log('  ' + ln)
        self._status(lines[0] if lines else title)
        if popup:
            QMessageBox.information(self, title, '\n'.join(lines[:12]))

    # ================================================================= 项目
    def on_new_project(self):
        """新建项目 → **回到启动器的「新建项目」页**

        以前这里弹一个自己的 NewProjectDialog ✗ 而启动器里也有一套创建界面 ✗
        两套并存的结果就是：改了一处忘了另一处（显示模式那次就漏过 ✗）
        用户报的"对话框还存在，被遗漏了"说的就是这个 ✗

        现在只留**一套**创建界面（启动器那个），这里只负责转过去 ✗
        没有回调时（比如直接用命令行打开工程、没走启动器）就退回"就地新建一个空白工程"，
        保证这条菜单项任何时候都不会点不动 ✓
        """
        if not self.confirm_discard():
            return
        cb = getattr(self, 'on_request_new', None)
        if cb:
            cb()
            return
        # 退路：没有启动器可用时，就地建一个空白工程
        from core.project import blank_project
        import tempfile
        d = os.path.dirname(self.file_path) if self.file_path else os.path.expanduser('~')
        self.project = blank_project('我的游戏')
        self.file_path = ''
        self.dirty = True
        self.update_title()
        self.refresh_assets()
        self.mode.on_activate()
        self.refresh_preview()
        self.run_checks()
        self._log('已新建一个空白工程（还没保存）—— 保存时会问你要放哪')

    def on_open(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, '打开项目', '',
            'GBAStudio 工程 (*.gbastudio);;所有文件 (*.*)')
        if not path:
            return
        try:
            self.project = Project.load(path)
            self.file_path = path
            self.dirty = False
            self.mode.on_activate()
            self.refresh_assets()
            self.refresh_preview()
            self.run_checks()
            self.update_title()
            self._log('已打开 %s' % path)
            self._status('已打开 %s' % os.path.basename(path))
        except Exception as e:
            QMessageBox.critical(self, '打开失败', str(e))

    def on_save(self):
        if not self.file_path:
            return self.on_save_as()
        try:
            self.project.save(self.file_path)
            self.dirty = False
            self.update_title()
            self._log('已保存 %s' % self.file_path)
            self._status('已保存到 %s' % os.path.basename(self.file_path))
            return True
        except Exception as e:
            QMessageBox.critical(self, '保存失败', str(e))
            return False

    def on_save_as(self):
        default = (self.file_path or
                   os.path.join(os.getcwd(), '%s.gbastudio' % self.project.name))
        path, _ = QFileDialog.getSaveFileName(self, '另存为', default,
                                              'GBA Studio 项目 (*.gbastudio)')
        if not path:
            return False
        self.file_path = path
        return self.on_save()

    def confirm_discard(self):
        if not self.dirty:
            return True
        r = QMessageBox.question(self, '还没保存', '当前项目有改动，要先保存吗？',
                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Yes:
            return bool(self.on_save())
        return True

    def closeEvent(self, ev):
        """关窗口前先问一句，别丢了没保存的东西。

        关掉之后 **回到项目列表**（如果是从启动器进来的）——
        不然用户想换个项目就得把程序整个重开 ✗
        """
        if self.dirty:
            r = QMessageBox.question(self, '还没保存',
                                     '「%s」有未保存的改动，保存后退出吗？' % self.project.name,
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                ev.ignore()
                return
            if r == QMessageBox.Save and not self.on_save():
                ev.ignore()
                return
        self._save_layout()
        ev.accept()
        # 回项目列表：用 singleShot 让窗口先真正关掉，再显示启动器，
        # 否则会出现"启动器闪一下又被编辑器盖住"
        cb = getattr(self, 'on_closed', None)
        if cb:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, cb)

    def _open_project_folder(self):
        if not self.file_path:
            QMessageBox.information(self, '还没有项目文件', '先新建或保存一个项目')
            return
        folder = os.path.dirname(self.file_path)
        import subprocess
        subprocess.Popen(['explorer.exe', folder])

    # ================================================================= 素材
    def _on_files_dropped(self, paths):
        """资源库收到拖放 → 按扩展名自动分类导入"""
        self._do_import(paths, kind=None, character=None, silent_dialog=True)

    def on_import_assets(self, preset_kind=None):
        if not self.file_path:
            r = QMessageBox.question(self, '还没有项目文件',
                                     '导入素材需要先把项目存盘（素材要放进项目目录）。\n现在保存吗？',
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes or not self.on_save_as():
                return
        dlg = ImportAssetsDialog(self.project, self, preset_kind)
        if dlg.exec() != ImportAssetsDialog.Accepted:
            return
        v = dlg.values()
        if not v['files']:
            QMessageBox.warning(self, '没有选文件', '请先添加要导入的文件')
            return
        self._do_import(v['files'], None, None)

    def _do_import(self, paths, kind, character, silent_dialog=False):
        proj_dir = os.path.dirname(self.file_path)
        ok, bad, notes = A.import_files(proj_dir, paths, kind, character)
        self.rescan_assets()
        lines = ['导入 %d 个素材（%d 个失败）' % (len(ok), len(bad))]
        lines += ['· ' + p for p in ok[:6]]
        if len(ok) > 6:
            lines.append('· …还有 %d 个' % (len(ok) - 6))
        lines += ['❌ %s：%s' % (os.path.basename(p), why) for p, why in bad]
        lines += notes
        self._log('── 导入素材 ──')
        self._done('导入完成', lines)
        if kind == 'char' and character:
            self.refresh_characters()

    def _classify(self, rel_path, kind, character=None):
        """手动归类：把文件挪进对应目录并记下类型"""
        proj_dir = os.path.dirname(self.file_path)
        a = self.project.find_asset(rel_path)
        if a is None:
            return
        new_rel, err = A.classify_asset(proj_dir, a, kind, character)
        if err:
            QMessageBox.warning(self, '归类失败', err)
            return
        a.path = new_rel
        a.kind = kind
        if kind == 'char' and character:
            c = self.project.character([x.name for x in self.project.characters if x.name == character][0]) \
                if any(x.name == character for x in self.project.characters) else None
            stem = os.path.splitext(os.path.basename(new_rel))[0]
            if c and stem not in c.poses:
                c.poses.append(stem)
        self.refresh_assets()
        self.refresh_characters()
        self.mark_dirty()
        self.run_checks()
        self._status('已归类：%s → %s' % (os.path.basename(new_rel),
                                          {'bg': '背景', 'char': '立绘', 'bgm': '音乐',
                                           'voice': '语音', 'se': '音效'}.get(kind, kind)))

    def on_export_assets(self):
        if not self.file_path:
            QMessageBox.information(self, '还没有项目文件', '先新建或保存一个项目')
            return
        if not self.project.assets:
            QMessageBox.information(self, '没有素材', '项目里还没有素材，先导入一些')
            return
        dest = QFileDialog.getExistingDirectory(self, '导出到哪个文件夹')
        if not dest:
            return
        proj_dir = os.path.dirname(self.file_path)
        n, bad = A.export_assets(proj_dir, dest, self.project.assets)
        lines = ['导出 %d 个素材到 %s' % (n, dest)]
        lines += ['❌ %s：%s' % (p, why) for p, why in bad[:8]]
        self._log('── 导出素材 ──')
        self._done('导出完成', lines)

    def rescan_assets(self):
        """重新扫描素材目录。**保留已登记的类型**，不会被扫描覆盖（手动归类才算数）"""
        if not self.file_path:
            return
        proj_dir = os.path.dirname(self.file_path)
        known = {a.path: a.kind for a in self.project.assets if a.kind}
        found, issues = A.scan_folder(proj_dir, known)
        self.project.assets = found
        self.refresh_assets()
        self.mark_dirty()

    def _asset_menu(self, pos):
        """右键资源库。菜单**先构建再弹出** —— 分开写是为了能自动化测试。"""
        it = self.asset_tree.itemAt(pos)
        path = it.data(0, Qt.UserRole) if it else None
        is_group = it is not None and it.parent() is None
        self._build_asset_menu(path, is_group).exec(
            self.asset_tree.viewport().mapToGlobal(pos))

    def _build_asset_menu(self, path, is_group=False):
        """
        资源库右键菜单。

        踩过的坑：原来把 `_classify_menu()` 返回的一整个菜单 addMenu 进来再改名，
        结果套成了「归类为 ▸ 归类为 ▸ 背景」两层，用户根本找不到分类选项
        （反馈的"右键没有分类选择"就是这个）。现在分类项直接建在主菜单里。
        """
        m = QMenu(self)
        m.addAction('导入素材…', lambda: self.on_import_assets())
        m.addAction('重新扫描素材目录', self.rescan_assets)

        if not path:
            if is_group:
                # 右键分类标题行时明确说明，不然只弹两项，看着像"没反应"
                a = m.addAction('（选中具体的素材文件才能归类）')
                a.setEnabled(False)
            return m

        m.addSeparator()
        head = m.addAction('归类为：')
        head.setEnabled(False)
        m.addAction('　　背景', lambda: self._classify(path, 'bg'))
        cm = m.addMenu('　　立绘（放进角色目录）')
        if self.project.characters:
            for c in self.project.characters:
                cm.addAction(c.name,
                             lambda _=False, n=c.name: self._classify(path, 'char', n))
        else:
            a = cm.addAction('（还没有角色，先去角色表新建）')
            a.setEnabled(False)
        m.addAction('　　背景音乐', lambda: self._classify(path, 'bgm'))
        m.addAction('　　人物语音', lambda: self._classify(path, 'voice'))
        m.addAction('　　音效', lambda: self._classify(path, 'se'))
        if self.project.find_asset(path) and self.project.find_asset(path).kind:
            m.addAction('　　设为未分类', lambda: self._classify(path, ''))

        m.addSeparator()
        m.addAction('在资源管理器中显示', lambda: self._reveal(path))
        m.addAction('复制相对路径', lambda: self._copy_text(path))
        m.addSeparator()
        m.addAction('从项目中移除…', lambda: self._remove_asset(path))
        return m

    def _asset_double_clicked(self, it, col):
        path = it.data(0, Qt.UserRole)
        if path:
            self._reveal(path)

    def _char_menu(self, pos):
        it = self.char_tree.itemAt(pos)
        name = it.text(0) if it and it.parent() is None else None
        self._build_char_menu(name).exec(self.char_tree.viewport().mapToGlobal(pos))

    def _build_char_menu(self, name=None):
        m = QMenu(self)
        m.addAction('新建角色…', self.on_add_character)
        if name:
            m.addSeparator()
            m.addAction('为「%s」导入立绘…' % name,
                        lambda: self.on_import_assets('char'))
            m.addAction('删除角色「%s」' % name, lambda: self.on_del_character(name))
        return m

    def _reveal(self, rel_path):
        full = os.path.join(os.path.dirname(self.file_path), rel_path)
        if os.path.isfile(full):
            import subprocess
            subprocess.Popen(['explorer.exe', '/select,', os.path.normpath(full)])
        else:
            QMessageBox.information(self, '文件不在', '找不到 %s\n（可能还没真正导入）' % rel_path)

    def _copy_text(self, text):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self._status('已复制：%s' % text)

    def _remove_asset(self, rel_path):
        r = QMessageBox.question(self, '移除素材',
                                 '从项目里移除 %s ？\n（只从项目清单移除，不删磁盘文件）' % rel_path)
        if r != QMessageBox.Yes:
            return
        self.project.assets = [a for a in self.project.assets if a.path != rel_path]
        self.refresh_assets()
        self.mark_dirty()
        self._status('已移除 %s' % rel_path)

    # ================================================================= 角色
    def on_add_character(self):
        name, ok = QInputDialog.getText(self, '新建角色', '角色显示名（玩家看到的名字）：')
        if not ok or not name.strip():
            return
        name = name.strip()
        cid = 'char%d' % (len(self.project.characters) + 1)
        from core.project import Character
        self.project.characters.append(
            Character(cid, name, '#ffd166', cid + '_', ['normal']))
        self.refresh_characters()
        self.mark_dirty()
        self._status('已新建角色「%s」，接着可以用右键菜单给它导入立绘' % name)

    def on_del_character(self, name):
        r = QMessageBox.question(self, '删除角色', '确定删除角色「%s」？' % name)
        if r != QMessageBox.Yes:
            return
        self.project.characters = [c for c in self.project.characters if c.name != name]
        self.refresh_characters()
        self.mark_dirty()

    # ================================================================= 场景
    def on_scene_manager(self):
        items = [s.name for s in self.project.scenes]
        m = QMenu(self)
        m.addAction('新建场景…', self.on_add_scene)
        if items:
            sub = m.addMenu('删除场景')
            for s in self.project.scenes:
                sub.addAction(s.name, lambda n=s.name: self.on_del_scene(n))
        m.exec(self.mapToGlobal(self.rect().center()))

    def on_add_scene(self):
        name, ok = QInputDialog.getText(self, '新建场景', '场景名（如 第二章）：')
        if not ok or not name.strip():
            return
        self.project.scenes.append(Scene(name.strip(), 'story'))
        self.refresh_scene_combo()
        self.mark_dirty()
        self._status('已新建场景「%s」' % name.strip())

    def on_del_scene(self, name):
        if len(self.project.scenes) <= 1:
            QMessageBox.warning(self, '不能删', '至少要留一个场景')
            return
        if QMessageBox.question(self, '删除场景', '确定删除场景「%s」及其片段？' % name) != QMessageBox.Yes:
            return
        self.project.scenes = [s for s in self.project.scenes if s.name != name]
        self.refresh_scene_combo()
        self.mark_dirty()

    def refresh_scene_combo(self):
        if hasattr(self.mode, 'reload_scenes'):
            self.mode.reload_scenes()

    # ================================================================= 资源库显示
    def refresh_assets(self):
        self.asset_tree.clear()
        groups = {}
        for a in self.project.assets:
            groups.setdefault(a.kind or '', []).append(a)
        titles = {'': '未分类（右键归类）', 'bg': '背景', 'char': '立绘', 'bgm': '音乐',
                  'voice': '语音', 'se': '音效', 'font': '字库'}
        order = ['', 'bg', 'char', 'bgm', 'voice', 'se', 'font']
        for kind in order:
            items = groups.get(kind, [])
            if not items:
                continue
            node = QTreeWidgetItem(self.asset_tree, ['%s (%d)' % (titles.get(kind, kind), len(items)), ''])
            node.setFlags(node.flags() & ~Qt.ItemIsSelectable)
            if kind == '':
                node.setForeground(0, QColor('#ffb703'))
            for a in items:
                # 未分类的显示父目录名，避免同名文件分不清
                label = os.path.basename(a.path)
                if kind == '':
                    parent = os.path.dirname(a.path).replace('\\', '/').rsplit('/', 1)[-1]
                    if parent and parent != 'assets':
                        label = '%s/%s' % (parent, label)
                it = QTreeWidgetItem(node, [label, a.note])
                it.setData(0, Qt.UserRole, a.path)
                it.setToolTip(0, a.path)
            node.setExpanded(kind in ('', 'bg', 'char'))
        self.refresh_characters()

    def refresh_characters(self):
        self.char_tree.clear()
        for c in self.project.characters:
            node = QTreeWidgetItem(self.char_tree, [c.name, '%d 个表情 · 前缀 %s'
                                                    % (len(c.poses), c.voice_prefix)])
            for p in c.poses:
                n = QTreeWidgetItem(node, ['　' + p, ''])
                n.setFlags(n.flags() & ~Qt.ItemIsSelectable)
            node.setExpanded(True)

    # ================================================================= 预览
    def _renderer(self):
        """预览渲染器（需要项目目录才能找素材），懒加载 + 换项目时重建"""
        from core.preview import PreviewRenderer
        proj_dir = os.path.dirname(self.file_path) if self.file_path else ''
        if not proj_dir:
            return None
        if getattr(self, '_rend', None) is None or getattr(self, '_rend_dir', '') != proj_dir:
            self._rend = PreviewRenderer(self.project, proj_dir)
            self._rend_dir = proj_dir
            self._rend_keys = {}
        return self._rend

    # ---------------------------------------------------------- 预览缩放
    def _zoom_changed(self, _idx=0):
        S.save_zoom(self.zoom_combo.currentData())
        self.refresh_preview()

    def _preview_scale(self):
        """
        算出该用几倍显示。
        'fit' = 适应窗口：**取整倍数**（最近邻缩放时，非整数倍会出现像素大小不一，
        看起来像"有的像素胖有的瘦"，很难看）。
        """
        z = self.zoom_combo.currentData()
        if z != 'fit':
            return int(z)
        avail_w = max(64, self.preview_label.width() - 4)
        avail_h = max(48, self.preview_label.height() - 4)
        return max(1, min(avail_w // 240, avail_h // 160))

    def eventFilter(self, obj, ev):
        """预览面板一改变大小就重新适应（'适应窗口'模式下）

        顺带把左上角的图层浮层重新钉一下 ✗
        —— 它是**绝对定位**的 ✓ 不跟着 layout 走 ✓
          容器一变宽变窄就得自己摆 ✓ 否则会飘到画面中间去
        """
        if ev.type() == ev.Type.Resize:
            if obj is getattr(self, 'preview_holder', None):
                self._layer_picker_place()
            if obj is getattr(self, 'preview_label', None):
                if self.zoom_combo.currentData() == 'fit':
                    self.refresh_preview()
        return super().eventFilter(obj, ev)

    def wheelEvent(self, ev):
        """Ctrl+滚轮 缩放预览（和常见图片查看器一致）"""
        if ev.modifiers() & Qt.ControlModifier and self.preview_label.underMouse():
            opts = [v for _, v in S.ZOOM_CHOICES if v != 'fit']
            cur = self._preview_scale()
            i = min(range(len(opts)), key=lambda k: abs(opts[k] - cur))
            i = max(0, min(len(opts) - 1, i + (1 if ev.angleDelta().y() > 0 else -1)))
            j = self.zoom_combo.findData(opts[i])
            if j >= 0:
                self.zoom_combo.setCurrentIndex(j)     # 会触发 _zoom_changed
            return
        super().wheelEvent(ev)

    # =============================================================== 地图窗口
    def refresh_layers(self):
        """把当前场景的图层刷到预览角上的选择器里"""
        if not hasattr(self, 'layer_picker'):
            return
        scene = None
        try:
            scene = self.mode.current_scene() if hasattr(self.mode, 'current_scene') else None
        except Exception:                                   # noqa: BLE001
            scene = None
        self.layer_picker.set_project(self.project, scene)
        # 选择器只在"这个工作区有图层"时才露面（关卡工作区不需要）
        self.layer_picker.setVisible(bool(scene is not None
                                          and getattr(scene, 'layers', None)))

    def _layer_picker_place(self):
        """把浮层钉在预览左上角（预览大小变了要重新钉）"""
        lp = getattr(self, 'layer_picker', None)
        if lp is not None and lp.isVisible():
            lp.move(6, 6)
            lp.raise_()

    def set_side_widget(self, w):
        """换掉中央左侧那个小组件（None = 收起，让预览占满）

        ——关卡工作区用它放地图 ✓ 剧情工作区不需要（图层选择已经挪到预览角上）
        """
        old = self.side_widget
        if old is not None:
            self.side_lay.removeWidget(old)
            old.setParent(None)
        self.side_widget = w
        if w is not None:
            self.side_lay.addWidget(w)
            w.show()
            self.split_center.setSizes([max(240, w.sizeHint().width()), 760])
            self.side_holder.show()
        else:
            self.side_holder.hide()
            self.split_center.setSizes([0, 1100])
        return old

    def _on_layer_selected(self, lid):
        L = self.layer_picker.current_layer()
        if L is None:
            return
        self._status('选中图层「%s」（%s，%d 条轨道）'
                     % (L.name, L.kind_title, len(L.tracks)))

    def _on_layer_visible(self):
        """隐藏/显示一个图层 → 画面要跟着变"""
        self.refresh_preview()

    def _project_touched(self, why=''):
        """工程数据被改了：标脏 + 刷新预览"""
        self.dirty = True
        if why:
            self._status(why)

    def refresh_preview(self):
        """
        真实渲染当前播放头时刻的画面。
        渲染器和实机逐像素一致（tools/check-preview.py 是验收工具），
        所以这里看到什么，烧进 ROM 就是什么。
        """
        if not hasattr(self, 'preview_label'):
            return
        # 地图窗口跟着当前场景走
        # ⚠ 放在"没有渲染器就 return"**之前** ✗
        #   否则没保存过的新工程里地图窗口永远是空的（它其实有图层）✓
        self.refresh_layers()
        r = self._renderer()
        if r is None:
            self.preview_label.setText('先把项目保存到磁盘\n（预览要从项目目录读素材）')
            self.preview_label.setStyleSheet('background:#101014; color:#8a8a99;')
            self.preview_info.setText('')
            return
        scene = self.mode.current_scene() if hasattr(self.mode, 'current_scene') else None
        t = self.timeline.playhead
        try:
            img = r.render(scene, t)
        except Exception as e:
            self.preview_label.setText('渲染出错：%s' % e)
            return
        scale = self._preview_scale()
        data = img.tobytes('raw', 'RGB')
        qimg = QImage(data, 240, 160, 240 * 3, QImage.Format_RGB888).copy()
        self.preview_label.setStyleSheet('background:#101014;')
        self.preview_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            240 * scale, 160 * scale, Qt.IgnoreAspectRatio, Qt.FastTransformation))
        # 报出这一刻的状态；立绘/素材缺失会在这里说清楚（不是静默空白）
        st = r.state_at(scene, t)
        bits = []
        if st.get('bg'):
            bits.append(os.path.basename(st['bg']))
        n_ch = len([v for v in st.get('chars', {}).values() if v])
        if n_ch:
            bits.append('%d 个立绘' % n_ch)
        ordn = 0
        if scene:
            marks = [t0 for _, t0 in self.timeline.dialogue_marks()]
            ordn = sum(1 for t0 in marks if t0 <= t + 1e-6)
        if ordn:
            bits.insert(0, '第 %d 句' % ordn)
        msg = ' · '.join(bits) if bits else '空场景'
        if st.get('notes'):
            msg += ' ⚠ ' + '；'.join(st['notes'][:2])
        fit = '（适应窗口）' if self.zoom_combo.currentData() == 'fit' else ''
        self.preview_info.setText('%s   %d× 最近邻%s' % (msg, scale, fit))

    # ---------------------------------------------------------- 界面字体
    def set_ui_font(self, pt):
        """
        改界面字体：字号 → 全局字体 + 时间轴尺寸 → 重画。

        时间轴的行高/列宽要跟着字号走，否则字体一大，
        轨道名和片段标签就挤在一起（这就是"字体调大了但界面反而更难看"的根源）。
        """
        S.apply_font(pt, QApplication.instance())
        for p, a in self.font_actions:
            a.setChecked(p == pt)
        s = apply_ui_scale(S.ui_scale())
        self.timeline.rebuild()
        self.refresh_preview()
        self._status('界面字体：%d 号（界面缩放 %.2f×）' % (pt, s))
        self._log('── 界面字体改为 %d 号（界面缩放 %.2f×）──' % (pt, s))

    # ---------------------------------------------------------- 播放
    def toggle_play(self):
        if getattr(self, '_playing', False):
            self.stop_play()
        else:
            self.start_play()

    def start_play(self):
        if self._renderer() is None:
            QMessageBox.information(self, '先保存项目', '播放需要从项目目录读素材，先保存一下项目')
            return
        scene = self.mode.current_scene() if hasattr(self.mode, 'current_scene') else None
        if not scene:
            return
        end = max([c.start + c.dur for c in scene.clips] + [0.0])
        if self.timeline.playhead >= end - 0.01:
            self.timeline.set_playhead(0.0)          # 播完了再按 = 从头播
        self._playing = True
        self._play_t0 = time.time() - self.timeline.playhead
        self.play_btn.setText('⏸ 暂停')
        self._play_timer.start(33)                   # ~30fps，够顺滑也不费 CPU

    def stop_play(self):
        self._playing = False
        self._play_timer.stop()
        self.play_btn.setText('▶ 播放')

    def _play_tick(self):
        scene = self.mode.current_scene() if hasattr(self.mode, 'current_scene') else None
        if not scene:
            self.stop_play()
            return
        end = max([c.start + c.dur for c in scene.clips] + [0.0])
        t = time.time() - self._play_t0
        if t >= end:
            self.timeline.set_playhead(end)
            self.refresh_preview()
            self.stop_play()
            self._status('播放结束')
            return
        self.timeline.set_playhead(t)
        self.timeline.setFocus()
        self.refresh_preview()

    # ================================================================= 检查/导出
    def run_checks(self):
        self.issues = A.check_project(self.project)
        self._log('── 合规检查 ──')
        self._log(A.format_report(self.issues))
        errs = sum(1 for i in self.issues if i.level == 'error')
        self._status('检查完成：%d 错误 / %d 警告' % (errs, len(self.issues) - errs))

    def on_export(self):
        """导出 GBA：时间轴 → 剧本 → 调用现有工具链编译（后台线程，界面不卡）"""
        if getattr(self, 'busy', False):
            return
        from core import compiler, gba_build
        proj_dir_self = os.path.dirname(self.file_path) if self.file_path else None
        text, notes, manifest = compiler.compile_project(self.project, proj_dir_self,
                                                         log=self._log)
        if text is None:
            QMessageBox.critical(self, '编译失败', '\n'.join(notes) or '没有可编译的内容')
            return
        # 关卡地图也写成 level.txt（P8）。放**引擎仓库的 scenario\\**，
        # 和 scenario.txt / assets.json 一起 —— 那边的脚本只认这个目录
        lvl_path = compiler.write_level(self.project, self.proj_ctx.get('gba_project'))
        if lvl_path:
            self._log('── 关卡地图 ──')
            self._log('  已写出 %s（编译脚本会转成引擎认识的 C 数组）' % lvl_path)
        proj_dir = self.proj_ctx.get('gba_project') or gba_build.find_gba_project()
        if not proj_dir:
            QMessageBox.showerror(self, '找不到 GBA 工程',
                                 '导出需要电脑上有这个 GBA 工程（含 build.ps1 和 .toolchain）。')
            return
        # 显示模式也要写出去：引擎是"多工程共用一次编译"的，
        # 模式属于**工程设置**，所以每次导出都按当前工程的设置刷新这个头文件
        inc = os.path.join(proj_dir, 'include')
        compiler.write_video_mode(self.project, inc, log=self._log)
        # 先生成一份"事件表"，让用户能直接看到哪些东西会被跳过
        s = self.mode.current_scene() if hasattr(self.mode, 'current_scene') else None
        if s:
            self._log('── 事件表（%s）──' % s.name)
            for t, name, desc in compiler.event_table(self.project, s):
                self._log('  %-8s %-6s %s' % ('%.2f' % t, name, desc))
        for n in notes:
            self._log('  ' + n)
        if notes and not QMessageBox.askokcancel(
                '有提示', '\n'.join(notes[:8]) + '\n\n仍然继续导出吗？'):
            return

        self.busy = True
        self._status('正在编译…（首次约 1 分钟）')
        self._log('')
        self._log('════════ 开始导出 GBA ════════')
        rom_name = self.project.settings.get('rom_name', 'gba_ai')

        def work():
            try:
                ok, rom = gba_build.export_rom(proj_dir, text, rom_name, log=self._log,
                                              manifest=manifest)
            except Exception as e:
                self._log('❌ 异常：%s' % e)
                ok, rom = False, None
            self.logq.put(('__export_done__', ok, rom))

        threading.Thread(target=work, daemon=True).start()

    def on_play(self):
        from core import gba_build
        p = self.proj_ctx.get('gba_project') or gba_build.find_gba_project()
        if p:
            gba_build.run_emulator(p, log=self._log)

    # ---------------------------------------------------------- 后台日志
    def _log(self, text):
        self.logq.put(('__log__', str(text)))

    def _poll_events(self):
        try:
            while True:
                item = self.logq.get_nowait()
                kind = item[0]
                if kind == '__log__':
                    self.log_box.append(item[1])
                    self.log_box.verticalScrollBar().setValue(
                        self.log_box.verticalScrollBar().maximum())
                elif kind == '__export_done__':
                    ok, rom = item[1], item[2]
                    self.busy = False
                    if ok:
                        self._status('导出成功：%s' % os.path.basename(rom or ''))
                        if QMessageBox.askyesno('导出成功',
                                               'ROM 已生成：\n%s\n\n现在打开模拟器试玩吗？' % rom):
                            self.on_play()
                    else:
                        self._status('导出失败')
                        QMessageBox.showerror('导出失败', '看日志面板最后几行。')
        except queue.Empty:
            pass
        QTimer.singleShot(80, self._poll_events)   # Qt 用 QTimer 续期（不是 Tkinter 的 after）

    # ================================================================= 布局
    def reset_layout(self):
        for title, d in self.all_docks:
            d.setVisible(True)
        for mode, dock in self.mode_docks:
            dock.setVisible(mode is self.modes[self.mode_idx])
        self.toolbar.setVisible(True)
        self.resizeDocks([d for _, d in self.all_docks],
                         [260, 300, 360, 130], Qt.Vertical)
        self.resizeDocks([self.dock_assets, self.dock_inspector], [240, 300], Qt.Horizontal)
        self._status('面板布局已重置')

    def _save_layout(self):
        try:
            s = S.qsettings()
            s.setValue('geometry', self.saveGeometry())
            s.setValue('state', self.saveState())
        except Exception:
            pass

    def _restore_layout(self):
        try:
            s = S.qsettings()
            g = s.value('geometry')
            st = s.value('state')
            if g:
                self.restoreGeometry(g)
            if st:
                self.restoreState(st)
        except Exception:
            pass

    def _show_shortcuts(self):
        QMessageBox.information(self, '快捷键', '\n'.join([
            'Ctrl+N  新建项目        Ctrl+O  打开',
            'Ctrl+S  保存            Ctrl+Shift+S  另存为',
            'Ctrl+I  导入素材        F7  合规检查',
            'F5      导出 GBA        Ctrl+0  重置面板布局',
            'Delete  删除选中片段    空格  播放/暂停（P3）',
            '',
            '时间轴：拖片段移动 · 拖边缘改长度 · 点顶部窄条移播放头 · Ctrl+滚轮缩放',
        ]))

    def _show_about(self):
        QMessageBox.information(self, '关于', '\n'.join([
            APP_TITLE + ' —— 多模式 2D 游戏编辑器',
            '当前阶段：P1 骨架（剧情模式的时间轴已可用）',
            '',
            '设计要点：',
            '· 数据模型通用，加游戏类型 = 加一个模式模块',
            '· 编辑器只产出数据 + 调用现有 C 工具链编译 GBA ROM',
            '· 合规检查会在编译前拦住 GBA 硬限制问题',
        ]))

    def mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.update_title()

    def update_title(self):
        name = os.path.basename(self.file_path) if self.file_path else self.project.name
        self.setWindowTitle('%s —— %s%s' % (APP_TITLE, name, ' *' if self.dirty else ''))
