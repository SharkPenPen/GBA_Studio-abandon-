# -*- coding: utf-8 -*-
"""
gba_build.py —— 调现有工具链把剧本编成 .gba

**不重新实现任何编译逻辑**，只做两件事：
  1. 把剧本写进 GBA 工程的 scenario/scenario.txt（原文件备份成 .bak）
  2. 依次调 scripts/build-assets.ps1 和 build.ps1

为什么必须重跑 build-assets.ps1：中文字库是**按剧本里出现过的字**生成的，
新写的台词会带进新汉字，不重算的话那些字在屏幕上会直接空白。

踩过的坑（docs/05 记过，这里照抄做法）：
  · TMP/TEMP 必须指到工程内的 .tmp，否则编译器写临时文件可能失败
  · PowerShell 往管道输出中文用的是控制台编码，要先设 [Console]::OutputEncoding
    为 UTF-8，Python 这边才能正确解码
"""
import os
import subprocess
import sys
import time

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def find_gba_project(start=None):
    """找 GBA 工程目录（含 build.ps1）。默认从 gbastudio 的上一级找"""
    cands = []
    if start:
        cands.append(start)
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [os.path.dirname(os.path.dirname(here)), os.getcwd()]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'build.ps1')) and \
           os.path.isfile(os.path.join(c, 'scripts', 'build-assets.ps1')):
            return os.path.abspath(c)
    return None


def _run_ps(project_dir, script_rel, log, timeout=900):
    script = os.path.join(project_dir, script_rel)
    if not os.path.isfile(script):
        log('找不到脚本：%s' % script)
        return False
    ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; & '%s'"
          % script.replace("'", "''"))
    env = dict(os.environ)
    tmp = os.path.join(project_dir, '.tmp')
    os.makedirs(tmp, exist_ok=True)
    env['TMP'] = tmp
    env['TEMP'] = tmp
    env['PYTHONIOENCODING'] = 'utf-8'
    log('> powershell %s' % script_rel)
    try:
        p = subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                              '-Command', ps],
                             cwd=project_dir, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        log('启动失败：%s' % e)
        return False
    t0 = time.time()
    while True:
        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                break
            if time.time() - t0 > timeout:
                p.kill()
                log('超时（%d 秒）' % timeout)
                return False
            continue
        txt = line.decode('utf-8', errors='replace').rstrip()
        if txt.strip():
            log('  ' + txt)
    log('  → 退出码 %s' % p.returncode)
    return p.returncode == 0


def export_rom(project_dir, scenario_text, rom_name='gba_ai', log=print, manifest=None):
    """
    manifest：P5 的资源清单（背景/立绘/LOGO 的源文件列表）。
    有它 → 资源编译器按清单生成索引表（任意数量资源）；
    没有 → 退回旧的写死资源流程。
    返回 (成功?, ROM 路径或 None)
    """
    if not project_dir:
        log('❌ 没找到 GBA 工程目录（需要含 build.ps1 的目录）')
        return False, None
    scen_dir = os.path.join(project_dir, 'scenario')
    os.makedirs(scen_dir, exist_ok=True)
    path = os.path.join(scen_dir, 'scenario.txt')
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                old = f.read()
            with open(path + '.bak', 'w', encoding='utf-8') as f:
                f.write(old)
            log('原剧本已备份到 scenario\\scenario.txt.bak')
        except Exception as e:
            log('备份剧本失败（继续）：%s' % e)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(scenario_text)
    log('剧本已写入 %s（%d 行）' % (path, scenario_text.count('\n')))

    if manifest is not None:
        try:
            import json
            mp = os.path.join(scen_dir, 'assets.json')
            with open(mp, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
            log('资源清单：背景 %d 张，立绘 %d 张%s'
                % (len(manifest.get('bg', [])), len(manifest.get('sprites', [])),
                   '，含 LOGO' if manifest.get('logo') else ''))
        except Exception as e:
            log('❌ 写资源清单失败：%s' % e)
            return False, None
    else:
        # 没有清单：把旧的清单删掉，否则资源编译器还会按旧清单跑
        old_mani = os.path.join(scen_dir, 'assets.json')
        if os.path.isfile(old_mani):
            try:
                os.remove(old_mani)
                log('已清除旧资源清单（本版没有素材清单）')
            except Exception:
                pass

    log('')
    log('── 第 1 步：生成资源（剧本 → C 数组、按新剧本重算中文字库、素材转换）──')
    if not _run_ps(project_dir, os.path.join('scripts', 'build-assets.ps1'), log):
        log('❌ 资源生成失败')
        return False, None
    log('')
    log('── 第 2 步：编译 ROM ──')
    if not _run_ps(project_dir, 'build.ps1', log):
        log('❌ 编译失败')
        return False, None

    rom = os.path.join(project_dir, rom_name + '.gba')
    if not os.path.isfile(rom):
        log('❌ 没找到 ROM：%s' % rom)
        return False, None
    log('')
    log('✅ 导出成功：%s（%.1f KB）' % (rom, os.path.getsize(rom) / 1024))
    return True, rom


def run_emulator(project_dir, log=print):
    """用工程自带的 play.cmd 试玩（启动后立即返回）"""
    play = os.path.join(project_dir, 'play.cmd')
    if not os.path.isfile(play):
        log('找不到 play.cmd')
        return False
    try:
        tmp = os.path.join(project_dir, '.tmp')
        os.makedirs(tmp, exist_ok=True)
        # 子进程输出必须重定向，否则 GUI 会继承本进程的管道，调用方收不了尾
        f = open(os.path.join(tmp, 'play-gbastudio.log'), 'ab')
        subprocess.Popen(['cmd.exe', '/c', play], cwd=project_dir, stdout=f, stderr=f,
                         creationflags=CREATE_NO_WINDOW)
        log('已启动模拟器')
        return True
    except Exception as e:
        log('启动模拟器失败：%s' % e)
        return False
