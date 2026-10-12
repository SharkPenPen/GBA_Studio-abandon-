# -*- coding: utf-8 -*-
"""
compiler.py —— 时间轴 → 剧本（事件表）+ 资源清单

P5 起引擎认的是**索引**，不再写死资源：
    bg <背景下标>          ← gfx_bgs[] 的下标
    char <位置> <立绘下标>  ← gfx_sprites[] 的下标（角色+表情在编译时展平）

所以编译时要做两件事：
  1. 收集这一版剧本**实际用到的**背景和立绘（用不到的不进 ROM，省空间）
  2. 写一份清单 scenario/assets.json，交给 tools/make_project_assets.py
     生成 C 资源表

位置：0=左 1=中 2=右

还被跳过的东西会**如实报告**（不假装成功）：
    语音 / BGM / 音效 / 特效 —— 引擎还没做音频（P6）
"""
import os

# 同一时刻的先后顺序：先换背景，再摆立绘，最后说话
PRIORITY = {'bg': 0, 'char1': 1, 'char2': 2, 'char3': 3, 'text': 4,
            'fx': 5, 'voice': 9, 'bgm': 9, 'se': 9}

POS_NUM = {'left': 0, 'center': 1, 'right': 2}


def _pos_num(props, kind):
    """位置 → 引擎编号。默认：第一条立绘轨靠左，其余靠右"""
    pos = props.get('pos') or ('left' if kind == 'char1' else 'right')
    return POS_NUM.get(pos, 0)


