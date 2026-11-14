"""Build the tested inline FIT schema from an ARM64 Image and DTB; offline only."""
import argparse
import hashlib
import json
import lzma
import struct
import zlib
from pathlib import Path
from fdt_codec import encode
from inspect_fit import fdt, inspect

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--dtb', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Output exists')
    image = a.image.read_bytes()
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('Expected uncompressed ARM64 Linux Image')
    text_offset, memory_size = struct.unpack_from('<QQ', image, 8)
    if text_offset != 0 or not len(image) <= memory_size <= 0x09b00000:
        raise ValueError('Unexpected Image offset/size for tested RAM banks')
    dtb = a.dtb.read_bytes()
    dt = fdt(dtb)
    if dt.get('/', {}).get('model', b'').find(b'MF297D') < 0:
        raise ValueError('Expected MF297D DTB')
    kernel = lzma.compress(image, format=lzma.FORMAT_ALONE,
        filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 8*1024*1024, 'lc': 3, 'lp': 0, 'pb': 2}])
    tree = {
        '/': {'timestamp': struct.pack('>I', 0), 'description': b'MF297D source-built OpenWrt\0', '#address-cells': struct.pack('>I', 1)},
        '/images': {},
        '/images/kernel-1': {'description': b'ARM64 OpenWrt Linux-6.18.55\0', 'data': kernel,
            'type': b'kernel\0', 'arch': b'arm64\0', 'os': b'linux\0', 'compression': b'lzma\0',
            'load': struct.pack('>I', 0x41000000), 'entry': struct.pack('>I', 0x41000000)},
        '/images/fdt-1': {'description': b'ARM64 MF297D device tree\0', 'data': dtb,
            'type': b'flat_dt\0', 'arch': b'arm64\0', 'compression': b'none\0'},
        '/configurations': {'default': b'config@mp03.3\0'},
        '/configurations/config@mp03.3': {'description': b'OpenWrt zte_mf297d\0', 'kernel': b'kernel-1\0', 'fdt': b'fdt-1\0'},
    }
    for node, data in [('/images/kernel-1', kernel), ('/images/fdt-1', dtb)]:
        tree[node+'/hash-1'] = {'algo': b'crc32\0', 'value': struct.pack('>I', zlib.crc32(data)&0xffffffff)}
        tree[node+'/hash-2'] = {'algo': b'sha1\0', 'value': hashlib.sha1(data).digest()}
    header = struct.pack('>10I', 0xd00dfeed, 56, 56, 56, 40, 17, 16, 0, 0, 0) + b'\0'*16
    out = encode(tree, header)
    assert lzma.decompress(fdt(out)['/images/kernel-1']['data'], format=lzma.FORMAT_ALONE) == image
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(out)
    result = inspect(a.out)
    assert all(h['valid'] for v in result['images'].values() for h in v['hashes'])
    print(json.dumps({'bytes': len(out), 'crc32': zlib.crc32(out)&0xffffffff,
        'sha256': hashlib.sha256(out).hexdigest(), 'image_memory_size': memory_size,
        'load_entry': '0x41000000', 'device_writes': False, 'new_fit_hardware_tested': False}, indent=2))

if __name__ == '__main__':
    main()
