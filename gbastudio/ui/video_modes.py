# -*- coding: utf-8 -*-
"""
video_modes.py —— GBA 六种显示模式：说明文字 + 示意图

【为什么需要这个文件】
"选显示模式"这件事，光给个下拉框是没用的 —— 用户不知道
"模式 0 和模式 3 到底差在哪"。而这两者的差别**不是性能高低，
是能做什么**：

    模式 0/1/2  给你**图块层**：地图/UI 省显存、能滚动、能旋转，
                但**没有位图层** —— 相机照片那种整屏彩色图放不进去
    模式 3/4/5  给你**位图层**：整屏任意颜色随便画，
                但**没有图块层** —— 没有硬件滚动、没有图层叠加

**位图和图块不能混用**（硬件就是这样），所以这个选择会影响整个项目。
更要紧的是：**中文文字**（11 像素点阵混排）只能在位图模式下正常显示，
图块模式的 8x8 网格塞不下 11 像素的字 —— 这一点必须在选之前说清楚。

每种模式给六样东西：
    图层清单 / 特效清单 / **容量账**（几个图块、多少颜色、多少显存）
    / **典型用法**（真机游戏怎么用的）/ 适合 / 代价
再加一张**画出来的**示意图（QPainter，不是素材图 —— 改文案不用重做图）。
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtWidgets import QWidget

# 界面配色（和编辑器其它地方一致）
C_BG = '#101014'
C_PANEL = '#1b1b24'
C_LINE = '#3a3a48'
C_TEXT = '#c8c8d4'
C_DIM = '#8a8a99'
C_ACCENT = '#ffb703'

# 图层类型的颜色：一眼区分"能滚动"和"能旋转"
C_TILE = '#3d6ea8'      # 普通图块层（能滚动）
C_AFFINE = '#8a5cc4'    # 仿射层（能旋转缩放）
C_BITMAP = '#2f7d5b'    # 位图层（任意颜色）
C_OBJ = '#c4741f'       # 精灵层


class ModeInfo:
    """一种显示模式的全部说明"""

    def __init__(self, m, title, tagline, layers, effects, budget, cases,
                 good, cost, layers_kind, screen='240x160',
                 colors='', obj=True):
        self.m = m                    # 模式号 0..5
        self.title = title
        self.tagline = tagline        # 一句话：它是什么
        self.layers = layers          # [(名字, 说明, 类型)] 类型用于画示意图
        self.effects = effects        # [(特性, 说明)]
        self.budget = budget          # [(项目, 数值)] 容量账
        self.cases = cases            # 典型用法（真机游戏怎么用的）
        self.good = good              # 适合做什么
        self.cost = cost              # 代价
        self.layers_kind = layers_kind  # 'tile' / 'bitmap'
        self.screen = screen
        self.colors = colors
        self.obj = obj


MODES = [
    ModeInfo(
        0, '模式 0 · 四个图块层',
        '最多图层：4 个能独立滚动的图块层，没有旋转缩放',
        layers=[('BG0', '图块层，4 或 8bpp', 'tile'),
                ('BG1', '图块层，4 或 8bpp', 'tile'),
                ('BG2', '图块层，只能 4bpp', 'tile'),
                ('BG3', '图块层，只能 4bpp', 'tile'),
                ('OBJ', '硬件精灵，128 个 / 每行 32 个', 'obj')],
        effects=[('硬件滚动', '支持：每层有独立的滚动寄存器，绕回是硬件行为，不花 CPU'),
                 ('旋转/缩放', '没有：想转只能每帧重传图块，代价极大'),
                 ('图层叠加', '支持：4 层 + 精灵，各有 0~3 优先级'),
                 ('颜色特效', '支持：整体马赛克、淡入淡出、亮度/对比度混合'),
                 ('双缓冲', '支持：改图块数据即可，不涉及整屏拷贝')],
        budget=[('图块显存', '64 KB = 2048 个 4bpp 图块，或 1024 个 8bpp 图块'),
                ('每层地图', '2 KB（32x32 格）~ 8 KB（64x64 格）'),
                ('颜色', '4bpp 每块 16 色（16 组可选）；8bpp 每层 256 色'),
                ('滚动开销', '0 周期（硬件做）；改一屏图块 = 搬 600 格')],
        cases='商业 GBA 游戏最常见的模式：战棋/策略的地图 + 光标 + 数值面板'
              '（如《Advance Wars》）、RPG 的野外 + 对话框 + 状态栏'
              '（如《黄金太阳》的菜单层）都是"多层图块各管一摊"。',
        good='地图类玩法：多层视差背景、HUD、菜单。省显存、滚动不花 CPU。',
        cost='没有位图层：整屏照片/大图放不进去 —— 图块网格固定 8x8，'
             '一张 240x160 的彩色图要拆成 600 个互不相同的图块，'
             '而且 4bpp 每块只有 16 色。',
        layers_kind='tile', colors='每层 256 色（4bpp 时 16 色一组）',
    ),
    ModeInfo(
        1, '模式 1 · 两层图块 + 一层旋转',
        '最常用的组合：两层图块 + 一层能旋转缩放的背景',
        layers=[('BG0', '图块层，可滚动', 'tile'),
                ('BG1', '图块层，可滚动', 'tile'),
                ('BG2', '**仿射层**：旋转缩放', 'affine'),
                ('OBJ', '硬件精灵', 'obj')],
        effects=[('硬件滚动', '支持：BG0/BG1 独立滚动；BG2 用参考点移动'),
                 ('旋转/缩放', '支持：BG2 一层，PA/PB/PC/PD 矩阵 + 参考点'),
                 ('图层叠加', '支持：3 层 + 精灵'),
                 ('环绕', 'BG2 可选：地图边界绕回，做无缝地形很省事'),
                 ('双缓冲', '支持')],
        budget=[('图块显存', '64 KB：普通层 4bpp/8bpp，仿射层 4bpp/8bpp'),
                ('仿射层地图', '16x16 ~ 128x128 格（128x128 像素 ~ 1024x1024）'),
                ('仿射层图块数', '**最多 256 个**（仿射地图条目只有 1 字节）'),
                ('颜色', '普通层每层 256 色；仿射层 256 色')],
        cases='有"会转的背景"的玩法最常用它：《马里奥赛车 Advance》的赛道、'
              '《F-Zero》系列的地面、各种伪 3D 赛车/飞行游戏 ——'
              '两层图块管 HUD 和天空，仿射层管会转的地面。',
        good='有"会转的背景"的玩法：转盘、雷达、伪 3D 地面、地图旋转。',
        cost='可用的普通图块层少了一层（HUD 和场景要挤在两个层里）；同样没有位图层。',
        layers_kind='tile', colors='256 色（4bpp 时 16 色一组）',
    ),
    ModeInfo(
        2, '模式 2 · 两层都能旋转',
        '两个仿射层：两层背景各自独立旋转缩放',
        layers=[('BG2', '**仿射层**：旋转缩放', 'affine'),
                ('BG3', '**仿射层**：旋转缩放', 'affine'),
                ('OBJ', '硬件精灵', 'obj')],
        effects=[('硬件滚动', '不支持：没有普通图块层，位移只能靠挪参考点'),
                 ('旋转/缩放', '支持：两层各自独立的矩阵'),
                 ('图层叠加', '支持：2 层 + 精灵（靠优先级排序）'),
                 ('环绕', '两层都可选'),
                 ('双缓冲', '支持')],
        budget=[('图块显存', '64 KB 两层分，**每层最多 256 个图块**'),
                ('每层地图', '16x16 ~ 128x128 格'),
                ('图块上限', '每层 256 个 —— 这是仿射层的硬限制'),
                ('颜色', '每层 256 色')],
        cases='真机上很少见 —— 因为它**没有普通图块层**，连个固定不动的 HUD 都画不了。'
              '一般只在"两层都要转"的特效场面用（旋转的天空 + 旋转的地面）；'
              '多数游戏宁可用模式 1 加精灵凑。',
        good='两层都要转的效果：旋转的地面 + 旋转的天空、双层视差旋转。',
        cost='**没有普通图块层** —— 想画个不旋转的 HUD 只能用精灵（128 个上限）'
             '或状态栏窗口。仿射层图块上限 256 个/层。',
        layers_kind='tile', colors='256 色',
    ),
    ModeInfo(
        3, '模式 3 · 整屏位图（32768 色）',
        '一块 240x160 的 16 位直接色画布：想画什么画什么',
        layers=[('BG2', '**位图层**：240x160、16bpp', 'bitmap'),
                ('OBJ', '硬件精灵（图块显存只剩 16KB）', 'obj')],
        effects=[('硬件滚动', '不支持：位图没有滚动寄存器，滚动 = 把画面整体搬 N 像素'),
                 ('旋转/缩放', '不支持（要自己逐像素算）'),
                 ('图层叠加', '不支持：只有一层背景，叠东西靠软件逐像素写上去'),
                 ('颜色特效', '支持：整体马赛克、淡入淡出、亮度混合'),
                 ('双缓冲', '**做不到**：一块画布 76,800 字节，96KB 显存装不下第二块')],
        budget=[('画布大小', '240x160x2 = **76,800 字节**（比 BG 图块区 64KB 还大，'
                            '所以借用了精灵图块区的一半）'),
                ('精灵图块显存', '**只剩 16 KB**（0x06014000 起）'),
                ('颜色', '32768 色（每通道 32 级直接色，不需要调色板）'),
                ('滚动开销', '整屏 DMA 拷贝 ≈ 2 万周期 ≈ 一帧的 7%（实测可用）')],
        cases='需要"整屏任意颜色"的场合：照片级背景、绘画风格画面、'
              '以及**大量文字的界面**（排版不受 8 像素网格限制）。'
              '不少 GBA 文字冒险/桌游/解谜游戏的标题与剧情画面用它。',
        good='**剧情/文字类**：中文点阵混排、照片级背景、任意像素效果。',
        cost='只有一层背景、不能滚动、单缓冲（改显存时画面可能撕裂，'
             '要用 VBlank 或淡入淡出遮住）；精灵图块显存减半。',
        layers_kind='bitmap', colors='32768 色（每通道 32 级）',
    ),
    ModeInfo(
        4, '模式 4 · 整屏位图（256 色，可翻页）',
        '8bpp 位图 + **两个页面**：唯一能真正双缓冲的模式',
        layers=[('BG2', '**位图层**：240x160、8bpp，两个页面', 'bitmap'),
                ('OBJ', '硬件精灵（图块显存 16KB）', 'obj')],
        effects=[('硬件滚动', '不支持（同模式 3）'),
                 ('旋转/缩放', '不支持'),
                 ('图层叠加', '不支持'),
                 ('翻页', '**支持**：画在背面那页，画完一次翻过去'),
                 ('双缓冲', '**支持** —— 六种模式里唯一真正做到的')],
        budget=[('每页大小', '240x160x1 = 38,400 字节；两页共 76,800 字节（正好塞得下）'),
                ('页面间隔', '**0xA000（40,960）字节**，不是 38,400 —— 硬件按页对齐'),
                ('颜色', '256 色（背景 + 文字共用一张调色板；精灵另有自己的 256 色）'),
                ('精灵图块显存', '16 KB')],
        cases='逐帧重绘全屏的玩法：伪 3D、粒子、水面/火焰这类逐像素特效。'
              '好处是**永远不会看到半张画**（画在背面页）。'
              '有些赛车/射击游戏用它做全屏特效层。',
        good='逐帧重绘全屏的玩法：伪 3D、粒子、逐像素特效。',
        cost='**颜色降到 256 色**（背景+立绘+文字共用一个调色板），'
             '照片会出色带；同样没有图块层。',
        layers_kind='bitmap', colors='256 色（调色板）',
    ),
    ModeInfo(
        5, '模式 5 · 小屏位图（160x128）',
        '和模式 3 一样是 16bpp 位图，但画面只有 160x128',
        layers=[('BG2', '**位图层**：160x128、16bpp', 'bitmap'),
                ('OBJ', '硬件精灵（图块显存 16KB，和模式 3/4 一样）', 'obj')],
        effects=[('硬件滚动', '不支持'),
                 ('旋转/缩放', '不支持'),
                 ('图层叠加', '不支持'),
                 ('双缓冲', '不支持（只有一页）'),
                 ('颜色特效', '支持：和模式 3 相同')],
        budget=[('画布大小', '160x128x2 = **40,960 字节**（只有模式 3 的 53%）'),
                ('到屏幕边缘', 'GBA 屏幕固定 240x160，**四周会留空**：'
                              '左右各 40 像素、上下各 16 像素'),
                ('颜色', '32768 色（同模式 3）'),
                ('CPU 开销', '每帧要写的像素只有模式 3 的 53%，'
                            '软件绘制的玩法能明显快一截')],
        cases='用不满整屏的小场面：小窗解谜、棋盘类玩法，'
              '以及"想省 CPU"的逐像素特效（面积小一半，随便算）。'
              '留空部分常用纯色背景或精灵边框补上。',
        good='用不满整屏的场景：小窗游戏、棋盘/方格玩法，少画像素 = 省 CPU。',
        cost='画面四周留空（左右各 40、上下各 16 像素），要自己用背景色或精灵填满；'
             '同样没有图块层。',
        layers_kind='bitmap', screen='160x128', colors='32768 色',
    ),
]

MODE_BY_N = {m.m: m for m in MODES}


# ---------------------------------------------------------------------------
# 示意图：把图层堆叠画出来
# ---------------------------------------------------------------------------
class ModeDiagram(QWidget):
    """一种显示模式的图层示意图。

    画法（一眼看出结构差别）：
        · 一个"屏幕"方框（模式 5 是 160x128，画得明显小一圈）
        · 图块层画成**带格子纹理的横条**（格子 = 8x8 图块网格）
        · 仿射层画成**斜的横条 + 旋转弧**（表示能旋转）
        · 位图层画成**一块实心画布**（带彩色条纹，表示任意颜色）
        · 精灵画成一个小方块，浮在最上面
    """

    def __init__(self, mode=None, parent=None):
        super().__init__(parent)
        self.mode = mode or MODES[0]
        # 高度按"屏幕框 + 底部颜色说明"算，别让控件撑满整列 ——
        # 撑满的话下面会留一大片黑，看着像没画完
        # 允许收窄：窗口小的时候自动变窄（paintEvent 按 self.width() 算 ✓）
        self.setMinimumWidth(180)
        self.setMaximumWidth(320)
        self.setMinimumHeight(200)
        self.setFixedHeight(232)

    def set_mode(self, mode):
        self.mode = mode
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(C_BG))

        info = self.mode
        W = self.width()
        sw, sh = 240, 160
        if info.screen.startswith('160'):
            sw, sh = 160, 128
        scr_w = min(W - 24, 240) * (sw / 240.0)
        scr_h = scr_w * sh / float(sw)
        x0 = 12
        y0 = 30

        p.setPen(QColor(C_DIM))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        p.drawText(x0, y0 - 8, '屏幕 %s' % info.screen)

        p.setPen(QPen(QColor(C_LINE), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x0, y0, scr_w, scr_h))
        # **裁剪在屏幕框内**：仿射层是斜着画的，不裁会画出框、压到右边的说明文字
        p.save()
        p.setClipRect(QRectF(x0, y0, scr_w, scr_h))

        rows = info.layers
        n_back = sum(1 for _, _, k in rows if k in ('tile', 'affine', 'bitmap'))
        if n_back <= 0:
            n_back = 1
        h = scr_h / float(n_back)
        y = y0
        for name, desc, kind in rows:
            if kind == 'obj':
                continue
            rect = QRectF(x0, y, scr_w, h)
            if kind == 'bitmap':
                # 位图：实心块 + 彩色条纹，表示"想画什么画什么"
                g = QColor(C_BITMAP)
                p.setBrush(QBrush(g))
                p.setPen(QPen(g.lighter(150), 1))
                p.drawRect(rect)
                p.setPen(Qt.NoPen)
                for i in range(6):
                    t = i / 5.0
                    col = QColor(int(40 + 120 * t), int(120 + 60 * (1 - t)),
                                 int(160 - 60 * t))
                    col.setAlpha(90)
                    p.setBrush(QBrush(col))
                    p.drawRect(QRectF(rect.x() + rect.width() * i / 6.0, rect.y(),
                                      rect.width() / 6.0,
                                      rect.height() * (0.35 + 0.5 * t)))
            elif kind == 'affine':
                # 仿射：斜条 + 旋转弧（表示能转）
                p.save()
                p.translate(rect.center())
                p.rotate(-12)
                r2 = QRectF(-rect.width() / 2, -rect.height() / 2,
                            rect.width(), rect.height())
                col = QColor(C_AFFINE)
                p.setBrush(QBrush(col))
                p.setPen(QPen(col.lighter(150), 1))
                p.drawRect(r2)
                p.setPen(QPen(QColor('#ffffff'), 1))
                p.setBrush(Qt.NoBrush)
                rr = min(r2.width(), r2.height()) * 0.22
                p.drawArc(QRectF(-rr, -rr, rr * 2, rr * 2), 30 * 16, 240 * 16)
                p.drawLine(QPointF(rr, 0), QPointF(rr * 0.6, -rr * 0.5))
                p.restore()
            else:
                # 图块层：格子纹理
                col = QColor(C_TILE)
                p.setBrush(QBrush(col))
                p.setPen(QPen(col.lighter(150), 1))
                p.drawRect(rect)
                p.setPen(QPen(QColor(255, 255, 255, 40), 1))
                step = rect.width() / 30.0 * 2     # 示意性的 8x8 格
                gx = rect.x()
                while gx < rect.x() + rect.width():
                    p.drawLine(QPointF(gx, rect.y()), QPointF(gx, rect.y() + rect.height()))
                    gx += step
            p.setPen(QColor('#ffffff'))
            f2 = QFont()
            f2.setPointSize(8)
            f2.setBold(True)
            p.setFont(f2)
            p.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignTop | Qt.AlignLeft, name)
            f3 = QFont()
            f3.setPointSize(7)
            p.setFont(f3)
            p.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignBottom | Qt.AlignLeft,
                       desc.replace('**', ''))
            y += h

        p.restore()

        # 精灵：浮在最上面
        if info.obj:
            sw2, sh2 = 14, 18
            sx = x0 + scr_w * 0.12
            sy = y0 + 6
            col = QColor(C_OBJ)
            p.setBrush(QBrush(col))
            p.setPen(QPen(col.lighter(160), 1))
            p.drawRect(QRectF(sx, sy, sw2, sh2))
            p.setPen(QColor('#ffffff'))
            p.setFont(f3)
            p.drawText(QPointF(sx + sw2 + 5, sy + sh2 * 0.7), 'OBJ 精灵')

        # 底部：颜色数
        p.setPen(QColor(C_DIM))
        p.setFont(f)
        p.drawText(QRectF(x0, y0 + scr_h + 6, scr_w, 18), Qt.AlignLeft,
                   '颜色：%s' % info.colors)
        p.end()


# ---------------------------------------------------------------------------
# 模式卡片：左示意图 + 右说明（**切换模式时要整块重建文字**）
# ---------------------------------------------------------------------------
class ModeCard(QWidget):
    """模式卡片。

    **为什么文字部分要能整体重建**（踩过的坑）：
    第一版只做了"换示意图"，切换列表时右边那堆标签**原封不动** ——
    于是不管点哪个模式，看到的都是同一个模式的说明 ✗
    用户看到的现象就是"模式解释只有一种"。

    所以这里把文字放进一个容器，`set_mode()` 时清掉重建 ——
    宁可重建（六种模式加起来也就几十个标签），也不要漏更新某一行。
    """

    def __init__(self, mode=None, parent=None):
        super().__init__(parent)
        self.mode = mode or MODES[0]

        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignTop)

        self.diagram = ModeDiagram(self.mode)
        lay.addWidget(self.diagram, 0, Qt.AlignTop)

        self.text_box = QWidget()
        # **最小宽度要小** ✗
        # 之前这里写 420，加上示意图的 320 和边距 = 卡片最少要 778 像素；
        # 窗口视口只有 576 时整块就溢出 → 出现横向滚动条 → 而且 QLabel
        # 拿到的是"撑开后的宽度"，于是**不换行、文字被截断** ✗
        #（我之前的截图窗口开得大，所以一直没暴露 —— 教训：验收要用用户的窗口尺寸）
        self.text_box.setMinimumWidth(1)
        self.text_lay = QVBoxLayout(self.text_box)
        self.text_lay.setContentsMargins(0, 0, 0, 0)
        self.text_lay.setSpacing(4)
        lay.addWidget(self.text_box, 1)
        self._build_text()

    # ---------------------------------------------------------------- 切换
    def set_mode(self, mode):
        self.mode = mode
        self.diagram.set_mode(mode)
        self._build_text()

    def _clear_text(self):
        while self.text_lay.count():
            it = self.text_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _build_text(self):
        from PySide6.QtWidgets import QLabel
        self._clear_text()
        mode = self.mode

        def plain(s):
            """去掉 ** 粗体标记。

            QLabel 不认 Markdown，漏掉哪个字段就会把 ** 原样显示出来 ✗
            （踩过：特效和容量账那两行忘了剥，界面上直接出现 `**做不到**`）
            所以统一在这里剥一次，而不是在每个字段上各写一遍。
            """
            return (s or '').replace('**', '')

        def add(text, style='color:%s;' % C_TEXT, wrap=True, tip=None):
            lab = QLabel(plain(text))
            lab.setWordWrap(wrap)
            # 允许随容器收缩：只给一个很小的最小宽度，别设固定宽度 ✗
            # （踩过：为了"能收缩"写成 setFixedWidth(1)，结果每个标签都变成
            #   1 像素宽，整列文字看不见了）
            lab.setMinimumWidth(1)
            lab.setStyleSheet(style)
            if tip:
                lab.setToolTip(tip)
            self.text_lay.addWidget(lab)
            return lab

        big = QFont()
        big.setPointSize(12)
        big.setBold(True)
        # 标题也要能换行 ✗ 设成不换行的话，窗口一窄就被切掉
        #（760x560 下"模式 3 · 整屏位图（32768 色）"就被截断了 —— 测试抓到的）
        t = add(mode.title, 'color:#f0f0f6;')
        t.setFont(big)
        add(mode.tagline.replace('**', ''))

        add('图层', 'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        for name, desc, kind in mode.layers:
            bullet = {'tile': '图块', 'affine': '仿射',
                      'bitmap': '位图', 'obj': '精灵'}[kind]
            add('　· <b>%s</b>（%s）　%s' % (name, bullet, desc.replace('**', '')))

        add('特效', 'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        for k, v in mode.effects:
            ok = v.startswith('支持')
            col = '#9fd6a0' if ok else '#d69f9f'
            add('　· %s　<span style="color:%s">%s</span>' % (k, col, v))

        add('容量账（按 240x160 算）',
            'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        for k, v in mode.budget:
            add('　· %s：%s' % (k, v))

        add('典型用法', 'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        add('　%s' % mode.cases.replace('**', ''), 'color:#a8c8e8;')

        add('适合', 'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        add(mode.good.replace('**', ''), 'color:#9fd6a0;')

        add('代价', 'color:%s; font-weight:600; margin-top:6px;' % C_ACCENT)
        add(mode.cost.replace('**', ''), 'color:#d69f9f;')

        self.text_lay.addStretch(1)
