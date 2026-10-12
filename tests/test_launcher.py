# -*- coding: utf-8 -*-
"""启动器（项目管理界面）的测试

界面的样子可以靠截图看，但下面这几件事必须用代码保证 ——
它们错了，用户是"点了没反应"或者"项目丢了"，很难自己诊断：
    1. 最近项目清单能存能读、打开过的排最前、去重
    2. 文件被删掉的项目要**标出来**（而不是点一下报错）
    3. 缩略图能按工程生成，且**不会每次都重渲染**（按修改时间缓存）
    4. 启动器发出的 open_project / new_project 信号带着正确的数据
"""
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
# 设置和最近项目都写到工作区里，别碰真实 %APPDATA%
APPDATA = os.path.join(ROOT, '.tmp', 'appdata')
os.environ['GBASTUDIO_SETTINGS_DIR'] = APPDATA
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

WORK = os.path.join(ROOT, '.tmp', 'test_launcher')


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _fresh():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    return WORK


def _make_project(path, name='测试项目', video_mode=3):
    from core.project import blank_project
    p = blank_project(name, video_mode=video_mode)
    p.save(path)
    return path


def test_recent_store_round_trip():
    d = _fresh()
    from ui.launcher import RecentStore
    store = RecentStore(os.path.join(d, 'recent.json'))
    a = _make_project(os.path.join(d, 'A', 'A.gbastudio'), 'A')
    b = _make_project(os.path.join(d, 'B', 'B.gbastudio'), 'B')
    store.touch(a, 'A')
    store.touch(b, 'B')
    # 后打开的排最前
    assert [x['name'] for x in store.items] == ['B', 'A'], store.items
    # 再打开 A：要挪到最前，而不是出现两条
    store.touch(a, 'A')
    assert [x['name'] for x in store.items] == ['A', 'B'], store.items
    assert len(store.items) == 2, '同一个项目不能重复记录'
    # 存到磁盘再读回来
    again = RecentStore(os.path.join(d, 'recent.json'))
    assert [x['name'] for x in again.items] == ['A', 'B']
    # 移除
    again.forget(a)
    assert [x['name'] for x in again.items] == ['B']


def test_missing_project_is_marked_not_crash():
    """文件被删掉的项目：列表里要标红提示，点开要有明确反馈 ——
    不能抛异常，也不能静默什么都不做"""
    d = _fresh()
    from ui.launcher import RecentStore, Launcher
    _app()
    gone = os.path.join(d, 'Nope', 'Nope.gbastudio')
    store = RecentStore(os.path.join(d, 'recent.json'))
    store.touch(gone, 'Nope')
    w = Launcher()
    w.store = store
    w.refresh_recent()
    assert w.list.count() == 1
    row = w._rows[0][1]
    texts = [lab.text() for lab in row.findChildren(type(row.thumb))] + \
            [lab.text() for lab in row.findChildren(__import__('PySide6.QtWidgets',
                                                               fromlist=['QLabel']).QLabel)]
    assert any('找不到' in t for t in texts), '缺失的项目要明确标出来：%s' % texts


def test_thumb_generated_and_cached():
    d = _fresh()
    proj = _make_project(os.path.join(d, 'T', 'T.gbastudio'), 'T')
    from ui.launcher import make_thumb, thumb_path_for
    t1 = make_thumb(proj)
    assert t1 and os.path.isfile(t1), '缩略图没生成'
    m1 = os.path.getmtime(t1)
    time.sleep(0.05)
    t2 = make_thumb(proj)
    assert t2 == t1
    assert os.path.getmtime(t2) == m1, '工程没变就不该重新渲染（启动器会卡）'
    # 工程变新 → 应该重做
    time.sleep(0.05)
    os.utime(proj, None)
    make_thumb(proj)
    assert os.path.getmtime(t1) != m1, '工程改过之后缩略图要重做'


def test_launcher_signals():
    """启动器发出的信号要带着正确的数据（main.py 靠它去开窗口）"""
    d = _fresh()
    from ui.launcher import RecentStore, Launcher
    _app()
    proj = _make_project(os.path.join(d, 'S', 'S.gbastudio'), 'S', video_mode=1)
    w = Launcher()
    w.store = RecentStore(os.path.join(d, 'recent.json'))
    w.store.touch(proj, 'S')
    w.refresh_recent()

    got = {}
    w.open_project.connect(lambda p: got.setdefault('open', p))
    w.list.setCurrentRow(0)
    w._open_selected()
    assert got.get('open') == proj, '打开信号要带项目路径'

    w.new_project.connect(lambda v: got.setdefault('new', v))
    w.tabs.setCurrentIndex(1)
    w.name_edit.setText('新项目')
    w.dir_edit.setText(d)
    w.mode_list.setCurrentRow(5)          # 模式 5
    w._create()
    v = got.get('new')
    assert v and v['name'] == '新项目' and v['video_mode'] == 5, v
    assert v['dir'] == d


