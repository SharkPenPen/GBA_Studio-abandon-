#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GBAStudio —— 多模式 2D 游戏编辑器

用法：
    python main.py                   启动 → **先看到项目列表**，双击进编辑器
    python main.py 工程.gbastudio     跳过列表，直接打开这个工程

【为什么改成"先列表再编辑器"】（界面参考 Pixel Game Maker MV）
以前双击就进编辑器，哪怕只是来看一眼，也得先对着一个空工程 ✗
现在分两层：
    Launcher（项目管理界面）  最近的项目 / 新建项目 / 示例
        ↓ 双击一个项目
    MainWindow（编辑器）      时间轴 / 预览 / 资源 / 属性
打开的项目会记进"最近的项目"，关掉编辑器又回到列表 ——
和 PGMMV 一样，所以"我现在有哪些项目"这件事始终在第一屏。

设计要点见 docs/15（框架审查）：
  · 三层分离：引擎（C）/ 数据模型（core/）/ 界面（ui/、modes/）
  · 加新游戏类型 = 加一个 Mode 模块 + 在 modes/__init__.py 登记一行
  · 编辑器只产出数据 + 调工具链，编译逻辑不重写
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 高 DPI 下界面不发虚（必须在 QApplication 之前设置）
os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')

# Qt 在 Windows 上找不到自己的字体目录时会**每次启动都打一行警告** ✗
# （"QFontDatabase: Cannot find font directory ... Qt no longer ships fonts"）
# 它不影响使用，但很吵。指向系统字体目录就没这行了。
if os.name == 'nt' and 'QT_QPA_FONTDIR' not in os.environ:
    _fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    if os.path.isdir(_fonts):
        os.environ['QT_QPA_FONTDIR'] = _fonts


