/* =====================================================================
 *  galgame.c —— 视觉小说的**应用层**：界面状态机 + 接线
 *
 *  这一层只干三件事：
 *    1. 有哪些界面（标题 / 剧情 / 选项 / 消息页 / 暂停）
 *    2. 玩家在某个界面按了键 → 切到哪个界面
 *    3. 菜单摆在屏幕的什么位置、长什么样
 *
 *  剧情怎么演（对话框、立绘、剧本命令）在 vn.c；
 *  菜单怎么画在 ui.c；界面栈和帧计数在 game.c；按键语义在 input.c。
 *  想加"关卡模式"这类新玩法，就照着这个文件另写一个，前面四个都不用动。
 *
 *  重构说明（P7）：这个文件原来是 538 行的单体，装着上面所有东西。
 *  拆分时**没有改任何绘制坐标**。
 * ===================================================================== */
#include "galgame.h"

#include "gfx.h"
#include "text.h"
#include "sound.h"          /* P6：Direct Sound A/B（语音走 A，BGM/音效走 B） */
#include "game.h"           /* 帧计数 + 界面栈 */
#include "input.h"          /* 输入动作 */
#include "ui.h"             /* 通用菜单/面板/消息页 */
#include "vn.h"             /* 视觉小说引擎 */
#include "level.h"          /* 关卡模式（P8）*/
#include "obj.h"            /* 硬件精灵（P12）*/
#include "gfx_assets.h"
#include "scenario.h"

/* 自动演示版 ROM（build.ps1 -Define GAL_AUTOPLAY）*/
#ifdef GAL_AUTOPLAY
#define AUTOPLAY_ON 1
#else
#define AUTOPLAY_ON 0
#endif

#define AUTO_START  20      /* 按住确认键多少帧后开始连发 */
#define AUTO_STEP    5      /* 连发间隔帧数 */

/* ---------------------------------------------------------------------
 * 界面状态
 * ------------------------------------------------------------------- */
typedef enum {
    GS_TITLE,
    GS_SCENE,
    GS_CHOICE,
    GS_MESSAGE,
    GS_PAUSE,
    GS_LEVEL,           /* P8：关卡试玩（和剧情模式并列的第二种玩法）*/
} GameState;

/* ---------------------------------------------------------------------
 * 界面文字（这些字符串会被 tools/make_cjk_font.py 自动收进字库）
 * ------------------------------------------------------------------- */
static const char *TITLE_ITEMS[] = { "开始游戏", "关卡试玩", "关于本作" };
#define TITLE_ITEM_N 3

static const char *PAUSE_ITEMS[] = { "继续游戏", "回到标题" };
#define PAUSE_ITEM_N 2


static const char *MSG_ABOUT[] = {
    "GBA 中文 galgame 框架 · 测试版",
    "",
    "引擎：libtonc + 自写中文点阵渲染",
    "字库：10x10 点阵，按需生成",
    "素材：1920x1080 缩放到 240x160",
    "",
    "↑↓ 选择   A 确认   B 跳过",
    "START 菜单",
};

#define MSG_FOOTER "按 A 或 B 返回"

/* ---------------------------------------------------------------------
 * 菜单的位置与样式
 *
 *  三种菜单（标题 / 暂停 / 选项）本质是同一个东西，差别全在这几个数字上，
 *  所以用一张样式表描述，画的时候都走 ui_menu()。
 *
 *  注意：颜色用的是 RGB15()，它在 tonc 里是**内联函数**，
 *  不能拿来初始化静态变量（编译期不知道值）。所以样式在 gal_init() 里填。
 * ------------------------------------------------------------------- */
static UiMenuStyle ST_TITLE;
static UiMenuStyle ST_PAUSE;
static UiMenuStyle ST_CHOICE;

static void init_menu_styles(void)
{
    ST_TITLE.fill = CLR_BOX_FILL;
    ST_TITLE.item_h = 16; ST_TITLE.pad_top = 8;
    ST_TITLE.text_dx = 26; ST_TITLE.cursor_dx = 12; ST_TITLE.centered = 0;

    ST_PAUSE.fill = CLR_CHOICE_FILL;
    ST_PAUSE.item_h = 16; ST_PAUSE.pad_top = 8;
    ST_PAUSE.text_dx = 26; ST_PAUSE.cursor_dx = 12; ST_PAUSE.centered = 0;

    ST_CHOICE.fill = CLR_CHOICE_FILL;
    ST_CHOICE.item_h = 20; ST_CHOICE.pad_top = 14;
    ST_CHOICE.text_dx = 18; ST_CHOICE.cursor_dx = 8; ST_CHOICE.centered = 1;  /* 居中 */
}

