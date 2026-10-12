#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check-preview.py —— 预览与实机的一致性回归测试

**这是 P3 的验收工具**：改动引擎布局（galgame.c）、字体（make_cjk_font.py）、
素材转换（make_assets.py）或预览渲染（preview.py）之后都应该跑一遍。

做法：
  1. 用 mGBA 跑 ROM 截图（截图由 scripts/dev/mgba-drive.ps1 产生）
  2. 在窗口截图里**搜出正好 240x160 的整数裁剪**（不能缩放！一缩放就差 50%）
  3. 用编辑器预览渲染同一时刻，逐像素比

为什么要"搜裁剪位置"：mGBA 窗口有标题栏、菜单栏和边框，
早先我用估算公式裁剪，偏了 1 个像素 —— 结果差异率 57%，
看起来像"渲染完全不对"，其实是裁剪偏了。整数搜索之后差异是 1 个像素。

用法：
    python tools/check-preview.py                     # 用默认样品和已有截图
    python tools/check-preview.py --rom-shots 目录
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

from PIL import Image, ImageChops                      # noqa: E402
from core.project import Project                       # noqa: E402
from core.preview import PreviewRenderer, SCR_W, SCR_H  # noqa: E402

# 样品里挑三句台词来比（时刻 + 台词内容）
CASES = [
    ('s7.png', 12.5, '于是她们沿着海岸，走向那片黄色的沙。'),
    ('s9.png', 18.5, '序章 · 完'),
    ('s6.png', 9.0, '叫你的东西，可不止那一座塔。'),
]
TYPE_SPEED = 2                       # 每字帧数（galgame.c）
FPS = 60


def find_crop(shot, target):
    """在窗口截图里搜出最贴合的 240x160 整数裁剪（**绝不缩放**）"""
    im = Image.open(shot).convert('RGB')
    W, H = im.size
    if W < SCR_W or H < SCR_H:
        raise SystemExit('%s 太小了（%dx%d）' % (shot, W, H))
    best = None
    for y0 in range(0, H - SCR_H + 1):
        for x0 in range(0, W - SCR_W + 1):
            c = im.crop((x0, y0, x0 + SCR_W, y0 + SCR_H))
            n = sum(ImageChops.difference(c, target).convert('L').histogram()[25:])
            if best is None or n < best[0]:
                best = (n, x0, y0, c)
                if n == 0:
                    return best
    return best


def diff_pixels(img, target):
    """两张 240x160 图差多少个像素（亮度差 > 24 才算）"""
    d = ImageChops.difference(img, target).convert('L')
    return sum(d.histogram()[25:])


def drive_series(rom, presses, wait_each, outdir, key='A'):
    """用 mgba-drive 按键驱动 ROM，每一步抓一帧（抓帧走显存渲染）。

    **为什么要按键，而不是"跑 N 秒再抓"**：
    剧情推进是靠玩家按 A 的，秒数只是"按了之后过了多久"。
    之前 autoplay 版本会自动推进，但它进了关卡就卡住（不按 START 退出）✗
    于是抓到的整串帧都是关卡画面，和编辑器预览里的对话完全对不上
    （差异率 40%~70%，看起来像"渲染全错"，其实是**根本没抓到那一句**）。

    改成按键驱动之后，"第几句台词"由**按了几次 A** 决定，
    不再依赖秒数 —— 语义对齐是确定的 ✓

    抓帧本身用 tools/grab_screen.py（从显存渲染，不截窗口）——
    老流程用窗口截图，失败时**不报错**，交出桌面或 160x28 的碎片当证据 ✗
    """
    import glob
    import subprocess

    driver = os.path.join(ROOT, 'scripts', 'dev', 'mgba-drive.ps1')
    if not os.path.isfile(driver):
        raise SystemExit('找不到 %s' % driver)

    os.makedirs(outdir, exist_ok=True)
    for f in glob.glob(os.path.join(outdir, 'v*.png')):
        os.remove(f)

    steps = ['wait:2', 'key:' + key, 'wait:3']
    for i in range(presses):
        steps.append('shot:v%02d' % i)
        steps.append('key:' + key)
        steps.append('wait:%g' % wait_each)
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', driver, '-Rom', os.path.abspath(rom),
                    '-Steps', ';'.join(steps), '-OutDir', os.path.abspath(outdir)],
                   capture_output=True)

    files = sorted(glob.glob(os.path.join(outdir, 'v*.png')))
    print('  按键驱动抓了 %d 帧（按了 %d 次 %s）' % (len(files), presses, key))
    return [(i * wait_each, f) for i, f in enumerate(files)]


