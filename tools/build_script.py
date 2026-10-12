#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_script.py —— 把纯文本剧本编译成 C 命令数组

【为什么要有这一层】
    移植 PC galgame 时，剧本动辄几万字，直接写进 C 代码没法维护，而且
    GBA 上没法解析文本（没有文件系统、RAM 只有 288KB）。
    正确做法是：**在 PC 上把剧本编译成紧凑的二进制命令表**，GBA 只负责顺序执行。

    顺便它还能自动收集"剧本里出现过的所有汉字"，交给字库生成器 ——
    这是中文 GBA 游戏最关键的一步：字库必须按需生成，不可能塞下整个中文字库
    （完整 CJK 字库 2 万多个字，10x10 点阵也要 400KB 以上，而且绝大多数用不到）。

【输入】scenario/scenario.txt     （格式说明见文件头注释）
【输出】
    source/assets/scenario.c        命令数组 + 字符串表
    include/scenario.h              命令枚举与结构体定义
    source/assets/scenario_charset.txt   剧本里用到的全部字符（给字库生成器）

用法：
    <bundled-python> tools/build_script.py
"""
import os
import re
import sys

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_TXT  = os.path.join(ROOT, 'scenario', 'scenario.txt')
OUT_C    = os.path.join(ROOT, 'source', 'assets', 'scenario.c')
OUT_H    = os.path.join(ROOT, 'include', 'scenario.h')
OUT_CHAR = os.path.join(ROOT, 'source', 'assets', 'scenario_charset.txt')

BG_IDS   = {'bg_title': 0, 'bg_ocean': 1}
CHAR_IDS = {'witch': 0, 'girl': 1}
POS_IDS  = {'left': 0, 'center': 1, 'right': 2}

OPS = ['CMD_END', 'CMD_BG', 'CMD_CHAR', 'CMD_HIDE', 'CMD_SAY', 'CMD_CHOICE', 'CMD_JUMP',
       'CMD_VOICE', 'CMD_BGM', 'CMD_BGM_STOP', 'CMD_SE', 'CMD_MODE']


def log(m):
    print('[script] ' + m)


def die(msg, line_no=None):
    where = f'第 {line_no} 行: ' if line_no else ''
    print(f'[script] 错误: {where}{msg}', file=sys.stderr)
    sys.exit(1)


def c_escape(s):
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        else:
            out.append(ch)
    return ''.join(out)


class Cmd:
    __slots__ = ('op', 'a', 'b', 's1', 's2', 't1', 't2', 'line')

    def __init__(self, op, a=0, b=0, s1='', s2='', t1=0, t2=0, line=0):
        self.op, self.a, self.b = op, a, b
        self.s1, self.s2 = s1, s2
        self.t1, self.t2 = t1, t2
        self.line = line


def parse(path):
    cmds = []
    labels = {}
    pending = []          # (cmd_index, 标签名, 目标字段序号)
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    for i, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        head, _, rest = line.partition(' ')
        head, rest = head.strip(), rest.strip()

        # 标签有两种写法： @名字   或   label 名字
        if head.startswith('@'):
            name = head[1:].strip()
            if not name:
                die('@ 后面要跟标签名', i)
            labels[name] = len(cmds)
            continue

        if head == 'label':
            if not rest:
                die('label 后面要跟标签名', i)
            labels[rest] = len(cmds)

        elif head == 'jump':
            cmds.append(Cmd('CMD_JUMP', line=i))
            pending.append((len(cmds) - 1, rest, 1))

        elif head == 'bg':
            # P5 起收**下标**（编辑器写出的就是数字，后面可能跟 "# 背景名" 注释）；
            # 手写剧本仍可写旧名字（bg_ocean 之类），这里兼容两种情况
            tok = rest.split()[0] if rest.split() else ''
            if tok.lstrip('-').isdigit():
                cmds.append(Cmd('CMD_BG', a=int(tok), line=i))
            elif tok in BG_IDS:
                cmds.append(Cmd('CMD_BG', a=BG_IDS[tok], line=i))
            else:
                die(f'背景要写下标数字（编辑器的输出），或旧名字 {", ".join(BG_IDS)}；'
                    f'收到 "{rest}"', i)

        elif head == 'char':
            parts = rest.split()
            if len(parts) < 2:
                die('char 用法: char <left|center|right|0|1|2> <立绘下标>', i)
            pos = int(parts[0]) if parts[0].lstrip('-').isdigit() else POS_IDS.get(parts[0])
            if pos is None:
                die(f'位置只能是 left/center/right 或 0/1/2，收到 "{parts[0]}"', i)
            if parts[1].lstrip('-').isdigit():
                ch = int(parts[1])
            elif parts[1] in CHAR_IDS:
                ch = CHAR_IDS[parts[1]]
            else:
                die(f'立绘要写下标数字（编辑器的输出），或旧名字 {", ".join(CHAR_IDS)}；'
                    f'收到 "{parts[1]}"', i)
            cmds.append(Cmd('CMD_CHAR', a=pos, b=ch, line=i))

        elif head == 'hide':
            tok = rest.split()[0] if rest.split() else ''
            pos = int(tok) if tok.lstrip('-').isdigit() else POS_IDS.get(tok)
            if pos is None:
                die('hide 用法: hide <left|center|right|0|1|2>', i)
            cmds.append(Cmd('CMD_HIDE', a=pos, line=i))

        elif head == 'voice':
            tok = rest.split()[0] if rest.split() else ''
            if not tok.lstrip('-').isdigit():
                die('voice 用法: voice <音频下标>', i)
            cmds.append(Cmd('CMD_VOICE', a=int(tok), line=i))

        elif head == 'bgm':
            parts = rest.split()
            if not parts or not parts[0].lstrip('-').isdigit():
                die('bgm 用法: bgm <音频下标> [loop|once]', i)
            loop = 1
            if len(parts) > 1:
                loop = 0 if parts[1] in ('once', '0', 'no') else 1
            cmds.append(Cmd('CMD_BGM', a=int(parts[0]), b=loop, line=i))

        elif head in ('bgm_stop', 'bgmstop'):
            cmds.append(Cmd('CMD_BGM_STOP', line=i))

        elif head == 'se':
            tok = rest.split()[0] if rest.split() else ''
            if not tok.lstrip('-').isdigit():
                die('se 用法: se <音频下标>', i)
            cmds.append(Cmd('CMD_SE', a=int(tok), line=i))

        elif head == 'mode':
            # mode <玩法编号>：0=剧情 1=关卡（见 scenario.h 的 GameMode）。
            # 剧情演到这里切进关卡；关卡退出后**回到下一句继续演**。
            tok = rest.split()[0] if rest.split() else ''
            if not tok.isdigit():
                die('mode 用法: mode <玩法编号>（0=剧情 1=关卡）', i)
            cmds.append(Cmd('CMD_MODE', a=int(tok), line=i))

        elif head == 'say':
            name, sep, text = rest.partition('|')
            if not sep:
                die('say 用法: say 名字|台词    （旁白写成  say |台词）', i)
            cmds.append(Cmd('CMD_SAY', s1=name.strip(), s2=text.strip(), line=i))

        elif head == 'choice':
            opts = [o.strip() for o in rest.split('|') if o.strip()]
            if len(opts) != 2:
                die('choice 必须正好两个选项，用 | 分隔', i)
            texts, targets = [], []
            for o in opts:
                t, arrow, lab = o.partition('->')
                if not arrow:
                    die(f'选项 "{o}" 缺少 ->目标标签', i)
                texts.append(t.strip())
                targets.append(lab.strip())
            cmds.append(Cmd('CMD_CHOICE', s1=texts[0], s2=texts[1], line=i))
            pending.append((len(cmds) - 1, targets[0], 1))
            pending.append((len(cmds) - 1, targets[1], 2))

        elif head == 'end':
            cmds.append(Cmd('CMD_END', line=i))

        else:
            die(f'未知指令 "{head}"', i)

    # 第二遍：把标签名解析成命令下标
    for idx, lab, slot in pending:
        if lab not in labels:
            die(f'找不到标签 "{lab}"（被 {cmds[idx].line} 行引用）')
        if slot == 1:
            cmds[idx].t1 = labels[lab]
        else:
            cmds[idx].t2 = labels[lab]

    cmds.append(Cmd('CMD_END', line=0))   # 兜底，防止越界
    return cmds, labels


def write_c(cmds):
    os.makedirs(os.path.dirname(OUT_C), exist_ok=True)
    # 字符串池：每条命令的文本单独一个 static 数组
    str_defs, str_names = [], []
    for n, c in enumerate(cmds):
        for field, val in (('s1', c.s1), ('s2', c.s2)):
            if val == '':
                str_names.append('s_empty')
                continue
            name = f's_{n}_{field}'
            str_defs.append(f'static const char {name}[] = "{c_escape(val)}";')
            str_names.append(name)

    lines = [
        '/* 由 tools/build_script.py 从 scenario/scenario.txt 自动生成，请勿手工修改。',
        ' * 改剧情请改 scenario/scenario.txt 再重新生成。 */',
        '#include "scenario.h"',
        '',
        'static const char s_empty[] = "";',
    ]
    lines += str_defs
    lines.append('')
    lines.append('const ScCmd scenario[] = {')
    for n, c in enumerate(cmds):
        s1 = str_names[n * 2]
        s2 = str_names[n * 2 + 1]
        lines.append(f'    {{ {c.op}, {c.a}, {c.b}, 0, {s1}, {s2}, {c.t1}, {c.t2} }},   /* 行 {c.line} */')
    lines.append('};')
    lines.append('')
    lines.append(f'const int scenario_count = {len(cmds)};')
    lines.append('')
    with open(OUT_C, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    log(f'{os.path.relpath(OUT_C, ROOT)}  {len(cmds)} 条命令，{len(str_defs)} 条字符串')


def write_h():
    h = f"""/* 由 tools/build_script.py 自动生成，请勿手工修改 */
