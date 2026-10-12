/* =====================================================================
 *  video.c —— 六种显示模式的实现
 *
 *  【显存怎么分】
 *      0x06000000 ┬ 图块数据 / 位图      64 KB
 *      0x06010000 ┼ OBJ 图块             32 KB  ← 位图模式下被挤到只剩 16 KB
 *      0x06018000 ┴ 调色板                1 KB  （BG 512 B + OBJ 512 B）
 *
 *  模式 3/5 的 16bpp 位图是 240x160x2 = 76,800 字节，比 BG 区的 64 KB 还大 ——
 *  所以它**借用** OBJ 图块区的前半段（0x06000000~0x06012BFF），
 *  OBJ 图块被挤到 0x06014000 之后，只剩 16 KB。
 *  这也正是"模式 3 做不到双缓冲"的原因：96 KB 装不下两块 76,800 的画布。
 *  模式 4 是 8bpp（38,400 B/页），两页 = 76,800 B，正好塞得下 → 能翻页。
 * ===================================================================== */
#include "video.h"

/* 模式能力表：一个模式一行，代码里查它，不要写 if (mode == 3) */
static const VideoCaps CAPS[VMODE_N] = {
    /* name       位图  bpp   w    h  页  普通层 仿射层 */
    { "mode 0",     0,   0, 240, 160, 1,   4,    0 },   /* 4 个图块层 */
    { "mode 1",     0,   0, 240, 160, 1,   2,    1 },   /* 2 图块 + 1 仿射 */
    { "mode 2",     0,   0, 240, 160, 1,   0,    2 },   /* 2 仿射 */
    { "mode 3",     1,  16, 240, 160, 1,   0,    0 },   /* 16bpp 位图，单缓冲 */
    { "mode 4",     1,   8, 240, 160, 2,   0,    0 },   /* 8bpp 位图，2 页 */
    { "mode 5",     1,  16, 160, 128, 1,   0,    0 },   /* 16bpp 位图，小屏 */
};

static VideoMode s_mode = VMODE_3;
static int s_page;                              /* 模式 4 的当前页 */

/* 模式 4 的两页间距。
 *
 * **是 0xA000 = 40,960，不是 240*160 = 38,400** ✗
 * 踩过：按 38,400 算，第二页会从第一页末尾提前 1,600 字节处开始，
 * 两页互相踩 → 画面一片花屏。GBA 的位图页按 0xA000 对齐，
 * 240x160 的 8bpp 只用 38,400，剩下的是页内填充。 */
#define PAGE8_STRIDE 0xA000
#define PAGE8_BYTES   (240 * 160)

const VideoCaps *video_caps(VideoMode m)
{
    if (m < 0 || m >= VMODE_N) m = VMODE_3;
    return &CAPS[m];
}

VideoMode video_mode(void)   { return s_mode; }
int video_w(void)            { return CAPS[s_mode].w; }
int video_h(void)            { return CAPS[s_mode].h; }
int video_is_bitmap(void)    { return CAPS[s_mode].is_bitmap; }
int video_pages(void)        { return CAPS[s_mode].pages; }

/* ---------------------------------------------------------------------
 * 层复位：换模式时先把所有层关掉、清一次屏
 *
 *  不清的话会看到上一模式的残留（显存内容还在），切换瞬间很脏。
 * ------------------------------------------------------------------- */
void video_reset_layers(void)
{
    /* 先关掉所有 BG 和 OBJ，只留一个"什么都没有"的画面 */
    REG_DISPCNT = DCNT_MODE(s_mode);
    for (int bg = 0; bg < 4; bg++) {
        REG_BGCNT[bg] = 0;
        (&REG_BG0HOFS)[(bg) * 2] = 0;
        (&REG_BG0HOFS)[(bg) * 2 + 1] = 0;
    }
    /* 清调色板（图块模式的颜色全在调色板里，不清会串色）*/
    for (int i = 0; i < 256; i++) {
        pal_bg_mem[i] = 0;
        pal_obj_mem[i] = 0;
    }
}

/* ---------------------------------------------------------------------
 * 初始化 / 切换
 * ------------------------------------------------------------------- */
