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
    print('Boot mode: real')

    from machine import Pin
    import network
    import usocket as socket
    import gc
    
    gc.collect()

    def sleep(t):
        time.sleep_ms(int(t * 1000))

    # Hardware connections
    headLight = Pin(32, Pin.OUT)
    rearLight = Pin(33, Pin.OUT)
    lights = {'headlight': headLight, 'rearlight': rearLight}

    def setLight(light, value):
        lights[light].value(value)

    def getLight(light):
        return lights[light].value()

    
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
    lights = {'headlight': 0, 'rearlight': 0}

    def setLight(light, value):
        global lights
        assert light in lights.keys()
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
        print('Lights: {} {} | Motor: {}% | Error: {}'.format('H' if lights['headlight'] else ' ', 'R' if lights['rearlight'] else ' ', throttle, errorCodes[currentError]))

else:
    raise RuntimeError('Implementation "{}" not recognized'.format(sys.implementation.name))


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
        except socket.timeout:
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
    print('Connected to controller')
    return True
    

## Main section ##
if __name__ == '__main__':
    sleep(1)
    getConfig()
    connected = False
    if 'controller-ssid' in config.keys() and 'controller-ssid-password' in config.keys() and 'controller-addr' in config.keys() and 'controller-traffic-port' in config.keys():
        print('Credentials for controller found in config, connecting...')
        connected = connectController(config['controller-ssid'], config['controller-ssid-password'], config['controller-addr'], int(config['controller-traffic-port']))
    while not connected:
        print('Unable to connect to controller')
        controllerInfo = discoverController()
        connected = connectController(*controllerInfo)
    print('===== Connected to controller, ready to send/recv packets =====')
