#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_assets.py —— 把 PC 尺寸的美术素材转换成 GBA 能直接用的位图数据

【为什么需要这一步】
    GBA 屏幕只有 240x160、15 位色（BGR555），而 PC 上的 galgame 素材通常是
    1920x1080 的 24 位图。移植时必须做：缩放 → 降色深 → 去掉背景 → 变成 C 能读的二进制。

【输出格式】（全部小端序 u16，每个像素一个 u16）
    像素值 = (r>>3) | ((g>>3)<<5) | ((b>>3)<<10)     即 BGR555
    立绘四角是"透明"的，用 key 色表示；每个立绘自带自己的 key（见 gfx_assets.h）

【产物】
    source/assets/*.bin          原始像素数据（由 .incbin 汇编进 ROM）
    source/assets/gfx_data.s     汇编存根，把 .bin 变成 C 可链接的符号
    source/assets/gfx_assets.c   资源描述表（尺寸 + key 色）
    include/gfx_assets.h         对外声明
    .tmp/assets_preview.png      转换结果预览（人工检查用）

用法（用 DSH 自带 Python，里面有 Pillow）：
    <bundled-python> tools/make_assets.py
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw

# ------------------------------------------------------------------ 路径
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX_DIR     = os.path.join(ROOT, 'assets_src', 'images')
OUT_DIR     = os.path.join(ROOT, 'source', 'assets')
INC_DIR     = os.path.join(ROOT, 'include')
TMP_DIR     = os.path.join(ROOT, '.tmp')

SCR_W, SCR_H = 240, 160

# 立绘高度（像素）。这个值不只是美术问题，也是**性能问题**：
#   模式 3 下立绘是软件逐像素贴上去的（没有硬件精灵），
#   一开始设成 148，两张立绘一帧要写约 4.8 万个像素，
#   超过"电子束从上扫到对话框(y=98)之前"的时间预算，
#   结果换立绘的那一帧会撕裂：立绘盖在对话框上面、文字区混进立绘像素。
#   降到 120 后像素量少了约 1/3，实测不再出现撕裂。
#   根治办法见 docs/05：用硬件精灵（模式 0）或双缓冲（模式 4）。
SPRITE_H = 120

# 候选 key 色（BGR555）。脚本会挑一个"该立绘里完全没出现过"的颜色，
# 这样 blit 时就能安全地把 key 当作透明。
KEY_CANDIDATES = [0x7C1F, 0x03E0, 0x7FFF, 0x001F, 0x7C00, 0x03FF, 0x0000, 0x4210]


def log(msg):
    print('[assets] ' + msg)


def to_bgr555(img):
    """RGB 图 -> BGR555 的 u16 数组"""
    a = np.asarray(img.convert('RGB'), dtype=np.uint16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    v = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
    return v.astype('<u2')


def save_bin(name, arr):
    path = os.path.join(OUT_DIR, name + '.bin')
    arr.tofile(path)
    log(f'  {name}.bin  {arr.shape[1] if arr.ndim == 2 else 0}x{arr.shape[0] if arr.ndim == 2 else 0}  {os.path.getsize(path):,} 字节')
    return path


def make_background(src_name, out_name):
    """全屏背景：1920x1080 -> 240x160 BGR555"""
    src = os.path.join(GFX_DIR, src_name)
    im = Image.open(src).convert('RGB')
    log(f'{src_name}  {im.width}x{im.height} -> {SCR_W}x{SCR_H}')
    im = im.resize((SCR_W, SCR_H), Image.LANCZOS)
    save_bin(out_name, to_bgr555(im))
    return im


def cut_background(im, thresh=40):
    """
    （备用方案）去掉"与画面边缘连通的白色背景"。

    只在素材**没有 alpha 通道**时才需要它。千万不要把它当成首选：
    本工程的素材全都自带 alpha，而 convert('RGB') 会把透明区变成黑色或白色垃圾，
    导致泛洪填充判错背景 —— 我第一次跑就踩了这个坑（紫发少女那张的包围盒
    被算成整幅 1920 宽，最后被压成 240x109 的畸形立绘）。
    """
    w, h = im.size
    small = im.resize((max(1, w // 2), max(1, h // 2)), Image.BILINEAR)
    work = small.copy()
    for seed in [(0, 0), (small.width - 1, 0), (0, small.height - 1), (small.width - 1, small.height - 1)]:
        try:
            ImageDraw.floodfill(work, seed, (255, 0, 255), thresh=thresh)
        except Exception:
            pass
    a = np.asarray(work, dtype=np.uint8)
    bg_small = (a[:, :, 0] > 200) & (a[:, :, 1] < 60) & (a[:, :, 2] > 200)
    bg = np.asarray(Image.fromarray((bg_small * 255).astype(np.uint8)).resize((w, h), Image.NEAREST)) > 128

    rgba = np.dstack([np.asarray(im.convert('RGB'), dtype=np.uint8),
                      np.where(bg, 0, 255).astype(np.uint8)])
    return Image.fromarray(rgba, 'RGBA')


def extract_rgba(src_name, thresh=40):
    """
    取出带透明信息的 RGBA 图。**优先使用文件自带的 alpha 通道**，
    只有素材确实没有 alpha 时才退回"抠白底"。
    """
    im = Image.open(os.path.join(GFX_DIR, src_name))
    if 'A' in im.getbands():
        a = np.asarray(im.getchannel('A'))
        frac = float((a < 128).mean())
        if frac > 0.005:
            log(f'  {src_name}: 使用素材自带的 alpha 通道（{frac*100:.1f}% 透明）')
            return im.convert('RGBA')
        log(f'  {src_name}: 有 alpha 但几乎不透明，改用抠白底')
    else:
        log(f'  {src_name}: 无 alpha 通道，改用抠白底')
    return cut_background(im.convert('RGB'), thresh)


def pick_key(arr_rgb, mask_opaque):
    """挑一个立绘自己没用到的颜色当透明 key"""
    used = set(np.unique(arr_rgb[mask_opaque]).tolist())
    for k in KEY_CANDIDATES:
        if int(k) not in used:
            return int(k)
    # 实在找不到就线性搜索
    for k in range(0x8000):
        if k not in used:
            return k
    return KEY_CANDIDATES[0]


def make_sprite_native(src_name, out_name):
    """
    精灵：**保持原尺寸**，只做"裁到内容包围盒 + 透明 key"，不缩放（P9）。

    为什么不能复用 make_character：那个会把图缩放到 120 像素高（立绘的尺寸）。
    16x24 的走路帧被拉成 120 高就废了 —— 精灵必须是**画多大就多大**，
    像素画尤其不能缩放（一缩就走形、还会引入半透明边缘）。

    顺带一提：不裁剪不行。PNG 画布常常比内容大（比如统一 32x32 的画布
    里画了个 16x24 的人），不裁的话每帧的"脚底位置"就对不齐，
    动画一播就上下抖。
    """
    rgba = extract_rgba(src_name)
    alpha = np.asarray(rgba)[:, :, 3]
    ys, xs = np.nonzero(alpha > 0)
    if len(xs) == 0:
        raise RuntimeError(f'{src_name}: 去背景后什么都不剩，阈值可能不对')
    ow, oh = rgba.size
    rgba = rgba.crop((int(xs.min()), int(ys.min()),
                      int(xs.max()) + 1, int(ys.max()) + 1))
    if (rgba.width, rgba.height) != (ow, oh):
        log(f'{src_name}  原图 {ow}x{oh} -> 裁到内容 {rgba.width}x{rgba.height}')

    a = np.asarray(rgba, dtype=np.uint8)
    opaque = a[:, :, 3] >= 128
    rgb = a[:, :, :3]
    key = pick_key(rgb, opaque)
    log(f'  精灵 {rgba.width}x{rgba.height}（不缩放），透明 key = 0x{key:04X}')

    out = to_bgr555(Image.fromarray(rgb, 'RGB')).astype(np.uint16)
    out[~opaque] = key
    save_bin(out_name, out)
    return Image.fromarray(np.dstack([rgb, np.where(opaque, 255, 0).astype(np.uint8)]), 'RGBA'), key


def make_character(src_name, out_name, target_h):
    """立绘：取 alpha -> 裁到人物包围盒 -> 缩放到目标高度 -> 输出（带透明 key）"""
    rgba = extract_rgba(src_name)
    alpha = np.asarray(rgba)[:, :, 3]

    ys, xs = np.nonzero(alpha > 0)
    if len(xs) == 0:
        raise RuntimeError(f'{src_name}: 去背景后什么都不剩，阈值可能不对')
    ow, oh = rgba.size
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    rgba = rgba.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))
    log(f'{src_name}  原图 {ow}x{oh} -> 人物包围盒 {rgba.width}x{rgba.height}')

    # 缩放：先按目标高度，若宽度超屏再按宽度压
    scale = target_h / rgba.height
    if rgba.width * scale > SCR_W:
        scale = SCR_W / rgba.width
    nw, nh = max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))
    rgba = rgba.resize((nw, nh), Image.LANCZOS)
    log(f'  缩放到 {nw}x{nh}（目标高度 {target_h}）')

    a = np.asarray(rgba, dtype=np.uint8)
    opaque = a[:, :, 3] >= 128          # 抗锯齿产生的半透明边缘按不透明处理，避免残影
    rgb = a[:, :, :3]
    key = pick_key(rgb, opaque)
    log(f'  透明 key = 0x{key:04X}')

    out = to_bgr555(Image.fromarray(rgb, 'RGB')).astype(np.uint16)
    out[~opaque] = key
    save_bin(out_name, out)
    return Image.fromarray(np.dstack([rgb, np.where(opaque, 255, 0).astype(np.uint8)]), 'RGBA'), key


def make_logo(src_name, out_name, max_w, max_h):
    """标题 LOGO：取 alpha，保持长宽比缩放到不超过 max_w x max_h"""
    rgba = extract_rgba(src_name, thresh=60)
    alpha = np.asarray(rgba)[:, :, 3]
    ys, xs = np.nonzero(alpha > 0)
    rgba = rgba.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = min(max_w / rgba.width, max_h / rgba.height)
    nw, nh = max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))
    rgba = rgba.resize((nw, nh), Image.LANCZOS)
    log(f'{src_name}  内容 {xs.max()-xs.min()+1}x{ys.max()-ys.min()+1} -> {nw}x{nh}')

    a = np.asarray(rgba, dtype=np.uint8)
    opaque = a[:, :, 3] >= 128
    key = pick_key(a[:, :, :3], opaque)
    out = to_bgr555(Image.fromarray(a[:, :, :3], 'RGB')).astype(np.uint16)
    out[~opaque] = key
    save_bin(out_name, out)
    log(f'  透明 key = 0x{key:04X}')
    return Image.fromarray(np.dstack([a[:, :, :3], np.where(opaque, 255, 0).astype(np.uint8)]), 'RGBA'), key


def write_asm_and_header(entries):
    """生成 .s 存根与 C 头文件/描述表"""
    # --- 汇编存根：把每个 .bin 变成符号 ---
    s_path = os.path.join(OUT_DIR, 'gfx_data.s')
    with open(s_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_assets.py 自动生成，请勿手工修改 */\n')
        f.write('    .section .rodata\n')
        for e in entries:
            f.write(f'\n    .global {e["sym"]}\n    .align 2\n{e["sym"]}:\n')
            f.write(f'    .incbin "{e["name"]}.bin"\n')
    log(f'  gfx_data.s  {len(entries)} 个符号')

    # --- 头文件 ---
    h_path = os.path.join(INC_DIR, 'gfx_assets.h')
    with open(h_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_assets.py 自动生成，请勿手工修改 */\n')
        f.write('#ifndef GFX_ASSETS_H\n#define GFX_ASSETS_H\n\n#include <tonc.h>\n\n')
        f.write('/* 一个位图资源：像素指针 + 尺寸；sprite 类资源另带透明 key */\n')
        f.write('typedef struct {\n    const u16 *px;\n    u16 w, h;\n    u16 key;      /* 仅立绘/LOGO 有意义 */\n} GfxAsset;\n\n')
        for e in entries:
            f.write(f'extern const GfxAsset {e["sym"]}_asset;\n')
        f.write('\n#endif /* GFX_ASSETS_H */\n')
    log(f'  gfx_assets.h')

    # --- 资源描述表（C） ---
    c_path = os.path.join(OUT_DIR, 'gfx_assets.c')
    with open(c_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* 由 tools/make_assets.py 自动生成，请勿手工修改 */\n')
        f.write('#include "gfx_assets.h"\n\n')
        for e in entries:
            f.write(f'extern const u16 {e["sym"]}[];\n')
        f.write('\n')
        for e in entries:
            f.write(f'const GfxAsset {e["sym"]}_asset = {{ {e["sym"]}, {e["w"]}, {e["h"]}, 0x{e["key"]:04X} }};\n')
    log(f'  gfx_assets.c')


def main():
    for d in (OUT_DIR, INC_DIR, TMP_DIR):
        os.makedirs(d, exist_ok=True)

    entries = []
    preview = Image.new('RGB', (SCR_W * 2 + 12, SCR_H * 2 + 12), (30, 30, 30))

    bg_title = make_background('biaotibeijing.png', 'bg_title')
    entries.append(dict(sym='gfx_bg_title', name='bg_title', w=SCR_W, h=SCR_H, key=0))
    bg_ocean = make_background('beijing.png', 'bg_ocean')
    entries.append(dict(sym='gfx_bg_ocean', name='bg_ocean', w=SCR_W, h=SCR_H, key=0))

    logo, logo_key = make_logo('biaoti.png', 'logo', 200, 56)
    entries.append(dict(sym='gfx_logo', name='logo', w=logo.width, h=logo.height, key=logo_key))

    witch, witch_key = make_character('jiaose01_zuo.png', 'char_witch', SPRITE_H)
    entries.append(dict(sym='gfx_char_witch', name='char_witch', w=witch.width, h=witch.height, key=witch_key))
    girl, girl_key = make_character('jiaose02_you.png', 'char_girl', SPRITE_H)
    entries.append(dict(sym='gfx_char_girl', name='char_girl', w=girl.width, h=girl.height, key=girl_key))

    write_asm_and_header(entries)

    # --- 预览图：棋盘格底 + 背景 + 立绘 ---
    def checker(w, h, s=8):
        im = Image.new('RGB', (w, h), (60, 60, 60))
        d = ImageDraw.Draw(im)
        for y in range(0, h, s):
            for x in range(0, w, s):
                if ((x // s) + (y // s)) % 2 == 0:
                    d.rectangle([x, y, x + s - 1, y + s - 1], fill=(110, 110, 110))
        return im

    pv = checker(SCR_W * 2 + 12, SCR_H + 12)
    pv.paste(bg_title, (4, 4))
    pv.paste(bg_ocean, (SCR_W + 8, 4))
    pv.save(os.path.join(TMP_DIR, 'preview_bg.png'))

    pv2 = checker(SCR_W, SCR_H)
    pv2.paste(bg_ocean, (0, 0))
    # 立绘按引擎里的摆放方式叠上去，检查透明 key 是否正确
    for im, x, y in ((witch, 8, SCR_H - witch.height), (girl, SCR_W - girl.width - 8, SCR_H - girl.height)):
        pv2.paste(im, (x, y), im)
    pv2.paste(logo, (20, 12), logo)
    pv2 = pv2.resize((SCR_W * 3, SCR_H * 3), Image.NEAREST)
    pv2.save(os.path.join(TMP_DIR, 'preview_scene.png'))
    log('预览图: .tmp/preview_bg.png（两张背景）、.tmp/preview_scene.png（合成场景）')


if __name__ == '__main__':
    main()
