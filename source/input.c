/* =====================================================================
 *  input.c —— 输入动作映射实现
 *
 *  按键表：想改键位只动这里。
 *  自动演示的节奏和以前**完全一致**（第 120 帧按一次 A、
 *  第 480 帧后的第 60 帧按一次下），这样重构前后的录屏能逐像素对比。
 * ===================================================================== */
#include "input.h"

/* 每个动作对应哪个键（一个动作一个键，够用且简单）*/
static const u16 s_keymap[ACT_COUNT] = {
    [ACT_CONFIRM] = KEY_A,
    [ACT_CANCEL]  = KEY_B,
    [ACT_UP]      = KEY_UP,
    [ACT_DOWN]    = KEY_DOWN,
    [ACT_LEFT]    = KEY_LEFT,
    [ACT_RIGHT]   = KEY_RIGHT,
    [ACT_MENU]    = KEY_START,
};

static int s_autoplay;
static int s_auto_a;            /* 这一帧"虚拟按下"了确认键 */
static int s_auto_down;         /* 这一帧"虚拟按下"了方向下 */
static int s_auto_left;         /* 关卡演示用：正"按着"左 */
static int s_auto_right;        /* 关卡演示用：正"按着"右 */
static int s_held[ACT_COUNT];   /* 各动作连续按住的帧数 */

void input_autoplay_enable(int on)
{
    s_autoplay = on;
    s_auto_a = s_auto_down = s_auto_left = s_auto_right = 0;
    for (int i = 0; i < ACT_COUNT; i++) s_held[i] = 0;
}

void input_poll(int frame)
{
    if (s_autoplay) {
        /* 自动演示：每隔一段时间自己"按"一下，把剧情走完 */
        s_auto_a    = ((frame % 120) == 0);
        s_auto_down = ((frame % 480) == 60);
        /* 关卡演示：每 240 帧一个来回（右 120 帧、左 120 帧）。
         * **VN 从不读左右键**，所以加上这两条不会影响剧情模式的演示。 */
        s_auto_right = (((frame / 120) & 1) == 0);
        s_auto_left  = !s_auto_right;
    } else {
        s_auto_a = s_auto_down = 0;
        s_auto_left = s_auto_right = 0;
    }

    /* 注意：**只统计真实按键**，不统计虚拟按键。
     * 重构前自动演示只注入 key_hit，不注入 key_is_down，
     * 所以"按住 A 连发"在自动演示里从不触发 —— 这个细节要保持，
     * 否则自动演示的推进节奏会变（录屏就对不上了）。 */
    for (int i = 0; i < ACT_COUNT; i++) {
        s_held[i] = key_is_down(s_keymap[i]) ? (s_held[i] + 1) : 0;
    }
}

int input_hit(InputAction a)
{
    if (a < 0 || a >= ACT_COUNT) return 0;
    if (key_hit(s_keymap[a])) return 1;         /* key_hit 是本帧的新按下 */
    if (s_autoplay && s_keymap[a] == KEY_A)    return s_auto_a;
    if (s_autoplay && s_keymap[a] == KEY_DOWN) return s_auto_down;
    return 0;
}

int input_down(InputAction a)
{
    if (a < 0 || a >= ACT_COUNT) return 0;
    if (s_autoplay && s_keymap[a] == KEY_LEFT)  return s_auto_left;
    if (s_autoplay && s_keymap[a] == KEY_RIGHT) return s_auto_right;
    return key_is_down(s_keymap[a]);
}

int input_held_frames(InputAction a)
{
    if (a < 0 || a >= ACT_COUNT) return 0;
    return s_held[a];
}

void input_axis(int *dx, int *dy)
{
    int x = 0, y = 0;
    if (input_down(ACT_LEFT))  x -= 1;
    if (input_down(ACT_RIGHT)) x += 1;
    if (input_down(ACT_UP))    y -= 1;
    if (input_down(ACT_DOWN))  y += 1;
    /* 反方向同时按 = 不动（不然会抖）*/
    if (x > 1) x = 0;
    if (y > 1) y = 0;
    if (dx) *dx = x;
    if (dy) *dy = y;
}
