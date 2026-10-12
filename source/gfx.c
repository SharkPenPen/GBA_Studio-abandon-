/* =====================================================================
 *  gfx.c —— 绘制原语（对外 API 不变，内部改成"往当前画布画"）
 *
 *  重构前：所有函数直接写 `vid_mem`，等于假设"屏幕就是一块 16bpp 位图"。
 *  重构后：委托给 surface.c 的**当前画布**，于是同一套代码能跑在
 *          模式 3/5（直色位图）、模式 4（8bpp 索引）、模式 0/1/2（图块画布）上。
 *
 *  这一层刻意保持"薄"：它只是 gfx 名字下的转发 + 背景图记忆，
 *  真正的像素操作在 surface.c。调用方（vn.c / level.c / ui.c / text.c）
 *  **一行都不用改**。
 *
 *  【性能保住的地方】
 *  DMA 快路径只对直色位图有意义（模式 3/5）：整屏背景一次 DMA、
 *  矩形恢复每行一次 DMA。索引/图块后端走 CPU 逐像素（要查色），
 *  这是"换模式"的固有代价，不是实现偷懒。
 * ===================================================================== */

#include "gfx.h"
#include "video.h"
#include "surface.h"
#include "obj.h"
#include "project_video.h"   /* 显示模式（由编辑器导出时写出）*/

/* 当前背景资源（gfx_restore_rect 用它取回被覆盖的像素） */
static const GfxAsset *s_bg = NULL;

/* ---------------------------------------------------------------------
 * DMA（只用于直色位图的快路径）
 * ------------------------------------------------------------------- */
static void dma_copy32(void *dst, const void *src, u32 words)
{
    REG_DMA3SAD = (u32)src;
    REG_DMA3DAD = (u32)dst;
    REG_DMA3CNT = words | DMA_CPY32;
}

/* ---------------------------------------------------------------------
 * 初始化
 * ------------------------------------------------------------------- */
void gfx_init(void)
{
    /* 用**工程里选的那个模式**（编辑器导出时写进 project_video.h）。
     * 没写过这个文件时退回模式 3 —— 和重构前完全一致，画面逐像素不变。 */
#ifndef GAL_VIDEO_MODE
#define GAL_VIDEO_MODE 3
#endif
    gfx_set_mode((VideoMode)GAL_VIDEO_MODE);
}

void gfx_set_mode(VideoMode m)
{
    video_set_mode(m);
    spr_init();                       /* 精灵层的显存位置随模式变，要重新初始化 */
    sf_forget_colors();              /* 调色板变了，查色缓存作废 */
    sf_set_current(sf_auto());
    s_bg = NULL;
    video_page_clear(0);          /* 换模式先清屏（8bpp 时两页都清），免得看到残留 */
    gfx_flush();
}

Surface *gfx_surface(void)     { return sf_current(); }
int      gfx_mode(void)        { return (int)video_mode(); }
int      gfx_is_bitmap(void)   { return video_is_bitmap(); }

/* 每帧画完之后调一次：图块后端要在这时把脏格传上去 */
void gfx_flush(void)
{
    Surface *s = sf_current();
    if (s) sf_flush(s);
}

void gfx_clear(u16 color)
{
    Surface *s = sf_current();
    if (!s) return;
    if (s->kind == SF_DIRECT) {
        /* 直色位图：两个像素拼一个 32 位，DMA 一次填满 */
        static volatile u32 pair;
        pair = ((u32)color << 16) | color;
        REG_DMA3SAD = (u32)&pair;
        REG_DMA3DAD = (u32)s->px;
        REG_DMA3CNT = (u32)((s->w * s->h) / 2) | DMA_FILL32;
    } else {
        sf_clear(s, color);
    }
}

/* ---------------------------------------------------------------------
 * 矩形（CPU 循环；图块后端会顺便标脏）
 * ------------------------------------------------------------------- */
void gfx_fill_rect(int x, int y, int w, int h, u16 color)
{
    Surface *s = sf_current();
    if (s) sf_fill(s, x, y, w, h, color);
}

void gfx_rect_border(int x, int y, int w, int h, u16 color)
{
    Surface *s = sf_current();
    if (s) sf_border(s, x, y, w, h, color);
}

void gfx_hline(int x, int y, int w, u16 color)
{
    Surface *s = sf_current();
    if (s) sf_fill(s, x, y, w, 1, color);
}

/* ---------------------------------------------------------------------
 * 背景与还原
 * ------------------------------------------------------------------- */
void gfx_set_bg(const GfxAsset *bg)
{
    s_bg = bg;
}

void gfx_draw_bg(const GfxAsset *bg)
{
    s_bg = bg;
    Surface *s = sf_current();
    if (!s || !bg || !bg->px) return;
    if (s->kind == SF_DIRECT && s->w == SCR_W && s->h == SCR_H) {
        /* 整屏 76800 字节 = 19200 个 32 位字，一次 DMA 搬完 */
        dma_copy32(s->px, bg->px, (SCR_W * SCR_H) / 2);
        return;
    }
    sf_draw_bg(s, bg);
}

void gfx_restore_rect(int x, int y, int w, int h)
{
    Surface *s = sf_current();
    if (!s || !s_bg || !s_bg->px) return;

    if (s->kind == SF_DIRECT && s->w == SCR_W && s->h == SCR_H) {
        if (x < 0) { w += x; x = 0; }
        if (y < 0) { h += y; y = 0; }
        if (x + w > SCR_W) w = SCR_W - x;
        if (y + h > SCR_H) h = SCR_H - y;
        if (w <= 0 || h <= 0) return;
        const u16 *src = s_bg->px + y * SCR_W + x;
        u16 *dst = s->px + y * SCR_W + x;
        u32 words = (u32)(w / 2);
        if (words == 0) {
            for (int row = 0; row < h; row++) dst[row * SCR_W] = src[row * SCR_W];
            return;
        }
        for (int row = 0; row < h; row++)
            dma_copy32(dst + row * SCR_W, src + row * SCR_W, words);
        return;
    }
    sf_restore(s, s_bg, x, y, w, h);
}

/* ---------------------------------------------------------------------
 * 立绘：带透明 key 的 blit（跳过连续透明像素，整段拷贝）
 * ------------------------------------------------------------------- */
void gfx_draw_sprite(const GfxAsset *a, int dx, int dy)
{
    Surface *s = sf_current();
    if (s) sf_draw_sprite(s, a, dx, dy);
}

/* ---------------------------------------------------------------------
 * 菜单光标：向右的实心三角
 *
 *  为什么要自己画：生成字库用的黑体在 10px 下**没有** ▶ 这个字形
 *（实测 ▼▲△→← 都有，▶◀♪ 没有）。与其去凑一个不存在的符号，
 *  不如直接用矩形拼一个，反正只有几行代码。
 * ------------------------------------------------------------------- */
void gfx_cursor_triangle(int x, int y, int size, u16 color)
{
    int half = size / 2;
    for (int i = 0; i < half; i++) {
        int rows = size - i * 2;
        gfx_fill_rect(x + i, y + i, 1, rows > 0 ? rows : 1, color);
    }
}
