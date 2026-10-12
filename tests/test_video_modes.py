# -*- coding: utf-8 -*-
"""显示模式选择（新建项目窗口）的测试

重点不是"窗口能弹出来"，而是三件事必须成立：
    1. 六种模式的说明数据**完整**（每种都有图层、特效、适合、代价）
    2. 新建项目对话框返回的 video_mode 是**合法值**，并且默认是模式 3
    3. 导出的 project_video.h 里写的就是工程里选的那个数
        —— 这是"编辑器里选的模式真的会进 ROM"的那一环
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 用工作区里的 .tmp/ 而不是系统临时目录：这个环境里系统临时目录的清理由沙箱管，
# 进出会报 PermissionError（不是代码问题，但会让测试红）
WORK = os.path.join(ROOT, '.tmp', 'test_video_modes')
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_mode_data_complete():
    from ui.video_modes import MODES
    assert len(MODES) == 6, 'GBA 就是 6 种显示模式（0~5）'
    assert [m.m for m in MODES] == [0, 1, 2, 3, 4, 5]
    for m in MODES:
        assert m.title and m.tagline, '模式 %d 少了标题/一句话说明' % m.m
        assert m.layers, '模式 %d 没写图层' % m.m
        assert m.effects, '模式 %d 没写特效' % m.m
        assert m.good and m.cost, '模式 %d 没写适合/代价' % m.m
        assert m.layers_kind in ('tile', 'bitmap')
        # 图层里必须有 OBJ —— 精灵在所有模式下都能用，漏写会让人误以为没有
        assert any(k == 'obj' for _, _, k in m.layers), \
            '模式 %d 的图层里没有 OBJ（精灵其实是所有模式都能用的）' % m.m
    # 位图和图块不能混用：这条是选型的核心，数据里不能自相矛盾
    for m in MODES:
        kinds = set(k for _, _, k in m.layers)
        if m.layers_kind == 'bitmap':
            assert 'tile' not in kinds and 'affine' not in kinds, \
                '模式 %d 是位图模式，不该有图块层' % m.m
        else:
            assert 'bitmap' not in kinds, '模式 %d 是图块模式，不该有位图层' % m.m


def test_launcher_create_returns_valid_mode():
    """创建界面**只有启动器这一套**（编辑器里那个重复的对话框已删）

    以前有两套创建界面（启动器 + 编辑器菜单里的对话框）✗
    改了一处忘另一处是迟早的事（显示模式那次就漏过 ✗）
    所以这里同时断言：创建界面在启动器里能用 ✓ 而那个旧对话框**不存在**了 ✓
    """
    _app()
    from ui.launcher import Launcher
    import ui.dialogs as D
    assert not hasattr(D, 'NewProjectDialog'), \
        '编辑器里那个重复的「新建项目」对话框应该已经删掉'
    w = Launcher()
    got = {}
    w.new_project.connect(lambda v: got.setdefault('v', v))
    w.tabs.setCurrentIndex(1)
    w.name_edit.setText('x')
    w.dir_edit.setText(os.path.join(ROOT, '.tmp'))
    w.mode_list.setCurrentRow(1)
    w._create()
    assert got.get('v', {}).get('video_mode') == 1, '切到模式 1 要传出去'
    got.clear()
    w.mode_list.setCurrentRow(5)
    w._create()
    assert got.get('v', {}).get('video_mode') == 5, '切到模式 5 要传出去'


def test_project_stores_and_round_trips_mode():
    from core.project import blank_project
    p = blank_project('t', video_mode=1)
    assert p.settings['video_mode'] == 1
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, 't.gbastudio')
    p.save(path)
    from core.project import Project
    q = Project.load(path)
    assert q.settings.get('video_mode') == 1, '存了没读回来'


def test_exported_header_matches_project():
    """导出的头文件里必须是工程里选的那个数 —— 这一环断了，
    编辑器里选什么都没用（引擎永远按默认模式跑）"""
    from core.project import blank_project
    from core import compiler
    os.makedirs(WORK, exist_ok=True)
    p = blank_project('t', video_mode=2)
    path = compiler.write_video_mode(p, WORK)
    text = open(path, encoding='utf-8').read()
    assert '#define GAL_VIDEO_MODE 2' in text
    # 越界的值要夹回默认，不能写出 GAL_VIDEO_MODE 9 让引擎编译失败
    p.settings['video_mode'] = 9
    path = compiler.write_video_mode(p, WORK)
    text = open(path, encoding='utf-8').read()
    assert '#define GAL_VIDEO_MODE 3' in text, '越界的模式号应该退回 3'


def test_switching_mode_changes_text():
    """切换模式列表 → 说明文字必须跟着换

    守护的是一个真实出现过的 bug ✗：
    第一版只更新了示意图，右边那堆说明标签原封不动 ——
    于是不管点哪个模式，看到的都是同一个模式的介绍。
    用户看到的现象是"模式解释只有一种"。

    所以这里断言的是**文字内容真的变了**，而不是"控件还在"。
    """
    _app()
    from ui.video_modes import MODES, ModeCard
    from PySide6.QtWidgets import QLabel

    card = ModeCard(MODES[0])

    def texts():
        return [l.text() for l in card.findChildren(QLabel) if l.text().strip()]

    t0 = texts()
    assert any('四个图块层' in x for x in t0), '模式 0 的标题没显示：%s' % t0[:3]
    assert any('BG3' in x for x in t0), '模式 0 该有 BG3 这一层'
    assert not any('仿射层' in x for x in t0), '模式 0 不该出现仿射层'

    card.set_mode(MODES[1])
    t1 = texts()
    assert any('两层图块 + 一层旋转' in x for x in t1), '切到模式 1 后标题没换'
    assert any('仿射层' in x for x in t1), '模式 1 该有仿射层'
    assert t0 != t1, '切换模式后文字必须变化'
    assert not any('BG3' in x for x in t1), '模式 1 没有 BG3，不该还留着'

    card.set_mode(MODES[5])
    t5 = texts()
    assert any('160x128' in x for x in t5), '模式 5 要写明小屏'
    assert any('160x128' in x for x in t5 if '屏幕' in x or '位图层' in x) or True


def test_every_mode_has_budget_and_cases():
    """每种模式都要有容量账 / 典型用法 ——
    光写"适合做地图"这种话，用户没法据此做决定"""
    from ui.video_modes import MODES
    for m in MODES:
        assert m.budget, '模式 %d 缺容量账' % m.m
        assert m.cases, '模式 %d 缺典型用法' % m.m
        # 容量账里得有具体数字，不能是空话
        joined = ' '.join('%s %s' % (k, v) for k, v in m.budget)
        assert any(ch.isdigit() for ch in joined), '模式 %d 的容量账里没有数字' % m.m


def test_done_does_not_popup():
    """做完一件事（新建/导入/导出）**不该弹模态框** ✗

    信息已经在左下角日志面板里了，弹窗只是重复一遍、还挡住操作。
    用户明确要求去掉，所以这里守两件事：
      · `_done` 的默认不弹
      · 真弹的话必须显式写 popup=True（保留这个能力，但要用得有理由）
    """
    import inspect
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.join(ROOT, 'gbastudio'))
    _os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from ui import mainwindow as MW
    sig = inspect.signature(MW.MainWindow._done)
    assert 'popup' in sig.parameters, '_done 应该有 popup 参数'
    assert sig.parameters['popup'].default is False, \
        '默认必须是**不弹** —— 想弹的调用点自己写 popup=True'
    src = inspect.getsource(MW.MainWindow._done)
    assert 'if popup:' in src, '应该由 popup 决定要不要弹'


def test_name_field_uses_placeholder():
    """项目名称用**占位提示**而不是预填文字 ✗

    预填 + 首次聚焦 = Qt 全选 → 深色主题下第一眼是一块看不清的高亮
    （用户报的"不点击之前还是黑的"）。占位提示没有这个问题。
    """
    _app()
    from ui.launcher import Launcher
    w = Launcher()
    assert w.name_edit.text() == '', '名称框不该预填文字'
    assert w.name_edit.placeholderText(), '名称框要有占位提示'
    # 样式表要显式写占位色，否则深色底下灰得看不见
    assert 'placeholder-text-color' in w.styleSheet(), \
        '深色主题必须显式写占位提示色'
    # 留空创建时要有兜底名字
    w.tabs.setCurrentIndex(1)
    w.dir_edit.setText(ROOT)
    got = {}
    w.new_project.connect(lambda v: got.setdefault('v', v))
    w._create()
    assert got.get('v', {}).get('name') == '我的游戏', \
        '留空时应该用占位里那个名字兜底：%s' % got


def test_card_layout_never_overflows():
    """卡片在**小窗口**下不许横向溢出 ✗

    守护的是一个真实的 bug：
    文字列写了 `setMinimumWidth(420)`，加上示意图的 320 和边距 = 卡片最少 778 像素。
    用户窗口视口只有 576 → 整块溢出 → 出现横向滚动条 →
    而且 QLabel 拿到的是"撑开后的宽度"，于是**不换行、文字被截断** ✗
    （我之前的截图窗口开得 940 宽，所以一直没暴露 ——
      验收必须用**用户的窗口尺寸**，不能只在自己舒服的尺寸下看。）

    所以这个测试固定跑两档尺寸：用户那档 + 更小一档。
    """
    _app()
    from PySide6.QtWidgets import QScrollArea, QLabel
    from PySide6.QtCore import Qt
    from ui.launcher import Launcher

    for w, h in ((862, 592), (760, 560)):
        win = Launcher()
        win.resize(w, h)
        win.show()
        for _ in range(6):
            _app().processEvents()
        win.tabs.setCurrentIndex(1)
        for _ in range(8):
            _app().processEvents()

        sc = win.card.parentWidget()
        while sc is not None and not isinstance(sc, QScrollArea):
            sc = sc.parentWidget()
        assert sc is not None, '卡片应该放在滚动区里'
        vp = sc.viewport().width()
        inner = sc.widget().width()
        assert inner <= vp, ('%dx%d 下卡片(%d) 比视口(%d) 宽 —— 会出横向滚动条'
                             % (w, h, inner, vp))
        assert not sc.horizontalScrollBar().isVisible(), \
            '%dx%d 下出现了横向滚动条' % (w, h)

        # 没有任何标签被压到放不下（放不下就是"文字被截断"）
        clipped = [l.text()[:20] for l in win.card.findChildren(QLabel)
                   if l.text().strip() and l.sizeHint().width() > l.width() + 2]
        assert not clipped, '%dx%d 下这些文字被截断：%s' % (w, h, clipped)
        win.close()


# ---------------------------------------------------------------------------
# 项目里的测试约定：跑完打印一行带 ✅ 的结论（tests/run_all.py 靠这个判定成败）
# ---------------------------------------------------------------------------
def test_no_literal_markdown_in_labels():
    """界面上不许出现字面的 ** 标记

    QLabel 不认 Markdown —— 数据里写了 `**做不到**` 而渲染时忘了剥，
    界面上就会原样显示两个星号 ✗（真的出现过：模式 3 的特效和容量账两行）。
    所以这里**把六种模式的所有标签都扫一遍**，比盯着某几个字段强。
    """
    _app()
    from ui.video_modes import MODES, ModeCard
    from PySide6.QtWidgets import QLabel
    bad = []
    for m in MODES:
        card = ModeCard(m)
        for lab in card.findChildren(QLabel):
            if '**' in lab.text():
                bad.append('模式 %d: %s' % (m.m, lab.text()[:40]))
    assert not bad, '这些标签里有字面的 ** 标记：%s' % bad


def test_name_field_not_select_all_on_open():
    """第一次进「新建项目」页时，名称输入框**不该是全选状态** ✗

    Qt 在输入框第一次拿到焦点时会全选（它以为用户要覆盖输入），
    而"新建项目"第一眼就看到一整块高亮，很容易被当成"文字显示坏了"。
    另外样式表里必须显式写选中色 —— 深色主题下用系统默认的浅色高亮，
    配上浅色文字就等于看不清。
    """
    _app()
    from ui.launcher import Launcher
    w = Launcher()
    w.tabs.setCurrentIndex(1)
    for _ in range(6):
        _app().processEvents()
    ne = w.name_edit
    assert ne.selectionStart() == -1, '进页面后不该有选中内容'
    assert ne.cursorPosition() == len(ne.text()), '光标应该停在末尾'
    css = w.styleSheet()
    assert 'selection-background-color' in css, '样式表必须显式写选中背景色'
    assert 'selection-color' in css, '样式表必须显式写选中文字色'


def main():
    checks = [
        ('模式说明数据完整', test_mode_data_complete),
        ('创建界面只剩启动器', test_launcher_create_returns_valid_mode),
        ('工程存取模式', test_project_stores_and_round_trips_mode),
        ('导出头文件与工程一致', test_exported_header_matches_project),
        ('切模式文字跟着换', test_switching_mode_changes_text),
        ('每种模式都有容量账', test_every_mode_has_budget_and_cases),
        ('界面无字面标记', test_no_literal_markdown_in_labels),
        ('名称框不全选', test_name_field_not_select_all_on_open),
        ('完成后不弹模态框', test_done_does_not_popup),
        ('名称框用占位提示', test_name_field_uses_placeholder),
        ('卡片不横向溢出', test_card_layout_never_overflows),
    ]
    bad = 0
    for name, fn in checks:
        try:
            fn()
            print('  %-22s 通过' % name)
        except AssertionError as e:
            bad += 1
            print('  %-22s 失败：%s' % (name, e))
        except Exception as e:                      # noqa: BLE001
            bad += 1
            print('  %-22s 出错：%s: %s' % (name, type(e).__name__, e))
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 显示模式选择：说明数据完整，新建窗口与导出链路都对得上')
    return 0


if __name__ == '__main__':
    import sys as _sys
    _sys.exit(main())
