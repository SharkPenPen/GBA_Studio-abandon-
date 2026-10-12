# -*- coding: utf-8 -*-
"""
project.py —— 项目数据模型（**通用设计，按需实现**）

这是整个工具里唯一"不能省"的东西：数据模型必须一开始就按通用设计，
否则将来加关卡模式/精灵模式时要推倒重来，已做的作品也会丢。

所以这里的结构是"多类型游戏"通用的一套：
    项目 Project
      ├─ 设置 settings（字号档位、屏幕尺寸、ROM 名…）
      ├─ 资源库 assets（图片/音乐/语音/音效，带 GBA 合规信息）
      ├─ 角色表 characters（显示名、颜色、立绘组、语音前缀）
      └─ 场景 scenes[]
            ├─ kind = story → 时间轴模式（轨道 + 片段）
            └─ kind = level → 关卡模式（图块层 + 实体对象）  ← 将来加
              └─ 对象 objects[]（背景/立绘/实体/图块层…）

当前（P1）只实现 story 场景用到的那部分，但字段和层次已经按通用留好。
"""
import json
import os
import time

from core.level import Level
from core.anim import Animation, default_animations

# ---------------------------------------------------------------------------
# 唯一 id
#
# **踩过的大坑**：原来用 `'c%d' % int(time.time()*1000000 % 1e8)` 生成 id，
# 而 Windows 上 time.time() 的精度只有约 **15.6 毫秒** —— 快速循环里创建的
# 十几个片段全都拿到同一个 id。后果是所有"按 id 找片段"的功能全错：
# 台词和语音的关联找错对象、按 id 删片段会一次删掉一串。
# 现在用"时间戳 + 递增序号"，同一毫秒内也不会重复。
# ---------------------------------------------------------------------------
_seq = [0]


def new_id(prefix='x'):
    _seq[0] += 1
    return '%s%d_%d' % (prefix, int(time.time() * 1000) % 100000000, _seq[0])

# 工程文件的格式标记。加载时会核对，写错了会明确报错而不是"读出个空工程"。
FORMAT = 'gbastudio'
VERSION = 1

# 片段最短长度（秒）——时间轴拖边缘和属性都按这个下限
MIN_DUR = 0.1

# ---------------------------------------------------------------------------
# 轨道类型（时间轴用）：决定片段长什么样、属性里能填什么
# ---------------------------------------------------------------------------
TRACK_TYPES = {
    'fx':    {'title': '特效', 'color': '#b07cd6', 'multi': False},
    'char3': {'title': '立绘C', 'color': '#d67ca8', 'multi': False},
    'char2': {'title': '立绘B', 'color': '#d67ca8', 'multi': False},
    'char1': {'title': '立绘A', 'color': '#d67ca8', 'multi': False},
    'bg':    {'title': '背景', 'color': '#4a90d9', 'multi': False},
    'text':  {'title': '台词', 'color': '#5c6b8a', 'multi': False},
    'voice': {'title': '语音', 'color': '#3f9d6d', 'multi': False},
    'bgm':   {'title': 'BGM',  'color': '#c9a227', 'multi': False},
    'se':    {'title': '音效', 'color': '#c96b27', 'multi': True},
}

# 字号档位：标称尺寸 → 实际字形尺寸（字形比标称小 1 像素，这是和美术对齐后的约定）
FONT_SIZES = {
    8:  {'cjk': None, 'ascii': 7},    # 中文做不到，只出英文/数字（见 docs/11）
    12: {'cjk': 11,   'ascii': 6},    # 主用档（已验证）
    16: {'cjk': 15,   'ascii': 8},    # 标题/大字号（已验证）
}


