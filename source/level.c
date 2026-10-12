/* =====================================================================
 *  level.c —— 关卡模式实现（最小可玩）
 *
 *  三个关键决定，都是被现有的渲染方式逼出来的：
 *
 *  1. **地图只画一次**。引擎是模式 3（位图，没有硬件图块），
 *     16x16 的图块只能软件填色。整屏 15x10 个格子 = 150 次矩形填充，
 *     每帧都画的话纯属浪费 —— 地图是静止的，进关卡画一次就够。
 *
 *  2. **擦角色不用 gfx_restore_rect()**。那个函数是从"背景资源"里取像素
 *     （见 gfx.c 的 s_bg），而关卡的地图是**程序画出来的**，没有对应的图片。
 *     所以这里自己写 redraw_tiles()：把角色占过的格子按地图数据重画一遍。
 *     代价是要多写十几行，好处是不用为了"能还原"去准备一张整屏背景图。
 *
 *  3. **碰撞用"四点采样"**：把角色矩形下一步的四个角换算成格子坐标，
 *     只要有一个是实心就挡住。比逐像素判断快得多，对格子地图也足够准。
 * ===================================================================== */
#include "level.h"

#include "gfx.h"
#include "text.h"
#include "input.h"
#include "game.h"
#include "anim.h"
#include "anim_data.h"    /* ANIM_FRAME_N / anim_frames（上传精灵帧要用）*/
#include "obj.h"          /* 硬件精灵（P12）*/
#include "bg.h"           /* 仿射图块层（模式 1/2）*/
#include "level_data.h"
#include "gfx_assets.h"

#define TILE        16
#define PLAYER_W    12
#define PLAYER_H    14
#define PLAYER_SPEED 1          /* 每帧走几像素 */

/* 图块类型（和 level_data.h 里生成的一致）*/
#define T_FLOOR  0
#define T_WALL   1
#define T_GRASS  2
#define T_WATER  3

static int s_px, s_py;          /* 玩家左上角像素坐标（这是**碰撞盒**的左上角）*/
static int s_ox, s_oy;          /* 上一帧的位置（用来擦除）*/
static LvlEvent s_event;
static int s_moved;
static int s_last_ix = -1;      /* 上一帧画的是哪个精灵（换帧了就得重画）*/

static Anim s_anim;             /* 玩家的动画状态（P9）*/
/* 朝向（左右翻转贴图）还没做：gfx 目前没有水平翻转的 blit。
 * 走路动画本身能看出在动，先不挡路。 */

/* 动画编号：生成的 anim_data.c 里的顺序（工程里"走路"在前、"待机"在后）*/
#define ANIM_WALK 0
#define ANIM_IDLE 1

/* 玩家精灵的显示尺寸（用第一帧的真实尺寸，不写死）*/
static int s_spr_w = PLAYER_W, s_spr_h = PLAYER_H;

/* ---- 硬件精灵（P12）----
 * 每个动画帧上传成一个 OBJ 图块，玩家用一个精灵槽显示。
 * 好处不只是"省 CPU"：**精灵不需要擦除** —— 它浮在背景之上，
 * 移开时背景本来就还在。P9 那个"走一路拖一串残影"的坑从此不存在。
 *
 * 排查记录（三个坑，都写进 obj.c 了）：
 *   1. 位图模式下 OBJ 图块只能在 0x06014000 之后，
 *      而 OAM 的图块号要从 0x06010000 数起 → 要加 512 的偏移
 *   2. 1D 图块映射要**显式置位**（DCNT_OBJ_2D 的值是 0，"清掉它"等于没做）
 *   3. **VRAM 不支持 8 位写** —— 4bpp 图块不能拿 u8* 直接在显存里拼半字节，
 *      必须在 RAM 里拼好再用 16 位搬进去。（这条是根因，靠读内存才定位到）
 *
 * 想退回软件贴图：编译时加 -Define GAL_NO_OBJ。 */
#ifdef GAL_NO_OBJ
#define OBJ_READY_DEFAULT 0
#else
#define OBJ_READY_DEFAULT 1
#endif
static int            s_tile_of[ANIM_FRAME_N];    /* 动画帧 → OBJ 图块号 */
static const SprSize *s_size_of[ANIM_FRAME_N];    /* 动画帧 → 精灵尺寸档位 */
static int            s_obj_ready = OBJ_READY_DEFAULT;
#define PLAYER_SLOT 0

