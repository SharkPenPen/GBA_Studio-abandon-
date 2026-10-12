# -*- coding: utf-8 -*-
"""
read_regs.py —— 直接读 GBA 硬件寄存器（绕过 GDB 的协议探测）

为什么要自己写：mGBA 的 GDB 调试接口只实现了老的远程协议子集，
新版 arm-none-eabi-gdb 一上来就探测各种特性，mGBA 不答，握手就超时了
（"Remote replied unexpectedly to 'vMustReplyEmpty'"）。

但我们其实只需要"读内存 + 停机"这两个功能，协议就几条包：
    读   $m<地址十六进制>,<长度十六进制>#<校验和>
    继续 $c#63
    暂停 直接发一个 0x03 字节（不带 $），然后收停机回报 T/S
校验和 = 前面所有字符的 ASCII 之和 & 0xFF。

【2026-10 重写：修"读数不稳"】
原来读到过"模式 6"这种**不存在的值** —— 根因不是模拟器，是这个客户端：
    1. 收到包**不回 `+` 应答** → 对端会重发/顶住
    2. 收到包之后**不清残留** → 只要有一次响应没读干净，
       下一次请求就会读到上一次的字节，**请求和响应错位** ✗
    3. 读到的东西**不做任何合理性检查** → 错位的值被当成真值用了 ✗
现在：严格一问一答、逐字节找包边界、回 ACK、失败就重试并**报错**而不是返回垃圾。
"""
import socket
import sys
import time

HOST, PORT = '127.0.0.1', 2345


def cksum(s):
    return sum(ord(c) for c in s) & 0xFF


class RspError(Exception):
    """协议层出错（连不上、超时、应答对不上）"""


