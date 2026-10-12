/* =====================================================================
 *  surface.c —— 画布实现
 *
 *  三种后端的差别只在"一个像素写到哪里"这一件事上，其余绘制逻辑完全共用。
 *  所以下面把写像素收成两个小函数（sf_put / sf_put_index），
 *  上层（矩形、描边、精灵、背景）一份代码通吃。
 *
 *  【图块后端怎么工作】
 *      在 RAM 里维护一张 w*h 的**下标图**（模式 3 的 76,800 B 换成 38,400 B）
 *      每个屏幕格（8x8）对应显存里**专属的一个图块**（不做图块去重）：
 *          格 (cx,cy) → 图块号 = cy*32 + cx  → 地图条目也写这个号
 *      写像素时把所在格标脏；每帧结束时 sf_flush() 只把**脏格**重编码传上去。
 *      600 个格子 × 64 字节 = 38.4 KB，BG 区 64 KB 放得下；
 *      地图 32x32 条目 × 2 字节 = 2 KB，放在后面的屏幕块里。
 *
 *      为什么不做图块去重（相同内容共用一个图块）：省显存，但每次改动都要
 *      重算引用、还得处理"被共享的图块不能随便改"。ROM 才 500 KB、
 *      显存也够用，先要的是**可预测**：一格一块，改哪传哪。
 * ===================================================================== */
#include "surface.h"
#include "video.h"

/* 放 .sbss：链接脚本里这是"EWRAM 里的未初始化段" —— **不占 ROM**。
 * 用 EWRAM_DATA 的话这些临时缓冲会被当成初始化数据塞进 ROM
 *（踩过：ROM 从 497 KB 涨到 571 KB，就为了几块根本不需要初值的缓冲）。*/
#define EWRAM_SCRATCH __attribute__((section(".sbss")))

static u8 EWRAM_SCRATCH s_lut[32768];   /* 三后端共用的查色表 */
static Surface EWRAM_SCRATCH s_direct;
static Surface EWRAM_SCRATCH s_indexed;
static Surface EWRAM_SCRATCH s_tiles;
static Surface *s_cur = NULL;

/* ---- 图块后端的 RAM 下标图（240x160 上限）---- */
static u8 EWRAM_SCRATCH s_tile_pixels[SF_MAX_W * SF_MAX_H];

/* ---------------------------------------------------------------------
 * 颜色 → 调色板下标
 *
 *  首次遇到某颜色时线性找最接近的一个（256 次比较），之后走缓存。
 *  距离用"分量的平方和"，不做开方 —— 比较大小不需要真距离。
 *
 *  查色表**三个后端共用一张**：同一时刻只有一个画布在画。
 *  （第一版每个画布各带一张 32 KB 的表，三份直接把 IWRAM 撑爆 10 万字节。）
 * ------------------------------------------------------------------- */
u8 sf_index(Surface *s, u16 color)
{
    u8 cached = s_lut[color & 0x7FFF];
    if (cached) return (u8)(cached - 1);

    int r = color & 31, g = (color >> 5) & 31, b = (color >> 10) & 31;
    int best = 0, bestd = 1 << 30;
    for (int i = 0; i < 256; i++) {
        u16 c = s->pal[i];
        int dr = r - (c & 31), dg = g - ((c >> 5) & 31), db = b - ((c >> 10) & 31);
        int d = dr * dr + dg * dg + db * db;
        if (d < bestd) { bestd = d; best = i; if (!d) break; }
    }
    s_lut[color & 0x7FFF] = (u8)(best + 1);
    return (u8)best;
}

/* ---------------------------------------------------------------------
 * 写像素：三种后端的分岔点
 * ------------------------------------------------------------------- */
static inline void sf_put(Surface *s, int x, int y, u16 color)
{
    if ((unsigned)x >= (unsigned)s->w || (unsigned)y >= (unsigned)s->h) return;
    if (s->kind == SF_DIRECT) {
        s->px[y * s->stride + x] = color;
    } else {
        s->idx[y * s->stride + x] = sf_index(s, color);
        if (s->kind == SF_TILES)
            s->dirty[(y >> 3) * s->cw + (x >> 3)] = 1;
    }
}

