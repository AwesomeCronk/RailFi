# RailFi Protocol
This document describes the communication protocol between a locomotive and a controller. Initialization, handshake, and control API are discussed.

## Initialization
When the locomotive has loaded the config and is ready to operate, it creates a WiFi access point (think mobile hotspot) named `RailFi_<road acronym>_<loco number>`. The default road acronym is `RF` and the default loco number is `0000`, so a locomotive controller with fresh firmware will name it's access point `RailFi_RF_0000`. This information is read from the locomotive's config file. Once a controller connects to this access point, it should connect a TCP socket to the locomotive's IP address on port `100` and perform a handshake.

## Handshake
The handshake procedure is outlined below. `0x` followed by hecadecimal characters indicates raw bytes to be transmitted

* Controller: TX `0xffff`
* Locomotive: TX `0xffff`
* Controller: TX `<password (utf-8) (8 bytes)>`
* Locomotive: TX `0xff`
* This section under construction

If at any point, the controller transmits incorrect data, the locomotive will transmit `0xdeadbeef` (raw bytes, not a string) and close the socket. It will then continue listening for controllers.

## Control API
This section under construction