# 一条轨道 = 一个 id + 一种类型。同一个类型可以有多条（bg / bg_2，se / se_2 …），
# 这样两条背景能各占一条轨道做淡入淡出，音效也能分层。
class Track:
    def __init__(self, tid, kind, name='', visible=True, muted=False):
        self.id = tid
        self.kind = kind            # 对应 TRACK_TYPES 的键
        self.name = name or TRACK_TYPES.get(kind, {}).get('title', kind)
        self.visible = visible
        self.muted = muted

    def to_dict(self):
        return {'id': self.id, 'kind': self.kind, 'name': self.name,
                'visible': self.visible, 'muted': self.muted}

    @staticmethod
    def from_dict(d):
        return Track(d['id'], d['kind'], d.get('name', ''),
                     d.get('visible', True), d.get('muted', False))


# 新场景默认带哪些轨道（顺序 = 时间轴上从下到上）
DEFAULT_TRACKS = [('se', 'se'), ('bgm', 'bgm'), ('voice', 'voice'),
                  ('text', 'text'), ('bg', 'bg'), ('char_1', 'char1')]


def _kind_of(track_id):
    """从轨道 id 反推类型：'bg_2' → 'bg'，'char_1' → 'char1'"""
    if track_id in TRACK_TYPES:
        return track_id
    if track_id.startswith('char'):
        return 'char1'
    return track_id.rsplit('_', 1)[0]


# ===========================================================================
# 图层（Layer）
#
# 【为什么要有它】
# 以前是"场景 → 轨道"两级 ✗ 轨道直接决定画面 ✓
# 但 GBA 的显示模式**本来就给了几个硬件层**（模式 0 有 4 个 BG ✓ 模式 3 只有 1 个 ✓）
# 而开发者真正想表达的是"这几样东西各自独立动"✓（背景做视差、云飘、地面不动 ✓）
#
# 所以加一级：**场景 → 图层 → 轨道 → 片段**
#     图层 = 一个硬件层 ✓ **数量由显示模式决定，不能增删** ✓
#     轨道 = 挂在图层上的东西 ✓ **想加多少加多少** ✓
#     同一图层里的多条轨道 → **打包时重叠成一张画面** ✓ 上下顺序 = 重叠顺序
#
# 【怎么做到不改动现有代码】
# `Scene.tracks` **保持扁平不动** ✓ 所有老代码（时间轴/编译器/预览）照常用它 ✓
# `Scene.layers` 只额外记"哪些轨道 id 属于哪一层" ✓
# ——加一层关系，不动原有结构 ✓
# ===========================================================================

# 每种显示模式的硬件图层（名字, 类型）
# 类型：tile 图块 / affine 仿射 / bitmap 位图 / obj 硬件精灵
# ⚠ 这份表必须和 ui/video_modes.py 里每种模式的 layers 一致
#   （那边还有给用户看的说明文字 ✓ 这里只要名字和类型 ✓）
#   两边不一致会被 tests/test_layers.py 抓到 ✓
MODE_LAYERS = {
    0: [('BG0', 'tile'), ('BG1', 'tile'), ('BG2', 'tile'), ('BG3', 'tile'),
        ('OBJ', 'obj')],
    1: [('BG0', 'tile'), ('BG1', 'tile'), ('BG2', 'affine'), ('OBJ', 'obj')],
    2: [('BG2', 'affine'), ('BG3', 'affine'), ('OBJ', 'obj')],
    3: [('BG2', 'bitmap'), ('OBJ', 'obj')],
    4: [('BG2', 'bitmap'), ('OBJ', 'obj')],
    5: [('BG2', 'bitmap'), ('OBJ', 'obj')],
}

LAYER_KIND_TITLE = {'tile': '图块层', 'affine': '仿射层',
                    'bitmap': '位图层', 'obj': '精灵层'}