/* ---------------------------------------------------------------------
 * 建画布
 * ------------------------------------------------------------------- */
static void sf_init_common(Surface *s, SfKind k, int w, int h)
{
    s->kind = k;
    s->w = w; s->h = h; s->stride = w;
    s->px = NULL; s->idx = NULL; s->pal = NULL;
    s->cw = (w + 7) >> 3;
    s->ch = (h + 7) >> 3;
    for (int i = 0; i < SF_MAX_CW * SF_MAX_CH; i++) s->dirty[i] = 0;
    s->bg = 0; s->tiles = NULL; s->map = NULL; s->map_pitch = 32;
}

Surface *sf_bitmap_direct(int w, int h, u16 *vram)
{
    sf_init_common(&s_direct, SF_DIRECT, w, h);
    s_direct.px = vram;
    return &s_direct;
}

Surface *sf_bitmap_indexed(int w, int h, u8 *vram, const u16 *pal)
{
    sf_init_common(&s_indexed, SF_INDEXED, w, h);
    s_indexed.idx = vram;
    s_indexed.pal = pal;
    return &s_indexed;
}

Surface *sf_tiles(int w, int h, int bg, int cb_base, int sb_base)
{
    sf_init_common(&s_tiles, SF_TILES, w, h);
    s_tiles.idx = s_tile_pixels;
    s_tiles.bg = bg;
    /* 图块数据区 / 地图区都在 BG 显存里，按 16KB / 2KB 块定位 */
    s_tiles.tiles = (u8 *)vid_mem + cb_base * 0x4000;
    s_tiles.map = (u16 *)((u8 *)vid_mem + sb_base * 0x800);
    s_tiles.map_pitch = 32;
    return &s_tiles;
}

/* ---------------------------------------------------------------------
 * 按当前显示模式自动选一个后端
 * ------------------------------------------------------------------- */
void sf_forget_colors(void)
{
    for (int i = 0; i < 32768; i++) s_lut[i] = 0;
}

Surface *sf_auto(void)
{
    const VideoCaps *c = video_caps(video_mode());
    if (!c->is_bitmap) {
        /* 图块模式。**模式 2 是个例外**：它只有两个**仿射**层，没有普通图块层 ✗
         * 而这里的图块画布用的是普通文本层（BG0 + 8bpp 图块 + 32x32 地图）。
         * 仿射层的地图格式、参数寄存器（PA/PB/PC/PD + 参考点）都不一样，
         * 还没做 —— 所以模式 2 下会**画不出东西**。
         *
         * 与其静默出错，不如明确说清楚：带上 GAL_MODE2_AFFINE 才允许进这个分支，
         * 没做的时候走直色位图那条路（模式 2 下没有位图，会在屏幕外，看得见"没画"）。 */
#ifdef GAL_MODE2_AFFINE
        if (c->aff_bgs && !c->reg_bgs) {
            /* 仿射图块画布（尚未实现）—— 占位，避免误以为能用 */
        }
#endif
        /* 模式 2 没有普通图块层：这里的 BG0 在模式 2 下**不存在** ✗
         * 图块画布会画不出来。明确提示，不做静默失败。 */
        if (c->reg_bgs == 0)
            return sf_bitmap_direct(c->w, c->h, video_vram());   /* 退到直色（模式 2 下无位图，等于空画面）*/
        Surface *s = sf_tiles(c->w, c->h, 0, 0, 25);
        /* 调色板显示：必须先铺一张调色板，否则画面全黑 */
        sf_build_default_palette((u16 *)pal_bg_mem);
        s->pal = (const u16 *)pal_bg_mem;
        video_bg_char_base(0, 0);
        video_bg_screen_base(0, 25);
        video_bg_enable(0, 1, 0);
        return s;
    }
    if (c->bpp == 8) {
        /* 8bpp（模式 4）：同样需要调色板；两页由 video.c 管 */
        sf_build_default_palette((u16 *)pal_bg_mem);
        return sf_bitmap_indexed(c->w, c->h, video_vram8(), (const u16 *)pal_bg_mem);
    }
    return sf_bitmap_direct(c->w, c->h, video_vram());
}

