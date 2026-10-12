/* =====================================================================
 *  anim_data.h —— 精灵动画表（**自动生成，不要手改**）
 *
 *  生成者：tools/make_project_anim.py
 *  数据来源：工程文件里的 animations（编辑器「精灵」模式编的）
 * ===================================================================== */
#ifndef ANIM_DATA_H
#define ANIM_DATA_H

#include <tonc.h>

#define ANIM_N       0
#define ANIM_FRAME_N 0

/* 每个动画一条：从 anim_frames 的第几项开始、共几帧、是否循环 */
typedef struct {
    u8 first;
    u8 n;
    u8 loop;
} AnimDef;

extern const AnimDef anim_defs[ANIM_N ? ANIM_N : 1];
extern const u8 anim_frames[ANIM_FRAME_N ? ANIM_FRAME_N : 1];   /* 精灵下标 */
extern const u8 anim_durs[ANIM_FRAME_N ? ANIM_FRAME_N : 1];     /* 每帧停几帧 */

#endif /* ANIM_DATA_H */
