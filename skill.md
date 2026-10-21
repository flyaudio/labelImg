# 运行环境
1，通过本机的anaconda powershell打开conda环境；
2，通过命令（conda activate labelme）激活对应python环境
3，文件目录是 D:\files\github\labelImg
4，顶层运行命令是 python.exe .\labelImg.py
5，pyinstall打包后的运行方式： 把dist文件夹下的labelImg.exe拷贝覆盖到labeltask文件夹，然后再labeltask文件夹下运行 ./labelImg.exe
6,每个目录下的setup.py的作用是，把顶层目录（sys.path.append(getRootDir())）加入当前运行环境，目的是为了能在*_test.py文件目录直接运行*_test.py文件


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
4、手动借鉴了X-AnyLabeling的代码，但未完成，未验证

# 程序打包
在D:\files\github\labelImg目录下，运行
pyinstall labelimg.spec -y


# 文件生成
pyuic6 auto_labeling.ui -o ui_auto_labeling.py


现在我需要增加一个开关服务的机制，目的是让labelimg能开/关远程服务器的label-server

# 远程服务器
远程服务器运行的是 X-AnyLabeling-Server
这个服务端的程序我是通过docker部署在远程的ubuntu22.04服务器，
启动方式是：
在ubuntu22.04中
xhost +
docker start anylabel
docker exec -it anylabel bash
cd /home/znzz/ma/X-AnyLabeling-Server
uvicorn app.main:app --host 0.0.0.0 --port 8000
需要把上述启动命令写进一个start_x-anylabeling-server.sh脚本中

在labelimg（客户端）中，在“服务器设置” -> "远程服务器设置"对话中，增加：
1、“测试连接”功能，测试用户输入的连接是否可达（默认http://192.168.31.5:8000）
2、“启动远程服务器”/“关闭远程服务器”功能。
远程服务器开机后默认启动一个主服务（label_server），该服务默认不占用gpu资源。
收到labelimg发来的启动命令后，label_server打印收到的信息并用新进程启动start_x-anylabeling-server.sh
收到labelimg发来的关闭命令后，label_server打印收到的信息并结束start_x-anylabeling-server.sh对应的进程，进程解释后，所占用的gpu资源全部释放。

阅读上述要求，列出你是如何实现这些功能？使用了哪些技术栈？ 优点是什么？



# todo
1、采纳X-AnyLabeling的大模型辅助标注的功能，保持labelimg轻量化（不在labelimg中部署大模型），为labelimg增加remote-server辅助标注功能采用client-server架构，远端服务器部署X-AnyLabeling-Server（已经部署 ，接入链接是http://192.168.31.5:8000）


2、支持mask标注


