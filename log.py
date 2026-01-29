# ! /usr/bin/env python
# -*- coding: utf-8 -*-
# __author__ = "Victor"
# Date: 2020/7/14

import os
import time
import threading
import logging
import colorlog #pip install colorlog
from logging import handlers
from datetime import datetime
from pathlib import Path
# import setup
# import utils.conf as conf
# import utils.pathUtil as pathUtil
from PyQt5.QtWidgets import QMessageBox, QApplication


_init_lock = threading.Lock()

M_size = 1024 * 1024
g_log_verbose = True #conf.getbool("debug", "log_verbose", False)


def showMsgBox(level, message):
    app = QApplication.instance()
    if app:
        msg_box = QMessageBox()
        msg_box.setWindowTitle(level.capitalize())
        msg_box.setText(message)

        if level == "warning":
            msg_box.setIcon(QMessageBox.Warning)
        elif level.lower() == "critical":
            msg_box.setIcon(QMessageBox.Critical)
        else:
            msg_box.setIcon(QMessageBox.Information)

        msg_box.exec_()


# def closeWerkzeugLogger():
#     if not conf.getbool("web", "enable_log", False):
#         werkzeugLogger = logging.getLogger('werkzeug')
#         werkzeugLogger.setLevel(logging.ERROR)

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',   # 蓝色
        'INFO': '\033[92m',    # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',    # 红色
        'CRITICAL': '\033[41m', # 背景红色
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        # record.asctime = f"{color}{self.formatTime(record)}{self.RESET}"
        # record.asctime = f"{color}{self.asctime}{self.RESET}"
        # record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"

        if record.levelname == 'DEBUG':
            record.levelname = 'D'
        elif record.levelname == 'INFO':
            record.levelname = 'I'
        elif record.levelname == 'WARNING':
            record.levelname = 'W'
        elif record.levelname == 'ERROR':
            record.levelname = 'E'
        elif record.levelname == 'CRITICAL':
            record.levelname = 'C'

        return super().format(record)

class CustomFormatter(logging.Formatter):
    def format(self, record):
        if record.levelname == 'DEBUG':
            record.levelname = 'D'
        elif record.levelname == 'INFO':
            record.levelname = 'I'
        elif record.levelname == 'WARNING':
            record.levelname = 'W'
        elif record.levelname == 'ERROR':
            record.levelname = 'E'
        elif record.levelname == 'CRITICAL':
            record.levelname = 'C'
        return super().format(record)


class Log(object):
    def __init__(self, logger="my_logger", log_cate='TDDS', split='time', split_attr='midnight',
                 backup_count=15):
        """
        split: 日期文件的切分规则，默认值为time
              time: 表示按照实际切分，每天一个文件， 好处是每天一个文件，数据量小比较OK;
              size: 表示按照大小切分, 每个文件100M， 好处是文件比较小；
              "":   空字符串表示所有日志写入单个文件中, 应该强烈避免
        split_attr: 文件切分属性，
                   当split='time'时,split_attr值可以为'S'每秒一个文件；’M'每分钟一个文件；'H'每小时一个文件；'D'每天一个文件；
                   当split='time'时,split_attr值可以为'midnight'在每天0点创建新文件；'W0'-'W6'每周的某天创建一个文件，0表示周一；
                   当split='size'时,split_attr值为一个元组，元组的第一个元素表示文件大小（单位M），第二个元素表示保留文件的数量
        backup_count: 保存的天数， 默认会保存最近15天
        """
        # new logger
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)
        self.log_time = time.strftime("%Y_%m_%d")
        # fileDir = Path(os.path.expanduser('~/user_data/log'))
        fileDir = Path("./")
        if not fileDir.exists():
            fileDir.mkdir(exist_ok=True)
        # self.log_path = str(fileDir)
        self.log_name = str(fileDir / 'label.log')
        print(self.log_name)

        if split == 'time':
            # interval 1天分割一次
            fh = handlers.TimedRotatingFileHandler(self.log_name, split_attr, interval=1,
                                                   backupCount=backup_count)
        elif split == 'size':
            log_size, self.log_backup_count = split_attr
            fh = handlers.RotatingFileHandler(self.log_name, maxBytes=log_size * M_size,
                                              backupCount=backup_count)
        else:
            fh = logging.FileHandler(self.log_name, 'a', encoding='utf-8')

        # file handler
        fh.setLevel(logging.DEBUG)
        # fh.setFormatter(CustomFormatter('%(asctime)s %(levelname)s %(message)s'))
        fh.setFormatter(CustomFormatter('%(asctime)s [%(process)d] %(levelname)s %(message)s'))
        self.logger.addHandler(fh)

        ch = logging.StreamHandler()
        consoleFormatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(process)d] %(message)s',
            # '%(log_color)s%(asctime)s [%(filename)s:%(lineno)d | %(funcName)s] %(message)s',
            log_colors={
                'D': 'cyan',
                'I': 'green',
                'W': 'yellow',
                'E': 'red',
                'C': 'red,bg_white'
            }
        )
        ch.setFormatter(consoleFormatter)
        if g_log_verbose:
            ch.setLevel(logging.DEBUG)
        else:
            ch.setLevel(logging.INFO)
        self.logger.addHandler(ch)

    def getlog(self):
        return self.logger


g_logger = None
def _get_logger():
    global g_logger
    if g_logger is None:
        with _init_lock:
            if g_logger is None:
                g_logger = Log()
    return g_logger

def _makeMsg(*param):
    msg = ""
    for p in param:
        if isinstance(p, float):
            msg += "%0.3f " % p
        else:
            msg += str(p) + " "
        # msg = msg.encode("utf-8").decode("gbk")
    return msg.rstrip()

def debug(*param):
    _get_logger().getlog().debug(_makeMsg(*param))

def info(*param):
    _get_logger().getlog().info(_makeMsg(*param))

def warn(*param):
    _get_logger().getlog().warning(_makeMsg(*param))

def error(*param):
    _get_logger().getlog().error(_makeMsg(*param))

def critical(*param):
    msg = _makeMsg(*param)
    _get_logger().getlog().critical(msg)
    showMsgBox("critical", msg)
    # raise RuntimeError('critical: ' + msg)

info("=====================================")
info("===============start=================")

############################################################

def test_msgbox():
    import sys
    app = QApplication(sys.argv)
    critical("===critical===")

if __name__ == '__main__':
    # test()
    test_msgbox()
