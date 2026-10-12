#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tsv_to_project.py —— 把解包出来的剧本（TSV）转成 GBAStudio 工程

【为什么要这个工具】
编辑器是**手工排时间轴**的 ✗ 而原作有 5705 句台词 ✓
手工排 = 几十小时 ✓ 不现实 ✓
所以这里把已经解析好的双语对照表**自动转成工程** ✓ 之后在编辑器里改就行 ✓

输入（解包工具产出，都在 `剧本/` 下）：
    台词对照_JP_CN.tsv    场景 / 索引 / 日文 / 中文   ← 主要是用它
    Rio_zhCN\\NameTable.txt   日文名 + 中文名 的成对表（可选，用来补说话人）

输出：
    <out>/<name>/<name>.gbastudio    一个可编辑的工程
    每个 TSV 场景 → 一个 story 场景，每页台词 → 一个 text 片段

【最要紧的一件事：分页】
引擎的对话框只有 **3 行**（`TEXT_LINES 3`）✗ 而原作一页经常超过 3 行 ✓
直接转过去，超出的部分会被**静默截掉** ✓
所以这里用 `core.preview.layout_text` —— 那是**照引擎一字不差重写的排版算法** ✗
先算出这句要几行，超过 3 行就**切成多页** ✓
这样"编辑器里看到的换行 = 实机上的换行" ✓

【内容说明】
这是从一部 18+ 作品解包出来的文本 ✓ 本工具只做**机械转换**，
不解析语义、不筛选内容；日志里只打统计数字，不打印台词 ✓

用法：
    python tools\\tsv_to_project.py --tsv "<TSV路径>" --out "<输出目录>" [--name 工程名]
                                   [--limit 3]      # 只转前 3 个场景（试跑）
                                   [--scenario-only] # 只出 scenario.txt，不建工程
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

from core.project import Project, Scene, Clip, Track, Character, Asset   # noqa: E402
from core import assets as As                                            # noqa: E402

# 和引擎一致的排版参数（预览里的 layout_text 就是照引擎重写的）
MAX_LINES = 3


def log(m):
    print('[script] ' + m)


# ---------------------------------------------------------------------------
# 读输入
# ---------------------------------------------------------------------------
def read_tsv(path):
    """读双语对照表 → [(场景, 索引, 中文), ...]

    中文里带原作的控制码，这里顺手清掉：
        「」    对话引号（外层包装，去掉）
        %K      等待按键（引擎的 say 本身就是等玩家 ✓ 不需要）
        %P      翻页（我们自己按 3 行分页 ✓ 所以也去掉）
        \\n      原作的手动换行（引擎会自动排版 ✓ 去掉，免得双重换行）
    """
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        head = f.readline().rstrip('\n').split('\t')
        # 表头可能是 场景/索引/日文/中文，也可能是别的顺序 —— 按名字找列
        try:
            i_sc = head.index('场景')
            i_ix = head.index('索引')
            i_cn = head.index('中文')
            i_jp = head.index('日文')
        except ValueError:
            i_sc, i_ix, i_cn = 0, 1, len(head) - 1
            i_jp = 2
        for ln in f:
            p = ln.rstrip('\n').split('\t')
            if len(p) <= max(i_sc, i_ix, i_cn):
                continue
            try:
                ix = int(p[i_ix])
            except ValueError:
                continue
            rows.append((p[i_sc].strip(), ix, p[i_cn], p[i_jp]))
    return rows


def clean_text(s):
    """清控制码 → 纯文本（只留下真正要显示的字）"""
    s = s.replace('「', '').replace('」', '')
    s = s.replace('%K', '').replace('%P', '')
    s = s.replace('%LF', '')
    s = s.replace('\\n', ' ')          # 原作的手动换行 → 空格（引擎自己会排）
    s = s.replace('\r', ' ').replace('\n', ' ')
    s = re.sub(r'%[A-Za-z0-9]{1,2}', '', s)     # 剩下的控制码一律去掉
    s = re.sub(r'[ \t\u3000]+', ' ', s).strip()
    return s


