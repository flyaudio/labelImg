from PyQt6 import uic
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QPoint,
    QTimer,
    QObject
)
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)


class Example(QObject):
    my_signal = pyqtSignal(str)

    def do_something(self):
        self.my_signal.emit("Hello, World!")# 发射信号并传递参数


def test():
    example = Example()
    example.my_signal.connect(lambda string: print(string))
    example.do_something()

if __name__ == '__main__':
    test()