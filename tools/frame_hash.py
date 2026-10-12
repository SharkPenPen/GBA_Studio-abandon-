#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frame_hash.py —— 帧精确的画面验收工具（P7 重构用）

**为什么不能用截图对比**：
    mGBA 的截图是按"真实时间"抓的，两次运行会累积几帧到几秒的漂移 ——
    打字机差一个字、▼ 闪烁差半个周期、甚至抓到完全不同的剧情位置。
    靠这种截图证明"重构没改行为"是站不住的（试过，20 张里只有 5 张能对上）。

**这个工具的做法**：
    1. 连上 mGBA 的 GDB 桩（mGBA 在 attach 时会重置游戏，所以两边都从第 0 帧开始）
    2. 轮询游戏自己的帧计数（game.c 里的 s_frame），等到**指定帧号**
    3. 发中断把 CPU 停住 —— 此刻画面是冻结的，再读就不会变
    4. 读整块显存（mode 3 的帧缓冲 0x06000000，240x160x2 字节）算校验和
    5. 继续跑，等下一个目标帧

    这样两版 ROM 在**同一帧号**上的画面可以直接比校验和，不受时序影响。

用法：
    python tools/frame_hash.py --elf build/p7new.elf --symbol s_frame \\
        --frames 60,120,300,600 --out .tmp/hash_new.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from read_regs import RSP      # 复用已有的最小 RSP 客户端

FB_ADDR = 0x06000000           # mode 3 帧缓冲
FB_SIZE = 240 * 160 * 2        # 16 位色，一像素两字节
CHUNK = 256                    # 一次读多少字节（实测 mGBA 的桩超过 256 就回 E06）


def symbol_addr(elf, name):
    """从 ELF 里读符号地址（静态变量不在 map 里，但 nm 能查到）"""
    nm = os.path.join(ROOT, '.toolchain', 'arm-none-eabi-gcc', 'bin',
                      'arm-none-eabi-nm.exe')
    if not os.path.isfile(nm):
        for dp, dn, fn in os.walk(os.path.join(ROOT, '.toolchain')):
            if 'arm-none-eabi-nm.exe' in fn:
                nm = os.path.join(dp, 'arm-none-eabi-nm.exe')
                break
    out = subprocess.run([nm, elf], capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == name:
            return int(parts[0], 16)
    raise SystemExit('在 %s 里找不到符号 %s' % (elf, name))


def read_u32(rsp, addr, retry=4):
    """
    读一个 32 位字。

    注意：发 `0x03` 中断之后 mGBA 会回一个停止包（`T05...`），
    如果不先把它收走，紧接着的内存读就会把这个停止包当成应答，
    得到 "non-hexadecimal number" 的报错。所以这里失败就重试一次。
    """
    last = None
    for _ in range(retry):
        try:
            b = rsp.read(addr, 4)
            if len(b) == 4:
                return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
        except Exception as e:          # noqa: BLE001 —— 协议层脏数据，重试即可
            last = e
            rsp.s.sendall(b'+')
            time.sleep(0.05)
    raise SystemExit('读内存 0x%08X 一直失败：%s' % (addr, last))


def wait_for_frame(rsp, addr, target, limit_s=90.0):
    """
    等到帧计数 >= target。

    做法：中断 CPU → 读帧计数 → 没到就继续跑 → 再来一次。
    帧计数只在 VBlank 里 +1，所以"中断时读到的值"是稳定的。
    """
    t0 = time.time()
    while time.time() - t0 < limit_s:
        rsp.s.sendall(b'\x03')           # 中断
        time.sleep(0.08)
        rsp._recv_packet()               # 吃掉停止包（T05…）
        rsp.s.sendall(b'+')
        time.sleep(0.02)
        cur = read_u32(rsp, addr)
        if cur >= target:
            return cur
        rsp.s.sendall(b'$c#63')          # 继续跑
        rsp.s.sendall(b'+')
        time.sleep(0.12)
    return None


def hash_fb(rsp):
    """把整块显存读回来算个校验和（读失败就重试，协议层偶尔会脏）"""
    h = hashlib.md5()
    for off in range(0, FB_SIZE, CHUNK):
        n = min(CHUNK, FB_SIZE - off)
        for attempt in range(5):
            try:
                b = rsp.read(FB_ADDR + off, n)
            except Exception:            # noqa: BLE001
                b = None
            if b and len(b) == n:
                h.update(b)
                break
            rsp.s.sendall(b'+')
            time.sleep(0.05)
        else:
            raise SystemExit('读显存 0x%08X 失败（偏移 %d）' % (FB_ADDR, off))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True)
    ap.add_argument('--symbol', default='s_frame')
    ap.add_argument('--frames', default='60,120,300,600',
                    help='只用于显示；ROM 必须用 -Define GAL_FREEZE_AT=N 编译')
    ap.add_argument('--out', required=True)
    ap.add_argument('--port', type=int, default=2345)
    ap.add_argument('--addr', default='',
                    help='直接给符号地址（十六进制）。build\\ 是共用的，'
                         '下一次编译会把上一次的 elf 删掉，所以要么立刻测，'
                         '要么把地址记下来传进来。')
    a = ap.parse_args()

    if a.addr:
        addr = int(a.addr, 16)
        print('  [hash] %s 的 %s 在 0x%08X（手工指定）'
              % (os.path.basename(a.elf), a.symbol, addr))
    else:
        addr = symbol_addr(a.elf, a.symbol)
        print('  [hash] %s 的 %s 在 0x%08X' % (os.path.basename(a.elf), a.symbol, addr))

    rsp = RSP(port=a.port)
    rsp.s.sendall(b'$c#63')              # attach 会重置游戏，这里让它跑起来
    rsp.s.sendall(b'+')
    print('  [hash] 已连上 GDB 桩，游戏从头跑；ROM 会在 GAL_FREEZE_AT 指定的帧停住')

    res = {}
    for f in [int(x) for x in a.frames.split(',') if x.strip()]:
        print('  [hash] 等它跑到第 %d 帧…' % f)
        # ROM 用 GAL_FREEZE_AT 冻结，帧计数只会停在 f，不会超过 ——
        # 所以 wait_for_frame 返回时就是**恰好第 f 帧**。
        cur = wait_for_frame(rsp, addr, f)
        if cur is None:
            print('  [hash] 第 %d 帧没等到，跳过' % f)
            continue
        print('  [hash] 到了（帧计数 %d），读显存…' % cur)
        res[str(f)] = hash_fb(rsp)
        print('  [hash] 第 %4d 帧 → %s' % (f, res[str(f)]))
        rsp.s.sendall(b'$c#63')
        rsp.s.sendall(b'+')

    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(res, fp, indent=2)
    print('  [hash] 写入 %s（%d 帧）' % (a.out, len(res)))
    rsp.close()


if __name__ == '__main__':
    main()