def read_names(path):
    """读 NameTable（UTF-16LE，日文名/中文名成对出现）→ {日文: 中文}

    ⚠ 解出来的字符串里混着长度字节和 %, 之类的填充 ✓
    这里只做"尽力而为"的提取：把连续的中日文字符切成一个个名字，
    相邻两个一配对 ✓ 配不上就跳过 ✓ 这个表只用来给台词补说话人，
    补不上不影响文字本身 ✓
    """
    try:
        raw = open(path, 'rb').read().decode('utf-16-le', 'ignore')
    except Exception:
        return {}
    # 去掉控制字节
    s = ''.join(ch for ch in raw if ch.isprintable() and ch not in '%·')
    names = re.findall(r'[\u3040-\u30ff\u4e00-\u9fff\uff66-\uff9fA-Za-z0-9]{1,12}', s)
    out = {}
    for i in range(0, len(names) - 1, 2):
        jp, cn = names[i], names[i + 1]
        if re.search(r'[\u4e00-\u9fff]', cn) and jp not in out:
            out[jp] = cn
    return out


# ---------------------------------------------------------------------------
# 分页：用引擎的排版算法算行数，超过 3 行就切开
# ---------------------------------------------------------------------------
def paginate(text, layout_text):
    """把一段长文本切成若干页，每页不超过 MAX_LINES 行

    返回 [页文本, ...]（每页都是可以直接放进一个 say 的字符串）
    """
    if not text:
        return []
    # ⚠ 必须传 max_lines=9999 ✗
    # `layout_text` 的默认参数就是 `max_lines=TEXT_LINES`（=3）——
    # 它是**给渲染用的**：排满 3 行就停 ✓
    # 拿默认值来分页的话，永远只看到 3 行 ✓ 于是"每句都刚好 3 行" ✓
    # 长台词**根本不会被切开**，超出的部分在实机上直接消失 ✗
    #（这个坑是被 tests/test_script_convert.py 抓出来的：分页测试自己先失败了 ✓）
    lines = layout_text(text, max_lines=9999)   # 先拿到**全部**行
    if len(lines) <= MAX_LINES:
        return [text]
    pages, cur = [], []
    for start, n in lines:
        cur.append(text[start:start + n])
        if len(cur) == MAX_LINES:
            pages.append(''.join(cur))
            cur = []
    if cur:
        pages.append(''.join(cur))
    return pages


# ---------------------------------------------------------------------------
# 转工程
# ---------------------------------------------------------------------------
def text_key(s):
    """和 ws2_scenes.py 里同一个指纹算法（两边必须一致 ✗）"""
    import hashlib
    if s is None:
        return ''
    x = str(s)
    x = re.sub(r'^[A-Za-z_]+', '', x)
    x = x.replace('「', '').replace('」', '')
    x = re.sub(r'%[A-Za-z0-9]{1,2}', '', x)
    x = x.replace('\\n', '').replace('\n', '')
    x = re.sub(r'[\s\u3000]+', '', x)
    return hashlib.md5(x.encode('utf-8')).hexdigest()[:16]


def _find_asset(proj, fname):
    """按文件名在工程素材里找

    ⚠ 传进来的可能是**裸文件名**（ws2 里是 BGBLACK.PNG ✓）
      也可能是**工程内相对路径**（预合成图给的是 assets/bg/comp_xxx.png ✓）
      所以两头都要先取 basename 再比 ✗
    （踩过：拿 basename 去比完整相对路径 → 永远不相等 →
      预合成图一张都挂不上，而且**不报错** ✓）
    """
    want = os.path.basename(str(fname)).lower()
    for a in proj.assets:
        if os.path.basename(a.path).lower() == want:
            return a.path
    # 退一步：忽略扩展名比
    stem = os.path.splitext(want)[0]
    for a in proj.assets:
        if os.path.splitext(os.path.basename(a.path).lower())[0] == stem:
            return a.path
    return None


