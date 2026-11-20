from pathlib import Path
import argparse,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('tree',type=Path);p.add_argument('profile',choices=['nand','initramfs']);a=p.parse_args()
tools=Path(__file__).resolve().parents[2]/'tools';sys.path.insert(0,str(tools))
from inspect_fit import fdt
from fdt_codec import encode
tree=a.tree.resolve();source=tree/'target/linux/qualcommax/dts/ipq5018-zte-mf297d.dts'
dtb=tree/'mf297d/profile.dtb';dtb.parent.mkdir(exist_ok=True)
subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(dtb),str(source)],check=True,stderr=subprocess.PIPE)
original=dtb.read_bytes();d=fdt(original)
for n,v in d.items():
 if '/partitions/partition@' in n and 'reg' in v and 'label' in v:
  if a.profile=='nand' and v['reg']==bytes.fromhex('02cc00000d340000'):v.pop('read-only',None)
  else:v['read-only']=b''
if a.profile=='initramfs':
 d['/chosen']['bootargs']=b'console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs maxcpus=1 clk_ignore_unused coherent_pool=2M panic=20 mf297d.public_ram=1\0'
else:d['/chosen'].pop('mf297d,recovery',None)
dtb.write_bytes(encode(d,original));subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(source),str(dtb)],check=True,stderr=subprocess.PIPE)