class Layer:
    """一个硬件层：里面挂着若干条轨道

    ⚠ 图层**不能增删** ✗ 数量由工程的显示模式决定 ✓（这是硬件事实）
       能改的只有：名字（用途名，比如"远山""云"）、可见性、滚动速度
    """

    def __init__(self, lid, name='', kind='tile', tracks=None, visible=True,
                 scroll_x=0.0, scroll_y=0.0, note=''):
        self.id = lid
        self.name = name or lid
        self.kind = kind            # tile / affine / bitmap / obj
        self.tracks = list(tracks or [])   # 轨道 id，**顺序 = 从下往上的重叠顺序**
        self.visible = visible
        self.scroll_x = float(scroll_x)    # 视差速度（阶段 6 引擎支持后用）
        self.scroll_y = float(scroll_y)
        self.note = note            # 给用户看的说明

    @property
    def kind_title(self):
        return LAYER_KIND_TITLE.get(self.kind, self.kind)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'kind': self.kind,
                'tracks': list(self.tracks), 'visible': self.visible,
                'scroll_x': self.scroll_x, 'scroll_y': self.scroll_y,
                'note': self.note}

    @staticmethod
    def from_dict(d):
        return Layer(d['id'], d.get('name', ''), d.get('kind', 'tile'),
                     d.get('tracks'), d.get('visible', True),
                     d.get('scroll_x', 0.0), d.get('scroll_y', 0.0),
                     d.get('note', ''))


def layers_for_mode(video_mode):
    """按显示模式造一套图层（数量、名字、类型都跟着模式走）"""
    # ⚠ 不能写 `video_mode or 3` ✗
    # 模式 **0** 是 falsy ✓ 会被当成"没给" → 掉进默认值 3 ✓
    # 于是模式 0 的工程建出来是模式 3 的图层表（4 个图块层变成 1 个位图层）✗
    # ——`or` 当默认值用，遇上合法的 0 就会静默出错 ✓
    try:
        m = int(video_mode)
    except (TypeError, ValueError):
        m = 3
    if m not in MODE_LAYERS:
        m = 3
    spec = MODE_LAYERS[m]
    out = []
    for i, (name, kind) in enumerate(spec):
        out.append(Layer('L%d' % (i + 1), name, kind,
                         note=LAYER_KIND_TITLE.get(kind, kind)))
    return out


class Clip:
    """时间轴上的一个片段"""
    def __init__(self, track, start, dur, kind='', ref='', props=None, cid=None):
        self.id = cid or new_id('c')
        self.track = track          # 轨道 id（对应 Scene.tracks 里的某项）
        self.start = float(start)
        self.dur = float(dur)
        self.kind = kind
        self.ref = ref
        self.props = dict(props or {})

    def to_dict(self):
        return {'id': self.id, 'track': self.track, 'start': self.start, 'dur': self.dur,
                'kind': self.kind, 'ref': self.ref, 'props': self.props}

    @staticmethod
    def from_dict(d):
        return Clip(d['track'], d['start'], d['dur'], d.get('kind', ''),
                    d.get('ref', ''), d.get('props'), d.get('id'))


class GObject:
    """场景里的一个对象（关卡模式/剧情模式共用）"""
    def __init__(self, otype, name='', layer=0, x=0, y=0, props=None, oid=None):
        self.id = oid or new_id('o')
        self.type = otype           # bg / char / tilemap / entity / textbox
        self.name = name
        self.layer = layer
        self.x, self.y = int(x), int(y)
        self.props = dict(props or {})

    def to_dict(self):
        return {'id': self.id, 'type': self.type, 'name': self.name, 'layer': self.layer,
                'x': self.x, 'y': self.y, 'props': self.props}

    @staticmethod
    def from_dict(d):
        return GObject(d['type'], d.get('name', ''), d.get('layer', 0),
                       d.get('x', 0), d.get('y', 0), d.get('props'), d.get('id'))


