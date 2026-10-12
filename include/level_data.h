/* =====================================================================
 *  level_data.h —— 关卡地图数据（**自动生成，不要手改**）
 *
 *  生成者：tools/make_project_level.py
 *  数据来源：工程里的 level.txt（编辑器「关卡」模式画笔刷出来的）
 *
 *  地图是一维数组，按行优先存：lvl_map[ty * LVL_W + tx]
 *  图块编号：0=地板 1=墙 2=草 3=水（墙和水不可通行）
 * ===================================================================== */
#ifndef LEVEL_DATA_H
#define LEVEL_DATA_H

#include <tonc.h>

#define LVL_W        15
#define LVL_H        10
#define LVL_START_X  1        /* 出生点（格子坐标）*/
#define LVL_START_Y  1
#define TILE_KIND_N   4        /* 图块类型数 */

extern const u8 lvl_map[LVL_H * LVL_W];

#endif /* LEVEL_DATA_H */
