/* =====================================================================
 *  obj.c —— 硬件精灵实现
 *
 *  【OBJ 的显存和调色板在哪】
 *      图块：0x06010000 起，32 KB
 *              —— 但**位图模式（3/4/5）下只有 0x06014000 起的 16 KB**，
 *                 因为位图借用了下面那段（见 video.c 的说明）
 *      调色板：0x05000200 起，512 字节（256 色；4bpp 时分成 16 组 × 16 色）
 *      属性表（OAM）：0x07000000 起，128 项 × 8 字节
 *
 *  【1D 还是 2D 图块映射】
 *  DISPCNT 的第 6 位决定。这里用 **1D**（图块按顺序排），
 *  因为它和"一张图切成若干个 8x8"的直觉一致：第 n 个图块就在第 n 个位置。
 *  2D 映射要按 32 图块一行去算，属于历史包袱。
 * ===================================================================== */
#include "obj.h"
#include "video.h"

/* ---------------------------------------------------------------------
 * 合法尺寸表（硬件就这几档）
 * ------------------------------------------------------------------- */
static const SprSize SIZES[] = {
    {  8,  8, 0, 0,  1 },   /* 方形 */
    { 16, 16, 0, 1,  4 },
    { 32, 32, 0, 2, 16 },
    { 64, 64, 0, 3, 64 },
    { 16,  8, 1, 0,  2 },   /* 横长 */
    { 32,  8, 1, 1,  4 },
    { 32, 16, 1, 2,  8 },
    { 64, 32, 1, 3, 32 },
    {  8, 16, 2, 0,  2 },   /* 竖长 */
    {  8, 32, 2, 1,  4 },
    { 16, 32, 2, 2,  8 },
    { 32, 64, 2, 3, 32 },
};
#define SIZE_N (int)(sizeof(SIZES) / sizeof(SIZES[0]))

/* ---------------------------------------------------------------------
 * 状态：软件里记一份，最后统一写 OAM
 * ------------------------------------------------------------------- */
typedef struct {
    int  on;
    int  x, y;              /* 屏幕坐标（左上角）*/
    int  tile;
    const SprSize *size;
    int  pal, prio, hflip, vflip;
    int  affine;            /* -1 = 不用仿射 */
} ObjSlot;

static ObjSlot s_slot[OBJ_MAX];
static int     s_tiles_used;        /* 已经用掉的图块数 */
static int     s_bpp;               /* 当前用 4 还是 8 bpp（由第一次上传决定）*/

/* 图块打包的**暂存区**（EWRAM 的未初始化段，不占 ROM）。
 * 为什么需要它：GBA 的 VRAM **不支持 8 位写**，而 4bpp 图块最自然的拼法
 * 就是按字节拼半字节 —— 直接在显存里拼，写入会被丢掉。
 * 详见 spr_upload() 里的说明。 */
#define EWRAM_SCRATCH2 __attribute__((section(".sbss")))
static u8 EWRAM_SCRATCH2 s_stage[64 * 64];      /* 最多 64 个 8bpp 图块 */

/* OBJ 图块显存起始：位图模式只有 16 KB 可用 */
static u8 *obj_vram(void)
{
    return video_is_bitmap() ? (u8 *)0x06014000 : (u8 *)0x06010000;
}
static int obj_vram_bytes(void)
{
    return video_is_bitmap() ? 16 * 1024 : 32 * 1024;
}

/* 图块号的起点偏移 —— 这是个**很容易漏的硬件细节**。
 *
 * OAM 里的图块号是从 **0x06010000** 数起的，但位图模式（3/4/5）下
 * 我们只能把图块放在 0x06014000 之后（下面那段被位图占了）。
 * 所以位图模式下第一个可用图块号不是 0，而是 0x4000 ÷ 每块字节数：
 *      4bpp（32 字节/块）→ 512
 *      8bpp（64 字节/块）→ 256
 * 踩过：数据传到了 0x06014000（对的），图块号却给了 0（错的）——
 * 硬件跑去 0x06010000 读，那是位图区，结果精灵整个不显示。
 * 画面看着像"没画精灵"，其实是画了、读到垃圾。 */
