/* =====================================================================
 *  bg.c —— 仿射图块层实现
 *
 *  【三个必须记住的硬件细节】
 *
 *  1. **地图条目只有 1 字节** → 图块号 0..255，最多 256 个图块 ✗
 *     所以"一格一个图块"的画布方案放不下（240x160 要 600 个）。
 *     仿射层适合"少量图块 + 大地图"。
 *
 *  2. **VRAM 不支持 8 位写**（和 OBJ 那次同一个坑）✗
 *     图块和地图都必须先在 RAM 里拼好，再用 16 位访问搬进去。
 *
 *  3. **参考点是"屏幕上的哪个像素对应地图上的哪个点"**：
 *     硬件按 `地图坐标 = (屏幕坐标 - 参考点)` 反着算。
 *     想做"以屏幕中心为轴旋转"，参考点就写屏幕中心 + 地图偏移。
 *     这一步很容易反，表现是"画面转到屏幕外面去了"。
 * ===================================================================== */
#include "bg.h"

/* 拼图块/地图用的暂存区（EWRAM 未初始化段，不占 ROM）*/
#define EWRAM_SCRATCH3 __attribute__((section(".sbss")))
static u8 EWRAM_SCRATCH3 s_stage[256 * 64];     /* 256 块 × 8bpp 64 字节 */
static u8 EWRAM_SCRATCH3 s_row[128];            /* 地图一行的暂存（最多 128 格）*/

static u8 *vram(void) { return (u8 *)vid_mem; }

/* 先把字节拼进 RAM 暂存区，再用 16 位搬到显存 */
static void vram_write_bytes(u8 *dst, const u8 *src, int n)
{
    u16 *d16 = (u16 *)dst;
    const u16 *s16 = (const u16 *)src;
    int words = n / 2;
    for (int i = 0; i < words; i++) d16[i] = s16[i];
}

void bg_affine_setup(int bg, int bpp, int cbb, int sbb, AffSize size, int prio)
{
    if (bg < 2 || bg > 3) return;        /* 只有 BG2/BG3 能当仿射层 */

    /* 注意：**没有"仿射"这个标志位** —— 一层是不是仿射，
     * 由"显示模式 + 层号"决定（模式 1 的 BG2、模式 2 的 BG2/BG3）。
     * 这里只设优先级、图块基址、地图基址、色深、地图尺寸。 */
    static const u16 SZ[4] = { BG_AFF_16x16, BG_AFF_32x32,
                               BG_AFF_64x64, BG_AFF_128x128 };
    u16 cnt = (u16)(BG_PRIO(prio & 3) | BG_CBB(cbb & 3) | BG_SBB(sbb & 31));
    if (bpp == 8) cnt |= 0x0080;         /* 8bpp 位 */
    cnt |= SZ[size & 3];
    REG_BGCNT[bg] = cnt;

    /* 打开这一层 */
    REG_DISPCNT |= (u16)(DCNT_BG0 << bg);

    /* 单位矩阵 + 参考点归零 */
    bg_affine_params(bg, 256, 0, 0, 256, 0, 0);
}

void bg_affine_tiles(int bg, const u8 *tiles, int n_tiles)
{
    if (bg < 2 || bg > 3) return;
    if (n_tiles > 256) n_tiles = 256;               /* 地图条目只有 1 字节 */
    int bytes = n_tiles * 64;                       /* 8bpp：一块 64 字节 */
    if (bytes > (int)sizeof(s_stage)) bytes = sizeof(s_stage);

    /* 先复制到 RAM 暂存区：**VRAM 不支持 8 位写**，
     * 而且调用方的数据可能在 ROM 里、也不保证 4 字节对齐，统一过一遍最省心。*/
    for (int i = 0; i < bytes; i++) s_stage[i] = tiles[i];

    /* 写到 BGxCNT 指定的那个图块块（和地图一样从寄存器里读回来，
     * 免得同一个数要在两处写，写岔了非常难查）*/
    int cbb = (REG_BGCNT[bg] & BG_CBB_MASK) >> 2;
    vram_write_bytes(vram() + cbb * 0x4000, s_stage, bytes);
}

void bg_affine_map(int bg, const u8 *map, int w_cells, int h_cells, int pitch)
{
    if (bg < 2 || bg > 3) return;
    /* 地图基址 = 显存 + SBB × 2KB。从 BGxCNT 里把它读回来，
     * 免得调用方要在两处写同一个数（写岔了非常难查）。*/
    u16 cnt = REG_BGCNT[bg];
    int sbb = (cnt & BG_SBB_MASK) >> 8;
    u8 *dst = vram() + sbb * 0x800;

    /* **行距 = 地图宽度**（16/32/64/128 格），不是固定的 128 ✗
     * 踩过：我按"仿射地图固定 128 字节一行"去写，于是 32x32 的地图
     * 每隔 128 字节才写 32 个字节 → 一路写到 4096 字节处，
     * **冲出这一块的 2KB 边界** ✗ 把后面的显存踩了（表现是整机跑飞、
     * DISPCNT 都变成没设过的值）。
     * 仿射层的地图就是"宽 × 高"个连续字节，行距等于宽度。 */
    int side = 16 << ((cnt >> 14) & 3);      /* 16 / 32 / 64 / 128 格 */
    if (side > 128) side = 128;

    int rows = (h_cells > side) ? side : h_cells;
    int cols = (w_cells > side) ? side : w_cells;
    int src_pitch = (pitch > 0) ? pitch : w_cells;

    for (int y = 0; y < rows; y++) {
        for (int x = 0; x < cols; x++)
            s_row[x] = map[y * src_pitch + x];
        vram_write_bytes(dst + y * side, s_row, cols);
    }
}

void bg_affine_params(int bg, int pa, int pb, int pc, int pd, int cx, int cy)
{
    if (bg < 2 || bg > 3) return;
    REG_BG_AFFINE[bg - 2].pa = (s16)pa;
    REG_BG_AFFINE[bg - 2].pb = (s16)pb;
    REG_BG_AFFINE[bg - 2].pc = (s16)pc;
    REG_BG_AFFINE[bg - 2].pd = (s16)pd;
    /* 参考点是 28 位定点（整数部分 20 位），直接写像素值即可 */
    REG_BG_AFFINE[bg - 2].dx = cx;
    REG_BG_AFFINE[bg - 2].dy = cy;
}

void bg_affine_rotate(int bg, int angle, int scale, int cx, int cy)
{
    /* lu_sin/lu_cos：角度是 16 位一圈（0x10000 = 360°），返回值是 4.12 定点。
     * 我们的 angle 是 0..255 一圈 → 左移 8 位；4.12 → 8.8 要 >> 4。 */
    int c = (int)(lu_cos((uint)angle << 8) >> 4);
    int s = (int)(lu_sin((uint)angle << 8) >> 4);
    if (scale == 0) scale = 256;
    /* 缩放放在分母上：放大一倍传 128 */
    bg_affine_params(bg,
                     c * 256 / scale, -s * 256 / scale,
                     s * 256 / scale,  c * 256 / scale,
                     cx, cy);
}

void bg_affine_scroll(int bg, int x, int y)
{
    if (bg < 2 || bg > 3) return;
    /* 仿射层没有 HOFS/VOFS，滚动等于把参考点挪过去 */
    REG_BG_AFFINE[bg - 2].dx = x;
    REG_BG_AFFINE[bg - 2].dy = y;
}
