/* =====================================================================
 *  vn.c —— 视觉小说引擎实现
 *
 *  代码从原来的 galgame.c 搬过来，**绘制顺序和坐标一个像素都没改**
 *  （重构的验收标准就是重启前后录屏逐像素一致）。
 *  改动只有两处：
 *    1. 界面状态切换（s_state = ...）交给调用方 —— 引擎只管剧情，
 *       不该知道"标题界面"长什么样
 *    2. 菜单绘制抽到 ui.c（标题/暂停/选项三处本来是同一个东西）
 * ===================================================================== */
#include "vn.h"

#include "game.h"           /* 帧计数：对话框右下角的 ▼ 闪烁要用 */
#include "gfx.h"
#include "text.h"
#include "sound.h"
#include "scenario.h"
#include "gfx_assets.h"
#include "snd_data.h"

/* ---------------------------------------------------------------------
 * 布局常量
 *
 *  字号 11 像素：来源是中易宋体 12px 的内嵌点阵，再用面积平均缩到 11x11
 *  （见 tools/make_cjk_font.py 的说明 —— 直接渲染 11px 会走轮廓线，笔画会断）。
 *  行距取 12（11 像素字形 + 1 像素间隙）。
 *
 *  下面几个尺寸是**推导出来的**，改 TEXT_LINES 或 LINE_H 时
 *  对话框高度和位置会自动跟着变，不用手工调。
 *
 *      y=101 ┌──────────────────────────────┐
 *            │ 魔女                          │  ← 名字（高亮色，画在框内）
 *      y=118 │ 台词第一行                    │
 *      y=130 │ 台词第二行                    │
 *      y=142 │ 台词第三行                 ▼  │  ← ▼ 提示可继续
 *      y=155 └──────────────────────────────┘
 * ------------------------------------------------------------------- */
#define BOX_X        4
#define BOX_W      232
#define TEXT_X      10
#define LINE_H      12                    /* 行距 */
#define TEXT_LINES   3                    /* 对话框显示几行 */
#define NAME_H      FONT_GLYPH_H          /* 名字行高 = 一个字高 */
#define PAD          3                    /* 框内边距 */

/* 每行的**像素**预算（不是字数）：从 x=10 排到 x=208，
 * 右边留出 16 像素给右下角的 ▼。汉字 11px、ASCII 半角 5px，
 * 所以一行最多 18 个汉字，中英混排时能放更多。 */
#define TEXT_MAX_PX 198

#define NAME_X      TEXT_X                /* 名字和台词左对齐 */
#define BOX_H       (PAD * 2 + NAME_H + 2 + TEXT_LINES * LINE_H)   /* = 55 */
#define BOX_Y       (SCR_H - 4 - BOX_H)                            /* 贴底 = 101 */
#define NAME_Y      (BOX_Y + PAD)
#define TEXT_Y      (BOX_Y + PAD + NAME_H + 2)

#define SPRITE_Y      4
#define SPRITE_MARGIN 2

#define TYPE_SPEED    2                   /* 每 N 帧显示一个字 */

/* ---------------------------------------------------------------------
 * 状态
 * ------------------------------------------------------------------- */
static int  s_pc;                         /* 剧本执行到第几条命令 */
static const ScCmd *s_cmd;                /* 当前命令（选项的文字从这里取）*/

static const GfxAsset *s_bg;
static s8   s_char[SC_POS_N] = { -1, -1, -1 };  /* 左/中/右各显示哪个立绘，-1 = 不显示 */

static const char *s_speaker = "";
static const char *s_text = "";
static TextLayout s_layout;
static int  s_total;                      /* 整句多少字 */
static int  s_reveal;                     /* 已显示多少字 */
static int  s_timer;
static int  s_typing;
static int  s_req_mode;                   /* 剧本要求切到哪个玩法（P10）*/

/* ---------------------------------------------------------------------
 * 资源映射
 *
 *  P5 起资源不再是写死的几个，而是由 tools/make_project_assets.py 按
 *  项目的素材清单生成索引表 —— 编辑器里放多少张背景、多少个角色，
 *  实机就认多少。剧本里的编号就是下标。
 *  越界一律回退到第 0 个，避免野指针把 ROM 读崩（宁可画面不对也别死机）。
 * ------------------------------------------------------------------- */
static const GfxAsset *bg_of(int id)
{
    if (gfx_bgs_count <= 0) return &gfx_bgs[0];
    if (id < 0 || id >= gfx_bgs_count) id = 0;
    return &gfx_bgs[id];
}

