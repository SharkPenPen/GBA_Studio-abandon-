/* 由 tools/make_project_assets.py 自动生成，请勿手工修改 */
#ifndef GFX_ASSETS_H
#define GFX_ASSETS_H

#include <tonc.h>

/* 一个位图资源：像素指针 + 尺寸；立绘另带透明 key */
typedef struct {
    const u16 *px;
    u16 w, h;
    u16 key;
} GfxAsset;

/* 背景表：剧本里 CMD_BG 的 a 字段就是这张表的下标 */
extern const GfxAsset gfx_bgs[];
extern const int gfx_bgs_count;

/* 立绘表：CMD_CHAR 的 b 字段是下标（角色+表情在编译时已展开） */
extern const GfxAsset gfx_sprites[];
extern const int gfx_sprites_count;

/* 关卡精灵占了前 0 个下标；剧情 char 的下标要加上它 */
#define GFX_FLAT_COUNT 0

/* 标题画面用哪张背景 */
#define GFX_TITLE_BG 0
/* 标题 LOGO（没有 logo 的工程用 0x0 的空资源兜底） */
extern const GfxAsset gfx_logo_asset;

#endif /* GFX_ASSETS_H */
