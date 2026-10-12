/* =====================================================================
 *  level.h —— 关卡模式（P8：验证"多类型"是不是真的）
 *
 *  和 vn.c 是**并列**的：两个都是"某一种玩法"，共用下面四层：
 *      game.c   帧计数 + 界面栈
 *      input.c  动作映射（P8 给它补了左右方向）
 *      ui.c     通用菜单
 *      gfx/text 位图与文字
 *
 *  这一版是最小可玩：一张图块地图 + 方向键走的角色 + 撞墙。
 *  故意不做的东西（留给后面）：镜头滚动、图块动画、NPC、道具。
 * ===================================================================== */
#ifndef LEVEL_H
#define LEVEL_H

#include <tonc.h>

/* 玩家在关卡里想干什么（由应用层决定切成哪个界面）*/
typedef enum {
    LVL_EVENT_NONE = 0,
    LVL_EVENT_EXIT,         /* 按了 START：想回标题 */
} LvlEvent;

void lvl_enter(void);           /* 进入关卡：画地图、把玩家放到出生点 */
void lvl_exit(void);            /* 离开关卡：**把硬件精灵藏起来**（否则它会留在剧情画面上）*/
void lvl_update(void);          /* 每帧：读方向键 → 走 → 撞墙就停 */
LvlEvent lvl_event(void);       /* 取一次事件（取完清掉）*/

/* 给应用层的只读信息（做 HUD 或调试用）*/
int lvl_player_tx(void);
int lvl_player_ty(void);

#endif /* LEVEL_H */
