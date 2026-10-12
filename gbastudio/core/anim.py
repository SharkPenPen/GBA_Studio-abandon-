# -*- coding: utf-8 -*-
"""
anim.py —— 精灵动画的数据模型（P9）

一个动画就是"一串帧 + 每帧停几帧"：

    走路:  [walk0 停6帧] → [walk1 停6帧] → [walk2 停6帧] → [walk1 停6帧] → 循环
    待机:  [idle 停30帧] → 循环

**为什么不做精灵表（sprite sheet）**：
    精灵表要把好几帧拼进一张图、再记每帧的矩形，省的是 ROM 空间。
    现在 ROM 才 500 KB（上限 32 MB），空间一点都不紧张，
    而分开的 PNG 在编辑器里**直接能看**、能单独换、能单独调色 ——
    先要的是顺手，不是省字节。等哪天真放不下了再合并（那时也是编译期自动合）。
"""
import os


class AnimFrame:
    def __init__(self, path='', dur=6):
        self.path = path            # 相对工程目录的素材路径
        self.dur = int(dur)         # 这一帧停多少帧（60 帧 = 1 秒）

    def to_dict(self):
        return {'path': self.path, 'dur': self.dur}

    @staticmethod
    def from_dict(d):
        return AnimFrame(d.get('path', ''), d.get('dur', 6))


class Animation:
    def __init__(self, name='新动画', frames=None, loop=True, aid=None):
        from core.project import new_id
        self.id = aid or new_id('a')
        self.name = name
        self.loop = bool(loop)
        self.frames = list(frames or [])

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'loop': self.loop,
                'frames': [f.to_dict() for f in self.frames]}

    @staticmethod
    def from_dict(d):
        return Animation(d.get('name', '新动画'),
                         [AnimFrame.from_dict(f) for f in d.get('frames', [])],
                         d.get('loop', True), d.get('id'))

    # ------------------------------------------------------------ 编辑
    def add_frame(self, path, dur=6, at=None):
        f = AnimFrame(path, dur)
        if at is None:
            self.frames.append(f)
        else:
            self.frames.insert(max(0, min(len(self.frames), at)), f)
        return f

    def remove_frame(self, i):
        if 0 <= i < len(self.frames):
            return self.frames.pop(i)
        return None

    def move_frame(self, i, delta):
        j = i + delta
        if 0 <= i < len(self.frames) and 0 <= j < len(self.frames):
            self.frames[i], self.frames[j] = self.frames[j], self.frames[i]
            return True
        return False

    def total_frames(self):
        return sum(max(1, f.dur) for f in self.frames)


# ---------------------------------------------------------------------------
# 工程里默认带两个动画（用测试精灵帧）
#
# 为什么默认就带：编辑器一打开「精灵」模式就能看到东西、能点播放 ——
# 空面板学不到东西。用户把自己的帧导入后改这两个（或者删掉重建）即可。
# ---------------------------------------------------------------------------
DEFAULT_SPRITE_DIR = 'assets/sprite'


def default_animations():
    def p(n):
        return '%s/%s.png' % (DEFAULT_SPRITE_DIR, n)

    walk = Animation('走路', loop=True)
    for n, d in (('player_walk0', 6), ('player_walk1', 6),
                 ('player_walk2', 6), ('player_walk1', 6)):
        walk.add_frame(p(n), d)
    idle = Animation('待机', loop=True)
    idle.add_frame(p('player_idle'), 30)
    return [walk, idle]


def animations_of(project, kind=None):
    """取工程里的动画；kind='walk'/'idle' 之类按名字找是调用方的事"""
    return list(getattr(project, 'animations', []) or [])


def find(project, name):
    for a in animations_of(project):
        if a.name == name:
            return a
    return None
