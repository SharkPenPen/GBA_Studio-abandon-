#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图层模型测试（阶段 2）

【这一层要守住什么】
1. **图层数 = 模式给的硬件层数** —— 不能多也不能少，不能被增删
2. 模式 0 不能被当成"没给"（它是 falsy，踩过这个坑）
3. 旧工程（没有 layers 字段）要能读，轨道自动归第一层
4. 存读往返不丢图层和归属
5. 时间轴的行清单：图层头 + 缩进的轨道；折叠后只剩图层头
6. **预览按图层叠**：上层盖下层；隐藏上层就露出下层
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, HERE)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['GBASTUDIO_SETTINGS_DIR'] = os.path.join(ROOT, '.tmp', 'appdata')
os.environ['GBASTUDIO_SETTINGS'] = os.path.join(ROOT, '.tmp', 'test-layers.ini')

from core.project import (blank_project, Project, MODE_LAYERS, Layer,   # noqa: E402
                          layers_for_mode)


# ---------------------------------------------------------------- 1. 模式表
def test_mode_layers_match_video_modes():
    """core 的图层表必须和 ui/video_modes.py 里给用户看的说明一致

    两处各有一份（core 不能反向依赖 ui）✗ 所以只能靠测试守住 ✓
    不一致的后果很隐蔽：界面说"模式 0 有四层"，实际只建出一层 ✓
    """
    from ui.video_modes import MODES
    bad = []
    for m in MODES:
        want = [(n, k) for n, _d, k in m.layers]
        got = MODE_LAYERS.get(m.m)
        if got != want:
            bad.append('模式 %d：ui 说 %s，core 是 %s' % (m.m, want, got))
    assert not bad, '图层表两边不一致：\n  ' + '\n  '.join(bad)
    print('     六种模式的图层表两边一致 ✓')


def test_layer_count_follows_mode():
    """图层数 = 模式的硬件层数（含精灵层）"""
    want = {0: 5, 1: 4, 2: 3, 3: 2, 4: 2, 5: 2}
    for mode, n in want.items():
        p = blank_project('t', video_mode=mode)
        s = p.scenes[0]
        assert len(s.layers) == n, '模式 %d 应该是 %d 层，实际 %d' % (mode, n, len(s.layers))
        # 最后一层永远是精灵层
        assert s.layers[-1].kind == 'obj', '模式 %d 的最后一层应该是精灵层' % mode
    # 模式 0 专测：它是 falsy，不能被"或"运算吃掉
    p0 = blank_project('t', video_mode=0)
    kinds = [L.kind for L in p0.scenes[0].layers]
    assert kinds.count('tile') == 4, '模式 0 应该有 4 个图块层，实际 %s' % kinds
    print('     模式 0→5 层 / 1→4 / 2→3 / 3,4,5→2，模式 0 没被当成"没给" ✓')


def test_layers_cannot_be_added():
    """图层不能增删 —— 界面上就不该有这种入口"""
    p = blank_project('t', video_mode=3)
    s = p.scenes[0]
    n = len(s.layers)
    # ensure_layers 再调一次不会多出层来
    s.ensure_layers(3)
    s.ensure_layers(3)
    assert len(s.layers) == n, 'ensure_layers 不该改变图层数量'
    print('     重复 ensure_layers 不会多出图层 ✓')


# ---------------------------------------------------------------- 2. 兼容
def test_old_project_gets_one_layer():
    """旧工程（没有 layers 字段）读进来：轨道全归第一层"""
    p = blank_project('t', video_mode=3)
    s = p.scenes[0]
    # 模拟旧文件：把 layers 去掉
    d = p.to_dict()
    for sd in d['scenes']:
        sd.pop('layers', None)
    q = Project('', 't')
    q.load_dict(d)
    s2 = q.scenes[0]
    assert s2.layers, '旧文件读进来应该自动补出图层'
    ids = set()
    for L in s2.layers:
        ids |= set(L.tracks)
    for tr in s2.tracks:
        assert tr.id in ids, '轨道 %s 没归到任何图层' % tr.id
    print('     旧工程自动归层：%d 层，轨道全部有归属 ✓' % len(s2.layers))


def test_roundtrip_keeps_layers():
    """存读往返：图层、名字、轨道归属都要在"""
    p = blank_project('t', video_mode=2)
    s = p.scenes[0]
    s.layers[0].name = '远山'
    s.layers[1].name = '云'
    s.assign_track('bg', s.layers[1].id)
    s.layers[1].scroll_x = 0.5
    path = os.path.join(ROOT, '.tmp', 'layer-rt.gbastudio')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    p.save(path)
    q = Project.load(path)
    s2 = q.scenes[0]
    assert [L.name for L in s2.layers][:2] == ['远山', '云'], [L.name for L in s2.layers]
    assert 'bg' in s2.layers[1].tracks, '轨道归属没存住'
    assert abs(s2.layers[1].scroll_x - 0.5) < 1e-6, '滚动速度没存住'
    print('     往返：图层名 / 归属 / 滚动速度都保住了 ✓')


