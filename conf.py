#coding=utf-8
import sys,os
import time
import configparser
import log
# import setup
# import utils.encry as encry

def is_python3():
    return sys.version[0] == '3'

assert is_python3()

def getRootDir():
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./")
    return root

g_cfg = None
def _get_cfg():
    global g_cfg
    if g_cfg is None:
        g_cfg = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        filename = os.path.join(getRootDir(), "debug.cfg")
        if not os.path.exists(filename):
            msg = "debug.cfg not exist"
            log.critical(msg)
            raise FileNotFoundError(msg)
        #     encry.encryptFile()
        # else:
        #     filename = encry.getFilename()
        # assert os.path.exists(filename)
        # print("cfg filename:", filename)
        g_cfg.read(filename)
    return g_cfg

def getlist(section,option,default=None):
    if default is not None:
        assert isinstance(default, list)
    if _get_cfg().has_section(section) and _get_cfg().has_option(section, option):
        text = _get_cfg().get(section,option)
        if "," in text:
            return text.split(",")
        else:
            return [line.strip() for line in _get_cfg().get(section, option).splitlines() if line.strip()]
    else:
        print("{}.{} empty".format(section, option))
        return default

def getstr(section,option,default=None):
    if default is not None:
        assert isinstance(default, str)
    if _get_cfg().has_section(section) and _get_cfg().has_option(section, option):
        return _get_cfg().get(section,option)
    else:
        print("{}.{} empty".format(section, option))
        return default

def getint(section,option,default=None):
    if default is not None:
        assert isinstance(default, int)
    if _get_cfg().has_section(section) and _get_cfg().has_option(section, option):
        return _get_cfg().getint(section,option)
    else:
        print("{}.{} empty".format(section, option))
        return default

def getfloat(section,option,default=None):
    if default is not None:
        assert isinstance(default, float)
    if _get_cfg().has_section(section) and _get_cfg().has_option(section, option):
        return _get_cfg().getfloat(section,option)
    else:
        print("{}.{} empty".format(section, option))
        return default

def getbool(section,option,default=None):
    if default is not None:
        assert isinstance(default, bool)
    if _get_cfg().has_section(section) and _get_cfg().has_option(section, option):
        return _get_cfg().getboolean(section,option)
    else:
        print("{}.{} empty".format(section, option))
        return default

##################################################################
def test_get():
    # r = getbool("test_bool","a")
    # print(r)
    # r = getlist("camera", "ids")
    # print(type(r), r)
    # r = getlist("camera", "test")
    # print(type(r), r)
    r = getstr("gpu", "device")
    print(type(r), r)
    #
    # source = getstr("cnn", "source", "empty")
    # print(source.isnumeric(), source)


def test():
    test_get()


if __name__ == '__main__':
    test()