Surface *sf_current(void) { return s_cur; }
void sf_set_current(Surface *s) { s_cur = s; }

/* ---------------------------------------------------------------------
 * 默认调色板：给图块 / 8bpp 后端用
 *
 *  图块模式和 8bpp 都是**调色板**显示（256 色），必须有人先把调色板填上，
 *  否则画出来是一片黑。最省事又够看的办法是铺一个 RGB 立方：
 *  6×8×6 = 288 > 256，所以取 6×6×6 = 216 色，剩下 40 个留给灰阶
 *（文字和 UI 大量用灰阶，给它们专用的、间距均匀的灰）。
 *
 *  这是"通用默认值"，不是最优解：等真的用图块模式做游戏时，
 *  应该由美术管线按素材生成**自适应调色板**（那才是 256 色该有的用法）。
 * ------------------------------------------------------------------- */
void sf_build_default_palette(u16 *pal)
{
    int i = 0;
    /* 6×6×6 色立方：每档 0/6/12/18/24/31（用 31 而不是 30，让纯白在表里）*/
    static const int lv[6] = { 0, 6, 12, 18, 24, 31 };
    for (int r = 0; r < 6; r++)
        for (int g = 0; g < 6; g++)
            for (int b = 0; b < 6; b++)
                pal[i++] = (u16)(lv[r] | (lv[g] << 5) | (lv[b] << 10));
    /* 剩下的填 40 级均匀灰阶（黑→白）*/
    for (; i < 256; i++) {
        int v = (i - 216) * 31 / 39;
        pal[i] = (u16)(v | (v << 5) | (v << 10));
    }
}

/* ---------------------------------------------------------------------
 * 绘制：一份代码，三种后端
 * ------------------------------------------------------------------- */
void sf_clear(Surface *s, u16 color)
{
    if (s->kind == SF_DIRECT) {
        for (int i = 0; i < s->w * s->h; i++) s->px[i] = color;
    } else {
        u8 ix = sf_index(s, color);
        for (int i = 0; i < s->w * s->h; i++) s->idx[i] = ix;
        for (int i = 0; i < SF_MAX_CW * SF_MAX_CH; i++) s->dirty[i] = 1;
    }
}

void sf_fill(Surface *s, int x, int y, int w, int h, u16 color)
{
    if (w <= 0 || h <= 0) return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > s->w) w = s->w - x;
    if (y + h > s->h) h = s->h - y;
    if (w <= 0 || h <= 0) return;

    if (s->kind == SF_DIRECT) {
        for (int r = 0; r < h; r++) {
            u16 *p = s->px + (y + r) * s->stride + x;
            for (int i = 0; i < w; i++) p[i] = color;
        }
        return;
    }

    u8 ix = sf_index(s, color);
    for (int r = 0; r < h; r++) {
        u8 *p = s->idx + (y + r) * s->stride + x;
        for (int i = 0; i < w; i++) p[i] = ix;
    }
    if (s->kind == SF_TILES) {
        for (int cy = y >> 3; cy <= (y + h - 1) >> 3; cy++)
            for (int cx = x >> 3; cx <= (x + w - 1) >> 3; cx++)
                s->dirty[cy * s->cw + cx] = 1;
    }
}

void sf_border(Surface *s, int x, int y, int w, int h, u16 color)
{
    sf_fill(s, x, y, w, 1, color);
    sf_fill(s, x, y + h - 1, w, 1, color);
    sf_fill(s, x, y, 1, h, color);
    sf_fill(s, x + w - 1, y, 1, h, color);
}

