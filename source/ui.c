/* =====================================================================
 *  ui.c —— 通用界面控件实现
 *
 *  坐标全部照搬重构前的写法，一个像素都没动 ——
 *  这次重构的目标就是"行为完全一致"，靠重启前后的录屏逐像素对比来验收。
 * ===================================================================== */
#include "ui.h"
#include "gfx.h"
#include "text.h"

void ui_panel(int x, int y, int w, int h, u16 fill)
{
    gfx_fill_rect(x, y, w, h, fill);
    gfx_rect_border(x, y, w, h, CLR_BOX_EDGE);
}

void ui_menu(int x, int y, int w, int h, const char **items, int n,
             int sel, const UiMenuStyle *st)
{
    ui_panel(x, y, w, h, st->fill);

    for (int i = 0; i < n; i++) {
        int iy = y + st->pad_top + i * st->item_h;
        u16 col = (i == sel) ? CLR_TEXT : CLR_DIM;
        if (st->centered)
            text_draw_center(x + st->text_dx, iy, w - st->text_dx * 2, items[i], col);
        else
            text_draw(x + st->text_dx, iy, items[i], col);
        if (i == sel)
            gfx_cursor_triangle(x + st->cursor_dx, iy, 10, CLR_CURSOR);
    }
}

void ui_menu_erase(int x, int y, int w, int h)
{
    /* 多擦 1 像素：边框画在 (x-1)~(x+w)，只擦 w 会留下一条边 */
    gfx_restore_rect(x - 1, y - 1, w + 2, h + 2);
}

void ui_message(const char **lines, int n, int line_h, const char *footer)
{
    gfx_fill_rect(0, 0, SCR_W, SCR_H, CLR_BOX_FILL);
    gfx_rect_border(2, 2, SCR_W - 4, SCR_H - 4, CLR_BOX_EDGE);

    int y = 16;
    for (int i = 0; i < n; i++) {
        text_draw(12, y, lines[i], CLR_TEXT);
        y += line_h + 1;
    }
    if (footer)
        text_draw(12, SCR_H - 16, footer, CLR_CURSOR);
}