def build_project(rows, name='移植剧本', limit=0, scenes_map=None,
                  assets=None, characters=None, comp_map=None):
    """把台词表转成一个工程对象。

    每个 TSV 场景 → 一个 story 场景；
    每页台词 → 一个 text 片段（时长按字数估，够读就行）。
    """
    from core.preview import layout_text

    scenes_by_id = {}
    order = []
    for sc, ix, cn, jp in rows:
        if sc not in scenes_by_id:
            scenes_by_id[sc] = []
            order.append(sc)
        scenes_by_id[sc].append((ix, cn, jp))
    if limit:
        order = order[:limit]

    p = Project(name=name)
    p.settings['video_mode'] = 3
    # **素材要先装上** ✗ 因为下面要靠文件名反查素材路径 ✓
    #（踩过：素材在循环之后才赋值 → _find_asset 永远找不到 → 图/语音都挂不上 ✓）
    p.assets = list(assets or [])
    p.characters = list(characters or [])
    p.scenes = []
    total_pages = 0
    total_chars = 0
    chars = set()

    for sc in order:
        items = sorted(scenes_by_id[sc])
        s = Scene(sc, 'story')
        # **轨道要先建齐** ✗
        # 片段是靠 track id 归类的 ✓ 没有对应轨道，编译器会**静默丢掉**那些片段 ✓
        #（踩过：只建了 text 轨道 → 导出清单 bg=0 audio=0 ✓ 图和语音全没进 ROM ✗）
        s.tracks = [Track('bg', 'bg', '背景'), Track('char_1', 'char1', '立绘'),
                    Track('text', 'text', '台词'), Track('voice', 'voice', '语音'),
                    Track('bgm', 'bgm', 'BGM'), Track('se', 'se', '音效')]
        clips = []
        t = 0.0
        for ix, raw, raw_jp in items:
            txt = clean_text(raw)
            if not txt:
                continue
            total_chars += len(txt)
            chars |= set(txt)
            # 真实调度（来自 .ws2）：这一句用哪张图、哪条语音、谁说的
            info = (scenes_map or {}).get(sc, {})
            # **优先用预合成图** ✗
            # 原作是"底图+立绘+蒙版"多层叠加 ✓ GBA 只有一层 ✗
            # 所以电脑上先把它们合成成一张 240x160（tools/compose_scenes.py ✓）
            # 这里直接取那张成品图 ✓ 找不到才退回裸底图 ✓
            # **按日文原文指纹查表** ✗
            # TSV 的"索引"是每场景从 0 开始 ✓ 而 ws2 的消息号是全局编号 ✗
            # 两边条目数也不一样 → 只能靠原文对齐 ✓
            tk = text_key(raw_jp)
            bg_file = ((comp_map or {}).get(sc) or {}).get(tk) \
                or (info.get('bg') or {}).get(tk)
            vo_file = (info.get('voice') or {}).get(tk)
            spk = (info.get('speaker') or {}).get(tk, '')
            for k, page in enumerate(paginate(txt, layout_text)):
                # 时长按字数估：每字 0.18 秒，最少 1.2 秒
                dur = max(1.2, len(page) * 0.18)
                # 分页后的**第一页**才挂说话人和语音（原作一句就是一页，几乎不会
                # 被我们切开；真被切开时语音只挂第一页更自然）
                props = {'text': page}
                if spk and k == 0:
                    props['speaker'] = spk
                clips.append(Clip('text', round(t, 2), round(dur, 2), 'text', '',
                                  props=props))
                if k == 0:
                    # 背景切换：和台词同一时刻，这样预览/实机就是"这句话配这张图"
                    if bg_file:
                        rel = _find_asset(p, bg_file)
                        if rel:
                            clips.append(Clip('bg', round(t, 2), round(dur, 2), 'bg', rel))
                    if vo_file:
                        rel = _find_asset(p, vo_file)
                        if rel:
                            clips.append(Clip('voice', round(t, 2), round(dur, 2),
                                              'voice', rel))
                t += dur
                total_pages += 1
        s.clips = clips
        s.duration = max(30.0, t + 1.0)
        p.scenes.append(s)

    # **背景要"持续"** ✗
    # ws2 里只在"切图那一刻"记录背景 ✓ 所以逐句挂会变成大量 1.2 秒的碎片 ✓
    # 中间没记录的行就成了"无背景"——预览/实机上会闪黑 ✓
    # 正确做法：一张图从它出现的那一刻**持续到下一张图出现** ✓
    for s in p.scenes:
        bgs = sorted([c for c in s.clips if c.track == 'bg'], key=lambda c: c.start)
        if not bgs:
            continue
        others = [c for c in s.clips if c.track != 'bg']
        for i, c in enumerate(bgs):
            nxt = bgs[i + 1].start if i + 1 < len(bgs) else s.duration
            c.dur = max(0.5, round(nxt - c.start, 2))
        # **相邻同一张图要合并** ✗
        # ws2 是逐句记背景的 ✓ 结果同一张图被切成几百段 ✓
        # 合并之后剧本里的 bg 命令少很多（ROM 里每条命令都要占字节 ✓）
        merged = []
        for c in bgs:
            if merged and merged[-1].ref == c.ref:
                merged[-1].dur = round(merged[-1].dur + c.dur, 2)
            else:
                merged.append(c)
        bgs = merged
        s.clips = others + bgs
        s.clips.sort(key=lambda c: (c.start, c.track))

    p.animations = []
    return p, {'scenes': len(order), 'pages': total_pages,
               'chars': total_chars, 'unique': len(chars)}


