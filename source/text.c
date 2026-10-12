/* =====================================================================
 *  text.c —— 10x10 中文点阵渲染实现
 *
 *  字库由 tools/make_cjk_font.py 生成：
 *      font_glyphs[]  每字 10 个 u16（10 行），最高位是最左边的像素
 *      font_index[]   升序码点表，和字形一一对应
 *  查找用二分，约 9 次比较（268 字的情况），比哈希表更省空间也够快。
 * ===================================================================== */

#include "text.h"
#include "gfx.h"

#define VID ((u16 *)vid_mem)

/* ---------------------------------------------------------------------
 * 字形查找
 * ------------------------------------------------------------------- */
const u16 *text_glyph(u32 cp)
{
    int lo = 0, hi = FONT_GLYPH_COUNT - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        u32 v = font_index[mid];
        if (v == cp)
            return &font_glyphs[mid * FONT_GLYPH_ROWS];
        if (v < cp) lo = mid + 1;
        else        hi = mid - 1;
    }
    return NULL;                       /* 字库里没有这个字 */
}

int text_advance(u32 codepoint)
{
    /* CJK 字体的 ASCII 是半角：汉字 11px，ASCII 6px（FONT_ASCII_W 由字库工具
     * 按源字体步进算出并写进 font_data.h，不要在这里写死 —— 改字号时会脱节）。
     * 字形数据仍然按全宽格子存（定长便于二分查找），ASCII 只用左半边，
     * 右半边是空的，正好被下一个字覆盖 —— 不需要额外的存储结构。 */
    return (codepoint < 0x80) ? FONT_ASCII_W : FONT_GLYPH_W;
}

int text_width(const char *utf8)
{
    int w = 0;
    const char *p = utf8;
    while (*p) w += text_advance(text_next_cp(&p));
    return w;
}

/* ---------------------------------------------------------------------
 * UTF-8 解码
 *
 *  汉字在 UTF-8 里是 3 字节，ASCII 是 1 字节。GBA 上没有标准库帮你做这件事，
 *  必须自己解 —— 这是移植任何中文/日文游戏都要过的一关。
 * ------------------------------------------------------------------- */
