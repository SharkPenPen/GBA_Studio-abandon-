# -*- coding: utf-8 -*-
"""
assets.py —— 资源库 + **GBA 合规检查**

合规检查是这个工具最有价值的部分之一：Godot 或普通编辑器不会告诉你
"调色板超 256 色 / 图块超 VRAM / 精灵超 128 个 / ROM 超 32MB"，
但 GBA 上这些是硬限制，违反了就是花屏或者直接跑不起来。

P1 阶段先做"静态数值检查"（尺寸、数量、体积、命名约定），
真正的图片量化/图块统计等 P3 导入素材时接上。
"""
import os

# GBA 硬件硬限制（其余见 docs/03 硬件速查）
SCR_W, SCR_H = 240, 160
MAX_OBJ = 128                       # 硬件精灵数上限


class Issue:
    def __init__(self, level, where, msg):
        self.level = level      # 'error' | 'warning' | 'info'
        self.where = where
        self.msg = msg

    def __str__(self):
        icon = {'error': '❌', 'warning': '⚠', 'info': '·'}[self.level]
        return '%s %s：%s' % (icon, self.where, self.msg)


# ---------------------------------------------------------------------------
# 素材导入的命名约定（docs/07 第 6 节）
#   assets/bg/海岸.png
#   assets/char/魔女/normal.png
#   assets/voice/序章/witch_0101.ogg
# ---------------------------------------------------------------------------
KIND_DIRS = {'bg': 'bg', 'char': 'char', 'sprite': 'sprite', 'bgm': 'bgm',
             'se': 'se', 'voice': 'voice'}
IMG_EXT = ('.png', '.bmp', '.jpg', '.jpeg')
AUD_EXT = ('.wav', '.ogg', '.mp3', '.flac')


def scan_folder(proj_dir, known=None):
    """
    扫描项目的 assets/ 目录，返回 (资源列表, 问题列表)。

    分类原则（按用户要求改了）：
      · **导入时不做任何分类** —— 文件原样放进 assets/，一律算"未分类"
      · assets/<bg|char|bgm|voice|se>/ 下面的文件按目录自动认类型（那是手动归类后的位置）
      · 已经在项目里登记过的素材，**保留它原来的类型**（不会被扫描覆盖）
    """
    assets, issues = [], []
    known = known or {}
    root = os.path.join(proj_dir, 'assets')
    if not os.path.isdir(root):
        issues.append(Issue('info', 'assets/', '还没有 assets 目录（导入素材会自动创建）'))
        return assets, issues

    for dirpath, _, files in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace('\\', '/')
        top = rel_dir.split('/')[0] if rel_dir != '.' else ''
        auto_kind = top if top in KIND_DIRS else ''      # 只有标准目录才自动认类型
        for fn in sorted(files):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, proj_dir).replace('\\', '/')
            ext = os.path.splitext(fn)[1].lower()
            if ext not in IMG_EXT + AUD_EXT:
                continue
            kind = known.get(rel, auto_kind)             # 已登记的类型优先
            w = h = 0
            dur = 0.0
            if ext in IMG_EXT:
                try:
                    from PIL import Image
                    with Image.open(full) as im:
                        w, h = im.size
                except Exception:
                    pass
                note = '%dx%d' % (w, h) if w else '图片'
                if kind == 'bg' and (w, h) != (SCR_W, SCR_H):
                    note += '（编译时缩到 240x160）'
            else:
                note = '音频'
                # **任何格式都读一下时长** ✗ 以前只读 .wav，于是导入 OGG 时
                # 时间轴上音频片段长度全靠猜（而且会显示成 0.0 秒）✗
                # 现在交给音频转码器统一读（它多后端：soundfile / ffmpeg / 内置 wave）
                dur = _audio_duration(full)
                if dur > 0:
                    note = '%.1f 秒' % dur
                # 顺便提示"这一条转成 GBA 格式后要占多少 ROM"
                try:
                    import sys as _s, os as _o
                    _s.path.insert(0, _o.path.join(
                        _o.path.dirname(_o.path.dirname(_o.path.dirname(
                            _o.path.abspath(__file__)))), 'tools'))
                    import audio_codec as _AC
                    if _AC.can_decode(full):
                        r = _AC.convert(full, _AC.DEFAULT_RATE, use_cache=True)[1]
                        kb = dur * r / 1024.0
                        if kb > 0:
                            note += '  ·  GBA 约 %.0f KB' % kb
                    else:
                        note += '  ·  ⚠ 需要解码库（跑 tools\\setup-audio-codec.py）'
                except Exception:
                    pass
            assets.append(_mk(kind, rel, note, w, h, dur))

    un = len([a for a in assets if not a.kind])
    if un:
        issues.append(Issue('info', '未分类素材',
                            '有 %d 个素材还没分类。右键 →「归类为」就能指定它们是背景/立绘/音乐/语音/音效' % un))
    return assets, issues


