/* 由 tools/make_cjk_font.py 自动生成，请勿手工修改 */
#ifndef FONT_DATA_H
#define FONT_DATA_H

#include <tonc.h>

#define FONT_GLYPH_W       11
#define FONT_GLYPH_H       11
#define FONT_GLYPH_ROWS    FONT_GLYPH_H
#define FONT_GLYPH_COUNT   801
#define FONT_GLYPH_BYTES   (FONT_GLYPH_ROWS * 2)
/* ASCII 的推进宽度：由字库工具按源字体步进算出，
 * C 侧不要写死，否则会和字库里的字形宽度脱节 */
#define FONT_ASCII_W       6

extern const u16 font_glyphs[];   /* 每字 FONT_GLYPH_ROWS 个 u16，高位在左 */
extern const u32 font_index[];    /* 升序码点表，与 font_glyphs 一一对应 */

#endif /* FONT_DATA_H */
