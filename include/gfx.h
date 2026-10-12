/* =====================================================================
 *  gfx.h —— 位图绘制原语（模式 3，240x160，16 位直接色）
 *
 *  为什么用模式 3：
 *    galgame 是"一张大背景 + 两三个立绘 + 一个对话框"，画面几乎是静态的。
 *    模式 3 是 16 位直接色，不需要调色板管理，两张不同色调的背景和立绘
 *    可以同时保持各自的原色 —— 换成模式 4（8bpp）就得把背景、立绘、文字
 *    挤进同一个 256 色调色板，颜色会明显劣化。
 *
 *  代价（参见 docs/05 移植笔记）：
 *    模式 3 的显存只有一块 240x160x2 = 76800 字节的画布，
 *    96KB 显存放不下第二块，所以**无法双缓冲**，换场景时会看到一次撕裂。
 * ===================================================================== */
#ifndef GFX_H
#define GFX_H

#include <tonc.h>
#include "gfx_assets.h"
#include "video.h"      /* VideoMode 枚举（显示模式）*/

/* 常用颜色（RGB15 是内联函数，运行期调用没问题） */
#define CLR_TEXT        RGB15(31, 31, 31)   /* 正文白 */
#define CLR_BOX_FILL    RGB15( 6,  7, 14)   /* 对话框底色：深蓝灰 */
#define CLR_BOX_EDGE    RGB15(24, 26, 31)   /* 对话框描边：浅灰 */
#define CLR_NAME_FILL   RGB15(22,  6, 10)   /* 名字牌底色：暗红 */
#define CLR_NAME_EDGE   RGB15(31, 24, 12)   /* 名字牌描边 */
#define CLR_CURSOR      RGB15(31, 26,  8)   /* 光标三角：亮黄 */
#define CLR_CHOICE_FILL RGB15( 8, 10, 18)   /* 选项面板底色 */
#define CLR_DIM         RGB15(12, 12, 14)   /* 暗色（未选中项） */

/* 初始化显示。默认模式 3（位图），和重构前一致 */
void gfx_init(void);

/* ---- 显示模式（P11：六种模式全支持）----
 * 换模式会重建画布并清屏。之后所有绘制自动落到新画布上，
 * 上层代码（剧情/关卡/菜单/文字）不用改一行。
 * 代价：图块模式（0/1/2）和 8bpp（4）下颜色降到 256 色。 */
void gfx_set_mode(VideoMode m);
int  gfx_mode(void);
int  gfx_is_bitmap(void);        /* 1 = 位图模式（3/4/5）*/

/* 每帧画完之后调一次：图块模式下把变化过的格子传进显存 */
void gfx_flush(void);

/* 当前画布（surface.c 的对象）；一般不用直接摸 */
struct Surface *gfx_surface(void);

/* 整屏填充 */
void gfx_clear(u16 color);

/* 实心矩形（小面积用，纯 CPU 循环） */
void gfx_fill_rect(int x, int y, int w, int h, u16 color);

/* 一条横线（比 fill_rect 少两次参数检查，热路径用） */
void gfx_hline(int x, int y, int w, u16 color);

/* 1 像素空心矩形（描边） */
void gfx_rect_border(int x, int y, int w, int h, u16 color);

/* 记住"当前背景"，之后 gfx_restore_rect() 就从这张图里取回像素 */
void gfx_set_bg(const GfxAsset *bg);

/* 整屏画背景（DMA 从 ROM 拷到显存） */
void gfx_draw_bg(const GfxAsset *bg);

/* 把一块矩形区域恢复成背景内容（用来擦掉立绘/文字，而不破坏背景） */
void gfx_restore_rect(int x, int y, int w, int h);

/* 画立绘：按资源自带的 key 色做透明处理（软件 blit） */
void gfx_draw_sprite(const GfxAsset *a, int dx, int dy);

/* 画一个向右的实心三角（菜单光标）。字库里没有 ▶，所以用代码画 */
void gfx_cursor_triangle(int x, int y, int size, u16 color);

#endif /* GFX_H */
