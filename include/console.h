/* =====================================================================
 *  console.h —— 屏幕文字（HUD / 调试输出）
 *
 *  为什么需要它：
 *    GBA 没有操作系统、没有终端，printf 默认往一个"黑洞"里写。
 *    这个模块把 libtonc 的 TTE（Tonc Text Engine）接上，让文字真的画到屏幕上。
 *    任何游戏都需要它：分数、血量、调试变量都靠它显示。
 *
 *  两种用法：
 *    con_printf(x, y, "HP: %d", hp);     // 指定位置画一行（推荐，位置可控）
 *    iprintf("HP: %d\n", hp);            // 像 PC 上一样用，自动换行（已接通 stdout）
 *
 *  限制（GBA 的客观条件，不是 bug）：
 *    - 默认用 8x8 的固定宽度点阵字体，只能显示 ASCII（英文/数字/符号），
 *      没有中文字库。要显示中文需要自己做点阵字库。
 *    - 浮点数请用定点整数代替（GBA 没有 FPU，%f 又慢又占空间）。
 * ===================================================================== */
#ifndef CONSOLE_H
#define CONSOLE_H

/* 初始化文字系统。必须在你把 REG_DISPCNT 设为模式 3 之后调用。
 * 同时会把 stdout 设为无缓冲，这样 iprintf 的输出会立刻出现在屏幕上。 */
void con_init(void);

/* 用背景色擦掉整屏文字（注意：它会填满整屏，会盖掉你的画面，
 * 所以通常在你自己的清屏之后、画文字之前用不到它）。 */
void con_clear(void);

/* 移动"光标"（供 iprintf 自动换行使用） */
void con_gotoxy(int x, int y);

/* 在 (x, y) 处画一行文字，不自动换行。
 * 返回画完之后的 x 坐标，方便接着往后画。 */
int  con_print(int x, int y, const char *text);

/* 在 (x, y) 处画一行格式化文字，用法和 printf 一样（整数版）。 */
void con_printf(int x, int y, const char *fmt, ...);

/* 当前光标位置（像素） */
void con_getpos(int *x, int *y);

#endif /* CONSOLE_H */
