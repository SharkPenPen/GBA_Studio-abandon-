#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws2_scenes.py —— 从 .ws2 字节码里提取"哪一句用哪张图、放哪条语音"

【为什么需要它】
剧本转换（tsv_to_project.py）只拿到**文字** ✗
"切哪张背景、显哪个立绘、放哪条语音"在 `.ws2` 字节码里 ✓
没有它，工程里的画面和语音只能是**合成的占位** ✓

【怎么做到的】
直接复用用户自己写的反汇编器 ✗（D:\\GitHud\\3DSStudio\\tools\\ws2_disasm.py ✓）
它是照着 pkuislm/ws2Parse + CLegacyFunctions.cs 写的 ✓
操作码的**完整参数表**从那份 C# 里读出来（249 条指令 ✓）
解密是 `rot_right2`（循环右移 2 位 ✓ 不是减法也不是异或 ✓）

反汇编出来的指令长这样（s0_01 的真实片段）：

    (51, ['bg01', 'BGBLACK.PNG', 1, 1])     设图层图片 —— bg01 是背景 ★
    (51, ['ev01', 'EV301_001M.PNG', 1, 1])  事件 CG / 立绘 ★
    (70, ['bg01', 0, 0, x, y, ...])         图层位置/缩放
    (101, [0, 0, 0.5, 0.0, 2, ''])          淡入 / 转场
    (21, ['%LF刹那', 0])                    说话人 ★
    (20, [index, 'char', '...', 0])         消息 —— **index 和 TSV 的行号完全对应** ★★
    (40, ['charSET', 'SET0040.OGG', ...])   语音文件 ★
    (30, ['bgm01', 'NSBGM02.OGG', ...])     BGM
    (7,  ['S0_03'])                         跳到下一场景

所以只要**顺序扫一遍** ✗ 边走边记"当前背景是谁、当前立绘是谁" ✓
遇到 `20`（消息）就把当时的状态记下来 ✓ 遇到 `40` 就记住这条消息的语音 ✓
得到的就是**真实的调度表** ✓✓

【输出】
{
  "s0_01": {
    "bg": {"0": "EV301_001M.PNG", "10": "EV301_002L.PNG", ...},
    "voice": {"5": "SET0040.OGG", "6": "YUU0032.OGG", ...},
    "speaker": {"5": "刹那", "6": "悠果", ...},
    "jump": "S0_03"
  }, ...
}

【注意】
素材来自一部 18+ 作品 ✗ 本工具只提取**文件名与编号** ✓
不输出、不解析任何台词内容 ✓
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_3DS = r'D:\GitHud\3DSStudio\tools'
DEFAULT_RIO = r'D:\游戏解包\Nightmare×sisters～淫狱的献祭～\剧本\Rio'
DEFAULT_NAMES = r'D:\游戏解包\Nightmare×sisters～淫狱的献祭～\剧本\Rio_zhCN\NameTable.txt'

# 指令号（从反汇编输出里实测出来的）
OP_SET_LAYER = 51      # 设图层图片：['层名', '文件名', ...]
OP_LAYER_POS = 70      # 图层位置
OP_FADE = 101          # 淡入/转场
OP_SPEAKER = 21        # 说话人：['%LF名字', 0]
OP_MESSAGE = 20        # 消息：[index, 'char'|..., '文本', 0]
OP_VOICE = 40          # 语音：['charSET', 'SET0040.OGG', ...]
OP_BGM = 30            # BGM：['bgm01', 'NSBGM02.OGG', ...]
OP_JUMP = 7            # 跳转：['S0_03']

# 图层名 → 用途（实测：bg01 是底图、ev01 是整屏 CG、st/char 是立绘）
RE_BG_LAYER = re.compile(r'^(bg|ev|bgm?_)', re.I)
RE_CHAR_LAYER = re.compile(r'^(st|char|cs)', re.I)
# 这些是特效遮罩，GBA 用不上
RE_SKIP_FILE = re.compile(r'^(efmsk_|layermask_|est_)', re.I)


