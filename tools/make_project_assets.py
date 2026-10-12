#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_project_assets.py —— 把**项目里的素材**编译成 C 资源表（P5 核心）

以前引擎只认识写死的 5 个资源（bg_title/bg_ocean/char_witch/char_girl），
所以编辑器里放第三张背景、第三个角色，实机根本不认。
现在改成：编辑器导出时写一份清单（scenario/assets.json），这个工具按清单
生成"索引表"，引擎用下标取资源 —— **任意数量的背景、角色、表情都能用**。

生成的三个文件：
    source/assets/gfx_data.s       .incbin 原始像素（BGR555）
    source/assets/gfx_assets.c     索引表：gfx_bgs[] / gfx_sprites[]
    include/gfx_assets.h           表和计数的声明 + 标题背景下标

清单格式（由 gbastudio/core/compiler.py 写出）：
    {
      "title_bg": 0,
      "bg":      [ {"name": "海岸", "src": "…/assets/bg/海岸.png"}, … ],
      "sprites": [ {"char": "witch", "pose": "normal", "src": "…/normal.png"}, … ]
    }

素材转换**复用 tools/make_assets.py 的函数**（和预览渲染同一套），
所以编辑器里看到的立绘/背景，和烧进 ROM 的必然一致。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

SPRITE_H = 120          # 立绘统一缩放到这个高度（和旧引擎一致）


def log(m):
    print('[assets] ' + m)