/* 颜色在运行期算（RGB15 是内联函数，不能拿来初始化静态变量）。
 *
 * 描边色是**单独给的**，不是在底色上做加法 —— RGB15 的 15 个位是
 * 5/5/5 三个通道，直接 +1 会从蓝通道进位到绿通道，颜色会突然跑偏。 */
static u16 s_col[TILE_KIND_N];
static u16 s_edge[TILE_KIND_N];

static void init_colors(void)
{
    s_col[T_FLOOR] = RGB15( 9,  9, 11);   s_edge[T_FLOOR] = RGB15(10, 10, 12);
    s_col[T_WALL]  = RGB15(14, 13, 16);   s_edge[T_WALL]  = RGB15(18, 17, 20);
    s_col[T_GRASS] = RGB15( 4, 12,  5);   s_edge[T_GRASS] = RGB15( 6, 16,  7);
    s_col[T_WATER] = RGB15( 3,  7, 18);   s_edge[T_WATER] = RGB15( 5, 10, 24);
}

static int tile_at(int tx, int ty)
{
    if (tx < 0 || ty < 0 || tx >= LVL_W || ty >= LVL_H) return T_WALL;  /* 出界当墙 */
    return lvl_map[ty * LVL_W + tx];
}

/* =====================================================================
 *  仿射图层版（模式 1 的 BG2 / 模式 2 的 BG2/BG3）—— 编译加 GAL_LEVEL_AFFINE
 *
 *  为什么关卡值得有一条仿射路径：仿射层能**整体旋转缩放** ✗
 *  而普通图块层只能滚动。模式 2 更是**只有仿射层**，不走这条路就没法用。
 *
 *  做法上有个关键取舍：仿射层的地图条目只有 1 字节（**最多 256 个图块**）✗
 *  所以不能像 sf_tiles 那样"一格一个专属图块"（240x160 要 600 个 ✗）。
 *  这里的做法是**真正的图块地图**：4 种地形各 1 个 8x8 图块，
 *  地图 30x20 格（每个 16x16 的地形格展开成 2x2 个 8x8 格）——
 *  一共只要 4 个图块，余量充足。
 * ===================================================================== */
#ifdef GAL_LEVEL_AFFINE
#define AFF_BG      2       /* 模式 1/2 下 BG2 是仿射层 */
#define AFF_W       30      /* 240/8 */
#define AFF_H       20      /* 160/8 */

/* 放 EWRAM 的未初始化段（不占 ROM）；obj.c / bg.c 里是同样的做法 */
#define EWRAM_SCRATCH_L __attribute__((section(".sbss")))
static u8 EWRAM_SCRATCH_L s_aff_tiles[4 * 64];      /* 4 块 8x8、8bpp */
/* 地图要按**整张** 32x32 格准备（256x256 像素）——
 * 仿射层显示的是整张地图，屏幕只看到其中一块，
 * 没写过的地方会露出显存垃圾（第一次就是这么白屏的 ✗）。*/
static u8 EWRAM_SCRATCH_L s_aff_map_full[32 * 32];
static int s_aff_angle = 0;

