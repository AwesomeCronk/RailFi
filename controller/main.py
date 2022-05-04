from PyQt6.QtWidgets import QApplication, QWidget, QListWidget, QListWidgetItem
import sys

class mainWindow(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.initUI()
        self.locomotivesList.addItem('USSC #148')

    def initUI(self):
        self.setGeometry(100, 100, 800, 500)
        self.locomotivesList = QListWidget(self)
        self.locomotivesList.itemClicked.connect(self.selectLocomotive)
        self.locomotivesList.setGeometry(5, 5, 300, 490)

    def selectLocomotive(self, caller):
        print('Selecting locomotive "{}"'.format(caller.text()))

if __name__ == '__main__':
    app = QApplication([])
    window = mainWindow()
    window.show()
    sys.exit(app.exec())