/* 消息页的行距 = 字高 + 1 像素间隙（和对话框行距是同一个数）*/
#define MSG_LINE_H 12

#define MENU_X 44
#define MENU_Y 94                         /* 3 项 ×16 + 边距 = 60，94+60=154 刚好不出屏 */
#define MENU_W 150
#define MENU_H (TITLE_ITEM_N * 16 + 12)

#define PAUSE_X 60
#define PAUSE_Y  52
#define PAUSE_W 120
#define PAUSE_H (PAUSE_ITEM_N * 16 + 12)

#define CHOICE_W 180
#define CHOICE_H  58
#define CHOICE_X ((SCR_W - CHOICE_W) / 2)
#define CHOICE_Y  28                      /* 放在对话框（y=98）上方 */

/* ---------------------------------------------------------------------
 * 状态
 * ------------------------------------------------------------------- */
static int s_menu_sel;
static VnStop s_stop = VN_STOP_NONE;

/* ---------------------------------------------------------------------
 * 各菜单的绘制
 * ------------------------------------------------------------------- */
static void draw_title_menu(void)
{
    ui_menu(MENU_X, MENU_Y, MENU_W, MENU_H, TITLE_ITEMS, TITLE_ITEM_N,
            s_menu_sel, &ST_TITLE);
}

static void draw_pause(void)
{
    ui_menu(PAUSE_X, PAUSE_Y, PAUSE_W, PAUSE_H, PAUSE_ITEMS, PAUSE_ITEM_N,
            s_menu_sel, &ST_PAUSE);
}

static void draw_choice_menu(void)
{
    const char *items[2] = { vn_choice_text(0), vn_choice_text(1) };
    ui_menu(CHOICE_X, CHOICE_Y, CHOICE_W, CHOICE_H, items, 2,
            s_menu_sel, &ST_CHOICE);
}

/* 回到标题画面 */
#ifdef GAL_SKIP_TITLE
/* 前置声明：跳过标题时要直接进剧情，那条路和标题菜单的"开始游戏"是同一条 */
static void handle_stop(void);
#endif

static void to_title(void)
{
    /* **音频总开关必须在分支之前开** ✗
     * snd_init() 以前只写在标题那条路里 ✓ 而它负责置 s_ready = 1 ✓
     * 跳过标题之后那条路不走了 → 整个音频系统没初始化 →
     * snd_play_voice / snd_play_bgm 全部直接 return ✗ **一点声音都没有** ✓
     * （这个坑很隐蔽：画面完全正常，就是不响 ✓）
     */
    snd_init();

#ifdef GAL_SKIP_TITLE
    /* **移植的工程不要引擎自带的演示标题** ✗
     *
     * 标题画面是给"框架示例"用的：底图是 GFX_TITLE_BG、菜单里还有
     * "关卡试玩"和"关于本作"（写着"测试版"）、音效是示例工程的测试音效。
     * 对一个真正的游戏来说，这些全是多余的 ✗ 玩家一开机就该进故事 ✓
     *
     * 所以工程可以在 project_video.h 里定义 GAL_SKIP_TITLE，
     * 让"去标题"这个动作变成"直接开始剧情" ✓
     * —— 放在 to_title() 里改，是因为**所有"回标题"的路径都经过它** ✓
     *    只改一处，结局后回标题、暂停里回标题，全都跟着对 ✓
     */
    (void)0;
    vn_begin();
    game_state_set(GS_SCENE);
    s_stop = vn_run();
    handle_stop();
    return;
#else
    game_state_set(GS_TITLE);
    s_menu_sel = 0;
    vn_clear_chars();
    vn_show_bg(GFX_TITLE_BG);

    /* LOGO 水平居中、靠上摆放 */
    gfx_draw_sprite(&gfx_logo_asset, (SCR_W - gfx_logo_asset.w) / 2, 14);
    draw_title_menu();
#endif
}

/* ---------------------------------------------------------------------
 * 剧情停下来之后：该进选项界面就进，该回标题就回
 *
 *  （顺手修了一个原来的 bug：以前进入选项界面时**没有画菜单**，
 *    要等玩家先按一下方向键菜单才出现 —— 看着像"选项没出来"。）
 * ------------------------------------------------------------------- */