def text_key(s):
    """日文原文的指纹（只存哈希，不存原文）

    **为什么必须靠它对齐** ✗
    TSV 的"索引"是**每个场景从 0 开始**的 ✓
    而 .ws2 里的消息号是**全局编号**（s1_01 是 99..196）✗
    两边条目数还不一样（127 vs 98）→ 按编号、按顺序都对不上 ✓
    但两边的**日文原文是同一句话** ✓ 所以拿原文做指纹最可靠 ✓
    （顺带也修好了语音/说话人的对齐 —— 它们原来对 s0 以外的场景全是错的 ✗）
    """
    import hashlib
    import re as _re
    if s is None:
        return ''
    x = str(s)
    # 去掉 TSV 那边的 char「」包装和控制码，只留纯文本
    x = _re.sub(r'^[A-Za-z_]+', '', x)
    x = x.replace('「', '').replace('」', '')
    x = _re.sub(r'%[A-Za-z0-9]{1,2}', '', x)
    x = x.replace('\\n', '').replace('\n', '')
    x = _re.sub(r'[\s\u3000]+', '', x)
    return hashlib.md5(x.encode('utf-8')).hexdigest()[:16]


def log(m):
    print('[ws2] ' + m)


def load_disasm():
    """加载用户自己的反汇编器"""
    if TOOLS_3DS not in sys.path:
        sys.path.insert(0, TOOLS_3DS)
    import ws2_disasm as W
    return W


def read_names(path):
    """NameTable（UTF-16LE，日文名/中文名成对）→ {日文: 中文}

    ⚠ 只做"尽力而为"的提取：切出连续的假名/汉字片段，相邻两个配一对 ✓
    配不上就不加说话人 ✓（不影响文字本身 ✓）
    """
    if not path or not os.path.isfile(path):
        return {}
    try:
        raw = open(path, 'rb').read().decode('utf-16-le', 'ignore')
    except Exception:
        return {}
    s = ''.join(ch for ch in raw if ch.isprintable() and ch not in '%·')
    names = re.findall(r'[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9]{1,12}', s)
    out = {}
    for i in range(0, len(names) - 1, 2):
        jp, cn = names[i], names[i + 1]
        if re.search(r'[\u4e00-\u9fff]', cn):
            out[jp] = cn
    return out


def extract_one(W, table, path, enc='shift_jis'):
    """反汇编一个 .ws2 → 调度表"""
    raw = open(path, 'rb').read()
    data = bytes(W.rot_right2(b) for b in raw)
    segs, pos, tail = W.parse_script(data, table, enc)
    if not segs:
        return None

    # 段是嵌套的 list（主流程 + 各函数体）✓ 这里只扫主流程 ✓
    main = segs[0][0]
    layers = {}          # 层名 → 文件名
    out = {'bg': {}, 'char': {}, 'voice': {}, 'bgm': {}, 'speaker': {},
           'jump': '', 'msgs': 0}
    cur_bgm = None
    for item in main:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        op, args = item
        if not isinstance(args, list) or not args:
            continue
        try:
            if op == OP_SET_LAYER and len(args) >= 2:
                layer, fname = str(args[0]), str(args[1])
                if RE_SKIP_FILE.match(fname):
                    continue
                layers[layer] = fname
            elif op == OP_MESSAGE:
                ix = args[0]
                if not isinstance(ix, int) or len(args) < 3:
                    continue
                out['msgs'] += 1
                ix = text_key(args[2])          # **用原文指纹当键** ✗ 不用消息号 ✓
                # 记下这一刻的背景 / 立绘
                base = None
                for ln, fn in layers.items():
                    if RE_BG_LAYER.match(ln):
                        base = fn
                chars = [fn for ln, fn in layers.items() if RE_CHAR_LAYER.match(ln)]
                if base:
                    out['bg'][str(ix)] = base
                if chars:
                    out['char'][str(ix)] = sorted(set(chars))
            elif op == OP_SPEAKER and args:
                nm = str(args[0]).replace('%LF', '').strip()
                if nm:
                    out['_pending_speaker'] = nm
            elif op == OP_VOICE and len(args) >= 2:
                f = str(args[1])
                # 语音属于**下一条消息** ✓（实测：40 在 20 前面 ✓）
                out['_pending_voice'] = f
            elif op == OP_BGM and len(args) >= 2:
                cur_bgm = str(args[1])
            elif op == OP_JUMP and args:
                j = str(args[0])
                if not out['jump']:
                    out['jump'] = j
        except Exception:
            continue

    # 再把 pending 的说话人/语音按"紧随其后的那条消息"落位
    cur_bgm = None
    pend_sp = pend_vo = None
    for item in main:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        op, args = item
        if not isinstance(args, list) or not args:
            continue
        if op == OP_SPEAKER:
            pend_sp = str(args[0]).replace('%LF', '').strip() or None
        elif op == OP_VOICE and len(args) >= 2:
            pend_vo = str(args[1])
        elif op == OP_MESSAGE and isinstance(args[0], int) and len(args) >= 3:
            ix = text_key(args[2])
            if pend_sp:
                out['speaker'][ix] = pend_sp
            if pend_vo:
                out['voice'][ix] = pend_vo
            if cur_bgm:
                out['bgm'][ix] = cur_bgm
            pend_sp = pend_vo = None
        elif op == OP_BGM and len(args) >= 2:
            cur_bgm = str(args[1])
    out.pop('_pending_speaker', None)
    out.pop('_pending_voice', None)
    return out