def convert(src, out_dir, base_name, kind):
    """
    转换一个素材，返回 (GfxAsset 初始化参数, bin 文件名)。
    直接调 make_assets 的函数，保证和编译器/预览完全一致。

    kind：'bg' 背景 / 'spr' 立绘 / 'flat' 精灵（原尺寸）/ 'logo' 标题图
    （踩过：这里曾经把立绘判成 'char'，而调用方传的是 'spr'，
      结果立绘按背景转了 —— 全屏 240x160、丢掉透明、体积大三倍）
    """
    import make_assets as MA
    if not os.path.isfile(src):
        raise RuntimeError('素材不存在：%s' % src)
    old_gfx, old_out = MA.GFX_DIR, MA.OUT_DIR
    MA.GFX_DIR = os.path.dirname(src)
    MA.OUT_DIR = out_dir
    try:
        if kind == 'spr':
            img, key = MA.make_character(os.path.basename(src), base_name, SPRITE_H)
            w, h = img.size
        elif kind == 'flat':
            # P9：精灵**不缩放**。立绘要缩到 120 高（那是立绘的规矩），
            # 16x24 的走路帧照那个规矩拉大就废了。
            img, key = MA.make_sprite_native(os.path.basename(src), base_name)
            w, h = img.size
        elif kind == 'logo':
            img, key = MA.make_logo(os.path.basename(src), base_name, 200, 53)
            w, h = img.size
        else:
            img = MA.make_background(os.path.basename(src), base_name)
            w, h, key = img.width, img.height, 0
    finally:
        MA.GFX_DIR, MA.OUT_DIR = old_gfx, old_out
    return (base_name, w, h, key), base_name + '.bin'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=os.path.join(ROOT, 'scenario', 'assets.json'))
    ap.add_argument('--assets-dir', default=os.path.join(ROOT, 'source', 'assets'))
    ap.add_argument('--include-dir', default=os.path.join(ROOT, 'include'))
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    global log
    if a.quiet:
        log = lambda m: None

    if not os.path.isfile(a.manifest):
        print('[assets] 没有清单文件 %s' % a.manifest)
        print('[assets] （旧流程：由 make_assets.py 处理写死的资源）')
        return 2

    with open(a.manifest, encoding='utf-8') as f:
        mani = json.load(f)

    os.makedirs(a.assets_dir, exist_ok=True)
    bgs, sprites, asm, total = [], [], [], 0

    def add(kind, entry, idx):
        nonlocal total
        base = '%s_%d' % (kind, idx)
        info, binname = convert(entry['src'], a.assets_dir, base, kind)
        total += os.path.getsize(os.path.join(a.assets_dir, binname))
        asm.append((base, binname))
        log('%-10s #%d  %-22s %dx%d  %s' % (kind, idx, entry.get('name', ''),
                                            info[1], info[2], binname))
        return info

    for i, e in enumerate(mani.get('bg', [])):
        bgs.append(add('bg', e, i))
    # P9：精灵**先**排进 sprites[]，占住下标 0..N-1。
    # 动画表（anim_data.c）按这个顺序记下标，所以顺序不能受"剧本用了几个立绘"影响。
    for i, e in enumerate(mani.get('flat', [])):
        sprites.append(add('flat', e, len(sprites)))
    for i, e in enumerate(mani.get('sprites', [])):
        sprites.append(add('spr', e, len(sprites)))
    logo = None
    if mani.get('logo'):
        logo = add('logo', mani['logo'], 0)

    if not bgs and not sprites:
        # **不能在这里退出** ✗
        # 以前是 `return 1` ✓ 于是"一张图都没有的工程"会让 build-assets
        # 在第 3 步抛错 ✓ 后面几步（音频/关卡/动画）全都不跑 ✓
        # 最后在**链接期**报一堆 undefined reference（anim_defs / gfx_logo_asset …）✗
        # 而"新建的工程"正好就是一张图都没有 ✓ 所以这个坑一定会踩到 ✓
        #
        # 正确做法：照常往下走 ✓ 产出**空表** + logo 兜底 ✓
        # 引擎那边本来就是按"表长可能是 0"写的 ✓
        print('[assets] 清单里没有素材 —— 生成空表（引擎需要这些符号存在）')

    # ---------------- gfx_data.s ----------------
    with open(os.path.join(a.assets_dir, 'gfx_data.s'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('/* 由 tools/make_project_assets.py 自动生成，请勿手工修改 */\n')
        f.write('    .section .rodata\n\n')
        for sym, binname in asm:
            f.write('    .global gfx_%s\n    .align 2\ngfx_%s:\n'
                    '    .incbin "%s"\n\n' % (sym, sym, binname))

    # ---------------- gfx_assets.c ----------------
    title_bg = int(mani.get('title_bg', 0))
    if not (0 <= title_bg < len(bgs)):
        title_bg = 0
    with open(os.path.join(a.assets_dir, 'gfx_assets.c'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write('/* 由 tools/make_project_assets.py 自动生成，请勿手工修改 */\n')
        f.write('#include "gfx_assets.h"\n\n')
        for sym, _ in asm:
            f.write('extern const u16 gfx_%s[];\n' % sym)
        f.write('\n')
        if bgs:
            f.write('const GfxAsset gfx_bgs[] = {\n')
            for sym, w, h, key in bgs:
                f.write('    { gfx_%s, %d, %d, 0x%04X },\n' % (sym, w, h, key))
            f.write('};\nconst int gfx_bgs_count = %d;\n\n' % len(bgs))
        else:
            f.write('const GfxAsset gfx_bgs[1] = { { 0, 0, 0, 0 } };\n'
                    'const int gfx_bgs_count = 0;\n\n')
        if sprites:
            f.write('const GfxAsset gfx_sprites[] = {\n')
            for sym, w, h, key in sprites:
                f.write('    { gfx_%s, %d, %d, 0x%04X },\n' % (sym, w, h, key))
            f.write('};\nconst int gfx_sprites_count = %d;\n' % len(sprites))
        else:
            f.write('const GfxAsset gfx_sprites[1] = { { 0, 0, 0, 0 } };\n'
                    'const int gfx_sprites_count = 0;\n')
        if logo:
            sym, w, h, key = logo
            f.write('\nconst GfxAsset gfx_logo_asset = { gfx_%s, %d, %d, 0x%04X };\n'
                    % (sym, w, h, key))
        else:
            # 没 logo 也要给一个 0x0 的空资源（否则链接期报 undefined reference）
            f.write('\nconst GfxAsset gfx_logo_asset = { 0, 0, 0, 0 };\n')

    # ---------------- gfx_assets.h ----------------
    hdr = os.path.join(a.include_dir, 'gfx_assets.h')
    with open(hdr, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_project_assets.py 自动生成，请勿手工修改 */\n')
        f.write('#ifndef GFX_ASSETS_H\n#define GFX_ASSETS_H\n\n')
        f.write('#include <tonc.h>\n\n')
        f.write('/* 一个位图资源：像素指针 + 尺寸；立绘另带透明 key */\n')
        f.write('typedef struct {\n'
                '    const u16 *px;\n'
                '    u16 w, h;\n'
                '    u16 key;\n'
                '} GfxAsset;\n\n')
        f.write('/* 背景表：剧本里 CMD_BG 的 a 字段就是这张表的下标 */\n')
        f.write('extern const GfxAsset gfx_bgs[];\nextern const int gfx_bgs_count;\n\n')
        f.write('/* 立绘表：CMD_CHAR 的 b 字段是下标（角色+表情在编译时已展开） */\n')
        f.write('extern const GfxAsset gfx_sprites[];\n'
                'extern const int gfx_sprites_count;\n\n')
        # **关卡精灵占了前面几个下标** ✗
        #
        # 这张表是「关卡精灵 + 立绘」拼起来的：为了让动画帧号稳定，
        # 关卡精灵先占住 0..N-1（见上面 flat 的那段注释），立绘从 N 开始。
        # 而剧情里的 char 下标是**立绘表自己的编号**（从 0 开始）——
        # 两者差一个 N，引擎必须加上这个偏移，否则剧情会
        # 把关卡小人当立绘画出来（踩过：魔女一直不出现，屏幕上却多出一个小人）。
        n_flat = len(mani.get('flat', []))
        f.write('/* 关卡精灵占了前 %d 个下标；剧情 char 的下标要加上它 */\n'
                '#define GFX_FLAT_COUNT %d\n\n' % (n_flat, n_flat))
        f.write('/* 标题画面用哪张背景 */\n#define GFX_TITLE_BG %d\n' % title_bg)
        # **logo 必须无条件声明** ✗
        # 引擎的标题画面引用 gfx_logo_asset，而这里原来只在"工程里有 logo"时才声明 ✗
        # 结果：新建的工程（没有 logo）一编译就报
        #     error: 'gfx_logo_asset' undeclared
        # —— 整份代码都编不过 ✗ 背景和立绘本来就有空表兜底，logo 漏了。
        f.write('/* 标题 LOGO（没有 logo 的工程用 0x0 的空资源兜底） */\n'
                'extern const GfxAsset gfx_logo_asset;\n')
        f.write('\n#endif /* GFX_ASSETS_H */\n')

    log('背景 %d 张，立绘 %d 张，共 %.1f KB'
        % (len(bgs), len(sprites), total / 1024))
    if total > 24 * 1024 * 1024:
        print('[assets] ⚠ 资源 %.1f MB 超过卡带常见容量，建议压缩背景或减少数量'
              % (total / 1024 / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
