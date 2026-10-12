#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_sample.py —— 生成一个**能直接跑通到 GBA ROM** 的样品工程

它做的事：
  1. 在 samples/ 下建一个项目目录（含 assets/ 标准目录结构）
  2. 把 assets_src/images 里的真实素材拷进去，并**手动归类**（背景 / 立绘）
  3. 建角色表（witch / girl，和现有引擎的角色 id 对齐）
  4. 排一条时间轴：换背景 → 出立绘 → 三句对话 → 换背景 → 收尾
  5. 存成 .gbastudio

只用了现有 C 引擎支持的元素（背景 / 立绘 / 台词），所以**导出的 ROM 能真跑**。
语音、音乐、特效这些片段故意没放 —— 引擎还不支持（编译器会如实报告跳过）。

用法：
    python tools/make_sample.py            # 生成到 samples/魔女与少女
    python tools/make_sample.py -o 别的目录
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))

from core.project import Project, Scene, Clip, Character   # noqa: E402
from core import assets as A                               # noqa: E402

# 素材来源（assets_src/images 里的原图）→ 在项目里的归类
# 后三个是 tools/make_test_assets.py 生成的**测试素材**，专门用来验证
# "引擎能不能认第三张背景、第三个角色、居中位置"（P5 的核心）。
SOURCES = [
    ('beijing.png',       'bg',   '海岸.png'),
    ('biaotibeijing.png', 'bg',   '沙漠.png'),
    ('test_forest.png',   'bg',   '森林.png'),
    ('test_night.png',    'bg',   '夜晚.png'),
    ('jiaose01_zuo.png',  'char', ('魔女', 'normal.png')),
    ('jiaose02_you.png',  'char', ('少女', 'normal.png')),
    ('test_golem.png',    'char', ('石人', 'normal.png')),
    ('biaoti.png',        '',     'LOGO.png'),          # 不归类，演示"未分类"状态
    # 精灵帧（关卡模式的玩家动画用）✗
    # 这 5 张原来只存在于仓库里那份 samples/ 里 ✓ 生成器漏了 ✓
    # 于是"测试改成现场生成"时立刻暴露：精灵模式的可选素材从 5 变成 1 ✓
    ('player_idle.png',  'sprite', 'player_idle.png'),
    ('player_jump.png',  'sprite', 'player_jump.png'),
    ('player_walk0.png', 'sprite', 'player_walk0.png'),
    ('player_walk1.png', 'sprite', 'player_walk1.png'),
    ('player_walk2.png', 'sprite', 'player_walk2.png'),
]

# 有人用测试素材时会打印提示，免得以后分不清哪些是真素材
TEST_SOURCES = {'test_forest.png', 'test_night.png', 'test_golem.png',
                'player_idle.png', 'player_jump.png', 'player_walk0.png',
                'player_walk1.png', 'player_walk2.png'}

# 音频（tools/make_test_audio.py 生成）：转换工具只认 WAV
AUDIO_SOURCES = [
    ('test_bgm.wav',     'bgm',   '序曲.wav'),
    ('test_voice_1.wav', 'voice', 'witch_0101.wav'),
    ('test_voice_2.wav', 'voice', 'girl_0102.wav'),
    ('test_se.wav',      'se',    '叮.wav'),
]

# 样品剧情（名字和内容随便写的，就是为了验证链路）
SCRIPT = [
    (0.0,  'bg',   'show', '海岸.png',               {}),
    (0.5,  'char', 'show', 'witch',                  {'pose': 'normal', 'pos': 'left'}),
    (1.0,  'say',  'witch',   '海风停了。',            {}),
    (3.0,  'say',  'witch',   '你看，连浪都不肯再往前推了。', {}),
    (6.0,  'char', 'show', 'girl',                   {'pose': 'normal', 'pos': 'right'}),
    (6.5,  'say',  'girl',    '……它又在叫我了。',       {}),
    (9.0,  'say',  'witch',   '叫你的东西，可不止那一座塔。', {}),
    (12.0, 'char', 'hide', 'girl',                   {'pos': 'right'}),
    (12.5, 'say',  'narrate', '于是她们沿着海岸，走向那片黄色的沙。', {}),
    (15.0, 'bg',   'show', '沙漠.png',               {}),
    (15.5, 'char', 'hide', 'witch',                  {'pos': 'left'}),
    (16.0, 'say',  'narrate', '那一天，沙漠里多了一个人的脚印。', {}),
    (18.5, 'say',  'narrate', '序章 · 完',            {}),
]

