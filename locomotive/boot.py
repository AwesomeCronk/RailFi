# Bootstrap RailFi to run on a locomotive (uPython device) or on a PC (CPython on Linux or Windows)
import sys

print('RailFi Locomotive firmware booting...')

if sys.implementation.name == 'micropython':
    print('Boot mode: real')

    from machine import Pin
    import network
    import usocket as socket
    import gc
    
    gc.collect()

    # Hardware connections
    headLight = Pin(32, Pin.OUT)
    rearLight = Pin(33, Pin.OUT)
    lights = {'headlight': headLight, 'rearlight': rearLight}

    def setLight(light, value):
        lights[light].value(value)

    def getLight(light):
        return lights[light].value()

elif sys.implementation.name == 'cpython':
    print('Boot mode: emulator')

else:
    raise RuntimeError('Implementation "{}" not recognized'.format(sys.implementation.name))

import time


# Error handling
# NO_ERROR is a placeholder to ensure that <code number> >= 1
errorCodes = [
    'NO_ERROR',
    'NO_CONFIG_FILE',
    'CONFIG_BAD_SYNTAX',
    'CONFIG_MISSING_ENTRY'
]

def raiseError(code):
    if code == 0 or code == 'NO_CODE':
        return
    
    if isinstance(code, int):
        codeNum = code
        codeName = errorCodes[code]
    else:
        codeName = code
        codeNum = errorCodes.index(code)

    print('ERROR {}: {}'.format(codeNum, codeName))

    setLight('headlight', 0)
    setLight('rearlight', 0)

    while True:
        # Two quick blinks to indicate errors
        for i in range(4):
            setLight('headlight', 1 - getLight('headlight'))
            setLight('rearlight', 1 - getLight('rearlight'))
            time.sleep_ms(125)

        # Blink <codeNum> times
        for i in range(codeNum * 2):
            time.sleep_ms(500)
            setLight('headlight', 1 - getLight('headlight'))
            setLight('rearlight', 1 - getLight('rearlight'))

        time.sleep(1)

# Check config to get behavior and loco info
configRequiredEntries = [
    'roadname',
    'roadacronym',
    'loconumber',
    'locomodel',
    'password',
    'modelmanufacturer'
]

def getConfig(configPath='config.txt'):
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
    for key in config.keys():
        print('"{}" : "{}"'.format(key, config[key]))
    return config

# Get a controller
def getController(config):
    # Host network RailFi_<loco name>_<loco number>
    apName = 'RailFi_' + config['roadacronym'] + '_' + config['loconumber']
    port = 100
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=apName)
    ap.config(max_clients=5)
    # ap.ifconfig(('192.168.100.100', '255.255.255.0', '192.168.100.100', '0.0.0.0'))
    ap.active(True)
    print('\nAP Info:\nSSID: {}\nLoco IP: {}\nLoco Handshake Port: {}'.format(ap.config('essid'), ap.ifconfig()[0], port))

    # Host on port 100 to get controller info
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', port))
    sock.listen(5)
    print('Socket bound')

    haveController = False
    while not haveController:
        conn, addr = sock.accept()
        # conn.settimeout(0.25)     # Uncomment if a timeout proves necessary
        print('Controller connected.')
        haveController, controllerInfo = handshake(conn)

# Handshake with controller
def handshake(conn):
    #Transmit 0xdeadbeef to indicate bad data
    def breakup():
        conn.send(b'\xde\xad\xbe\xef')
        conn.close()
        return False, ()

    print('Performing handshake.')

    # First contact: Controller sends 0xffff, Locomotive responds 0xffff
    firstContact = conn.recv(2)
    if firstContact != b'\xff\xff':
        print('First contact incorrect.')
        return breakup()
    conn.send(b'\xff\xff')
    print('First contact correct.')

    # Get password
    try:
        password = conn.recv(8).decode('UTF-8')
    except UnicodeError:
        print('Bad password data')
        return breakup()
        
    # Test password
    if password != config['password']:
        print('Password incorrect.')
        return breakup()
    conn.send(b'\xff')
    print('Password correct.')

    # Get AP info (ssid, password) and API info (addr, port)
    ssid = conn.recv(32)
    # return True, (ssid, password, addr, port)
    return False, ()

## Join control network

config = getConfig()
getController(config)