/* =====================================================================
 *  bg.h —— 仿射图块层（模式 1 的 BG2 / 模式 2 的 BG2、BG3）
 *
 *  【仿射层和普通图块层的区别 —— 决定了该怎么用它】
 *
 *      普通文本层（BG0/BG1，模式 0/1）      仿射层（BG2/BG3，模式 1/2）
 *      地图条目 2 字节                      地图条目 **1 字节**
 *         → 图块号 10 位，最多 1024 个         → 图块号 **8 位，最多 256 个**
 *      地图 32x32 ~ 64x64 **格**            地图 16x16 ~ 128x128 **格**
 *         (=256x256 ~ 512x512 像素)            (=128x128 ~ 1024x1024 像素)
 *      只能滚动                              能**旋转、缩放**（PA/PB/PC/PD）
 *      边界截断                              有环绕（wraparound）
 *
 *  所以：**别把"整屏位图画布"那套搬到仿射层上** ✗
 *  一格一个图块的方案在 240x160 下要 600 个图块，而仿射层只能放 256 个 ✗
 *
 *  仿射层的正确用法是它擅长的：**一张真正的图块地图 + 少量图块**
 *  （比如一个 15x10 的关卡只要十几种图块），然后可以整体旋转缩放 ——
 *  这正是模式 2 存在的意义。
 * ===================================================================== */
#ifndef BG_H
#define BG_H

#include <tonc.h>

/* 地图尺寸（仿射层专用编码，单位是**格**）*/
typedef enum {
    AFF_16x16   = 0,    /* 128x128 像素 */
    AFF_32x32   = 1,    /* 256x256 */
    AFF_64x64   = 2,    /* 512x512 */
    AFF_128x128 = 3,    /* 1024x1024 */
} AffSize;

/* 建一个仿射层。
 *   bg   0..3（只有模式 1 的 BG2、模式 2 的 BG2/BG3 是仿射的，传错由调用方负责）
 *   bpp  4 或 8（仿射层两种都支持；8bpp 用 256 色整块调色板）
 *   cbb  图块数据放在第几个 16KB 块（0..3）
 *   sbb  地图数据放在第几个 2KB 块（0..31）
 *   size 地图尺寸（见 AffSize）
 *   prio 0..3，越小越靠前 */
void bg_affine_setup(int bg, int bpp, int cbb, int sbb, AffSize size, int prio);

/* 上传图块数据（8bpp：每块 64 字节；4bpp：每块 32 字节）。
 * **注意 VRAM 不支持 8 位写**，所以这里先在 RAM 里拼好再 16 位搬 —— 见 bg.c。*/
void bg_affine_tiles(int bg, const u8 *tiles, int n_tiles);

/* 上传地图（每格 1 字节的图块号）。pitch 是源数据每行多少格。*/
void bg_affine_map(int bg, const u8 *map, int w_cells, int h_cells, int pitch);

/* 变换：PA/PB/PC/PD 是 8.8 定点（256 = 1.0），(cx,cy) 是旋转缩放的中心（像素坐标）*/
void bg_affine_params(int bg, int pa, int pb, int pc, int pd, int cx, int cy);

/* 常用封装：按角度和缩放设置（angle 0..255 = 一圈，scale 256 = 原大小）*/
void bg_affine_rotate(int bg, int angle, int scale, int cx, int cy);

/* 滚动（仿射层的"滚动"其实是移动参考点，这里换算成像素偏移）*/
void bg_affine_scroll(int bg, int x, int y);

#endif /* BG_H */