static void handle_stop(void)
{
    if (s_stop == VN_STOP_CHOICE) {
        s_menu_sel = 0;
        game_state_set(GS_CHOICE);
        draw_choice_menu();
    } else if (s_stop == VN_STOP_MODE) {
        /* P10：剧本要求换玩法。**用 push 而不是 set** ——
         * 这样关卡结束（START 退出）时 pop 回来还是 GS_SCENE，
         * 剧情接着下一句演，而不是被打回标题。 */
        if (vn_requested_mode() == MODE_LEVEL) {
            game_state_push(GS_LEVEL);
            lvl_enter();
        }
    } else if (s_stop == VN_STOP_END) {
        to_title();
    }
}

/* ---------------------------------------------------------------------
 * 入口
 * ------------------------------------------------------------------- */
void gal_init(void)
{
    game_init();
    init_menu_styles();          /* 颜色是 RGB15() 算出来的，只能运行期填 */
    input_autoplay_enable(AUTOPLAY_ON);
    s_menu_sel = 0;
    s_stop = VN_STOP_NONE;
    to_title();
}

#ifdef GAL_MODETEST
/* ---------------------------------------------------------------------
 * 调试用：每 2 秒换一个显示模式，把当前界面重画一遍
 *
 * 用途是**验证画布抽象真的成立** —— 同一段绘制代码，
 * 在直色位图（3）、8bpp 索引（4）、图块画布（0/1）下应该画出同一个画面，
 * 只是图块/8bpp 模式颜色降到 256 色。
 * ------------------------------------------------------------------- */
static void redraw_current(void)
{
    switch (game_state()) {
    case GS_SCENE: vn_redraw(); break;
    case GS_LEVEL: lvl_enter(); break;
    default:       to_title();  break;
    }
}
#endif

