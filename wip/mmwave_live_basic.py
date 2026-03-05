import serial
import struct
import time
import numpy as np
import binascii

###########################################
# USER SETTINGS
###########################################

CLI_PORT = "COM6"
DATA_PORT = "COM5"

CLI_BAUD = 115200
DATA_BAUD = 921600

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

# Debug controls
PRINT_RAW_UART = True
PRINT_PACKET_HEX = True
PRINT_TLV_HEX = True

###########################################
# RADAR COMMAND LIST
###########################################

RADAR_CMDS = [
    "sensorStop","flushCfg","dfeDataOutputMode 1","channelCfg 15 7 0",
    "adcCfg 2 1","adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1",
    "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 16 0 100 1 0",
    "lowPower 0 0",
    "guiMonitor -1 1 1 0 0 0 1",
    "cfarCfg -1 0 2 8 4 3 0 15 1",
    "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",
    "sensorStart"
]

###########################################
# SERIAL SETUP
###########################################

def connect_uart():
    cli = serial.Serial(CLI_PORT, CLI_BAUD, timeout=1)
    data = serial.Serial(DATA_PORT, DATA_BAUD, timeout=1)
    time.sleep(1)
    return cli, data

###########################################
# SEND CONFIG
###########################################

def send_config(cli):
    print("Sending config...\n")

    for cmd in RADAR_CMDS:
        print("[CLI]", cmd)
        cli.write((cmd + '\n').encode())
        time.sleep(0.08)

        resp = cli.read(cli.in_waiting or 1)
        if resp:
            print(resp.decode(errors="ignore").strip())

    print("\nConfig sent.\n")

###########################################
# DEBUG HEX DUMP
###########################################

def hex_dump(data, length=64):
    return binascii.hexlify(data[:length]).decode()

###########################################
# FIND MAGIC WORD
###########################################

def find_magic(buffer):
    return buffer.find(MAGIC_WORD)

###########################################
# HEADER PARSER
###########################################

def parse_header(packet):

    header_struct = 'QIIIIIIII'
    header = struct.unpack(header_struct, packet[:40])

    return {
        "packet_len": header[2],
        "frame_num": header[4],
        "num_tlvs": header[7]
    }

###########################################
# DETECTED OBJECT TLV PARSER
###########################################

def parse_detected_objects(payload):

    num_obj = struct.unpack('I', payload[:4])[0]

    objects = []
    idx = 4

    for _ in range(num_obj):

        x, y, z, velocity = struct.unpack('ffff', payload[idx:idx+16])
        idx += 16

        power = 20*np.log10(np.sqrt(x*x+y*y+z*z)+1e-6)

        objects.append({
            "x":x,
            "y":y,
            "z":z,
            "doppler":velocity,
            "power_db":power
        })

    return objects

###########################################
# FRAME PARSER
###########################################

def parse_frame(packet):

    if PRINT_PACKET_HEX:
        print("\n--- RAW PACKET HEX ---")
        print(hex_dump(packet,128))

    header = parse_header(packet)

    offset = 40
    objects = []

    for tlv_index in range(header["num_tlvs"]):

        tlv_type, tlv_len = struct.unpack('II', packet[offset:offset+8])
        offset += 8

        payload = packet[offset:offset + tlv_len - 8]

        if PRINT_TLV_HEX:
            print(f"\nTLV {tlv_index} type={tlv_type}")
            print(hex_dump(payload,64))

        if tlv_type == 1:
            objects = parse_detected_objects(payload)

        offset += tlv_len - 8

    return header, objects

###########################################
# MAIN LOOP
###########################################

def main():

    cli, data = connect_uart()
    send_config(cli)

    buffer = bytearray()

    print("Reading radar data...\n")

    while True:

        new_bytes = data.read(4096)
        print(new_bytes)
        if PRINT_RAW_UART and new_bytes:
            print("\nUART RAW:", hex_dump(new_bytes,64))

        buffer.extend(new_bytes)

        idx = find_magic(buffer)
        if idx == -1:
            continue

        if len(buffer[idx:]) < 48:
            continue

        packet_len = struct.unpack('I', buffer[idx+12:idx+16])[0]

        if len(buffer[idx:]) < packet_len:
            continue

        packet = buffer[idx:idx+packet_len]

        try:
            header, objects = parse_frame(packet)

            print(f"\nFrame {header['frame_num']} | Objects {len(objects)}")

            for obj in objects:
                print(
                    f"x={obj['x']:.2f} "
                    f"y={obj['y']:.2f} "
                    f"z={obj['z']:.2f} "
                    f"vel={obj['doppler']:.2f} m/s "
                    f"power={obj['power_db']:.2f} dB"
                )

        except Exception as e:
            print("Parse error:", e)

        buffer = buffer[idx+packet_len:]

###########################################
# RUN
###########################################

if __name__ == "__main__":
    main()
