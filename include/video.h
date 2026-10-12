/* =====================================================================
 *  video.h —— GBA 六种显示模式的统一入口
 *
 *  为什么要这一层：GBA 有 6 种显示模式（0~5），它们的**背景层能力完全不同**：
 *
 *      模式 0   4 个图块层              没有旋转缩放
 *      模式 1   2 个图块层 + 1 个仿射层  最常用
 *      模式 2   2 个仿射层              没有普通图块层
 *      模式 3   1 个 16bpp 位图层       单缓冲、不能滚动
 *      模式 4   1 个 8bpp 位图层        有 2 页可翻页（双缓冲）
 *      模式 5   1 个 16bpp 位图层       只有 160x128
 *
 *  **位图和图块层不能混用**（硬件就是这样）：
 *  模式 0/1/2 有图块没位图，模式 3/4/5 有图没图块。
 *  而 **OBJ（硬件精灵）在任何模式下都能用** —— 这条最容易被忽略。
 *
 *  这一层只回答三个问题：
 *      现在是什么模式？这个模式能干什么？怎么切过去？
 *  具体"往哪画"由 surface.c 负责。
 * ===================================================================== */
#ifndef VIDEO_H
#define VIDEO_H

#include <tonc.h>

typedef enum {
    VMODE_0 = 0,        /* 4 个图块层 */
    VMODE_1 = 1,        /* 2 图块 + 1 仿射 */
    VMODE_2 = 2,        /* 2 仿射 */
    VMODE_3 = 3,        /* 16bpp 位图 240x160（本工程原来的模式）*/
    VMODE_4 = 4,        /* 8bpp 位图 240x160，可翻页 */
    VMODE_5 = 5,        /* 16bpp 位图 160x128 */
    VMODE_N = 6,
} VideoMode;

/* 一个模式的能力（查表用，别在代码里散落 if (mode == 3)）*/
typedef struct {
    const char *name;
    int is_bitmap;      /* 1 = 有位图背景层（3/4/5），0 = 只有图块层（0/1/2）*/
    int bpp;            /* 位图模式的色深：16 或 8；图块模式填 0 */
    int w, h;           /* 可见分辨率（模式 5 是 160x128）*/
    int pages;          /* 位图页数（模式 4 是 2，其余 1）*/
    int reg_bgs;        /* 普通图块层数量 */
    int aff_bgs;        /* 仿射图块层数量 */
} VideoCaps;

const VideoCaps *video_caps(VideoMode m);

/* ---- 初始化与切换 ---- */
void video_init(VideoMode m);       /* 上电后调一次（默认模式 3）*/
void video_set_mode(VideoMode m);   /* 运行期切换：会重设 DISPCNT 和显存布局 */
VideoMode video_mode(void);

/* ---- 当前模式的能力（快捷查询）---- */
int video_w(void);
int video_h(void);
int video_is_bitmap(void);
int video_pages(void);

/* ---- 位图模式：帧缓冲与翻页 ---- */
u16 *video_vram(void);              /* 16bpp 模式的当前页首地址 */
u8  *video_vram8(void);             /* 8bpp 模式的当前页首地址 */
void video_page_flip(void);         /* 模式 4 翻到另一页；其他模式空操作 */
void video_page_clear(u16 color);   /* 清空**当前页**（翻页后才不会闪旧内容）*/

/* ---- 图块模式：背景层开关与滚动 ---- */
void video_bg_enable(int bg, int on, int priority);
void video_bg_scroll(int bg, int x, int y);
void video_bg_char_base(int bg, int block);     /* 图块数据在第几个 16KB 块 */
void video_bg_screen_base(int bg, int block);   /* 地图数据在第几个 2KB 块 */
void video_bg_size(int bg, int size);           /* 0=32x32 1=64x32 2=32x64 3=64x64 */

/* ---- 中断与同步 ---- */
void video_vsync(void);             /* 等一次 VBlank（每帧画完之后调）*/

/* 模式切换时的收尾：清屏 + 关掉所有层，避免残留上一模式的画面 */
void video_reset_layers(void);

#endif /* VIDEO_H */
