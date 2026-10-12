

# -*- coding: utf-8 -*-
"""验证：顶部改成台词序号刻度 / 吸附到其它片段 / 信息栏不再强调秒数"""
import os
import sys
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Project, Clip
import ui.timeline as T

# 显式加载样品工程（启动时给的是空工程，测试需要真实内容）
from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
_proj = Project.load(SAMPLE) if os.path.isfile(SAMPLE) else None
win = MainWindow(_proj, proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE if _proj else ''
win.resize(1300, 800)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()
s = win.project.scenes[0]
tv = win.timeline
tv.rebuild()

print('=== 1. 顶部：不画任何刻度（秒数不要，序号也不要） ===')
# 精确检查：**顶部窄条区域里不能有任何文字**
# （轨道名和片段标签是正当的，不能一概而论）
texts = [it for it in tv.scene_.items()
         if it.__class__.__name__ == 'QGraphicsSimpleTextItem']
in_ruler = [(it.text(), round(it.scenePos().y())) for it in texts
            if it.scenePos().y() < T.RULER_H]
print('   顶部窄条区里的文字:', in_ruler or '（空）')
print('   顶部窄条高度: %d px' % T.RULER_H)
assert not in_ruler, '顶上还画着东西: %s' % in_ruler
assert '句' not in [it.text() for it in texts], '顶上还有"句"'
assert not any(it.text().strip().isdigit() for it in texts), '还有序号数字'
print('   ✓ 顶部是一条干净的窄条')

print('\n=== 2. 片段标签就是台词内容（不带 #序号） ===')
labels = []
for it in tv._clip_items:
    if it.kind == 'text':
        labels.append(it.label_text)
print('   台词片段标签:', labels)
assert labels, '没有台词片段'
assert not any(x.startswith('#') for x in labels), '片段标签上还有 #序号'
assert '海风停了' in labels[0], labels
print('   ✓ 标签干净')

print('\n=== 3. 信息栏报句子数，不报秒数 ===')
mode._refresh_info()
info = mode.info.text()
n_text = len([c for c in s.clips if mode.kind_of(c) == 'text'])
n_voice = len([c for c in s.clips if mode.kind_of(c) == 'voice'])
print('   信息栏:', info)
assert '台词 %d 句' % n_text in info, '信息栏的台词句数不对（应为 %d）' % n_text
assert '语音 %d 条' % n_voice in info
assert '秒' not in info, '信息栏不该出现秒数'

print('\n=== 3b. "第几句"的信息还在（预览信息栏用得到） ===')
marks = tv.dialogue_marks()
print('   台词起点:', marks)
assert len(marks) == n_text, (len(marks), n_text)
assert [n for n, _ in marks] == list(range(1, n_text + 1))

print('\n=== 4. 吸附：拖到另一个片段起点附近会自动吸上去 ===')
bg1 = [c for c in s.clips if c.track == 'bg'][0]
bg2 = Clip('bg_2', 8.03, 4.0, 'show', 'x.png', {})   # 故意差一点
s.clips.append(bg2)
tv.rebuild()
# 把 bg2 的起点拖到 bg1 的起点附近（0.12 秒偏差，应该被吸到 0.00）
tv.px_per_sec = 26.0
snapped = tv.snap_time(0.12, ignore=bg2)
print('   0.12 秒 → 吸附到 %.2f（bg1 起点 %.2f）' % (snapped, bg1.start))
assert abs(snapped - bg1.start) < 1e-6, snapped
# 远处的值只按网格吸附
far = tv.snap_time(13.37, ignore=bg2)
print('   13.37 秒 → 网格吸附 %.2f' % far)
assert abs(far - 13.35) < 1e-6 or abs(far - 13.40) < 1e-6, far

print('\n=== 5. 属性标题显示"第 N 句" ===')
txt = [c for c in s.clips if c.track == 'text'][0]
mode.on_selection(txt)
app.processEvents()
body = win.inspector_body
t0 = body.itemAt(0).widget()
print('   属性首行:', t0.text() if hasattr(t0, 'text') else t0)
assert hasattr(t0, 'text') and '第 1 句' in t0.text(), t0.text()

print('\n✅ 全部通过')
