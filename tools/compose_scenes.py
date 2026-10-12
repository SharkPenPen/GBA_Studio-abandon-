#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compose_scenes.py —— 把"底图 + 立绘 + 蒙版"预先合成成**一张** 240x160 图

【为什么这么做】
原作是**多层叠加**的：底图（BG/EV）+ 立绘（st）+ 特效蒙版（EFMSK）
GBA 只有**一层**背景 ✗ 而且位图模式（模式 3/4/5）连图层都没有 ✓
所以唯一的办法是：**在电脑上先把它们合好** ✗ 交给 GBA 的就是一张成品图 ✓

这正好是 GBA 视觉小说的通行做法 ✗ "预渲染背景" ✓

【合多少张】
实测：45 个台词场景一共只有 **180 种不同的图层组合** ✓
     s0 章 114 种、s1 章 44 种、s2 章 51 种
每张 240x160 16bpp = 75 KB → 全部加起来 **13.2 MB** ✓
（6 盘卡带总容量 192 MB → 只占 7% ✓ 完全放得下 ✓）

【坐标怎么换算】
ws2 里的位置是**原始分辨率**空间（1280x720）✓
GBA 是 240x160 → 缩放系数 240/1280 = 0.1875 ✓
蒙版按"正片叠底"（multiply）叠加 ✗ 这是对 Darken/Mask 类特效最接近的近似 ✓

用法：
    python tools\\compose_scenes.py --recipes .tmp\\scene_recipes.json `
                                   --src "<解包目录>" `
                                   --out "<工程>\\assets\\bg"
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

SCR_W, SCR_H = 240, 160
SRC_W, SRC_H = 1280, 720
SCALE = SCR_W / float(SRC_W)


def log(m):
    print('[compose] ' + m)


def build_index(src):
    """把解包目录里的图片建成 {文件名小写: 路径} 索引"""
    idx = {}
    for dp, dn, fn in os.walk(src):
        if any(x in dp for x in ('音频', '剧本', '视频', '字体')):
            continue
        for f in fn:
            if f.lower().endswith(('.png', '.jpg', '.bmp')):
                idx.setdefault(f.lower(), os.path.join(dp, f))
                # 也按"去掉扩展名"建一份，方便大小写/扩展名不一致时能对上
                idx.setdefault(os.path.splitext(f.lower())[0], os.path.join(dp, f))
    return idx


def find(idx, name):
    if not name:
        return None
    n = str(name).lower()
    return idx.get(n) or idx.get(os.path.splitext(n)[0])


# **三个"色块底"必须按名字来，不能读文件内容** ✗
#
# 踩过（用户报的"开局红屏"就是这个）：
#   立绘/Chip2/bgBLACK.png   名字叫 BLACK，内容却是【纯红】
#   立绘/Chip2/bgRED.png     名字叫 RED，  内容却是【纯白】
#   立绘/Chip2/bgWHITE.png   名字叫 WHITE，内容却是【纯黑】
# —— 文件名和内容**整个对调了** ✓
#
# 原因：这三个根本不是背景图 ✗ 是**着色器用的色块遮罩** ✓
# （引擎里 `BGBLACK` 这个图层的意思是"整屏黑" ✓ 用它做淡入淡出 ✓）
# 拿它的**内容**当背景 → 开场就红屏 ✓
#
# 所以：看到这三个名字，**自己生成纯色** ✓ 不看文件内容 ✓
SOLID_BY_NAME = {
    'bgblack': (0, 0, 0),
    'bgwhite': (255, 255, 255),
    'bgred': (255, 0, 0),
}


