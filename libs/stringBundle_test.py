import os
import locale
import setup
import libs.stringBundle
from libs.stringBundle import StringBundle


def test():
	print("LANG=", os.getenv('LANG'))
	print("LC_ALL=", os.getenv('LC_ALL'))
	print("", locale.getdefaultlocale())
	r = StringBundle.get_bundle("")
	print("eng=", r.id_to_message)
	r = StringBundle.get_bundle("zh_CN")
	print("ch=", r.id_to_message)
	r = StringBundle.get_bundle("ja_JP")
	print("jp=", r.id_to_message)


def test_create_lookup_fallback_list():
	a = libs.stringBundle.create_lookup_fallback_list("zh_CN")
	print(a)


# def test_load_bundle():
# 	StringBundle.get_bundle().__test


if __name__ == '__main__':
	test()
	# test_create_lookup_fallback_list()
	# test_load_bundle()
