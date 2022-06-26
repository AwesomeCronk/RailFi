import sys, time

print('RailFi locomotive firmware booting')

# Bootstrap RailFi to run on a locomotive (uPython device) or on a PC (CPython on Linux or Windows)

# NO_ERROR is a placeholder to ensure that <code number> >= 1
errorCodes = [
    'NO_ERROR',
    'NO_CONFIG_FILE',
    'CONFIG_BAD_SYNTAX',
    'CONFIG_MISSING_ENTRY'
]
currentError = 0
configRequiredEntries = [
    'road-name',
    'road-acronym',
    'loco-number',
    'loco-model',
    'password',
    'model-manufacturer'
]
config = {}
throttle = 0


## Emulation handling ##
bootMode = 'real' if sys.implementation.name == 'micropython' else 'emulator' if sys.implementation.name == 'cpython' else 'unknown'

if bootMode == 'real':
    time.sleep_ms(1000)
    print('Boot mode: real')

    from machine import Pin, freq

    bootPin = Pin(0, Pin.IN)
    if bootPin.value() == 0:
        print('Booting to REPL')
        sys.exit()

    import network
    import usocket as socket
    import gc
    
    freq(240000000)
    gc.collect()

    # Sleep for t seconds
    def sleep(t):
        time.sleep_ms(int(t * 1000))


    # Hardware connections
    headLight = Pin(32, Pin.OUT)
    rearLight = Pin(33, Pin.OUT)
    lights = [headLight, rearLight]

    def setLight(light, value):
        lights[light].value(value)

    def getLight(light):
        return lights[light].value()

    class motorInterface():
        def __init__(self):
            self.SDI = Pin(19, Pin.IN)
            self.SDO = Pin(21, Pin.OUT, value=0)
            self.SCK = Pin(22, Pin.OUT, value=0)
            self.EN = Pin(23, Pin.OUT, value=0)
            self.CSN = Pin(18, Pin.OUT, value=1)

        def enable(self): self.EN.value(1)
        def disable(self): self.EN.value(0)
        def select(self): self.CSN.value(0)
        def deselect(self): self.CSN.value(1)

        def interact(self, rw, address, labt, data):
            # Prepare the command
            bits = [0] * 16
            bits[0] = 1
            bits[1] = labt  # Should be 1 in all known configurations
            for i in (4, 3, 2, 1, 0):
                bits[2 + i] = address // (2 ** i)
                address = address % (2 ** i)
            bits[7] = rw
            for i in (7, 6, 5, 4, 3, 2, 1, 0):
                bits[8 + i] = data // (2 ** i)
                data = data % (2 ** i)
            print('Preparing to send', ''.join([str(bit) for bit in bits]))

            # Interact with the driver chip
            self.select()
            globalErrorFlag = self.SDI.value()
            if globalErrorFlag: print('GEF set')

            for i in range(16):
                self.SCK.value(1)
                self.SDO.value(bits[i])
                self.SCK.value(0)
                bits[i] = self.SDI.value()

            self.deselect()
            print('Responded with', ''.join([str(bit) for bit in bits]))


    motor = motorInterface()

    def setThrottle(value):
        command = b'00' # NOT AN ACTUAL COMMAND
        response = bytearray(len(command))
        motor.write_readinto(command, response)
        print(response)

    
    ap = None   # DO NOT reference outside of platform abstraction functions!!!
    
    def startAP(apName):
        global ap
        ap = network.WLAN(network.AP_IF)
        ap.config(essid=apName)
        ap.config(max_clients=5)
        # ap.ifconfig(('192.168.100.100', '255.255.255.0', '192.168.100.100', '0.0.0.0'))
        ap.active(True)
        return ap.config('essid'), ap.ifconfig()[0]

    def stopAP():
        ap.active(False)
        del ap
        gc.collect()

    sta = None  # DO NOT reference outside of platform abstraction functions!!!
    
    def startSTA(ssid, password):
        global sta
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.scan()
        sta.connect(ssid, password)
        for i in range(5):
            if sta.isconnected():
                break
            print('Waiting for STA to connect...')
            time.sleep(0.5)
        print(sta.ifconfig())

    def stopSTA():
        sta.active(False)
        del sta
        gc.collect()

elif bootMode == 'emulator':
    print('Boot mode: emulator')

    import socket

    sleep = time.sleep

    # Virtual hardware connections
    lights = [0, 0]

    def setLight(light, value):
        global lights
        lights[light] = value
        # print('Light "{}" set to {}'.format(light, value))
        displayHardware()

    def getLight(light):
        return lights[light]


    def startAP(apName):
        print('Pretending to start access point "{}"'.format(apName))
        return '<wifi>', '<ip address>'

    def stopAP():
        print('Pretending to stop access point')

    def startSTA(ssid, password):
        print('Pretending to start station and connect to {}'.format(ssid))

    def stopSTA():
        print('Pretending to stop station')


    # Hardware display
    def displayHardware():
        print('Lights: {} {} | Motor: {}% | Error: {}'.format('H' if lights[0] else ' ', 'R' if lights[1] else ' ', throttle, errorCodes[currentError]))

