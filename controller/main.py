import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QListWidget, QLabel,
    QSlider, QPushButton
)

class locomotive():
    def __init__(self, name, socket):
        self.name = name
        self.socket = socket

    

class mainWindow(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.initUI()
        # self.locomotivesList.addItem('USSC #148')
        # self.locomotivesList.addItem('UP #4014')
        # self.locomotivesList.addItem('BHC #110')

    def initUI(self):
        padding = 5
        self.resize(400, 400)
        self.setWindowTitle('RailFi controller')
        self.locomotivesList = QListWidget(self)
        self.locomotivesList.currentItemChanged.connect(self.selectLocomotive)
        self.locomotivesList.move(padding, padding)
        self.locomotivesList.resize(120, self.height() - (2 * padding))
        
        self.locomotiveName = QLabel(self)
        self.locomotiveName.setText('<locomotive>')
        self.locomotiveName.move(self.locomotivesList.width() + (2 * padding), padding)
        self.locomotiveName.resize(160, 40)

        self.headlightButton = QPushButton(self)
        self.headlightButton.setText('Headlight: OFF')
        self.headlightButton.move(self.locomotivesList.width() + (2 * padding), self.locomotiveName.height() + (2 * padding))
        
        self.rearlightButton = QPushButton(self)
        self.rearlightButton.setText('Rear light: OFF')
        self.rearlightButton.move(self.locomotivesList.width() + (2 * padding), self.locomotiveName.height() + self.headlightButton.height() + (3 * padding))

        self.throttleLabel = QLabel(self)
        self.throttleLabel.setText('Throttle: 0%')
        self.throttleLabel.move(self.locomotivesList.width() + (2 * padding), self.locomotiveName.height() + self.headlightButton.height() + self.rearlightButton.height() + (4 * padding))
        
        self.throttleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.throttleSlider.move(self.locomotivesList.width() + (2 * padding), self.locomotiveName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + (5 * padding))
        self.throttleSlider.resize(30, 100)

        self.directionButton = QPushButton(self)
        self.directionButton.setText('Direction: FWD')
        self.directionButton.move(self.locomotivesList.width() + (2 * padding), self.locomotiveName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + self.throttleSlider.height() + (6 * padding))

    def selectLocomotive(self, caller):
        print('Selecting locomotive "{}"'.format(caller.text()))

if __name__ == '__main__':
    app = QApplication([])
    window = mainWindow()
    window.show()
    sys.exit(app.exec())