def _audio_duration(path):
    """读音频时长（秒）。读不到返回 0。

    先走 tools/audio_codec.py（多后端 ✗ 支持 OGG/MP3/FLAC）
    不行再退回内置的 WAV 读取 ✓ 保证至少 WAV 一直能用
    """
    try:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.join(
            _o.path.dirname(_o.path.dirname(_o.path.dirname(
                _o.path.abspath(__file__)))), 'tools'))
        import audio_codec as _AC
        vals, rate = _AC.load_any(path)
        if rate > 0:
            return len(vals) / float(rate)
    except Exception:
        pass
    try:
        return _wav_duration(path)
    except Exception:
        return 0.0


def _mk(kind, rel, note, w, h, dur):
    from core.project import Asset
    return Asset(kind, rel, note, w, h, dur)


# ---------------------------------------------------------------------------
# 导入 / 导出素材
# ---------------------------------------------------------------------------
def ensure_dirs(proj_dir):
    """建好 assets/ 的标准目录结构（导入素材自动归位靠它）"""
    made = []
    for sub in ('bg', 'char', 'sprite', 'bgm', 'voice', 'se'):
        d = os.path.join(proj_dir, 'assets', sub)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            made.append('assets/' + sub)
    return made



def import_files(proj_dir, paths, kind=None, character=None, rename=None):
    """
    把外部文件拷进项目。

    **默认不做分类**（按用户要求）：文件原样放进 assets/，之后在资源库里
    右键「归类为」手动指定是背景/立绘/音乐/语音/音效。
    传了 kind 才按老办法直接放进对应目录（给"归类"功能复用）。

    返回 (成功列表, 失败列表, 提示列表)
    """
    ensure_dirs(proj_dir)
    ok, bad, notes = [], [], []
    for src in paths:
        if not os.path.isfile(src):
            bad.append((src, '文件不存在'))
            continue
        ext = os.path.splitext(src)[1].lower()
        if ext not in IMG_EXT + AUD_EXT:
            bad.append((src, '不支持的格式（支持 png/jpg/bmp 和 wav/ogg/mp3）'))
            continue
        base = os.path.basename(src)
        if rename:
            base = rename(base)
        if kind == 'char' and character:
            dst_dir = os.path.join(proj_dir, 'assets', 'char', character)
        elif kind:
            dst_dir = os.path.join(proj_dir, 'assets', KIND_DIRS[kind])
        else:
            dst_dir = os.path.join(proj_dir, 'assets')      # 不分类：直接放 assets 下
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, base)
        if os.path.abspath(dst) == os.path.abspath(src):
            notes.append('%s 已经在项目里，跳过' % base)
            continue
        if os.path.exists(dst):
            stem, e2 = os.path.splitext(base)
            i = 2
            while os.path.exists(os.path.join(dst_dir, '%s_%d%s' % (stem, i, e2))):
                i += 1
            dst = os.path.join(dst_dir, '%s_%d%s' % (stem, i, e2))
            notes.append('%s 重名，已存为 %s' % (base, os.path.basename(dst)))
        try:
            import shutil
            # 用 copy 而不是 copy2：copy2 会连只读属性一起复制过来，
            # 之后想删/改这个素材就会 PermissionError（踩过）
            shutil.copy(src, dst)
            try:
                os.chmod(dst, 0o666)      # 清掉可能的只读标记
            except Exception:
                pass
            ok.append(os.path.relpath(dst, proj_dir).replace('\\', '/'))
        except Exception as e:
            bad.append((src, str(e)))
    if ok and not kind:
        notes.append('导入的素材是「未分类」状态，右键可以归类')
    return ok, bad, notes


def classify_asset(proj_dir, asset, kind, character=None):
    """
    手动归类：把文件挪进对应目录，返回新的相对路径。
    （这是用户要的"人工手动分类"）
    """
    src = os.path.join(proj_dir, asset.path)
    if not os.path.isfile(src):
        return None, '文件不存在：%s' % asset.path
    ext = os.path.splitext(src)[1].lower()
    if kind == 'char' and character:
        dst_dir = os.path.join(proj_dir, 'assets', 'char', character)
    else:
        dst_dir = os.path.join(proj_dir, 'assets', KIND_DIRS[kind])
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    try:
        import shutil
        if os.path.abspath(src) != os.path.abspath(dst):
            if os.path.exists(dst):
                return None, '目标目录里已有同名文件：%s' % os.path.basename(dst)
            shutil.move(src, dst)
            try:
                os.chmod(dst, 0o666)
            except Exception:
                pass
        return os.path.relpath(dst, proj_dir).replace('\\', '/'), None
    except Exception as e:
        return None, str(e)


