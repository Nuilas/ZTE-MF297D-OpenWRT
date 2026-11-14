"""Prepare private own-unit calibration files offline. No device writes."""
import argparse, functools, hashlib, json, struct
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--art', required=True, type=Path)
p.add_argument('--mac-partition', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
def main():
    a = p.parse_args()
    art = a.art.read_bytes()
    base_bytes = a.mac_partition.read_bytes()[:6]
    if len(base_bytes) != 6 or base_bytes[0] & 1 or base_bytes in (b'\0'*6, b'\xff'*6):
        raise ValueError('Invalid own-unit base MAC')
    base = int.from_bytes(base_bytes, 'big')
    outputs = {}
    for offset, add, name in [(0x1000,2,'cal-ahb-c000000.wifi.bin'),(0x26800,3,'cal-ahb-b00a040.wifi.bin')]:
        b = bytearray(art[offset:offset+0x20000])
        if len(b) != 0x20000 or functools.reduce(int.__xor__,struct.unpack('<65536H',b)) != 0xffff:
            raise ValueError('Unexpected ART geometry/checksum')
        b[14:20] = (base+add).to_bytes(6,'big')
        b[10:12] = b'\0\0'
        struct.pack_into('<H',b,10,functools.reduce(int.__xor__,struct.unpack('<65536H',b))^0xffff)
        assert functools.reduce(int.__xor__,struct.unpack('<65536H',b)) == 0xffff
        outputs[name] = bytes(b)
    a.out.mkdir(parents=True, exist_ok=False)
    for name,b in outputs.items(): (a.out/name).write_bytes(b)
    print(json.dumps({'files':len(outputs),'checksum_valid':True,'device_writes':False}))
if __name__ == '__main__': main()
