#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
from PyQt6 import QtGui
from PyQt6.QtGui import *
from PyQt6.QtCore import *

import setup
import log
import conf
from libs.utils import distance
from libs.geo.point import Point


class Rect(Point):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TYPE = "point"

    def reach_max_points(self):
        assert self.type == self.TYPE
        if len(self.points) >= 1:
            return True
        return False

    def paint(self, painter: QtGui.QPainter):
        if len(self.points) != 1:
            log.critical(
                f"err point num for {self.TYPE}: "
                f"expected 1, got {len(self.points)}"
            )
            return
        super(Point).paint(self, painter)
