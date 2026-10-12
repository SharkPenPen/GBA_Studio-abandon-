/* =====================================================================
 *  obj.h —— 硬件精灵（OBJ）
 *
 *  【为什么值得单独做一层】
 *  OBJ 是 GBA 上**唯一在所有显示模式下都能用**的图形硬件：
 *  模式 0~5 全都能显示精灵，而且完全由硬件合成 —— CPU 一个像素都不用碰。
 *  我们的立绘/角色一直是软件逐像素贴的（贴完还要小心擦干净，
 *  踩过"走一路拖一串残影"的坑）。改用 OBJ 之后：
 *      · 画一个角色 = 写 3 个 16 位属性（OAM 里 8 字节），不是 1 万个像素
 *      · **不需要擦除** —— 精灵浮在背景上，移开时背景本来就还在
 *      · 可以做几十上百个（128 个精灵，每行最多 32 个）
 *
 *  【硬限制，必须知道】
 *  1. 精灵尺寸只能是固定几档：8x8 / 16x16 / 32x32 / 64x64，
 *     以及 16x8 / 32x8 / 32x16 / 64x32 / 8x16 / 8x32 这些长方形。
 *     **没有 10x22 这种尺寸** —— 所以上传时会自动选"装得下的最小一档"，
 *     内容放左上角，右边/下边留空（spr_fit_size() 就是干这个的）。
 *  2. 4bpp 精灵用 16 色一组（16 组可选），8bpp 用 256 色。
 *     我们的素材是 16 位直接色，所以要**减色**：先把出现最多的若干颜色
 *     挑出来当调色板，其余像素就近映射。颜色多且渐变细腻的图会掉色。
 *  3. 图块显存：模式 0/1/2 下 OBJ 有 32 KB（4bpp = 1024 个 8x8），
 *     **位图模式（3/4/5）下只剩 16 KB**（512 个）—— 因为位图借用了下面那段。
 *     所以位图模式下能放的精灵数量是图块模式的一半。
 *  4. 精灵在屏幕外/被关掉时要把 y 设到 160 之外或置"禁用"位，
 *     否则会在边缘露出半截。
 * ===================================================================== */
#ifndef OBJ_H
#define OBJ_H

#include <tonc.h>
#include "gfx_assets.h"

#define OBJ_MAX      128        /* 硬件上限 */
#define OBJ_PAL_MAX  16         /* 4bpp 的调色板组数（每组 16 色）*/

/* 一档合法的精灵尺寸（按 OBJ 的 shape/size 编码）*/
typedef struct {
    int w, h;
    int shape;      /* 0=方形 1=横长 2=竖长 */
    int size;       /* 0..3 */
    int tiles;      /* 占几个 8x8 图块 */
} SprSize;

void spr_init(void);                    /* 清 OAM、关掉所有精灵 */
void spr_hide_all(void);

/* 把一张素材的像素传成 OBJ 图块，返回起始图块号（-1 = 显存不够）。
 *   bpp       4 或 8
 *   pal_bank  4bpp 时用哪一组 16 色（0..15）；会把这组颜色写进 OBJ 调色板
 * 返回的 tile 号和 spr_show() 里要用的一致。 */
int  spr_upload(const GfxAsset *a, int bpp, int pal_bank);

/* 显示/移动一个精灵。
 *   slot  0..127
 *   size  用上面 spr_fit_size() 得到的档位
 * 内容按左上角对齐（上传时也是这么放的）。 */
void spr_show(int slot, int x, int y, int tile, const SprSize *size,
              int pal_bank, int prio, int hflip, int vflip);
void spr_hide(int slot);

/* 按素材尺寸挑一档"装得下的最小尺寸" */
const SprSize *spr_fit_size(int w, int h);

/* 仿射（旋转/缩放）：最多 32 组矩阵，精灵可选其中一组。
 *   sx/sy  缩放（256 = 原大小，256*2 = 放大一倍）
 *   angle  旋转角度（0..255 对应一圈；256 = 360 度）*/
void spr_affine(int id, int sx, int sy, int angle);
void spr_show_affine(int slot, int x, int y, int tile, const SprSize *size,
                     int pal_bank, int prio, int affine_id);

/* 把软件里设好的状态写进 OAM（每帧末尾调一次）*/
void spr_flush(void);

/* 用了多少图块（调试/容量检查用）*/
int  spr_tiles_used(void);
int  spr_tiles_max(void);

#endif /* OBJ_H */
