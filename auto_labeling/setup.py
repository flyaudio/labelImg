# coding=utf-8
import sys, os

def getRootDir():
	if getattr(sys, 'frozen', False):
		root = os.path.dirname(os.path.abspath(sys.executable))
	else:
		root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../")
	return root
sys.path.append(getRootDir())


def setCurPath(filename):
	currentPath = os.path.dirname(filename)
	if currentPath != "":
		os.chdir(currentPath)

