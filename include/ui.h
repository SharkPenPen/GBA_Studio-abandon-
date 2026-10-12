/* =====================================================================
 *  ui.h —— 通用界面控件（任何类型的游戏都用得上）
 *
 *  目前提供三样：
 *    ui_panel()   一个描边的面板
 *    ui_menu()    竖排菜单（标题菜单、暂停菜单、剧情选项都是它）
 *    ui_message() 整屏文字页（关于 / 提示）
 *
 *  为什么把菜单抽出来：标题、暂停、选项这三处的画法**本质是同一个东西** ——
 *  一个框 + 若干项 + 高亮当前项 + 左边一个三角光标。原来各写一遍，
 *  改个间距要改三处、还容易改漏。现在样式用一张表描述（UiMenuStyle）。
 * ===================================================================== */
#ifndef UI_H
#define UI_H

#include <tonc.h>

/* 菜单外观。三种菜单只差这几个数字，所以能用同一个函数画。 */
typedef struct {
    u16 fill;       /* 底色 */
    int item_h;     /* 每项的行高 */
    int pad_top;    /* 第一项距菜单顶部的距离 */
    int text_dx;    /* 文字相对菜单左边的偏移 */
    int cursor_dx;  /* 三角光标相对菜单左边的偏移 */
    int centered;   /* 文字是否在 (w - 2*text_dx) 范围内居中 */
} UiMenuStyle;

void ui_panel(int x, int y, int w, int h, u16 fill);

/* 画菜单。h 是框高（各菜单自己算，不在这里猜）。 */
void ui_menu(int x, int y, int w, int h, const char **items, int n,
             int sel, const UiMenuStyle *st);

/* 擦掉菜单：把底下原来的画面恢复回来（比整屏重画省事，也不闪）*/
void ui_menu_erase(int x, int y, int w, int h);

/* 整屏文字页；footer 画在底部提示怎么返回（可以为 NULL）*/
void ui_message(const char **lines, int n, int line_h, const char *footer);

#endif /* UI_H */
