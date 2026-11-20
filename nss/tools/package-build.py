from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,tarfile
p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);p.add_argument('--profile',choices=['nand','initramfs'],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
t=a.tree.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=True);k=t/'build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx'
if a.profile=='initramfs':
 source=t/'bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-zte_mf297d-initramfs-uImage.itb';assert source.is_file();shutil.copyfile(source,o/'openwrt-mf297d-nss-initramfs.itb')
else:
 kernel=o/'kernel.bin';assert not kernel.exists(),'Use a fresh output directory for each build'
 tools=Path(__file__).resolve().parents[2]/'tools'
 subprocess.run([sys.executable,str(tools/'build_fit.py'),'--image',str(k/'linux-6.18.60/arch/arm64/boot/Image'),'--dtb',str(k/'image-ipq5018-zte-mf297d.dtb'),'--out',str(kernel)],check=True)
 raw=(k/'root.squashfs').read_bytes();(o/'rootfs.bin').write_bytes(raw.ljust((len(raw)+4095)//4096*4096,b'\0'))
 m={'model':'zte,mf297d','kind':'MF297D-NAND-BUNDLE-1','kernel_version':'6.18.60','rootfs_alignment':4096,'sysupgrade_compatible':False,'generic_stock_factory_image':False,'files':{n:{'bytes':(o/n).stat().st_size,'sha256':hashlib.sha256((o/n).read_bytes()).hexdigest()} for n in ['kernel.bin','rootfs.bin']}}
 (o/'NAND-MANIFEST.json').write_text(json.dumps(m,indent=2))
 with tarfile.open(o/'openwrt-mf297d-nss-nand.bin','w',format=tarfile.USTAR_FORMAT) as archive:
  for n in ['kernel.bin','rootfs.bin','NAND-MANIFEST.json']:archive.add(o/n,arcname='mf297d-nand/'+n)
(o/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(o.iterdir()) if f.is_file() and f.name!='SHA256SUMS'))
print('Outputs:',o)