void video_set_mode(VideoMode m)
{
    if (m < 0 || m >= VMODE_N) m = VMODE_3;
    s_mode = m;
    s_page = 0;
    video_reset_layers();

    const VideoCaps *c = &CAPS[m];
    if (c->is_bitmap) {
        /* 位图模式：打开承载画面的那一层。
         *   模式 3/4/5 的位图都在 BG2 上（硬件规定）*/
        REG_DISPCNT = DCNT_MODE(m) | DCNT_BG2;
        if (m == VMODE_3) {
            /* 16bpp：整屏 76,800 B 占满 0x06000000 起的区域 */
        } else if (m == VMODE_4) {
            /* 8bpp：两页共 76,800 B，用 BG2 的页位（DISPCNT bit4）选页 */
            REG_DISPCNT &= ~DCNT_PAGE;
        } else {
            /* 模式 5：160x128 的 16bpp，占 40,960 B */
        }
    } else {
        /* 图块模式：先把 BG0 打开（默认全屏文字层，其他层由调用方按需开）
         * 详细的图块/地图布局由 bg.c 设置。 */
        REG_DISPCNT = DCNT_MODE(m);
        /* 图块画布用 **8bpp** 图块（一格 64 字节）：256 色足够放地图和文字，
         * 而 4bpp 只有 16 色 —— 文字一上去就花。（曾经按 4bpp 设过，
         * 因为测试地图全是纯色块，4bpp/8bpp 读出来一样，看不出问题。）*/
        REG_BG0CNT = BG_PRIO(3) | BG_CBB(0) | BG_SBB(25) | BG_8BPP | BG_REG_32x32;
    }
}

void video_init(VideoMode m)
{
    /* 上电默认模式 3：和重构前行为一致（现有画面逐像素不变）*/
    video_set_mode(m);
}

/* ---------------------------------------------------------------------
 * 位图模式：帧缓冲与翻页
 * ------------------------------------------------------------------- */
u16 *video_vram(void)
{
    /* 16bpp 位图从 0x06000000 开始（模式 3/5）*/
    return (u16 *)vid_mem;
}

u8 *video_vram8(void)
{
    /* 8bpp（模式 4）：两页紧挨着放 */
    return (u8 *)vid_mem + s_page * PAGE8_STRIDE;
}

void video_page_flip(void)
{
    if (CAPS[s_mode].pages < 2) return;      /* 只有模式 4 能翻 */
    s_page ^= 1;
    /* 页选择在 DISPCNT 的第 4 位 */
    if (s_page) REG_DISPCNT |=  DCNT_PAGE;
    else        REG_DISPCNT &= ~DCNT_PAGE;
}

void video_page_clear(u16 color)
{
    if (CAPS[s_mode].is_bitmap && CAPS[s_mode].bpp == 8) {
        /* 8bpp：颜色是调色板下标 —— 调用方传进来的 u16 低字节当下标用。
         * **两页都要清**：翻页只是换"显示哪一页"，另一页里还留着上次的内容，
         * 不清的话翻过去会闪一下旧画面/黑屏（第一次就是这么翻出黑屏的）。 */
        for (int pg = 0; pg < 2; pg++) {
            u8 *p = (u8 *)vid_mem + pg * PAGE8_STRIDE;
            for (int i = 0; i < 240 * 160; i++) p[i] = (u8)color;
        }
    } else if (CAPS[s_mode].is_bitmap) {
        u16 *p = video_vram();
        u32 pair = ((u32)color << 16) | color;
        for (int i = 0; i < (CAPS[s_mode].w * CAPS[s_mode].h) / 2; i++)
            ((u32 *)p)[i] = pair;
    }
}

/* ---------------------------------------------------------------------
 * 图块模式：背景层控制
 * ------------------------------------------------------------------- */
void video_bg_enable(int bg, int on, int priority)
{
    if (bg < 0 || bg > 3) return;
    if (!on) {
        REG_DISPCNT &= ~(DCNT_BG0 << bg);
        return;
    }
    REG_DISPCNT |= (DCNT_BG0 << bg);
    u16 cnt = REG_BGCNT[bg] & ~BG_PRIO_MASK;
    REG_BGCNT[bg] = cnt | BG_PRIO(priority & 3);
}

void video_bg_scroll(int bg, int x, int y)
{
    if (bg < 0 || bg > 3) return;
    (&REG_BG0HOFS)[(bg) * 2] = (u16)x;
    (&REG_BG0HOFS)[(bg) * 2 + 1] = (u16)y;
}

void video_bg_char_base(int bg, int block)
{
    if (bg < 0 || bg > 3) return;
    REG_BGCNT[bg] = (REG_BGCNT[bg] & ~BG_CBB_MASK) | BG_CBB(block & 3);
}

void video_bg_screen_base(int bg, int block)
{
    if (bg < 0 || bg > 3) return;
    REG_BGCNT[bg] = (REG_BGCNT[bg] & ~BG_SBB_MASK) | BG_SBB(block & 31);
}

void video_bg_size(int bg, int size)
{
    if (bg < 0 || bg > 3) return;
    REG_BGCNT[bg] = (REG_BGCNT[bg] & ~BG_SIZE_MASK) | BG_SIZE(size & 3);
}

/* ---------------------------------------------------------------------
 * 等 VBlank
 *
 *  直接改显存（模式 3/5）时，在 VBlank 之外写会看到**撕裂**：
 *  上半屏是新画面、下半屏是旧的。所以每帧画完要等一次。
 * ------------------------------------------------------------------- */
void video_vsync(void)
{
    VBlankIntrWait();
}
