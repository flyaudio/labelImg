import unittest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
# from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar,
#                              QAction, QMenuBar)
import setup
from libs.canvas import Canvas


class TestAboutDialog(unittest.TestCase):
	def setUp(self):
		'''每个测试用例执行前自动调用'''
		print("setup")
		self.app = QtWidgets.QApplication.instance()
		if self.app is None:
			self.app = QtWidgets.QApplication([])

	def tearDown(self):
		'''每个测试用例执行后自动调用'''
		print("tear down")
		self.app.processEvents()

	def test(self):
		window = TestWindow()
		window.show()
		print("1=", window.wrapper.current_cursor())
		self.app.exec()


class TestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.wrapper = Canvas(self)
		self.setCentralWidget(self.wrapper)


def test():
	canvas = Canvas()


if __name__ == '__main__':
	unittest.main()
# test()
