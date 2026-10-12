/* =====================================================================
 *  text.h —— 10x10 中文点阵文字渲染
 *
 *  为什么不用 libtonc 的 TTE：
 *    TTE 是给日文/ASCII 设计的，字形表按"码点 0~255 直接索引"，
 *    中文码点动辄几万，索引方式完全不适用；而且 TTE 假设每个字形宽度
 *    由字体表给出，中文是固定宽度，用不上。
 *    所以这里自己写一层：UTF-8 解码 → 二分查找字形 → 逐点写显存。
 * ===================================================================== */
#ifndef TEXT_H
#define TEXT_H

#include <tonc.h>
#include "font_data.h"

/* 一次最多排几行（对话框是 3 行，留一点余量） */
#define TEXT_MAX_LINES 5

/* 排版结果：每行在原文里的起始指针 + 字符个数 */
typedef struct {
    const char *line[TEXT_MAX_LINES];
    u8  len[TEXT_MAX_LINES];
    u8  count;
} TextLayout;

/* 取出一个字符的字形数据（找不到返回 NULL）。字形 = FONT_GLYPH_ROWS 个 u16 */
const u16 *text_glyph(u32 codepoint);

/* UTF-8 解码：读取一个字符并推进指针。非法字节按 '?' 处理并前进 1 字节 */
u32 text_next_cp(const char **pp);

/* 字符串有多少个"字"（不是字节数 —— 一个汉字在 UTF-8 里占 3 字节） */
int text_count(const char *utf8);

/* 一个字符占多宽：ASCII 半角（FONT_GLYPH_W/2），其余全角（FONT_GLYPH_W）。
 * 宋体等 CJK 字体的 ASCII 步进本来就是汉字的一半，照这个宽度排才能让
 * "GBA" 看起来是三个半角字母，而不是三个被撑开的全角字。 */
int text_advance(u32 codepoint);

/* 整串文字占多少像素宽 */
int text_width(const char *utf8);

/* 在 (x, y) 画一行字，返回结束时的 x */
int text_draw(int x, int y, const char *utf8, u16 color);

/* 只画前 n 个字（打字机效果用） */
int text_draw_n(int x, int y, const char *utf8, int n, u16 color);

/* 在 [x, x+width) 范围内居中画一行 */
void text_draw_center(int x, int y, int width, const char *utf8, u16 color);

/* 自动换行排版（含中文禁则处理）。max_px 是每行的像素预算，不是字数 ——
 * 这样中英混排时换行位置才准确（半角字符只占一半宽度）。 */
void text_layout(const char *utf8, int max_px, int max_lines, TextLayout *out);

/* 按排版结果绘制，只显示前 reveal 个字（打字机效果） */
void text_draw_layout(const TextLayout *lay, int x, int y, int line_h,
                      int reveal, u16 color);

#endif /* TEXT_H */
