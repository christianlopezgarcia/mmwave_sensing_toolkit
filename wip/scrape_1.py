import serial
import struct
import threading
import time

# ---------------------------
# PORT SETTINGS
# ---------------------------
CLI_PORT = "COM6"
DATA_PORT = "COM5"

CLI_BAUD = 115200
DATA_BAUD = 921600

# ---------------------------
# TI PACKET CONSTANTS
# ---------------------------
MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
HEADER_FORMAT = 'Q8I'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# ---------------------------
# HARD-CODED RADAR COMMANDS
# ---------------------------
RADAR_CMDS = [

"sensorStop",
"flushCfg",
"dfeDataOutputMode 1",
"channelCfg 15 7 0",
"adcCfg 2 1",
"adcbufCfg -1 0 1 1 1",
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
"compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
"measureRangeBiasAndRxChanPhase 0 1.5 0.2",
"CQRxSatMonitor 0 3 5 121 0",
"CQSigImgMonitor 0 127 4",
"analogMonitor 0 0",
"aoaFovCfg -1 -90 90 -90 90",
"cfarFovCfg -1 0 0 8.92",
"cfarFovCfg -1 1 -1 1.00",
"calibData 0 0 0",
"sensorStart"
]

# ---------------------------
# SEND COMMAND
# ---------------------------
def send_command(cli, cmd):
    cli.write((cmd + '\n').encode())
    print("mmwDemo:/>" + cmd)
    time.sleep(0.05)


# ---------------------------
# CLI OUTPUT READER
# ---------------------------
def read_cli(cli):

    while True:
        try:
            line = cli.readline().decode(errors="ignore").strip()

            if line:
                print(line)

        except:
            break


# ---------------------------
# DETECTED POINT PARSER
# ---------------------------
def parse_detected_points(data):

    point_struct = "4f"
    size = struct.calcsize(point_struct)
    num = len(data) // size

    print(f"\nDetected Objects: {num}")

    for i in range(num):
        x,y,z,v = struct.unpack(
            point_struct,
            data[i*size:(i+1)*size
        ])

        print(f"X:{x:.2f} Y:{y:.2f} Z:{z:.2f} V:{v:.2f}")


# ---------------------------
# PARSE PACKET
# ---------------------------
def parse_packet(packet, num_tlvs):

    offset = HEADER_SIZE
    plen = len(packet)

    for _ in range(num_tlvs):

        if offset + 8 > plen:
            return

        tlv_type, tlv_len = struct.unpack(
            "2I",
            packet[offset:offset+8]
        )

        offset += 8

        if tlv_len < 8 or offset + (tlv_len-8) > plen:
            return

        tlv_data = packet[offset:offset + tlv_len - 8]

        if tlv_type == 1:
            parse_detected_points(tlv_data)

        offset += tlv_len - 8


# ---------------------------
# DATA STREAM READER
# ---------------------------
def read_data(port):

    buffer = bytearray()

    while True:

        data = port.read(4096)
        buffer.extend(data)

        while True:

            start = buffer.find(MAGIC_WORD)

            if start == -1:
                buffer.clear()
                break

            if len(buffer) < start + HEADER_SIZE:
                break

            header = buffer[start:start+HEADER_SIZE]
            unpacked = struct.unpack(HEADER_FORMAT, header)

            total_len = unpacked[2]
            num_tlvs = unpacked[7]

            if len(buffer) < start + total_len:
                break

            packet = buffer[start:start+total_len]

            try:
                parse_packet(packet, num_tlvs)
            except:
                pass

            buffer = buffer[start + total_len:]


# ---------------------------
# MAIN
# ---------------------------
def main():

    print("Opening ports...")

    cli = serial.Serial(CLI_PORT, CLI_BAUD, timeout=1)
    data = serial.Serial(DATA_PORT, DATA_BAUD, timeout=1)

    print("Ports opened")

    # Start CLI listener
    threading.Thread(target=read_cli, args=(cli,), daemon=True).start()

    # Send full command list
    for cmd in RADAR_CMDS:
        send_command(cli, cmd)

    # Start radar data stream
    read_data(data)


if __name__ == "__main__":
    main()