def main():
    ap = argparse.ArgumentParser(description='从 .ws2 提取场景调度（背景/立绘/语音/说话人）')
    ap.add_argument('--rio', default=DEFAULT_RIO, help='.ws2 所在目录')
    ap.add_argument('--names', default=DEFAULT_NAMES, help='NameTable.txt')
    ap.add_argument('--out', default=os.path.join(ROOT, '.tmp', 'ws2_scenes.json'))
    ap.add_argument('--only', default='', help='只处理这些场景（逗号分隔，如 s0_01,s1_01）')
    a = ap.parse_args()

    if not os.path.isdir(a.rio):
        log('✗ 找不到 .ws2 目录：%s' % a.rio)
        return 1
    W = load_disasm()
    table = W.parse_tables()
    log('操作码参数表：%d 条指令' % len(table))

    names = read_names(a.names)
    if names:
        log('人名表 %d 条' % len(names))

    want = set(x.strip() for x in a.only.split(',') if x.strip())
    files = sorted(f for f in os.listdir(a.rio) if f.lower().endswith('.ws2'))
    if want:
        files = [f for f in files if os.path.splitext(f)[0] in want]
    log('要处理 %d 个 .ws2' % len(files))

    result = {}
    ok = fail = 0
    tot_msg = tot_bg = tot_vo = tot_sp = 0
    for f in files:
        sc = os.path.splitext(f)[0]
        try:
            r = extract_one(W, table, os.path.join(a.rio, f))
        except Exception as e:                          # noqa: BLE001
            r = None
            log('  ✗ %s 解析失败：%s' % (sc, e))
        if not r:
            fail += 1
            continue
        ok += 1
        # 说话人译成中文（人名表是日文→中文成对）
        for ix, jp in list(r['speaker'].items()):
            if jp in names:
                r['speaker'][ix] = names[jp]
        result[sc] = r
        tot_msg += r['msgs']
        tot_bg += len(r['bg'])
        tot_vo += len(r['voice'])
        tot_sp += len(r['speaker'])

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)

    log('')
    log('解析成功 %d 个，失败 %d 个' % (ok, fail))
    log('消息 %d 条；带背景 %d 条；带语音 %d 条；带说话人 %d 条'
        % (tot_msg, tot_bg, tot_vo, tot_sp))
    log('已写出 %s' % a.out)
    # 抽一个场景给个直观例子（只报文件名/编号，不打印文本）
    if result:
        sc = 's0_01' if 's0_01' in result else sorted(result)[0]
        r = result[sc]
        log('')
        log('例子 %s：消息 %d 条，背景 %d 处，语音 %d 条，说话人 %d 个，跳转 %r'
            % (sc, r['msgs'], len(r['bg']), len(r['voice']), len(r['speaker']),
               r['jump']))
        bgs = sorted(set(r['bg'].values()))
        log('  用到的背景/CG：%d 张，例如 %s' % (len(bgs), bgs[:4]))
        spk = sorted(set(r['speaker'].values()))
        if spk:
            log('  说话人：%s' % spk[:6])
    return 0


if __name__ == '__main__':
    sys.exit(main())
