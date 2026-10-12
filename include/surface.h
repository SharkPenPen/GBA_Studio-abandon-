/* =====================================================================
 *  surface.h —— 画布抽象：同一套绘制代码，跑在任何显示模式上
 *
 *  【为什么要这一层】
 *  重构前所有绘制都直接写 `vid_mem`（假设"屏幕就是一块 16bpp 位图"）。
 *  但 GBA 的模式 0/1/2 **没有位图**，模式 4 是 8bpp（颜色要查调色板）。
 *  与其在每处绘制里写 if (mode==...) ，不如把"往哪画"抽成一个对象。
 *
 *  【三种后端】
 *      SF_DIRECT    直色位图（模式 3、5）
 *                   写像素就是 `px[i] = 颜色`，最简单最快
 *      SF_INDEXED   索引位图（模式 4）
 *                   写像素要先把 15 位色查成调色板下标 —— 颜色会有损，
 *                   换来的是**两页可以翻**（不撕裂）
 *      SF_TILES     图块画布（模式 0/1/2）
 *                   先在 RAM 里画（一张 240x160 的下标图），
 *                   每帧把**变化过的 8x8 格**转成图块传进显存。
 *                   能滚动（硬件做），代价是颜色同样降到 256 色。
 *
 *  【颜色怎么对上】
 *  调用方永远写 15 位色（RGB15），后端自己查表：
 *  首次遇到某个颜色时，在调色板里找最接近的一个，记进 32KB 的缓存表
 *  （`lut`，存"下标+1"，0 表示没填过）。之后就是一次查表，很快。
 *  这就是"全面支持"的代价：图块/8bpp 模式下颜色降到 256 色。
 * ===================================================================== */
#ifndef SURFACE_H
#define SURFACE_H

#include <tonc.h>
#include "gfx_assets.h"

typedef enum {
    SF_DIRECT = 0,      /* 16bpp 直色 */
    SF_INDEXED,         /* 8bpp 索引（含模式 4 的显存页）*/
    SF_TILES,           /* 图块画布（RAM 缓冲 + 脏格回传）*/
} SfKind;

#define SF_MAX_W 240
#define SF_MAX_H 160
#define SF_MAX_CW 30        /* 脏格表：240/8 */
#define SF_MAX_CH 20        /* 160/8 */

typedef struct Surface {
    SfKind kind;
    int    w, h;            /* 逻辑尺寸（模式 5 是 160x128）*/
    int    stride;          /* 每行多少个像素 */

    u16   *px;              /* SF_DIRECT：目标（VRAM）*/
    u8    *idx;             /* SF_INDEXED / SF_TILES：8 位下标缓冲 */

    const u16 *pal;         /* 256 色调色板（INDEXED/TILES 用）*/
    /* 查色表不放在这里：三后端共用一张全局表（见 surface.c 的说明）*/

    /* ---- SF_TILES 专用 ---- */
    int    bg;              /* 画到哪个背景层 */
    u8     dirty[SF_MAX_CW * SF_MAX_CH];
    int    cw, ch;          /* 脏格表尺寸 */
    u8    *tiles;           /* 图块数据区（显存）*/
    u16   *map;             /* 地图区（显存）*/
    int    map_pitch;       /* 地图每行多少格（32 或 64）*/
} Surface;

/* ---- 建画布（都用静态实例，别在栈上建：结构体里有 32KB 的查色表）---- */
Surface *sf_bitmap_direct(int w, int h, u16 *vram);            /* 模式 3/5 */
Surface *sf_bitmap_indexed(int w, int h, u8 *vram, const u16 *pal);  /* 模式 4 */
Surface *sf_tiles(int w, int h, int bg, int cb_base, int sb_base);   /* 模式 0/1/2 */

/* 按当前显示模式自动建一个合适的画布（推荐入口）*/
Surface *sf_auto(void);
Surface *sf_current(void);
void     sf_set_current(Surface *s);

/* ---- 绘制（三种后端共用同一套语义）---- */
void sf_clear(Surface *s, u16 color);
void sf_fill(Surface *s, int x, int y, int w, int h, u16 color);
void sf_border(Surface *s, int x, int y, int w, int h, u16 color);
void sf_draw_sprite(Surface *s, const GfxAsset *a, int dx, int dy);
void sf_draw_bg(Surface *s, const GfxAsset *bg);        /* 整屏图（按行 blit）*/
void sf_restore(Surface *s, const GfxAsset *bg, int x, int y, int w, int h);

/* ---- 收尾 ---- */
void sf_flush(Surface *s);      /* SF_TILES：把脏格转成图块传上去；其他后端空操作 */

/* 颜色 → 下标（外部一般不用调，绘制函数内部用）*/
u8   sf_index(Surface *s, u16 color);

/* 换模式/换调色板后要清掉查色缓存（否则会拿旧调色板算出的下标去画）*/
void sf_forget_colors(void);

/* 铺一张默认 256 色调色板（6x6x6 色立方 + 灰阶）。
 * 图块模式和 8bpp 都靠调色板显示，不铺就是一片黑。
 * 真要拿这两种模式做游戏，应该按素材生成自适应调色板。 */
void sf_build_default_palette(u16 *pal);

#endif /* SURFACE_H */
