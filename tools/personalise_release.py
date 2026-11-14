"""Prepare an owned-unit DTB and extract Image from a release FIT; offline only."""
import argparse,hashlib,json,lzma,re,struct,zlib
from pathlib import Path
from inspect_fit import fdt,inspect
from fdt_codec import encode
p=argparse.ArgumentParser(description=__doc__);p.add_argument('firmware',type=Path);p.add_argument('--lan-mac',required=True);p.add_argument('--wan-mac',required=True);p.add_argument('--out',type=Path,default=Path('ready'));a=p.parse_args()
def mac(value):
 if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',value):raise ValueError('MAC must be xx:xx:xx:xx:xx:xx')
 b=bytes.fromhex(value.replace(':',''))
 if b[0]&1 or b in (bytes(6),bytes.fromhex('020000000001'),bytes.fromhex('020000000002')):raise ValueError('Use your own unicast MAC address')
 return b
lan,wan=mac(a.lan_mac),mac(a.wan_mac);assert lan!=wan
report=inspect(a.firmware);assert all(h['valid'] for v in report['images'].values() for h in v['hashes'])
blob=a.firmware.read_bytes();tree=fdt(blob);old=tree['/images/fdt-1']['data'];dt=fdt(old)
assert dt['/']['model'].rstrip(b'\0')==b'ZTE MF297D'
nodes=[n for n,v in dt.items() if 'local-mac-address' in v];assert len(nodes)==2
for n in nodes:dt[n]['local-mac-address']=wan if n.endswith('/ethernet-port@5') else lan
dtb=encode(dt,old);kernel=tree['/images/kernel-1'];assert kernel['compression']==b'lzma\0'
image=lzma.decompress(kernel['data'],format=lzma.FORMAT_ALONE);assert image[56:60]==b'ARM\x64'
a.out.mkdir(exist_ok=False,parents=True)
(a.out/'Image').write_bytes(image);(a.out/'mf297d.dtb').write_bytes(dtb)
args=dt['/chosen']['bootargs'].rstrip(b'\0').decode();(a.out/'bootargs.txt').write_text(args+'\n')
tree['/images/fdt-1']['data']=dtb
for n,v in tree.items():
 if n.startswith('/images/fdt-1/hash'):
  alg=v['algo'].rstrip(b'\0').decode();v['value']=struct.pack('>I',zlib.crc32(dtb)&0xffffffff) if alg=='crc32' else hashlib.new(alg,dtb).digest()
(a.out/'personalised.itb').write_bytes(encode(tree,blob))
(a.out/'SHA256SUMS').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in [a.out/'Image',a.out/'mf297d.dtb',a.out/'bootargs.txt',a.out/'personalised.itb']))
print('Prepared '+str(a.out)+'. No device writes. RAM boot tools accept only the NSS RAM image; native FIT needs an existing matching installation and updated boot CRC.')