static int obj_tile_bias(void)
{
    if (!video_is_bitmap()) return 0;
    return (s_bpp == 8) ? 256 : 512;
}

int spr_tiles_used(void) { return s_tiles_used; }
int spr_tiles_max(void)  { return obj_vram_bytes() / (s_bpp == 8 ? 64 : 32); }

void spr_init(void)
{
    s_tiles_used = 0;
    s_bpp = 4;
    for (int i = 0; i < OBJ_MAX; i++) s_slot[i].on = 0;
    spr_hide_all();
    spr_flush();
    /* **1D 图块映射**（DISPCNT 第 6 位 = 1）：
     * 图块按顺序排，"第 n 个 8x8"就在第 n 个位置 —— 和"一张图切成若干块"的直觉一致。
     * 2D 映射要按 32 图块一行去算地址，是历史包袱。
     *（踩过：DCNT_OBJ_2D 的值是 0，"清掉这一位"等于什么都没做 ✗
     *  要显式置 DCNT_OBJ_1D 才对。）*/
    REG_DISPCNT |= DCNT_OBJ_1D;
    REG_DISPCNT |= DCNT_OBJ;        /* 打开精灵层 */
}

void spr_hide_all(void)
{
    for (int i = 0; i < OBJ_MAX; i++) {
        s_slot[i].on = 0;
        oam_mem[i].attr0 = ATTR0_HIDE;
    }
}

const SprSize *spr_fit_size(int w, int h)
{
    /* 挑"装得下且面积最小"的一档。
     * 因为尺寸档位是离散的，10x22 会用 16x32（不是 16x16 装不下高）。*/
    const SprSize *best = NULL;
    int bestarea = 1 << 30;
    for (int i = 0; i < SIZE_N; i++) {
        if (SIZES[i].w < w || SIZES[i].h < h) continue;
        int area = SIZES[i].w * SIZES[i].h;
        if (area < bestarea) { bestarea = area; best = &SIZES[i]; }
    }
    return best;        /* 理论上一定找得到（最大 64x64）*/
}

/* ---------------------------------------------------------------------
 * 减色：16 位直接色 → 调色板下标
 *
 *  做法很朴素（够用就行，见 obj.h 的说明）：
 *    1. 统计这张图里出现最多的颜色（透明 key 不算）
 *    2. 取前 N-1 个当调色板（下标 0 留给透明）
 *    3. 其余像素就近映射到已选颜色
 *  渐变细腻的图会掉色；像素画、色块图基本无损。
 * ------------------------------------------------------------------- */
#define QUANT_MAX 256

static int color_index(u16 *pal, int n, u16 c)
{
    int r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
    int best = 0, bestd = 1 << 30;
    for (int i = 0; i < n; i++) {
        u16 p = pal[i];
        int dr = r - (p & 31), dg = g - ((p >> 5) & 31), db = b - ((p >> 10) & 31);
        int d = dr * dr + dg * dg + db * db;
        if (d < bestd) { bestd = d; best = i; if (!d) break; }
    }
    return best;
}

/* ---------------------------------------------------------------------
 * 上传：素材 → OBJ 图块
 * ------------------------------------------------------------------- */
