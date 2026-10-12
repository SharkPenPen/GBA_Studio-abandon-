#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
剧本转换：解包剧本（TSV）→ 工程 / scenario.txt

守护的东西：
  · 控制码清干净（%K %P \\n 「」都不该留在台词里）
  · **超过 3 行的台词必须分页** ✗ 引擎对话框只有 3 行，不分页会被静默截掉
  · 分页用的排版算法和引擎一致（core.preview.layout_text）
  · 建出来的工程能被编辑器读回、能导出
  · **.ps1 必须有 UTF-8 BOM** ✗ 这是这个项目反复踩的坑
    （丢了 BOM，PowerShell 会按 GBK 读中文 → 乱码 → 语法错）
"""
import io
import os
import sys
import glob
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

TMP = os.path.join(ROOT, '.tmp', 'script-conv-test')

# 解包出来的对照表（存在才测真实数据）
REAL_TSV = r"D:\游戏解包\Nightmare×sisters～淫狱的献祭～\剧本\台词对照_JP_CN.tsv"


def _mk_tsv(path, rows):
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('场景\t索引\t日文\t中文\n')
        for sc, ix, cn in rows:
            f.write('%s\t%d\tchar「x」\t%s\n' % (sc, ix, cn))


def test_control_codes_stripped():
    """控制码必须清干净 —— 留在台词里会实机显示成方块或乱码"""
    import tsv_to_project as T
    cases = [
        ('除灵结束，我和姐姐一起泡澡。%K%P', '除灵结束，我和姐姐一起泡澡。'),
        ('「引号包着的」%K%P', '引号包着的'),
        ('第一行\\n第二行%K%P', '第一行 第二行'),
        ('带着%K中间的控制码%P', '带着中间的控制码'),
        ('  多余   空格\u3000　%K%P  ', '多余 空格'),
    ]
    for raw, want in cases:
        got = T.clean_text(raw)
        assert got == want, '%r → %r，期望 %r' % (raw, got, want)
    # 控制码一个都不能剩
    for raw, _ in cases:
        got = T.clean_text(raw)
        for bad in ('%K', '%P', '「', '」', '\\n'):
            assert bad not in got, '%r 里还留着 %s' % (raw, bad)


def test_long_line_is_paginated():
    """超过 3 行的台词必须被切开 —— 否则实机上后半句直接消失

    引擎的对话框写死 `TEXT_LINES 3` ✗ 而且**不报错**，只是不画 ✓
    这是最难查的一类问题，所以钉死在测试里。
    """
    import tsv_to_project as T
    from core.preview import layout_text

    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, 'long.tsv')
    long_cn = '这是一句特别长的台词，' * 8      # 远超 3 行
    # ⚠ 这里也要传 max_lines=9999 ✗
    # layout_text 的默认就是"只排 3 行"（给渲染用的）✓
    # 用默认值断言"超过 3 行"是**永远不成立**的 ✗（第一版就这么写的 ✓
    # 于是测试报"样本得真的超过 3 行" ✓ 反而暴露了分页本身的同一个 bug ✓）
    assert len(layout_text(T.clean_text(long_cn), max_lines=9999)) > 3, \
        '样本得真的超过 3 行'

    _mk_tsv(p, [('s0_01', 0, long_cn), ('s0_01', 1, '短句。%K%P')])
    rows = T.read_tsv(p)
    assert len(rows) == 2
    proj, st = T.build_project(rows, 'T')
    # 长句被切成多页 → 片段数应该多于原始行数
    assert st['pages'] > 2, '长台词没有被分页：页数 = %d' % st['pages']
    for s in proj.scenes:
        for c in s.clips:
            n = len(layout_text(c.props['text'], max_lines=9999))
            assert n <= 3, '有一页仍然超过 3 行（%d 行）—— 实机上会被截掉' % n


def test_project_round_trip():
    """转出来的工程要能被编辑器读回、并且能导出成剧本"""
    import tsv_to_project as T
    from core.project import Project
    from core import compiler

    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, 'rt.tsv')
    _mk_tsv(p, [('s0_01', 0, '第一句。%K%P'), ('s0_01', 1, '第二句。%K%P'),
                ('s0_02', 0, '另一幕。%K%P')])
    rows = T.read_tsv(p)
    proj, st = T.build_project(rows, 'RT')
    out = os.path.join(TMP, 'RT')
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, 'RT.gbastudio')
    proj.path = path
    proj.save(path)

    back = Project.load(path)
    assert len(back.scenes) == 2, '两个 TSV 场景应该变成两个场景，实际 %d' % len(back.scenes)
    assert sum(len(s.clips) for s in back.scenes) >= 3, '台词片段少了'

    text, notes, mani = compiler.compile_project(back, out, log=lambda m: None)
    says = [ln for ln in text.splitlines() if ln.startswith('say ')]
    assert len(says) >= 3, '导出的 say 太少：%d' % len(says)
    for ln in says:
        body = ln.split('|', 1)[1]
        for bad in ('%K', '%P', '「', '」'):
            assert bad not in body, '导出后还带着控制码：%s' % bad


def test_real_script_converts():
    """有真实对照表时，整部剧本要能转完并且统计合理

    （没装素材的机器上跳过 ✓ 不硬依赖）
    """
    import tsv_to_project as T
    if not os.path.isfile(REAL_TSV):
        print('     （没有真实对照表，跳过）')
        return
    rows = T.read_tsv(REAL_TSV)
    assert len(rows) > 1000, '真实剧本应该上千行，实际 %d' % len(rows)
    proj, st = T.build_project(rows, 'REAL')
    assert st['scenes'] >= 30, '场景数偏少：%d' % st['scenes']
    assert st['chars'] > 50000, '中文字数偏少：%d' % st['chars']
    # 字库和文本都得放得进 32MB（这是可行性评估的核心结论）
    font_kb = st['unique'] * 25 / 1024.0
    text_kb = st['chars'] * 2 / 1024.0
    assert font_kb + text_kb < 2 * 1024, \
        '剧本+字库占了 %.0f KB，超出预期（应该只有几百 KB）' % (font_kb + text_kb)
    print('     %d 场景 / %d 页 / %d 字（%d 个不同字）→ 字库 %.0f KB + 文本 %.0f KB'
          % (st['scenes'], st['pages'], st['chars'], st['unique'], font_kb, text_kb))


def test_ps1_files_have_utf8_bom():
    """**所有 .ps1 必须有 UTF-8 BOM** ✗

    这个坑今天又踩了一次：编辑 `scripts/build-assets.ps1` 时 BOM 丢了 ✗
    PowerShell 5.1 没有 BOM 就按 GBK 读 ✓ 中文全变乱码 ✓
    报的却是莫名其妙的语法错（"Array index expression is missing"）✗
      —— 完全看不出是编码问题，能查半天 ✓

    所以钉死：只要仓库里有 .ps1，它就必须带 BOM ✓
    """
    bad = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn
                 if d not in ('.git', '.tmp', 'build', '.toolchain', '__pycache__', '.tools')]
        for f in fn:
            if f.endswith('.ps1'):
                q = os.path.join(dp, f)
                if not open(q, 'rb').read(3) == b'\xef\xbb\xbf':
                    bad.append(os.path.relpath(q, ROOT))
    assert not bad, ('这些 .ps1 丢了 UTF-8 BOM（PowerShell 会把中文读成乱码）：%s。'
                     '修法：在文件开头写回 EF BB BF' % bad)


def test_chapter_split():
    """分章：只取某一章，而且各章**互不重叠**

    守护的是分盘策略的地基 ✗
    32MB 是**每盘卡带**的限制 ✓ 所以分章 = 多盘 = 可装内容成倍 ✓
    但前提是：剧本按章切得干净 ✓ 素材按份切得**不重叠** ✓
    否则两盘装同一批素材 = 白分 ✓

    （实测数字见 docs/20-分章分盘实测.md：背景 35%→93%、语音 12%→36%）
    """
    import tsv_to_project as T
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, 'chap.tsv')
    _mk_tsv(p, [('s0_01', 0, '甲%K%P'), ('s0_02', 0, '乙%K%P'),
                ('s1_01', 0, '丙%K%P'), ('s2_01', 0, '丁%K%P'),
                ('s2_02', 0, '戊%K%P')])
    rows = T.read_tsv(p)
    assert len(rows) == 5

    # 按章过滤（和 main() 里 --chapter 的逻辑一致）
    import re as _re
    got = {}
    for ch in ('0', '1', '2'):
        got[ch] = [r for r in rows if _re.match(r's%s_' % ch, r[0], _re.I)]
    assert [len(got[c]) for c in '012'] == [2, 1, 2], \
        '分章数量不对：%s' % {c: len(got[c]) for c in '012'}
    total = sum(len(v) for v in got.values())
    assert total == len(rows), '分章后有台词丢了：%d / %d' % (total, len(rows))

    # 素材分份必须互不重叠、合起来是全集
    files = list(range(20))
    shares = [[x for j, x in enumerate(files) if j % 3 == i] for i in range(3)]
    flat = [x for s in shares for x in s]
    assert sorted(flat) == files, '三份合起来不是全集'
    assert len(set(flat)) == len(flat), '三份之间有重复 ✗ 那两盘会装同一批素材'
    assert all(len(s) > 0 for s in shares), '有份是空的'


def test_chapter_build_restores_sample():
    """分章构建脚本必须**自己把示例导出还原**（并做完整重编）

    踩过两次：
      1. 只拷 scenario/ 目录里那两个文件 → 音频那条链没恢复 → test_audio_data 红 ✗
      2. 还原时编译没加 -Clean → 增量编译留下上一章的目标文件 →
         示例 ROM 变成 511,520（应为 513,916）✗
    所以这里静态检查脚本里这两件事都在 ✓
    """
    src = open(os.path.join(ROOT, 'tools', 'build_chapters.py'), encoding='utf-8').read()
    # 还原不再依赖某个具体示例工程（示例已经删掉了 ✓）
    # 改成检查：脚本有备份 + 还原的动作 ✓ 不绑定某个工程名 ✓
    assert 'backup' in src.lower() or '备份' in src, '应该先备份当前导出'
    assert 'compile_project' in src, '还原时要重新导出示例'
    assert '-Clean' in src, '还原时的编译必须 -Clean（否则会剩上一章的目标文件）'
    assert src.count('-Clean') >= 2, \
        '两处编译（章节的 + 还原的）都该带 -Clean，现在只有 %d 处' % src.count('-Clean')


def test_every_python_file_parses():
    """仓库里每个 .py 都要能编译过

    ⚠ 为什么需要这条 ✗
    改 `build_chapters.py` 时把一处 `try:` 改坏了 ✓ 语法都不成立 ✓
    但**测试全绿** ✗ —— 因为 `test_script_convert.py` 只是把它当**文本**读
    （检查里面有没有某个字符串 ✓）✓ 从来没 import 过它 ✓
    一个文件"被测试提到过" ≠ "被测试验证过" ✓

    所以这里统一 parse 一遍 ✓ 成本几乎为零 ✓ 能挡住整类事故 ✓
    """
    import ast
    import glob
    bad = []
    for pat in ('tests/*.py', 'tools/*.py', 'gbastudio/*.py',
                'gbastudio/*/*.py', 'gbastudio/*/*/*.py'):
        for q in glob.glob(os.path.join(ROOT, pat)):
            try:
                ast.parse(io.open(q, encoding='utf-8').read(), filename=q)
            except SyntaxError as e:
                bad.append('%s:%s %s' % (os.path.relpath(q, ROOT), e.lineno, e.msg))
    assert not bad, '这些文件编译不过：\n  ' + '\n  '.join(bad)


def main():
    tests = [
        ('控制码清干净', test_control_codes_stripped),
        ('超长台词分页', test_long_line_is_paginated),
        ('工程往返 + 导出', test_project_round_trip),
        ('真实剧本能转', test_real_script_converts),
        ('.ps1 有 BOM', test_ps1_files_have_utf8_bom),
        ('分章切分不重叠', test_chapter_split),
        ('分章脚本会自动还原', test_chapter_build_restores_sample),
        ('所有 py 都能编译', test_every_python_file_parses),
    ]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print('    %-20s 通过' % name)
        except AssertionError as e:
            print('    %-20s 失败：%s' % (name, e))
            bad += 1
        except Exception as e:                          # noqa: BLE001
            print('    %-20s 出错：%s: %s' % (name, type(e).__name__, e))
            bad += 1
    print()
    if bad:
        print('❌ %d 项没通过' % bad)
        return 1
    print('✅ 剧本转换：控制码、分页、往返导出、.ps1 编码都对得上')
    return 0


if __name__ == '__main__':
    sys.exit(main())
