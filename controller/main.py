import sys, time
import usocket as socket

class locomotive():
    packetTypes = [
        'SET_THROTTLE',
        'GET_THROTTLE',
        'SET_LIGHT',
        'GET_LIGHT',
        'E_STOP',
        'ACKNOWLEDGE',
        'CONCLUDE',
        'ERROR'
    ]

    def __init__(self, name, conn):
        self.name = name
        self.conn = conn
        self.inBuffer = b''

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

def main():
    pass

if __name__ == '__main__':
    main()
