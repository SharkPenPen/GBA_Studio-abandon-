#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_test_sprites.py —— 生成测试用的精灵帧（P9）

**为什么程序画而不是找素材**：
    测试用的图必须是"一眼能认出来的"——哪一帧、朝哪边、动没动，
    截图里立刻能判断。真人素材做不到这点（每帧看着都差不多），
    出了问题也说不清是"没切帧"还是"切对了但没播"。

画 5 张 16x24 的小人：
    player_idle   站着（手臂垂下）
    player_walk0  走 1（左腿前）
    player_walk1  走 2（两腿并拢）
    player_walk2  走 3（右腿前）   ← walk1 复用，走路序列是 0,1,2,1
    player_jump   跳（两腿收起）

输出到 assets_src/test/，再由编辑器导入工程、分配置成「精灵」素材。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

from PIL import Image, ImageDraw          # noqa: E402

W, H = 16, 24
OUT = os.path.join(ROOT, 'assets_src', 'test')

SKIN = (240, 200, 150, 255)
HAIR = (70, 50, 40, 255)
SHIRT = (70, 120, 200, 255)
PANTS = (50, 50, 70, 255)
SHOE = (35, 35, 35, 255)
EYE = (30, 30, 30, 255)
KEY = (0, 0, 0, 0)              # 透明（引擎按 key 色做透明 blit）


def body(d, dx_arm=0, leg=0, dy=0, legs_up=False):
    """
    画一个 16x24 的小人。

    leg：迈步幅度。两条腿**错开画**（前腿往前、后腿往后），
         中间留 1 像素空隙 —— 不然两条腿并在一起就是一块色块，
         截图里根本看不出哪一帧是哪一帧（第一版就是这样，改了）。
    """
    y = 2 + dy
    # 头（6x6）+ 头发 + 眼睛
    d.rectangle([5, y, 10, y + 5], fill=SKIN, outline=HAIR)
    d.rectangle([5, y, 10, y + 1], fill=HAIR)
    d.point((7, y + 3), fill=EYE)
    d.point((9, y + 3), fill=EYE)
    # 身体（6x8）
    d.rectangle([5, y + 6, 10, y + 13], fill=SHIRT, outline=PANTS)
    # 手臂：前后摆（和腿相反，这是走路的对侧摆动）
    d.rectangle([3 + dx_arm, y + 6, 4 + dx_arm, y + 12], fill=SHIRT)
    d.rectangle([11 - dx_arm, y + 6, 12 - dx_arm, y + 12], fill=SHIRT)
    # 腿
    if legs_up:                                   # 跳：两腿收起
        d.rectangle([4, y + 14, 6, y + 18], fill=PANTS)
        d.rectangle([9, y + 14, 11, y + 18], fill=PANTS)
        d.rectangle([3, y + 18, 6, y + 19], fill=SHOE)
        d.rectangle([9, y + 18, 12, y + 19], fill=SHOE)
    else:
        # 前腿往后腿的**外侧**错开，中间留缝
        d.rectangle([5 + leg, y + 14, 6 + leg, y + 20], fill=PANTS)
        d.rectangle([9 - leg, y + 14, 10 - leg, y + 20], fill=PANTS)
        d.rectangle([4 + leg, y + 21, 7 + leg, y + 22], fill=SHOE)
        d.rectangle([8 - leg, y + 21, 11 - leg, y + 22], fill=SHOE)


def make(name, **kw):
    im = Image.new('RGBA', (W, H), KEY)
    d = ImageDraw.Draw(im)
    body(d, **kw)
    path = os.path.join(OUT, name + '.png')
    im.save(path)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    # 走路用 0,1,2,1 循环（4 帧一个来回），迈步幅度 ±2 像素，肉眼看得出来
    made = [
        make('player_idle'),
        make('player_walk0', leg=2, dx_arm=1),
        make('player_walk1', leg=0, dx_arm=0),
        make('player_walk2', leg=-2, dx_arm=-1),
        make('player_jump', legs_up=True, dy=-1),
    ]
    print('  [sprites] 生成 %d 张 %dx%d 精灵帧：' % (len(made), W, H))
    for p in made:
        print('    %s' % os.path.relpath(p, ROOT))
    print('  [sprites] 下一步：在编辑器里「导入素材」选这些 png，')
    print('            右键归类为「精灵」，再到「精灵」模式里连成动画。')


if __name__ == '__main__':
    main()