static void lvl_affine_build(void)
{
    /* ---- 调色板：把地形颜色放到 1..4 号（0 留给"空"）----
     * 仿射层是调色板显示，颜色必须先写进调色板。 */
    pal_bg_mem[0] = RGB15(0, 0, 0);
    pal_bg_mem[1] = RGB15( 9,  9, 11);      /* 地板 */
    pal_bg_mem[2] = RGB15(14, 13, 16);      /* 墙 */
    pal_bg_mem[3] = RGB15( 4, 12,  5);      /* 草 */
    pal_bg_mem[4] = RGB15( 3,  7, 18);      /* 水 */

    /* ---- 图块：4 种地形，每种一块纯色 8x8（8bpp：一块 64 字节）---- */
    for (int t = 0; t < 4; t++) {
        u8 ix = (u8)(t + 1);                /* 调色板下标 1..4 */
        for (int i = 0; i < 64; i++) s_aff_tiles[t * 64 + i] = ix;
    }

    /* ---- 地图：先把**整张** 32x32 铺成地板，再把关卡写在左上角 ----
     * 关键点：仿射层显示的是**整张地图**（32x32 格 = 256x256 像素），
     * 屏幕上只看到其中一块。不把整张填满的话，转到/移到没写过的格子
     * 就会看到显存里的垃圾（第一次就是这么白屏的 ✗）。 */
    for (int i = 0; i < 32 * 32; i++) s_aff_map_full[i] = 0;   /* 0 = 地板 */
    for (int ty = 0; ty < LVL_H; ty++) {
        for (int tx = 0; tx < LVL_W; tx++) {
            u8 t = (u8)lvl_map[ty * LVL_W + tx];
            for (int y2 = 0; y2 < 2; y2++)
                for (int x2 = 0; x2 < 2; x2++)
                    s_aff_map_full[(ty * 2 + y2) * 32 + (tx * 2 + x2)] = t;
        }
    }

    /* ---- 建层：8bpp、图块放 0 号块、地图放 28 号屏幕块（避开图块区）----
     * 地图用 32x32 这一档（256x256 像素）。 */
    bg_affine_setup(AFF_BG, 8, 0, 28, AFF_32x32, 0);
    bg_affine_tiles(AFF_BG, s_aff_tiles, 4);
    bg_affine_map(AFF_BG, s_aff_map_full, 32, 32, 32);
    /* 旋转中心 = **关卡自己的中心**（不是地图中心 ✗）：
     * 关卡占 30x20 格 = 240x160 像素，中心在 (120, 80)。 */
    bg_affine_rotate(AFF_BG, 0, 256, AFF_W * 8 / 2, AFF_H * 8 / 2);
}

static void lvl_affine_update(void)
{
    /* 每 3 帧转 1°，把"能旋转"这件事直接摆在画面上 */
    if (game_frame() % 3 == 0) s_aff_angle = (s_aff_angle + 1) & 255;
    bg_affine_rotate(AFF_BG, s_aff_angle, 256, AFF_W * 8 / 2, AFF_H * 8 / 2);
}
#endif  /* GAL_LEVEL_AFFINE */

static int is_solid(int t)
{
    return (t == T_WALL) || (t == T_WATER);
}

/* 画一个格子：底色 + 描边（比纯色块好看，也看得出格子边界）*/
static void draw_tile(int tx, int ty)
{
    int t = tile_at(tx, ty);
    int x = tx * TILE, y = ty * TILE;
    gfx_fill_rect(x, y, TILE, TILE, s_col[t]);
    if (t != T_FLOOR)
        gfx_rect_border(x, y, TILE, TILE, s_edge[t]);
}

/* 把一块矩形覆盖到的格子重画（擦角色用）*/
static void redraw_tiles(int x, int y, int w, int h)
{
    int tx0 = x / TILE, ty0 = y / TILE;
    int tx1 = (x + w - 1) / TILE, ty1 = (y + h - 1) / TILE;
    for (int ty = ty0; ty <= ty1; ty++)
        for (int tx = tx0; tx <= tx1; tx++)
            draw_tile(tx, ty);
}

/* ---------------------------------------------------------------------
 * 玩家精灵的定位
 *
 *  **画和擦必须用同一个锚点**，否则就会拖残影 —— 这里踩过一个坑：
 *  画的时候拿"碰撞盒宽"当锚点、擦的时候拿"精灵宽"当锚点，
 *  两者差了 6 像素，结果擦的地方根本不是画的地方，走一路留一串小人。
 *
 *  所以这里只留一个定位函数：**水平居中于碰撞盒，脚底对齐盒底**。
 *  擦除则用一个比所有帧都大的框（各帧裁得紧、宽度差个一两像素很正常）。
 * ------------------------------------------------------------------- */
static void player_anchor(int px, int py, int w, int h, int *dx, int *dy)
{
    *dx = px + (PLAYER_W - w) / 2;
    *dy = py + PLAYER_H - h;
}