class Scene:
    def __init__(self, name, kind='story', sid=None):
        self.id = sid or new_id('s')
        self.name = name
        self.kind = kind            # story（时间轴）/ level（图块关卡）/ title / menu
        self.tracks = [Track(tid, k) for tid, k in DEFAULT_TRACKS]
        self.objects = []           # [GObject]（关卡模式用；story 模式的画面由轨道决定）
        self.clips = []             # [Clip]（story 模式用）
        # 图层：数量由显示模式决定 ✓ 装的是"哪些轨道属于我" ✓
        # 空列表表示"还没按模式建过" ✓ Project.load 会用工程模式补上 ✓
        self.layers = []
        self.duration = 30.0        # 场景长度（秒，仅 story）

    # ---------------------------------------------------------------- 轨道
    def track(self, tid):
        for t in self.tracks:
            if t.id == tid:
                return t
        return None

    def tracks_of(self, kind):
        return [t for t in self.tracks if t.kind == kind]

    def first_track(self, kind):
        ts = self.tracks_of(kind)
        return ts[0] if ts else None

    def add_track(self, kind):
        """加一条同类轨道：bg → bg_2 → bg_3 …，名字也带序号避免重名"""
        n = len(self.tracks_of(kind)) + 1
        base = {'char1': 'char'}.get(kind, kind)
        tid = base if n == 1 else '%s_%d' % (base, n)
        while self.track(tid):
            n += 1
            tid = '%s_%d' % (base, n)
        title = TRACK_TYPES.get(kind, {}).get('title', kind)
        if kind.startswith('char'):
            # 立绘按顺序叫 A / B / C，一眼看出是第几个位置
            name = '立绘' + chr(ord('A') + len(self.tracks_of(kind)))
        else:
            same = [t for t in self.tracks if t.name == title or t.name.startswith(title + ' ')]
            name = title if not same else '%s %d' % (title, len(same) + 1)
        t = Track(tid, kind, name)
        # 插在同类轨道的最后一条之后，保持"同类型挨着"
        idx = max([i for i, x in enumerate(self.tracks) if x.kind == kind] or [-1]) + 1
        self.tracks.insert(idx, t)
        return t

    def remove_track(self, tid):
        """删轨道，连同它上面的片段。至少要留一条轨道"""
        if len(self.tracks) <= 1:
            return False
        self.tracks = [t for t in self.tracks if t.id != tid]
        self.clips = [c for c in self.clips if c.track != tid]
        return True

    # ---------------------------------------------------------------- 图层
    def ensure_layers(self, video_mode):
        """按模式补齐图层 ✗ 并把还没归层的轨道塞进第一层

        为什么要"塞进第一层"：旧工程没有图层这一级 ✓
        建了图层之后，如果轨道没归属 ✓ 时间轴就画不出来 ✓
        所以默认全归第一层 ✓ 用户再自己往上层拖 ✓
        """
        if not self.layers:
            self.layers = layers_for_mode(video_mode)
        known = set()
        for L in self.layers:
            known |= set(L.tracks)
        for tr in self.tracks:
            if tr.id not in known:
                # 视觉轨放最上面的图块/位图层更自然，但第一版统一进第一层
                # ——可预测比"聪明"重要 ✓ 用户自己拖一下就好
                self.layers[0].tracks.append(tr.id)
        # 清掉指向已不存在的轨道的引用（删轨道之后可能留下）
        ids = {tr.id for tr in self.tracks}
        for L in self.layers:
            L.tracks = [x for x in L.tracks if x in ids]
        return self.layers

    def layer(self, lid):
        for L in self.layers:
            if L.id == lid:
                return L
        return None

    def layer_of(self, track_id):
        """这条轨道属于哪一层（没有就返回 None）"""
        for L in self.layers:
            if track_id in L.tracks:
                return L
        return None

    def assign_track(self, track_id, layer_id, index=None):
        """把轨道挪到某一层（index 指定它在层里的上下位置）"""
        for L in self.layers:
            if track_id in L.tracks:
                L.tracks.remove(track_id)
        tgt = self.layer(layer_id)
        if tgt is None:
            return False
        if index is None:
            tgt.tracks.append(track_id)
        else:
            tgt.tracks.insert(max(0, min(index, len(tgt.tracks))), track_id)
        return True

    def tracks_in_layer(self, lid):
        L = self.layer(lid)
        if L is None:
            return []
        # 按图层里记的顺序返回（顺序 = 从下往上的重叠顺序）
        return [t for t in (self.track(x) for x in L.tracks) if t is not None]

    def visual_layers(self):
        """会画东西的图层（排除精灵层和空层）—— 预览和打包按这个顺序画"""
        return [L for L in self.layers if L.visible and L.tracks
                and L.kind != 'obj']

    def track_clips(self, tid):
        return sorted([c for c in self.clips if c.track == tid], key=lambda c: c.start)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'kind': self.kind,
                'duration': self.duration,
                'tracks': [t.to_dict() for t in self.tracks],
                'layers': [L.to_dict() for L in self.layers],
                'objects': [o.to_dict() for o in self.objects],
                'clips': [c.to_dict() for c in self.clips]}

    @staticmethod
    def from_dict(d):
        s = Scene(d['name'], d.get('kind', 'story'), d.get('id'))
        s.duration = d.get('duration', 30.0)
        s.objects = [GObject.from_dict(o) for o in d.get('objects', [])]
        s.clips = [Clip.from_dict(c) for c in d.get('clips', [])]
        tracks = [Track.from_dict(t) for t in d.get('tracks', [])]
        if tracks:
            s.tracks = tracks
        else:
            # 旧文件没有 tracks 字段：按片段用到的轨道补出来（向前兼容）
            s.tracks = [Track(tid, k) for tid, k in DEFAULT_TRACKS]
            used = []
            for c in s.clips:
                if c.track not in [t.id for t in s.tracks] and c.track not in used:
                    used.append(c.track)
            for tid in used:
                s.tracks.append(Track(tid, _kind_of(tid)))
        # 图层：新文件直接读 ✓ 旧文件留空 ✓ 由 Project.load 按工程模式补 ✓
        s.layers = [Layer.from_dict(L) for L in d.get('layers', [])]
        return s


