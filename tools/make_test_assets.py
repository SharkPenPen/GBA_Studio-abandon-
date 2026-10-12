#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_test_assets.py —— 造几个"一眼能认出来"的测试素材（验证 P5）

为什么需要：现有素材只有两张背景两个角色。要证明"任意数量资源都能用"，
就得有第三、第四个资源。真画是不可能的，所以用程序生成辨识度高的图形：

    test_forest.png   绿色渐变 + 树形色块（背景）
    test_night.png    深蓝渐变 + 星点（背景）
    test_golem.png    带 alpha 的石人形（立绘，验证居中位置）

它们**只用于测试**，风格和真素材完全不同 —— 一旦出现在画面上，
一眼就能确认"这个资源真的被编译进去了"。
"""
import argparse
import math
import os
import random

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def forest(w=1920, h=1080):
    im = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)],
               fill=(int(30 + 60 * t), int(90 + 90 * t), int(40 + 40 * t)))
    rnd = random.Random(7)
    for i in range(26):                      # 一排树
        x = int(i * w / 26) + rnd.randint(-20, 20)
        th = rnd.randint(int(h * 0.35), int(h * 0.75))
        tw = rnd.randint(70, 150)
        d.polygon([(x, h - th), (x - tw, h), (x + tw, h)],
                  fill=(20 + rnd.randint(0, 30), 70 + rnd.randint(0, 40), 30))
    d.rectangle([0, h - 60, w, h], fill=(60, 70, 40))     # 地面
    return im


def night(w=1920, h=1080):
    im = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(8 + 20 * t), int(10 + 26 * t), int(40 + 60 * t)))
    rnd = random.Random(11)
    for _ in range(240):                     # 星
        x, y = rnd.randint(0, w), rnd.randint(0, int(h * 0.7))
        r = rnd.choice([1, 1, 1, 2])
        d.ellipse([x, y, x + r, y + r], fill=(230, 230, 255))
    d.ellipse([int(w * 0.72), 90, int(w * 0.72) + 170, 260], fill=(240, 240, 210))  # 月亮
    d.rectangle([0, int(h * 0.82), w, h], fill=(18, 20, 34))                       # 地平线
    return im


def golem(w=520, h=760):
    """带 alpha 的石人：验证"第三个角色"和居中位置"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body = (150, 140, 130, 255)
    dark = (95, 88, 82, 255)
    d.rounded_rectangle([w * 0.28, h * 0.10, w * 0.72, h * 0.42], 26, fill=body,
                        outline=dark, width=6)                       # 头
    d.rectangle([w * 0.16, h * 0.44, w * 0.84, h * 0.78], fill=body,
                outline=dark, width=6)                               # 身
    d.rectangle([w * 0.02, h * 0.46, w * 0.16, h * 0.72], fill=dark)  # 左臂
    d.rectangle([w * 0.84, h * 0.46, w * 0.98, h * 0.72], fill=dark)  # 右臂
    d.rectangle([w * 0.28, h * 0.78, w * 0.46, h * 0.98], fill=dark)  # 腿
    d.rectangle([w * 0.54, h * 0.78, w * 0.72, h * 0.98], fill=dark)
    for i, cx in enumerate((0.38, 0.62)):                             # 发光的眼
        x = w * cx
        d.ellipse([x - 26, h * 0.24, x + 26, h * 0.24 + 52], fill=(255, 120, 90, 255))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, 'assets_src', 'test'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name, im in (('test_forest.png', forest()), ('test_night.png', night()),
                     ('test_golem.png', golem())):
        p = os.path.join(a.out, name)
        im.save(p)
        print('  %-20s %-11s %s' % (name, '%dx%d' % im.size,
                                    '%.0f KB' % (os.path.getsize(p) / 1024)))


if __name__ == '__main__':
    main()