def fill_scene_assets(proj, per_scene_bg=1, voices_per_scene=4, use_bgm=True):
    """**演示填充**：把工程里的素材轮着挂到场景上

    为什么需要它 ✗
    编译器只打包**被片段引用**的素材 ✓ 而纯文字工程不引用任何图/音 ✓
    所以想量"整部作品 + 素材"到底多大，就得先把素材挂上去 ✓

    ⚠ 这是**合成**的挂法（背景轮着用、语音顺序贴）✓ 不是原作的真实调度 ✓
    真实调度在 .ws2 字节码里 ✓ 需要操作码表才能自动补上 ✓
    这个函数的意义是：**先把容量账量准** ✓
    """
    bgs = [a.path for a in proj.assets if a.kind == 'bg']
    chars = [c.id for c in proj.characters]
    voices = [a.path for a in proj.assets if a.kind == 'voice']
    bgms = [a.path for a in proj.assets if a.kind == 'bgm']
    se = [a.path for a in proj.assets if a.kind == 'se']

    vi, si = 0, 0
    for n, sc in enumerate(proj.scenes):
        extra = []
        if bgs:
            for k in range(per_scene_bg):
                rel = bgs[(n * per_scene_bg + k) % len(bgs)]
                extra.append(Clip('bg', 0.0, max(30.0, sc.duration),
                                  'bg', rel))
        if chars and n % 2 == 0:
            extra.append(Clip('char_1', 0.5, max(20.0, sc.duration - 1),
                              'char1', chars[n % len(chars)]))
        if use_bgm and bgms:
            extra.append(Clip('bgm', 0.0, max(30.0, sc.duration), 'bgm',
                              bgms[n % len(bgms)]))
        # 语音：每个场景前几页挂几条
        if voices:
            texts = [c for c in sc.clips if c.track == 'text'][:voices_per_scene]
            for c in texts:
                extra.append(Clip('voice', c.start, c.dur, 'voice',
                                  voices[vi % len(voices)]))
                vi += 1
        if se and n % 3 == 0:
            extra.append(Clip('se', 1.0, 2.0, 'se', se[si % len(se)]))
            si += 1
        # 轨道要存在，片段才能被识别
        have = {tr.id for tr in sc.tracks}
        for tid, kind, nm in (('bg', 'bg', '背景'), ('char_1', 'char1', '立绘'),
                              ('bgm', 'bgm', 'BGM'), ('voice', 'voice', '语音'),
                              ('se', 'se', '音效')):
            if tid not in have:
                sc.tracks.append(Track(tid, kind, nm))
        sc.clips = extra + sc.clips
    return proj


