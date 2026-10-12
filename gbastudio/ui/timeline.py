# -*- coding: utf-8 -*-
"""
timeline.py —— 时间轴画布（多轨道）

画：左侧轨道名 | 顶部窄条 | 轨道 | 片段 | 播放头
交互：
    点片段选中 · 拖片段移动 · 拖片段左右边缘改长度 · 点顶部窄条移播放头
    滚轮滚动 · Ctrl+滚轮缩放

关于"时间"：**界面上不显示刻度**（不显示秒数，也不显示第几句）。
顶部那条窄条只用来放播放头把手和"点一下移播放头"，不画任何刻度：
片段自己就带着内容和名字，刻度既多余又要跟着对。
秒数只在属性里作为次要信息出现（编译器和语音同步需要它）。
对齐靠**吸附**：拖片段时会吸到其它片段的首尾，不用看刻度。
"""
import math

from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QCursor
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, \
    QGraphicsSimpleTextItem

from core.project import TRACK_TYPES, MIN_DUR

# 这些尺寸**跟着界面字体缩放**（见 apply_ui_scale）。
# 写死的话，把界面字体调大以后轨道名和片段标签会挤在一起。
LEFT_W = 84          # 左侧轨道名列宽
ROW_H = 24           # 轨道行高
RULER_H = 20         # 顶部条形区高度
SNAP = 0.05          # 吸附精度（秒）
EDGE_PX = 5          # 边缘命中范围（拖长度用）
SNAP_PX = 7          # 吸附到其它片段边缘的像素阈值


def apply_ui_scale(scale=1.0):
    """
    按界面缩放系数重算尺寸。改了界面字体之后要调一次并 rebuild()。

    缩放的是**行高和列宽**（跟着字走），不缩放时间轴的横向比例
    （px_per_sec 是时间刻度，和字体无关）。
    """
    global LEFT_W, ROW_H, RULER_H, EDGE_PX, SNAP_PX
    s = max(0.7, min(2.5, scale))
    LEFT_W = int(round(84 * s))
    ROW_H = int(round(24 * s))
    RULER_H = int(round(20 * s))
    EDGE_PX = max(4, int(round(5 * s)))
    SNAP_PX = max(5, int(round(7 * s)))
    return s


def track_color(kind):
    return TRACK_TYPES.get(kind, {}).get('color', '#5c6b8a')


class ClipItem(QGraphicsRectItem):
    """一个片段。拖左右边缘 = 改长度；拖中间 = 移动"""

    def __init__(self, clip, kind):
        super().__init__()
        self.clip = clip
        self.kind = kind
        self.color = QColor(track_color(kind))
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.label = QGraphicsSimpleTextItem('', self)
        self.label.setBrush(QBrush(QColor(245, 245, 250)))
        self._w = 10.0
        self._h = 10.0

    def set_geometry(self, x, y, w, h):
        self._w, self._h = w, h
        self.setRect(QRectF(0, 0, w, h))
        self.setPos(x, y)
        self.label.setPos(4, 3)
        self.label.setText(self.label_text if w > 26 else '')

    @property
    def label_text(self):
        c = self.clip
        if self.kind.startswith('char'):
            return '%s/%s' % (c.ref or '?', c.props.get('pose', 'normal'))
        if self.kind == 'text':
            t = (c.props.get('text', '') or '')[:12]
            return t
        if self.kind == 'bg':
            return (c.ref or '').split('/')[-1].rsplit('.', 1)[0] or '背景'
        if self.kind in ('voice', 'se'):
            return (c.ref or '').split('/')[-1].rsplit('.', 1)[0] or '音频'
        if self.kind == 'bgm':
            return (c.ref or '').split('/')[-1].rsplit('.', 1)[0] or 'BGM'
        if self.kind == 'fx':
            return {'fade': '淡入淡出', 'shake': '震屏', 'flash': '闪白'}.get(c.kind, c.kind or '特效')
        return c.track

    def paint(self, painter, option, widget=None):
        sel = self.isSelected()
        base = self.color
        painter.setPen(QPen(QColor(255, 220, 120) if sel else base.lighter(150),
                            2 if sel else 1))
        painter.setBrush(QBrush(base.darker(115)))
        painter.drawRoundedRect(self.rect(), 3, 3)

        # 语音/音效画个假波形（P3 换真实波形），让"对齐"看得见
        if self.kind in ('voice', 'se') and self._w > 12:
            painter.setPen(QPen(base.lighter(170), 1))
            h = self._h
            for i in range(3, int(self._w) - 3, 2):
                amp = (math.sin(i * 0.7) * 0.5 + 0.5) * (h * 0.32)
                painter.drawLine(QPointF(i, h / 2 - amp), QPointF(i, h / 2 + amp))

        # 选中时把左右两个"拉手"画出来，提示可以拖长度
        if sel:
            painter.setPen(QPen(QColor(255, 220, 120), 2))
            painter.drawLine(QPointF(0, 2), QPointF(0, self._h - 2))
            painter.drawLine(QPointF(self._w - 1, 2), QPointF(self._w - 1, self._h - 2))

    def edge_at(self, local_x):
        """返回 'l' / 'r' / None：鼠标在不在左右边缘上"""
        if local_x <= EDGE_PX:
            return 'l'
        if local_x >= self._w - EDGE_PX:
            return 'r'
        return None


