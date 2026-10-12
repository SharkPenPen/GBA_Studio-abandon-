#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_sample.py —— 测试用的示例工程夹具（现场生成，不依赖仓库里的 samples/）

【为什么要这样】
以前测试直接读 `samples/魔女与少女/` ✓ 于是：
    · 仓库里必须长期留一份示例 ✗
    · 测试依赖一个"持久存在的文件" ✓ 那个文件一改，测试就红 ✓
    · 更糟的是：示例本来是"给引擎做验收用的" ✓ 却变成了引擎和测试的**依赖** ✓
      ——用户的原话是"示例是用来测试引擎的，不是构建引擎的，不能和引擎有关系" ✓

所以改成：测试**自己现场生成**一份最小示例 ✓
生成到 `.tmp/sample/`（工作区里的草稿区 ✓ 可以随时删 ✓）
用 `tools/make_sample.py` ✓（那个生成器是正式工具 ✓ 不会被删 ✓）

**好处**：
    · 仓库里可以没有 samples/ ✓
    · 测试不依赖任何"历史遗留文件" ✓ 每次都是新生成的 ✓
    · 生成出来的东西和"用户新建工程"走同一套代码 ✓ 更接近真实 ✓

【用法】
    from _sample import SAMPLE, SAMPLE_DIR
    p = Project.load(SAMPLE)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FIXTURE_DIR = os.path.join(ROOT, '.tmp', 'sample')
SAMPLE_DIR = os.path.join(FIXTURE_DIR, '魔女与少女')
SAMPLE = os.path.join(SAMPLE_DIR, '魔女与少女.gbastudio')


def ensure():
    """确保夹具存在、而且是**最新生成器**产的。返回项目文件路径。

    ⚠ 不能只看"文件在不在" ✗
    踩过：改了 `make_sample.py` 之后跑测试 ✓ 结果夹具还是旧的 ✓
    因为 `.tmp` 的删除**静默失败过**（工作区里有拒绝删除权限的项 ✓）
    于是测试用一个过期夹具跑 ✓ 报出"精灵素材只有 1 个"这种假故障 ✓
    ——**夹具要跟着生成器走，不能只跟着存在性走** ✓

    所以这里比一次修改时间：生成器比夹具新 → 重新生成 ✓
    """
    gen = os.path.join(ROOT, 'tools', 'make_sample.py')
    if not os.path.isfile(gen):
        raise RuntimeError('缺少生成器 %s（它是正式工具，不该被删）' % gen)
    if os.path.isfile(SAMPLE) and os.path.getmtime(SAMPLE) >= os.path.getmtime(gen):
        return SAMPLE
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    r = subprocess.run([sys.executable, gen, '-o', FIXTURE_DIR, '-n', '魔女与少女'],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', cwd=ROOT)
    if not os.path.isfile(SAMPLE):
        raise RuntimeError('示例夹具生成失败：\n%s\n%s'
                           % (r.stdout or '', r.stderr or ''))
    return SAMPLE


# 导入时就准备好 —— 测试文件里直接 `from _sample import SAMPLE` 就能用
ensure()
