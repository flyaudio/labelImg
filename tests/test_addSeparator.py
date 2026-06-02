import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar,
                             QAction, QMenuBar)
from PyQt5.QtCore import Qt

# --------------------- 完全复刻你看到的 LabelImg 工具类 ---------------------
# 批量添加动作的工具函数（LabelImg 源码里的函数）
def add_actions(target, actions):
    for action in actions:
        if action is None:
            target.addSeparator()  # ← 这里就是 addSeparator() 核心用法！
        else:
            target.addAction(action)

# 你看不懂的 WindowMixin 类（原封不动）
class WindowMixin(object):
    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = QToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.RightToolBarArea, toolbar)
        return toolbar

# --------------------- 测试主窗口：演示 addSeparator() ---------------------
class MainWindow(QMainWindow, WindowMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("addSeparator() 分隔线测试")
        self.resize(600, 400)

        # 1. 创建测试按钮（动作）
        self.open_act = QAction("打开", self)
        self.save_act = QAction("保存", self)
        self.exit_act = QAction("退出", self)
        self.copy_act = QAction("复制", self)
        self.paste_act = QAction("粘贴", self)

        # 2. 创建菜单 + 用 addSeparator() 分组
        self.menu(
            "文件",
            actions=[
                self.open_act,   # 第一项
                self.save_act,   # 第二项
                None,            # ← None 会触发 addSeparator()，添加分隔线！
                self.exit_act    # 分隔线下方的项
            ]
        )

        # 3. 创建工具栏 + 用 addSeparator() 分组
        self.toolbar(
            "操作",
            actions=[
                self.open_act,
                self.save_act,
                None,            # ← 工具栏也能加分隔线！
                self.copy_act,
                self.paste_act
            ]
        )

# --------------------- 程序入口 ---------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())