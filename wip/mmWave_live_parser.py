import serial
import time
import struct

# Configuration
CLI_PORT = "COM6"
DATA_PORT = "COM5"
RADAR_CMDS = [
    "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 7 0",
    "adcCfg 2 1", "adcbufCfg -1 0 1 1 1", 
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4", "frameCfg 0 2 16 0 100 1 0",
    "lowPower 0 0", "guiMonitor -1 1 1 0 0 0 1", # Note: Type 7 (Side info) enabled
    "cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5", "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256", "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0", "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2", "CQRxSatMonitor 0 3 5 121 0",
    "CQSigImgMonitor 0 127 4", "analogMonitor 0 0", "aoaFovCfg -1 -90 90 -90 90",
    "cfarFovCfg -1 0 0 8.92", "cfarFovCfg -1 1 -1 1.00", "calibData 0 0 0",
    "sensorStart"
]

def send_cmds(port, cmds):
    """Sends radar configuration commands via CLI port."""
    for cmd in cmds:
        port.write((cmd + '\n').encode())
        time.sleep(0.1)
        print(f"[CLI] {port.read_all().decode().strip()}")

def parse_live_data(data_port, duration=5):
    magic_word = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    end_time = time.time() + duration
    buffer = bytearray()

    while time.time() < end_time:
        if data_port.in_waiting > 0:
            buffer.extend(data_port.read(data_port.in_waiting))
        
        while magic_word in buffer:
            start = buffer.find(magic_word)
            if len(buffer) < start + 40: break 
            
            header = buffer[start:start+40]
            total_len = struct.unpack('<I', header[12:16])[0]
            num_tlvs = struct.unpack('<I', header[32:36])[0]

            if len(buffer) < start + total_len: break
            packet = buffer[start:start+total_len]
            del buffer[:start+total_len]

            cursor = 40
            for _ in range(num_tlvs):
                # Ensure we have enough bytes for a TLV header (8 bytes)
                if cursor + 8 > len(packet): break
                
                t_type, t_len = struct.unpack('<2I', packet[cursor:cursor+8])
                # t_len includes the 8-byte TLV header in some SDKs, 
                # but in yours, it usually represents just the data payload.
                t_data = packet[cursor+8 : cursor+t_len]
                
                if t_type == 1: # Detected Points
                    # Calculate points based on actual bytes received to avoid unpack errors
                    obj_struct_size = 16 
                    actual_objs = len(t_data) // obj_struct_size
                    for i in range(actual_objs):
                        x, y, z, v = struct.unpack('<4f', t_data[i*16 : (i+1)*16])
                        print(f"Obj {i} -> Vel: {v:.2f} m/s")

                elif t_type == 7: # Side Info (SNR/Noise)
                    obj_side_size = 4
                    actual_objs = len(t_data) // obj_side_size
                    for i in range(actual_objs):
                        snr, noise = struct.unpack('<2H', t_data[i*4 : (i+1)*4])
                        print(f"Obj {i} -> Relative Power (SNR): {snr*0.1:.1f} dB")

                cursor += t_len

def main():
    with serial.Serial(CLI_PORT, 115200, timeout=1) as cli, serial.Serial(DATA_PORT, 921600, timeout=1) as data:
        
        print("Sending Config...")
        send_cmds(cli, RADAR_CMDS)
        
        print(f"Reading data for 5 seconds...")
        import time
        current_time = time.time()
        while time.time() < current_time+1:
            bytecount = data.inWaiting()
            s = data.read(bytecount)
            if s:
                print(s)
        cli.close()
        data.close()
        # parse_live_data(data, duration=5)

if __name__ == "__main__":
    main()