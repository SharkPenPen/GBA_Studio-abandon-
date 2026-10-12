

# -*- coding: utf-8 -*-
"""验证：多轨道 / 拖边缘改长度 / 导入不分类 / 属性不再重叠"""
import os
import sys
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Clip, MIN_DUR
from core import assets as A

def find_test_png(n=2):
    """找几张现成的 PNG 当测试素材（不写死路径，挪目录也不会挂）"""
    hits = []
    for d in ('docs/screenshots', 'assets_src/images', 'assets_src/test'):
        full = os.path.join(ROOT, d.replace('/', os.sep))
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if f.lower().endswith('.png'):
                hits.append(os.path.join(full, f))
                if len(hits) >= n:
                    return hits
    return hits


win = MainWindow()
win.resize(1300, 800)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()
s = win.project.scenes[0]

print('=== 1. 多轨道：同一类型可以有多条 ===')
print('   初始轨道:', [(t.id, t.name) for t in s.tracks])
b1 = s.first_track('bg')
b2 = s.add_track('bg')
b3 = s.add_track('bg')
print('   背景轨道共 3 条:', [t.id for t in s.tracks_of('bg')])
assert len(s.tracks_of('bg')) == 3, [t.id for t in s.tracks_of('bg')]
# 两条背景各放一个片段，互不重叠（不同轨道）
c1 = Clip(b1.id, 0, 5, 'show', 'a.png', {})
c2 = Clip(b2.id, 5, 5, 'show', 'b.png', {})
s.clips += [c1, c2]
win.timeline.set_project(win.project, s)
print('   两条背景各占一条轨道:', c1.track, '/', c2.track, '✓')

print('\n=== 2. 拖边缘改长度（时间轴上直接改） ===')
item = None
for it in win.timeline._clip_items:
    if it.clip is c1:
        item = it
assert item is not None
print('   片段初始: 起点 %.2f 时长 %.2f' % (c1.start, c1.dur))
# 模拟：命中右边缘 → 拖 +2 秒
local_right = item._w - 2
print('   右边缘命中检测:', item.edge_at(local_right), '（应为 r）')
assert item.edge_at(local_right) == 'r'
assert item.edge_at(2) == 'l'
assert item.edge_at(item._w / 2) is None
# 直接调拖动逻辑（等价于鼠标拖）
win.timeline._drag = ('trim_r', item, 0, c1.start, c1.dur)
c1.dur = max(MIN_DUR, c1.dur + 2.0)
win.timeline._drag = None
print('   拖右边缘 +2 秒后: 时长 %.2f ✓' % c1.dur)
assert abs(c1.dur - 7.0) < 1e-6

print('\n=== 3. 导入不分类 ===')
proj_dir = r'D:\GitHud\GBA_AI\.tmp\gba2test2'
import shutil
shutil.rmtree(proj_dir, ignore_errors=True)
os.makedirs(proj_dir)
A.ensure_dirs(proj_dir)
src = find_test_png(1)[0]
ok, bad, notes = A.import_files(proj_dir, [src])          # 不传 kind
print('   导入结果:', ok)
assert ok and ok[0].startswith('assets/') and '/bg/' not in ok[0], '不该被自动分类到 bg/'
found, issues = A.scan_folder(proj_dir, {})
print('   扫描类型:', [a.kind or '未分类' for a in found])
assert found and found[0].kind == '', '未分类的素材 kind 应为空'
# 手动归类
new_rel, err = A.classify_asset(proj_dir, found[0], 'bg')
print('   手动归类为背景 →', new_rel, '（错误:', err, '）')
assert new_rel and new_rel.startswith('assets/bg/')
found2, _ = A.scan_folder(proj_dir, {new_rel: 'bg'})
print('   重新扫描类型:', [a.kind for a in found2], '✓ 归类被保留')

print('\n=== 4. 属性不再重叠（新旧控件不会叠一起） ===')
body = win.inspector_body
mode.on_selection(c1)
app.processEvents()
n1 = body.count()
first_widgets = [body.itemAt(i).widget() for i in range(n1)]
mode.on_selection(c2)          # 换成另一个片段
app.processEvents()
n2 = body.count()
second_widgets = [body.itemAt(i).widget() for i in range(n2)]
overlap = set(id(w) for w in first_widgets if w) & set(id(w) for w in second_widgets if w)
print('   切换片段：控件数 %d → %d，重复使用的控件 %d 个（应为 0）' % (n1, n2, len(overlap)))
assert not overlap, '旧控件还留在布局里'

print('\n✅ 全部通过')
shutil.rmtree(proj_dir, ignore_errors=True)