else:
    raise RuntimeError('Implementation "{}" not recognized'.format(sys.implementation.name))


# Get current time in seconds
def now():
    return time.time_ns() / 1000000000


## Error handling ##
def raiseError(code):
    global currentError
    if code == 0 or code == 'NO_ERROR':
        return
    
    if isinstance(code, int):
        codeNum = code
        codeName = errorCodes[code]
    else:
        codeName = code
        codeNum = errorCodes.index(code)

    currentError = codeNum
    print('ERROR {}: {}'.format(codeNum, codeName))

    setLight('headlight', 0)
    setLight('rearlight', 0)
    sleep(0.5)

    while True:
        # Two quick blinks to indicate errors
        for i in range(4):
            setLight('headlight', 1 - getLight('headlight'))
            setLight('rearlight', 1 - getLight('rearlight'))
            sleep(0.1)

        # Blink <codeNum> times
        for i in range(codeNum * 2):
            sleep(0.4)
            setLight('headlight', 1 - getLight('headlight'))
            setLight('rearlight', 1 - getLight('rearlight'))

        sleep(1)


## Config loading ##
def getConfig(configPath='config.txt'):
    global config
    # Open the config file
    try:
        with open(configPath, 'r') as configFile:
            configText = configFile.read()
    except:
        raiseError('NO_CONFIG_FILE')

    # Read the config data
    try:
        config = {}
        configLines = configText.split('\n')
        for line in configLines:
            field, value = line.split(' : ')
            config[field] = value
    except:
        raiseError('CONFIG_BAD_SYNTAX')

    # Check for missing entries
    for key in configRequiredEntries:
        if not key in config.keys():
            raiseError('CONFIG_MISSING_ENTRY')


## Controller connection ##
controllerSocket = None

def discoverController():
    print('===== Entering discovery mode =====')
    # Host network RailFi_<loco name>_<loco number>
    apName = 'RailFi_Discover_' + config['road-acronym'] + '_' + config['loco-number']
    port = 2000
    ssid, locoIP = startAP(apName)
    print('AP Info:\nSSID: {}\nLoco IP: {}\nLoco Handshake Port: {}'.format(ssid, locoIP, port))

    # Serve a socket for controllers to connect to
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', port))
    sock.listen(5)
    print('Socket bound')

    # if bootMode == 'real':
    #     print(gc.mem_free())

    haveController = False
    while not haveController:
        print('Waiting for connection...')
        conn, addr = sock.accept()
        # conn.settimeout(0.25)     # Uncomment if a timeout proves necessary
        print('Controller connected for discovery')

        # First contact: Controller sends 0xffff, Locomotive responds 0xffff
        firstContact = conn.recv(2)
        if firstContact != b'\xff\xff':
            print('First contact incorrect')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
        conn.send(b'\xff\xff')
        print('First contact correct')

        # Get password
        try:
            password = conn.recv(16).decode('UTF-8')
        except UnicodeError:
            print('Bad password data')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
            
        # Test password
        if password != config['password']:
            print('Password incorrect')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
        conn.send(b'\xff\xff')
        print('Password correct')

        # Get AP info (ssid, password) and API info (addr, port)
        ssid = conn.recv(32).decode('utf-8')
        password = conn.recv(16).decode('utf-8')
        addr = conn.recv(16).decode('utf-8')
        port = int.from_bytes(conn.recv(2), 'big')
        conn.send(b'\xff\xff')
        conn.close()
        stopAP()
        haveController = True
        print('Discovery complete, controller info obtained')
        return (ssid, password, addr, port)

def connectController(ssid, password, addr, trafficPort):  # Establish a connection to the controller and globalize the socket, return bool of success
    global controllerSocket

    print('===== Connecting to controller "{}" on access point "{}" ====='.format(addr, ssid))
    startSTA(ssid, password)
    trafficSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    trafficSocket.settimeout(1.0)
    for i in range(5):
        try:
            trafficSocket.connect((addr, trafficPort))
            break
        except OSError:
            print('Connection timed out')
            if i == 4:
                print('Connection timed out too many times')
                return False
    print('Connected to traffic cop')

    if trafficSocket.recv(2) != b'\x00\x00':
        trafficSocket.send(b'\xde\xad\xbe\xef')
        trafficSocket.close()
        print('First contact incorrect')
        return False
    trafficSocket.sendall(b'\x00\x00')
    print('Completed first contact')

    dedicatedPort = int.from_bytes(trafficSocket.recv(2), 'big')
    trafficSocket.sendall(b'\x00\x00')
    print('Directed to port {}'.format(dedicatedPort))

    trafficSocket.close()
    print('Disconnected from traffic cop')

    controllerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Pausing to let controller initialize dedicated socket')
    sleep(0.5)
    controllerSocket.connect((addr, dedicatedPort))
    controllerSocket.settimeout(0.5)
    print('Connected to controller')
    return True
    

