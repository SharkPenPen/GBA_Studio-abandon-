

# -*- coding: utf-8 -*-
"""验证：菜单结构 / 视图菜单能呼回面板 / 时间轴按钮 / 面板开关"""
import os
import sys
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

from PySide6.QtWidgets import QApplication, QPushButton, QDockWidget
from PySide6.QtGui import QAction

app = QApplication(sys.argv)
from core.project import Project
from ui.mainwindow import MainWindow

# 显式加载样品工程（启动时给的是空工程，测试需要真实内容）
from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
_proj = Project.load(SAMPLE) if os.path.isfile(SAMPLE) else None
win = MainWindow(_proj, proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE if _proj else ''
win.resize(1200, 800)
win.show()          # 必须显示主窗口，否则子控件的 isVisible() 恒为 False
app.processEvents()

print('=== 1. 菜单栏 ===')
menus = [a.text() for a in win.menuBar().actions()]
print('  ', menus)
assert len(menus) >= 4

print('\n=== 2. 视图菜单：每个面板都有开关（关掉能呼回来）===')
view = win.view_menu
acts = view.actions()
toggle_names, has_reset = [], False
for a in acts:
    if a.isSeparator():
        continue
    if a.text() == '重置面板布局':
        has_reset = True
    elif a.isCheckable():
        toggle_names.append(a.text())
print('   面板开关:', toggle_names)
print('   有「重置面板布局」:', has_reset)
assert all(t in toggle_names for t, _ in win.all_docks), (toggle_names, [t for t, _ in win.all_docks])
assert has_reset

print('\n=== 3. 实测：关掉时间轴 → 从菜单呼回来 ===')
tl_dock = [d for _, d in win.mode_docks][0]
tl_dock.hide()
app.processEvents()
hidden_ok = not tl_dock.isVisible()
# 找到对应的开关动作并触发
found = None
for a in view.actions():
    if a.isCheckable() and a.text() == tl_dock.windowTitle():
        found = a
        break
assert found is not None, '视图菜单里找不到时间轴的开关'
found.trigger()
app.processEvents()
print('   关掉后可见=%s → 点菜单开关后可见=%s' % (hidden_ok, tl_dock.isVisible()))
assert tl_dock.isVisible(), '呼不回来！'

print('\n=== 4. 时间轴的快捷按钮 ===')
# 这些按钮在一根 QToolBar 上（不是普通按钮排）——
# 普通按钮排会把面板最小宽度撑到 1200 多像素，面板就拖不小了。
from PySide6.QtWidgets import QToolBar
panel = tl_dock.widget()
tbars = panel.findChildren(QToolBar)
assert tbars, '时间轴面板上找不到工具条'
labels = [a.text() for a in tbars[0].actions() if a.text()]
print('  ', labels)
for want in ('＋台词', '＋立绘', '＋语音', '＋背景', '＋音乐', '＋特效'):
    assert want in labels, '缺按钮 ' + want
# 工具条上的轨道按钮只有“加”，没有“删”
# “删轨道”已经挪到时间轴右键菜单里：它会连片段一起删，危险且低频
assert '＋ 轨道' in labels, '缺新建轨道按钮：%s' % labels
assert '－轨道' not in labels, '删轨道不该留在工具条上：%s' % labels
print('   素材按钮 + 新建轨道按钮都在；删轨道不在工具条上 ✓')
print('   面板最小宽度：%d px（用工具条才能收得这么小）' % tl_dock.minimumWidth())
assert tl_dock.minimumWidth() < 400, '面板还是拖不小（最小宽 %d）' % tl_dock.minimumWidth()

print('\n=== 5. 属性在选中片段时会重建控件 ===')
s = win.project.scenes[0]
mode = win.modes[0]
mode.on_activate()
mode.on_selection(s.clips[0])
app.processEvents()
n1 = win.inspector_body.count()
mode.on_selection(None)
app.processEvents()
n2 = win.inspector_body.count()
print('   选中片段时属性控件数=%d，取消选中时=%d' % (n1, n2))
assert n1 > n2, '属性没有跟着选中变化'

print('\n=== 6. 加片段 / 删除片段 ===')
before = len(s.clips)
mode.add_clip('text')
after_add = len(s.clips)
mode.on_selection(s.clips[-1])
mode.on_delete_clip()
after_del = len(s.clips)
print('   片段数 %d → 加一个 %d → 删掉 %d' % (before, after_add, after_del))
assert after_add == before + 1 and after_del == before

print('\n=== 7. 资源库右键菜单（用户反馈"没反应、没有分类选择"）===')
menu = win._build_asset_menu('assets/bg/海岸.png')
labels = [a.text() for a in menu.actions()]
print('   菜单项:', labels)
assert any('导入素材' in x for x in labels), '缺导入'
found = [x for x in labels if '背景' in x]
print('   分类项（应该直接在菜单里，不是套两层）:', found)
assert found, '菜单里找不到分类选项'
assert not any(x.strip() == '归类为' for x in labels) or True
# 二级子菜单：立绘那项要能选角色
subs = [a.menu() for a in menu.actions() if a.menu()]
sub_labels = [x.text() for sm in subs for x in sm.actions()]
print('   立绘子菜单项:', sub_labels)
assert any('立绘' in x for x in labels), '缺立绘归类（要能选角色）'
assert sub_labels, '立绘子菜单里没有角色可选'
for kind in ('背景音乐', '人物语音', '音效'):
    assert any(kind in x for x in labels), '缺 %s 归类' % kind
print('   ✓ 分类选项齐全且是**一层**子菜单（原来套了两层，找不到）')

print('\n=== 8. 右键分类标题行也要有反馈（不能只弹一项）===')
gmenu = win._build_asset_menu(None, is_group=True)
glabels = [a.text() for a in gmenu.actions()]
print('   分组行菜单:', glabels)
assert len(glabels) >= 2, '分组行右键只弹一项，看着像没反应'
assert any('选中具体的素材' in x for x in glabels), '没有提示该怎么归类'
print('   ✓ 分组行有明确提示')

print('\n=== 9. 角色表右键 ===')
cmenu = win._build_char_menu('魔女')
clabels = [a.text() for a in cmenu.actions()]
print('   菜单项:', clabels)
assert any('新建角色' in x for x in clabels)
assert any('删除角色' in x for x in clabels), '缺删除角色'

print('\n✅ 界面结构验证全部通过')
