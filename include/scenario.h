/* 由 tools/build_script.py 自动生成，请勿手工修改 */
#ifndef SCENARIO_H
#define SCENARIO_H

#include <tonc.h>

/* 命令类型 */
typedef enum {
    CMD_END, CMD_BG, CMD_CHAR, CMD_HIDE, CMD_SAY, CMD_CHOICE, CMD_JUMP, CMD_VOICE, CMD_BGM, CMD_BGM_STOP, CMD_SE, CMD_MODE
} ScOp;

/* 玩法编号（CMD_MODE 的 a）—— 剧本里写 `mode 1` 就是切到关卡 */
typedef enum {
    MODE_VN    = 0,     /* 视觉小说 */
    MODE_LEVEL = 1,     /* 关卡 */
    MODE_N     = 2,
} GameMode;

/* 背景编号 = gfx_bgs[] 的下标（由 make_project_assets.py 按项目素材生成） */
/* 人物编号 = gfx_sprites[] 的下标（角色+表情在编译时展平成一维表） */
/* 立绘位置：左 / 中 / 右 */
typedef enum { SC_POS_LEFT = 0, SC_POS_CENTER = 1, SC_POS_RIGHT = 2, SC_POS_N = 3 } ScPos;

/* 一条剧本命令。
 *   CMD_BG     a=背景下标（gfx_bgs）
 *   CMD_CHAR   a=位置(ScPos)  b=立绘下标（gfx_sprites）
 *   CMD_HIDE   a=位置
 *   CMD_SAY    s1=说话人（空串=旁白）  s2=台词
 *   CMD_CHOICE s1/s2=两个选项文本      t1/t2=各自的跳转目标
 *   CMD_JUMP   t1=目标下标
 *   CMD_VOICE  a=音频下标（走 Direct Sound A，一次播完）
 *   CMD_BGM    a=音频下标  b=是否循环（走 B）
 *   CMD_BGM_STOP 停止 BGM
 *   CMD_SE     a=音频下标（抢占 B，播完自动把 BGM 接回去）
 *   CMD_MODE   a=玩法编号（GameMode）—— 剧情演到这里切成关卡，
 *              关卡退出后**回到剧本的下一句继续**
 *   CMD_END    结束，回标题 */
typedef struct {
    u8  op;
    u8  a;
    u8  b;
    u8  pad;
    const char *s1;
    const char *s2;
    u16 t1;
    u16 t2;
} ScCmd;

extern const ScCmd scenario[];
extern const int scenario_count;

#endif /* SCENARIO_H */