## Main section ##
packetTypes = [
    'SET_THROTTLE',
    'GET_THROTTLE',
    'SET_LIGHT',
    'GET_LIGHT',
    'E_STOP',
    'ACKNOWLEDGE',
    'ERROR'
]

inBuffer = b''

def genPacket(packetType, payload):
    print('Generating packet')        
    binary = b'RF-'
    
    # Get packet type as int
    if isinstance(packetType, str):
        if packetType in packetTypes: packetType = packetTypes.index(packetType)
        else: raise ValueError('Invalid packet type "{}"'.format(packetType))
    elif isinstance(packetType, int): pass
    else: raise ValueError('Invalid packet type "{}"'.format(packetType))

    binary += int.to_bytes(packetType, 1, 'big')
    if len(payload) >= 2 ** 16: raise ValueError('Payload too long')
    binary += int.to_bytes(len(payload), 2, 'big')
    binary += payload

    print('Packet generation results:', binary)
    return binary

def send(packetType, payload):
    print('Sending packet')
    controllerSocket.sendall(genPacket(packetType, payload))
    print('Sent packet')

def recv(numPackets, maxLoops=10):
    global inBuffer; conn = controllerSocket
    print('Receiving packets')
    # try: inBuffer += conn.recv(4096)
    # except OSError: pass
    packets = []
    for i in range(maxLoops):
        # print('inBuffer:', inBuffer)
        if len(inBuffer) < 6:
            print('Attempting to receive more data')
            try: inBuffer += conn.recv(4096)
            except OSError: pass

        if len(inBuffer) >= 6:
            print('Decoding packet from buffer')
            prefix = inBuffer[0:3]
            if prefix != b'RF-':
                # print('Found data that is not a packet, discarding first byte in buffer')
                inBuffer = inBuffer[1:]

            packetType = int.from_bytes(inBuffer[3:4], 'big')
            payloadSize = int.from_bytes(inBuffer[4:6], 'big')
            
            if len(inBuffer) < payloadSize + 6:
                print('Packet incomplete, waiting to receive more data in buffer')
                break

            payload = inBuffer[6:payloadSize + 6]

            inBuffer = inBuffer[payloadSize + 6:]
            print('Decoded packet:', (packetType, payload))
            packets.append((packetType, payload))

            if len(packets) >= numPackets: break

        # else:
        #     print('Not enough data in buffer')
    
    return packets

def main():
    print('===== Beginning main operation =====')
    # Initialization

    # Operation
    while True:
        packets = recv(1)
        if len(packets):
            packet = packets[0]
            print('===== Processing command packet =====')
            startTime = now()
            packetType, payload = packet
            print('packet:', packet, end=' - ')

            processedPacket = True  # Assume True, set to False only if the two else statements at the end fire
            if packetType < len(packetTypes):
                
                if packetTypes[packetType] == 'SET_LIGHT':
                    print('SET_LIGHT')
                    setLight(payload[0], payload[1])
                    print('Set light {} to {}'.format(payload[0], payload[1]))
                    send('ACKNOWLEDGE', b'')

                elif packetTypes[packetType] == 'GET_LIGHT':
                    print('GET_LIGHT')
                    value = getLight(payload[0])
                    send('ACKNOWLEDGE', int.to_bytes(value, 1, 'big'))

                elif packetTypes[packetType] == 'SET_THROTTLE':
                    print('SET_THROTTLE')
                    setThrottle(payload[0])
                    print('Set throttle to {}'.format(payload[0]))
                    send('ACKNOWLEDGE', b'')

                else: print('Unable to process packets of type {} at this time'.format(packetTypes[packetType])); processedPacket = False
            
            else: print('Unknown packet type:', packetType); processedPacket = False

            endTime = now()
            print('Time:', endTime - startTime)

        sleep(0.01)

if __name__ == '__main__':
    getConfig()
    connected = False

    # Attempt to connect based on config
    if 'controller-ssid' in config.keys() and 'controller-ssid-password' in config.keys() and 'controller-addr' in config.keys() and 'controller-traffic-port' in config.keys():
        print('Credentials for controller found in config, connecting...')
        connected = connectController(config['controller-ssid'], config['controller-ssid-password'], config['controller-addr'], int(config['controller-traffic-port']))
    
    # Attempt failed, enter discovery mode
    while not connected:
        print('Unable to connect to controller')
        controllerInfo = discoverController()
        connected = connectController(*controllerInfo)
    print('Connected to controller, ready to send/recv packets')

    # All the normal stuff
    main()
