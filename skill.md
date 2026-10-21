# 运行环境
1，通过本机的anaconda powershell打开conda环境；
2，通过命令（conda activate labelme）激活对应python环境
3，文件目录是 D:\files\github\labelImg
4，顶层运行命令是 python.exe .\labelImg.py
5，pyinstall打包后的运行方式： 把dist文件夹下的labelImg.exe拷贝覆盖到labeltask文件夹，然后再labeltask文件夹下运行 ./labelImg.exe


# 代码情况
这个工程是labelimg代码的克隆。 改动如下：
1、将pyqt5升级到pyqt6
2、在编辑菜单增加了
	change_to_OK1
	change_to_CQ
	change_to_BD
	change_to_NG1
	的功能
3、在菜单栏增加了tool->增强的功能，此功能独立

# 程序打包
在D:\files\github\labelImg目录下，运行
pyinstall labelimg.spec -y


# 文件生成
pyuic6 auto_labeling.ui -o ui_auto_labeling.py