import serial
import struct
import time
import numpy as np

# SETTINGS
CLI_PORT, DATA_PORT = "COM6", "COM5"
CLI_BAUD, DATA_BAUD = 115200, 921600
MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
VERBOSE = True  # Set to True to see the "under the hood" parsing

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

def show_raw_bytes(packet, limit=64):
    """Prints raw bytes in a hex-editor style format."""
    print(f"\n[RAW DATA] First {limit} bytes of packet:")
    hex_string = ' '.join(f"{b:02x}" for b in packet[:limit])
    # Print in rows of 16 bytes for readability
    rows = [hex_string[i:i+48] for i in range(0, len(hex_string), 48)]
    for row in rows:
        print(f"    {row}")
    print("-" * 50)

def parse_frame(packet, debug=True):
    if len(packet) < 40: return None, []
    
    # 1. Show the bytes before we turn them into numbers
    if debug:
        show_raw_bytes(packet)

    header = struct.unpack('<QIIIIIIII', packet[:40])
    frame_num = header[4]
    num_tlvs = header[7]
    
    print(f"\n[DEBUG] --- Frame: {frame_num} | Header Size: 40B | Total: {header[2]}B ---")
    
    objects = []
    cursor = 40
    for i in range(num_tlvs):
        t_type, t_len = struct.unpack('<II', packet[cursor:cursor+8])
        print(f"        > TLV[{i}] Type {t_type} Found ({t_len} bytes)")
        
        cursor += 8
        t_data = packet[cursor : cursor + t_len]
        
        if t_type == 1: # Points
            num_objs = t_len // 16
            for j in range(num_objs):
                x, y, z, v = struct.unpack('<4f', t_data[j*16 : (j+1)*16])
                dist = np.sqrt(x**2 + y**2 + z**2)
                objects.append({'dist': dist, 'snr': 0})
        elif t_type == 7: # SNR
            num_stats = t_len // 4
            for j in range(min(num_stats, len(objects))):
                snr, _ = struct.unpack('<HH', t_data[j*4 : (j+1)*4])
                objects[j]['snr'] = snr * 0.1 

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

    for cmd in RADAR_CMDS:
        cli.write((cmd + '\n').encode())
        time.sleep(0.02)
        resp = cli.read_all().decode('utf-8', errors='ignore')
        if "Error" in resp:
            print(f"[CMD ERROR] {cmd}: {resp.strip()}")
            
    print("[OK] Configuration Sent\n")

    buffer = bytearray()
    
    try:
        while True:
            if data_port.in_waiting > 0:
                new_data = data_port.read(data_port.in_waiting)
                buffer.extend(new_data)

            # Search for Magic Word
            idx = buffer.find(MAGIC_WORD)
            if idx == -1:
                if len(buffer) > 10000: buffer = bytearray()
                continue
            
            # Need at least the full header to find the packet length
            if len(buffer) < idx + 16:
                continue
                
            total_len = struct.unpack('<I', buffer[idx+12 : idx+16])[0]
            
            if len(buffer) < idx + total_len:
                continue
            
            # Extract and parse
            packet = buffer[idx : idx + total_len]
            buffer = buffer[idx + total_len:] # Clear used data
            
            f_id, objs = parse_frame(packet)
            
            if objs:
                print(f" >> SUCCESS: Parsed {len(objs)} objects in Frame {f_id}")
                for k, obj in enumerate(objs[:2]): # Show first 2 objects
                    print(f"    Obj {k}: Dist={obj['dist']:.2f}m, SNR={obj['snr']:.1f}dB")

    except KeyboardInterrupt:
        print("\nStopping Sensor...")
        cli.write("sensorStop\n".encode())
        cli.close()
        data_port.close()

if __name__ == "__main__":
    main()