# -*- coding: utf-8 -*-
"""
modes/common.py —— 各模式共用的小工具

**为什么单独一个文件**：放在 modes/__init__.py 里会造成循环导入 ——
__init__ 要先 import 各个模式类，而模式类又反过来 import __init__ 里的东西，
那时候它还没定义完。放这里就没这个问题（谁都能安全地 import）。

目前只有一个函数：清空布局。看着简单，但**写错的表现很隐蔽**：
属性栏是三个模式共用的，清不干净就会旧控件浮在新控件上面。
"""


def clear_layout(lay):
    """
    递归清空一个布局：控件立刻脱离（隐藏 + setParent(None)）+ 延迟销毁，
    子布局也要递归处理。只 takeAt 不递归的话，嵌套布局里的控件会留下来继续显示。

    **三个模式共用这一份**：P9 就真踩过一次 —— 精灵模式自己抄了一份、
    漏了递归和隐藏，测试立刻报出 84 个残留控件（还都是可见的顶层窗口）。
    """
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        sub = it.layout()
        if sub is not None:
            clear_layout(sub)
            sub.setParent(None)