void sf_draw_sprite(Surface *s, const GfxAsset *a, int dx, int dy)
{
    if (!a || !a->px) return;
    const u16 key = a->key;

    int sy0 = 0, sy1 = a->h;
    if (dy < 0) sy0 = -dy;
    if (dy + sy1 > s->h) sy1 = s->h - dy;
    if (sy1 <= sy0) return;
    int sx0 = 0, sx1 = a->w;
    if (dx < 0) sx0 = -dx;
    if (dx + sx1 > s->w) sx1 = s->w - dx;
    if (sx1 <= sx0) return;

    for (int row = sy0; row < sy1; row++) {
        const u16 *src = a->px + row * a->w;
        int y = dy + row;
        int x = sx0;
        while (x < sx1) {
            if (src[x] == key) { x++; continue; }       /* 透明跳过 */
            int start = x;
            while (x < sx1 && src[x] != key) x++;       /* 找一整段实体 */
            if (s->kind == SF_DIRECT) {
                u16 *dst = s->px + y * s->stride + dx;
                for (int i = start; i < x; i++) dst[i] = src[i];
            } else {
                for (int i = start; i < x; i++)
                    sf_put(s, dx + i, y, src[i]);
            }
        }
    }
}

void sf_draw_bg(Surface *s, const GfxAsset *bg)
{
    if (!bg || !bg->px) return;
    int rows = (bg->h < s->h) ? bg->h : s->h;
    int cols = (bg->w < s->w) ? bg->w : s->w;
    for (int y = 0; y < rows; y++) {
        const u16 *src = bg->px + y * bg->w;
        if (s->kind == SF_DIRECT) {
            u16 *dst = s->px + y * s->stride;
            for (int x = 0; x < cols; x++) dst[x] = src[x];
        } else {
            for (int x = 0; x < cols; x++) sf_put(s, x, y, src[x]);
        }
    }
}

void sf_restore(Surface *s, const GfxAsset *bg, int x, int y, int w, int h)
{
    if (!bg || !bg->px) return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > s->w) w = s->w - x;
    if (y + h > s->h) h = s->h - y;
    if (w <= 0 || h <= 0) return;

    for (int r = 0; r < h; r++) {
        const u16 *src = bg->px + (y + r) * bg->w + x;
        if (s->kind == SF_DIRECT) {
            u16 *dst = s->px + (y + r) * s->stride + x;
            for (int i = 0; i < w; i++) dst[i] = src[i];
        } else {
            for (int i = 0; i < w; i++) sf_put(s, x + i, y + r, src[i]);
        }
    }
}

/* ---------------------------------------------------------------------
 * 图块后端：脏格 → 图块 → 显存
 *
 *  8bpp 图块 = 8 行 × 8 字节（一行 8 个下标）＝ 64 字节。
 *  地图条目：低 10 位是图块号，8bpp 模式下没有调色板分组。
 * ------------------------------------------------------------------- */
void sf_flush(Surface *s)
{
    if (s->kind != SF_TILES || !s->tiles || !s->map) return;

    for (int cy = 0; cy < s->ch; cy++) {
        for (int cx = 0; cx < s->cw; cx++) {
            if (!s->dirty[cy * s->cw + cx]) continue;
            s->dirty[cy * s->cw + cx] = 0;

            int tile = cy * s->map_pitch + cx;      /* 一格一个专属图块 */
            u8 *dst = s->tiles + tile * 64;
            int px0 = cx << 3, py0 = cy << 3;

            for (int r = 0; r < 8; r++) {
                int y = py0 + r;
                u8 *row = dst + r * 8;
                if (y >= s->h) { for (int i = 0; i < 8; i++) row[i] = 0; continue; }
                for (int i = 0; i < 8; i++) {
                    int x = px0 + i;
                    row[i] = (x < s->w) ? s->idx[y * s->stride + x] : 0;
                }
            }
            s->map[cy * s->map_pitch + cx] = (u16)tile;
        }
    }
}
