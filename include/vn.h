/* =====================================================================
 *  vn.h —— 视觉小说引擎（剧情执行 + 对话框 + 立绘 + 选项）
 *
 *  这一层是"galgame 专用"的：它认识剧本命令（scenario.h）、
 *  知道对话框该画在哪、立绘怎么摆。换一种游戏类型（关卡、RPG）
 *  就另写一个 *_game.c，复用 game/input/ui 三层，不需要动这个文件。
 *
 *  调用顺序（在界面状态机里就是这么用的）：
 *
 *      vn_begin();                        // 开始游戏：回到剧本开头
 *      VnStop why = vn_run();             // 一路执行到需要等玩家
 *      while (1) {
 *          vn_tick();                     // 每帧：打字机动画
 *          if (玩家按了确认) why = vn_advance();
 *          if (why == VN_STOP_CHOICE) { ...弹出选项菜单... }
 *          if (why == VN_STOP_END)    { ...回标题... }
 *      }
 * ===================================================================== */
#ifndef VN_H
#define VN_H

#include <tonc.h>

/* 剧本"停在哪" —— 由调用方决定接下来切到哪个界面 */
typedef enum {
    VN_STOP_NONE = 0,   /* 还在跑（一般不会返回这个）*/
    VN_STOP_SAY,        /* 停在一句台词上，等玩家推进 */
    VN_STOP_CHOICE,     /* 停在选项上，等玩家选 */
    VN_STOP_MODE,       /* P10：剧本要求换成另一种玩法（进关卡），用 vn_requested_mode() 问是哪个 */
    VN_STOP_END,        /* 剧本结束 */
} VnStop;

/* ---- 生命周期 ---- */
void vn_begin(void);            /* 从头开始（清立绘、pc=0）*/
void vn_redraw(void);           /* 整屏重画（从菜单回来时用）*/
void vn_show_bg(int id);        /* 换背景并画出来（标题画面也用它）*/
void vn_clear_chars(void);      /* 清掉所有立绘 */

/* ---- 每帧 ---- */
void vn_tick(void);             /* 打字机推进一个字 */
VnStop vn_advance(void);        /* 玩家推进一句：打字中→显示完；语音中→掐掉语音；否则下一条 */

/* ---- 剧本执行 ---- */
VnStop vn_run(void);            /* 执行命令直到需要等玩家 */

/* 剧本要求切模式时，问它"切到哪个"（GameMode）。返回 VN_STOP_MODE 之后才有效。
 * 注意：这时剧本指针**已经停在下一句**了 —— 关卡玩完回来直接 vn_run() 就接着演。 */
int  vn_requested_mode(void);

/* ---- 选项（画菜单由调用方用 ui_menu 负责，这里只管数据）*/
int  vn_choice_count(void);
const char *vn_choice_text(int i);
void vn_choice_commit(int i);   /* 选中第 i 项：跳到对应分支 */
void vn_after_overlay(void);    /* 关掉浮层后恢复立绘层和对话框 */

#endif /* VN_H */