class AssetTable:
    """收集这一版用到的素材，给每个分配下标（写进清单交给资源编译器）"""

    def __init__(self, project, proj_dir):
        self.project = project
        self.proj_dir = proj_dir or ''
        self.bgs = []            # [{'name','src'}]
        self.sprites = []        # [{'char','pose','src'}]
        self.audio_list = []     # [{'kind','name','src'}]
        self._bg_ix = {}
        self._spr_ix = {}
        self._aud_ix = {}

    def _abs(self, rel):
        return os.path.join(self.proj_dir, rel.replace('/', os.sep)) \
            if self.proj_dir else rel

    def bg(self, rel):
        """背景 → 下标；找不到文件返回 None"""
        if rel in self._bg_ix:
            return self._bg_ix[rel]
        p = self._abs(rel)
        if not os.path.isfile(p):
            return None
        i = len(self.bgs)
        self.bgs.append({'name': os.path.splitext(os.path.basename(rel))[0], 'src': p})
        self._bg_ix[rel] = i
        return i

    def audio(self, rel, kind):
        """
        音频 → 下标。voice / bgm / se 共用一张表（引擎按命令区分走哪路）。
        找不到文件或格式不支持时返回 (None, 原因) —— 明确报出来，不静默跳过。
        """
        key = 'a:' + (rel or '')
        if key in self._aud_ix:
            v = self._aud_ix[key]
            # 命中缓存也要返回**元组**，否则调用方解包会炸（踩过）
            return (v, None) if isinstance(v, int) else (None, v)
        if not rel:
            self._aud_ix[key] = '音频片段没指定文件'
            return None, self._aud_ix[key]
        p = self._abs(rel)
        if not os.path.isfile(p):
            msg = '音频文件不存在：%s' % rel
            self._aud_ix[key] = msg
            return None, msg
        ext = os.path.splitext(p)[1].lower()
        # **不再只认 WAV** ✗
        # 以前这里写死 `ext != '.wav'` 就把音频跳过，用户得先用别的软件转 ✗
        # 现在导出时会**自动转码**（tools/audio_codec.py，多后端：
        # soundfile / ffmpeg / 内置 wave），OGG/MP3/FLAC 直接能用 ✓
        # 只有"本机一点解码能力都没有"时才报错，并且把该跑的命令写清楚 ✓
        try:
            import sys as _s, os as _o
            _s.path.insert(0, _o.path.join(
                _o.path.dirname(_o.path.dirname(_o.path.dirname(
                    _o.path.abspath(__file__)))), 'tools'))
            import audio_codec as _AC
            _can, _hint = _AC.can_decode(p), _AC.hint()
        except Exception:
            _can, _hint = (ext == '.wav'), ''
        if not _can:
            msg = ('%s 是 %s 格式，本机没有解码器。%s'
                   % (os.path.basename(rel), ext or '未知',
                      _hint or '先转成 WAV'))
            self._aud_ix[key] = msg
            return None, msg
        i = len(self.audio_list)
        self.audio_list.append({'kind': kind, 'name':
                                os.path.splitext(os.path.basename(rel))[0], 'src': p})
        self._aud_ix[key] = i
        return i, None

    def sprite(self, char_id, pose):
        key = '%s/%s' % (char_id, pose)
        if key in self._spr_ix:
            v = self._spr_ix[key]
            return (v, None) if isinstance(v, int) else (None, v)   # 同上，必须返回元组
        ch = self.project.character(char_id)
        if ch is None:
            self._spr_ix[key] = '角色表里没有 id=%s' % char_id
            return None, self._spr_ix[key]
        want = '%s.png' % pose
        norm = lambda s: s.replace('\\', '/')
        mine = [a for a in self.project.assets
                if a.kind == 'char' and ch.name in norm(a.path)]
        hit = None
        cand = 'assets/char/%s/%s' % (ch.name, want)
        if os.path.isfile(self._abs(cand)):
            hit = cand
        else:
            for a in mine:
                if os.path.basename(norm(a.path)) == want:
                    hit = a.path
                    break
            if hit is None and mine:
                hit = mine[0].path
                pose = os.path.splitext(os.path.basename(norm(hit)))[0]
        if hit is None:
            msg = '角色「%s」还没有立绘' % ch.name
            self._spr_ix[key] = msg
            return None, msg
        p = self._abs(hit)
        if not os.path.isfile(p):
            msg = '立绘文件不存在：%s' % hit
            self._spr_ix[key] = msg
            return None, msg
        i = len(self.sprites)
        self.sprites.append({'char': char_id, 'pose': pose, 'src': p})
        self._spr_ix[key] = i
        return i, None

    def manifest(self):
        """标题背景 + LOGO + 精灵（P9）"""
        title = 0
        tb = (self.project.settings or {}).get('title_bg')
        if tb:
            ix = self._bg_ix.get(tb)
            if ix is not None:
                title = ix

        # P9：精灵（kind == 'sprite'）单独一张清单，生成脚本会把它们
        # **排在 gfx_sprites[] 最前面**，下标就是 0,1,2…
        #
        # 为什么要单独一张、还要保证顺序：动画表（anim_data.c）里记的是
        # "第几号精灵"，而 gfx_sprites[] 里还混着立绘。要是精灵的下标
        # 取决于"这次剧本用了几个立绘"，加一句台词就会让动画全错位 ——
        # 这种错很难查（画面只是"动得不对"，不报错）。
        flat = []
        for a in self.project.assets:
            if a.kind == 'sprite':
                p = self._abs(a.path)
                if os.path.isfile(p):
                    flat.append({'name': os.path.basename(a.path), 'src': p})

        # P9：动画也进清单。这里就把帧的**绝对路径**解析好 ——
        # 生成脚本（make_project_anim.py）只认清单，不用再去啃 .gbastudio，
        # 和背景/立绘/音频走同一条路。
        anims = []
        for an in getattr(self.project, 'animations', []) or []:
            frames = []
            for fr in an.frames:
                p = self._abs(fr.path)
                if os.path.isfile(p):
                    frames.append({'src': p, 'dur': max(1, fr.dur)})
            if frames:
                anims.append({'name': an.name, 'loop': bool(an.loop),
                              'frames': frames})

        m = {'title_bg': title, 'bg': self.bgs, 'sprites': self.sprites,
             'flat': flat, 'animations': anims, 'audio': self.audio_list}
        # LOGO：项目里名字带 logo 的素材（未分类也行，样品里就是这种）
        for a in self.project.assets:
            base = os.path.splitext(os.path.basename(a.path))[0].lower()
            if 'logo' in base or base in ('标题', 'biaoti'):
                p = self._abs(a.path)
                if os.path.isfile(p):
                    m['logo'] = {'name': base, 'src': p}
                    break
        return m