def main():
    ap = argparse.ArgumentParser(description='把解包的剧本 TSV 转成 GBAStudio 工程')
    ap.add_argument('--tsv', required=True, help='台词对照_JP_CN.tsv 的路径')
    ap.add_argument('--out', required=True, help='输出目录')
    ap.add_argument('--name', default='移植剧本', help='工程名（也是子目录名）')
    ap.add_argument('--names', default='', help='NameTable.txt 路径（可选）')
    ap.add_argument('--limit', type=int, default=0, help='只转前 N 个场景（试跑用）')
    ap.add_argument('--max-lines', type=int, default=0,
                    help='只转前 N 句台词（做小工程试玩用）。'
                         '按原作的顺序取前 N 句，跨场景连续')
    ap.add_argument('--keep-assets', action='store_true',
                    help='保留目标工程里已有的素材和角色表（第二次转、补调度时用）')
    ap.add_argument('--composite-map', default='',
                    help='compose_scenes.py 产出的"每句用图表"'
                         '——给了它就用预合成的一层成品图（GBA 只有一层背景）')
    ap.add_argument('--scenes-json', default='',
                    help='ws2_scenes.py 产出的调度表（背景/语音/说话人）'
                         '——给了它就是**真实调度**，不给就是纯文字')
    ap.add_argument('--chapter', default='',
                    help='只转某一章（如 s0 / s1 / s2）。'
                         '分章的意义：32MB 是**每盘卡带**的限制 ✗ 分成几章就能做几盘 ✓')
    ap.add_argument('--fill', action='store_true',
                    help='演示填充：把素材轮着挂到场景上（只为量容量，不是真实调度）')
    ap.add_argument('--scenario-only', action='store_true',
                    help='只输出 scenario.txt，不建工程（给引擎直接用）')
    a = ap.parse_args()

    if not os.path.isfile(a.tsv):
        log('✗ 找不到 %s' % a.tsv)
        return 1

    rows = read_tsv(a.tsv)
    if a.chapter:
        # 场景名形如 s0_01 ✓ 取 s 后面的数字当章节号 ✓
        want = a.chapter.lower().lstrip('s')
        rows = [r for r in rows if re.match(r's%s_' % want, r[0], re.I)]
        log('只取第 %s 章：%d 行台词' % (want, len(rows)))
    if a.max_lines and len(rows) > a.max_lines:
        # 只取前 N 句：保持原作顺序（TSV 本来就是按场景/行号排好的）
        rows = rows[:a.max_lines]
        log('只取前 %d 句台词' % a.max_lines)
    log('读入 %d 行台词' % len(rows))
    if not rows:
        log('✗ 一行都没读到，检查一下 TSV 的列名/编码')
        return 1
    names = read_names(a.names) if a.names and os.path.isfile(a.names) else {}
    if names:
        log('人名表 %d 条（仅用于补说话人，补不上不影响文字）' % len(names))

    scenes_map = None
    if a.scenes_json and os.path.isfile(a.scenes_json):
        with open(a.scenes_json, encoding='utf-8') as f:
            scenes_map = json.load(f)
        log('真实调度表：%d 个场景（背景/语音/说话人都会按原作挂上）'
            % len(scenes_map))
    elif a.scenes_json:
        log('⚠ 找不到调度表 %s，按纯文字转' % a.scenes_json)
    # **保留已收的素材** ✗
    # 流程是：先转一次（建工程）→ 收素材 → 再转一次（用真实调度挂图/语音）
    # 第二次要能按文件名找到素材 ✓ 所以先把上一轮的素材读进来 ✓
    keep_a, keep_c = [], []
    tgt_dir = os.path.join(a.out, a.name)
    tgt = os.path.join(tgt_dir, a.name + '.gbastudio')
    if a.keep_assets and os.path.isfile(tgt):
        try:
            old_p = Project.load(tgt)
            keep_a, keep_c = old_p.assets, old_p.characters
            log('保留了工程里已有的 %d 个素材、%d 个角色'
                % (len(keep_a), len(keep_c)))
        except Exception as e:                          # noqa: BLE001
            log('⚠ 读取已有工程失败（%s），当作新工程' % e)

    # 预合成图：把用到的那些登记成 bg 素材（文件已经在 assets/bg 下了）
    comp_map = None
    if a.composite_map and os.path.isfile(a.composite_map):
        comp_map = json.load(open(a.composite_map, encoding='utf-8'))
        tgt_dir0 = os.path.join(a.out, a.name)
        used = set()
        for per in comp_map.values():
            for rel in per.values():
                if rel:
                    used.add(rel)
        for rel in sorted(used):
            q = os.path.join(tgt_dir0, rel.replace('/', os.sep))
            if os.path.isfile(q) and not any(x.path == rel for x in keep_a):
                keep_a.append(Asset('bg', rel, '预合成'))
        log('预合成图：%d 张登记为背景素材（多层已合成成一层）' % len(used))
    elif a.composite_map:
        log('⚠ 找不到预合成表 %s' % a.composite_map)

    proj, st = build_project(rows, a.name, a.limit, scenes_map,
                             assets=keep_a, characters=keep_c, comp_map=comp_map)
    if a.fill:
        # 素材必须先收进工程（tools/collect_assets.py）
        if not proj.assets:
            log('⚠ 工程里还没有素材，--fill 无从下手。先跑：')
            log('   python tools\\collect_assets.py --src "<解包目录>" --project "<工程>"')
        else:
            fill_scene_assets(proj)
            import collections as _c
            log('演示填充：%s' % dict(_c.Counter(
                c.track for s in proj.scenes for c in s.clips)))
    log('场景 %d 个；分页后 %d 页；中文 %d 字（%d 个不同字）'
        % (st['scenes'], st['pages'], st['chars'], st['unique']))
    if a.limit:
        log('（--limit %d：只转了前 %d 个场景）' % (a.limit, st['scenes']))

    # 字库需求：引擎 11x11 点阵 1bpp ≈ 每字 25 字节（含表）
    kb = st['unique'] * 25 / 1024.0
    log('字库需求：%d 个不同字 ≈ %.0f KB（引擎的字库是自动生成的 ✓）'
        % (st['unique'], kb))
    log('文本需求：约 %.0f KB（按每字 2 字节算）' % (st['chars'] * 2 / 1024.0))

    if a.scenario_only:
        from core import compiler
        pd = os.path.join(a.out, a.name)
        os.makedirs(pd, exist_ok=True)
        # 临时保存一下，让编译器能解析相对路径（这个工程没有外部素材）
        tmp = os.path.join(pd, a.name + '.gbastudio')
        proj.path = tmp
        proj.save(tmp)
        text, notes, mani = compiler.compile_project(proj, pd, log=lambda m: None)
        out = os.path.join(a.out, 'scenario.txt')
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        log('已写出 %s（%d 行）' % (out, len(text.splitlines())))
        for n in notes[:3]:
            log('  提示：%s' % n)
        return 0

    pd = As.ensure_dirs(os.path.join(a.out, a.name))
    path = os.path.join(a.out, a.name, a.name + '.gbastudio')
    proj.path = path
    proj.save(path)
    log('工程已写出：%s' % path)
    log('   在编辑器里打开它就能改台词、加立绘/语音/背景 ✓')
    log('   导出后会自动生成字库（只用剧本里出现过的字）✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