class Character:
    """角色表：解决"台词 / 配音 / 立绘"的自动对应（见 docs/07 第 6 节）"""
    def __init__(self, cid, name, color='#ffd166', voice_prefix='', poses=None):
        self.id = cid               # witch
        self.name = name            # 魔女
        self.color = color          # 名字高亮色
        self.voice_prefix = voice_prefix or (cid + '_')
        self.poses = list(poses or ['normal'])

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'color': self.color,
                'voice_prefix': self.voice_prefix, 'poses': self.poses}

    @staticmethod
    def from_dict(d):
        return Character(d['id'], d['name'], d.get('color', '#ffd166'),
                         d.get('voice_prefix', ''), d.get('poses'))


class Asset:
    def __init__(self, kind, path, note='', w=0, h=0, dur=0.0):
        self.kind = kind            # bg / char / bgm / voice / se / font
        self.path = path            # 相对项目目录
        self.note = note
        self.w, self.h = w, h       # 转换后的 GBA 尺寸
        self.dur = dur              # 音频时长（秒）

    def to_dict(self):
        return {'kind': self.kind, 'path': self.path, 'note': self.note,
                'w': self.w, 'h': self.h, 'dur': self.dur}

    @staticmethod
    def from_dict(d):
        return Asset(d['kind'], d['path'], d.get('note', ''), d.get('w', 0),
                     d.get('h', 0), d.get('dur', 0.0))


