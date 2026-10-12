# -*- coding: utf-8 -*-
"""
preview.py —— 240×160 预览渲染（在编辑器里看到"实机画面"）

**这个文件里的每个常量都必须和 source/galgame.c 一致**，否则预览和实机就会不一致。
对照关系（改引擎时记得同步改这里）：

    galgame.c                    这里
    BOX_X / BOX_W / BOX_H   →    BOX_X / BOX_W / BOX_H
    TEXT_X / TEXT_Y / LINE_H→    TEXT_X / TEXT_Y / LINE_H
    TEXT_LINES / PAD        →    同
    SPRITE_Y / SPRITE_MARGIN→    同
    TEXT_MAX_PX             →    同
    char_x() 左=2 右=W-w-2  →    sprite_x()
    draw_scene 顺序：背景 → 立绘 → 对话框（框→名字→正文→▼）

排版算法（换行、禁则、打字机）也是照 text.c 的 text_layout 重写的，
不是"大概齐" —— 目标是**和实机逐像素一致**（有对比测试 tools 里可以验）。

素材转换**直接调用编译时用的那两个工具**（make_assets / make_cjk_font），
不另写一套，从根上避免"预览好看、实机走样"。
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

SCR_W, SCR_H = 240, 160

# ---- 引擎布局常量（source/galgame.c）----
BOX_X, BOX_W = 4, 232
TEXT_X = 10
LINE_H = 12
TEXT_LINES = 3
PAD = 3
NAME_H = 11
BOX_H = PAD * 2 + NAME_H + 2 + TEXT_LINES * LINE_H    # 55
BOX_Y = SCR_H - 4 - BOX_H                             # 101
NAME_Y = BOX_Y + PAD                                  # 104
TEXT_Y = BOX_Y + PAD + NAME_H + 2                     # 117
SPRITE_Y = 4
SPRITE_MARGIN = 2
TEXT_MAX_PX = 198
SPRITE_H = 120

# ---- 字体（include/font_data.h）----
GLYPH_W, GLYPH_H, ASCII_W = 11, 11, 6
STRIKE_SIZE = 12          # 命中宋体内嵌点阵的源字号（不要改）
FONT_PATH = r'C:\Windows\Fonts\simsun.ttc'

# ---- 节奏（galgame.c）----
TYPE_SPEED = 2            # 每 N 帧显示一个字
FPS = 60

# ---- 颜色（include/gfx.h，RGB15 → 8bit）----


def rgb15(r, g, b):
    """GBA 是 5 位色，展开到 8 位要和硬件一致（高 3 位补低位，不是简单 <<3）"""
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


CLR_TEXT = rgb15(31, 31, 31)
CLR_BOX_FILL = rgb15(6, 7, 14)
CLR_BOX_EDGE = rgb15(24, 26, 31)
CLR_CURSOR = rgb15(31, 26, 8)

# ---- 换行禁则（source/text.c）----
NO_LINE_START = {0xFF0C, 0x3002, 0x3001, 0xFF01, 0xFF1F, 0xFF1A, 0xFF1B,
                 0xFF09, 0x300D, 0x300F, 0x2026, 0x2014, 0x00B7}
NO_LINE_END = {0xFF08, 0x300C, 0x300E}


def advance(ch):
    """一个字符占几像素：ASCII 半角，其余全角（text.c 的 text_advance）"""
    return ASCII_W if ord(ch) < 0x80 else GLYPH_W



def layout_text(s, max_px=TEXT_MAX_PX, max_lines=TEXT_LINES):
    """照 text.c 的 text_layout 重写：按**像素**排满一行 + 两条禁则"""
    lines = []
    p = 0
    while p < len(s) and len(lines) < max_lines:
        start, n, w, q = p, 0, 0, p
        while q < len(s) and w < max_px:
            if s[q] == '\n':
                break
            adv = advance(s[q])
            if w + adv > max_px:
                break
            w += adv
            q += 1
            n += 1
        if q < len(s) and s[q] == '\n':                  # 显式换行
            lines.append((start, n))
            p = q + 1
            continue
        if q < len(s) and n > 1 and ord(s[q]) in NO_LINE_START:
            n -= 1                                       # 收尾标点不留在下行开头
        while n > 1 and ord(s[start + n - 1]) in NO_LINE_END:
            n -= 1                                       # 开头标点不留在上行结尾
        lines.append((start, n))
        p = start + n
    return lines


# 5 位色量化表：GBA 每个通道只有 32 级，硬件就是这么显示的。
# 不量化的话编辑器里渐变很顺，实机上会出现色带 —— 那就失去"所见即所得"的意义了。
_LUT = [((v >> 3) << 3) | ((v >> 3) >> 2) for v in range(256)]


def quantize_bgr555(img):
    """把一帧量化到硬件色深（每通道 5 位）"""
    return img.point(_LUT * 3)


class PreviewRenderer:
    """
    渲染器。资源转换结果会缓存（第一次几百毫秒，之后基本免费）。
    """

    def __init__(self, project, proj_dir):
        self.project = project
        self.proj_dir = proj_dir
        self._bg_cache = {}
        self._char_cache = {}
        self._glyph_cache = {}
        self._font = None
        self._top = None
        self._warned = set()

    # ---------------------------------------------------------------- 字体
    def _ensure_font(self):
        if self._font is None:
            import make_cjk_font as MF
            from PIL import ImageFont
            self._font = ImageFont.truetype(FONT_PATH, STRIKE_SIZE)
            # 截取窗口要和编译时算出来的**一样**，否则整行字会上下偏移
            self._top = MF.find_vertical_window(
                self._font, STRIKE_SIZE, '海风蘑菇塔ABC123')
        return self._font

    def glyph(self, ch):
        """返回 11 行位图（每行一个整数，高位在左）；和字库工具产出的完全一致"""
        if ch in self._glyph_cache:
            return self._glyph_cache[ch]
        import make_cjk_font as MF
        font = self._ensure_font()
        gw = GLYPH_W if ord(ch) >= 0x80 else ASCII_W
        rows, ink, _shift = MF.render_glyph(font, STRIKE_SIZE, ch, self._top,
                                           GLYPH_W, gw)
        self._glyph_cache[ch] = (rows, gw)
        return self._glyph_cache[ch]

    def draw_text(self, img, x, y, s, color, reveal=None):
        """画一行字。reveal=None 表示全画；否则只画前 reveal 个字（打字机）"""
        px = img.load()
        shown = 0
        cx = x
        for ch in s:
            if reveal is not None and shown >= reveal:
                break
            if ch == '\n':
                continue
            rows, gw = self.glyph(ch)
            for r, mask in enumerate(rows):
                yy = y + r
                if not (0 <= yy < SCR_H):
                    continue
                m = mask
                for b in range(GLYPH_W):
                    if m & 0x8000:
                        xx = cx + b
                        if 0 <= xx < SCR_W:
                            px[xx, yy] = color
                    m = (m << 1) & 0xFFFF
                    if m == 0:
                        break
            cx += gw
            shown += 1
        return cx

    # ---------------------------------------------------------------- 素材
    def sprite_path(self, char_id, pose='normal'):
        """
        角色 id + 表情 → 立绘文件。按命名约定找（和编译器/引擎一致）：
            1) assets/char/<角色名>/<表情>.png
            2) 资源库里该角色目录下、文件名等于表情的立绘
            3) 该角色目录下的任意一张立绘（退而求其次，总比不显示好）
        找不到时返回 (None, 原因) —— 叫"立绘缺失"，不是"静默空白"。
        """
        ch = self.project.character(char_id)
        if ch is None:
            return None, '角色表里没有 id=%s' % char_id
        norm = lambda s: s.replace('\\', '/')
        want = '%s.png' % pose
        cand = 'assets/char/%s/%s' % (ch.name, want)
        if os.path.isfile(self._src_path(cand)):
            return cand, None
        mine = [a for a in self.project.assets
                if a.kind == 'char' and ch.name in norm(a.path)]
        for a in mine:
            if os.path.basename(norm(a.path)) == want:
                return a.path, None
        if mine:
            return mine[0].path, '没有表情「%s」，暂用 %s' % (
                pose, os.path.basename(norm(mine[0].path)))
        return None, '角色「%s」还没有立绘（右键资源库导入）' % ch.name

    def _src_path(self, rel):
        return os.path.join(self.proj_dir, rel.replace('/', os.sep))

    def background(self, rel):
        """背景：和编译时一样 —— 直接 LANCZOS 缩放到 240×160"""
        if rel in self._bg_cache:
            return self._bg_cache[rel]
        p = self._src_path(rel)
        im = None
        if os.path.isfile(p):
            try:
                im = Image.open(p).convert('RGB').resize((SCR_W, SCR_H), Image.LANCZOS)
            except Exception as e:
                self._warn(rel, '背景读不出来：%s' % e)
        if im is None:
            im = Image.new('RGB', (SCR_W, SCR_H), (24, 24, 32))
        self._bg_cache[rel] = im
        return im

    def character(self, rel):
        """
        立绘：**调用编译时用的 make_assets.make_character**，保证和实机完全一致。

        注意 make_assets 是按 GFX_DIR + 文件名找源图的（那是编译时的约定），
        而项目里素材可能在 assets/char/<角色>/ 这种子目录，
        所以这里临时把 GFX_DIR 指到该文件所在目录 —— 早先没这么做，
        结果它去 graphics/ 下找 normal.png，找不到就静默返回空图，
        表现为"预览里立绘不见了"。
        """
        if rel in self._char_cache:
            return self._char_cache[rel]
        p = self._src_path(rel)
        im = None
        if os.path.isfile(p):
            try:
                import make_assets as MA
                out_dir = os.path.join(ROOT, '.tmp', 'preview-cache')
                os.makedirs(out_dir, exist_ok=True)
                old_gfx, old_out = MA.GFX_DIR, MA.OUT_DIR
                MA.GFX_DIR = os.path.dirname(p)
                MA.OUT_DIR = out_dir
                try:
                    rgba, _key = MA.make_character(os.path.basename(p), 'preview_tmp',
                                                   SPRITE_H)
                finally:
                    MA.GFX_DIR, MA.OUT_DIR = old_gfx, old_out
                im = rgba
            except Exception as e:
                self._warn(rel, '立绘转换失败：%s: %s' % (type(e).__name__, e))
        else:
            self._warn(rel, '立绘文件不存在：%s' % p)
        self._char_cache[rel] = im
        return im

    def _warn(self, key, msg):
        if key not in self._warned:
            self._warned.add(key)
            print('[preview] %s' % msg)

    # ---------------------------------------------------------------- 状态
    def state_at(self, scene, t):
        """
        算出播放头 t 时刻的画面状态。时间轴是"排布视图"，
        所以取"起点 <= t 的最后一个片段"，和实机按顺序执行的效果一致。
        """
        st = {'bg': None, 'chars': {}, 'text': None, 'reveal': None, 'cursor': False,
              'has_content': False,     # 这一时刻之前，引擎是否已经执行过"会画框"的命令
              # **按图层分组的画面**：从下往上的每一层各自算出"这一刻它显示什么"
              # 每一项是 {'layer': Layer, 'bg': 相对路径 或 None,
              #           'chars': {'left': 路径, 'right': 路径}}
              # ——没有图层的旧场景这里是空列表 ✓ render 会走原来那条单层路径 ✓
              'layers': [],
              'notes': []}
        if not scene:
            return st

        def kk(c):
            tk = scene.track(c.track)
            return tk.kind if tk else ''

        for c in sorted(scene.clips, key=lambda x: x.start):
            if c.start > t:
                continue
            k = kk(c)
            if k == 'bg':
                # 引擎的 bg 是硬切（淡入属性还没实现），这里如实照做
                st['bg'] = c.ref
                st['has_content'] = True
            elif k.startswith('char'):
                st['has_content'] = True
                pos = c.props.get('pos') or ('left' if k == 'char1' else 'right')
                if (c.props.get('action') or c.kind) == 'hide':
                    st['chars'][pos] = None
                else:
                    # ref 存的是**角色 id**，这里换算成立绘文件（找不到就记下原因）
                    rel, why = self.sprite_path(c.ref, c.props.get('pose', 'normal'))
                    st['chars'][pos] = rel
                    if why:
                        st['notes'].append(why)
            elif k == 'text':
                # 引擎在 CMD_SAY 里也会 draw_box ✗ 所以台词一开始播就算有内容
                if c.start <= t:
                    st['has_content'] = True
                if c.start <= t < c.start + c.dur:
                    st['text'] = c
                    frames = (t - c.start) * FPS
                    total = len(c.props.get('text') or '')
                    st['reveal'] = min(total, int(frames // TYPE_SPEED))
                    st['cursor'] = st['reveal'] >= total
                elif c.start + c.dur <= t:
                    st['text'] = None

        # ---- 按图层再算一遍"每一层这一刻显示什么" ----
        #
        # 【为什么要再算一遍而不是顺手记】
        # 上面那个循环是"整场景取最后一个片段" ✓ 对单层画面是对的 ✓
        # 但图层要的是"**各自层内**取最后一个片段" ✓ 两者的归属不同 ✓
        # 所以单独走一遍 ✓ 规则完全照抄上面（同一条轨道类型 → 同一种处理）✓
        # 这样"三层里各放一张背景"才能各自显示 ✗ 而不是互相覆盖 ✓
        #
        # 提示：**没有图层的旧场景**这里就是空列表 ✓ render 走单层路径 ✓
        #      所以老工程的表现**一个像素都不会变** ✓
        if getattr(scene, 'layers', None):
            for L in scene.layers:
                if not L.visible or L.kind == 'obj':
                    continue          # 隐藏的层不画；精灵层由立绘轨道单独处理
                bucket = {'layer': L, 'bg': None, 'chars': {}}
                ids = set(L.tracks)
                for c in sorted(scene.clips, key=lambda x: x.start):
                    if c.start > t or c.track not in ids:
                        continue
                    k = kk(c)
                    if k == 'bg':
                        bucket['bg'] = c.ref
                    elif k.startswith('char'):
                        pos = c.props.get('pos') or ('left' if k == 'char1' else 'right')
                        if (c.props.get('action') or c.kind) == 'hide':
                            bucket['chars'][pos] = None
                        else:
                            rel, _why = self.sprite_path(c.ref,
                                                         c.props.get('pose', 'normal'))
                            bucket['chars'][pos] = rel
                st['layers'].append(bucket)
        return st

    # ---------------------------------------------------------------- 渲染
    def render(self, scene, t, blink_on=True):
        """画一帧，返回 240×160 的 PIL 图"""
        st = self.state_at(scene, t)
        img = Image.new('RGB', (SCR_W, SCR_H), (0, 0, 0))

        def _paste_chars(chars):
            # 引擎的顺序：左、右
            for pos in ('left', 'right'):
                rel = chars.get(pos)
                if not rel:
                    continue
                ch_img = self.character(rel)
                if ch_img is None:
                    continue
                x = SPRITE_MARGIN if pos == 'left' else SCR_W - ch_img.width - SPRITE_MARGIN
                img.paste(ch_img, (x, SPRITE_Y), ch_img)

        if st['layers']:
            # **按图层从下往上叠** ✗
            # 每层先铺它自己的背景 ✓ 再叠它自己的立绘 ✓
            # 上一层盖在下一层上面 —— 这就是"轨道上下决定重叠上下"的落点 ✓
            #
            # ⚠ 层与层之间这里还**不做独立滚动**（视差）✗
            #   因为引擎现在还没有多 BG 滚动（那是阶段 6）✓
            #   预览不能显示"实机做不到的效果" ✓ 所以先按静态叠加来 ✓
            for bucket in st['layers']:
                if bucket['bg']:
                    img.paste(self.background(bucket['bg']), (0, 0))
                _paste_chars(bucket['chars'])
        else:
            # 1) 背景
            if st['bg']:
                img.paste(self.background(st['bg']), (0, 0))
            # 2) 立绘
            _paste_chars(st['chars'])

        # 3) 对话框（框 → 名字 → 正文 → ▼）
        #
        # **什么时候该画这个框：以引擎为准** ✗
        # 引擎（vn.c）是在**执行到 bg / 立绘 / 台词命令**的时候顺手把框画出来的 ——
        # 也就是说"场景里有过任何内容"才会有框 ✓
        # 而一个片段都没有的空场景（刚新建的工程就是这样）引擎**根本不画框** ✓
        #
        # 踩过：预览这里原来是无条件画框，于是空工程的预览里出现
        # 一个**没有文字也没有▼的空蓝框** —— 看起来像坏了 ✗
        #（用户报的"默认的光标位置文字显示有问题"就是这个）
        if st['has_content']:
            d = ImageDraw.Draw(img)
            d.rectangle([BOX_X, BOX_Y, BOX_X + BOX_W - 1, BOX_Y + BOX_H - 1],
                        fill=CLR_BOX_FILL)
            d.rectangle([BOX_X, BOX_Y, BOX_X + BOX_W - 1, BOX_Y + BOX_H - 1],
                        outline=CLR_BOX_EDGE)

            if st['text'] is not None:
                c = st['text']
                speaker = ''
                if c.props.get('style') != 'narrate':
                    ch = self.project.character(c.ref)
                    speaker = c.props.get('speaker') or (ch.name if ch else '')
                if speaker:
                    self.draw_text(img, TEXT_X, NAME_Y, speaker, CLR_CURSOR)
                body = c.props.get('text') or ''
                for i, (start, n) in enumerate(layout_text(body)):
                    self.draw_text(img, TEXT_X, TEXT_Y + i * LINE_H, body[start:start + n],
                                   CLR_TEXT, reveal=(st['reveal'] - sum(
                                       x[1] for x in layout_text(body)[:i])))
                if st['cursor'] and blink_on:
                    self.draw_text(img, BOX_X + BOX_W - 16, BOX_Y + BOX_H - 14, '▼', CLR_CURSOR)
        # 最后统一量化到硬件色深：预览里看到的颜色 = 实机能显示的颜色
        return quantize_bgr555(img)