int spr_upload(const GfxAsset *a, int bpp, int pal_bank)
{
    if (!a || !a->px) return -1;
    if (bpp != 8) bpp = 4;

    /* 4bpp 一组 16 色，8bpp 一共 256 色 */
    const int ncol = (bpp == 4) ? 16 : 256;
    u16 *pal = (u16 *)&pal_obj_mem[(bpp == 4) ? (pal_bank & 15) * 16 : 0];
    u16 chosen[QUANT_MAX];
    int nchosen = 0;

    if (s_tiles_used == 0) s_bpp = bpp;

    const SprSize *sz = spr_fit_size(a->w, a->h);
    if (!sz) return -1;
    int need = sz->tiles;
    if (s_tiles_used + need > spr_tiles_max()) return -1;   /* 显存不够 */

    /* ---- 1. 挑颜色：统计频次（对 16 位色做直接计数太大，
     *         用一个小的"已见颜色"表逐次查找，素材不大，够快）---- */
    u16 seen[QUANT_MAX];
    int cnt[QUANT_MAX];
    int nseen = 0;
    for (int i = 0; i < a->w * a->h && nseen < ncol; i++) {
        u16 c = a->px[i];
        if (c == a->key) continue;
        int f = 0;
        for (int k = 0; k < nseen; k++) if (seen[k] == c) { f = 1; cnt[k]++; break; }
        if (!f) { seen[nseen] = c; cnt[nseen] = 1; nseen++; }
    }
    /* 按频次从多到少选进调色板（下标 0 保留给透明）*/
    chosen[0] = 0;                       /* 透明色（实际不会画出来）*/
    nchosen = 1;
    for (int k = 0; k < nseen && nchosen < ncol; k++) {
        int bi = -1, bv = -1;
        for (int j = 0; j < nseen; j++)
            if (cnt[j] > bv) { bv = cnt[j]; bi = j; }
        if (bi < 0) break;
        chosen[nchosen++] = seen[bi];
        cnt[bi] = -1;                    /* 取走 */
    }
    for (int i = 0; i < nchosen; i++) pal[i] = chosen[i];

    /* ---- 2. 在 RAM 暂存区里拼图块，再用 16 位访问搬进显存 ----
     *
     * **为什么不能直接往显存里拼**：GBA 的 VRAM **不支持 8 位写** ✗
     * （OAM 和调色板同理）。4bpp 图块是"一个字节装两个像素"，
     * 最自然的写法就是拿 u8* 拼半字节 —— 而这样做**写入会被直接丢掉** ✗
     *
     * 这个坑非常阴：代码看着完全正确、`s_tiles_used` 照常自增、
     * 调色板（16 位写）也成功，只有图块显存是空的。
     * 画面表现是"精灵完全不显示"，靠截图根本猜不到原因 ——
     * 最后是**读内存**（OAM 属性正确、调色板有颜色、图块区全零）才定位到的。 */
    u8 *stage = s_stage;
    int tile_bytes = (bpp == 8) ? 64 : 32;
    int tw = sz->w >> 3;                 /* 横向几个图块 */

    for (int i = 0; i < need * tile_bytes; i++) stage[i] = 0;   /* RAM 里可以字节写 */

    for (int y = 0; y < a->h && y < sz->h; y++) {
        for (int x = 0; x < a->w && x < sz->w; x++) {
            u16 c = a->px[y * a->w + x];
            if (c == a->key) continue;                   /* 透明 */
            int ix = color_index(chosen, nchosen, c);
            int tx = x >> 3, ty = y >> 3;                /* 第几个图块 */
            int px = x & 7, py = y & 7;                  /* 块内坐标 */
            int tile_off = (ty * tw + tx) * tile_bytes;
            if (bpp == 8) {
                stage[tile_off + py * 8 + px] = (u8)ix;
            } else {
                u8 *p = stage + tile_off + py * 4 + (px >> 1);
                if (px & 1) *p = (u8)((*p & 0x0F) | (ix << 4));
                else        *p = (u8)((*p & 0xF0) | (ix & 0x0F));
            }
        }
    }

    /* 16 位访问搬进显存（VRAM 只支持 16/32 位访问）*/
    {
        u8 *dst = obj_vram() + (s_tiles_used * tile_bytes);
        u16 *d16 = (u16 *)dst;
        u16 *s16 = (u16 *)stage;
        int words = (need * tile_bytes) / 2;
        for (int i = 0; i < words; i++) d16[i] = s16[i];
    }

    int first = s_tiles_used;
    s_tiles_used += need;
    return first + obj_tile_bias();     /* 位图模式要加起点偏移，见 obj_tile_bias() */
}

/* ---------------------------------------------------------------------
 * 显示与隐藏
 * ------------------------------------------------------------------- */
