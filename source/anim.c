/* =====================================================================
 *  anim.c —— 精灵帧动画实现（P9）
 *
 *  数据表（anim_defs / anim_frames / anim_durs）由
 *  tools/make_project_anim.py 按工程里的动画自动生成。
 *
 *  一个容易踩的点：**帧计时是按"游戏帧"算的**，不是毫秒。
 *  GBA 一秒恒定 60 帧，所以"停 6 帧"就是 0.1 秒，简单又准。
 *  换成毫秒反而要读硬件定时器、还要处理掉帧。
 * ===================================================================== */
#include "anim.h"
#include "anim_data.h"

static const AnimDef *def_of(int id)
{
    if (id < 0 || id >= ANIM_N) return NULL;
    if (anim_defs[id].n == 0) return NULL;
    return &anim_defs[id];
}

void anim_init(Anim *a)
{
    a->id = -1;
    a->step = 0;
    a->timer = 0;
    a->done = 0;
}

void anim_play(Anim *a, int id)
{
    if (a->id == id) return;            /* 已经在播同一个，别打断进度 */
    anim_restart(a, id);
}

void anim_restart(Anim *a, int id)
{
    if (!def_of(id)) {
        anim_stop(a);
        return;
    }
    a->id = (s8)id;
    a->step = 0;
    a->timer = 0;
    a->done = 0;
}

void anim_stop(Anim *a)
{
    a->id = -1;
    a->step = 0;
    a->timer = 0;
    a->done = 0;
}

void anim_update(Anim *a)
{
    const AnimDef *d = def_of(a->id);
    if (!d || d->n == 0) return;

    a->timer++;
    int cur = anim_durs[d->first + a->step];
    if (cur < 1) cur = 1;

    if (a->timer < cur) return;
    a->timer = 0;

    if (a->step + 1 < d->n) {
        a->step++;
    } else if (d->loop) {
        a->step = 0;                    /* 循环：回到第一帧 */
    } else {
        a->done = 1;                    /* 播一次：停在最后一帧 */
    }
}

int anim_sprite_index(const Anim *a)
{
    const AnimDef *d = def_of(a->id);
    if (!d) return -1;
    int i = d->first + a->step;
    if (i < 0 || i >= ANIM_FRAME_N) return -1;
    return anim_frames[i];
}

int anim_is_done(const Anim *a)
{
    return a->done;
}

int anim_current(const Anim *a)
{
    return a->id;
}
