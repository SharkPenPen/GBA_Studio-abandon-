/* =====================================================================
 *  console.c —— 屏幕文字的实现（基于 libtonc 的 TTE）
 *
 *  原理，三句话：
 *    1. TTE 内部维护一个"当前目标画布"和"当前光标"。在模式 3 下，
 *       它直接往帧缓冲（VRAM）里写像素，所以文字能和你的图形画在同一层上。
 *    2. tte_write() 会从光标处开始画字符串，并自动向右推进光标。
 *    3. newlib 的 printf 最终会调用 _write()。我们把 _write() 覆盖掉，
 *       让它转交给 tte_write()，printf 就"通"到屏幕上了。
 * ===================================================================== */

#include <stdio.h>
#include <stdarg.h>
#include <tonc.h>

#include "console.h"

/* TTE 的字体数据（定义在 libtonc 的 src/font/sys8.s 里，已编进 libtonc.a）。
 * sys8Font 是 8x8 固定宽度点阵字体，覆盖 ASCII 0x20~0x7F。 */
extern const TFont sys8Font;

/* 行高（像素）。sys8 字体每行 8 像素。 */
#define CON_LINE_H 8

/* ---------------------------------------------------------------------
 * 初始化
 * ------------------------------------------------------------------- */
void con_init(void)
{
    /* 为"模式 3 的位图文字"初始化 TTE：
     *   参数 3          = 视频模式 3
     *   &sys8Font       = 使用 8x8 系统字体
     *   NULL            = 用 TTE 的默认字形渲染器（bmp16_drawg） */
    tte_init_bmp(3, &sys8Font, NULL);

    /* 颜色。模式 3 是 16 位直接色，所以这里给的是"字面颜色值"而不是调色板编号。
     * 注意 libtonc 的 RGB15() 是内联函数，用在运行期赋值没问题。 */
    tte_set_ink(RGB15(31, 31, 31));     /* 文字：白 */
    tte_set_shadow(RGB15(2, 2, 6));     /* 阴影：与背景同色（等于不要阴影） */
    tte_set_paper(RGB15(2, 2, 6));      /* 底色：与背景同色，擦除时不留白块 */

    tte_set_pos(0, 0);

    /* 关键一步：把 stdout 设为"无缓冲"。
     * newlib 默认把 stdout 当成块缓冲，printf 的内容要等缓冲区满了才真正调用
     * _write()，那样屏幕上半天不出现文字。设为 _IONBF 就每次都立刻输出。 */
    setvbuf(stdout, NULL, _IONBF, 0);
}

/* ---------------------------------------------------------------------
 * 光标与绘制
 * ------------------------------------------------------------------- */
void con_gotoxy(int x, int y)
{
    tte_set_pos(x, y);
}

void con_getpos(int *x, int *y)
{
    tte_get_pos(x, y);
}

int con_print(int x, int y, const char *text)
{
    tte_set_pos(x, y);
    return tte_write(text);
}

void con_printf(int x, int y, const char *fmt, ...)
{
    char buf[96];
    va_list args;

    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    tte_set_pos(x, y);
    tte_write(buf);
}

/* ---------------------------------------------------------------------
 * 覆盖 newlib 的 _write()，把 printf 的输出接到屏幕上
 *
 *  syscalls.c 里的 _write 标记为 __attribute__((weak))，
 *  所以这个强符号会替换掉它 —— 这是 C 链接器的标准机制。
 *
 *  为什么要攒成一段再画：
 *    printf 可能一次只给一个字符（也可能给一整行），逐字符调用 tte_write 太慢；
 *    这里先把不含换行的连续字符攒进小缓冲区，再一次性画出去。
 * ------------------------------------------------------------------- */
int _write(int file, char *ptr, int len)
{
    (void)file;

    char line[80];
    int n = 0;

    for (int i = 0; i < len; i++) {
        char c = ptr[i];

        if (c == '\n') {
            /* 先把这一行画完，再换到下一行行首 */
            if (n > 0) {
                line[n] = '\0';
                tte_write(line);
                n = 0;
            }
            int x, y;
            tte_get_pos(&x, &y);
            tte_set_pos(0, y + CON_LINE_H);
        } else if (c != '\r') {
            if (n >= (int)sizeof(line) - 1) {
                line[n] = '\0';
                tte_write(line);
                n = 0;
            }
            line[n++] = c;
        }
    }

    if (n > 0) {
        line[n] = '\0';
        tte_write(line);
    }

    return len;
}