static const GfxAsset *char_of(int id)
{
    /* 剧情里的 char 下标是**立绘表自己的编号**（编译时从 0 开始），
     * 而 gfx_sprites[] 是「关卡精灵 + 立绘」拼起来的：
     * 关卡精灵先占住 0..GFX_FLAT_COUNT-1（P9 为了让动画帧号稳定），
     * 立绘从 GFX_FLAT_COUNT 开始 ✗
     *
     * 所以这里要加偏移。**只在这一处加** —— 下标到资源的换算只此一家，
     * 散在多处迟早会漏掉某个。
     *
     * 踩过的坑：不加偏移时，剧情把关卡的 10x22 小人当立绘用了 ——
     * 表现是"魔女一直不出现，屏幕上却多出一个不认识的小人"，
     * 靠肉眼很难联想到是**下标基准**错了。是"从显存渲染 + 逐像素比对"
     * 的验证手段把它逼出来的（差异图和实机画面并排一看就明白了）。 */
    id += GFX_FLAT_COUNT;
    if (gfx_sprites_count <= 0) return &gfx_sprites[0];
    if (id < 0) id = 0;
    if (id >= gfx_sprites_count) id = gfx_sprites_count - 1;
    return &gfx_sprites[id];
}

/* 三个位置：左贴边 / 居中 / 右贴边 */
static int char_x(int pos, const GfxAsset *a)
{
    if (pos == SC_POS_LEFT)
        return SPRITE_MARGIN;
    if (pos == SC_POS_CENTER)
        return (SCR_W - a->w) / 2;
    return SCR_W - a->w - SPRITE_MARGIN;
}

/* ---------------------------------------------------------------------
 * 对话框
 * ------------------------------------------------------------------- */
static void draw_box_frame(void)
{
    gfx_fill_rect(BOX_X, BOX_Y, BOX_W, BOX_H, CLR_BOX_FILL);
    gfx_rect_border(BOX_X, BOX_Y, BOX_W, BOX_H, CLR_BOX_EDGE);
}

static void draw_name_plate(void)
{
    /* 名字画在对话框**内部**，不再单独做一个浮在框外的牌子。
     * 原因是踩过一个 bug：牌子挂在框外时，旁白（说话人为空）只是"不画"，
     * 却没把上一句的名字擦掉 —— 结果旁白旁边一直挂着"魔女"。
     * 画在框内就没这个问题：每次换句都会重画整个框，旧名字自然被覆盖。 */
    if (text_count(s_speaker) == 0) return;      /* 旁白：不画名字 */
    text_draw(NAME_X, NAME_Y, s_speaker, CLR_CURSOR);
}

/* 只重画对话框里的正文区域（推进对话时每帧都会走这里） */
static void redraw_text(void)
{
    int y0 = TEXT_Y - 2;
    int h  = TEXT_LINES * LINE_H + 3;

    gfx_fill_rect(BOX_X + 2, y0, BOX_W - 4, h, CLR_BOX_FILL);
    text_draw_layout(&s_layout, TEXT_X, TEXT_Y, LINE_H, s_reveal, CLR_TEXT);

    /* 这一句显示完了：在右下角闪一个 ▼，提示"可以按 A 继续" */
    if (!s_typing) {
        if ((game_frame() / 30) & 1)
            text_draw(BOX_X + BOX_W - 16, BOX_Y + BOX_H - 14, "▼", CLR_CURSOR);
    }
}

static void draw_box(void)
{
    draw_box_frame();
    draw_name_plate();
    redraw_text();
}

/* ---------------------------------------------------------------------
 * 立绘层
 *
 *  只恢复对话框以上的区域：对话框是不透明的，下半部分本来就该被它盖住。
 *  这样既擦干净了立绘，又不会把对话框一起擦掉。
 * ------------------------------------------------------------------- */
static void redraw_sprites(void)
{
    gfx_restore_rect(0, 0, SCR_W, BOX_Y);

    for (int pos = 0; pos < SC_POS_N; pos++) {
        if (s_char[pos] < 0) continue;
        const GfxAsset *a = char_of(s_char[pos]);
        gfx_draw_sprite(a, char_x(pos, a), SPRITE_Y);
    }
}

/* ---------------------------------------------------------------------
 * 对外接口
 * ------------------------------------------------------------------- */
void vn_clear_chars(void)
{
    for (int i = 0; i < SC_POS_N; i++) s_char[i] = -1;
}

void vn_show_bg(int id)
{
    s_bg = bg_of(id);
    gfx_draw_bg(s_bg);
}

void vn_redraw(void)
{
    gfx_draw_bg(s_bg);
    redraw_sprites();
    draw_box();
}

void vn_after_overlay(void)
{
    /* 关掉浮层（选项/菜单）之后，把被它盖住的立绘和对话框恢复回来 */
    redraw_sprites();
    draw_box();
}