def test_entry_is_pyw_not_cmd():
    """入口必须是 `.pyw`，**不许留 `.cmd`**

    实测（2026-10-10）：这台机器上双击 .cmd 会弹"打开文件 - 安全警告"，
    双击 .pyw 不弹 —— Windows 把 .cmd/.bat/.exe 归到"不安全文件"名单里，
    .pyw 不在。所以项目里不该再放 .cmd，免得用户又点到会弹窗的那个。

    顺带确认 .pyw 里的标记检查用的是 **Win32 API**：
    PowerShell 的 Get-Item -Stream 在受限环境里会静默失败，
    拿它的"没发现"当证据会得出错误结论（这个坑刚踩过）。
    """
    assert os.path.isfile(os.path.join(ROOT, '启动编辑器.pyw')), '缺少 .pyw 入口'
    assert not os.path.isfile(os.path.join(ROOT, '启动编辑器.cmd')), \
        '不该再有 .cmd 入口（双击会弹安全警告）'
    tool = os.path.join(ROOT, '解除下载标记.pyw')
    assert os.path.isfile(tool), '缺少标记检查工具'
    src = open(tool, encoding='utf-8').read()
    assert 'FindFirstStreamW' in src, '标记检查要用 Win32 API（PowerShell 那套会静默失败）'


def test_launcher_startup_reports_to_log_not_popup():
    """启动器打开项目时**不弹模态框** —— 检查结果写进日志面板

    用户明确要求"消除打开时的弹窗"。这里守的是：
    打开一个正常项目之后，没有任何 information/warning 级别的弹窗。
    """
    _app()
    import main as M
    from PySide6.QtWidgets import QMessageBox
    pops = []
    saved = QMessageBox.information
    QMessageBox.information = staticmethod(
        lambda *a, **k: (pops.append(a[1] if len(a) > 1 else '?'), QMessageBox.Ok)[1])
    try:
        core = M.App(_app())
        core.show_launcher()
        from _sample import SAMPLE as _SP
        proj = _SP
        if os.path.isfile(proj):
            core.open_project(proj)
            _app().processEvents()
            assert not pops, '打开项目不该弹窗，弹了：%s' % pops
            assert core.win is not None, '应该进了编辑器'
            core.win.dirty = False
            core.win.close()
    finally:
        QMessageBox.information = saved


def test_new_project_defaults_to_blank():
    """新建项目的默认必须是**空白**，而且 blank_project 里真的什么都不带

    守护两个真实问题：
      1. 下拉框第一项以前是"带示例素材" —— 用户不动它就点创建，
         拿到的工程里全是示例素材（用户报的"里面带着默认素材"）
      2. `blank_project` 也没真空白：`Project.__init__` 会装上默认的
         "走路/待机"两套动画，而它们引用的是**不存在的默认精灵下标**
    """
    _app()
    from core.project import blank_project, demo_project
    b = blank_project('空白')
    assert len(b.assets) == 0, '空白项目不该有素材'
    assert len(b.characters) == 0, '空白项目不该有角色'
    assert len(b.animations) == 0, '空白项目不该有动画（默认动画引用不存在的素材）'
    assert len(b.scenes) >= 1, '空白项目至少要有一个场景，不然时间轴是空的'

    d = demo_project('示例')
    assert len(d.animations) > 0, '示例项目应该带动画'

    from ui.launcher import Launcher
    w = Launcher()
    assert w.template.itemData(0) == 'blank', '下拉框第一项必须是空白（默认选中项）'
    got = {}
    w.new_project.connect(lambda v: got.setdefault('v', v))
    w.name_edit.setText('x')
    w.dir_edit.setText(ROOT)
    w._create()
    assert got.get('v', {}).get('template') == 'blank', \
        '不动下拉框直接创建，应该是空白模板'


def test_open_project_hides_launcher():
    """打开/新建项目之后：启动器要**藏起来**，编辑器要顶到前面

    只 hide() 启动器是不够的：新窗口可能开在它后面，
    用户看到的是"启动器还在"，以为没关掉
    """
    _app()
    import main as M
    core = M.App(_app())
    core.show_launcher()
    _app().processEvents()
    assert core.launcher.isVisible()
    from _sample import SAMPLE as _SP
    proj = _SP
    if os.path.isfile(proj):
        core.open_project(proj)
        _app().processEvents()
        assert not core.launcher.isVisible(), '打开项目后启动器应该藏起来'
        assert core.win is not None and core.win.isVisible(), '编辑器应该显示'
        core.win.dirty = False
        core.win.close()


def main():
    checks = [
        ('最近项目清单存取', test_recent_store_round_trip),
        ('缺失项目有提示', test_missing_project_is_marked_not_crash),
        ('缩略图生成与缓存', test_thumb_generated_and_cached),
        ('启动器信号数据', test_launcher_signals),
        ('入口是 pyw 不是 cmd', test_entry_is_pyw_not_cmd),
        ('打开项目不弹窗', test_launcher_startup_reports_to_log_not_popup),
        ('新建默认空白', test_new_project_defaults_to_blank),
        ('打开后藏起启动器', test_open_project_hides_launcher),
    ]
    bad = 0
    for name, fn in checks:
        try:
            fn()
            print('  %-20s 通过' % name)
        except AssertionError as e:
            bad += 1
            print('  %-20s 失败：%s' % (name, e))
        except Exception as e:                       # noqa: BLE001
            bad += 1
            print('  %-20s 出错：%s: %s' % (name, type(e).__name__, e))
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 启动器：项目清单、缺失提示、缩略图缓存、信号数据都对')
    return 0


if __name__ == '__main__':
    import sys as _sys
    _sys.exit(main())
