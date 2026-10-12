# -*- coding: utf-8 -*-
"""
dialogs.py —— 各种对话框

「新建项目」和「导入素材」这两件事，光有功能不够，**必须有反馈**：
用户点了按钮要立刻知道"做了什么、东西放哪了、下一步该干嘛"。
所以这两个对话框都会在完成后写日志 + 状态栏提示 + 弹出结果摘要。
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QComboBox, QLabel, QPushButton,
                               QFileDialog, QCheckBox, QListWidget, QListWidgetItem,
                               QMessageBox, QScrollArea)

from core import assets as A
from ui.video_modes import MODES as MODE_LIST, ModeCard, C_DIM


def _section_label(text):
    lab = QLabel(text)
    lab.setStyleSheet('color:#ffb703; font-weight:600; margin-top:8px;')
    return lab


# 新建项目的默认选中项：模式 3（本项目一直用它 —— 中文文字和照片背景都靠它）
DEFAULT_MODE_ROW = next((i for i, m in enumerate(MODE_LIST) if m.m == 3), 0)


class ImportAssetsDialog(QDialog):
    """
    导入素材：**只选文件，不选类型**。

    按用户要求去掉了"放进哪一类"——默认分类覆盖不了所有需求，
    所以导入时一律放进 assets/ 并标为「未分类」，
    之后在资源库里右键「归类为」手动指定（那才是准确的）。
    """

    def __init__(self, project, parent=None, preset_kind=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle('导入素材')
        self.setMinimumWidth(620)

        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        self.files = QListWidget()
        self.files.setMinimumHeight(180)
        row.addWidget(self.files, 1)
        col = QVBoxLayout()
        b1 = QPushButton('添加文件…')
        b1.clicked.connect(self._add_files)
        b2 = QPushButton('添加文件夹…')
        b2.clicked.connect(self._add_folder)
        b3 = QPushButton('移除选中')
        b3.clicked.connect(self._remove_selected)
        col.addWidget(b1)
        col.addWidget(b2)
        col.addWidget(b3)
        col.addStretch(1)
        row.addLayout(col)
        lay.addWidget(QLabel('要导入的文件（**也可以直接把文件拖到这里**）：'))
        lay.addLayout(row)
        self.setAcceptDrops(True)

        tip = QLabel('导入后文件会放进项目的 assets/ 目录，并标记为「未分类」。\n'
                     '在资源库里右键 →「归类为」再指定它们是 背景 / 立绘 / 音乐 / 语音 / 音效。')
        tip.setStyleSheet('color:#8a8a99;')
        lay.addWidget(tip)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('导入')
        bb.button(QDialogButtonBox.Cancel).setText('取消')
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    # ------------------------------------------------------------ 拖放
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for url in ev.mimeData().urls():
            self._append(url.toLocalFile())

    # ------------------------------------------------------------ 列表
    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, '选择素材', '',
            '素材文件 (*.png *.jpg *.jpeg *.bmp *.wav *.ogg *.mp3);;所有文件 (*.*)')
        for f in files:
            self._append(f)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, '选择文件夹（会导入里面的所有素材）')
        if not d:
            return
        n = 0
        for root, _, files in os.walk(d):
            for fn in files:
                if os.path.splitext(fn)[1].lower() in A.IMG_EXT + A.AUD_EXT:
                    self._append(os.path.join(root, fn))
                    n += 1
        if n == 0:
            QMessageBox.information(self, '这个文件夹里没有素材',
                                    '只支持图片（png/jpg/bmp）和音频（wav/ogg/mp3）')

    def _append(self, path):
        if not path or not os.path.isfile(path):
            return
        if not self.files.findItems(path, Qt.MatchExactly):
            it = QListWidgetItem(path)
            it.setToolTip(path)
            self.files.addItem(it)

    def _remove_selected(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))

    def values(self):
        return {'files': [self.files.item(i).text() for i in range(self.files.count())]}
