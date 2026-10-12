#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拖放与图层选择器测试

【守住什么】
用户提的两条交互要求：
    ① 图层选择挪到**预览左上角**，很小 ✓
    ② **素材从资源库直接拖到轨道上** ✓

这两条都是"看得见但很容易被后续改动碰坏"的东西 ✗
（比如某次改动把 AcceptDrops 关了 ✓ 界面照常 ✓ 只是拖不进去了 ✓ 没人会发现）
所以在这里钉死 ✓
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, HERE)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['GBASTUDIO_SETTINGS_DIR'] = os.path.join(ROOT, '.tmp', 'appdata')
os.environ['GBASTUDIO_SETTINGS'] = os.path.join(ROOT, '.tmp', 'test-dnd.ini')

from PySide6.QtWidgets import QApplication, QMessageBox      # noqa: E402

_app = QApplication.instance() or QApplication([])

from _sample import SAMPLE                                    # noqa: E402
from core.project import Project                              # noqa: E402


def _win():
    from ui.mainwindow import MainWindow
    p = Project.load(SAMPLE)
    w = MainWindow(p, proj_ctx={'gba_project': ROOT})
    w.resize(1440, 900)
    w.show()
    for _ in range(6):
        _app.processEvents()
    w.dirty = False
    return w, p


# ------------------------------------------------------------ ① 图层选择器
def test_layer_picker_on_preview():
    """图层选择器：在预览左上角、很小、列的是当前场景的图层"""
    w, p = _win()
    lp = w.layer_picker
    assert lp is not None, '没有图层选择器'
    # 它是**预览容器的子控件**（浮层），不是某个 dock
    assert lp.parent() is w.preview_holder, '图层选择器应该是预览里的浮层'
    assert lp.x() <= 12 and lp.y() <= 12, '应该贴在左上角，实际 (%d,%d)' % (lp.x(), lp.y())
    assert lp.width() < 260 and lp.height() < 40, \
        '要"很小"，实际 %dx%d' % (lp.width(), lp.height())
    s = w.modes[0].current_scene()
    # 横排按钮：一层一个，文字就是硬件层名（BG0 / BG1 / … / OBJ）
    assert len(lp._buttons) == len(s.layers), \
        '按钮数应该等于图层数（%d vs %d）' % (len(lp._buttons), len(s.layers))
    names = [b.text() for _L, b in lp._buttons]
    assert names == [L.name for L in s.layers], \
        '按钮文字该是图层名：%s vs %s' % (names, [L.name for L in s.layers])
    # 从左到右 = 从底到顶（1 = 最底层，和 BG0 一致）
    assert names[0].startswith('BG'), '最左边该是最底层：%s' % names
    first = lp.current_layer()
    assert first is not None and first.id == s.layers[0].id, '默认选中第一层'
    assert lp.width() < 400, '要"很小"，实际宽 %d' % lp.width()
    print('     浮在预览 (%d,%d)，%dx%d，横排 %s，默认选 %s ✓'
          % (lp.x(), lp.y(), lp.width(), lp.height(), names, first.name))


def test_layer_picker_eye_toggles():
    """眼睛开关：切一下图层可见性，预览跟着变"""
    w, p = _win()
    lp = w.layer_picker
    L = lp.current_layer()
    v0 = L.visible
    lp._on_eye()
    assert L.visible != v0, '眼睛没起作用'
    lp._on_eye()
    assert L.visible == v0, '再点一次该切回来'
    print('     眼睛切换图层可见性 ✓')


def test_layer_picker_hidden_in_level_workspace():
    """关卡工作区不需要图层选择器（那里没有时间轴图层）"""
    w, p = _win()
    w.switch_mode(1)
    for _ in range(4):
        _app.processEvents()
    assert not w.layer_picker.isVisible(), '关卡工作区不该显示图层选择器'
    # 而中央左侧那一格该出现地图
    assert w.side_holder.isVisible() and w.side_widget is not None, \
        '关卡工作区应该在中央左侧放地图小组件'
    w.switch_mode(0)
    for _ in range(4):
        _app.processEvents()
    assert not w.side_holder.isVisible(), '剧情工作区左槽该收起（让预览占满）'
    print('     关卡→左槽出现地图；剧情→左槽收起、选择器出现在预览上 ✓')


# ------------------------------------------------------------ ② 拖放
def test_drop_creates_clip():
    """把背景拖到背景轨上 → 生成一个片段，落在拖的那个时刻"""
    w, p = _win()
    st = w.modes[0]
    s = st.current_scene()
    bg = p.assets_of('bg')[0]
    n0 = len(s.clips)
    st._on_asset_dropped('bg', 1.5, bg.path)
    got = [c for c in s.clips if c.track == 'bg' and abs(c.start - 1.5) < 0.01]
    assert len(s.clips) == n0 + 1, '应该多出一个片段'
    assert got, '没落在 1.5 秒处'
    assert got[0].ref == bg.path, 'ref 应该是素材路径，实际 %r' % got[0].ref
    assert got[0].dur >= 0.4, '时长不对'
    print('     背景落在背景轨 %.2f 秒，时长 %.1f ✓' % (got[0].start, got[0].dur))


