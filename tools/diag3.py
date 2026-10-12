# -*- coding: utf-8 -*-
"""
diag3.py —— 连上 mGBA 后**先让它继续跑**，再中断读寄存器

前一版踩的坑：GDB 客户端一连上，mGBA 会把游戏复位并在入口停住
（读到的 s_frame 一直是 0、VCOUNT 不变 —— 那是开机瞬间的状态）。
正确流程是：连接 → 发 c(continue) 让它跑 → 过一会儿发 0x03 中断 → 再读。
"""
import subprocess
import sys
import time

sys.path.insert(0, r"D:\GitHud\GBA_AI\.tmp")
from read_regs import RSP, cksum

ELF = r"D:\GitHud\GBA_AI\build\sample_auto.elf"
NM = r"D:\GitHud\GBA_AI\.toolchain\arm-none-eabi-gcc\bin\arm-none-eabi-nm.exe"


def syms():
    out = subprocess.run([NM, ELF], capture_output=True, text=True).stdout
    d = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3:
            d[p[2]] = int(p[0], 16)
    return d


def main():
    addrs = syms()
    r = RSP()

    print('  连接后先让游戏跑 12 秒（进入第一幕，BGM 应该在放）…')
    r.s.sendall(b'$c#63')          # continue
    time.sleep(12)
    r.s.sendall(b'\x03')           # 中断
    time.sleep(0.8)
    try:
        r.s.recv(4096)             # 丢掉中断响应
    except Exception:
        pass

    print()
    print('  === 引擎状态（这次应该是运行中的真实值） ===')
    for name, n in (('s_frame', 4), ('s_pc', 4), ('s_state', 1), ('s_ready', 4),
                    ('s_voice', 4), ('s_bgm', 4), ('s_bgm_playing', 4), ('s_se', 4),
                    ('s_typing', 4), ('s_total', 4)):
        if name not in addrs:
            continue
        b = r.read(addrs[name], n)
        v = int.from_bytes(b, 'little') if b else None
        print('    %-14s = %s' % (name, ('0x%0*X' % (n * 2, v)) if v is not None else '读失败'))

    print()
    print('  === 音频硬件寄存器 ===')
    REG = [('SOUNDCNT_X 总开关', 0x04000084, 2),
           ('SOUNDCNT_H A/B 音量与输出', 0x04000082, 2),
           ('TM0CNT 语音定时器', 0x04000102, 2),
           ('TM0D   语音重载值', 0x04000100, 2),
           ('DMA1CNT 语音DMA', 0x040000BC, 4),
           ('DMA1SAD 语音DMA源', 0x040000B8, 4),
           ('TM1CNT BGM定时器', 0x04000106, 2),
           ('TM1D   BGM重载值', 0x04000104, 2),
           ('DMA2CNT BGM DMA', 0x040000C8, 4),
           ('DMA2SAD BGM DMA源', 0x040000C4, 4)]
    vals = {}
    for name, addr, n in REG:
        b = r.read(addr, n)
        v = int.from_bytes(b, 'little') if b else None
        vals[name.split()[0]] = v
        print('    %-26s = %s' % (name, ('0x%0*X' % (n * 2, v)) if v is not None else '读失败'))

    print()
    print('  === 判定 ===')
    x = vals.get('SOUNDCNT_X') or 0
    h = vals.get('SOUNDCNT_H') or 0
    t1 = vals.get('TM1CNT') or 0
    d2 = vals.get('DMA2CNT') or 0
    src = vals.get('DMA2SAD') or 0
    print('    总开关 SOUNDCNT_X bit7      : %s' % ('开 ✓' if x & 0x80 else '关 ✗'))
    print('    DS B 左右输出 (bit12/13)    : %s'
          % ('开 ✓' if (h & 0x1000) and (h & 0x2000) else '关 ✗'))
    print('    BGM 定时器 TM1CNT bit7      : %s' % ('跑 ✓' if t1 & 0x80 else '停 ✗'))
    print('    BGM DMA 使能 bit31          : %s' % ('是 ✓' if d2 & 0x80000000 else '否 ✗'))
    print('    BGM DMA 源地址              : 0x%08X %s'
          % (src, '（指向 ROM ✓）' if 0x08000000 <= src < 0x0A000000 else '（不对 ✗）'))
    if 'snd_aud_0' in addrs:
        print('    期望的 BGM 数据首地址        : 0x%08X' % addrs['snd_aud_0'])
    r.close()


if __name__ == '__main__':
    main()