static void draw_player(void)
{
    /* P12：优先用**硬件精灵**画（浮在背景上，不需要擦除）。
     * 精灵画布的左上角对齐"内容左上角" —— 上传时内容就是放在左上角的，
     * 右边/下边多出来的部分是透明（下标 0），不会挡到背景。 */
    int ix = anim_sprite_index(&s_anim);
    if (s_obj_ready && ix >= 0 && ix < gfx_sprites_count && s_tile_of[ix] >= 0) {
        const GfxAsset *a = &gfx_sprites[ix];
        const SprSize *sz = s_size_of[ix];
        int cx, cy;
        player_anchor(s_px, s_py, a->w, a->h, &cx, &cy);
        /* 优先级 0 = 最前（背景层是 3），所以精灵不会被地图挡住 */
        spr_show(PLAYER_SLOT, cx, cy, s_tile_of[ix], sz, ix & 15, 0, 0, 0);
        return;
    }
    /* 显存不够或没配动画：退回软件贴图，至少看得见人在哪 */
    if (ix >= 0 && ix < gfx_sprites_count) {
        const GfxAsset *a = &gfx_sprites[ix];
        int dx, dy;
        player_anchor(s_px, s_py, a->w, a->h, &dx, &dy);
        gfx_draw_sprite(a, dx, dy);
        return;
    }
    gfx_fill_rect(s_px, s_py, PLAYER_W, PLAYER_H, RGB15(26, 20,  8));
    gfx_rect_border(s_px, s_py, PLAYER_W, PLAYER_H, RGB15(31, 28, 14));
    gfx_fill_rect(s_px + 3, s_py + 4, 2, 2, RGB15(31, 31, 31));
    gfx_fill_rect(s_px + 7, s_py + 4, 2, 2, RGB15(31, 31, 31));
    gfx_fill_rect(s_px + 3, s_py + 9, 6, 2, RGB15(18, 12,  4));
}

/* 擦掉玩家：擦的范围要按**精灵**算，不能只擦碰撞盒 ——
 * 精灵比盒子大一圈，只擦盒子会在地上留下半个身子。
 *
 * **只在软件贴图时才需要**：用硬件精灵的话，精灵根本没写进背景，
 * 移开就自动露出原来的地图，不需要擦（这条是 OBJ 最大的好处之一）。 */
static void erase_player_at(int px, int py)
{
    if (s_obj_ready) return;            /* 硬件精灵：不用擦 */
    int w = s_spr_w + 4, h = s_spr_h + 2;
    int dx, dy;
    player_anchor(px, py, w, h, &dx, &dy);
    redraw_tiles(dx, dy, w, h);
}

/* 从 (x,y) 出发能不能站 —— 四点采样 */
static int can_stand(int x, int y)
{
    if (is_solid(tile_at(x / TILE, y / TILE))) return 0;
    if (is_solid(tile_at((x + PLAYER_W - 1) / TILE, y / TILE))) return 0;
    if (is_solid(tile_at(x / TILE, (y + PLAYER_H - 1) / TILE))) return 0;
    if (is_solid(tile_at((x + PLAYER_W - 1) / TILE,
                         (y + PLAYER_H - 1) / TILE))) return 0;
    return 1;
}

void lvl_enter(void)
{
    init_colors();
    s_event = LVL_EVENT_NONE;
    s_moved = 0;

    for (int ty = 0; ty < LVL_H; ty++)
        for (int tx = 0; tx < LVL_W; tx++)
            draw_tile(tx, ty);

    /* 精灵尺寸从第一帧取（工程里配了什么尺寸就用什么，不写死）*/
    anim_init(&s_anim);
    anim_play(&s_anim, ANIM_IDLE);
    int ix = anim_sprite_index(&s_anim);
    if (ix >= 0 && ix < gfx_sprites_count) {
        s_spr_w = gfx_sprites[ix].w;
        s_spr_h = gfx_sprites[ix].h;
    }

    /* ---- 把动画帧上传成硬件精灵（P12）----
     * 每个帧给一个**独立的调色板组**：4bpp 精灵是 16 色一组，共 16 组，
     * 各帧用自己的组就不会互相串色（帧数超过 16 才会开始复用）。 */
    spr_hide_all();
    {
        int bank = 0;
        for (int i = 0; i < ANIM_FRAME_N; i++) {
            int si = anim_frames[i];
            if (si < 0 || si >= gfx_sprites_count) { s_tile_of[i] = -1; continue; }
            s_size_of[i] = spr_fit_size(gfx_sprites[si].w, gfx_sprites[si].h);
            s_tile_of[i] = spr_upload(&gfx_sprites[si], 4, bank);
            if (s_tile_of[i] < 0) { s_obj_ready = 0; break; }   /* 显存不够就退回软件贴图 */
            bank = (bank + 1) & 15;
        }
    }

    /* 对照精灵：固定放在屏幕中间。
     * 用来区分"图块上传坏了"还是"OAM 属性写错了" ——
     * 它和玩家用的是同一批图块，只是位置写死。
     * 诊断结果：它也不显示 → 问题在 OBJ 上传/OAM 这条链上，不在玩家定位。 */
#ifdef GAL_OBJ_DEBUG
    if (s_obj_ready && s_tile_of[0] >= 0)
        spr_show(5, 110, 60, s_tile_of[0], s_size_of[0], 0, 0, 0, 0);
#endif

    /* 仿射图块路径（GAL_LEVEL_AFFINE）：整张地图画到仿射层上 */
#ifdef GAL_LEVEL_AFFINE
    lvl_affine_build();
#else
    for (int ty = 0; ty < LVL_H; ty++)
        for (int tx = 0; tx < LVL_W; tx++)
            draw_tile(tx, ty);
#endif

    s_px = LVL_START_X * TILE + (TILE - PLAYER_W) / 2;
    s_py = LVL_START_Y * TILE + (TILE - PLAYER_H) / 2;
    s_ox = s_px; s_oy = s_py;
    s_last_ix = -1;             /* 重进关卡：别拿上一次的帧号做比较 */
    draw_player();

    text_draw(4, 2, "方向键移动  START 退出", CLR_TEXT);
}

