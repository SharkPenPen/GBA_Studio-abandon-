# -*- coding: utf-8 -*-
"""
level.py —— 关卡地图的数据模型

一个关卡就是"格子地图 + 出生点"，故意做得很小：

    cells[ty][tx] = 图块编号（0=地板 1=墙 2=草 3=水）

**为什么不做图块自动拼接、图层、对象层**：那些等真的需要第二张地图时再说。
现在最要紧的是把"编辑器画的地图 → 引擎认的数据"这条路打通 ——
路通了，加功能就是往两边各加一点。
"""
import os

# 图块编号 ↔ 名字 ↔ 存盘字符
TILE_NAMES = {0: '地板', 1: '墙', 2: '草', 3: '水'}
TILE_CHARS = {0: '.', 1: '#', 2: 'g', 3: '~'}
CHAR_TILES = {v: k for k, v in TILE_CHARS.items()}
TILE_COLORS = {0: '#2a2a30', 1: '#6e6a78', 2: '#2e6b32', 3: '#24418c'}

SOLID = (1, 3)              # 走不过去的图块

DEFAULT_ROWS = [
    '###############',
    '#.............#',
    '#....##.......#',
    '#....##..~~~..#',
    '#........~~~..#',
    '#..gg....~~~..#',
    '#..gg.........#',
    '#....##.......#',
    '#....##.......#',
    '###############',
]

MAX_W, MAX_H = 30, 20        # 再大就得做镜头滚动了（引擎还没做）


class Level:
    def __init__(self, w=15, h=10, cells=None, start=(1, 1)):
        self.w = int(w)
        self.h = int(h)
        self.cells = cells or [[0] * self.w for _ in range(self.h)]
        self.start = tuple(start)

    # ------------------------------------------------------------ 构造
    @staticmethod
    def default():
        rows = DEFAULT_ROWS
        cells = [[CHAR_TILES.get(c, 0) for c in r] for r in rows]
        return Level(len(rows[0]), len(rows), cells, (1, 1))

    # ------------------------------------------------------------ 编辑
    def in_range(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h

    def get(self, tx, ty):
        return self.cells[ty][tx] if self.in_range(tx, ty) else 1

    def set(self, tx, ty, tile):
        if self.in_range(tx, ty):
            self.cells[ty][tx] = int(tile)

    def paint(self, tx, ty, tile):
        """画一格；如果画的是出生点所在的格子，出生点自动挪开"""
        self.set(tx, ty, tile)
        if tuple(self.start) == (tx, ty) and tile in SOLID:
            self.move_start_to_free()

    def move_start_to_free(self):
        for ty in range(self.h):
            for tx in range(self.w):
                if self.cells[ty][tx] not in SOLID:
                    self.start = (tx, ty)
                    return True
        return False

    def clear(self, tile=0):
        self.cells = [[tile] * self.w for _ in range(self.h)]

    def resize(self, w, h, fill=0):
        w = max(5, min(MAX_W, int(w)))
        h = max(5, min(MAX_H, int(h)))
        old = self.cells
        self.cells = [[fill] * w for _ in range(h)]
        for ty in range(min(h, len(old))):
            for tx in range(min(w, len(old[ty]))):
                self.cells[ty][tx] = old[ty][tx]
        self.w, self.h = w, h
        # 四周围一圈墙：地图总得有个边，不然角色会走出屏幕
        for tx in range(w):
            self.cells[0][tx] = 1
            self.cells[h - 1][tx] = 1
        for ty in range(h):
            self.cells[ty][0] = 1
            self.cells[ty][w - 1] = 1
        if not self.in_range(*self.start) or self.get(*self.start) in SOLID:
            self.move_start_to_free()

    # ------------------------------------------------------------ 存档
    def to_dict(self):
        return {'w': self.w, 'h': self.h,
                'start': list(self.start),
                'cells': self.cells}

    @staticmethod
    def from_dict(d):
        if not d:
            return Level.default()
        return Level(d.get('w', 15), d.get('h', 10),
                     d.get('cells'), tuple(d.get('start', (1, 1))))

    # ------------------------------------------------------------ 文本
    def to_text(self):
        """
        导出给人看的 level.txt（引擎不读它，是编译脚本读）。

        **注释用 `;` 不用 `#`** —— 因为墙的字符就是 `#`，
        用 `#` 当注释符会把整张地图都当成注释跳掉（第一次就是这么写的，
        结果解析出空地图、悄悄回退到默认地图，测试还"通过"了）。
        """
        out = ['; 关卡地图（编辑器「关卡」模式生成）',
               '; 字符：. 地板   # 墙   g 草   ~ 水',
               '; 出生点 %d %d' % (self.start[0], self.start[1])]
        for ty in range(self.h):
            out.append(''.join(TILE_CHARS.get(self.cells[ty][tx], '.')
                               for tx in range(self.w)))
        return '\n'.join(out) + '\n'

    @staticmethod
    def from_text(text):
        start = (1, 1)
        rows = []
        for line in text.splitlines():
            s = line.rstrip()
            if s.startswith(';'):                 # 注释
                if '出生点' in s:
                    nums = [int(x) for x in s.replace('出生点', ' ').split()
                            if x.lstrip('-').isdigit()]
                    if len(nums) >= 2:
                        start = (nums[0], nums[1])
                continue
            if s:
                rows.append(s)
        if not rows:
            return Level.default()
        w = max(len(r) for r in rows)
        cells = [[CHAR_TILES.get(c, 0) for c in r.ljust(w, '.')] for r in rows]
        return Level(w, len(rows), cells, start)

    def load(self, path):
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                other = Level.from_text(f.read())
            self.w, self.h = other.w, other.h
            self.cells, self.start = other.cells, other.start
            return True
        return False

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(self.to_text())
        return path
