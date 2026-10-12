/* =====================================================================
 *  game.c —— 通用游戏层实现
 * ===================================================================== */
#include "game.h"

static int s_frame;
static int s_state;
static int s_stack[GAME_STACK_MAX];
static int s_depth;

void game_init(void)
{
    s_frame = 0;
    s_state = 0;
    s_depth = 0;
}

void game_tick(void)
{
    s_frame++;
}

int game_frame(void)
{
    return s_frame;
}

void game_state_set(int st)
{
    s_state = st;
    s_depth = 0;                /* 直接切换 = 丢掉历史（比如"回到标题"）*/
}

void game_state_push(int st)
{
    if (s_depth < GAME_STACK_MAX)
        s_stack[s_depth++] = s_state;
    s_state = st;
}

int game_state_pop(void)
{
    if (s_depth <= 0)
        return -1;
    s_state = s_stack[--s_depth];
    return s_state;
}

int game_state(void)
{
    return s_state;
}
