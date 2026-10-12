#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grab_screen.py —— 不截图，直接读显存把画面渲染出来

【为什么要这样】
窗口截图（scripts/dev/shot-window.ps1）在这台机器上**不稳定** ✗：
窗口位置/时序一变就抓到别的东西，而且**不报错** —— 只是安静地给你一张
桌面或者 160x28 的碎片。它已经浪费过好几轮排查时间，
还让我得出过一次错误结论（"模式 1 花屏"，其实是抓到了模式切换那一帧）。

从显存渲染就没有这些问题：
    · 不依赖窗口位置、前台/后台、DPI
    · 结果是**确定**的，同一帧读两次必然一样（可以断言）
    · 能顺便把"这一帧的寄存器状态"一起打印出来，出问题直接看到原因

【能渲染哪些模式】
    mode 3  16bpp 位图     直接读 0x06000000 的 240x160 个 u16
    mode 4  8bpp 位图      读当前页 + BG 调色板
    mode 0/1 普通图块层     读调色板 + 图块 + 地图，自己拼出来（含 BG 优先级）
    mode 2  仿射图块层      按 PA/PB/PC/PD + 参考点做**逆变换**采样
    精灵（OBJ）             读 OAM + OBJ 图块 + OBJ 调色板，按优先级叠上去
    15 位色 → 8 位 RGB      直接 <<3 展开（和硬件显示一致，不做伽马）

【用法】
    python tools/grab_screen.py --out shot.png            # 连上就跑（自动 continue）
    python tools/grab_screen.py --wait 4 --out shot.png   # 等游戏跑 4 秒再抓
    python tools/grab_screen.py --probe                   # 只打印状态，不出图
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

from read_regs import RSP, RspError      # noqa: E402

try:
    from PIL import Image
except ImportError:
    print('  需要 Pillow（.tools/pylibs）')
    raise

W, H = 240, 160

# 调色板 / 显存
PAL_BG = 0x05000000
PAL_OBJ = 0x05000200
VRAM = 0x06000000
OAM = 0x07000000


def rgb15(c):
    """15 位色 → (r,g,b)。硬件就是每个通道 5 位直接显示，这里 <<3 补齐。"""
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def read_palette(r, base):
    b = r.read_block(base, 512)
    return list(struct.unpack('<256H', b))


def mode_of(dc):
    return dc & 7


def is_bitmap(m):
    return m >= 3


