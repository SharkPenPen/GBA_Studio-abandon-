#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_video.py —— 读显示相关的寄存器和显存（排查某个显示模式画不对）

读什么：
    DISPCNT            当前模式、开了哪些层、1D 精灵映射
    BG0CNT..BG3CNT     每层的图块基址/地图基址/色深/尺寸/优先级
    BG0HOFS/VOFS       滚动
    BG2PA..BG2PD       仿射参数（模式 1/2 的仿射层）
    几个关键地址的显存内容（图块区、地图区）

为什么要读而不是截图：截图只能告诉你"画错了"，
读寄存器才能告诉你"哪一层的哪个字段没设对"。上一次查 OBJ 就是靠这个一轮定位的。

用法：
    python tools/dump_video.py --elf build/xxx.elf --wait 4
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

REGS = [
    ('DISPCNT', 0x04000000),
    ('BG0CNT', 0x04000008), ('BG1CNT', 0x0400000A),
    ('BG2CNT', 0x0400000C), ('BG3CNT', 0x0400000E),
    ('BG0HOFS', 0x04000010), ('BG0VOFS', 0x04000012),
    ('BG2PA', 0x04000020), ('BG2PB', 0x04000022),
    ('BG2PC', 0x04000024), ('BG2PD', 0x04000026),
    ('BG2X', 0x04000028), ('BG2Y', 0x0400002C),
]

BG_CBB_MASK, BG_SBB_MASK, BG_SIZE_MASK = 0x000C, 0x1F00, 0xC000


def read_u16(rsp, addr):
    for _ in range(4):
        try:
            b = rsp.read(addr, 2)
            if b and len(b) == 2:
                return struct.unpack('<H', b)[0]
        except Exception:                     # noqa: BLE001
            pass
        rsp.s.sendall(b'+')
        time.sleep(0.03)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wait', type=float, default=4.0)
    ap.add_argument('--port', type=int, default=2345)
    a = ap.parse_args()

    rsp = RSP(port=a.port)
    rsp.s.sendall(b'$c#63')
    rsp.s.sendall(b'+')
    print('  等 %.0f 秒…' % a.wait)
    time.sleep(a.wait)
    rsp.s.sendall(b'\x03')
    time.sleep(0.1)
    rsp._recv_packet()
    rsp.s.sendall(b'+')
    time.sleep(0.02)

    dc = read_u16(rsp, 0x04000000)
    print()
    print('  DISPCNT = 0x%04X  模式=%d  BG=%d%d%d%d  OBJ=%d  1D=%d'
          % (dc, dc & 7, (dc >> 3) & 1, (dc >> 2) & 1, (dc >> 1) & 1, dc & 1,
             (dc >> 12) & 1, (dc >> 6) & 1))
    print()
    for i in range(4):
        c = read_u16(rsp, 0x04000008 + i * 2)
        if c is None:
            continue
        print('  BG%dCNT = 0x%04X  优先级=%d 图块基址=%d 地图基址=%-2d 色深=%s 尺寸=%d'
              % (i, c, c & 3, (c & BG_CBB_MASK) >> 2, (c & BG_SBB_MASK) >> 8,
                 '8bpp' if (c & 0x80) else '4bpp', (c & BG_SIZE_MASK) >> 14))
    print()
    for name, ad in REGS:
        if name.endswith(('HOFS', 'VOFS')) or name.startswith('BG2') and name[3:5] in ('PA', 'PB', 'PC', 'PD'):
            v = read_u16(rsp, ad)
            print('  %-8s = 0x%04X (%d)' % (name, v, v))
    for name, ad in (('BG2X', 0x04000028), ('BG2Y', 0x0400002C)):
        b = read_mem(rsp, ad, 4)
        if len(b) == 4:
            print('  %-8s = 0x%08X' % (name, struct.unpack('<I', b)[0]))

    print()
    print('  显存抽样（每 2KB 看非零字节数）:')
    for base in range(0x06000000, 0x06018000, 0x800):
        b = read_mem(rsp, base, 0x100)
        nz = sum(1 for x in b if x)
        if nz:
            print('    0x%08X  非零 %3d/256   前 12 字节: %s'
                  % (base, nz, ' '.join('%02X' % x for x in b[:12])))
    rsp.close()


if __name__ == '__main__':
    main()