#ifndef SCENARIO_H
#define SCENARIO_H

#include <tonc.h>

/* 命令类型 */
typedef enum {{
    {', '.join(OPS)}
}} ScOp;

/* 玩法编号（CMD_MODE 的 a）—— 剧本里写 `mode 1` 就是切到关卡 */
typedef enum {{
    MODE_VN    = 0,     /* 视觉小说 */
    MODE_LEVEL = 1,     /* 关卡 */
    MODE_N     = 2,
}} GameMode;

/* 背景编号 = gfx_bgs[] 的下标（由 make_project_assets.py 按项目素材生成） */
/* 人物编号 = gfx_sprites[] 的下标（角色+表情在编译时展平成一维表） */
/* 立绘位置：左 / 中 / 右 */
typedef enum {{ SC_POS_LEFT = 0, SC_POS_CENTER = 1, SC_POS_RIGHT = 2, SC_POS_N = 3 }} ScPos;

/* 一条剧本命令。
 *   CMD_BG     a=背景下标（gfx_bgs）
 *   CMD_CHAR   a=位置(ScPos)  b=立绘下标（gfx_sprites）
 *   CMD_HIDE   a=位置
 *   CMD_SAY    s1=说话人（空串=旁白）  s2=台词
 *   CMD_CHOICE s1/s2=两个选项文本      t1/t2=各自的跳转目标
 *   CMD_JUMP   t1=目标下标
 *   CMD_VOICE  a=音频下标（走 Direct Sound A，一次播完）
 *   CMD_BGM    a=音频下标  b=是否循环（走 B）
 *   CMD_BGM_STOP 停止 BGM
 *   CMD_SE     a=音频下标（抢占 B，播完自动把 BGM 接回去）
 *   CMD_MODE   a=玩法编号（GameMode）—— 剧情演到这里切成关卡，
 *              关卡退出后**回到剧本的下一句继续**
 *   CMD_END    结束，回标题 */
