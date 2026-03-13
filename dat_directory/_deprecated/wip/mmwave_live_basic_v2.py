import serial
import struct
import time
import numpy as np

# SETTINGS
CLI_PORT, DATA_PORT = "COM6", "COM5"
CLI_BAUD, DATA_BAUD = 115200, 921600
MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
VERBOSE = True 

RADAR_CMDS = [
    "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 7 0",
    "adcCfg 2 1", "adcbufCfg -1 0 1 1 1", 
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4", "frameCfg 0 2 16 0 100 1 0",
    "lowPower 0 0", "guiMonitor -1 1 1 0 0 0 1",
    "cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5", "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256", "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0", 
    "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2", "CQRxSatMonitor 0 3 5 121 0",
    "CQSigImgMonitor 0 127 4", "analogMonitor 0 0", "aoaFovCfg -1 -90 90 -90 90",
    "cfarFovCfg -1 0 0 8.92", "cfarFovCfg -1 1 -1 1.00", "calibData 0 0 0",
    "sensorStart"
]

def show_raw_bytes(packet, label="PACKET"):
    """Prints bytes in a clean hex format for learning."""
    print(f"\n[RAW {label}] (Size: {len(packet)}B):")
    hex_string = ' '.join(f"{b:02x}" for b in packet)
    rows = [hex_string[i:i+48] for i in range(0, len(hex_string), 48)]
    for row in rows:
        print(f"    {row}")

def parse_frame(packet, debug=True):
    if len(packet) < 40: return None, []
    
    # 1. Show the full raw packet before any processing
    if debug:
        show_raw_bytes(packet, label="FULL FRAME")

    # Unpack Header
    header = struct.unpack('<QIIIIIIII', packet[:40])
    print('HEADER -- ', header)
    frame_num = header[4]
    num_tlvs = header[7]
    total_len = header[2]
    
    print(f"\n{'#'*80}")
    print(f"### HEADER LOGIC: Frame (header 4) {frame_num} | TLVs (Header 7): {num_tlvs} | Expected Size: {total_len}B")
    print(f"{'#'*80}")
    
    objects = []
    cursor = 40
    for i in range(num_tlvs):
        # TLV Header
        t_type, t_len = struct.unpack('<II', packet[cursor:cursor+8])
        tlv_raw_header = packet[cursor:cursor+8]
        
        print(f"\n  [TLV {i}] TYPE {t_type} | LEN {t_len}")
        print(f"  RAW TLV HEADER: {tlv_raw_header.hex(' ')}")
        
        cursor += 8
        t_data = packet[cursor : cursor + t_len]
        
        if t_type == 1: # Point Cloud
            num_objs = t_len // 16
            print(f"  >> DATA: Processing {num_objs} Objects")
            for j in range(num_objs):
                obj_slice = t_data[j*16 : (j+1)*16]
                x, y, z, v = struct.unpack('<4f', obj_slice)
                dist = np.sqrt(x**2 + y**2 + z**2)
                objects.append({'x': x, 'y': y, 'z': z, 'dist': dist, 'snr': 0})
                
                # 4 bytes make which float
                print(f"    OBJ {j} HEX: [X:{obj_slice[0:4].hex()}] [Y:{obj_slice[4:8].hex()}] [Z:{obj_slice[8:12].hex()}] [V:{obj_slice[12:16].hex()}]")
                print(f"    OBJ {j} VAL: X={x:.2f} Y={y:.2f} Z={z:.2f} | Dist={dist:.2f}m")
        
        elif t_type == 7: # SNR
            num_stats = t_len // 4
            for j in range(min(num_stats, len(objects))):
                stat_slice = t_data[j*4 : (j+1)*4]
                snr, noise = struct.unpack('<HH', stat_slice)
                objects[j]['snr'] = snr * 0.1 
                print(f"    SNR {j} HEX: {stat_slice.hex(' ')} -> {objects[j]['snr']:.1f}dB")
        
        else:
            # SEE EVERYTHING: This shows the data for TLVs we aren't parsing yet
            print(f"  >> DATA: Unparsed Type {t_type} Content:")
            show_raw_bytes(t_data, label=f"TYPE_{t_type}_DATA")

        cursor += t_len 
    return frame_num, objects

def main():
    print("--- Initializing Radar ---")
    try:
        cli = serial.Serial(CLI_PORT, CLI_BAUD, timeout=1)
        data_port = serial.Serial(DATA_PORT, DATA_BAUD, timeout=1)
    except Exception as e:
        print(f"[CRITICAL] Could not open ports: {e}")
        return

    # Configuration Loop (Original Logic)
    for cmd in RADAR_CMDS:
        cli.write((cmd + '\n').encode())
        time.sleep(0.02)
        resp = cli.read_all().decode('utf-8', errors='ignore')
        print(f"TX: {cmd}") # {resp}
        if "Error" in resp:
            print(f"  RX ERROR: {resp.strip()}")
            
    print("[OK] Configuration Sent\n")
    buffer = bytearray()
    
    try:
        while True:
            if data_port.in_waiting > 0:
                new_data = data_port.read(data_port.in_waiting)
                # RAW INGEST: See data before it's even synced to a frame
                buffer.extend(new_data)
                # if VERBOSE:
                #     print(f"\n[PORT READ] Got {len(new_data)} bytes: {new_data.hex(' ')} appending to buffer")
                    # print(new_data)

            # Sync logic
            idx = buffer.find(MAGIC_WORD)
            if idx == -1:
                if len(buffer) > 10000: buffer = bytearray()
                continue
            
            if len(buffer) < idx + 16: continue
            total_len = struct.unpack('<I', buffer[idx+12 : idx+16])[0]
            
            if len(buffer) < idx + total_len: continue
            
            packet = buffer[idx : idx + total_len]
            buffer = buffer[idx + total_len:]
            
            # if VERBOSE:
            #     print(f'Anlyzing buffer array, and packet data \n Packet: {packet} \n Buffer: {buffer}')

            f_id, objs = parse_frame(packet, debug=VERBOSE)

    except KeyboardInterrupt:
        print("\nStopping Sensor...")
        cli.write("sensorStop\n".encode())
        cli.close()
        data_port.close()

if __name__ == "__main__":
    main()