void spr_show(int slot, int x, int y, int tile, const SprSize *size,
              int pal_bank, int prio, int hflip, int vflip)
{
    if (slot < 0 || slot >= OBJ_MAX || !size) return;
    ObjSlot *s = &s_slot[slot];
    s->on = 1; s->x = x; s->y = y; s->tile = tile; s->size = size;
    s->pal = pal_bank & 15; s->prio = prio & 3;
    s->hflip = hflip; s->vflip = vflip; s->affine = -1;
}

void spr_show_affine(int slot, int x, int y, int tile, const SprSize *size,
                     int pal_bank, int prio, int affine_id)
{
    spr_show(slot, x, y, tile, size, pal_bank, prio, 0, 0);
    if (slot >= 0 && slot < OBJ_MAX) s_slot[slot].affine = affine_id & 31;
}

void spr_hide(int slot)
{
    if (slot < 0 || slot >= OBJ_MAX) return;
    s_slot[slot].on = 0;
}

void spr_affine(int id, int sx, int sy, int angle)
{
    if (id < 0 || id > 31) return;
    /* 旋转矩阵：PA = cos/sx   PB = -sin/sx   PC = sin/sy   PD = cos/sy
     *
     * 两个定点格式要注意（踩过一次）：
     *   · lu_sin/lu_cos 的**角度**是 16 位表示一圈（0x10000 = 360°），
     *     我们的 angle 是 0..255，所以要左移 8 位
     *   · 它们的**返回值**是 4.12 定点（4096 = 1.0），
     *     而仿射寄存器要 8.8（256 = 1.0），所以要 >> 4
     *   · 缩放是放在**分母**上的：放大一倍要传 128 而不是 512 */
    int c = (int)(lu_cos((uint)angle << 8) >> 4);
    int s = (int)(lu_sin((uint)angle << 8) >> 4);
    if (sx == 0) sx = 256;
    if (sy == 0) sy = 256;
    obj_aff_mem[id].pa = (s16)( c * 256 / sx);
    obj_aff_mem[id].pb = (s16)(-s * 256 / sx);
    obj_aff_mem[id].pc = (s16)( s * 256 / sy);
    obj_aff_mem[id].pd = (s16)( c * 256 / sy);
}

/* ---------------------------------------------------------------------
 * 写 OAM
 *
 *  属性 0：y(8) + 仿射开关(1) + 双线性(1) + 禁用(2) + 模式(2) + 马赛克(1) + 色深(1) + 形状(2)
 *  属性 1：x(9) + 仿射组(5) + 水平翻转(1) + 垂直翻转(1) + 尺寸(2)
 *  属性 2：图块号(10) + 优先级(2) + 调色板组(4)
 * ------------------------------------------------------------------- */
void spr_flush(void)
{
    for (int i = 0; i < OBJ_MAX; i++) {
        ObjSlot *s = &s_slot[i];
        if (!s->on) { oam_mem[i].attr0 = ATTR0_HIDE; continue; }

        /* 属性 0：y | 对象类型 | 色深 | 形状 */
        u16 a0 = (u16)(s->y & 0xFF);
        a0 |= (s->affine >= 0) ? ATTR0_AFF : ATTR0_REG;
        if (s_bpp == 8) a0 |= ATTR0_8BPP;
        a0 |= (u16)(s->size->shape << 14);
        oam_mem[i].attr0 = a0;

        /* 属性 1：x | （仿射组号 或 翻转）| 尺寸 */
        u16 a1 = (u16)(s->x & 0x1FF);
        if (s->affine >= 0) {
            a1 |= (u16)(s->affine << ATTR1_AFF_ID_SHIFT);
        } else {
            if (s->hflip) a1 |= ATTR1_HFLIP;
            if (s->vflip) a1 |= ATTR1_VFLIP;
        }
        a1 |= (u16)(s->size->size << 14);
        oam_mem[i].attr1 = a1;

        /* 属性 2：图块号 | 优先级 | 调色板组 */
        oam_mem[i].attr2 = (u16)((s->tile & 0x3FF)
                                 | ((s->prio & 3) << ATTR2_PRIO_SHIFT)
                                 | ((s->pal & 15) << 12));
    }
}
