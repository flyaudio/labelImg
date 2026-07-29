from math import sqrt
from libs.ustr import ustr
import hashlib
import re
import sys
import json
import os
import time
# from PyQt6.QtCore import QRegularExpression
# from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
# QT5 = True


def new_icon(icon):
    return QIcon(':/' + icon)


def new_button(text, icon=None, slot=None):
    b = QPushButton(text)
    if icon is not None:
        b.setIcon(new_icon(icon))
    if slot is not None:
        b.clicked.connect(slot)
    return b


def new_action(parent, text, slot=None, shortcut=None, icon=None,
               tip=None, checkable=False, enabled=True):
    """Create a new action and assign callbacks, shortcuts, etc."""
    a = QAction(text, parent)
    if icon is not None:
        a.setIcon(new_icon(icon))
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    if tip is not None:
        a.setToolTip(tip)
        a.setStatusTip(tip)
    if slot is not None:
        a.triggered.connect(slot)
    if checkable:
        a.setCheckable(True)
    a.setEnabled(enabled)
    return a


def add_actions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)


def label_validator():
    # return QRegExpValidator(QRegExp(r'^[^ \t].+'), None)
    return QRegularExpressionValidator(QRegularExpression(r'^[^ \t].+'), None)


class Struct(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def distance(p):
    return sqrt(p.x() * p.x() + p.y() * p.y())


def format_shortcut(text):
    mod, key = text.split('+', 1)
    return '<b>%s</b>+<b>%s</b>' % (mod, key)


def generate_color_by_text(text):
    alpha = 120
    COLORS_MAP = {
        "OK": QColor(0, 255, 0, alpha),  # 绿
        "OK1": QColor(0, 255, 0, alpha),  # 绿
        "CQ": QColor(255, 0, 0, alpha),  # 红
        "BD": QColor(0, 0, 255, alpha),  # 蓝
        "NG": QColor(255, 255, 0, alpha),  # 黄
        "NG1": QColor(255, 255, 0, alpha),  # 黄
        "NG2": QColor(255, 0, 255, alpha),  # 紫
        "OK2": QColor(0, 255, 255, alpha),  # 青
        "NG3": QColor(255, 128, 0, alpha),  # 橙
        "NG4": QColor(128, 0, 255, alpha),  # 紫蓝
        "NG5": QColor(255, 20, 147, alpha),  # 深粉
        "NG6": QColor(0, 128, 128, alpha),  # 蓝绿
    }
    text_lower = text.strip().upper()
    if text_lower in COLORS_MAP:
        return COLORS_MAP[text_lower]
    s = ustr(text)
    hash_code = int(hashlib.sha256(s.encode('utf-8')).hexdigest(), 16)
    r = int((hash_code / 255) % 255)
    g = int((hash_code / 65025) % 255)
    b = int((hash_code / 16581375) % 255)
    return QColor(r, g, b, 100)


def have_qstring():
    """p3/qt5 get rid of QString wrapper as py3 has native unicode str type"""
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))


def util_qt_strlistclass():
    return QStringList if have_qstring() else list


def natural_sort(list, key=lambda s:s):
    """
    Sort the list into natural alphanumeric order.
    """
    def get_alphanum_key_func(key):
        convert = lambda text: int(text) if text.isdigit() else text
        return lambda s: [convert(c) for c in re.split('([0-9]+)', key(s))]
    sort_key = get_alphanum_key_func(key)
    list.sort(key=sort_key)


# QT4 has a trimmed method, in QT5 this is called strip
# if QT5:
def trimmed(text):
    return text.strip()
# else:
#     def trimmed(text):
#         return text.trimmed()


class EventTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventTracker, cls).__new__(cls)
            cls._instance.counters = {}
            cls._instance.timer = {}
        return cls._instance

    def increment(self, counter_name):
        if counter_name not in self.counters:
            self.counters[counter_name] = 0
        self.counters[counter_name] += 1
        if counter_name not in self.timer:
            self.timer[counter_name] = time.time()
        return self.counters[counter_name]

    def get_count(self, counter_name):
        return self.counters.get(counter_name, 0)

    def get_all_counts(self):
        return self.counters.copy()

    def reset(self, counter_name=None):
        if counter_name is None:
            self.counters = {}
            self.timer = {}
        elif counter_name in self.counters:
            self.counters[counter_name] = 0
            self.timer[counter_name] = 0


def load_json(file_path: str) -> dict:
    """Load the json file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, file_path: str):
    """Save the json file"""
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def set_icon_path(icon_name: str, format: str = "svg") -> str:
    """Set the path to the icon

    Args:
        icon_name: Name of the icon file without extension
        format: File format extension (default: 'svg')
    """
    return f"anylabeling/resources/icons/{icon_name}.{format}"