void gal_update(void)
{
    game_tick();
    input_poll(game_frame());
    snd_update();        /* 音频进度：语音倒计时、BGM 循环、音效播完恢复 BGM */

#ifdef GAL_MODETEST
    {
#ifdef GAL_MODETEST_FIXED
        /* 只钉在一个模式上（排查单模式问题时用）：
         * 每隔 2 秒重画一次，但不换模式，方便读寄存器/显存。 */
        static const VideoMode fixed = (VideoMode)GAL_MODETEST_FIXED;
        static int f_tick = 0;
        if (++f_tick == 60) {
            gfx_set_mode(fixed);
            redraw_current();
            gfx_flush();
        }
#else
        static const VideoMode seq[] = { VMODE_3, VMODE_4, VMODE_0, VMODE_1 };
        static int si = 0, tick = 0;
        if (++tick >= 120) {
            tick = 0;
            si = (si + 1) % 4;
            gfx_set_mode(seq[si]);
            redraw_current();
            gfx_flush();
        }
#endif
    }
#endif

#ifdef GAL_FREEZE_AT
    /* 验收专用（build.ps1 -Define GAL_FREEZE_AT=300）：
     * 跑到指定帧就**停住不动**，画面冻在那儿。这样用 GDB 桩读显存
     * 拿到的就是"第 N 帧的画面"，可以拿两版 ROM 的校验和直接比 ——
     * 不受模拟器截图时序的影响。平时编译不带这个宏，一个字节都不多。 */
    if (game_frame() >= GAL_FREEZE_AT) {
        for (;;) VBlankIntrWait();
    }
#endif

    switch (game_state()) {

    /* ---------------------------------------------------------- 标题 */
    case GS_TITLE:
        if (input_hit(ACT_DOWN)) {
            ui_menu_erase(MENU_X, MENU_Y, MENU_W, MENU_H);
            s_menu_sel = (s_menu_sel + 1) % TITLE_ITEM_N;
            draw_title_menu();
        }
        if (input_hit(ACT_UP)) {
            ui_menu_erase(MENU_X, MENU_Y, MENU_W, MENU_H);
            s_menu_sel = (s_menu_sel + TITLE_ITEM_N - 1) % TITLE_ITEM_N;
            draw_title_menu();
        }
        if (input_hit(ACT_CONFIRM)) {
            switch (s_menu_sel) {
            case 0:                               /* 开始游戏 */
                vn_begin();
                game_state_set(GS_SCENE);
                s_stop = vn_run();
                handle_stop();
                break;
            case 1:                               /* 关卡试玩（P8）*/
                game_state_set(GS_LEVEL);
                lvl_enter();
                break;
            default:                              /* 关于本作 */
                game_state_push(GS_MESSAGE);
                ui_message(MSG_ABOUT, 8, MSG_LINE_H, MSG_FOOTER);
                break;
            }
        }
        break;

    /* ------------------------------------------------ 关卡（P8）*/
    case GS_LEVEL:
        lvl_update();
        if (lvl_event() == LVL_EVENT_EXIT) {
            /* 从哪来回哪去：剧本里切进来的就回剧情接着演，
             * 标题菜单进来的就回标题（栈里没东西时 pop 返回 -1）。 */
            int back = game_state_pop();
            lvl_exit();                 /* 走之前把精灵收掉（见 lvl_exit 的说明）*/
            if (back == GS_SCENE) {
                vn_redraw();                 /* 把关卡的画面盖回剧情画面 */
                s_stop = VN_STOP_SAY;        /* 关卡已经"消费"掉了那个切模式命令 */
            } else {
                to_title();
            }
        }
        break;

    /* ---------------------------------------------------------- 剧情 */
    case GS_SCENE:
        vn_tick();

        /* 推进一句：还在打字就立刻显示完，否则执行下一条命令。
         * 单次按下（input_hit）和长按连发（隔 AUTO_STEP 帧）互斥，
         * 否则同一帧会推进两次。 */
        if (input_hit(ACT_CONFIRM) || input_hit(ACT_CANCEL)) {
            s_stop = vn_advance();
            handle_stop();
        } else if (input_held_frames(ACT_CONFIRM) > AUTO_START &&
                   ((input_held_frames(ACT_CONFIRM) - AUTO_START) % AUTO_STEP) == 0) {
            s_stop = vn_advance();
            handle_stop();
        }

        /* START：游戏内菜单（剧情已经结束/进选项时就不再弹）*/
        if (game_state() == GS_SCENE && input_hit(ACT_MENU)) {
            game_state_push(GS_PAUSE);
            s_menu_sel = 0;
            draw_pause();
        }
        break;

    /* ---------------------------------------------------------- 选项 */
    case GS_CHOICE:
        if (input_hit(ACT_DOWN) || input_hit(ACT_UP)) {
            s_menu_sel ^= 1;
            draw_choice_menu();
        }
        if (input_hit(ACT_CONFIRM)) {
            ui_menu_erase(CHOICE_X, CHOICE_Y, CHOICE_W, CHOICE_H);
            vn_after_overlay();
            vn_choice_commit(s_menu_sel);
            game_state_set(GS_SCENE);
            s_stop = vn_run();
            handle_stop();
        }
        break;

    /* ------------------------------------------------------ 消息页 */
    case GS_MESSAGE:
        if (input_hit(ACT_CONFIRM) || input_hit(ACT_CANCEL)) {
            lvl_exit();
            int back = game_state_pop();
            if (back == GS_TITLE)
                to_title();
            else
                vn_redraw();
        }
        break;

    /* ---------------------------------------------------- 游戏内菜单 */
    case GS_PAUSE:
        if (input_hit(ACT_DOWN) || input_hit(ACT_UP)) {
            s_menu_sel ^= 1;
            draw_pause();
        }
        if (input_hit(ACT_CANCEL) || input_hit(ACT_MENU)) {
            game_state_set(GS_SCENE);
            vn_redraw();
        }
        if (input_hit(ACT_CONFIRM)) {
            if (s_menu_sel == 0) {                 /* 继续游戏 */
                game_state_set(GS_SCENE);
                vn_redraw();
            } else {                               /* 回到标题 */
                to_title();
            }
        }
        break;
    }

    /* 每帧收尾：图块画布（模式 0/1/2）要把这一帧改动过的 8x8 格转成图块传进显存。
     * 直色位图（3/5）和 8bpp（4）下这个函数什么都不做 —— 它们直接写显存。 */
    gfx_flush();

    /* 防御性收尾：**不在关卡里就不该有任何硬件精灵** ✗
     *
     * 精灵是独立图层，不属于任何一屏 —— 只要有一处 spr_show() 忘了配对的隐藏，
     * 它就会一直留在屏幕上（踩过：关卡的玩家精灵跟着进了剧情画面，
     * 左上角多出一个小人，肉眼很容易当成"编辑器预览画错了"）。
     *
     * 之前已经在 lvl_exit() 里收过一次；这里再兜一道底，
     * 把"精灵只在关卡里存在"变成一条**每帧都成立的约束**，
     * 而不是依赖每条退出路径都记得收拾。代价是每帧一次 128 次循环，可以忽略。
     *
     * 注意顺序：必须在 spr_flush() **之前**，否则这一帧的隐藏要等下一帧才生效。 */
    if (game_state() != GS_LEVEL) spr_hide_all();

    spr_flush();      /* 硬件精灵：把这一帧设好的位置写进 OAM */
}
