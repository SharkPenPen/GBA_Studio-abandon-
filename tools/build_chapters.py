#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_chapters.py —— 按章节分盘构建（每章一个独立 ROM）

【为什么分章】
32 MB 是**每盘卡带**的限制 ✗ 不是"整个游戏"的限制 ✓
所以把作品切成几章 ✓ 每章做一盘 ✓ 可装的东西成倍增加 ✓

实测（Nightmare×sisters，3 章）：

                    单盘塞完        分 3 章
    背景            150/429 (35%)   429/429 (100%)
    语音            180/1488 (12%)  ~600/1488 (~45%)
    文字            100%            100%
    立绘            12 个           12 个

**文字和背景能全搬，语音从 12% 提到 ~45%** ✓

【它做什么】
对每一章依次执行：

    1. tsv_to_project.py --chapter sN     剧本 → 工程
    2. collect_assets.py --share i/n      素材 → 工程的第 i 份
    3. 容量预算填充                        把这一章的容量用满（背景/立绘/语音/BGM）
    4. 导出 → 资源编译 → 编译 ROM         量出真实大小

⚠ 第 3 步是**合成**填充（背景摊开、语音顺序贴）✗ 不是原作调度 ✓
   原作调度在 .ws2 字节码里 ✓ 需要操作码表才能自动补上 ✓
   这里的目的只是**把容量账量准** ✓

⚠ 每一步都会覆盖引擎仓库的 scenario/ ✗ 所以脚本会**先备份、最后还原** ✓

用法：
    python tools\\build_chapters.py --src "<解包目录>" --tsv "<对照表>" --out "<输出目录>"
                                   [--chapters s0,s1]   # 只做某几章
                                   [--work "<临时工作目录>"]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, '.tools', 'pylibs'))

ROM_BUDGET_MB = 27.0        # 卡带 32MB，留 5MB 余量
FIXED_KB = 800              # 引擎 + 剧本 + 字库
KB_PER_SEC = 11.0           # 8bit 单声道 11025Hz（实测）
BG_KB, CHAR_KB = 75.0, 50.0  # 实测
BGM_SEC, VOICE_SEC = 85.0, 6.0


def log(m):
    print('[chapter] ' + m)


def run(cmd, **kw):
    return subprocess.run(cmd, **kw)


def count_voice(chap, src, tsv, work, scenes_json):
    """这一章有多少条**不同的**语音（决定拆几盘）

    ⚠ 必须以**调度表**为准 ✗
    踩过：原来优先读磁盘上的工程 ✓ 但那个工程可能是上一次拆盘后**已经裁过**的 ✓
    于是第二次跑就得出"不用拆"的结论 ✓✓ 分盘静默失效 ✗
    （教训：判断"该做多少"要看**源头数据**，不能看**上一次的半成品** ✓）
    """
    import json as _j
    want = chap.lower().lstrip('s')
    try:
        sm = _j.load(open(scenes_json, encoding='utf-8'))
        seen = set()
        for sc, info in sm.items():
            if not re.match(r's%s_' % want, sc, re.I):
                continue
            seen |= set((info.get('voice') or {}).values())
        if seen:
            return len(seen)
    except Exception:                                   # noqa: BLE001
        pass
    # 退路：实在没有调度表就数工程里的
    try:
        from core.project import Project
        p = Project.load(os.path.join(work, chap, chap + '.gbastudio'))
        seen = set()
        for s in p.scenes:
            for c in s.clips:
                if c.track == 'voice':
                    seen.add(c.ref)
        return len(seen)
    except Exception:                                   # noqa: BLE001
        return 0


