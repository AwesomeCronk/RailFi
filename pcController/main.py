import sys, socket, time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QListWidget, QLabel,
    QSlider, QPushButton
)


class locomotive():
    packetTypes = [
        'SET_THROTTLE',
        'GET_THROTTLE',
        'SET_LIGHT',
        'GET_LIGHT',
        'E_STOP',
        'ACKNOWLEDGE',
        'ERROR'
    ]

    def __init__(self, name, conn):
        self.name = name
        self.conn = conn
        self.inBuffer = b''

        self.throttle = 0
        self.lights = [False, False]

        print('Loco interface "{}" initialized'.format(self.name))

        # Synchronize by sending GET_**** packets and setting variables with responses
        # print('Loco interface "{}" synchronized'.format(self.name))
    
    def genPacket(self, packetType, payload):
        print('Generating packet')        
        binary = b'RF-'
        
        # Get packet type as int
        if isinstance(packetType, str):
            if packetType in self.packetTypes: packetType = self.packetTypes.index(packetType)
            else: raise ValueError('Invalid packet type "{}"'.format(packetType))
        elif isinstance(packetType, int): pass
        else: raise ValueError('Invalid packet type "{}"'.format(packetType))

        binary += int.to_bytes(packetType, 1, 'big')
        if len(payload) >= 2 ** 16: raise ValueError('Payload too long')
        binary += int.to_bytes(len(payload), 2, 'big')
        binary += payload

        print('Packet generation results:', binary)
        return binary

    def send(self, packetType, payload):
        print('Sending packet')
        self.conn.sendall(self.genPacket(packetType, payload))
        print('Sent packet')

    def recv(self, numPackets, maxLoops=10):
        inBuffer = self.inBuffer; conn = self.conn
        print('Receiving packets')
        try: inBuffer += conn.recv(4096)
        except OSError: pass
        packets = []
        for i in range(maxLoops):
            # print('inBuffer:', inBuffer)
            if len(inBuffer) < 6:
                # print('Attempting to receive more data')
                try: inBuffer += conn.recv(4096)
                except OSError: pass

            if len(inBuffer) >= 6:
                # print('Decoding packet from buffer')
                prefix = inBuffer[0:3]
                if prefix != b'RF-':
                    # print('Found data that is not a packet, discarding first byte in buffer')
                    inBuffer = inBuffer[1:]

                packetType = int.from_bytes(inBuffer[3:4], 'big')
                payloadSize = int.from_bytes(inBuffer[4:6], 'big')
                
                if len(inBuffer) < payloadSize + 6:
                    # print('Packet incomplete, waiting to receive more data in buffer')
                    break

                payload = inBuffer[6:payloadSize + 6]

                inBuffer = inBuffer[payloadSize + 6:]
                # print('Decoded packet:', (packetType, payload))
                packets.append((packetType, payload))

                if len(packets) >= numPackets: break

            # else:
            #     print('Not enough data in buffer')
        
        return packets


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

                dedicatedPort = self.parent().trafficPort + 1   # Start at the first port after the traffic port
                dedicatedSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Walk up port numbers until one works
                bound = False
                while not bound:
                    try: dedicatedSocket.bind(('', dedicatedPort)); bound = True
                    except OSError: dedicatedPort += 1
                dedicatedSocket.listen(1)
                dedicatedSocket.settimeout(1.0)

                conn.sendall(int.to_bytes(dedicatedPort, 2, 'big'))
                print('Directed new loco to port {}'.format(dedicatedPort))

                conn.close()
                self.newConnection.emit((dedicatedSocket,))

                # while not self.parent().processingConnection:
                #     if not self.parent().runFlag: break
                #     print('Traffic cop waiting for parent to begin processing last connection...')
                #     time.sleep(0.1)

            except OSError:
                pass
        self.finished.emit()


