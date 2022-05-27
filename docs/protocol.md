# RailFi Protocol
This document describes the communication protocol between a locomotive and a controller. Initialization, handshake, and control API are discussed. `0x` followed by hecadecimal characters indicates raw bytes to be transmitted. `L: ` indicates that a locomotive is to perform an action, `C: ` a controller, and `R: ` a remote.

## Discovery
If a locomotive has no controller contact or is unable to contact the controller.

* L: Blink status `DISCOVERY_MODE`
* L: Start access point `RailFi_Discover_<road-acronym>_<loco-number>` and host at `192.168.4.1` on port `2000`
* C: Join above access point and connect to above address/port
* C: TX `0xffff`
* L: TX `0xffff`
* C: TX `<password (utf-8) (up to 16 bytes)>`
* L: TX `0xffff`
* C: TX `<network-SSID (utf-8) (up to 32 bytes)>`
* C: TX `<network-password (utf-8) (up to 16 bytes)>`
* C: TX `<controller-addr (utf-8) (up to 16 bytes)>`
* C: TX `<controller-traffic-port (big-endian raw) (2 bytes)>`
* L: TX `0xffff`
* L: Disconnect from access point

If at any point, the controller transmits incorrect data, the locomotive will transmit `0xdeadbeef` (raw bytes, not a string) and close the connection. It will then continue listening for controllers. Up to 5 connections will be held in queue at once and the first connection will be processed first. The first connection to be processed successfully will cause the access point to be shut down and the locomotive will connect to the controller.

## Connection
If a locomotive already has a contact for a controller, it will try to connect to it.

* C: Start or join access point `<network-SSID>` and host at `<controller-addr>` on port `<controller-traffic-port>`
* L: Join above access point and connect to above address/port
* C: TX `0x0000`
* L: TX `0x0000`
* C: Generate dedicated port for locomotive
* C: TX `<controller-dedicated-port (big-endian raw) (2 bytes)>`
* L: TX `0x0000`
* L: Disconnect socket
* L: Connect to `<controller-addr>` on port `<controller-dedicated-port>`

If at any point, the controller transmits incorrect data, the locomotive will transmit `0xdeadbeef` (raw bytes, not a string) and close the connection. It will then go into discovery mode. Once this sequence is complete, the controller and locomotive will begin sending packets to each other.

## Packets
Packets are structured in a message-response manner. Each packet carries a conversation ID, generated such that each one is unique, even if one side generates packets without being aware of previous packets. Each side keeps track of the number of conversations it has initiated. Both sides multiply that number by 2, then the locomotive adds 1 to it to create the conversaton ID. When the conversation counter rolls over to `2 ** 31`, it will wrap back to zero before the next packet is transmitted to prevent integer overflow from causing errors.

### Packet structure
* 3B: `RF-` (utf-8)
* 1B: `<packet-type>` (int8)
* 4B: `<conversation-ID>` (int32)
* 2B: `<payload-size>` (int16)

Packets may carry a payload of 65535 bytes or less. No error checking or hashes are included. All integers are big-endian.

## Control API
This section under construction