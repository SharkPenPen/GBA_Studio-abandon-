#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_obj.py —— 用 GDB 桩读硬件精灵的现场（排查 OBJ 不显示）

思路：不再靠截图猜。直接读三样东西：
    1. DISPCNT（0x04000000）—— 精灵层到底开了没有、是不是 1D 图块映射
    2. OAM（0x07000000，128 项 × 8 字节）—— 属性 0/1/2 拼得对不对
    3. OBJ 图块显存（0x06014000 起）和 OBJ 调色板（0x05000200 起）
       —— 数据到底有没有写进去

用法：
    python tools/dump_obj.py --elf build/p12d.elf --wait 6
（ROM 必须用 -Define GAL_AUTOPLAY,GAL_USE_OBJ,GAL_OBJ_DEBUG 编译，
  并且用 mGBA -g 启动等这个脚本接上去。）
"""
import argparse
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from read_regs import RSP      # noqa: E402

OAM = 0x07000000
PAL_OBJ = 0x05000200
OBJ_VRAM = 0x06014000
DISPCNT = 0x04000000


def nm_addr(elf, name):
    nm = os.path.join(ROOT, '.toolchain', 'arm-none-eabi-gcc', 'bin',
                      'arm-none-eabi-nm.exe')
    out = subprocess.run([nm, elf], capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3 and p[2] == name:
            return int(p[0], 16)
    return None


def read_u32(rsp, addr):
    for _ in range(4):
        try:
            b = rsp.read(addr, 4)
            if b and len(b) == 4:
                return struct.unpack('<I', b)[0]
        except Exception:                     # noqa: BLE001
            pass
        rsp.s.sendall(b'+')
        time.sleep(0.05)
    return None


def read_mem(rsp, addr, n, chunk=256):
    out = b''
    while len(out) < n:
        k = min(chunk, n - len(out))
        got = None
        for _ in range(4):
            try:
                got = rsp.read(addr + len(out), k)
                if got and len(got) == k:
                    break
            except Exception:                 # noqa: BLE001
                pass
            rsp.s.sendall(b'+')
            time.sleep(0.03)
        if not got or len(got) != k:
            return out
        out += got
    return out


def halt(rsp):
    rsp.s.sendall(b'\x03')
    time.sleep(0.08)
    rsp._recv_packet()
    rsp.s.sendall(b'+')
    time.sleep(0.02)


def cont(rsp):
    rsp.s.sendall(b'$c#63')
    rsp.s.sendall(b'+')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True)
    ap.add_argument('--wait', type=float, default=6.0)
    ap.add_argument('--port', type=int, default=2345)
    a = ap.parse_args()

    rsp = RSP(port=a.port)
    cont(rsp)
    print('  等 %.0f 秒让游戏自己走到关卡…' % a.wait)
    time.sleep(a.wait)
    halt(rsp)

    dc = read_u32(rsp, DISPCNT)
    print()
    print('  DISPCNT = 0x%04X' % dc)
    print('    mode          = %d' % (dc & 7))
    print('    BG0/1/2/3 开  = %d %d %d %d'
          % (dc & 1, (dc >> 1) & 1, (dc >> 2) & 1, (dc >> 3) & 1))
    print('    OBJ 层开      = %d   ← 必须是 1' % ((dc >> 12) & 1))
    print('    OBJ 1D 映射   = %d   ← 必须是 1（DCNT_OBJ_1D=0x40）' % ((dc >> 6) & 1))
    print('    强制空白      = %d' % ((dc >> 7) & 1))

    for name in ('s_obj_ready', 's_tiles_used', 's_tile_of', 's_bpp'):
        ad = nm_addr(a.elf, name)
        if ad is None:
            continue
        if name == 's_tile_of':
            raw = read_mem(rsp, ad, 16)
            vals = [struct.unpack('<b', raw[i:i + 1])[0] for i in range(min(8, len(raw)))]
            print('  %-12s = %s' % (name, vals))
        else:
            v = read_u32(rsp, ad)
            print('  %-12s = %d' % (name, v if v is not None else -1))

    print()
    print('  OAM（前 8 个精灵）:')
    oam = read_mem(rsp, OAM, 8 * 8)
    for i in range(8):
        if len(oam) < i * 8 + 8:
            break
        a0, a1, a2, _ = struct.unpack('<HHHH', oam[i * 8:i * 8 + 8])
        y, x = a0 & 0xFF, a1 & 0x1FF
        shape = (a0 >> 14) & 3
        size = (a1 >> 14) & 3
        tile = a2 & 0x3FF
        mode = (a0 >> 8) & 3
        pal = (a2 >> 12) & 15
        prio = (a2 >> 10) & 3
        if a0 == 0 and a1 == 0 and a2 == 0:
            continue
        print('    #%-3d attr0=%04X attr1=%04X attr2=%04X | y=%3d x=%3d 模式=%d '
              'shape=%d size=%d 图块=%d 调色板组=%d 优先级=%d'
              % (i, a0, a1, a2, y, x, mode, shape, size, tile, pal, prio))

    print()
    pal = read_mem(rsp, PAL_OBJ, 32)
    print('  OBJ 调色板前 16 色: %s'
          % ' '.join('%04X' % struct.unpack('<H', pal[i:i + 2])[0]
                     for i in range(0, min(32, len(pal)) - 1, 2)))
    tiles = read_mem(rsp, OBJ_VRAM, 64)
    nz = sum(1 for b in tiles if b)
    print('  OBJ 图块显存 0x06014000 前 64 字节: 非零 %d 个' % nz)
    if nz:
        print('    %s' % ' '.join('%02X' % b for b in tiles[:32]))
    rsp.close()


if __name__ == '__main__':
    main()