def compose(base_path, spr_path, mask_path, pos, out_path, base_name=''):
    """合成一张 → 返回是否成功"""
    from PIL import Image
    key = os.path.splitext(os.path.basename(str(base_name or base_path)))[0].lower()
    if key in SOLID_BY_NAME:
        # 纯色底：直接铺满，不读源文件
        out = Image.new('RGB', (SCR_W, SCR_H), SOLID_BY_NAME[key])
        if mask_path:
            try:
                mk = Image.open(mask_path).convert('L').resize((SCR_W, SCR_H),
                                                               Image.LANCZOS)
                dark = Image.new('RGB', (SCR_W, SCR_H), (0, 0, 0))
                dark.paste(out, (0, 0), mk)
                out = dark
            except Exception:
                pass
        out.save(out_path)
        return True

    # 底图：按 GBA 分辨率等比缩放 + 居中裁切（和资源管线同一套做法）
    im = Image.open(base_path).convert('RGB')
    r = max(SCR_W / float(im.width), SCR_H / float(im.height))
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))),
                   Image.LANCZOS)
    left = (im.width - SCR_W) // 2
    top = (im.height - SCR_H) // 2
    out = im.crop((left, top, left + SCR_W, top + SCR_H))

    # 立绘：按原始坐标缩放后贴上去（带 alpha）
    if spr_path:
        try:
            sp = Image.open(spr_path).convert('RGBA')
            sp = sp.resize((max(1, int(sp.width * SCALE)), max(1, int(sp.height * SCALE))),
                           Image.LANCZOS)
            x = int(round(-pos[0] * SCALE)) if pos else 0
            y = int(round(-pos[1] * SCALE)) if pos else 0
            out = out.convert('RGBA')
            out.alpha_composite(sp, (x, y))
            out = out.convert('RGB')
        except Exception:
            pass

    # 蒙版：正片叠底（对 Darken / Mask 类特效最接近的近似）
    if mask_path:
        try:
            mk = Image.open(mask_path).convert('L').resize((SCR_W, SCR_H), Image.LANCZOS)
            dark = Image.new('RGB', (SCR_W, SCR_H), (0, 0, 0))
            dark.paste(out, (0, 0), mk)          # 用蒙版当 alpha，把画面压暗
            out = dark
        except Exception:
            pass
    out.save(out_path)
    return True


def key_of(recipe):
    """配方 → 稳定的短文件名"""
    s = json.dumps(recipe, ensure_ascii=False, sort_keys=True)
    return 'comp_' + hashlib.md5(s.encode('utf-8')).hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser(description='把多层合成为一张 240x160 图')
    ap.add_argument('--recipes', required=True, help='ws2 提取出的配方表')
    ap.add_argument('--src', required=True, help='解包根目录（找图用）')
    ap.add_argument('--out', required=True, help='输出目录（工程的 assets/bg）')
    ap.add_argument('--report', default='', help='配方 → 文件名 的映射表（JSON）')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    recipes = json.load(open(a.recipes, encoding='utf-8'))
    idx = build_index(a.src)
    log('图片索引 %d 条' % len(idx))

    # 收集所有不同的配方
    uniq = {}
    for sc, per in recipes.items():
        for ix, key in per.items():
            uniq.setdefault(key, []).append((sc, ix))
    log('不同配方 %d 种' % len(uniq))
    if a.limit:
        uniq = dict(list(uniq.items())[:a.limit])

    os.makedirs(a.out, exist_ok=True)
    mapping = {}
    ok = miss_base = miss_mask = 0
    for key, where in uniq.items():
        base, pos, spr, mask = json.loads(key)
        name = key_of(key)
        rel = 'assets/bg/%s.png' % name
        dst = os.path.join(a.out, name + '.png')
        bp = find(idx, base)
        if not bp:
            miss_base += 1
            mapping[key] = ''
            continue
        sp = find(idx, spr[0]) if spr else None
        mp = find(idx, mask) if mask else None
        if mask and not mp:
            miss_mask += 1
        try:
            if not os.path.isfile(dst):
                compose(bp, sp, mp, pos, dst, base_name=base)
            mapping[key] = rel
            ok += 1
        except Exception as e:                          # noqa: BLE001
            log('  ✗ %s：%s' % (base, e))
            mapping[key] = ''

    log('合成成功 %d 张；底图缺失 %d；蒙版缺失 %d' % (ok, miss_base, miss_mask))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=1)
        log('配方映射已写出 %s' % a.report)
        # **再来一份转换器直接能用的**：(场景, 行号) -> 合成图路径
        # 转换器是按"第几句用哪张图"取素材的，这个格式正好
        per_line = {}
        for key, where in uniq.items():
            rel = mapping.get(key) or ''
            if not rel:
                continue
            for sc, ix in where:
                per_line.setdefault(sc, {})[str(ix)] = rel
        with open(a.report.replace('.json', '_lines.json'), 'w', encoding='utf-8') as f:
            json.dump(per_line, f, ensure_ascii=False, indent=1)
        log('每句用图表已写出 %s' % a.report.replace('.json', '_lines.json'))
    import glob
    n = len(glob.glob(os.path.join(a.out, 'comp_*.png')))
    tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(a.out, 'comp_*.png')))
    log('目录里共 %d 张合成图，%.1f MB（磁盘 PNG）；转成 GBA 格式约 %.1f MB'
        % (n, tot / 1048576.0, n * 75 / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