def compile_scene(project, scene, table, log=None):
    """把一个场景编译成剧本行 + 问题列表"""
    lines, notes = [], []
    s = scene

    def kind_of(c):
        t = s.track(c.track)
        return t.kind if t else ''

    clips = list(s.clips)

    def sort_key(c):
        k = kind_of(c)
        return (round(c.start, 3), PRIORITY.get(k, 5))
    clips.sort(key=sort_key)

    skipped = {'voice': 0, 'bgm': 0, 'se': 0, 'fx': 0}

    for c in clips:
        k = kind_of(c)
        ch = project.character(c.ref)

        if k == 'bg':
            ix = table.bg(c.ref)
            if ix is None:
                notes.append('⚠ 背景文件不存在，已跳过：%s' % (c.ref or '?'))
            else:
                lines.append('bg %d            # %s' % (ix, os.path.basename(c.ref)))

        elif k.startswith('char'):
            pos = _pos_num(c.props, k)
            action = c.props.get('action') or c.kind or 'show'
            if action == 'hide':
                lines.append('hide %d' % pos)
            else:
                ix, why = table.sprite(c.ref, c.props.get('pose', 'normal'))
                if ix is None:
                    notes.append('⚠ %s，已跳过' % why)
                    continue
                lines.append('char %d %d        # %s/%s'
                             % (pos, ix, c.ref, c.props.get('pose', 'normal')))

        elif k == 'text':
            txt = (c.props.get('text') or '').strip()
            if not txt:
                continue
            name = c.props.get('speaker') or (ch.name if ch else '')
            if c.props.get('style') == 'narrate':
                name = ''
            lines.append('say %s|%s' % (name, txt.replace('|', '｜')))

        # ---- 音频（P6）：语音走 A，BGM/音效走 B ----
        elif k == 'voice':
            ix, why = table.audio(c.ref, 'voice')
            if ix is None:
                notes.append('⚠ %s，语音已跳过' % why)
            else:
                lines.append('voice %d' % ix)

        elif k == 'bgm':
            ix, why = table.audio(c.ref, 'bgm')
            if ix is None:
                notes.append('⚠ %s，音乐已跳过' % why)
            else:
                lines.append('bgm %d %s' % (ix, 'loop' if c.props.get('loop', True)
                                            else 'once'))

        elif k == 'se':
            ix, why = table.audio(c.ref, 'se')
            if ix is None:
                notes.append('⚠ %s，音效已跳过' % why)
            else:
                lines.append('se %d' % ix)

        elif k == 'fx' and c.kind == 'mode':
            # P10：切玩法的片段。放在 fx 轨上 —— 它本来就是"非画面事件"的轨道，
            # 触发方式（到时间就执行）也和特效一样，没必要单开一条轨道。
            to = (c.props or {}).get('to', 'level')
            lines.append('mode %d' % (1 if to == 'level' else 0))
            if c.props:
                pass

        elif k in skipped:
            skipped[k] += 1

    for k, n in skipped.items():
        if n:
            zh = {'fx': '特效'}[k]
            notes.append('⚠ 有 %d 个%s片段被跳过（引擎还没做特效）' % (n, zh))
    return lines, notes