typedef struct {{
    u8  op;
    u8  a;
    u8  b;
    u8  pad;
    const char *s1;
    const char *s2;
    u16 t1;
    u16 t2;
}} ScCmd;

extern const ScCmd scenario[];
extern const int scenario_count;

#endif /* SCENARIO_H */
"""
    with open(OUT_H, 'w', encoding='utf-8', newline='\n') as f:
        f.write(h)
    log(f'{os.path.relpath(OUT_H, ROOT)}')


def write_charset(cmds):
    chars = set()
    for c in cmds:
        for s in (c.s1, c.s2):
            for ch in s:
                if ord(ch) > 0x7E:      # ASCII 由字库工具统一补齐
                    chars.add(ch)
    os.makedirs(os.path.dirname(OUT_CHAR), exist_ok=True)
    with open(OUT_CHAR, 'w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(sorted(chars)))
    log(f'{os.path.relpath(OUT_CHAR, ROOT)}  {len(chars)} 个非 ASCII 字符')
    return chars


def main():
    if not os.path.exists(SRC_TXT):
        die(f'找不到剧本文件 {SRC_TXT}')
    cmds, labels = parse(SRC_TXT)
    write_c(cmds)
    write_h()
    write_charset(cmds)
    log(f'标签: {", ".join(labels)}')


if __name__ == '__main__':
    main()