def build_one(chap, src, tsv, out_dir, work, scenes_json='',
              voice_from=0, voice_to=0, part='', a_comp=''):
    """一章走完整条链路，返回统计"""
    from core.project import Project, Clip, Track
    from core import compiler
    import tsv_to_project as T

    proj_dir = os.path.join(work, chap)
    if os.path.isdir(proj_dir):
        shutil.rmtree(proj_dir, ignore_errors=True)
    os.makedirs(work, exist_ok=True)

    # 1) 剧本
    r = run([sys.executable, os.path.join(ROOT, 'tools', 'tsv_to_project.py'),
             '--tsv', tsv, '--out', work, '--name', chap, '--chapter', chap],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise RuntimeError('剧本转换失败：%s' % (r.stdout or r.stderr)[-300:])
    lines = [l for l in (r.stdout or '').splitlines() if '场景' in l]
    if lines:
        log('  ' + lines[-1].strip())

    # 2) 素材：**全库收进来**，让编译器按真实调度只打包用到的那几张
    #    （实测：s1 章只用 10 张背景 + 123 条语音 ✓ 所以不必再"按份切"了 ✓）
    r = run([sys.executable, os.path.join(ROOT, 'tools', 'collect_assets.py'),
             '--src', src, '--project', os.path.join(work, chap),
             '--share', '1/1', '--max-bg', '500', '--max-char', '20',
             '--max-voice', '1600', '--max-bgm', '20', '--max-se', '200'],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise RuntimeError('素材收集失败：%s' % (r.stdout or r.stderr)[-300:])
    for l in (r.stdout or '').splitlines():
        if '收进工程' in l or '角色表' in l:
            log('  ' + l.strip())

    # 3) **带真实调度再转一次** ✗
    #    调度表来自 .ws2（用户自己的反汇编器解析出来的 ✓）
    #    这一步才会把"哪一句配哪张图、放哪条语音、谁说的"挂上去 ✓
    if scenes_json and os.path.isfile(scenes_json):
        r = run([sys.executable, os.path.join(ROOT, 'tools', 'tsv_to_project.py'),
                 '--tsv', tsv, '--out', work, '--name', chap, '--chapter', chap,
                 '--scenes-json', scenes_json, '--keep-assets'],
                capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            raise RuntimeError('补调度失败：%s' % (r.stdout or r.stderr)[-300:])
        log('  已按原作调度挂上背景 / 语音 / 说话人')
    else:
        log('  ⚠ 没有调度表，只能是纯文字（跑 tools/ws2_scenes.py 生成）')

    # 3.5) **多层合成成一层** ✗
    # 原作是"底图 + 立绘 + 蒙版"叠加 ✓ GBA 只有一层背景 ✗
    # 这里在电脑上先把它们合成成 240x160 的成品图 ✓ 交给 GBA 的就是一张 ✓
    if a_comp and os.path.isfile(a_comp):
        r = run([sys.executable, os.path.join(ROOT, 'tools', 'compose_scenes.py'),
                 '--recipes', a_comp,
                 '--src', src,
                 '--out', os.path.join(work, chap, 'assets', 'bg'),
                 '--report', os.path.join(work, chap, '_comp_map.json')],
                capture_output=True, text=True, encoding='utf-8', errors='replace')
        for l in (r.stdout or '').splitlines():
            if '合成成功' in l or '共 ' in l:
                log('  ' + l.strip())
        maps = os.path.join(work, chap, '_comp_map_lines.json')
        if os.path.isfile(maps):
            r = run([sys.executable, os.path.join(ROOT, 'tools', 'tsv_to_project.py'),
                     '--tsv', tsv, '--out', work, '--name', chap, '--chapter', chap,
                     '--scenes-json', scenes_json, '--composite-map', maps,
                     '--keep-assets'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode != 0:
                raise RuntimeError('合成图挂载失败：%s' % (r.stdout or r.stderr)[-300:])
            for l in (r.stdout or '').splitlines():
                if '预合成' in l:
                    log('  ' + l.strip())

    p = Project.load(os.path.join(work, chap, chap + '.gbastudio'))

    # **按语音条数裁一刀** ✗
    # 实测：真实调度下每章只用 10~28 张背景（1~2 MB）✓
    # 于是卡带几乎**全被语音占满** ✗ 一张 32MB 卡放不下 979 条（≈64 MB）✓
    # 所以分盘要**按语音量**分，不是按章分 ✓
    # voice_from/voice_to：这一盘只留 [from, to) 区间内的语音 ✓ 其余留给下一盘 ✓
    allv = []
    seen = set()
    for s in p.scenes:
        for c in sorted([x for x in s.clips if x.track == 'voice'], key=lambda x: x.start):
            if c.ref not in seen:
                seen.add(c.ref)
                allv.append(c.ref)
    if voice_to:
        keep = set(allv[voice_from:voice_to])
        for s in p.scenes:
            s.clips = [c for c in s.clips
                       if c.track != 'voice' or c.ref in keep]
    else:
        keep = set(allv)
    p.save()
    nv = sum(1 for s in p.scenes for c in s.clips if c.track == 'voice')
    import collections as _c
    kind = _c.Counter(x.track for s in p.scenes for x in s.clips)
    log('  片段：%s' % dict(kind))
    log('  语音：这一盘留 %d 条（全章共 %d 条不同语音%s）'
        % (nv, len(allv), '，%d~%d' % (voice_from, voice_to) if voice_to else ''))

    # 4) 导出 → 资源 → ROM
    text, notes, mani = compiler.compile_project(p, proj_dir, log=lambda m: None)
    if not os.path.isdir(os.path.join(ROOT, 'scenario')):
        os.makedirs(os.path.join(ROOT, 'scenario'), exist_ok=True)
    with open(os.path.join(ROOT, 'scenario', 'scenario.txt'), 'w',
              encoding='utf-8', newline='\n') as f:
        f.write(text)
    with open(os.path.join(ROOT, 'scenario', 'assets.json'), 'w',
              encoding='utf-8', newline='\n') as f:
        json.dump(mani, f, ensure_ascii=False, indent=1)
    compiler.write_video_mode(p, os.path.join(ROOT, 'include'), log=lambda m: None)

    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command']
    run(ps + ["& '%s'" % os.path.join(ROOT, 'scripts', 'build-assets.ps1')],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    rom = os.path.join(ROOT, 'nxs_%s.gba' % (part or chap))
    if os.path.isfile(rom):
        os.remove(rom)
    rr = run(ps + ["& '%s' -OutputName nxs_%s -Clean"
                   % (os.path.join(ROOT, 'build.ps1'), part or chap)],
             capture_output=True, text=True, encoding='utf-8', errors='replace')
    size = os.path.getsize(rom) if os.path.isfile(rom) else 0
    ok = size > 0
    return {'chapter': chap, 'voice_total': len(allv), 'part': part,
            'scenes': len(p.scenes),
            'pages': sum(1 for s in p.scenes for c in s.clips if c.track == 'text'),
            'bg': len(mani.get('bg', [])),
            'sprites': len(mani.get('sprites', [])),
            'audio': len(mani.get('audio', [])),
            'voice': sum(1 for s in p.scenes for c in s.clips if c.track == 'voice'),
            'rom': size, 'ok': ok}


def main():
    ap = argparse.ArgumentParser(description='按章节分盘构建')
    ap.add_argument('--src', required=True, help='解包根目录')
    ap.add_argument('--tsv', required=True, help='台词对照表')
    ap.add_argument('--out', default=os.path.join(ROOT, '.tmp', 'chapters'))
    ap.add_argument('--work', default=os.path.join(ROOT, '.tmp', 'chap'))
    ap.add_argument('--chapters', default='s0,s1,s2')
    ap.add_argument('--composite', default=os.path.join(ROOT, '.tmp', 'scene_recipes.json'),
                    help='compose_scenes.py 用的配方表（多层合成成一层）')
    ap.add_argument('--only-part', type=int, default=0,
                    help='只做第 N 份（配合拆盘用）。比如只想重编 s0p1 就写 1')
    ap.add_argument('--voice-cap', type=int, default=330,
                    help='每盘最多放多少条不同语音（超了就自动拆盘）。'
                         '330 条 × 66KB ≈ 21MB，加上图正好塞进 32MB 卡带')
    ap.add_argument('--scenes-json', default=os.path.join(ROOT, '.tmp', 'ws2_scenes.json'),
                    help='ws2_scenes.py 产出的调度表（背景/语音/说话人）')
    a = ap.parse_args()

    # **调度表和配方表要是没有就先生成** ✗
    # 它们原来是会话里临时跑出来的 ✓ 清掉 .tmp 就没了 ✓ 那样流水线跑不动 ✓
    # 所以这里自动补一步 ✓（两个工具都是秒级的 ✓）
    for tool, out in (('ws2_scenes.py', a.scenes_json),
                      ('ws2_recipes.py', a.composite)):
        if out and not os.path.isfile(out):
            log('缺少 %s，先自动生成…' % os.path.basename(out))
            subprocess.run([sys.executable, os.path.join(ROOT, 'tools', tool),
                            '--out', out], capture_output=True)
            log('  %s' % ('已生成' if os.path.isfile(out) else '生成失败 ✗'))

    chaps = [c.strip() for c in a.chapters.split(',') if c.strip()]
    log('要做 %d 章：%s' % (len(chaps), ', '.join(chaps)))

    # 备份引擎仓库的"当前导出"
    bk = os.path.join(ROOT, '.tmp', 'backup_before_chapters')
    if os.path.isdir(bk):
        shutil.rmtree(bk, ignore_errors=True)
    os.makedirs(os.path.join(bk, 'scenario'), exist_ok=True)
    for f in ('scenario.txt', 'assets.json'):
        src = os.path.join(ROOT, 'scenario', f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(bk, 'scenario', f))
    log('已备份当前导出（跑完会还原）')

    results = []
    try:
        for c in chaps:
            # **先探一遍这一章有多少条不同语音** ✗ 超上限就自动拆成几盘 ✓
            n_voice = count_voice(c, a.src, a.tsv, a.work, a.scenes_json)
            cap = a.voice_cap
            parts = []
            if cap and n_voice > cap:
                k = 0
                while k * cap < n_voice:
                    parts.append((k * cap, min((k + 1) * cap, n_voice)))
                    k += 1
                log('')
                log('=== 第 %s 章：%d 条语音 > 上限 %d → 拆成 %d 盘 ==='
                    % (c, n_voice, cap, len(parts)))
            else:
                parts = [(0, 0)]
                log('')
                log('=== 第 %s 章（%d 条语音）===' % (c, n_voice))

            for pi, (vf, vt) in enumerate(parts):
                if a.only_part and pi + 1 != a.only_part:
                    continue
                name = c if len(parts) == 1 else '%sp%d' % (c, pi + 1)
                log('--- %s%s ---' % (name, '' if len(parts) == 1 else
                                      '（语音 %d~%d）' % (vf, vt)))
                t0 = time.time()
                try:
                    r = build_one(c, a.src, a.tsv, a.out, a.work, a.scenes_json,
                                  voice_from=vf, voice_to=vt, part=name,
                                  a_comp=a.composite)
                    r['sec'] = time.time() - t0
                    r['chapter'] = name
                    results.append(r)
                    log('  ✅ ROM %.2f MB（卡带 %.1f%%）  场景 %d / 页 %d / 背景 %d / 音频 %d'
                        % (r['rom'] / 1048576.0, r['rom'] / 33554432.0 * 100,
                           r['scenes'], r['pages'], r['bg'], r['audio']))
                except Exception as e:                  # noqa: BLE001
                    log('  ❌ %s 失败：%s' % (name, e))
                    results.append({'chapter': name, 'ok': False, 'rom': 0, 'error': str(e)})
    finally:
        # 还原：把备份的 scenario 文件拷回去
        # 以前这里会"从示例工程重新导出" —— 示例已经删掉了，不能这么做。
        # 而且本来也不该绑某个具体工程：**备份了什么就还原什么** 才是对的。
        for f in ('scenario.txt', 'assets.json'):
            s = os.path.join(bk, 'scenario', f)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(ROOT, 'scenario', f))
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-Command', "& '%s'" % os.path.join(ROOT, 'scripts', 'build-assets.ps1')],
                       capture_output=True)
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-Command', "& '%s' -OutputName gba_ai -Clean" % os.path.join(ROOT, 'build.ps1')],
                       capture_output=True)
        log('')
        log('已还原示例工程的导出')

    log('')
    log('=== 汇总 ===')
    tot = 0
    for r in results:
        if r.get('ok'):
            tot += r['rom']
            log('  %-4s %6.2f MB  场景 %2d  页 %4d  背景 %3d  音频 %3d  用时 %.0f 秒'
                % (r['chapter'], r['rom'] / 1048576.0, r['scenes'], r['pages'],
                   r['bg'], r['audio'], r.get('sec', 0)))
        else:
            log('  %-4s 失败：%s' % (r['chapter'], r.get('error', '?')))
    if tot:
        log('  合计 %.1f MB（%d 盘卡带）' % (tot / 1048576.0, len(results)))
    with open(os.path.join(ROOT, '.tmp', 'chapters_report.json'), 'w',
              encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    log('  报告：.tmp\\chapters_report.json')
    return 0 if all(r.get('ok') for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
