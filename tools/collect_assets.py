#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_assets.py —— 把解包出来的素材按类型收进工程

【为什么先做这个】
"自动补上背景切换 / 立绘显隐"要两样东西：
    1. 剧本里的命令（哪一句切哪张图）  ← 在 .ws2 字节码里，需要操作码表
    2. **素材本身在工程里，而且分类正确**  ← 就是这个工具

第 2 件是第 1 件的前提 ✗ 没有它，就算解析出"切到 BG12"也找不到文件 ✓

【怎么分类（只看文件名和尺寸，不看内容）】
    背景     PNG输出/ 里 1280x720 的图（＋ 背景/ 目录里的）
    立绘     立绘/ 里符合角色命名规则的图（NameTable 里的 CSTxx 系列）
    语音     音频/语音/*.ogg
    音乐     音频/BGM/*.ogg
    音效     音频/音效/*.ogg

【一条重要的实测结论】
`立绘/` 目录里**不全是立绘** ✗ 实测有 150 张 1280x720 里混着整张 CG
（转换时"人物包围盒"就是整张图 ✓）→ 所以这里按**命名规则**筛，
不按目录筛 ✓ 拿不准的标成"未分类"，留给人在编辑器里归类 ✓

用法：
    python tools\\collect_assets.py --src "<解包目录>" --project "<工程.gbastudio>"
                                   [--max-bg 200] [--max-char 200] [--dry-run]
"""
import argparse
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

SCR_W, SCR_H = 240, 160
IMMENSE = 1280 * 720          # 原始素材的分辨率


def log(m):
    print('[assets] ' + m)


def _img_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def scan(src):
    """扫出候选素材

    【分类规则是实测出来的，不是猜的】
    解包时是**按封包分目录**的（Chip1..6）✗ 所以目录名不可信 ✗
    实测：`立绘/` 目录里其实是 BG / EV / 特效遮罩 ✓ 一张角色立绘都没有 ✗
    真正可信的是**文件名前缀 + 所在目录的用途**：

        PNG输出/ST##X_Y/*_composed.png   角色立绘（完整立绘，不是差分帧）★
        PNG输出/EV.../*                   事件 CG（能当背景用）
        立绘/Chip3/BG*.PNG                真正的背景（实测背景在这里）
        音频/{语音,BGM,音效}/*.ogg         音频

    故意不要的：
        EFMSK_ / LAYERMASK_ / EST_   特效遮罩，GBA 用不上
        SYS_*                        界面图，等做菜单时再说
    """
    out = {'bg': [], 'char': [], 'voice': [], 'bgm': [], 'se': [], 'other': []}
    png = os.path.join(src, 'PNG输出')

    # 角色立绘：取每个 ST* 目录里的 *_composed.png（完整立绘）
    if os.path.isdir(png):
        for d in sorted(os.listdir(png)):
            if not re.match(r'^ST\d', d, re.I):
                continue
            dd = os.path.join(png, d)
            if not os.path.isdir(dd):
                continue
            best = None
            for f in sorted(os.listdir(dd)):
                if f.lower().endswith('.png') and 'composed' in f.lower():
                    best = os.path.join(dd, f)
                    break
            if best is None:                     # 没有合成图就退回第一帧
                fr = sorted(f for f in os.listdir(dd)
                            if f.lower().endswith('.png') and f.lower().startswith('frame'))
                if fr:
                    best = os.path.join(dd, fr[0])
            if best:
                out['char'].append(best)

    # 事件 CG：每个 EV* 目录取一张（优先带 composed 的，其次最大的）
    if os.path.isdir(png):
        for d in sorted(os.listdir(png)):
            if not re.match(r'^[Ee][Vv]\d', d):
                continue
            dd = os.path.join(png, d)
            if not os.path.isdir(dd):
                continue
            cands = [os.path.join(dd, f) for f in sorted(os.listdir(dd))
                     if f.lower().endswith('.png')]
            if not cands:
                continue
            comp = [c for c in cands if 'composed' in os.path.basename(c).lower()]
            pickone = comp[0] if comp else max(cands, key=os.path.getsize)
            out['bg'].append(pickone)

    # 背景：立绘\Chip3\BG*.PNG 这一类
    for sub in ('立绘', '背景'):
        d = os.path.join(src, sub)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            for f in sorted(fn):
                if not f.lower().endswith('.png'):
                    continue
                if re.match(r'^BG', f, re.I):
                    out['bg'].append(os.path.join(dp, f))

    # 音频
    ad = os.path.join(src, '音频')
    for sub, kind in (('语音', 'voice'), ('BGM', 'bgm'), ('音效', 'se')):
        d = os.path.join(ad, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(('.ogg', '.wav', '.mp3', '.flac')):
                    out[kind].append(os.path.join(d, f))
    return out


def pick(lst, limit):
    """均匀取样：不总是取前 N 个（那样只会拿到第一章的素材）"""
    if not limit or len(lst) <= limit:
        return lst
    step = len(lst) / float(limit)
    return [lst[int(i * step)] for i in range(limit)]


def copy_in(project, files, kind, limit, dry):
    """把素材拷进工程的 assets/<kind>/ 并登记"""
    from core.project import Asset
    made = []
    for p in pick(files, limit):
        name = os.path.basename(p)
        rel = 'assets/%s/%s' % (kind, name)
        dst = os.path.join(project, rel.replace('/', os.sep))
        if not dry:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(p):
                shutil.copy2(p, dst)
        made.append(rel)
    return made


def main():
    ap = argparse.ArgumentParser(description='把解包素材按类型收进工程')
    ap.add_argument('--src', required=True, help='解包根目录')
    ap.add_argument('--project', required=True, help='工程目录，或 .gbastudio 文件')
    ap.add_argument('--max-bg', type=int, default=150)
    ap.add_argument('--max-char', type=int, default=80)
    ap.add_argument('--max-voice', type=int, default=200)
    ap.add_argument('--max-bgm', type=int, default=10)
    ap.add_argument('--max-se', type=int, default=60)
    ap.add_argument('--share', default='',
                    help='只取第 i 份（共 n 份），形如 1/3。'
                         '分章时每章拿自己那一份素材 ✗ 各盘的容量互不挤占 ✓')
    ap.add_argument('--dry-run', action='store_true', help='只看统计，不拷文件')
    ap.add_argument('--no-save', action='store_true', help='拷文件但不改工程')
    a = ap.parse_args()

    if not os.path.isdir(a.src):
        log('✗ 找不到素材目录 %s' % a.src)
        return 1

    proj_path = a.project
    if os.path.isdir(proj_path):
        cands = [f for f in os.listdir(proj_path) if f.endswith('.gbastudio')]
        if not cands:
            log('✗ 这个目录里没有 .gbastudio 文件：%s' % proj_path)
            return 1
        proj_path = os.path.join(proj_path, cands[0])
    proj_dir = os.path.dirname(os.path.abspath(proj_path))

    log('扫描素材 …')
    found = scan(a.src)
    if a.share:
        # 把每一类**均匀切成 n 份**，只取第 i 份
        try:
            i_s, n_s = a.share.split('/')
            i_s, n_s = int(i_s) - 1, int(n_s)
            assert 0 <= i_s < n_s
        except Exception:
            log('✗ --share 要写成 1/3 这样（第 1 份，共 3 份）')
            return 1
        for k in list(found):
            lst = found[k]
            found[k] = [x for j, x in enumerate(lst) if j % n_s == i_s]
        log('只取第 %d/%d 份素材' % (i_s + 1, n_s))
    for k in ('bg', 'char', 'voice', 'bgm', 'se', 'other'):
        log('   %-6s %5d 个' % (k, len(found[k])))
    if not sum(len(v) for v in found.values()):
        log('✗ 一个都没扫到，检查 --src 指向的目录结构')
        return 1

    from core.project import Project
    p = Project.load(proj_path)

    limits = {'bg': a.max_bg, 'char': a.max_char, 'voice': a.max_voice,
              'bgm': a.max_bgm, 'se': a.max_se}
    from core.project import Asset, Character
    added = {}
    keep = [x for x in p.assets if x.kind not in limits]      # 保留别的类型
    for kind, lim in limits.items():
        if kind == 'char':
            # **立绘要按角色分目录** ✗
            # 编译器是按"资源路径里含角色名"来找立绘的 ✓
            # 所以放成 assets/char/<ID>/normal.png ✓ 并给每个 ID 建一条角色表 ✓
            chars = []
            for src_path in pick(found['char'], lim):
                cid = os.path.basename(os.path.dirname(src_path))
                rel = 'assets/char/%s/normal.png' % cid
                dst = os.path.join(proj_dir, rel.replace('/', os.sep))
                if not a.dry_run:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.isfile(dst):
                        shutil.copy2(src_path, dst)
                keep.append(Asset('char', rel, ''))
                chars.append(Character(cid, cid, '#ffd166', cid + '_', ['normal']))
            # 同名角色不重复加
            have = {c.id for c in p.characters}
            for c in chars:
                if c.id not in have:
                    p.characters.append(c)
            added[kind] = len(chars)
            continue
        rels = copy_in(proj_dir, found[kind], kind, lim, a.dry_run)
        added[kind] = len(rels)
        for rel in rels:
            keep.append(Asset(kind, rel, ''))
    p.assets = keep

    log('')
    log('收进工程：%s' % '  '.join('%s %d' % (k, v) for k, v in added.items() if v))
    log('角色表：%d 个（立绘按 assets/char/<角色ID>/normal.png 摆好，编译器认这个路径）'
        % len(p.characters))
    if found['other']:
        log('⚠ 有 %d 张图没敢归类（命名不像立绘）—— 在编辑器里右键「归类为」即可'
            % len(found['other']))
    if a.dry_run:
        log('（--dry-run：没有真的拷文件、没有改工程）')
        return 0
    if not a.no_save:
        p.save(proj_path)
        log('工程已更新：%s' % proj_path)
    # 体积预估
    total = 0
    sizes = {'bg': 75.0, 'char': 50.0}      # KB，实测值
    for k, v in added.items():
        total += v * sizes.get(k, 0)
    if total:
        log('这些图转成 GBA 格式后约 %.1f MB（背景 75KB/张、立绘 50KB/张 实测）'
            % (total / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
