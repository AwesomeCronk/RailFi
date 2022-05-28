import sys, socket, time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QListWidget, QLabel,
    QSlider, QPushButton
)

class loco():
    def __init__(self, name, socket):
        self.name = name
        self.socket = socket

# Thread to manage incoming connections on the traffic socket (There should only ever be *ONE* instance of this running at a time!)
class trafficCop(QThread):
    newConnection = pyqtSignal(tuple)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent, *args)
        print('Traffic cop initialized')

    def run(self):
        while self.parent().runFlag:
            
            while self.parent().processingConnection:
                if not self.parent().runFlag: break
                print('Traffic cop waiting for parent to finish processing last connection...')
                time.sleep(0.1)

            try:
                conn, addr = self.parent().trafficSocket.accept()
                conn.sendall(b'\x00\x00')
                if conn.recv(2) != b'\x00\x00':
                    conn.close()
                    continue

                dedicatedPort = 4001 + len(self.parent().locos)
                conn.sendall(int.to_bytes(dedicatedPort, 2, 'big'))
                print('Directed new loco to port {}'.format(dedicatedPort))

                conn.close()
                self.newConnection.emit((dedicatedPort,))

                # while not self.parent().processingConnection:
                #     if not self.parent().runFlag: break
                #     print('Traffic cop waiting for parent to begin processing last connection...')
                #     time.sleep(0.1)

            except socket.timeout:
                pass
        self.finished.emit()

class mainWindow(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.runFlag = True
        self.processingConnection = False

        self.initUI()

        # Traffic cop setup (for directing locos to dedicated sockets when they connect)
        self.trafficSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.trafficSocket.bind(('', 4000))
        self.trafficSocket.listen(5)
        self.trafficSocket.settimeout(1.0)
        self.trafficCop = trafficCop(self)
        self.trafficCop.newConnection.connect(self.newLocoConnecting)
        self.trafficCop.start()
        print('Started traffic cop')

        self.locos = []     # Contains tuples of (port, connection, name)


    def closeEvent(self, event):
        self.runFlag = False
        print('Waiting for threads to stop')
        time.sleep(1)
        event.accept()

    ## UI functions ##
    def initUI(self):
        padding = 5
        self.resize(400, 400)
        self.setWindowTitle('RailFi controller')
        self.locosList = QListWidget(self)
        self.locosList.currentItemChanged.connect(self.selectLoco)
        self.locosList.move(padding, padding)
        self.locosList.resize(120, self.height() - (2 * padding))
        
        self.locoName = QLabel(self)
        self.locoName.setText('<loco>')
        self.locoName.move(self.locosList.width() + (2 * padding), padding)
        self.locoName.resize(160, 40)

        self.headlightButton = QPushButton(self)
        self.headlightButton.setText('Headlight: OFF')
        self.headlightButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + (2 * padding))
        
        self.rearlightButton = QPushButton(self)
        self.rearlightButton.setText('Rear light: OFF')
        self.rearlightButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + (3 * padding))

        self.throttleLabel = QLabel(self)
        self.throttleLabel.setText('Throttle: 0%')
        self.throttleLabel.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + (4 * padding))
        
        self.throttleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.throttleSlider.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + (5 * padding))
        self.throttleSlider.resize(30, 100)

        self.directionButton = QPushButton(self)
        self.directionButton.setText('Direction: FWD')
        self.directionButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + self.throttleSlider.height() + (6 * padding))

    def selectLoco(self, caller):
        print('Selecting loco "{}"'.format(caller.text()))

    ## Networking ##
    def newLocoConnecting(self, args):
        dedicatedPort = args[0]
        print('Loco connecting to port {}'.format(dedicatedPort))
        self.processingConnection = True
        dedicatedSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dedicatedSocket.bind(('', dedicatedPort))
        dedicatedSocket.listen(1)
        dedicatedSocket.settimeout(1.0)

        try:
            conn, addr = dedicatedSocket.accept()
            self.locos.append((dedicatedPort, conn, addr))
        except socket.timeout:
            print('Loco did not connect in time')

        self.processingConnection = False


if __name__ == '__main__':
    app = QApplication([])
    window = mainWindow()
    window.show()
    sys.exit(app.exec())
