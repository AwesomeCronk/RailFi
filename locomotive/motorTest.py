from machine import Pin

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
        self.SDO.value(0)

        self.deselect()
        print('Responded with', ''.join([str(bit) for bit in bits]))
