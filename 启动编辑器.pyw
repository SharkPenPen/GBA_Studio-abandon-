#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动编辑器.pyw —— 双击这个文件启动 GBAStudio

为什么用 .pyw 而不是 .cmd：
    .cmd 里写中文注释/路径容易踩编码坑，而且 cmd 启动的 GUI 子进程会继承父进程
    的管道句柄，调用方（包括我自己调试时）容易"收不了尾"。
    .pyw 由 pythonw.exe 直接运行、不开控制台、也没有编码问题。
    双击即用；想看报错就用命令行跑：
        python gbastudio\\main.py
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, 'gbastudio', 'main.py')

os.chdir(HERE)
sys.path.insert(0, os.path.join(HERE, 'gbastudio'))

try:
    runpy.run_path(ENTRY, run_name='__main__')
except Exception:
    # 没有控制台看不到报错，所以把错误写到文件里，方便排查
    import traceback
    with open(os.path.join(HERE, '.tmp', 'gbastudio-crash.log'), 'w', encoding='utf-8') as f:
        f.write('启动失败：\n')
        f.write(traceback.format_exc())
    raise