def export_assets(proj_dir, dest_dir, assets):
    """把素材（或转换后的资源）拷到指定目录，返回 (成功数, 失败列表)"""
    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    n, bad = 0, []
    for a in assets:
        src = os.path.join(proj_dir, a.path)
        if not os.path.isfile(src):
            bad.append((a.path, '文件不存在'))
            continue
        d = os.path.join(dest_dir, KIND_DIRS.get(a.kind, ''), os.path.basename(a.path))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        try:
            shutil.copy2(src, d)
            n += 1
        except Exception as e:
            bad.append((a.path, str(e)))
    return n, bad


def _fmt_dur(d):
    if d <= 0:
        return '音频'
    return '%.1f 秒' % d


def _wav_duration(path):
    """读 WAV 头算时长（不加载整个文件）"""
    try:
        import wave
        with wave.open(path, 'rb') as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 合规检查
# ---------------------------------------------------------------------------
def check_project(proj):
    """返回 [Issue]。P1 先查"能算出来的"，避免用户到编译时才发现"""
    issues = []

    # 1. 字号档位
    fs = proj.settings.get('font_size', 12)
    from core.project import FONT_SIZES
    if fs not in FONT_SIZES:
        issues.append(Issue('error', '项目设置', '字号档位 %s 不支持（可选 8/12/16）' % fs))
    elif FONT_SIZES[fs]['cjk'] is None:
        issues.append(Issue('warning', '项目设置',
                            '字号 %d 档没有中文（汉字最小需要 12 档），中文会自动回退到 12 档' % fs))

    # 2. 角色表 vs 立绘素材
    for c in proj.characters:
        for pose in c.poses:
            hit = any(a.kind == 'char' and c.name in a.path and pose in a.path
                      for a in proj.assets)
            if not hit:
                issues.append(Issue('warning', '角色 %s' % c.name,
                                    '表情 "%s" 找不到立绘（assets/char/%s/%s.png）'
                                    % (pose, c.name, pose)))

    # 3. 时间轴：语音重叠（GBA 只有 1 路语音通道，重叠是硬错误）
    for s in proj.scenes:
        if s.kind != 'story':
            continue

        def kind_of(c):
            t = s.track(c.track)
            return t.kind if t else ''

        vs = sorted([c for c in s.clips if kind_of(c) == 'voice'], key=lambda c: c.start)
        for i in range(len(vs) - 1):
            a, b = vs[i], vs[i + 1]
            if a.start + a.dur > b.start + 0.001:
                issues.append(Issue('error', '场景 %s' % s.name,
                                    '语音重叠：%.1f~%.1f 与 %.1f~%.1f（GBA 只有 1 路语音，'
                                    '请把后一条往后挪或删掉）'
                                    % (a.start, a.start + a.dur, b.start, b.start + b.dur)))
        for t in [c for c in s.clips if kind_of(c) == 'text']:
            txt = t.props.get('text', '')
            if not txt.strip():
                issues.append(Issue('warning', '场景 %s' % s.name, '有一句空台词'))
            elif _text_px(txt, proj.settings.get('font_size', 12)) > 18 * 11 * 3:
                issues.append(Issue('error', '场景 %s' % s.name,
                                    '台词太长（超出一屏能显示的量）：「%s…」' % txt[:10]))

    # 4. 资源数量与体积（粗算）
    n_char = len([a for a in proj.assets if a.kind == 'char'])
    if n_char > MAX_OBJ:
        issues.append(Issue('error', '立绘', '立绘数 %d 超过硬件精灵上限 %d' % (n_char, MAX_OBJ)))
    bg_kb = len([a for a in proj.assets if a.kind == 'bg']) * 76.8
    voice_kb = sum(a.dur for a in proj.assets if a.kind == 'voice') * 11.0   # 8bit/11kHz
    total_kb = bg_kb + voice_kb + n_char * 30
    if total_kb > 4096:
        issues.append(Issue('info', '体积估算',
                            '资源约 %.1f MB（背景 %.1f + 语音 %.1f + 立绘 %.1f），'
                            '卡带上限 32 MB' % (total_kb / 1024, bg_kb / 1024,
                                              voice_kb / 1024, n_char * 30 / 1024)))
    return issues


def _text_px(s, font_size):
    """按字号档位估算文字宽度（汉字 = 档位-1 像素，ASCII 半角）"""
    from core.project import FONT_SIZES
    fs = FONT_SIZES.get(font_size, FONT_SIZES[12])
    cjk = fs['cjk'] or FONT_SIZES[12]['cjk']
    asc = fs['ascii']
    return sum(asc if ord(c) < 0x80 else cjk for c in s)


def format_report(issues):
    if not issues:
        return '✅ 没有发现问题'
    errs = [i for i in issues if i.level == 'error']
    warns = [i for i in issues if i.level == 'warning']
    return '检查完成：%d 个错误 / %d 个警告\n' % (len(errs), len(warns)) + \
           '\n'.join(str(i) for i in issues[:20])