u32 text_next_cp(const char **pp)
{
    const u8 *p = (const u8 *)*pp;
    u32 c = *p;

    if (c < 0x80) {                    /* 0xxxxxxx */
        *pp = (const char *)(p + 1);
        return c;
    }
    if ((c & 0xE0) == 0xC0 && (p[1] & 0xC0) == 0x80) {          /* 110xxxxx */
        *pp = (const char *)(p + 2);
        return ((c & 0x1F) << 6) | (p[1] & 0x3F);
    }
    if ((c & 0xF0) == 0xE0 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80) {  /* 1110xxxx */
        *pp = (const char *)(p + 3);
        return ((c & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F);
    }
    if ((c & 0xF8) == 0xF0 && (p[1] & 0xC0) == 0x80 &&
        (p[2] & 0xC0) == 0x80 && (p[3] & 0xC0) == 0x80) {       /* 11110xxx */
        *pp = (const char *)(p + 4);
        return ((c & 0x07) << 18) | ((p[1] & 0x3F) << 12) |
               ((p[2] & 0x3F) << 6) | (p[3] & 0x3F);
    }
    *pp = (const char *)(p + 1);       /* 非法字节：跳过，返回 '?' */
    return '?';
}

int text_count(const char *utf8)
{
    int n = 0;
    const char *p = utf8;
    while (*p) { text_next_cp(&p); n++; }
    return n;
}

/* ---------------------------------------------------------------------
 * 绘制一个字形
 *
 *  只遍历"有墨迹"的像素：先看整行掩码是否为 0（空白行直接跳过），
 *  再在行内左移掩码。10x10 的字形平均只有 30 来个亮点，
 *  比逐像素判断快几倍。
 * ------------------------------------------------------------------- */
static void draw_glyph(int x, int y, const u16 *g, u16 color)
{
    if (!g) return;                    /* 字库缺字 → 留空（见 docs/05 缺字排查） */
    if (y + FONT_GLYPH_H <= 0 || y >= SCR_H) return;
    if (x + FONT_GLYPH_W <= 0 || x >= SCR_W) return;

    if (x >= 0 && y >= 0 && x + FONT_GLYPH_W <= SCR_W && y + FONT_GLYPH_H <= SCR_H) {
        /* 完全在屏幕内：快路径 */
        for (int row = 0; row < FONT_GLYPH_ROWS; row++) {
            u16 m = g[row];
            if (!m) continue;
            u16 *dst = VID + (y + row) * SCR_W + x;
            for (int b = 0; b < FONT_GLYPH_W && m; b++, m <<= 1) {
                if (m & 0x8000) dst[b] = color;
            }
        }
        return;
    }
    /* 贴边（半角字符排在行尾时会半出屏）：逐点裁剪 */
    for (int row = 0; row < FONT_GLYPH_ROWS; row++) {
        int py = y + row;
        if (py < 0 || py >= SCR_H) continue;
        u16 m = g[row];
        u16 *dst = VID + py * SCR_W;
        for (int b = 0; b < FONT_GLYPH_W && m; b++, m <<= 1) {
            int px = x + b;
            if ((m & 0x8000) && px >= 0 && px < SCR_W) dst[px] = color;
        }
    }
}

int text_draw(int x, int y, const char *utf8, u16 color)
{
    const char *p = utf8;
    while (*p) {
        u32 cp = text_next_cp(&p);
        draw_glyph(x, y, text_glyph(cp), color);
        x += text_advance(cp);
    }
    return x;
}

int text_draw_n(int x, int y, const char *utf8, int n, u16 color)
{
    const char *p = utf8;
    int i = 0;
    while (*p && i < n) {
        u32 cp = text_next_cp(&p);
        draw_glyph(x, y, text_glyph(cp), color);
        x += text_advance(cp);
        i++;
    }
    return x;
}

void text_draw_center(int x, int y, int width, const char *utf8, u16 color)
{
    int w = text_width(utf8);
    int start = x + (width - w) / 2;
    if (start < x) start = x;
    text_draw(start, y, utf8, color);
}

/* ---------------------------------------------------------------------
 * 中文换行（禁则处理）
 *
 *  西文按空格断词，中文没有空格，只能在字与字之间断。但不能乱断：
 *    - 行首不能是 ，。、！？：；）」』…— 这类"收尾标点"
 *    - 行尾不能是 （「『 这类"开头标点"
 *  处理办法：本行排满 max_chars 后，如果下一个字是收尾标点，
 *  就把本行最后一个字挤到下一行，让标点留在行尾。
 * ------------------------------------------------------------------- */
static int is_no_line_start(u32 cp)
{
    switch (cp) {
        case 0xFF0C: case 0x3002: case 0x3001: case 0xFF01: case 0xFF1F:
        case 0xFF1A: case 0xFF1B: case 0xFF09: case 0x300D: case 0x300F:
        case 0x2026: case 0x2014: case 0x00B7:
            return 1;
        default:
            return 0;
    }
}

static int is_no_line_end(u32 cp)
{
    switch (cp) {
        case 0xFF08: case 0x300C: case 0x300E:
            return 1;
        default:
            return 0;
    }
}

void text_layout(const char *utf8, int max_px, int max_lines, TextLayout *out)
{
    out->count = 0;
    const char *p = utf8;

    while (*p && out->count < max_lines) {
        const char *line_start = p;
        int n = 0, w = 0;

        /* 按**像素**排满一行，不是按字数 —— 中英混排时半角字符只占一半宽度，
         * 按字数算会导致换行过早（一行明明还能放下几个字母）。 */
        const char *q = p;
        while (*q && w < max_px) {
            if (*q == '\n') break;
            const char *t = q;
            int adv = text_advance(text_next_cp(&t));
            if (w + adv > max_px) break;
            w += adv;
            q = t;
            n++;
        }

        if (*q == '\n') {              /* 显式换行 */
            out->line[out->count] = line_start;
            out->len[out->count]  = (u8)n;
            out->count++;
            p = q + 1;
            continue;
        }

        /* 禁则修正一：下一个字是收尾标点 → 本行少放一个字 */
        if (*q && n > 1) {
            const char *t = q;
            u32 nxt = text_next_cp(&t);
            if (is_no_line_start(nxt)) n--;
        }

        /* 禁则修正二：本行最后一个字是开头标点 → 也挪到下一行 */
        while (n > 1) {
            const char *t = line_start;
            u32 last = 0;
            for (int i = 0; i < n; i++) last = text_next_cp(&t);
            if (!is_no_line_end(last)) break;
            n--;
        }

        out->line[out->count] = line_start;
        out->len[out->count]  = (u8)n;
        out->count++;

        p = line_start;                /* 指针推进到本行末尾 */
        for (int i = 0; i < n; i++) text_next_cp(&p);
    }
}

void text_draw_layout(const TextLayout *lay, int x, int y, int line_h,
                      int reveal, u16 color)
{
    int shown = 0;
    for (int i = 0; i < lay->count; i++) {
        int left = reveal - shown;
        if (left <= 0) break;
        int n = (left < lay->len[i]) ? left : lay->len[i];
        text_draw_n(x, y + i * line_h, lay->line[i], n, color);
        shown += n;
    }
}