class RSP:
    """GDB 远程串行协议的最小实现：只做"读内存"和"停机/继续"。

    严格的同步规则（这是稳定的关键）：
        · 发请求前先把 socket 里的残留读干净
        · 每收到一个完整包，立刻回一个 '+'
        · 收到的包如果不是这次请求的应答，就丢掉继续等（而不是拿来当结果）
    """

    def __init__(self, host=HOST, port=PORT, timeout=5.0, debug=False, resume=False):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self.buf = b''
        self.debug = debug
        self.stats = {'req': 0, 'retry': 0, 'stale': 0}
        if resume:
            self.cont()

    def run_for(self, seconds):
        """让游戏跑 seconds 秒，然后**冻住**，返回时可以放心读。

        推荐用法：
            run_for(4)  →  读一堆东西  →  cont()

        （实测 mGBA 的桩**跑着也能读** —— 不是"必须停住才能读"。
          但**冻住再读**仍是对的：读到的是同一帧的快照，
          不会出现"上半屏这一帧、下半屏下一帧"的撕裂。）
        """
        self.cont()
        time.sleep(seconds)
        self.halt()

    # ---- 底层收发 ----
    def _drain(self):
        """把 socket 里已经到达的字节读进缓冲区（不阻塞太久）"""
        self.s.settimeout(0.02)
        try:
            while True:
                chunk = self.s.recv(4096)
                if not chunk:
                    break
                self.buf += chunk
        except socket.timeout:
            pass
        except OSError:
            pass
        finally:
            self.s.settimeout(5.0)

    def _ack(self):
        try:
            self.s.sendall(b'+')
        except OSError:
            pass

    def _next_packet(self, timeout=2.0):
        """从缓冲区里取一个 $...#xx 包；返回 (内容, 校验是否通过) 或 None"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            i = self.buf.find(b'$')
            if i >= 0:
                j = self.buf.find(b'#', i)
                if j >= 0 and len(self.buf) >= j + 3:
                    body = self.buf[i + 1:j]
                    got = self.buf[j + 1:j + 3]
                    self.buf = self.buf[j + 3:]
                    try:
                        want = int(got, 16)
                    except ValueError:
                        want = -1
                    ok = (cksum(body.decode('latin1')) == want)
                    return body.decode('latin1'), ok
                # 包还没收全
            if i > 0:                    # '$' 之前的杂字节（含 '+'/'-'）丢掉
                self.buf = self.buf[i:]
            try:
                chunk = self.s.recv(4096)
            except socket.timeout:
                continue
            except OSError as e:
                raise RspError('socket 出错: %s' % e)
            if not chunk:
                raise RspError('连接被对端关闭')
            self.buf += chunk
        return None

    # ---- 对外 ----
    def send_raw(self, payload):
        self.s.sendall(payload)

    def read(self, addr, n, tries=4):
        """读内存。每次请求都严格等它自己的应答；失败重试，最终仍失败则抛错。

        **协议细节（踩过）**：GDB 远程协议的 `m` 响应**就是纯十六进制**
        （比如 `$0010#c1`），**没有 `m` 前缀** ✗
        我一开始按"必须 m 开头"来判断，结果每个响应都被当成过期包丢掉 ✗
        表现是"永远没有应答" —— 看起来像模拟器不响应，其实是自己把答案扔了。
        """
        cmd = 'm%x,%x' % (addr, n)
        pkt = ('$%s#%02x' % (cmd, cksum(cmd))).encode()
        last = None
        for attempt in range(tries):
            self._drain()
            self.s.sendall(pkt)
            self.stats['req'] += 1
            hexs, ok = None, False
            for _ in range(4):
                got = self._next_packet()
                if got is None:
                    break
                body, ok = got
                self._ack()
                if body[:1] in ('T', 'S', 'W', 'X'):
                    self.stats['stale'] += 1     # 停机/继续回报，不是这次的答案
                    continue
                hexs = body
                break
            if hexs is None:
                last = '没有应答'
            elif hexs.startswith('E'):
                last = '对端返回错误 %s' % hexs
            elif not ok:
                last = '校验和不对'
            else:
                try:
                    b = bytes.fromhex(hexs)
                except ValueError:
                    last = '返回的不是十六进制: %r' % hexs[:20]
                else:
                    if len(b) == n:
                        return b
                    last = '长度不对（要 %d 给 %d）' % (n, len(b))
            self.stats['retry'] += 1
        raise RspError('读 0x%08X（%d 字节）失败: %s' % (addr, n, last))

    def read_u16(self, addr):
        return int.from_bytes(self.read(addr, 2), 'little')

    def read_u32(self, addr):
        return int.from_bytes(self.read(addr, 4), 'little')

    def read_s16(self, addr):
        return int.from_bytes(self.read(addr, 2), 'little', signed=True)

    def read_s32(self, addr):
        return int.from_bytes(self.read(addr, 4), 'little', signed=True)

    def read_block(self, addr, n, chunk=512):
        """大块读（显存用）。分批 + 每批严格校验。"""
        out = b''
        while len(out) < n:
            k = min(chunk, n - len(out))
            out += self.read(addr + len(out), k)
        return out

    # ---- 停机 / 继续（要冻结画面取一致的一帧时用）----
    def halt(self, timeout=3.0):
        """请求暂停。对端回 T/S 停机回报才算成功。"""
        self._drain()
        self.s.sendall(b'\x03')
        deadline = time.time() + timeout
        while time.time() < deadline:
            got = self._next_packet(timeout=0.5)
            if got is None:
                continue
            body, ok = got
            self._ack()
            if body[:1] in ('T', 'S', 'W', 'X'):
                return True
        raise RspError('请求暂停失败（没收到停机回报）')

    def cont(self):
        self.s.sendall(b'$c#63')
        try:
            self._ack()
        except OSError:
            pass

    def probe(self, frame_addr=None):
        """自检：确认"链路通" **且"游戏真的在跑"**。

        光读一个寄存器不够 —— CPU 停着的时候读到的值也是"合法"的，
        只是毫无意义（踩过：DISPCNT=0 被当成"寄存器坏了"，
        其实是用 `-g` 启动后没 continue，CPU 还停在启动处 ✗）。

        所以分两步：
          1. DISPCNT 的模式位必须是 0..5（排除链路错位）
          2. 如果给了帧计数地址，看它**会不会变**（排除"CPU 没跑"）
        """
        dc = None
        for _ in range(6):
            dc = self.read_u16(0x04000000)
            if (dc & 7) <= 5:
                break
        if dc is None or (dc & 7) > 5:
            raise RspError('自检失败：DISPCNT 读出来不是合理的模式号（链路错位）')

        if frame_addr:
            a = self.read_u32(frame_addr)
            time.sleep(0.25)
            b = self.read_u32(frame_addr)
            if a == b:
                raise RspError('自检失败：帧计数没在变（0x%08X 一直是 %d）'
                               '—— CPU 可能没 continue' % (frame_addr, a))
        return dc

    def close(self):
        try:
            self.s.close()
        except Exception:                      # noqa: BLE001
            pass


# =====================================================================
#  下面这段是"读音频寄存器"的老功能，保留原样
# =====================================================================
REGS = [
    ('SOUNDCNT_X  总开关(bit7=1)',      0x04000084, 2),
    ('SOUNDCNT_H  DSA/DSB 音量与输出',  0x04000082, 2),
    ('SOUNDBIAS   偏置',                0x04000088, 2),
    ('TM0CNT  语音定时器(bit7=使能)',   0x04000102, 2),
    ('TM0D    语音重载值(11025Hz≈1521)', 0x04000100, 2),
    ('DMA1CNT 语音DMA控制',             0x040000BC, 4),
    ('DMA1SAD 语音DMA源地址',           0x040000B8, 4),
    ('TM1CNT  BGM定时器',               0x04000106, 2),
    ('TM1D    BGM重载值',               0x04000104, 2),
    ('DMA2CNT BGM/音效DMA控制',         0x040000C8, 4),
    ('DMA2SAD BGM/音效DMA源地址',       0x040000C4, 4),
]


def main():
    addrs = {}
    for line in sys.stdin.read().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            addrs[k.strip()] = v.strip()
    r = RSP()
    dc = r.probe()
    print('  已连上 mGBA 的调试接口 (127.0.0.1:2345)')
    print('  自检 DISPCNT=0x%04X（模式 %d）—— 链路正常' % (dc, dc & 7))
    print()
    print('  %-34s %s' % ('寄存器', '读数'))
    print('  ' + '-' * 56)
    vals = {}
    for name, addr, n in REGS:
        try:
            v = int.from_bytes(r.read(addr, n), 'little')
        except RspError as e:
            print('  %-34s 读失败: %s' % (name, e))
            continue
        vals[name] = v
        extra = ''
        if 'SOUNDCNT_X' in name:
            extra = '  ← 总开关 %s' % ('开 ✓' if v & 0x80 else '关 ✗')
        elif 'TM0CNT' in name or 'TM1CNT' in name:
            extra = '  ← 定时器 %s' % ('跑 ✓' if v & 0x80 else '停 ✗')
        elif name.startswith('DMA') and 'CNT' in name:
            extra = '  ← DMA %s' % ('开 ✓' if v & 0x80000000 else '关 ✗')
        print('  %-34s 0x%0*X%s' % (name, n * 2, v, extra))
    print()
    # 关键判断
    ch = vals.get('SOUNDCNT_H  DSA/DSB 音量与输出', 0)
    print('  判定：')
    print('    Direct Sound B 左右输出: %s'
          % ('开 ✓' if (ch & 0x1000) and (ch & 0x2000) else '关 ✗'))
    print('    Direct Sound A 左右输出: %s'
          % ('开 ✓' if (ch & 0x0100) and (ch & 0x0200) else '关 ✗（此刻可能没在放语音）'))
    d2 = vals.get('DMA2CNT BGM/音效DMA控制', 0)
    print('    BGM DMA 正在搬运: %s' % ('是 ✓' if d2 & 0x80000000 else '否 ✗'))
    src = vals.get('DMA2SAD BGM/音效DMA源地址', 0)
    print('    BGM DMA 源地址: 0x%08X（ROM 段 0x08000000 起 = %s）'
          % (src, '指向 ROM ✓' if 0x08000000 <= src < 0x0A000000 else '不对 ✗'))
    if 'snd_clips' in addrs:
        print('    snd_clips 表地址: %s' % addrs['snd_clips'])
    r.close()


if __name__ == '__main__':
    main()