class Project:
    def __init__(self, path='', name='未命名'):
        self.path = path
        self.name = name
        self.assets = []
        self.characters = []
        self.scenes = []
        self.level = Level.default()      # P8：关卡模式的地图
        self.animations = default_animations()   # P9：精灵动画
        self.settings = {
            'font_size': 12,        # 默认字号档位（8/12/16）
            'rom_name': 'gba_ai',
            'proj_dir': '',         # GBA 工程目录（编译用）
            # **显示模式**（GBA 的 mode 0~5）：决定能用哪些图层和特效。
            # 这是架构级选择 —— 位图和图块层不能混用，建好之后改起来很麻烦，
            # 所以新建项目时就要选（见 ui/video_modes.py 的说明和示意图）。
            'video_mode': 3,
        }

    # ---------------------------------------------------------------- 便捷方法
    def scene(self, sid):
        for s in self.scenes:
            if s.id == sid:
                return s
        return None

    def character(self, cid):
        for c in self.characters:
            if c.id == cid:
                return c
        return None

    def assets_of(self, kind):
        return [a for a in self.assets if a.kind == kind]

    def find_asset(self, path):
        for a in self.assets:
            if a.path == path:
                return a
        return None

    # ---------------------------------------------------------------- 存取
    def to_dict(self):
        return {
            'format': FORMAT, 'version': VERSION, 'name': self.name,
            'settings': self.settings,
            'characters': [c.to_dict() for c in self.characters],
            'assets': [a.to_dict() for a in self.assets],
            'scenes': [s.to_dict() for s in self.scenes],
            'level': self.level.to_dict(),
            'animations': [a.to_dict() for a in self.animations],
        }

    def load_dict(self, d):
        self.name = d.get('name', '未命名')
        self.settings.update(d.get('settings', {}))
        self.characters = [Character.from_dict(c) for c in d.get('characters', [])]
        self.assets = [Asset.from_dict(a) for a in d.get('assets', [])]
        self.scenes = [Scene.from_dict(s) for s in d.get('scenes', [])]
        self.level = Level.from_dict(d.get('level'))
        self.animations = ([Animation.from_dict(a) for a in d['animations']]
                           if d.get('animations') else default_animations())
        # **按工程的显示模式补齐图层** ✗
        # 旧工程没有 layers 字段 ✓ 新工程有 ✓
        # 补的时候：数量/名字/类型全跟着模式走 ✓ 已有的轨道全归第一层 ✓
        # 放在 _repair_ids 之前：那一步会删掉失效的片段/关联，
        # 之后 ensure_layers 再清一遍悬空的轨道引用 ✓ 两边都不漏 ✓
        mode = int(self.settings.get('video_mode', 3))
        for s in self.scenes:
            if s.kind == 'story':
                s.ensure_layers(mode)

        # 修复重复 id（早期版本在 Windows 上生成的 id 会撞车）。
        # 不修的话"按 id 找片段"会找错对象：删一条删掉一串、
        # 台词和语音的关联对错人。顺手把关联字段也一起理顺。
        self._repair_ids()

    def _repair_ids(self):
        """
        修复重复的片段 id（早期版本在 Windows 上生成 id 会撞车）。

        顺便清理失效的关联：语音片段的 props['for'] 指向某条台词，
        如果那个 id 已经不存在（或被改掉了），就把关联断开 ——
        旧文件里 id 有歧义，没法猜出原本指向谁，断开比连错好。
        """
        fixed = 0
        for sc in self.scenes:
            seen = set()
            for c in sc.clips:
                if c.id in seen:
                    c.id = new_id('c')
                    fixed += 1
                seen.add(c.id)
            ids = {c.id for c in sc.clips}
            for c in sc.clips:
                if c.props.get('for') and c.props['for'] not in ids:
                    c.props.pop('for')
                    c.props.pop('sync_start', None)
        return fixed

    def save(self, path=None):
        path = path or self.path
        if not path:
            raise ValueError('没有指定保存路径')
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def load(path):
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        # 核对格式标记：拿错文件（比如普通 JSON）要明确报错，
        # 而不是"读进来一个空工程"让人对着空白界面发愣
        if d.get('format') != FORMAT:
            raise ValueError('不是 GBAStudio 工程（format=%r，应该是 %r）\n%s'
                             % (d.get('format'), FORMAT, path))
        p = Project(path, d.get('name', '未命名'))
        p.load_dict(d)
        return p


# ---------------------------------------------------------------------------
# 新建工程
#
# 分成两个函数，因为用途完全不同：
#   blank_project()  **空的**，界面干净 —— 启动时和"新建工程 → 空白"用它
#   demo_project()   带一段示例剧情 —— 只在"新建工程 → 示例剧情"时用
#
# 以前只有一个 new_project()（自带示例素材和剧情），结果一打开编辑器
# 就满屏"假素材"（那些路径在磁盘上并不存在），既乱又让人以为工程里有东西。
# ---------------------------------------------------------------------------
def _apply_layers(p):
    """新建工程之后，按模式把每个 story 场景的图层建好

    ⚠ 单独一个函数，是因为 blank_project / demo_project 都是
      "先造场景，再设 settings" ✓ 顺序反着来 ✓
      所以图层只能在设完 settings 之后补 ✓
    """
    mode = int(p.settings.get('video_mode', 3))
    for s in p.scenes:
        if s.kind == 'story':
            s.ensure_layers(mode)
    return p


