# -*- coding: utf-8 -*-
"""
settings.py —— 界面缩放与偏好设置

**为什么要单独一个模块**：界面字体一改，好几处的尺寸都得跟着变
（时间轴行高、轨道名列宽、按钮高度…），散在各文件里就会"改了字体但时间轴还是老样子"。
这里统一算，别处只管问。

存哪：**%APPDATA%\\GBAStudio\\settings.ini**（一个 INI 文件，不是注册表）。

    原来的写法是 QSettings('GBAStudio', 'Editor')，默认落到注册表 ——
    实测**写不进去**（写完立刻读回来是 None），等于设置一直没存住。
    改存 INI 文件：一定能写、能直接打开看、能随工程一起备份，
    也和这个工程"不写注册表、不污染系统"的一贯做法一致
    （安装脚本同样把东西全放在工程目录里）。
"""
import os

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# 界面字体档位：(菜单里显示的名字, 点大小)
FONT_CHOICES = [('小', 8), ('标准', 9), ('大', 11), ('特大', 13)]
DEFAULT_FONT_PT = 9
FONT_FAMILY = 'Microsoft YaHei UI'

# 预览缩放档位。'fit' = 适应窗口（拖多大就显示多大）
ZOOM_CHOICES = [('适应窗口', 'fit'), ('1×', 1), ('2×', 2), ('3×', 3),
                ('4×', 4), ('6×', 6), ('8×', 8)]
DEFAULT_ZOOM = 'fit'


def ini_path():
    """
    设置文件的位置。优先级：

      1. 环境变量 GBASTUDIO_SETTINGS 指定的文件 —— 便携安装和自动化测试用
      2. %APPDATA%\\GBAStudio\\settings.ini —— 正常情况
      3. 用户主目录（%APPDATA% 不存在时的退路）

    注意 %APPDATA% 在某些受限环境里是**不存在的**，所以不能只用它。
    """
    env = os.environ.get('GBASTUDIO_SETTINGS')
    if env:
        d = os.path.dirname(os.path.abspath(env))
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return os.path.abspath(env)
    base = os.environ.get('APPDATA')
    if base:
        d = os.path.join(base, 'GBAStudio')
        try:
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, 'settings.ini')
        except OSError:
            pass
    return os.path.join(os.path.expanduser('~'), 'gbastudio-settings.ini')


def qsettings():
    """拿设置对象（窗口布局等也用它，全工程只有这一处 QSettings）"""
    return QSettings(ini_path(), QSettings.IniFormat)


def _write(key, value):
    """
    写一项并立刻落盘。

    写不进去要**明确报出来** —— 原来用 QSettings 默认（注册表）时写完读回来是 None，
    而且一声不响，结果"改了界面字体，下次启动又变回去"这种问题极难查。
    """
    s = qsettings()
    s.setValue(key, value)
    s.sync()
    if s.status() != QSettings.NoError:
        print('[settings] ⚠ 设置写不进去（%s）：%s' % (key, ini_path()))
    return s.status() == QSettings.NoError


# ---------------------------------------------------------------------------
# 当前值（模块级，简单够用；改的时候走 save_* 顺便落盘）
# ---------------------------------------------------------------------------
font_pt = DEFAULT_FONT_PT
zoom = DEFAULT_ZOOM


def ui_scale():
    """相对于标准字号的缩放系数。界面里所有"跟着字体走"的尺寸都乘它。"""
    return font_pt / float(DEFAULT_FONT_PT)


def load():
    """启动时读一次"""
    global font_pt, zoom
    s = qsettings()
    try:
        font_pt = int(s.value('ui/font_pt', DEFAULT_FONT_PT))
    except (TypeError, ValueError):
        font_pt = DEFAULT_FONT_PT
    if font_pt not in [v for _, v in FONT_CHOICES]:
        font_pt = DEFAULT_FONT_PT
    z = s.value('ui/preview_zoom', DEFAULT_ZOOM)
    zoom = z if z == 'fit' else int(z) if str(z).isdigit() else DEFAULT_ZOOM
    return font_pt, zoom


def save_font(pt):
    global font_pt
    font_pt = int(pt)
    _write('ui/font_pt', font_pt)


def save_zoom(z):
    global zoom
    zoom = z
    _write('ui/preview_zoom', z)


def font(pt=None):
    return QFont(FONT_FAMILY, pt or font_pt)


def apply_font(pt=None, app=None):
    """
    改界面字体。

    坑：Qt 的 QApplication.setFont() **只影响之后创建的控件**，
    已经在界面上的不会变。所以要挨个把新字体按到现有控件上。
    好在本工程没有哪个控件是故意用别的字体的，全部覆盖是安全的。
    """
    app = app or QApplication.instance()
    if app is None:
        return
    f = font(pt)
    app.setFont(f)
    for w in app.allWidgets():
        w.setFont(f)
    save_font(pt if pt else font_pt)