void vn_begin(void)
{
    /* 清干净：立绘、剧本指针、**还有台词和说话人**。
     *
     * 【这里修了一个真实的 bug】
     * 原来**故意不清** s_text / s_speaker —— 那是 P7 纯重构时的约束
     *（"行为不能变"），注释里也写了"要改得单独提出来改"。现在改了 ✓
     *
     * 不清的后果：开局的第一条 CMD_BG 会把对话框画出来 ✓
     * 而那时 s_text 还是**上一周目的最后一句** ✗
     * 于是玩家看到的是"上局结尾的台词"在开局闪一下 ✓
     * 下一帧 CMD_SAY 才把它盖掉 ✓ 看着像画面抖了一下 ✓
     *
     * 后果不严重，但它是**每次重玩都会出现**的可见瑕疵 ✓
     * 而且"新的一局还带着上一局的台词"本身就是错的 ✓
     */
    vn_clear_chars();
    /* ⚠ s_text / s_speaker 是 `const char *`（指向字符串），不是数组 ✗
     * 所以只能**改指针**，不能往里面写字符 ✓
     *（第一版我写了 s_speaker[0] = '\0' ✓ 那是往字符串字面量里写 ✓
     *  未定义行为 ✓ 在 GBA 上很可能直接崩 ✓ ——写之前先看清类型 ✓）
     *
     * 置成空串就够了 ✗ draw_box() 看到 s_text 为空 ✓ 不会画任何字 ✓
     * s_reveal 是打字机进度 ✓ 也要归零 ✓ 否则下一句会"已经打完" ✓ */
    s_text = "";
    s_speaker = "";
    s_reveal = 0;
    s_pc = 0;
}

/* 执行命令，直到遇到需要等玩家的命令（说话 / 选项 / 结束） */
VnStop vn_run(void)
{
    while (s_pc >= 0 && s_pc < scenario_count) {
        const ScCmd *c = &scenario[s_pc];
        s_cmd = c;

        switch (c->op) {
        case CMD_BG:
            s_bg = bg_of(c->a);
            gfx_draw_bg(s_bg);
            redraw_sprites();
            draw_box();
            s_pc++;
            break;

        case CMD_CHAR:
            s_char[c->a] = (s8)c->b;
            redraw_sprites();
            draw_box();
            s_pc++;
            break;

        case CMD_HIDE:
            s_char[c->a] = -1;
            redraw_sprites();
            draw_box();
            s_pc++;
            break;

        case CMD_JUMP:
            s_pc = c->t1;
            break;

        /* ---- 音频（P6）：语音走 A，BGM/音效走 B ---- */
        case CMD_VOICE:
            if (c->a < snd_clips_count) snd_play_voice(&snd_clips[c->a]);
            s_pc++;
            break;

        case CMD_BGM:
            if (c->a < snd_clips_count) snd_play_bgm(&snd_clips[c->a], c->b);
            s_pc++;
            break;

        case CMD_BGM_STOP:
            snd_stop_bgm();
            s_pc++;
            break;

        case CMD_SE:
            if (c->a < snd_clips_count) snd_play_se(&snd_clips[c->a]);
            s_pc++;
            break;

        case CMD_SAY:
            s_speaker = c->s1;
            s_text    = c->s2;
            text_layout(s_text, TEXT_MAX_PX, TEXT_LINES, &s_layout);
            s_total   = text_count(s_text);
            s_reveal  = 0;
            s_timer   = 0;
            s_typing  = 1;
            draw_box();
            s_pc++;                             /* 下一条命令等按键后再执行 */
            return VN_STOP_SAY;

        case CMD_CHOICE:
            return VN_STOP_CHOICE;

        /* P10：剧本要求换玩法（"演到这里开始打关卡"）。
         * **先把 pc 推进一格再返回** —— 关卡玩完回来接着演下一句，
         * 不会卡在同一个命令上反复进关卡。 */
        case CMD_MODE:
            s_req_mode = c->a;
            s_pc++;
            return VN_STOP_MODE;

        case CMD_END:
        default:
            return VN_STOP_END;
        }
    }
    /* 剧本跑完了（防御性） */
    return VN_STOP_END;
}

void vn_tick(void)
{
    /* 打字机：每 TYPE_SPEED 帧多显示一个字 */
    if (!s_typing) return;
    s_timer++;
    if (s_timer >= TYPE_SPEED) {
        s_timer = 0;
        s_reveal++;
        if (s_reveal >= s_total) {
            s_reveal = s_total;
            s_typing = 0;
        }
        redraw_text();
    }
}

VnStop vn_advance(void)
{
    if (s_typing) {                       /* 还在打字 → 立刻显示完 */
        s_reveal = s_total;
        s_typing = 0;
        redraw_text();
        return VN_STOP_SAY;
    }
    if (snd_voice_busy()) {
        /* 文字已显示完、但语音还在播：第一下按键**掐掉语音**，不推进。
         * 这是 galgame 的通用习惯（不想听可以直接跳过，但不会误跳下一句）。 */
        snd_stop_voice();
        return VN_STOP_SAY;
    }
    return vn_run();                      /* 已显示完 → 下一条命令 */
}

/* ---------------------------------------------------------------------
 * 选项：文字由引擎给，画菜单由调用方负责（ui_menu）
 * ------------------------------------------------------------------- */
int vn_choice_count(void)
{
    return 2;                             /* 剧本里一个选项就是两条分支 */
}

const char *vn_choice_text(int i)
{
    if (!s_cmd) return "";
    return (i == 0) ? s_cmd->s1 : s_cmd->s2;
}

void vn_choice_commit(int i)
{
    if (!s_cmd) return;
    s_pc = (i == 0) ? s_cmd->t1 : s_cmd->t2;
}

int vn_requested_mode(void)
{
    return s_req_mode;
}
