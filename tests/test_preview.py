

# -*- coding: utf-8 -*-
"""P3 验收：预览渲染 + 播放 + 跟着播放头/编辑刷新"""
import os
import sys
import time
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from ui.mainwindow import MainWindow
from core.project import Project

from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
win = MainWindow(Project.load(SAMPLE), proj_ctx={'gba_project': ROOT})
win.file_path = SAMPLE
win.resize(1300, 860)
win.show()
app.processEvents()
mode = win.modes[0]
mode.on_activate()
scene = win.project.scenes[0]

print('=== 1. 预览用的是真实渲染（不再是占位图） ===')
win.timeline.set_playhead(7.0)   # t=0 时立绘还没出场，这里挑一个有立绘有台词的时刻
app.processEvents()
print('   信息栏:', win.preview_info.text())
assert '立绘' in win.preview_info.text() or '句' in win.preview_info.text()
assert '占位' not in win.preview_info.text()

print('\n=== 2. 播放头一动，预览就跟着变 ===')
frames = []
for t in (0.0, 1.2, 7.0, 12.6, 16.2):
    win.timeline.set_playhead(t)
    app.processEvents()
    pm = win.preview_label.pixmap()
    frames.append((t, pm.width(), pm.height(), win.preview_info.text()))
for t, w, h, info in frames:
    print('   t=%5.1f  %dx%d  %s' % (t, w, h, info))
assert len(set(f[3] for f in frames)) >= 4, '预览没跟着播放头变'
# 显示尺寸必须是 240×160 的**整数倍**（最近邻缩放，非整数倍会让像素大小不一）
for t, w, h, _ in frames:
    assert w % 240 == 0 and h % 160 == 0 and w > 0, \
        't=%.1f 的显示尺寸 %dx%d 不是 240x160 的整数倍' % (t, w, h)
    assert w // 240 == h // 160, '横纵缩放倍数不一致'
print('   显示尺寸都是 240x160 的整数倍 ✓（当前 %d×）' % (frames[0][1] // 240))

print('\n=== 2b. 缩放档位：固定倍数 + 适应窗口 ===')
import ui.settings as S
for label, val in S.ZOOM_CHOICES:
    i = win.zoom_combo.findData(val)
    assert i >= 0, '缩放下拉框里没有 %s' % label
    win.zoom_combo.setCurrentIndex(i)
    app.processEvents()
    pm = win.preview_label.pixmap()
    if val == 'fit':
        print('   %-8s → %dx%d（适应窗口拿到的整数倍）' % (label, pm.width(), pm.height()))
        assert pm.width() % 240 == 0
    else:
        print('   %-8s → %dx%d' % (label, pm.width(), pm.height()))
        assert pm.width() == 240 * val, '%s 应该是 %d 像素宽' % (label, 240 * val)
# 回到适应窗口，后面的测试按这个来
win.zoom_combo.setCurrentIndex(win.zoom_combo.findData('fit'))
app.processEvents()

print('\n=== 3. 播放：按时间推进，到末尾自动停 ===')
end = max(c.start + c.dur for c in scene.clips)
win.timeline.set_playhead(end - 1.5)   # 从接近末尾开始，1.5 秒就能播完
win.start_play()
print('   开始播放，按钮文字:', win.play_btn.text())
assert win._playing
t0 = time.time()
while win._playing and time.time() - t0 < 10:
    app.processEvents()
    time.sleep(0.02)
el = time.time() - t0
print('   播放结束，用时 %.1f 秒，播放头 %.1f，按钮文字: %s'
      % (el, win.timeline.playhead, win.play_btn.text()))
assert not win._playing, '没有自动停'
assert win.timeline.playhead >= end - 0.2, (win.timeline.playhead, end)
assert '▶' in win.play_btn.text()

print('\n=== 4. 改台词，预览立刻反映 ===')
win.timeline.set_playhead(13.0)
app.processEvents()
c = [x for x in scene.clips if x.track == 'text' and abs(x.start - 12.5) < 0.01][0]
old = c.props['text']
c.props['text'] = '（改过的台词，用来验证预览会实时刷新）'
win.refresh_preview()
app.processEvents()
print('   改成:', c.props['text'])
c.props['text'] = old
win.refresh_preview()

print('\n=== 5. 立绘缺失时给明确提示（不是静默空白） ===')
scene.tracks.append(__import__('core.project', fromlist=['Track']).Track('char_9', 'char1', '立绘X'))
from core.project import Clip
scene.clips.append(Clip('char_9', 0, 3, '', '不存在的角色', {'pose': 'normal', 'pos': 'left'}))
win.timeline.set_playhead(1.0)
app.processEvents()
print('   信息栏:', win.preview_info.text())
assert '角色表里没有' in win.preview_info.text() or '⚠' in win.preview_info.text()

print('\n✅ P3 验收通过')

def test_empty_scene_draws_no_dialogue_box():
    """空场景**不该画台词框** —— 和引擎保持一致

    引擎（vn.c）只在执行 bg / 立绘 / 台词命令时才 draw_box()，
    连 vn_begin() 都不画 ✗ 所以一个片段都没有的空场景（刚新建的工程就是这样）
    实机上是**一片黑、没有框** ✓

    踩过：预览原来是无条件画框，于是空工程里出现一个
    "没有文字也没有▼的空蓝框"，看起来像坏了 ✗
    （用户报的"默认的光标位置对话框有问题"就是这个）
    """
    import os as _os
    import sys as _sys
    ROOT2 = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _sys.path.insert(0, _os.path.join(ROOT2, 'gbastudio'))
    _os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from core.project import blank_project, demo_project
    from core.preview import (PreviewRenderer, BOX_X, BOX_Y, BOX_W, BOX_H,
                              CLR_BOX_FILL)

    def box_pixels(img):
        n = 0
        for y in range(BOX_Y + 2, BOX_Y + BOX_H - 2, 4):
            for x in range(BOX_X + 2, BOX_X + BOX_W - 2, 4):
                px = img.getpixel((x, y))
                if all(abs(px[i] - CLR_BOX_FILL[i]) < 6 for i in range(3)):
                    n += 1
        return n

    b = blank_project('空')
    r = PreviewRenderer(b, _os.path.join(ROOT2, '.tmp'))
    assert box_pixels(r.render(b.scenes[0], 1.0)) == 0, \
        '空场景不该画台词框（引擎也不画）'

    # 有内容的场景必须有框（不然就矫枉过正了）
    d = demo_project('示例')
    r2 = PreviewRenderer(d, _os.path.dirname(SAMPLE))
    assert box_pixels(r2.render(d.scenes[0], 1.0)) > 0, \
        '有内容的场景应该画台词框'


# 这个文件是脚本式的（上面直接跑），所以函数光定义不会执行 —— 这里显式调用
test_empty_scene_draws_no_dialogue_box()
print('✅ 空场景不画台词框（和引擎一致），有内容的场景照常画')
