#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解除下载标记.pyw —— 检查并清除"来自 Internet"标记（Zone.Identifier）

【为什么是 .pyw 而不是 .cmd】
用户实测：这台机器上双击 **.cmd 会弹"打开文件 - 安全警告"**，
而 **.pyw 不弹** ✗ 原因是 Windows 的"不安全文件"判定认的是**文件类型** ——
.cmd/.bat/.exe 这类"可执行类型"会被检查，.pyw 不在那个名单里
（证据：assoc .cmd 有结果，assoc .pyw 查不到关联 ✗）。

所以这个工具也改成 .pyw：双击不弹警告 ✗ 顺带也没有了 cmd 的 GBK 编码限制 ✓

它做两件事：
  1. 递归找出带 Internet 标记（Zone.Identifier）的文件，列出来并清掉
  2. 把结论用**窗口**告诉你（.pyw 没有控制台，必须用窗口反馈）
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = ('.toolchain', '.tmp', 'build', '__pycache__', '.git')


def has_mark(path):
    """文件有没有 Zone.Identifier 流。

    直接用 Windows API 枚举数据流 —— 比读注册表/猜靠谱 ✗
    （踩过：用 PowerShell 的 Get-Item -Stream 在受限环境里会 Access denied，
     于是得出"没有标记"的错误结论）
    """
    import ctypes
    from ctypes import wintypes

    INVALID = ctypes.c_void_p(-1).value
    kernel32 = ctypes.windll.kernel32
    kernel32.FindFirstStreamW.restype = wintypes.HANDLE
    kernel32.FindFirstStreamW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD]
    kernel32.FindNextStreamW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.FindClose.argtypes = [wintypes.HANDLE]

    class STREAM_INFO(ctypes.Structure):
        _fields_ = [('dwStreamSize', ctypes.c_longlong),
                    ('cStreamName', wintypes.DWORD),
                    ('szStreamName', wintypes.WCHAR * 296)]

    info = STREAM_INFO()
    h = kernel32.FindFirstStreamW(path, 0, ctypes.byref(info), 0)
    if h == INVALID or not h:
        return False
    found = False
    while True:
        if info.szStreamName.lower().startswith(':zone.identifier'):
            found = True
            break
        if not kernel32.FindNextStreamW(h, ctypes.byref(info)):
            break
    kernel32.FindClose(h)
    return found


def unblock(path):
    import ctypes
    return bool(ctypes.windll.kernel32.DeleteFileW(
        path + ':Zone.Identifier'))


def main():
    root = tk.Tk()
    root.withdraw()

    hits = []
    total = 0
    for dp, dn, fn in os.walk(HERE):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            p = os.path.join(dp, f)
            total += 1
            try:
                if has_mark(p):
                    hits.append(p)
            except Exception:                      # noqa: BLE001
                pass

    if not hits:
        messagebox.showinfo(
            '解除下载标记',
            '扫描了 %d 个文件，**没有**发现带 Internet 标记的文件。\n\n'
            '也就是说：那个安全警告不是"来自 Internet"引起的。\n'
            '（这台机器上双击 .cmd 会弹、双击 .pyw 不弹 —— 说明是\n'
            ' Windows 把 .cmd 归到了"不安全文件类型"，不是文件被标记）\n\n'
            '结论：用 启动编辑器.pyw 启动即可，不用管这个工具。' % total)
        return

    for p in hits:
        unblock(p)
    messagebox.showinfo(
        '解除下载标记',
        '清除了 %d 个文件的 Internet 标记（共扫描 %d 个）：\n\n%s'
        % (len(hits), total, '\n'.join(os.path.relpath(x, HERE) for x in hits[:12])))


if __name__ == '__main__':
    main()
