/* =====================================================================
 *  GBA 中文 galgame 测试框架
 *  ---------------------------------------------------------------------
 *  这是把 PC 平台的 galgame 往 GBA 移植的一次完整试探：从 1920x1080 的
 *  素材、几万字的剧本文本，一直做到 240x160、288KB 内存的掌机上能跑。
 *
 *  目录分工：
 *    scenario/scenario.txt   剧本（纯文本，改剧情只动这个文件）
 *    tools/build_script.py   剧本 → C 命令数组（顺便收集字库要用到的字）
 *    tools/make_cjk_font.py  按需生成 10x10 中文点阵字库
 *    tools/make_assets.py    图片 → GBA 的 16 位色位图数据
 *    source/gfx.c            位图绘制原语（DMA 搬运、透明 blit）
 *    source/text.c           中文文字渲染（UTF-8 解码 + 二分查字库 + 禁则换行）
 *    source/galgame.c        引擎（状态机、对话框、立绘、选项、菜单）
 *
 *  重新生成资源（改了剧本或素材之后）：
 *    .\scripts\build-assets.ps1
 *
 *  操作：↑↓ 选择   A 确认/推进   B 跳过动画   START 菜单   长按 A 快进
 * ===================================================================== */

#include <tonc.h>

#include "gfx.h"
#include "text.h"
#include "galgame.h"

int main(void)
{
    gfx_init();          /* 显示模式、DMA 等硬件初始化 */
    gal_init();          /* 引擎初始化：进入标题画面 */

    /* 主循环：每秒约 60 圈
     *   vid_vsync() 等这一帧画完；key_poll() 取一次按键快照；
     *   剩下的交给引擎，引擎内部按"只重画变化的部分"来画。 */
    while (1) {
        vid_vsync();
        key_poll();
        gal_update();
    }

    return 0;            /* GBA 上不会走到这里 */
}