class TimelineView(QGraphicsView):
    clipSelected = Signal(object)      # 选中片段（None = 取消选中）
    clipChanged = Signal()             # 片段被移动/改长度
    playheadMoved = Signal(float)      # 播放头移动（预览要跟着刷新）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setBackgroundBrush(QBrush(QColor(26, 26, 32)))
        # 内容**贴左上角**，不要居中：
        #   QGraphicsView 默认把小于视口的场景摆在正中间，
        #   于是时间轴上方会空出一大片（面板拉高时尤其明显，看着像少了东西）
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)

        self.project = None
        self.scene = None
        self.px_per_sec = 26.0
        self.playhead = 0.0
        self._drag = None          # ('move'|'trim_l'|'trim_r', item, 起始信息)
        self._clip_items = []
        self.setMinimumHeight(60)   # 面板能自由缩小，别设太死

    # ------------------------------------------------------------ 数据
        self.collapsed = set()      # 折叠起来的图层 id
        # 接收从素材库拖过来的素材（丢到轨道上就变成一个片段）
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

    layerClicked = Signal(str)      # 点了某个图层头（地图窗口跟着选中它）
    # 从素材库拖了一个素材放到轨道上：(轨道 id, 落点秒数, 素材相对路径)
    assetDropped = Signal(str, float, str)

    def set_project(self, project, scene=None):
        self.project = project
        self.scene = scene or (project.scenes[0] if project and project.scenes else None)
        self.rebuild()

    # ------------------------------------------------------------ 行模型
    #
    # 【为什么要有"行"这一层】
    # 以前时间轴的行 = 轨道 ✓ 一行一条轨道 ✓
    # 加了图层之后，一条轨道还得知道"我在哪一层里" ✓
    # 而且图层要能折叠 ✓ 折叠后它的轨道行就不出现 ✓
    # ——所以画之前先把"这一屏有哪几行"算出来 ✓ 行 = ('layer', 图层) 或 ('track', 轨道)
    #
    # 行高统一 ROW_H ✓ 命中测试、拖拽、滚动全都按"第几行"算 ✓ 不会两套算法打架 ✓

    def ordered_tracks(self):
        """场景里的全部轨道，**按图层分组排序**（图层顺序 + 层内上下顺序）

        ⚠ 返回的是**全部**轨道 ✗ 不受折叠影响 ✓
          折叠只影响"画不画"✓ 不影响数据和命中测试 ✓
          别的模块（预览/编译器）拿到的轨道集合也不会因为折叠而变少 ✓
        """
        if not self.scene:
            return []
        if not getattr(self.scene, 'layers', None):
            return list(self.scene.tracks)          # 还没建图层的旧场景
        out, seen = [], set()
        for L in self.scene.layers:
            for tid in L.tracks:
                tr = self.scene.track(tid)
                if tr is not None and tid not in seen:
                    out.append(tr)
                    seen.add(tid)
        # 兜底：万一有轨道没归到任何层（数据坏了），也让它显示出来
        for tr in self.scene.tracks:
            if tr.id not in seen:
                out.append(tr)
        return out

    def visible_tracks(self):
        """场景里定义的所有轨道；空白的额外轨道也显示（能看到、能往里拖东西）"""
        return self.ordered_tracks()

    def rows(self):
        """这一屏要画的行：[('layer', Layer), ('track', Track), ...]

        每个图层先出一行"图层头"✓ 再出它里面的轨道行 ✓
        折叠起来的图层只出图层头 ✓
        """
        if not self.scene:
            return []
        if not getattr(self.scene, 'layers', None):
            return [('track', tr) for tr in self.scene.tracks]
        out = []
        placed = set()
        for L in self.scene.layers:
            n = len(L.tracks)
            out.append(('layer', L))
            if L.id in self.collapsed:
                placed |= set(L.tracks)
                continue
            for tid in L.tracks:
                tr = self.scene.track(tid)
                if tr is not None:
                    out.append(('track', tr))
                    placed.add(tid)
        for tr in self.scene.tracks:                # 兜底
            if tr.id not in placed:
                out.append(('track', tr))
        return out

    def row_index_of_track(self, track_id):
        """某条轨道在第几行（找不到返回 0）"""
        for i, (kind, obj) in enumerate(self.rows()):
            if kind == 'track' and obj.id == track_id:
                return i
        return 0

    def row_at(self, view_pos):
        """鼠标在第几行上（返回 (行号, 行内容) 或 (None, None)）"""
        p = self.mapToScene(view_pos.toPoint() if hasattr(view_pos, 'toPoint') else view_pos)
        if p.y() < RULER_H:
            return None, None
        i = int((p.y() - RULER_H) // ROW_H)
        rs = self.rows()
        if 0 <= i < len(rs):
            return i, rs[i]
        return None, None

    def toggle_layer(self, lid):
        """折叠 / 展开一个图层"""
        if lid in self.collapsed:
            self.collapsed.discard(lid)
        else:
            self.collapsed.add(lid)
        self.rebuild()

    def duration(self):
        """
        时间轴该画多长：**内容末尾 + 2 秒**，不再用固定的 scene.duration。
        （以前新场景固定 30 秒、示例 24 秒，导致内容演完了后面还拖着一大段空白，
          看起来像"轨道长度不对"。）
        """
        if not self.scene:
            return 16.0
        end = max([c.start + c.dur for c in self.scene.clips] + [0.0])
        return max(12.0, end + 2.0)

    def preferred_height(self):
        """
        放得下所有轨道需要多高 —— 默认布局用。

        不这么算的话，一打开时间轴只露出最上面一条轨道（其余要滚动才看得见），
        新用户会以为"只有一条轨道"。这里按实际轨道数算。
        """
        # 按**行数**算（含图层头 ✓ 折叠的层只有头一行 ✓）
        n = max(1, len(self.rows()))
        return RULER_H + n * ROW_H + 26      # 26 给横向滚动条留位

    def dialogue_marks(self):
        """
        台词片段的起点时刻（按先后排序）。返回 [(第几句, 起点秒)]

        时间轴上**不再画**这些序号（顶部保持干净），但"现在演到第几句"
        这个信息在预览信息栏里还用得到，所以留着。
        """
        if not self.scene:
            return []
        rows = []
        for tk in self.scene.tracks:
            if tk.kind == 'text':
                for c in self.scene.track_clips(tk.id):
                    rows.append(c.start)
        rows.sort()
        return [(i + 1, t) for i, t in enumerate(rows)]

    # ------------------------------------------------------------ 绘制
    def rebuild(self):
        s = self.scene_
        s.clear()
        self._clip_items = []
        rows = self.rows()
        dur = self.duration()
        W = LEFT_W + dur * self.px_per_sec + 60
        H = RULER_H + max(1, len(rows)) * ROW_H + 8

        # 顶部：一条干净的窄条（**不画刻度和序号**）
        #   原来这里画"句"和 1/2/3 序号，实际用起来是干扰 ——
        #   片段自己就带台词内容，序号既多余又要跟着对。
        #   这条窄条保留是为了放播放头的小把手，以及"点这里移播放头"的操作。
        s.addRect(0, 0, W, RULER_H, QPen(Qt.NoPen), QBrush(QColor(22, 22, 28)))
        s.addLine(0, RULER_H - 1, W, RULER_H - 1, QPen(QColor(70, 70, 84)))
        s.addLine(LEFT_W - 1, 2, LEFT_W - 1, RULER_H - 3, QPen(QColor(58, 58, 68)))

        # 行 + 片段：图层头一行 ✓ 它下面的轨道缩进一行 ✓
        for i, (rkind, robj) in enumerate(rows):
            y = RULER_H + i * ROW_H
            if rkind == 'layer':
                self._draw_layer_row(s, robj, y, W, i)
                continue
            tk = robj
            s.addRect(0, y, LEFT_W, ROW_H, QPen(QColor(58, 58, 68)),
                      QBrush(QColor(38, 38, 46)))
            # 这个轨道属于哪一层 → 决定缩进和左侧的竖线
            L = self.scene.layer_of(tk.id) if self.scene else None
            indent = 14 if L is not None else 0
            if L is not None:
                s.addLine(9, y, 9, y + ROW_H, QPen(QColor(72, 72, 88)))   # 归属竖线
            t = s.addSimpleText(tk.name)
            t.setBrush(QBrush(QColor(205, 205, 218) if tk.visible else QColor(110, 110, 125)))
            # 名字**右对齐贴住内容区分界线**、垂直居中（原来固定 8,+4，看着是飘的）
            br = t.boundingRect()
            t.setPos(max(4 + indent, LEFT_W - 8 - br.width()),
                     y + (ROW_H - br.height()) / 2 - 1)
            s.addLine(LEFT_W, y + ROW_H, W, y + ROW_H, QPen(QColor(46, 46, 55)))
            if i % 2 == 0:
                s.addRect(LEFT_W, y, W - LEFT_W, ROW_H, QPen(Qt.NoPen),
                          QBrush(QColor(30, 30, 37)))
            if not self.scene:
                continue
            for c in self.scene.track_clips(tk.id):
                item = ClipItem(c, tk.kind)
                item.set_geometry(LEFT_W + c.start * self.px_per_sec, y + 3,
                                  max(6.0, c.dur * self.px_per_sec), ROW_H - 6)
                s.addItem(item)
                self._clip_items.append(item)

        # 播放头
        px = LEFT_W + self.playhead * self.px_per_sec
        self._ph_line = s.addLine(px, 0, px, H, QPen(QColor(232, 84, 84), 1.6))
        self._ph_head = s.addRect(px - 5, 0, 10, 9, QPen(Qt.NoPen), QBrush(QColor(232, 84, 84)))
        s.setSceneRect(-2, -2, W + 4, H + 4)

    def _draw_layer_row(self, s, L, y, W, i):
        """画一行"图层头"

        样子：`▼ 远山   图块层`  + 右边一条淡带
        —— 和轨道行的区别要**一眼看得出** ✗
           所以：底色更亮一点、名字加粗、左边有折叠箭头 ✓
           轨道行则缩进 14 像素 + 一根归属竖线 ✓（见 rebuild）
        """
        collapsed = L.id in self.collapsed
        # 左列（和内容区的分界线对齐）
        s.addRect(0, y, LEFT_W, ROW_H, QPen(QColor(70, 70, 86)),
                  QBrush(QColor(46, 46, 58)))
        # 折叠箭头
        t = s.addSimpleText('▶' if collapsed else '▼')
        t.setBrush(QBrush(QColor(150, 150, 168)))
        t.setPos(4, y + (ROW_H - t.boundingRect().height()) / 2 - 1)
        # 图层名（加粗一点：用更亮的颜色代替字重，QGraphicsSimpleTextItem 不好设粗体）
        name = s.addSimpleText(L.name)
        name.setBrush(QBrush(QColor(255, 209, 102) if L.visible else QColor(120, 120, 132)))
        br = name.boundingRect()
        name.setPos(18, y + (ROW_H - br.height()) / 2 - 1)
        # 类型（小字，贴在名字右边）
        kind = s.addSimpleText(L.kind_title)
        kind.setBrush(QBrush(QColor(120, 120, 136)))
        kind.setPos(18 + br.width() + 8, y + (ROW_H - kind.boundingRect().height()) / 2)
        # 内容区：一条淡带（表示"这一行是分组，不是片段轨"）
        s.addRect(LEFT_W, y, W - LEFT_W, ROW_H, QPen(Qt.NoPen),
                  QBrush(QColor(40, 40, 50)))
        s.addLine(LEFT_W, y + ROW_H, W, y + ROW_H, QPen(QColor(58, 58, 70)))
        # 这条图层里有几段（折叠时尤其有用：知道里面有没有东西）
        n = sum(len(self.scene.track_clips(tid)) for tid in L.tracks) if self.scene else 0
        if n:
            c = s.addSimpleText('%d 段' % n)
            c.setBrush(QBrush(QColor(110, 110, 126)))
            c.setPos(LEFT_W + 8, y + (ROW_H - c.boundingRect().height()) / 2 - 1)

    def snap_time(self, t, ignore=None):
        """
        吸附：优先吸到其它片段的首尾（这样不用看秒数也能对齐），
        其次吸到 0.05 秒网格。
        """
        if self.scene:
            thresh = SNAP_PX / self.px_per_sec
            best, bestd = None, thresh
            for c in self.scene.clips:
                if c is ignore:
                    continue
                for edge in (c.start, c.start + c.dur):
                    d = abs(edge - t)
                    if d < bestd:
                        best, bestd = edge, d
            if best is not None:
                return round(best, 3)
        return round(t / SNAP) * SNAP

    def set_playhead(self, sec):
        self.playhead = max(0.0, sec)
        if hasattr(self, '_ph_line'):
            px = LEFT_W + self.playhead * self.px_per_sec
            self._ph_line.setLine(px, 0, px, self.scene_.sceneRect().height())
            self._ph_head.setRect(px - 5, 0, 10, 9)
        self.playheadMoved.emit(self.playhead)

    # ------------------------------------------------------------ 交互
    def _time_at(self, view_pos):
        p = self.mapToScene(view_pos.toPoint() if hasattr(view_pos, 'toPoint') else view_pos)
        return (p.x() - LEFT_W) / self.px_per_sec

    def _clip_at(self, view_pos):
        it = self.itemAt(view_pos.toPoint() if hasattr(view_pos, 'toPoint') else view_pos)
        return it if isinstance(it, ClipItem) else None

    # ------------------------------------------------------------ 拖放
    ASSET_MIME = 'application/x-gbastudio-asset'

    def _drop_target(self, pos):
        """鼠标底下是哪条轨道、哪个时刻。返回 (Track, 秒) 或 (None, 0)"""
        _i, row = self.row_at(pos)
        if row is None or row[0] != 'track':
            return None, 0.0
        return row[1], max(0.0, self._time_at(pos))

    def _asset_path(self, mime):
        if not mime.hasFormat(self.ASSET_MIME):
            return ''
        return bytes(mime.data(self.ASSET_MIME)).decode('utf-8', 'replace')

    def dragEnterEvent(self, ev):
        if self._asset_path(ev.mimeData()):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        """只有落在**轨道行**上才算数（落在图层头/标尺上不接受）"""
        if not self._asset_path(ev.mimeData()):
            super().dragMoveEvent(ev)
            return
        tk, _t = self._drop_target(ev.position())
        if tk is not None:
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dropEvent(self, ev):
        path = self._asset_path(ev.mimeData())
        if not path:
            super().dropEvent(ev)
            return
        tk, tsec = self._drop_target(ev.position())
        if tk is None:
            ev.ignore()
            return
        self.assetDropped.emit(tk.id, tsec, path)
        ev.acceptProposedAction()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self._drag:
            mode, item, x0, s0, d0 = self._drag
            dt = (pos.x() - x0) / self.px_per_sec
            c = item.clip
            if mode == 'move':
                c.start = max(0.0, self.snap_time(s0 + dt, ignore=c))
            elif mode == 'trim_l':
                ns = max(0.0, min(s0 + d0 - MIN_DUR, self.snap_time(s0 + dt, ignore=c)))
                c.dur = s0 + d0 - ns
                c.start = ns
            elif mode == 'trim_r':
                c.dur = max(MIN_DUR, self.snap_time(d0 + dt, ignore=c))
            tk = self.scene.track(c.track) if self.scene else None
            y = RULER_H + self.row_index_of_track(c.track) * ROW_H + 3
            item.set_geometry(LEFT_W + c.start * self.px_per_sec, y,
                              max(6.0, c.dur * self.px_per_sec), ROW_H - 6)
            self.set_playhead(c.start if mode == 'trim_l' else self.playhead)
            super().mouseMoveEvent(ev)
            return

        # 鼠标在边缘时换成左右箭头，提示"这里能拖长度"
        item = self._clip_at(pos)
        if item is not None:
            local = self.mapToScene(pos.toPoint()).x() - item.pos().x()
            self.setCursor(QCursor(Qt.SizeHorCursor if item.edge_at(local) else Qt.ArrowCursor))
        else:
            self.setCursor(QCursor(Qt.ArrowCursor))
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev):
        pos = ev.position()
        # 先看是不是点在**图层头**上：折叠箭头 或 选中这一层
        ri, row = self.row_at(pos)
        if row is not None and row[0] == 'layer':
            L = row[1]
            if pos.x() < 18:                 # 点在箭头上 → 折叠/展开
                self.toggle_layer(L.id)
                return
            self.layerClicked.emit(L.id)
            for it in self.scene_.items():
                it.setSelected(False)
            self.clipSelected.emit(None)
            return
        item = self._clip_at(pos)
        if item is not None:
            self.scene_.clearSelection()
            item.setSelected(True)
            local = self.mapToScene(pos.toPoint()).x() - item.pos().x()
            edge = item.edge_at(local)
            mode = {'l': 'trim_l', 'r': 'trim_r'}.get(edge, 'move')
            self._drag = (mode, item, pos.x(), item.clip.start, item.clip.dur)
            self.clipSelected.emit(item.clip)
        elif pos.x() > LEFT_W and pos.y() < RULER_H + 4:
            self.set_playhead(self._time_at(pos))
        else:
            self.scene_.clearSelection()
            self.clipSelected.emit(None)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._drag:
            mode = self._drag[0]
            self._drag = None
            self.clipChanged.emit()
            if mode in ('trim_l', 'trim_r'):
                self.rebuild()          # 改完长度重画一遍，标签宽度跟着更新
            self.set_playhead(self.playhead)
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.px_per_sec = max(6.0, min(160.0,
                                           self.px_per_sec * (1.15 if ev.angleDelta().y() > 0 else 0.87)))
            self.rebuild()
        else:
            super().wheelEvent(ev)