def blank_project(name='我的游戏', video_mode=3):
    """空工程：一个空场景 + 默认轨道，**不带任何素材**。

    ⚠ 这里必须显式清掉 Project.__init__ 带进来的默认内容 ✗
    `Project.__init__` 会给 `self.animations` 装上默认的"走路/待机"两套动画，
    而它们引用的是**默认精灵的下标**——空白工程里根本没有那些素材 ✗
    表现就是"新建的空白项目里带着一堆默认素材"（用户报的就是这个）。

    关卡地图（Level.default）保留：它是**数据**不是素材（一张 15x10 的
    平地地图，用纯色块画得出来），留着一张空地图比留一个空关卡列表好用 ✓
    """
    p = Project(name=name)
    p.settings['video_mode'] = video_mode
    p.scenes = [Scene('第一幕', 'story')]
    p.animations = []          # ← 关键：默认动画会引用不存在的素材
    return _apply_layers(p)


def demo_project(name='我的游戏'):
    """示例工程：自带角色、素材和一段能直接导出的剧情（供学习参考）"""
    p = Project(name=name)
    p.characters = [
        Character('witch', '魔女', '#ffd166', 'witch_', ['normal', 'smile', 'angry']),
        Character('girl', '少女', '#8ecae6', 'girl_', ['normal', 'smile', 'sad']),
    ]
    p.assets = [
        Asset('bg', 'assets/bg/海岸.png', '240x160', 240, 160),
        Asset('bg', 'assets/bg/沙漠.png', '240x160', 240, 160),
        Asset('char', 'assets/char/魔女/normal.png', '111x120', 111, 120),
        Asset('char', 'assets/char/少女/normal.png', '152x120', 152, 120),
        Asset('bgm', 'assets/bgm/序章.wav', '音频', 0, 0, 18.0),
    ]
    s = Scene('序章', 'story')
    s.duration = 18.0
    s.clips = [
        Clip('bg', 0, 18, 'show', 'assets/bg/海岸.png'),
        Clip('bgm', 0, 17.5, 'play', 'assets/bgm/序章.wav', {'loop': True, 'fade': 1.0}),
        Clip('char_1', 2, 22, 'show', 'witch', {'pose': 'smile', 'pos': 'left'}),
        Clip('text', 3, 3.2, 'say', 'witch',
             {'text': '海风停了。', 'voice': 'auto', 'wait': 'voice_or_key'}),
        Clip('voice', 3, 3.2, 'play', 'assets/voice/序章/witch_0101.wav', {'auto': True}),
        Clip('char_2', 7, 17, 'show', 'girl', {'pose': 'normal', 'pos': 'right'}),
        Clip('text', 7.5, 4.0, 'say', 'girl',
             {'text': '……它又在叫我了。', 'voice': 'auto', 'wait': 'voice_or_key'}),
        Clip('voice', 7.5, 4.0, 'play', 'assets/voice/序章/girl_0102.wav', {'auto': True}),
        Clip('fx', 12, 0.8, 'fade', '', {'mode': 'in', 'color': '#000000'}),
        Clip('text', 13, 3.6, 'say', 'witch',
             {'text': '你挑一个吧。反正我跟着你。', 'voice': 'auto', 'wait': 'key'}),
        Clip('voice', 13, 3.6, 'play', 'assets/voice/序章/witch_0103.wav', {'auto': True}),
    ]
    s.add_track('char1')        # 序章里两个人同时在场，所以第二条立绘轨道
    p.scenes = [s]
    return _apply_layers(p)


# 兼容旧名字（外部脚本/测试可能在用）
new_project = blank_project
