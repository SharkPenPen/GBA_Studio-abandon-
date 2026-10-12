
import os
import sys, os, time
# 从文件位置推导工程根目录（不写死绝对路径，工程挪到哪都能跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(ROOT, 'gbastudio'))
from core.project import Project
from core import compiler, gba_build

from _sample import SAMPLE   # 现场生成的夹具，不再依赖仓库里的 samples/
p = Project.load(SAMPLE)
pd = os.path.dirname(SAMPLE)
text, notes, mani = compiler.compile_project(p, pd)
proj = gba_build.find_gba_project()
t0 = time.time()
ok, rom = gba_build.export_rom(proj, text, 'gba_ai', log=lambda s: print("  " + str(s)),
                               manifest=mani)
print()
print("  耗时 %.1f 秒  结果=%s  %s" % (time.time()-t0, ok, rom))
sys.exit(0 if ok else 1)