class App:
    """把"启动器"和"编辑器窗口"串起来的那点胶水。

    单独写一个类是为了让两件事能各自独立测试：
        · 启动器不依赖编辑器（测试里可以只开启动器）
        · 编辑器不依赖启动器（命令行直接给路径时，启动器完全不参与）
    """

    def __init__(self, app):
        self.app = app
        self.win = None            # 编辑器窗口（每次打开项目时新建）
        self.launcher = None

    # ---- 启动器 ----
    def show_launcher(self):
        from ui.launcher import Launcher
        if self.launcher is None:
            self.launcher = Launcher()
            self.launcher.open_project.connect(self.open_project)
            self.launcher.new_project.connect(self.create_project)
        self.launcher.refresh_recent()
        self.launcher.show()
        self.launcher.raise_()
        self.launcher.activateWindow()

    # ---- 打开 / 新建 ----
    def open_project(self, path):
        from PySide6.QtWidgets import QMessageBox
        from core.project import Project
        from core.gba_build import find_gba_project
        from ui.mainwindow import MainWindow
        from ui.launcher import RecentStore
        try:
            proj = Project.load(path)
        except Exception as e:                              # noqa: BLE001
            QMessageBox.critical(self.launcher, '打开失败', '%s\n\n%s' % (path, e))
            return
        RecentStore().touch(path, proj.name)
        if self.launcher:
            self.launcher.hide()

        # 已经有编辑器窗口 → 先关掉它 ✗
        # 不关的话每打开一个项目就多留一个窗口（而且是不可见的孤儿窗口）。
        # 关之前把 on_closed 摘掉：否则它会"关掉→回启动器"，把刚藏起来的启动器又弹出来。
        if self.win is not None:
            try:
                self.win.on_closed = None
                self.win.dirty = False
                self.win.close()
            except Exception:                              # noqa: BLE001
                pass
            self.win = None

        self.win = MainWindow(proj, proj_ctx={'gba_project': find_gba_project()})
        self.win.file_path = path
        self.win.update_title()
        # 关掉编辑器 → 回到项目列表（不然想换个项目得把程序整个重开）
        self.win.on_closed = self.back_to_launcher
        # 编辑器菜单「文件 → 新建项目」转到这里（创建界面只留启动器那一套）
        self.win.on_request_new = self.request_new_project
        self.win.show()
        # **光 show() 不够** ✗ 新窗口可能开在启动器后面，
        # 用户看到的是"启动器还在"，以为没关掉 ✓
        # 所以：先 hide 启动器，再把编辑器 raise + activate。
        if self.launcher:
            self.launcher.hide()
        self.win.raise_()
        self.win.activateWindow()
        self._fix_dock_sizes(self.win)

    def create_project(self, v):
        """在启动器里点「创建」时走这里"""
        from PySide6.QtWidgets import QMessageBox
        from core import assets as A
        from core.project import blank_project, demo_project
        from ui.launcher import RecentStore, make_thumb
        import os as _os
        folder = _os.path.join(v['dir'], v['name'])
        try:
            _os.makedirs(folder, exist_ok=True)
            A.ensure_dirs(folder)
            proj = demo_project(v['name']) if v['template'] == 'demo' \
                else blank_project(v['name'], video_mode=v.get('video_mode', 3))
            # 显示模式是架构级选择：两种模板都要按用户选的来
            proj.settings['video_mode'] = v.get('video_mode', 3)
            path = _os.path.join(folder, '%s.gbastudio' % v['name'])
            proj.save(path)
        except Exception as e:                              # noqa: BLE001
            QMessageBox.critical(self.launcher, '新建失败', '建目录/写文件出错：\n%s' % e)
            return
        RecentStore().touch(path, v['name'])
        try:
            make_thumb(path)          # 先生成缩略图，回列表时就能看到
        except Exception:                                   # noqa: BLE001
            pass
        self.open_project(path)

    def request_new_project(self):
        """编辑器里点「新建项目」→ 回到启动器的创建页（唯一的一套创建界面）"""
        self.show_launcher()
        if self.launcher:
            self.launcher.focus_new_tab()

    def back_to_launcher(self):
        if self.win is not None:
            self.win = None
        self.show_launcher()

    # ---- 编辑器默认布局 ----
    @staticmethod
    def _fix_dock_sizes(win):
        """默认布局：**时间轴要一打开就看得见全部轨道**。

        为什么先用 setMinimumHeight 而不是直接 resizeDocks：
        实测 resizeDocks 会"打个折" —— 请求 230 像素只给到 134，
        结果时间轴只露出两条轨道，新用户会以为"只有一条轨道" ✗
        设最小高度是硬约束，Qt 一定满足；等布局稳定之后（300 毫秒后）
        再放开最小高度，用户照样能把它拖小。
        """
        from PySide6.QtCore import Qt, QTimer

        def fix():
            docks = [d for _, d in win.mode_docks]
            need = win.timeline.preferred_height() + 44      # 44 给面板上的工具条
            if docks:
                win.timeline.setMinimumHeight(need)
                # 日志是"状态栏"性质，默认给一条窄的就够；
                # 不压的话它会和预览一起分掉下半屏（实测占到 298 像素）
                win.dock_log.setMaximumHeight(130)
                win.resizeDocks(docks + [win.dock_log],
                                [max(200, need)] * len(docks) + [110], Qt.Vertical)
                win.resizeDocks([win.dock_assets, win.dock_inspector],
                                [230, 300], Qt.Horizontal)

            def relax():
                # 布局已经定型，把"硬约束"恢复成"软限制"，用户就能自由拖了
                win.timeline.setMinimumHeight(70)
                win.dock_log.setMaximumHeight(16777215)

            QTimer.singleShot(300, relax)

        QTimer.singleShot(60, fix)


def main():
    from PySide6.QtWidgets import QApplication
    from ui import settings as S

    app = QApplication(sys.argv)
    app.setApplicationName('GBAStudio')
    # 界面字体和预览缩放存在 %APPDATA%（属于"这台机器的偏好"，不是工程数据）
    S.load()
    app.setFont(S.font())

    core = App(app)

    # 命令行直接给了工程 → 跳过列表（从文件管理器双击 .gbastudio 走这条）
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        core.open_project(sys.argv[1])
    else:
        core.show_launcher()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
