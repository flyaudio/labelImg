import unittest
from unittest import TestCase
import setup
from labelImg import get_main_app


class TestMainWindow(TestCase):

    app = None
    win = None

    def setUp(self):
        self.app, self.win = get_main_app()

    def tearDown(self):
        self.win.close()
        self.app.quit()

    def test_noop(self):
        pass
if __name__ == '__main__':
    unittest.main()
