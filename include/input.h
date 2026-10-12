/* =====================================================================
 *  input.h —— 输入动作映射
 *
 *  游戏代码不该直接问"A 键按了吗"，而该问"确认键按了吗"：
 *    · 以后要做按键设置（重绑），只改这一张表
 *    · 做关卡模式时，"跳跃"和"确认"可以是同一个键，但语义分开写更清楚
 *    · 自动演示（attract mode）的虚拟按键也在这里注入，
 *      不用在每个用到按键的地方都套一层宏
 * ===================================================================== */
#ifndef INPUT_H
#define INPUT_H

#include <tonc.h>

typedef enum {
    ACT_CONFIRM = 0,    /* 确认 / 推进（默认 A）*/
    ACT_CANCEL,         /* 取消 / 跳过（默认 B）*/
    ACT_UP,
    ACT_DOWN,
    ACT_LEFT,           /* P8 加的：VN 只用上下，关卡模式要左右走 */
    ACT_RIGHT,
    ACT_MENU,           /* 菜单（默认 START）*/
    ACT_COUNT
} InputAction;

void input_poll(int frame);             /* 每帧调一次（传帧号，自动演示要按节奏来）*/
int  input_hit(InputAction a);          /* 这一帧刚按下 */
int  input_down(InputAction a);         /* 正按着（连发用）*/
int  input_held_frames(InputAction a);  /* 已经按了连续几帧（松手清零）*/

/* 方向轴：关卡模式"往哪走"比"哪个键"好用，一次拿到 dx/dy（各是 -1/0/1）*/
void input_axis(int *dx, int *dy);

/* 自动演示模式：游戏自己按固定节奏产生虚拟按键（编译期 GAL_AUTOPLAY 打开）*/
void input_autoplay_enable(int on);

#endif /* INPUT_H */