def line_times(project):
    """列出**整个工程**里每一句台词，以及"它完全显示完、光标亮着"的那个时刻。

    按行号对齐的基础：不再猜秒数，直接问工程模型
    "第 i 句台词是什么、在哪个场景、什么时候完整可见"。

    **必须跨场景** ✗：实机是一幕接一幕往下演的，
    只列 scenes[0] 的话，第二幕之后的台词在预览里根本不存在
    （踩过：样品第一幕 7 句、剧本 11 句，后面 4 句永远匹配不上，
     表现成"差异率 12%"，看起来像渲染错，其实是**预览里没这一幕**）。
    """
    out = []
    for scene in project.scenes:
        for c in sorted(scene.clips, key=lambda x: x.start):
            tk = scene.track(c.track)
            if not tk or tk.kind != 'text':
                continue
            txt = c.props.get('text') or ''
            typed = (len(txt) * TYPE_SPEED + 2) / float(FPS)
            tt = c.start + typed
            if tt >= c.start + c.dur:
                tt = c.start + c.dur - 0.02
            out.append((len(out), scene, tt, txt, c.props.get('speaker') or ''))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default=os.path.join(
        ROOT, '.tmp', 'sample', '魔女与少女', '魔女与少女.gbastudio'))
    ap.add_argument('--rom-shots', default=os.path.join(ROOT, '.tmp', 'shots'))
    ap.add_argument('--save-diff', default=os.path.join(
        ROOT, 'docs', 'screenshots', 'screenshot-preview-diff.png'))
    ap.add_argument('--grab', action='store_true',
                    help='不用预先截好的图，直接让 ROM 跑起来从显存抓帧（推荐）')
    ap.add_argument('--grab-rom', default='gba_ai.gba',
                    help='抓帧用的 ROM（默认 gba_ai.gba，用按键驱动的普通版）')
    ap.add_argument('--grab-presses', type=int, default=10,
                    help='按几次 A（每按一次推进一句台词）')
    ap.add_argument('--grab-wait', type=float, default=3.0,
                    help='每次按键后等几秒（等打字机把这句话打完）')
    ap.add_argument('--scan-seconds', type=float, default=25.0,
                    help='扫描时间轴的上限')
    ap.add_argument('--scan-step', type=float, default=0.1,
                    help='扫描步长（秒）')
    a = ap.parse_args()

    if not os.path.isfile(a.project):
        raise SystemExit('找不到项目：%s\n先跑 python tools/make_sample.py' % a.project)
    proj_dir = os.path.dirname(a.project)
    p = Project.load(a.project)
    r = PreviewRenderer(p, proj_dir)
    scene = p.scenes[0]

    print('比较「编辑器预览」与「实机画面」…')
    print('%-10s %-12s %-10s %s' % ('用例', '差异像素', '占比', '判定'))
    print('-' * 58)

    # --grab：先让 ROM 跑一串，再从显存抓帧（不截窗口）。
    # 每个用例挑**最接近**的那一帧来比，于是"时刻"不再是要人工调的魔法数字。
    series = None
    if a.grab:
        rom = os.path.join(ROOT, a.grab_rom)
        if not os.path.isfile(rom):
            raise SystemExit('找不到 ROM：%s\n先跑 .\\build.ps1 -Define GAL_AUTOPLAY -OutputName sample_auto' % rom)
        series = drive_series(rom, a.grab_presses, a.grab_wait,
                              os.path.join(ROOT, '.tmp', 'shots'))

    all_ok = True
    worst = None

    if series:
        # ---- 按行号对齐：每帧实机画面去和**每一句台词的预览图**比 ----
        #
        # 为什么不再扫时间轴：扫出来的最佳匹配总落在 t=0，
        # 说明两边在"这一帧是哪一句"上就没对齐 —— 而秒数本来就不该是判据 ✗
        #
        # 现在直接问工程模型："第 i 句台词在什么时候是完整可见的"，
        # 拿那句话的预览图去比。匹配到的行号还必须是**单调递增**的
        #（按了 1 次 A 是第 1 句、按了 2 次是第 2 句……顺序错了就是真错位）。
        lines = line_times(p)
        print('  工程里一共 %d 句台词（跨 %d 幕）' % (len(lines), len(p.scenes)))
        shots = []
        for _when, path in series:
            im = Image.open(path).convert('RGB')
            if im.size != (SCR_W, SCR_H):
                continue
            shots.append((os.path.basename(path), im))

        images = [(i, txt, r.render(sc, tt)) for i, sc, tt, txt, sp in lines]
        cursor = -1
        skipped = 0
        for name, im in shots:
            best = None
            for i, txt, mine in images:
                n = diff_pixels(im, mine)
                if best is None or n < best[0]:
                    best = (n, i, txt, mine)
            n, i, txt, mine = best
            pct = n / (SCR_W * SCR_H) * 100
            if pct >= 0.5:
                # 预览只画剧情（模式 3 那一套）；关卡/标题这类帧本来就对不上
                print('%-10s %-12d %-9s %s' % (name, n, '%.3f%%' % pct,
                                               '不是剧情画面（关卡/标题），跳过'))
                skipped += 1
                continue
            order_ok = i >= cursor
            cursor = i
            print('%-10s %-12d %-9s 匹配第 %d 句%s  %s'
                  % (name, n, '%.3f%%' % pct, i + 1,
                     '' if order_ok else '  ← 顺序不对 ✗',
                     ('「%s」' % txt[:12]) if txt else ''))
            if not order_ok:
                all_ok = False
            if worst is None or n > worst[0]:
                worst = (n, im, mine)
        print('-' * 58)
        if skipped == len(shots):
            print('结论：⚠ 一帧剧情画面都没抓到（检查按键序列）')
            all_ok = False
        else:
            print('结论：%s' % ('✅ 预览与实机逐像素一致，且台词顺序对得上'
                                if all_ok else '⚠ 有对不上的帧或顺序错位'))
        if worst and a.save_diff:
            real, mine = worst[1], worst[2]
            d = ImageChops.difference(real, mine).convert('L')
            vis = real.copy()
            dv, vp = d.load(), vis.load()
            for y in range(SCR_H):
                for x in range(SCR_W):
                    if dv[x, y] > 24:
                        vp[x, y] = (255, 0, 0)
            S = 3
            canvas = Image.new('RGB', (SCR_W * S * 2 + 30, SCR_H * S + 20), (20, 20, 26))
            canvas.paste(real.resize((SCR_W * S, SCR_H * S), Image.NEAREST), (10, 10))
            canvas.paste(vis.resize((SCR_W * S, SCR_H * S), Image.NEAREST),
                         (SCR_W * S + 20, 10))
            canvas.save(a.save_diff)
            print('对比图：%s（左=实机，右=实机+差异标红）' % a.save_diff)
        return 0 if all_ok else 1

    for fn, t, txt in CASES:
        mine = r.render(scene, t + len(txt) * TYPE_SPEED / FPS + 0.05)
        shot = os.path.join(a.rom_shots, fn)
        if not os.path.isfile(shot):
            print('%-10s （没有这张截图，跳过）' % fn)
            continue
        n, x0, y0, real = find_crop(shot, mine)
        pct = n / (SCR_W * SCR_H) * 100
        ok = pct < 0.5
        all_ok = all_ok and ok
        print('%-10s %-12d %-10s %s  (裁剪 %d,%d)' % (fn, n, '%.3f%%' % pct,
                                                      '一致' if ok else '有差异', x0, y0))
        if worst is None or n > worst[0]:
            worst = (n, real, mine)
    print('-' * 58)
    print('结论：%s' % ('预览与实机逐像素一致' if all_ok else '有可见差异，检查布局常量/字体/色深'))

    if worst and a.save_diff:
        real, mine = worst[1], worst[2]
        d = ImageChops.difference(real, mine).convert('L')
        vis = real.copy()
        dv, vp = d.load(), vis.load()
        for y in range(SCR_H):
            for x in range(SCR_W):
                if dv[x, y] > 24:
                    vp[x, y] = (255, 0, 0)
        S = 3
        canvas = Image.new('RGB', (SCR_W * S * 2 + 30, SCR_H * S + 20), (20, 20, 26))
        canvas.paste(real.resize((SCR_W * S, SCR_H * S), Image.NEAREST), (10, 10))
        canvas.paste(vis.resize((SCR_W * S, SCR_H * S), Image.NEAREST),
                     (SCR_W * S + 20, 10))
        canvas.save(a.save_diff)
        print('对比图：%s（左=实机，右=实机+差异标红）' % a.save_diff)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
