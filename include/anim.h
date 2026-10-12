/* =====================================================================
 *  anim.h —— 精灵帧动画（P9）
 *
 *  一个"动画"就是一串帧 + 每帧停几帧（见 core/anim.py 的说明）。
 *  这里只管**播放进度**：现在该显示第几帧、什么时候换下一帧。
 *  "这一帧是哪张图"由调用方拿去查精灵表 —— 动画系统不该认识资源表。
 *
 *  用法：
 *      static Anim s_walk;
 *      anim_play(&s_walk, ANIM_WALK);
 *      ...
 *      anim_update(&s_walk);                     // 每帧调一次
 *      int ix = anim_sprite_index(&s_walk);      // 拿去 gfx_draw_sprite
 * ===================================================================== */
#ifndef ANIM_H
#define ANIM_H

#include <tonc.h>

typedef struct {
    s8  id;         /* 正在播哪个动画，-1 = 没在播 */
    u8  step;       /* 播到第几帧（动画内部的序号）*/
    u8  timer;      /* 这一帧已经停了几帧 */
    u8  done;       /* 不循环的动画播完了 */
} Anim;

void anim_init(Anim *a);
void anim_play(Anim *a, int id);        /* 换动画（同一个就不重播）*/
void anim_restart(Anim *a, int id);     /* 强制从头播 */
void anim_stop(Anim *a);
void anim_update(Anim *a);              /* 每帧调一次：推进计时、换帧 */

int  anim_sprite_index(const Anim *a);  /* 当前帧对应的精灵下标，-1 = 没有 */
int  anim_is_done(const Anim *a);
int  anim_current(const Anim *a);       /* 正在播哪个动画 */

#endif /* ANIM_H */
