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
        'ACK',
        'END_CONVERSATION',
        'ERROR'
    ]

    def __init__(self, name, conn):
        self.name = name
        self.conn = conn
        self.activeConversations = []
        self.inBuffer = b''

        self.lights = [False, False]

        print('Loco interface "{}" initialized'.format(self.name))

        # Synchronize by sending GET_**** packets and setting variables with responses
        # print('Loco interface "{}" synchronized'.format(self.name))
    
    def genPacket(self, packetType, conversationID, payload):
        print('Generating packet')        
        binary = b'RF-'
        
        # Get packet type as int
        if isinstance(packetType, str):
            if packetType in self.packetTypes: packetType = self.packetTypes.index(packetType)
            else: raise ValueError('Invalid packet type "{}"'.format(packetType))
        elif isinstance(packetType, int): pass
        else: raise ValueError('Invalid packet type "{}"'.format(packetType))

        # Generate a new conversation ID
        if conversationID == -1: conversationID = self.activeConversations[-1] + 2 if 0 < len(self.activeConversations) < 2 ** 31 else 0
        if not conversationID in self.activeConversations: self.activeConversations.append(conversationID)

        binary += int.to_bytes(packetType, 1, 'big')
        binary += int.to_bytes(conversationID, 4, 'big')
        if len(payload) >= 2 ** 16: raise ValueError('Payload too long')
        binary += int.to_bytes(len(payload), 2, 'big')
        binary += payload

        print('Packet generation results:', binary)
        return binary

    def send(self, data):
        print('Sending packet data')
        self.conn.sendall(data)

    def recv(self, maxPackets=-1, clearConversations=True):
        print('Receiving packets')
        try: self.inBuffer += self.conn.recv(4096)
        except socket.timeout: pass
        packets = []
        while True:
            # print('inBuffer:', self.inBuffer)
            print('Decoding packet from buffer')
            if len(self.inBuffer) < 10:
                print('Attempting to receive more data')
                try: self.inBuffer += self.conn.recv(4096)
                except socket.timeout: pass

            if len(self.inBuffer) < 10:
                print('Not enough data in buffer')
                print(self.inBuffer)
                break

            prefix = self.inBuffer[0:3]
            if prefix != b'RF-':
                print('Found data that is not a packet, discarding byte')

            packetType = int.from_bytes(self.inBuffer[3:4], 'big')
            conversationID = int.from_bytes(self.inBuffer[4:8], 'big')
            payloadSize = int.from_bytes(self.inBuffer[8:10], 'big')
            # print('prefix:', prefix)
            # print('packetType:', self.packetTypes[packetType])
            # print('conversationID:', conversationID)
            # print('payloadSize:', payloadSize)
            
            if len(self.inBuffer) < payloadSize + 10:
                print('Packet incomplete, waiting to receive more data in buffer')
                break

            payload = self.inBuffer[10:payloadSize + 10]
            # print('payload:', payload)

            self.inBuffer = self.inBuffer[payloadSize + 10:]
            print('Decoded packet:', (packetType, conversationID, payload))
            if clearConversations and self.packetTypes[packetType] == 'END_CONVERSATION': self.activeConversations.remove(conversationID); print('Conversation {} ended'.format(conversationID))
            else: packets.append((packetType, conversationID, payload))

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
        
        self.throttleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.throttleSlider.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + (5 * padding))
        self.throttleSlider.resize(30, 100)

        self.directionButton = QPushButton(self)
        self.directionButton.setText('Direction: FWD')
        self.directionButton.move(self.locosList.width() + (2 * padding), self.locoName.height() + self.headlightButton.height() + self.rearlightButton.height() + self.throttleLabel.height() + self.throttleSlider.height() + (6 * padding))

    
    ## Loco Control ##
    def selectLoco(self, caller):
        print('Selecting loco "{}"'.format(caller.text()))
        for loco in self.locos:
            if loco.name == caller.text():
                self.selectedLoco = loco

    def toggleHeadlight(self):
        if self.selectedLoco is None: return
        print('===== toggleHeadlight =====')
        self.selectedLoco.send(self.selectedLoco.genPacket('SET_LIGHT', -1, b'\x00' + (b'\x00' if self.selectedLoco.lights[0] else b'\x01')))
        self.selectedLoco.recv()
        
        self.selectedLoco.send(self.selectedLoco.genPacket('GET_LIGHT', -1, b'\x00'))
        conversationID = self.selectedLoco.activeConversations[-1]
        packets = self.selectedLoco.recv(); print('packets:', packets)
        headlightStatus = None
        for packet in packets:
            if packet[1] == conversationID:
                if self.selectedLoco.packetTypes[packet[0]] == 'ACK':
                    headlightStatus = bool(int.from_bytes(packet[2], 'big'))
                    break
            else: print('Unrelated packet:', packet)

        if headlightStatus is None:
            print('Did not find a GET_LIGHT ACK packet')
        else:
            self.selectedLoco.lights[0] = headlightStatus
            self.headlightButton.setText('Headlight: ' + ('ON' if headlightStatus else 'OFF'))
            print('Updated headlight status')


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
            conn.settimeout(0.5)
            self.locos.append(locomotive(str(addr), conn))
            self.locosList.addItem(self.locos[-1].name)
        except socket.timeout:
            print('Loco did not connect in time')

        self.processingConnection = False


if __name__ == '__main__':
    app = QApplication([])
    window = mainWindow()
    window.show()
    sys.exit(app.exec())
