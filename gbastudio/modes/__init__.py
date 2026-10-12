# -*- coding: utf-8 -*-
"""
modes —— 模式注册表

**加一个新游戏类型 = 加一个 Mode 子类 + 在 MODES 里登记一行。**
主窗口读这张表自动生成模式切换按钮、菜单和面板布局，不用改主窗口代码。

这和上一版节点编辑器里的"节点类型注册表"是同一个套路 ——
那次证明有效，所以这里继续用。
"""
from modes.common import clear_layout          # noqa: F401  （对外仍然从 modes 导出）
from modes.story import StoryMode
from modes.level import LevelMode
from modes.sprite import SpriteMode

# 顺序就是界面上模式按钮的顺序
MODES = [
    StoryMode,
    LevelMode,
    SpriteMode,
]

# 还没实现的模式先占位，让"多模式"这件事在界面上就看得出来
PLANNED_MODES = [
    ('logic',  '逻辑', '事件表：条件 → 动作'),
]


def create_modes(win):
    return [cls(win) for cls in MODES]