# ---------------------------------------------------------------------
# 位图模式
# ---------------------------------------------------------------------
def render_bitmap(r, m, pal):
    if m == 3 or m == 5:
        n = (W * H * 2) if m == 3 else (160 * 128 * 2)
        b = r.read_block(VRAM, n)
        px = struct.unpack('<%dH' % (len(b) // 2), b)
        w, h = (W, H) if m == 3 else (160, 128)
        img = Image.new('RGB', (w, h))
        img.putdata([rgb15(c) for c in px])
        return img
    # mode 4：8bpp，两页由 DISPCNT bit4 选
    page = 1 if (dc_page(r) & 0x10) else 0
    b = r.read_block(VRAM + page * 0xA000, W * H)
    img = Image.new('RGB', (W, H))
    img.putdata([rgb15(pal[i]) for i in b])
    return img


def dc_page(r):
    return r.read_u16(0x04000000)


# ---------------------------------------------------------------------
# 普通图块层（mode 0/1）
# ---------------------------------------------------------------------
def render_text_bg(r, bg, pal, canvas, prio_map):
    cnt = r.read_u16(0x04000008 + bg * 2)
    if not (r.read_u16(0x04000000) >> (8 + bg)) & 1:
        return                                   # 这一层没开
    cbb = (cnt & 0x000C) >> 2
    sbb = (cnt & 0x1F00) >> 8
    bpp8 = bool(cnt & 0x80)
    size = (cnt >> 14) & 3
    prio = cnt & 3
    hofs = r.read_u16(0x04000010 + bg * 4)
    vofs = r.read_u16(0x04000012 + bg * 4)

    map_w = {0: 32, 1: 64, 2: 32, 3: 64}[size]
    map_h = {0: 32, 1: 32, 2: 64, 3: 64}[size]
    # 地图：每个屏幕块 32x32 项、2KB
    mbytes = r.read_block(VRAM + sbb * 0x800, 0x800 * ((map_w // 32) * (map_h // 32)))
    entries = struct.unpack('<%dH' % (len(mbytes) // 2), mbytes)

    tile_bytes = 64 if bpp8 else 32
    tdata = r.read_block(VRAM + cbb * 0x4000, 0x4000)

    for sy in range(H):
        my = (sy + vofs) & (map_h * 8 - 1)
        for sx in range(W):
            mx = (sx + hofs) & (map_w * 8 - 1)
            # 屏幕块编号：每 32x32 项一块，横向块数 = map_w/32
            bx = mx // 256
            by = my // 256
            blk = by * (map_w // 32) + bx
            ent_off = blk * 1024 + ((my % 256) // 8) * 32 + ((mx % 256) // 8)
            if ent_off >= len(entries):
                continue
            e = entries[ent_off]
            tile = e & 0x3FF
            hf = (e >> 10) & 1
            vf = (e >> 11) & 1
            pb = (e >> 12) & 15
            px = mx & 7
            py = my & 7
            if hf:
                px = 7 - px
            if vf:
                py = 7 - py
            off = tile * tile_bytes
            if bpp8:
                if off + py * 8 + px >= len(tdata):
                    continue
                ix = tdata[off + py * 8 + px]
            else:
                if off + py * 4 + (px >> 1) >= len(tdata):
                    continue
                byte = tdata[off + py * 4 + (px >> 1)]
                ix = (byte >> 4) if (px & 1) else (byte & 15)
                ix += pb * 16
            if ix == 0:
                continue                          # 下标 0 = 透明，露出下层
            prev = prio_map[sy * W + sx]
            if prev is not None and prev <= prio:
                continue
            prio_map[sy * W + sx] = prio
            canvas[sy * W + sx] = rgb15(pal[ix])


# ---------------------------------------------------------------------
# 仿射图块层（mode 1 的 BG2 / mode 2 的 BG2/BG3）
# ---------------------------------------------------------------------
def render_affine_bg(r, bg, pal, canvas, prio_map):
    dc = r.read_u16(0x04000000)
    if not (dc >> (8 + bg)) & 1:
        return
    cnt = r.read_u16(0x04000008 + bg * 2)
    cbb = (cnt & 0x000C) >> 2
    sbb = (cnt & 0x1F00) >> 8
    bpp8 = bool(cnt & 0x80)
    wrap = bool(cnt & 0x2000)
    prio = cnt & 3
    size = (cnt >> 14) & 3
    side = {0: 16, 1: 32, 2: 64, 3: 128}[size]      # 地图边长（格）
    map_px = side * 8

    i = bg - 2
    pa = r.read_s16(0x04000020 + i * 16)
    pb = r.read_s16(0x04000022 + i * 16)
    pc = r.read_s16(0x04000024 + i * 16)
    pd = r.read_s16(0x04000026 + i * 16)
    refx = r.read_s32(0x04000028 + i * 16) >> 8      # 28 位定点，取整数部分
    refy = r.read_s32(0x0400002C + i * 16) >> 8

    # 逆矩阵：解 [pa pb; pc pd] · (tex - ref) = (scr - ref)
    det = pa * pd - pb * pc
    if det == 0:
        return
    mbytes = r.read_block(VRAM + sbb * 0x800, side * side)
    tdata = r.read_block(VRAM + cbb * 0x4000, 0x4000)
    tile_bytes = 64 if bpp8 else 32

    for sy in range(H):
        dy = sy - refy
        for sx in range(W):
            dx = sx - refx
            # 逆变换（8.8 定点）
            tx = refx + (pd * dx - pb * dy) * 256 // det
            ty = refy + (-pc * dx + pa * dy) * 256 // det
            tx //= 256
            ty //= 256
            if wrap:
                tx %= map_px
                ty %= map_px
            elif tx < 0 or ty < 0 or tx >= map_px or ty >= map_px:
                continue
            cell = (ty // 8) * side + (tx // 8)
            if cell >= len(mbytes):
                continue
            tile = mbytes[cell]
            px, py = tx & 7, ty & 7
            off = tile * tile_bytes
            if bpp8:
                if off + py * 8 + px >= len(tdata):
                    continue
                ix = tdata[off + py * 8 + px]
            else:
                if off + py * 4 + (px >> 1) >= len(tdata):
                    continue
                byte = tdata[off + py * 4 + (px >> 1)]
                ix = (byte >> 4) if (px & 1) else (byte & 15)
            if ix == 0:
                continue
            prev = prio_map[sy * W + sx]
            if prev is not None and prev <= prio:
                continue
            prio_map[sy * W + sx] = prio
            canvas[sy * W + sx] = rgb15(pal[ix])


# ---------------------------------------------------------------------
# 精灵（OBJ）
# ---------------------------------------------------------------------
OBJ_SHAPE = {0: {0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64)},
             1: {0: (16, 8), 1: (32, 8), 2: (32, 16), 3: (64, 32)},
             2: {0: (8, 16), 1: (8, 32), 2: (16, 32), 3: (32, 64)}}


def render_obj(r, canvas, prio_map):
    dc = r.read_u16(0x04000000)
    if not (dc >> 12) & 1:
        return                                   # 精灵层没开
    one_d = bool(dc & 0x40)
    pal = read_palette(r, PAL_OBJ)
    # 位图模式下 OBJ 图块只能放在 0x06014000 之后
    vbase = 0x06014000 if is_bitmap(mode_of(dc)) else 0x06010000
    tdata = r.read_block(vbase, 0x4000)

    oam = r.read_block(OAM, 128 * 8)
    for idx in range(127, -1, -1):
        a0, a1, a2, _ = struct.unpack('<HHHH', oam[idx * 8:idx * 8 + 8])
        if (a0 >> 8) & 3 == 2:
            continue                              # 禁用
        shape = (a0 >> 14) & 3
        size = (a1 >> 14) & 3
        wh = OBJ_SHAPE.get(shape, {}).get(size)
        if not wh:
            continue
        ow, oh = wh
        y = a0 & 0xFF
        if y >= 160:
            y -= 256
        x = a1 & 0x1FF
        if x >= 240:
            x -= 512
        tile = a2 & 0x3FF
        prio = (a2 >> 10) & 3
        pb = (a2 >> 12) & 15
        obpp8 = bool(a0 & 0x2000)
        tb = 64 if obpp8 else 32
        hf = (a1 >> 12) & 1
        vf = (a1 >> 13) & 1
        tw = ow // 8
        for sy in range(oh):
            yy = y + sy
            if yy < 0 or yy >= H:
                continue
            for sx in range(ow):
                xx = x + sx
                if xx < 0 or xx >= W:
                    continue
                px, py = sx, sy
                if hf:
                    px = ow - 1 - px
                if vf:
                    py = oh - 1 - py
                if one_d:
                    t = tile + (py // 8) * tw + (px // 8)
                else:
                    t = tile + (py // 8) * 32 + (px // 8)
                off = t * tb
                if obpp8:
                    if off + (py % 8) * 8 + (px % 8) >= len(tdata):
                        continue
                    ix = tdata[off + (py % 8) * 8 + (px % 8)]
                else:
                    o2 = off + (py % 8) * 4 + ((px % 8) >> 1)
                    if o2 >= len(tdata):
                        continue
                    byte = tdata[o2]
                    ix = (byte >> 4) if (px & 1) else (byte & 15)
                    ix += pb * 16
                if ix == 0:
                    continue
                prev = prio_map[yy * W + xx]
                if prev is not None and prev <= prio:
                    continue
                # 精灵之间：同优先级时编号小的盖住编号大的（硬件行为），
                # 这里按编号从大到小画，小的后画就压在上面
                prio_map[yy * W + xx] = prio
                canvas[yy * W + xx] = rgb15(pal[ix])


# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--wait', type=float, default=2.0,
                    help='连上后等多久再抓（让游戏跑到想要的画面）')
    ap.add_argument('--probe', action='store_true', help='只打印状态不出图')
    ap.add_argument('--frame-addr', default='',
                    help='帧计数变量地址（十六进制），给了就检查它会不会变')
    a = ap.parse_args()

    r = RSP()
    frame_addr = int(a.frame_addr, 16) if a.frame_addr else None
    # -g 启动时 CPU 停在启动处 → 先跑 a.wait 秒 → 再冻住 → 之后放心读
    r.run_for(a.wait)
    try:
        dc = r.probe(frame_addr)
        m = mode_of(dc)
        print('  已跑到第 %.1f 秒并冻住（读的是同一帧的快照）' % a.wait)
        print('  自检 DISPCNT=0x%04X 模式=%d %s'
              % (dc, m, 'OK' if m <= 5 else 'FAIL'))
        dc = r.read_u16(0x04000000)
        m = mode_of(dc)
        print('  冻结后 DISPCNT=0x%04X 模式=%d' % (dc, m))
        print('  层开关：BG0=%d BG1=%d BG2=%d BG3=%d OBJ=%d  1D图块=%d'
              % ((dc >> 8) & 1, (dc >> 9) & 1, (dc >> 10) & 1, (dc >> 11) & 1,
                 (dc >> 12) & 1, (dc >> 6) & 1))
        if m in (0, 1, 2):
            for i in range(4):
                c = r.read_u16(0x04000008 + i * 2)
                print('    BG%dCNT=0x%04X 优先级=%d 图块块=%d 地图块=%-2d %s 开=%d'
                      % (i, c, c & 3, (c & 0x0C) >> 2, (c & 0x1F00) >> 8,
                         '8bpp' if c & 0x80 else '4bpp', (dc >> (8 + i)) & 1))
        if m in (1, 2):
            for i in (0, 1):
                bg = 2 + i
                if not (dc >> (8 + bg)) & 1:
                    continue
                pa = r.read_s16(0x04000020 + i * 16)
                pb = r.read_s16(0x04000022 + i * 16)
                pc = r.read_s16(0x04000024 + i * 16)
                pd = r.read_s16(0x04000026 + i * 16)
                x = r.read_s32(0x04000028 + i * 16)
                y = r.read_s32(0x0400002C + i * 16)
                print('    BG%d 仿射 PA=%d PB=%d PC=%d PD=%d 参考点=(%.1f,%.1f)'
                      % (bg, pa, pb, pc, pd, x / 256.0, y / 256.0))

        if a.probe:
            return

        pal_bg = read_palette(r, PAL_BG)
        canvas = [rgb15(pal_bg[0])] * (W * H)      # 0 号色 = 背景色（backdrop）
        prio_map = [None] * (W * H)

        if m == 3 or m == 4 or m == 5:
            img = render_bitmap(r, m, pal_bg)
        else:
            # 图块模式：按优先级从后往前画（prio 大的先画）
            layers = [(r.read_u16(0x04000008 + i * 2) & 3, i) for i in range(4)]
            for _p, i in sorted(layers, reverse=True):
                if m == 2 or (m == 1 and i >= 2):
                    render_affine_bg(r, i, pal_bg, canvas, prio_map)
                else:
                    render_text_bg(r, i, pal_bg, canvas, prio_map)
            render_obj(r, canvas, prio_map)
            img = Image.new('RGB', (W, H))
            img.putdata(canvas)

        if a.out:
            img.save(a.out)
            print('  已保存 %s (%dx%d)' % (a.out, img.size[0], img.size[1]))
        else:
            print('  （没给 --out，没出图）')
    finally:
        try:
            r.cont()
        except Exception:                      # noqa: BLE001
            pass
        r.close()


if __name__ == '__main__':
    try:
        main()
    except RspError as e:
        print('  出错：%s' % e)
        sys.exit(1)