def test_drop_audio_uses_asset_duration():
    """音频拖上去，时长应该用素材自己的时长（不是拍脑袋的默认值）"""
    w, p = _win()
    st = w.modes[0]
    s = st.current_scene()
    au = (p.assets_of('voice') or p.assets_of('bgm') or p.assets_of('se'))
    au = [a for a in au if a.dur]
    if not au:
        print('     （示例里没有带时长的音频，跳过）')
        return
    a = au[0]
    tk = s.first_track(a.kind) or s.add_track(a.kind)
    st._on_asset_dropped(tk.id, 2.0, a.path)
    got = [c for c in s.clips if c.track == tk.id and abs(c.start - 2.0) < 0.01]
    assert got, '没生成片段'
    assert abs(got[0].dur - a.dur) < 0.05, \
        '时长该跟素材一致（素材 %.2f，片段 %.2f）' % (a.dur, got[0].dur)
    print('     %s 拖上去时长 %.2f 秒，和素材一致 ✓' % (a.kind, got[0].dur))


def test_drop_char_uses_character_id():
    """立绘拖上去：ref 存的是**角色 id**，不是文件路径"""
    w, p = _win()
    st = w.modes[0]
    s = st.current_scene()
    chars = [a for a in p.assets if a.kind == 'char']
    if not chars:
        print('     （示例里没有立绘素材，跳过）')
        return
    a = chars[0]
    tk = s.first_track('char1') or s.add_track('char1')
    st._on_asset_dropped(tk.id, 3.0, a.path)
    got = [c for c in s.clips if c.track == tk.id and abs(c.start - 3.0) < 0.01]
    assert got, '没生成片段'
    ids = [c.id for c in p.characters]
    assert got[0].ref in ids, \
        'ref 必须是角色 id（%s），实际 %r —— 写成路径的话实机会找不到立绘' % (ids, got[0].ref)
    assert got[0].props.get('pose'), '应该有表情'
    print('     立绘 ref = %s（角色 id），表情 %s ✓'
          % (got[0].ref, got[0].props.get('pose')))


def test_drop_wrong_track_warns():
    """类型不对就明确提示，而不是默默吞掉"""
    w, p = _win()
    pops = []
    orig = QMessageBox.information
    QMessageBox.information = staticmethod(
        lambda *a, **k: pops.append(a[2] if len(a) > 2 else '?'))
    try:
        st = w.modes[0]
        s = st.current_scene()
        bg = p.assets_of('bg')[0]
        v = s.first_track('voice')
        n0 = len(s.clips)
        st._on_asset_dropped(v.id, 2.0, bg.path)
        assert len(s.clips) == n0, '放错轨道不该生成片段'
        assert pops, '应该弹提示告诉用户该放哪条轨道'
    finally:
        QMessageBox.information = orig
    print('     背景拖到语音轨 → 提示「%s」且不生成片段 ✓' % pops[0][:24])


def test_timeline_accepts_drops():
    """时间轴本身要开着拖放接收（关掉就"拖了没反应"）"""
    w, p = _win()
    tv = w.timeline
    assert tv.acceptDrops(), '时间轴没开 AcceptDrops —— 拖进去会毫无反应'
    assert hasattr(tv, 'assetDropped'), '时间轴缺 assetDropped 信号'
    # 素材树要能拖出去
    at = w.asset_tree
    assert at.dragEnabled(), '资源库没开拖出（dragEnabled）'
    assert hasattr(at, 'ASSET_MIME') and at.ASSET_MIME == tv.ASSET_MIME, \
        '两边的 MIME 类型不一致，拖过去认不出来'
    print('     时间轴收拖 ✓ 资源库能拖出 ✓ 两边 MIME 一致（%s）✓' % at.ASSET_MIME)


def main():
    tests = [
        ('选择器在预览左上角', test_layer_picker_on_preview),
        ('眼睛切可见性', test_layer_picker_eye_toggles),
        ('按工作区显隐', test_layer_picker_hidden_in_level_workspace),
        ('拖放生成片段', test_drop_creates_clip),
        ('音频时长跟素材', test_drop_audio_uses_asset_duration),
        ('立绘用角色 id', test_drop_char_uses_character_id),
        ('放错轨道有提示', test_drop_wrong_track_warns),
        ('拖放通道开着', test_timeline_accepts_drops),
    ]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print('    %-18s 通过' % name)
        except AssertionError as e:
            print('    %-18s 失败：%s' % (name, e))
            bad += 1
        except Exception as e:                              # noqa: BLE001
            import traceback
            print('    %-18s 出错：%s: %s' % (name, type(e).__name__, e))
            traceback.print_exc()
            bad += 1
    print()
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 拖放与图层选择器：拖得进去、落得对、类型不匹配会提示')
    return 0


if __name__ == '__main__':
    sys.exit(main())
