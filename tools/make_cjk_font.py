#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_cjk_font.py —— 生成中文点阵字库（GBA 用）

【为什么必须自己生成】
    GBA 没有任何中文字库，也没有文件系统。完整 CJK 字库有两万多个字，
    点阵也要几百 KB，而且 99% 用不到。
    正确做法：**只把"这个游戏里真正会出现的字"做成点阵**。
    本工程的字符来源有三个，自动合并：
      1. source/assets/scenario_charset.txt   剧本里出现过的字（build_script.py 产出）
      2. source/**.c 里字符串字面量中的非 ASCII 字符（UI 文字，比如"开始游戏"）
         —— 扫描前会先剥掉注释，否则注释里的中文会被误当成 UI 文字塞进字库
      3. ASCII 可打印字符 0x20~0x7E
    这样永远不会漏字 —— 漏字的后果是屏幕上出现空白，很难查。

【字体与字号的选择（实测结论）】
    默认：**中易宋体 SimSun，源字号 12px → 输出 11x11**。

    这里有个反直觉的关键点，值得记住：
    宋体只在 **12px（9 号）** 这一档**内嵌点阵字形**（Windows 上经典的
    "宋体 12px 点阵"），FreeType 会直接取这套手工调过的点阵，笔画锐利。
    判据：渲染结果的**灰度级只有 2 个**（纯黑白）；其它字号是上百个灰度级
    （轮廓线缩放 + 抗锯齿），小字号下会糊、会断。

    实测（同一句话的平均亮点数）：
        simsun 12px 内嵌点阵          ✅ 40.4 亮点，灰度级 2
        simsun 12px 点阵缩放到 11px   ✅ 36.4 亮点 —— 仍然锐利，推荐
        simsun 11px 轮廓(阈值100)     ❌ 18.9 亮点，9/18 个字笔画断裂
        simsun 11px 轮廓(阈值70)      ❌ 25.6 亮点，笔画细且脏
        simhei 10px 轮廓              ⚠ 30.9 亮点，笔画粘连、复杂字糊成块

    所以"想更小"的正确做法不是"把字号调小"，而是
    **渲染 12px 命中点阵 → 再用面积平均缩放到目标尺寸**。
    这样缩小的是手工点阵，不是缩放轮廓线，质量差别很大。

    参数：--strike 源字号（默认 12，必须是命中点阵的那一档）
          --size   输出格子尺寸（默认 11）

【半角 ASCII】
    宋体的 ASCII 步进是汉字的一半（12px 时 6px，11px 输出时 5px）。
    字库里每个字形仍然占 size x size 的格子（保持定长、便于二分查找），
    但 C 侧对 ASCII 只推进一半宽度，于是同一个格子里能塞下两个字 ——
    文本里的 "GBA" 才不会被撑成全角宽度。
    极少数超宽字母（m、W 之类）墨迹会超出半角宽度，脚本会把它们整体左移。

【点阵格式】每个字 size 行，每行一个 u16，**最高位是最左边的像素**（bit15 = x0）。
    字库按码点升序排列，C 侧用二分查找。

【产物】
    source/assets/font_glyphs.bin    点阵数据
    source/assets/font_index.bin     码点表（升序 u32）
    source/assets/font_data.s        汇编存根
    include/font_data.h              尺寸与声明
    .tmp/font_preview.png            实际点阵渲染预览（人工检查）

用法：
    <bundled-python> tools/make_cjk_font.py
    <bundled-python> tools/make_cjk_font.py --size 12        # 不缩放，直接用 12px 点阵
    <bundled-python> tools/make_cjk_font.py --font C:\\Windows\\Fonts\\simhei.ttf --strike 16
"""
import os
import re
import sys
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, 'source', 'assets')
INC_DIR   = os.path.join(ROOT, 'include')
TMP_DIR   = os.path.join(ROOT, '.tmp')
CHARSET   = os.path.join(ASSET_DIR, 'scenario_charset.txt')

# 中易宋体（SimSun）。12px 有内嵌点阵字形，是中文小字号的最佳来源
DEFAULT_FONT = r'C:\Windows\Fonts\simsun.ttc'
STRIKE_SIZE  = 12     # 命中内嵌点阵的源字号（不要改，除非换字体）
DEFAULT_SIZE = 11     # 输出格子尺寸（由源点阵缩放得到）

# 界面上要用到、但可能不在剧本里的符号。
# 注意：这些符号必须是所选字体里**真实存在**的，否则会渲染成空白。
# 实测宋体 12px：▼▲△▽→←↑↓…—·、。，！？：；（）「」『』★☆○●□■※ 都有；
#                ▶◀♪ 没有（菜单光标因此在 C 代码里用画三角形实现）。
EXTRA_SYMBOLS = '▼▲△▽→←↑↓…—·、。，！？：；（）「」『』★☆○●□■※　'
ASCII_PRINTABLE = ''.join(chr(c) for c in range(0x20, 0x7F))


def strip_comments(src):
    """
    去掉 C 源码里的注释。

    必须做这一步：注释里的中文（比如 /* 这里要"重画整屏" */）会被字符串正则误当成
    字符串字面量，把一堆只在注释里出现的字塞进字库。功能上无害，但字库会白白变大。
    """
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':                       # 字符串字面量，整段保留
            out.append(c)
            i += 1
            while i < n:
                out.append(src[i])
                if src[i] == '\\' and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "'":                       # 字符字面量
            out.append(c)
            i += 1
            while i < n:
                out.append(src[i])
                if src[i] == '\\' and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        if src.startswith('/*', i):        # 块注释
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if src.startswith('//', i):        # 行注释
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def log(m):
    print('[font] ' + m)


def decode(b):
    """PIL 返回的是单通道位图，这里只关心"这个像素亮不亮" """
    return np.asarray(b, dtype=np.uint8)


def collect_charset():
    chars = set(ASCII_PRINTABLE) | set(EXTRA_SYMBOLS)
    if os.path.exists(CHARSET):
        with open(CHARSET, encoding='utf-8') as f:
            chars |= set(f.read())
        log(f'剧本字符集: {CHARSET}')
    else:
        log(f'警告: 找不到 {CHARSET}（先跑 tools/build_script.py）')

    # 扫 C 源码里的字符串字面量，抓非 ASCII 字符（UI 文字）
    n_c = 0
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'source')):
        for fn in files:
            if not fn.endswith('.c') and not fn.endswith('.h'):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding='utf-8', errors='ignore') as f:
                src = strip_comments(f.read())
            for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', src):
                for ch in lit:
                    if ord(ch) > 0x7E:
                        chars.add(ch)
                        n_c += 1
    log(f'C 源码字符串里额外发现 {n_c} 处非 ASCII 字符（可能有重复）')
    chars.discard('\n')
    chars.discard('\r')
    return sorted(chars, key=ord)


def find_vertical_window(font, size, samples):
    """找出应该截取哪 10 行：把所有样字的墨迹行取并集，再选覆盖最好的窗口"""
    rows = np.zeros(size * 2 + 6, dtype=int)
    for ch in samples:
        canvas = Image.new('L', (size * 2, size * 2 + 6), 0)
        ImageDraw.Draw(canvas).text((0, 0), ch, font=font, fill=255)
        ink = (decode(canvas) > 100).sum(axis=1)
        rows += (ink > 0).astype(int)
    used = np.nonzero(rows)[0]
    if len(used) == 0:
        raise RuntimeError('字体渲染不出任何墨迹，字体路径或字号可能不对')
    best, best_top = -1, int(used[0])
    for top in range(0, len(rows) - size + 1):
        score = rows[top:top + size].sum()
        if score > best:
            best, best_top = score, top
    log(f'墨迹行范围 {used.min()}~{used.max()}，选定截取窗口 y=[{best_top}, {best_top + size})')
    return best_top


def render_glyph(font, strike, ch, top, cell, glyph_w=None):
    """
    把一个字渲染成点阵（每行一个 u16，高位在左）。

    strike  ：渲染用的源字号（必须命中内嵌点阵）
    top     ：从源图第几行开始截（由 find_vertical_window 决定）
    cell    ：**存储格子的宽度**（= FONT_GLYPH_W）。所有字形都占这么宽，
              保持定长，C 侧才能用简单的二分查找。
    glyph_w ：这个字形**实际画多宽**。汉字 = cell；ASCII = 半角宽度
              （按源字体步进等比缩放，宋体 12px 的 6px → 11px 输出的 6px）。
              字形只填满格子的左边 glyph_w 列，右边留空，
              C 侧对 ASCII 只推进 glyph_w 像素，于是右边空白正好被下一个字覆盖。

    注意 "cell 与 strike 不同" 时要**面积平均缩放点阵**，
    这和"直接用更小字号渲染"完全不同：前者缩放手工点阵，后者缩放轮廓线再抗锯齿。

    返回 (行点阵, 亮点数, 左移列数)
    """
    if glyph_w is None:
        glyph_w = cell
    # 源图上取多宽：ASCII 只取源字体的半角框
    src_w = strike if glyph_w >= cell else max(1, round(strike * glyph_w / cell))

    canvas = Image.new('L', (strike * 2, strike * 2 + 6), 0)
    ImageDraw.Draw(canvas).text((0, 0), ch, font=font, fill=255)
    a = decode(canvas)
    b = (a[top:top + strike, 0:src_w] > 100)          # 截窗口 + 二值化

    if (cell, glyph_w) != (strike, src_w):             # 点阵缩放（面积平均）
        img = Image.fromarray((b * 255).astype(np.uint8))
        img = img.resize((glyph_w, cell), Image.BOX)
        b = np.asarray(img) > 100

    shifted = 0
    cols = np.nonzero(b.sum(axis=0))[0]
    if len(cols) and int(cols.max()) > glyph_w - 1:    # 墨迹溢出色块 → 整体左移
        over = int(cols.max()) - (glyph_w - 1)
        b = np.roll(b, -over, axis=1)
        b[:, glyph_w - over:] = False
        shifted = over

    rows = []
    for y in range(cell):
        v = 0
        for x in range(glyph_w):
            if b[y, x]:
                v |= (1 << (15 - x))         # 最高位 = 最左像素
        rows.append(v)
    return rows, int(b.sum()), shifted


def write_asm_and_header(count, gw, gh, ascii_w):
    s_path = os.path.join(ASSET_DIR, 'font_data.s')
    with open(s_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_cjk_font.py 自动生成，请勿手工修改 */\n')
        f.write('    .section .rodata\n')
        f.write('\n    .global font_glyphs\n    .align 2\nfont_glyphs:\n')
        f.write('    .incbin "font_glyphs.bin"\n')
        f.write('\n    .global font_index\n    .align 2\nfont_index:\n')
        f.write('    .incbin "font_index.bin"\n')
    log('font_data.s')

    with open(os.path.join(INC_DIR, 'font_data.h'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_cjk_font.py 自动生成，请勿手工修改 */\n')
        f.write('#ifndef FONT_DATA_H\n#define FONT_DATA_H\n\n#include <tonc.h>\n\n')
        f.write(f'#define FONT_GLYPH_W       {gw}\n')
        f.write(f'#define FONT_GLYPH_H       {gh}\n')
        f.write('#define FONT_GLYPH_ROWS    FONT_GLYPH_H\n')
        f.write(f'#define FONT_GLYPH_COUNT   {count}\n')
        f.write('#define FONT_GLYPH_BYTES   (FONT_GLYPH_ROWS * 2)\n')
        f.write(f'/* ASCII 的推进宽度：由字库工具按源字体步进算出，\n')
        f.write(f' * C 侧不要写死，否则会和字库里的字形宽度脱节 */\n')
        f.write(f'#define FONT_ASCII_W       {ascii_w}\n\n')
        f.write('extern const u16 font_glyphs[];   /* 每字 FONT_GLYPH_ROWS 个 u16，高位在左 */\n')
        f.write('extern const u32 font_index[];    /* 升序码点表，与 font_glyphs 一一对应 */\n\n')
        f.write('#endif /* FONT_DATA_H */\n')
    log('font_data.h')


def write_preview(charset, glyph_map, size, top, ascii_w, samples):
    """用生成的点阵（而不是 TTF）拼出真实效果图，供人工确认。
    这里按 C 侧的真实排版来画：ASCII 只占 ascii_w 像素宽。"""
    def advance(ch):
        return ascii_w if ord(ch) < 0x80 else size

    def render_line(text, scale):
        w = sum(advance(c) for c in text)
        img = Image.new('L', (max(1, w), size), 0)
        px = img.load()
        x = 0
        for ch in text:
            g = glyph_map.get(ch)
            if g:
                for y in range(size):
                    v = g[y]
                    for b in range(size):
                        if v & (1 << (15 - b)):
                            px[x + b, y] = 255
            x += advance(ch)
        return img.resize((img.width * scale, img.height * scale), Image.NEAREST)

    lines = [s for s in samples if s]
    imgs = [render_line(t, 4) for t in lines[:5]]
    total_h = sum(i.height + 8 for i in imgs) + 8
    max_w = max(i.width for i in imgs) + 16
    out = Image.new('L', (max_w, total_h), 25)
    y = 4
    for im in imgs:
        out.paste(im, (8, y))
        y += im.height + 8
    out.save(os.path.join(TMP_DIR, 'font_preview.png'))
    log(f'.tmp/font_preview.png（{len(imgs)} 行真实点阵预览，按实际排版宽度）')


def main():
    size = DEFAULT_SIZE
    strike = STRIKE_SIZE
    font_path = DEFAULT_FONT
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--size' and i + 1 < len(args):
            size = int(args[i + 1])
        if a == '--strike' and i + 1 < len(args):
            strike = int(args[i + 1])
        if a == '--font' and i + 1 < len(args):
            font_path = args[i + 1]
    if not os.path.exists(font_path):
        print(f'[font] 找不到字体 {font_path}', file=sys.stderr)
        sys.exit(1)

    os.makedirs(ASSET_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    font = ImageFont.truetype(font_path, strike)
    log(f'字体 {os.path.basename(font_path)}  源字号 {strike}px → 输出 {size}x{size}')

    # 先确认源字号是否真的命中内嵌点阵：渲染一句话，数灰度级。
    # 灰度级 == 2 表示只有纯黑纯白，即"点阵字形"；上百个灰度级说明是轮廓线缩放。
    probe = Image.new('L', (strike * 10, strike * 2 + 6), 0)
    ImageDraw.Draw(probe).text((0, 0), '国矗蘑菇塔少女沙漠', font=font, fill=255)
    levels = len(np.unique(np.asarray(probe)))
    if levels <= 2:
        log(f'源字号命中内嵌点阵 ✅（灰度级 {levels}）')
    else:
        log(f'⚠ 源字号没命中内嵌点阵（灰度级 {levels}，>2 说明是轮廓+抗锯齿，字会糊）')
        log('   宋体的内嵌点阵只在 12px（9 号）这一档，建议 --strike 12')

    adv_cjk = font.getlength('国')
    adv_ascii = font.getlength('A')
    log(f'源字步进：汉字 {adv_cjk:.1f}px  ASCII {adv_ascii:.1f}px')
    half = (abs(adv_ascii * 2 - adv_cjk) < 0.5)      # ASCII 是不是半角
    log(f'ASCII {"是半角（C 侧只推进一半宽度）" if half else "是全角"}')

    # ASCII 推进宽度：按源字体步进等比缩放到输出尺寸。
    # 不能简单写 size//2 —— 宋体 12px 的 ASCII 墨迹有 6 列宽（94 个可打印字符里
    # 只有 1 个 m 到第 7 列），缩到 11px 后用 6 列刚好够；用 size//2 = 5 列
    # 会把 38 个字符（墨迹到第 6 列的）砍掉一列。
    ascii_w = int(adv_ascii * size / strike + 0.5) if half else size
    if ascii_w > size:
        ascii_w = size
    log(f'ASCII 推进宽度 = {ascii_w}px（存储仍占 {size} 宽的格子，只用左边 {ascii_w} 列）')

    charset = collect_charset()
    log(f'字符集共 {len(charset)} 个字符')

    top = find_vertical_window(font, strike, charset)

    glyphs, index, blanks, shifted_chars = [], [], [], []
    glyph_map = {}
    for ch in charset:
        gw = ascii_w if (half and ord(ch) < 0x80) else size
        rows, ink, shifted = render_glyph(font, strike, ch, top, size, gw)
        if ch != ' ' and ink == 0:
            blanks.append(ch)
        if shifted:
            shifted_chars.append(f'{ch}(左移{shifted})')
        glyphs.extend(rows)
        index.append(ord(ch))
        glyph_map[ch] = rows

    if shifted_chars:
        log(f'字形墨迹超出可用宽度、已整体左移的 {len(shifted_chars)} 个: {" ".join(shifted_chars)}')
    if blanks:
        log(f'⚠ 有 {len(blanks)} 个字符渲染为空白（字库缺字或该字太复杂）: {"".join(blanks[:40])}')

    with open(os.path.join(ASSET_DIR, 'font_glyphs.bin'), 'wb') as f:
        f.write(struct.pack('<%dH' % len(glyphs), *glyphs))
    with open(os.path.join(ASSET_DIR, 'font_index.bin'), 'wb') as f:
        f.write(struct.pack('<%dI' % len(index), *index))
    log(f'font_glyphs.bin  {len(glyphs) * 2:,} 字节（{len(index)} 字 × {size}x{size}）')
    log(f'font_index.bin   {len(index) * 4:,} 字节')

    write_asm_and_header(len(index), size, size, ascii_w)

    with open(os.path.join(ROOT, 'scenario', 'scenario.txt'), encoding='utf-8') as f:
        samples = [l.split('|', 1)[-1].strip() for l in f
                   if l.strip().startswith('say') and '|' in l]
    # 最后一行故意做成中英混排：ASCII 是半角，用来确认 "GBA" 没有被撑成全角宽度
    write_preview(charset, glyph_map, size, top, ascii_w,
                  samples[:3] + ['GBA 中文 galgame 测试 · 点阵字库'])


if __name__ == '__main__':
    main()
