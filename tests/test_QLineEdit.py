import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit

class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QLineEdit 基础示例")
        self.resize(400, 100)

        self.line_edit = QLineEdit(self)
        # 设置占位提示文字（空输入时显示的灰色提示）
        # self.line_edit.setEchoMode(QLineEdit.EchoMode.NoEcho) #Password,PasswordEchoOnEdit
        self.line_edit.setPlaceholderText("请输入内容...")
        self.line_edit.setClearButtonEnabled(True) # 开启内置清除按钮：输入内容后右侧出现 × 按钮，点击清空

        # 布局管理
        layout = QVBoxLayout(self)
        layout.addWidget(self.line_edit)

        # 1. 文本发生变化时触发（包括代码setText修改也会触发）
        self.line_edit.textChanged.connect(self.on_text_changed)

        # 2. 用户手动编辑文本时触发（代码修改文本不会触发，更适合监听用户输入）
        # self.line_edit.textEdited.connect(self.on_text_edited)

        # 3. 按下回车键时触发
        self.line_edit.returnPressed.connect(self.on_edit_finish)

        # 4. 编辑完成时触发（失去焦点 或 按下回车，两种情况都会触发）
        self.line_edit.editingFinished.connect(self.on_edit_finish)

    def on_text_changed(self, text):
        print(f"文本变化了，当前内容：{text}")

    def on_edit_finish(self):
        print(f"用户按下了回车，输入内容：{self.line_edit.text()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())