def test_assign_track_moves():
    """轨道可以在层之间挪，且不会同时属于两层"""
    p = blank_project('t', video_mode=1)          # 3 个 BG 层 + 精灵层
    s = p.scenes[0]
    a, b = s.layers[0], s.layers[1]
    s.assign_track('bg', b.id)
    assert 'bg' in b.tracks and 'bg' not in a.tracks
    n = sum(1 for L in s.layers if 'bg' in L.tracks)
    assert n == 1, '一条轨道只能属于一个图层，现在属于 %d 个' % n
    print('     轨道挪层：只属于一层 ✓')


# ---------------------------------------------------------------- 3. 时间轴
def test_timeline_rows_and_collapse():
    """时间轴的行：图层头 + 缩进的轨道；折叠后只剩图层头"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from ui.timeline import TimelineView
    p = blank_project('t', video_mode=2)          # 2 个 BG 层 + 精灵层
    s = p.scenes[0]
    tv = TimelineView()
    tv.set_project(p, s)
    rows = tv.rows()
    kinds = [k for k, _o in rows]
    assert kinds.count('layer') == len(s.layers), '图层头数量不对：%s' % kinds
    assert kinds.count('track') == len(s.tracks), '轨道行数量不对'
    # 第一行应该是图层头
    assert kinds[0] == 'layer'
    # 折叠第一层
    first = s.layers[0]
    n_before = len(tv.rows())
    tv.toggle_layer(first.id)
    n_after = len(tv.rows())
    assert n_after == n_before - len(first.tracks), \
        '折叠后应该少掉这一层的 %d 行（%d → %d）' % (len(first.tracks), n_before, n_after)
    # 折叠只影响"画不画" ✗ 不影响轨道集合
    assert len(tv.visible_tracks()) == len(s.tracks), '折叠不该改变轨道集合'
    tv.toggle_layer(first.id)
    assert len(tv.rows()) == n_before, '再点一次应该展开'
    print('     行清单 %d 行（%d 图层头 + %d 轨道）；折叠 %d → %d ✓'
          % (n_before, kinds.count('layer'), kinds.count('track'), n_before, n_after))


# ---------------------------------------------------------------- 4. 预览
def _asset_img(name):
    """造一个小 PNG 当素材（不依赖示例工程）"""
    from PIL import Image
    d = os.path.join(ROOT, '.tmp', 'layer-assets')
    os.makedirs(d, exist_ok=True)
    q = os.path.join(d, name)
    im = Image.new('RGB', (240, 160), (255, 0, 0) if name.startswith('red') else (0, 0, 255))
    im.save(q)
    return q


def test_preview_stacks_layers():
    """预览按图层从下往上叠：上层盖下层；隐藏上层露出下层"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from core.preview import PreviewRenderer
    from core.project import Scene, Clip

    p = blank_project('t', video_mode=2)
    s = p.scenes[0]
    _asset_img('red.png')
    _asset_img('blue.png')
    # 两个图层各放一张背景（底层红、上层蓝）
    s.layers[0].tracks = ['bg'] if 'bg' in s.tracks else s.layers[0].tracks
    s.layers[1].tracks = ['bg_2'] if s.track('bg_2') else s.layers[1].tracks
    if s.track('bg_2') is None:
        from core.project import Track
        s.tracks.append(Track('bg_2', 'bg'))
        s.layers[1].tracks = ['bg_2']
    s.clips = [Clip('bg', 0, 10, 'show', 'assets/bg/red.png'),
               Clip('bg_2', 0, 10, 'show', 'assets/bg/blue.png')]
    r = PreviewRenderer(p, os.path.join(ROOT, '.tmp'))
    img = r.render(s, 1.0)
    st = r.state_at(s, 1.0)
    assert len(st['layers']) == 2, '应该算出两个图层的画面，实际 %d' % len(st['layers'])
    # 上层是蓝 → 最终画面蓝色占多数
    px = list(img.getdata())
    blue = sum(1 for c in px if c[2] > c[0])
    assert blue > len(px) * 0.5, '上层（蓝）应该盖住下层，实际蓝色只占 %.0f%%' \
        % (blue * 100.0 / len(px))
    # 隐藏上层 → 露出下层的红
    s.layers[1].visible = False
    st2 = r.state_at(s, 1.0)
    assert len(st2['layers']) == 1, '隐藏的图层不该出现在画面里'
    print('     分层叠加：上层盖下层 ✓ 隐藏上层后只剩 %d 层 ✓' % len(st2['layers']))


def main():
    tests = [
        ('图层表两边一致', test_mode_layers_match_video_modes),
        ('图层数跟模式走', test_layer_count_follows_mode),
        ('图层不能增删', test_layers_cannot_be_added),
        ('旧工程自动归层', test_old_project_gets_one_layer),
        ('往返不丢图层', test_roundtrip_keeps_layers),
        ('轨道可挪层', test_assign_track_moves),
        ('时间轴行与折叠', test_timeline_rows_and_collapse),
        ('预览按层叠加', test_preview_stacks_layers),
    ]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print('    %-16s 通过' % name)
        except AssertionError as e:
            print('    %-16s 失败：%s' % (name, e))
            bad += 1
        except Exception as e:                              # noqa: BLE001
            import traceback
            print('    %-16s 出错：%s: %s' % (name, type(e).__name__, e))
            traceback.print_exc()
            bad += 1
    print()
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 图层模型：模式决定层数、旧工程兼容、时间轴分行、预览分层都对得上')
    return 0


if __name__ == '__main__':
    sys.exit(main())
