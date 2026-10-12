

# -*- coding: utf-8 -*-
"""功能测试：新建项目目录结构 / 导入 / 扫描 / 导出 / 片段增删切"""
import os
import shutil
import sys
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from core import assets as A
from core.project import Project, Scene, Clip, new_project, Character


def find_test_png(n=2):
    """找几张现成的 PNG 当测试素材（不写死路径，挪目录也不会挂）"""
    hits = []
    for d in ('docs/screenshots', 'assets_src/images', 'assets_src/test'):
        full = os.path.join(ROOT, d.replace('/', os.sep))
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if f.lower().endswith('.png'):
                hits.append(os.path.join(full, f))
                if len(hits) >= n:
                    return hits
    return hits

tmp = r'D:\GitHud\GBA_AI\.tmp\gba2test'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
print('测试目录:', tmp)

# ---------------- 1. 新建项目：目录结构 ----------------
proj_dir = os.path.join(tmp, '测试游戏')
os.makedirs(proj_dir)
made = A.ensure_dirs(proj_dir)
print('\n1) 新建项目建目录:', made)
for sub in ('bg', 'char', 'bgm', 'voice', 'se'):
    p = os.path.join(proj_dir, 'assets', sub)
    assert os.path.isdir(p), '缺目录 ' + sub
print('   5 个素材目录都建好了 ✓')

p = new_project('测试游戏')
path = os.path.join(proj_dir, '测试游戏.gbastudio')
p.save(path)
print('   项目文件已保存:', os.path.basename(path), os.path.getsize(path), 'B')

# ---------------- 2. 导入素材 ----------------
srcs = find_test_png(2)
ok, bad, notes = A.import_files(proj_dir, srcs, kind='bg')
print('\n2) 导入背景:', ok, '失败:', bad)
assert len(ok) == 2 and not bad

# 重名导入应当自动改名
ok2, bad2, notes2 = A.import_files(proj_dir, srcs, kind='bg')
print('   再次导入同名文件:', ok2, '| 提示:', notes2)
assert '_2' in (ok2[0] if ok2 else ''), '重名没有自动改名'

# 立绘导入到角色目录
ok3, _, notes3 = A.import_files(proj_dir, [srcs[0]], kind='char', character='魔女')
print('   立绘导入:', ok3)
assert ok3 and 'char/魔女/' in ok3[0].replace('\\', '/')

# ---------------- 3. 扫描资源库 ----------------
found, issues = A.scan_folder(proj_dir)
kinds = {}
for a in found:
    kinds[a.kind] = kinds.get(a.kind, 0) + 1
print('\n3) 扫描结果:', kinds, '| 问题:', len(issues))
assert kinds.get('bg') == 4 and kinds.get('char') == 1, kinds

# ---------------- 4. 合规检查 ----------------
p.assets = found
iss = A.check_project(p)
print('\n4) 合规检查:', len(iss), '条')
for i in iss[:4]:
    print('   ', i)

# ---------------- 5. 导出素材 ----------------
out = os.path.join(tmp, '导出')
n, bad = A.export_assets(proj_dir, out, found)
print('\n5) 导出素材: %d 个成功, %d 个失败' % (n, len(bad)))
assert n == len(found)
sub = os.listdir(os.path.join(out, 'bg'))
print('   导出目录 bg/ 里有:', len(sub), '个文件 ✓')

# ---------------- 6. 片段增删切（纯数据逻辑） ----------------
s = Scene('测试场景', 'story')
s.clips = [Clip('text', 1.0, 4.0, 'say', 'witch', {'text': '第一句'})]
c = s.clips[0]
# 切开
t = 2.5
left = Clip(c.track, c.start, t - c.start, c.kind, c.ref, dict(c.props))
right = Clip(c.track, t, c.start + c.dur - t, c.kind, c.ref, dict(c.props))
s.clips = [left, right]
print('\n6) 切开片段: %.1f+%.1f = %.1f 秒（原 %.1f 秒）'
      % (left.dur, right.dur, left.dur + right.dur, c.dur))
assert abs((left.dur + right.dur) - c.dur) < 1e-6
# 删除：按 id 删，**只该删掉那一个**
s.clips = [x for x in s.clips if x.id != left.id]
print('   删除 left 后剩:', len(s.clips), '个片段（right 还在才对）')
assert len(s.clips) == 1 and s.clips[0].id == right.id, \
    '按 id 删除误伤了别的片段 —— 检查 id 是不是重复了'
# 顺带确认所有片段 id 唯一（早期版本在 Windows 上会全部撞车，
# 结果是"删一个删一串、台词和语音关联对错人"）
ids = [x.id for x in s.clips]
assert len(ids) == len(set(ids)), '片段 id 有重复: %s' % ids

# ---------------- 7. 存档往返（含新片段） ----------------
p.scenes = [s]
p.save(path)
p2 = Project.load(path)
print('\n7) 存档往返: 场景 %d 个, 片段 %d 个, 角色 %d 个'
      % (len(p2.scenes), len(p2.scenes[0].clips), len(p2.characters)))
assert len(p2.scenes[0].clips) == 1
assert p2.scenes[0].clips[0].id == right.id, '存档没保住片段 id'

shutil.rmtree(tmp, ignore_errors=True)
print('\n✅ 全部功能测试通过（测试目录已清理）')
