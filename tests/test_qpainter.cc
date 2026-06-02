#include <QApplication>
#include <QWidget>
#include <QPainter>
#include <QPixmap>

class MyWidget : public QWidget {
protected:
   void paintEvent(QPaintEvent *) override {
       QPainter painter(this);
       QPixmap pixmap(":/images/sample.jpg"); // 加载资源图片
       painter.drawPixmap(0, 0, pixmap); // 在窗口左上角绘制图片
   }
};
int main(int argc, char *argv[]) {
   QApplication app(argc, argv);
   MyWidget window;
   window.resize(400, 300);
   window.show();
   return app.exec();
}