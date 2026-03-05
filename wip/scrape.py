import serial
import struct
import threading
# =========================
# PORT CONFIG
# ==========================
CLI_PORT = "COM6"
DATA_PORT = "COM5"

CLI_BAUD = 115200
DATA_BAUD = 921600

# ==========================
# TI MMWAVE CONSTANTS
# ==========================
MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
HEADER_FORMAT = 'Q8I'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# ==========================
# CLI PORT READER
# ==========================
def read_cli(cli_port):
    while True:
        try:
            line = cli_port.readline().decode(errors='ignore').strip()
            if line:
                print("[CLI]", line)
        except:
            break
# ==========================
# DETECTED POINT PARSER
# ==========================
def parse_detected_points(data):
    point_struct = '4f'
    point_size = struct.calcsize(point_struct)
    num_points = len(data) // point_size
    print(f"\nDetected Objects: {num_points}")
    for i in range(num_points):
        x, y, z, v = struct.unpack(
            point_struct,
            data[i * point_size:(i + 1) * point_size]
        )
        print(f"X:{x:.2f} Y:{y:.2f} Z:{z:.2f} V:{v:.2f}")
# ==========================
# PACKET PARSER (SAFE)
# ==========================
def parse_packet(packet, num_tlvs):
    offset = HEADER_SIZE
    packet_len = len(packet)
    for _ in range(num_tlvs):
        # Check TLV header exists
        if offset + 8 > packet_len:
            return
        tlv_type, tlv_length = struct.unpack(
            '2I',
            packet[offset:offset + 8]
        )
        offset += 8
        # Validate TLV size
        if tlv_length < 8 or offset + (tlv_length - 8) > packet_len:
            return
        tlv_data = packet[offset:offset + tlv_length - 8]
        # TLV TYPE 1 = Detected Points
        if tlv_type == 1:
            parse_detected_points(tlv_data)
        offset += tlv_length - 8
# ==========================
# DATA PORT READER
# ==========================
def read_data(data_port):
    buffer = bytearray()
    while True:
        try:
            data = data_port.read(4096)
            print(data)
            buffer.extend(data)
            while True:
                start = buffer.find(MAGIC_WORD)
                if start == -1:
                    buffer.clear()
                    break
                if len(buffer) < start + HEADER_SIZE:
                    break
                header = buffer[start:start + HEADER_SIZE]
                unpacked = struct.unpack(HEADER_FORMAT, header)
                total_packet_len = unpacked[2]
                num_tlvs = unpacked[7]
                # Wait until full packet arrives
                if len(buffer) < start + total_packet_len:
                    break
                packet = buffer[start:start + total_packet_len]
                try:
                    parse_packet(packet, num_tlvs)
                except Exception as e:
                    print("Packet parse error:", e)
                # Remove processed packet
                buffer = buffer[start + total_packet_len:]
        except Exception as e:
            print("Data read error:", e)
            break
# ==========================
# MAIN
# ==========================

def main():
    print("Opening ports...")
    cli_port = serial.Serial(CLI_PORT, CLI_BAUD, timeout=1)
    data_port = serial.Serial(DATA_PORT, DATA_BAUD, timeout=1)
    print("Ports opened")
    # Start CLI reader thread
    threading.Thread(
        target=read_cli,
        args=(cli_port,),
        daemon=True
    ).start()

    # Start data reader
    read_data(data_port)
if __name__ == "__main__":
    main()