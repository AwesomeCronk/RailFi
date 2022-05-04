import sys, time

print('RailFi Locomotive firmware booting...')

# Bootstrap RailFi to run on a locomotive (uPython device) or on a PC (CPython on Linux or Windows)

# NO_ERROR is a placeholder to ensure that <code number> >= 1
errorCodes = [
    'NO_ERROR',
    'NO_CONFIG_FILE',
    'CONFIG_BAD_SYNTAX',
    'CONFIG_MISSING_ENTRY'
]
activeError = 0
configRequiredEntries = [
    'roadname',
    'roadacronym',
    'loconumber',
    'locomodel',
    'password',
    'modelmanufacturer'
]
config = {}
throttle = 0

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

    
    ap = None
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
        # del ap  # Saves RAM, may/may not be an issue

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


    # Hardware display
    def displayHardware():
        print('Lights: {} {} | Motor: {}% | Error: {}'.format('H' if lights['headlight'] else ' ', 'R' if lights['rearlight'] else ' ', throttle, errorCodes[activeError]))

else:
    raise RuntimeError('Implementation "{}" not recognized'.format(sys.implementation.name))


## Error handling ##
def raiseError(code):
    global activeError
    if code == 0 or code == 'NO_CODE':
        return
    
    if isinstance(code, int):
        codeNum = code
        codeName = errorCodes[code]
    else:
        codeName = code
        codeNum = errorCodes.index(code)

    activeError = code
    print('ERROR {}: {}'.format(codeNum, codeName))

    setLight('headlight', 0)
    setLight('rearlight', 0)

    while True:
        # Two quick blinks to indicate errors
        for i in range(4):
            setLight('headlight', 1 - getLight('headlight'))
            setLight('rearlight', 1 - getLight('rearlight'))
            sleep(0.125)

        # Blink <codeNum> times
        for i in range(codeNum * 2):
            sleep(0.500)
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

    # Dump the config over UART
    # for key in config.keys():
    #     print('"{}" : "{}"'.format(key, config[key]))


## Controller connection ##
def discoverController():
    # Host network RailFi_<loco name>_<loco number>
    apName = 'RailFi_' + config['roadacronym'] + '_' + config['loconumber']
    port = 2000
    ssid, locoIP = startAP(apName)
    print('\nAP Info:\nSSID: {}\nLoco IP: {}\nLoco Handshake Port: {}'.format(ssid, locoIP, port))

    # Serve a socket for controllers to connect to
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', port))
    sock.listen(5)
    print('Socket bound')

    haveController = False
    while not haveController:
        conn, addr = sock.accept()
        # conn.settimeout(0.25)     # Uncomment if a timeout proves necessary
        print('Controller connected.')

        print('Performing handshake.')

        # First contact: Controller sends 0xffff, Locomotive responds 0xffff
        firstContact = conn.recv(2)
        if firstContact != b'\xff\xff':
            print('First contact incorrect.')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
        conn.send(b'\xff\xff')
        print('First contact correct.')

        # Get password
        try:
            password = conn.recv(8).decode('UTF-8')
        except UnicodeError:
            print('Bad password data')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
            
        # Test password
        if password != config['password']:
            print('Password incorrect.')
            haveController = False
            conn.send(b'\xde\xad\xbe\xef')
            conn.close()
            continue
        conn.send(b'\xff')
        print('Password correct.')

        # Get AP info (ssid, password) and API info (addr, port)
        ssid = conn.recv(32).decode('utf-8')
        password = conn.recv(16).decode('utf-8')
        addr = conn.recv(16).decode('utf-8')
        port = int.from_bytes(conn.recv(2), 'big')
        conn.close()
        stopAP()
        haveController = True
        return (ssid, password, addr, port)

def connectController():
    pass

if __name__ == '__main__':
    getConfig()
    print(discoverController())