def write_video_mode(project, out_dir, log=None):
    """把工程选的显示模式写成一个小头文件，交给引擎。

    **为什么要写文件而不是直接改引擎源码**：引擎是"一次编译、多工程共用"的，
    显示模式属于**工程设置** ✗ 直接改源码的话，切工程就得改代码，
    而且改了什么没人记得住。写成 include/project_video.h 之后：
        · 引擎里只有一处 #include 它
        · 每次导出都会按当前工程的设置刷新
        · git diff 里能看见"这个工程用的是模式几"
    """
    mode = int(project.settings.get('video_mode', 3))
    if mode < 0 or mode > 5:
        mode = 3
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'project_video.h')
    # **要不要跳过引擎自带的演示标题** ✗
    # 标题画面是给框架示例用的：底图是引擎内置的、菜单里有"关卡试玩"和"关于本作"
    #（写着"测试版"）、音效是示例工程的测试音效 ✗
    # 真正的游戏应该一开机就进故事 ✓ 所以默认跳过 ✓
    # 想要标题的工程把它设成 0 就行 ✓
    skip = 1 if project.settings.get('skip_title', 1) else 0
    text = ('/* 由导出流程写出，请勿手工修改。\n'
            ' * 这个工程用的 GBA 显示模式：%d\n'
            ' * 开场：%s\n'
            ' * 改它们请用编辑器「项目设置」——模式是架构级选择，换个数字不是小事。 */\n'
            '#ifndef PROJECT_VIDEO_H\n#define PROJECT_VIDEO_H\n\n'
            '#define GAL_VIDEO_MODE %d\n'
            '#define GAL_SKIP_TITLE %d\n\n#endif\n'
            % (mode,
               '跳过引擎演示标题，直接进剧情' if skip else '显示引擎自带的标题菜单',
               mode, skip))
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    if log:
        log('显示模式：模式 %d → %s' % (mode, os.path.basename(path)))
    return path


def compile_project(project, proj_dir=None, log=None):
    """
    编译整个项目，返回 (剧本文本, 提示列表, 资源清单)
    资源清单要写成 scenario/assets.json，交给 tools/make_project_assets.py
    """
    table = AssetTable(project, proj_dir)
    out, notes = [], []
    scenes = [s for s in project.scenes if s.kind == 'story']
    if not scenes:
        return None, ['❌ 没有剧情场景'], None

    for i, s in enumerate(scenes):
        if log:
            log('── 场景 %d：%s ──' % (i + 1, s.name))
        lines, n = compile_scene(project, s, table, log)
        if lines:
            out.append('# ===== %s =====' % s.name)
            out += lines
        notes += n

    if not out:
        return None, ['❌ 编译结果为空（时间轴上一个片段都没有？）'] + notes, None
    out.append('')
    out.append('end')
    if not table.bgs:
        notes.append('⚠ 一张背景都没用上（实机会黑屏）')

    # ---- 图层：如实说明"这一版导出还不会分层" ✗ ----
    #
    # 编辑器里已经有图层了（数量由模式定 ✓ 层内轨道打包时重叠 ✓）
    # 但**引擎还不支持同时显示多个 BG 层**（那是后面的阶段 6）✓
    # 所以这一版导出：把画面**合成成一张**交给引擎 ✓ 结果是对的 ✓ 但视差做不了 ✓
    #
    # 为什么一定要说出来：用户在图层面板里看到 4 个层 ✓
    # 如果导出后什么都不提 ✓ 他会以为"视差已经能用" ✓ 到实机上才发现不动 ✓
    # ——**做不到的事要在导出时就讲清楚** ✓ 不能等到实机 ✓
    multi = [s.name for s in project.scenes
             if s.kind == 'story' and getattr(s, 'layers', None)
             and len([L for L in s.layers if L.kind != 'obj' and L.tracks]) > 1]
    if multi:
        notes.append('ℹ 有 %d 个场景用了多个图层（%s…）：'
                     '本版导出会把它们**合成成一张画面** ✓ 画面是对的，'
                     '但层与层之间还不能独立滚动（视差待引擎支持）'
                     % (len(multi), '、'.join(multi[:3])))
    return '\n'.join(out) + '\n', notes, table.manifest()


def write_level(project, gba_dir):
    """
    把关卡地图写成 level.txt（P8）。

    和 scenario.txt 一样，这是给**编译脚本**看的中间产物，不是引擎读的：
    引擎要的是 C 数组（tools/make_project_level.py 负责转）。
    先落成文本的好处是能直接打开看、能进版本管理、出问题好查。
    """
    if not gba_dir or getattr(project, 'level', None) is None:
        return None
    # 和 scenario.txt / assets.json 放一起：引擎那边的脚本只认这个目录
    return project.level.save(os.path.join(gba_dir, 'scenario', 'level.txt'))
