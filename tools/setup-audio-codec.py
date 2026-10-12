#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup-audio-codec.py —— 装音频解码库（用于把 OGG/MP3 转成 GBA 格式）

【为什么要自己下载解压，而不是 pip install】
实测环境：`pip install` 一定失败 ✗

    ERROR: Could not install packages due to an OSError:
    [Errno 13] Permission denied: '...\\pip-unpack-xxxx\\soundfile-....whl.metadata'

根因不是网络、也不是权限配错 ✗ 而是：
**这个工作区不允许删除子目录**（有一条 DeleteSubdirectoriesAndFiles 的拒绝项，
是 DSH 沙箱自己的设计），而 pip 从解包到安装**全程依赖临时目录的创建与清理** ✗
（实测：普通的读写都没问题 ✓ 只有 `tempfile.TemporaryDirectory()` 会报拒绝访问 ✗）

而 **wheel 本质上就是一个 zip 包** ✗ 所以这里干脆跳过 pip：
    下载 wheel → 用 zipfile 解压到 .tools/pylibs → 完事
不建临时目录、不删任何东西，因此在这个环境里是**稳的** ✓

【装的是什么】
    soundfile   读写音频，自带 libsndfile（能解 OGG/Vorbis、FLAC、MP3 等）
    cffi        soundfile 的依赖（带编译好的后端）
    pycparser   cffi 的依赖（纯 Python）

装到 **项目自己的** `.tools/pylibs/` ✓ 不是系统目录 ✓
换台机器就把这个目录一起拷走，或者重跑一次这个脚本 ✓

用法：
    python tools\\setup-audio-codec.py          # 装/修复
    python tools\\setup-audio-codec.py --check  # 只看装没装
"""
import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, '.tools', 'pylibs')

WANT = ['soundfile', 'cffi', 'pycparser']
# cffi 有编译好的扩展，要挑对本机 Python 版本与架构的 wheel
TAG_HINTS = ('win_amd64',)


def log(m):
    print('[codec] ' + m)


def pick_wheel(urls, py_tag):
    """从 PyPI 给的链接里挑一个能用的 wheel（优先本机 Python 版本 + win_amd64）"""
    cands = [u for u in urls if u.endswith('.whl')]
    if not cands:
        return None
    for want in (py_tag, 'py3', 'py2.py3'):
        for hint in TAG_HINTS:
            for u in cands:
                name = u.rsplit('/', 1)[-1]
                if want in name and hint in name:
                    return u
    # 纯 Python 包（pycparser）任何 wheel 都一样
    for u in cands:
        if 'py2.py3-none-any' in u or 'py3-none-any' in u:
            return u
    return None


def fetch(url, timeout=60):
    log('下载 %s' % url.rsplit('/', 1)[-1])
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def install_one(pkg, py_tag):
    meta = json.loads(fetch('https://pypi.org/pypi/%s/json' % pkg).decode('utf-8'))
    ver = meta['info']['version']
    urls = [f['url'] for f in meta['releases'].get(ver, [])]
    url = pick_wheel(urls, py_tag)
    if not url:
        log('✗ %s %s 没有适合本机的 wheel（版本/架构不匹配）' % (pkg, ver))
        return False
    blob = fetch(url)
    os.makedirs(LIB, exist_ok=True)
    n = 0
    # **直接解压，不建临时目录**（这就是绕开 pip 的关键）
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            if name.endswith('/'):
                continue
            # 跳过 wheel 的元数据目录里的描述文件也没关系，留着更好排查
            dst = os.path.join(LIB, name.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with z.open(name) as src, open(dst, 'wb') as out:
                out.write(src.read())
            n += 1
    log('✓ %s %s → %d 个文件' % (pkg, ver, n))
    # **把依赖也装掉** ✗ 手写依赖列表会漏（踩过：cffi 2.x 需要 typing_extensions，
    # 少了它 import 直接失败）。wheel 里自带 METADATA，读它就行 ✓
    deps = []
    for name in z.namelist() if False else []:
        pass
    return True


def requires_of(pkg):
    """读 wheel 的 METADATA，取出它依赖哪些包"""
    meta = json.loads(fetch('https://pypi.org/pypi/%s/json' % pkg).decode('utf-8'))
    ver = meta['info']['version']
    urls = [f['url'] for f in meta['releases'].get(ver, [])]
    url = pick_wheel(urls, 'py3')
    if not url:
        return []
    blob = fetch(url)
    out = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for n in z.namelist():
            if n.endswith('METADATA'):
                text = z.read(n).decode('utf-8', 'replace')
                for line in text.splitlines():
                    if line.startswith('Requires-Dist:'):
                        spec = line.split(':', 1)[1].strip()
                        # 跳过 extras（形如 foo; extra == "x"）和平台标记
                        if 'extra ==' in spec:
                            continue
                        nm = spec.split(';')[0].split('[')[0].strip()
                        nm = nm.split(' ')[0].split('(')[0].split('<')[0] \
                               .split('>')[0].split('=')[0].split('!')[0].strip()
                        if nm and nm.lower() not in ('python',):
                            out.append(nm)
                break
    return out


def check():
    sys.path.insert(0, LIB)
    try:
        import soundfile as sf
        subs = sf.available_subtypes('OGG')
        log('soundfile %s 已装 ✓  OGG 可读：%s'
            % (sf.__version__, '是' if subs else '否'))
        return True
    except Exception as e:                              # noqa: BLE001
        log('还没装好：%s: %s' % (type(e).__name__, e))
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只检查，不下载')
    a = ap.parse_args()

    log('库目录：%s' % LIB)
    if a.check:
        return 0 if check() else 1

    if check():
        log('已经能用了，不需要重装（想强制重装就删掉 .tools/pylibs/soundfile*）')
        return 0

    py_tag = 'cp%d%d' % (sys.version_info.major, sys.version_info.minor)
    log('本机 Python 标记：%s / win_amd64' % py_tag)
    done, queue, ok = set(), list(WANT), True
    while queue:
        pkg = queue.pop(0)
        key = pkg.lower().replace('-', '_')
        if key in done:
            continue
        done.add(key)
        try:
            if not install_one(pkg, py_tag):
                ok = False
                continue
        except Exception as e:                          # noqa: BLE001
            log('✗ %s 装失败：%s: %s' % (pkg, type(e).__name__, e))
            ok = False
            continue
        # 递归：它的依赖也装上（读 wheel 自带的 METADATA，不手写清单）
        try:
            for d in requires_of(pkg):
                if d.lower().replace('-', '_') not in done:
                    log('   %s 需要 %s，一起装' % (pkg, d))
                    queue.append(d)
        except Exception as e:                          # noqa: BLE001
            log('   读 %s 的依赖失败（继续）：%s' % (pkg, e))
    log('')
    if check():
        log('完成 ✓ 现在 OGG/MP3 可以被自动转码了')
        return 0
    log('✗ 还是不能用。也可以直接找一份 ffmpeg.exe 放到 .tools/ 下，'
        '音频工具会自动用它')
    return 1


if __name__ == '__main__':
    sys.exit(main())