class mainWindow(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.runFlag = True
        self.processingConnection = False
        self.trafficPort = 4000

        self.initUI()

        # Traffic cop setup (for directing locos to dedicated sockets when they connect)
        self.trafficSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Walk up port numbers until one works
        bound = False
        while not bound:
            try: self.trafficSocket.bind(('', self.trafficPort)); bound = True
            except OSError: self.trafficPort += 1
        self.trafficSocket.listen(5)
        self.trafficSocket.settimeout(0.5)
        self.trafficCop = trafficCop(self)
        self.trafficCop.newConnection.connect(self.newLocoConnecting)
        self.trafficCop.start()
        print('Started traffic cop')

        self.locos = []     # Contains instances of loco
        self.selectedLoco = None

    def closeEvent(self, event):
        self.runFlag = False
        print('Waiting for threads to stop')
        time.sleep(0.6)
        event.accept()

    def newLocoConnecting(self, args):
        dedicatedSocket = args[0]
        print('Loco connecting')
        self.processingConnection = True

        try:
            conn, addr = dedicatedSocket.accept()
            conn.settimeout(0.2)
            self.locos.append(locomotive(str(addr), conn))
            self.locosList.addItem(self.locos[-1].name)
        except OSError:
            print('Loco did not connect in time')

        self.processingConnection = False


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
        self.headlightButton.clicked.connect(self.toggleHeadlight)
        
        self.rearlightButton = QPushButton(self)
        self.rearlightButton.setText('Rear light: OFF')
        self.rearlightButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + (3 * padding))

        self.throttleLabel = QLabel(self)
        self.throttleLabel.setText('Throttle: 0%')
        self.throttleLabel.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + (4 * padding))
        self.throttleLabel.resize(160, 40)
        
        self.throttleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.throttleSlider.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + (5 * padding))
        self.throttleSlider.resize(30, 100)
        self.throttleSlider.valueChanged[int].connect(self.setThrottle)

        self.directionButton = QPushButton(self)
        self.directionButton.setText('Direction: FWD')
        self.directionButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + self.throttleSlider.height() + (6 * padding))
        self.directionButton.clicked.connect(self.reverse)

    
    ## Loco Control ##
    def selectLoco(self, caller):
        print('Selecting loco "{}"'.format(caller.text()))
        for loco in self.locos:
            if loco.name == caller.text():
                self.selectedLoco = loco

    def _setThrottle(self):
        print('Setting throttle to', self.selectedLoco.throttle)

        # Perform a SET_THROTTLE
        self.selectedLoco.send('SET_THROTTLE', int.to_bytes(self.selectedLoco.throttle, 1, 'big', signed=True))
        response = self.selectedLoco.recv(1)[0]
        print('Acknowledged:', locomotive.packetTypes[response[0]] == 'ACKNOWLEDGE')

        # Perform as GET_THROTTLE
        self.selectedLoco.send('GET_THROTTLE', b'')
        response = self.selectedLoco.recv(1)[0]
        print('Acknowledged:', locomotive.packetTypes[response[0]] == 'ACKNOWLEDGE')

        # Update locomotive interface and UI
        throttleStatus = int.from_bytes(response[1], 'big', signed=True)
        if self.selectedLoco.throttle != throttleStatus: print('DISCREPANCY: {} vs {}'.format(self.selectedLoco.throttle, throttleStatus))
        self.selectedLoco.throttle = throttleStatus
        self.throttleLabel.setText('Throttle: {}%'.format(+throttleStatus))
        self.directionButton.setText('Direction: ' + 'FWD' if throttleStatus >= 0 else 'REV')

    def setThrottle(self, value):
        if self.selectedLoco is None: return
        print('===== setThrottle =====')
        self.selectedLoco.throttle = round(value * 1.01) * (1 if self.selectedLoco.throttle >= 0 else -1)
        self._setThrottle()

    def reverse(self):
        if self.selectedLoco is None: return
        print('===== reverse =====')
        self.selectedLoco.throttle *= -1
        self._setThrottle()
        

    def toggleHeadlight(self):
        if self.selectedLoco is None: return
        print('===== toggleHeadlight =====')

        # Perform a SET_LIGHT
        self.selectedLoco.send('SET_LIGHT', b'\x00' + (b'\x00' if self.selectedLoco.lights[0] else b'\x01'))
        response = self.selectedLoco.recv(1)[0]
        print('Acknowledged:', locomotive.packetTypes[response[0]] == 'ACKNOWLEDGE')
        
        # Perform a GET_LIGHT
        self.selectedLoco.send('GET_LIGHT', b'\x00')
        response = self.selectedLoco.recv(1)[0]
        print('Acknowledged:', locomotive.packetTypes[response[0]] == 'ACKNOWLEDGE')
        
        # Update locomotive interface and UI
        headlightStatus = bool(int.from_bytes(response[1], 'big'))
        self.selectedLoco.lights[0] = headlightStatus
        self.headlightButton.setText('Headlight: ' + ('ON' if headlightStatus else 'OFF'))
        print('Updated headlight status')


if __name__ == '__main__':
    app = QApplication([])
    window = mainWindow()
    window.show()
    sys.exit(app.exec())