LvlEvent lvl_event(void)
{
    LvlEvent e = s_event;
    s_event = LVL_EVENT_NONE;
    return e;
}

void lvl_exit(void)
{
    /* **离开关卡必须把硬件精灵藏起来** ✗
     *
     * 精灵是独立于背景层的硬件，它不"属于"某一关的画面 ——
     * 关卡里用 spr_show() 放出来的角色，如果走的时候不管它，
     * 它会**一直留在屏幕上**，跟着进剧情、进标题 ✗
     *
     * 这个 bug 是"从显存渲染 + 逐像素比对"的验证手段抓到的：
     * 剧情画面和编辑器预览一比，左上角多出一个红色的角色轮廓 ——
     * 靠肉眼截图看多半会被当成"预览画错了"。
     *
     * 顺带一提：软件贴图时代不存在这个问题（画进背景的东西会随背景重画而消失），
     * 这是改用硬件精灵之后**新引入**的一类坑。 */
    spr_hide_all();
    spr_flush();            /* 立刻写进 OAM，别等下一帧的 flush */
}

void lvl_update(void)
{
#ifdef GAL_LEVEL_AFFINE
    lvl_affine_update();
#endif
    int dx, dy;
    input_axis(&dx, &dy);

    /* 每帧移动：先试完整的一步，走不动就分轴再试 ——
     * 这样贴墙走的时候不会"卡住不动"，而是顺着墙滑。 */
    int nx = s_px + dx * PLAYER_SPEED;
    int ny = s_py + dy * PLAYER_SPEED;
    if (dx && dy) {
        if (can_stand(nx, ny))            { s_px = nx; s_py = ny; }
        else if (can_stand(nx, s_py))     { s_px = nx; }
        else if (can_stand(s_px, ny))     { s_py = ny; }
    } else {
        if (can_stand(nx, ny))            { s_px = nx; s_py = ny; }
    }

    /* ---- 动画（P9）：动起来播"走路"，停下播"待机" ---- */
    if (dx || dy) anim_play(&s_anim, ANIM_WALK);
    else          anim_play(&s_anim, ANIM_IDLE);
    anim_update(&s_anim);

    int moved = (s_px != s_ox || s_py != s_oy);
    /* 动画换帧时就算"人没动"也得重画，不然走路会一格一格地卡 */
    int ix = anim_sprite_index(&s_anim);

    if (moved || ix != s_last_ix) {
        /* 先把**老位置**盖回去，再画新位置。
         * 顺序不能反：先画新的话，两个矩形重叠的部分会被老位置的擦除抹掉。 */
        erase_player_at(s_ox, s_oy);
        draw_player();
        s_ox = s_px; s_oy = s_py;
        s_last_ix = ix;
        s_moved++;
        /* HUD 画在地图上面，所以每帧重画一次（很小，不心疼）*/
        text_draw(4, 2, "方向键移动  START 退出", CLR_TEXT);
    }

    if (input_hit(ACT_MENU))
        s_event = LVL_EVENT_EXIT;
}

int lvl_player_tx(void) { return s_px / TILE; }
int lvl_player_ty(void) { return s_py / TILE; }