# 第二幕：专门用来验证 P5 —— 第三/第四张背景、第三个角色（居中）
SCRIPT2 = [
    (0.0,  'bg',   'show', '森林.png',               {}),
    (0.5,  'char', 'show', 'golem',                  {'pose': 'normal', 'pos': 'center'}),
    (1.0,  'say',  'narrate', '森林深处，有个东西一直站着没动。', {}),
    (4.0,  'say',  'narrate', '它不是树。它在等。',    {}),
    (7.0,  'bg',   'show', '夜晚.png',               {}),
    (7.5,  'say',  'narrate', '天黑了。它还在。',      {}),
    (10.0, 'char', 'hide', 'golem',                  {'pos': 'center'}),
    (10.5, 'say',  'narrate', '第二幕 · 完',          {}),
]


def _force_rm(path):
    """删目录：遇到只读文件先清属性再删（copy2 会把只读属性带过来）"""
    import stat

    def onerr(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    shutil.rmtree(path, onerror=onerr)


def build_scene(name, script, chars, audio=None):
    """把脚本表变成 Scene（两幕共用同一段逻辑，避免两份代码走偏）"""
    s = Scene(name, 'story')
    s.clips = []
    for t, kind, a, b, props in script:
        if kind == 'bg':
            s.clips.append(Clip('bg', t, 6.0, 'show', 'assets/bg/' + b, {'trans': 'fade'}))
        elif kind == 'char':
            pos = props.get('pos', 'left')
            tid = {'left': 'char_1', 'center': 'char_3', 'right': 'char_2'}[pos]
            if not s.track(tid):
                while len(s.tracks_of('char1')) < (3 if pos == 'center' else 2):
                    s.add_track('char1')
            cp = dict(props)
            cp['action'] = a
            s.clips.append(Clip(tid, t, 6.0, '', b, cp))
        elif kind == 'say':
            c = next((x for x in chars if x.id == a), None)
            s.clips.append(Clip('text', t, 2.4, 'say', a,
                                {'text': b, 'voice': 'auto', 'wait': 'key',
                                 'style': 'narrate' if a == 'narrate' else 'say',
                                 'speaker': c.name if c else ''}))
    end = max(c.start + c.dur for c in s.clips)

    # ---- 音频（P6）----
    # 语音贴在每句对话上（只给前两句配，够验证"语音和台词对齐"就行）
    if audio:
        says = [c for c in s.clips if c.track == 'text' and c.ref != 'narrate']
        for i, clip in enumerate(says[:2]):
            rel = audio['voice'][i % len(audio['voice'])]
            s.clips.append(Clip('voice', clip.start, 2.0, 'play', rel, {'auto': True}))
        # BGM 铺满整幕，循环
        s.clips.append(Clip('bgm', 0.0, end, 'play', audio['bgm'],
                            {'loop': True, 'fade': 0.5}))
        # 音效放在中间某句，验证"音效抢占 BGM 再恢复"
        if len(says) > 2:
            s.clips.append(Clip('se', says[2].start, 0.3, 'play', audio['se'],
                                {'volume': 1.0}))

    for c in s.clips:                      # 背景铺到内容末尾，避免超长的背景条
        if c.track == 'bg':
            c.dur = max(1.0, end - c.start)
    s.duration = end
    return s


def build_project(out_dir, name='魔女与少女'):
    proj_dir = os.path.join(out_dir, name)
    if os.path.isdir(proj_dir):
        _force_rm(proj_dir)
    os.makedirs(proj_dir)
    A.ensure_dirs(proj_dir)

    # ---- 1. 拷素材（先都放成未分类，再"手动归类"，走的就是用户在界面上走的那条路）
    gfx = os.path.join(ROOT, 'assets_src', 'images')
    test_dir = os.path.join(ROOT, 'assets_src', 'test')
    imported = []
    for src, kind, dest in SOURCES:
        s = os.path.join(test_dir if src in TEST_SOURCES else gfx, src)
        if not os.path.isfile(s):
            print('  ⚠ 缺素材 %s，跳过（测试素材先跑 tools/make_test_assets.py）' % src)
            continue
        # 按目标名导入（背景用中文名，立绘用表情名 normal.png）
        want = dest if isinstance(dest, str) else dest[1]
        ok, bad, notes = A.import_files(proj_dir, [s], rename=lambda _f, w=want: w)
        if not ok:
            print('  ⚠ 导入失败 %s：%s' % (src, bad))
            continue
        rel = ok[0]
        if kind == 'bg':
            new_rel, err = A.classify_asset(proj_dir, _fake(rel), 'bg')
            print('  归类 背景 → %s' % new_rel)
        elif kind == 'char':
            char_name, pose = dest
            new_rel, err = A.classify_asset(proj_dir, _fake(rel), 'char', char_name)
            print('  归类 立绘 %s/%s → %s' % (char_name, pose, new_rel))
        elif kind == 'sprite':
            # **精灵帧也要归类** ✗
            # 原来这里只有 bg / char 两个分支 ✓ 其它一律"保持未分类" ✗
            # 于是 5 张 player_*.png 进了工程却是未分类 ✓
            # 精灵模式的可选素材就少了 ✓（测试改成现场生成时才暴露 ✓）
            new_rel, err = A.classify_asset(proj_dir, _fake(rel), 'sprite')
            print('  归类 精灵 → %s' % new_rel)
        else:
            new_rel = rel
            print('  保持未分类：%s' % os.path.basename(rel))
        imported.append(new_rel)

    # ---- 2. 角色表（id 供剧本引用；名字给玩家看）
    chars = [Character('witch', '魔女', '#ffd166', 'witch_', ['normal']),
             Character('girl', '少女', '#8ecae6', 'girl_', ['normal']),
             Character('golem', '石人', '#b0a89e', 'golem_', ['normal'])]

    # ---- 2.5 音频（P6）：按类型导入，转换工具只认 WAV
    audio_dir = os.path.join(ROOT, 'assets_src', 'test')
    audio = None
    got = {'voice': [], 'bgm': '', 'se': ''}
    for src, kind, dest in AUDIO_SOURCES:
        s = os.path.join(audio_dir, src)
        if not os.path.isfile(s):
            print('  ⚠ 缺音频 %s，跳过（先跑 tools/make_test_audio.py）' % src)
            continue
        ok, bad, _ = A.import_files(proj_dir, [s], kind=kind,
                                    rename=lambda _f, w=dest: w)
        if not ok:
            print('  ⚠ 音频导入失败 %s：%s' % (src, bad))
            continue
        print('  归类 音频 %-5s → %s' % (kind, ok[0]))
        if kind == 'voice':
            got['voice'].append(ok[0])
        else:
            got[kind] = ok[0]
    if got['bgm'] or got['voice'] or got['se']:
        audio = got

    # ---- 3. 时间轴（两幕）
    scenes = [build_scene('序章', SCRIPT, chars, audio),
              build_scene('第二幕', SCRIPT2, chars, audio)]

    # ---- 4. 存盘
    proj = Project(name=name)
    proj.characters = chars
    proj.scenes = scenes
    proj.settings['rom_name'] = 'gba_ai'
    proj.assets, issues = A.scan_folder(proj_dir, {})
    path = os.path.join(proj_dir, name + '.gbastudio')
    proj.save(path)
    return path, proj_dir, proj, issues


class _fake:
    """classify_asset 需要的是"有 .path 的对象"，这里包一下相对路径"""
    def __init__(self, path):
        self.path = path
        self.kind = ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, 'samples'))
    ap.add_argument('-n', '--name', default='魔女与少女')
    a = ap.parse_args()

    print('生成样品工程…')
    path, proj_dir, proj, issues = build_project(a.out, a.name)
    print('')
    print('项目文件：%s' % path)
    print('项目目录：%s' % proj_dir)
    print('素材：%d 个（其中未分类 %d 个）'
          % (len(proj.assets), len([x for x in proj.assets if not x.kind])))
    for sc in proj.scenes:
        print('场景 %-6s 片段 %2d 个，台词 %d 句'
              % (sc.name, len(sc.clips),
                 len([c for c in sc.clips if c.track == 'text'])))
    for i in issues[:5]:
        print('  %s' % i)
    print('')
    print('下一步：双击「启动编辑器」→ 打开这个 .gbastudio → 点「导出 GBA」')


if __name__ == '__main__':
    main()
