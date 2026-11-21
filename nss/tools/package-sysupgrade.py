#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Create a deterministic LuCI/sysupgrade tar with OpenWrt fwtool metadata."""
from pathlib import Path
import argparse,hashlib,io,json,lzma,os,struct,subprocess,sys,tarfile,tempfile,zlib

P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'tools'))
from inspect_fit import fdt,inspect

def package(kernel,root,out,fwtool,revision='mf297d-sysupgrade-v1'):
    k=kernel.read_bytes();tree=fdt(k)
    assert all(h['valid'] for image in inspect(kernel)['images'].values() for h in image['hashes']), 'FIT hash mismatch'
    dt=fdt(tree['/images/fdt-1']['data'])
    assert dt['/']['model']==b'ZTE MF297D\0'
    args=dt['/chosen']['bootargs']
    assert b'root=/dev/ubiblock0_5 ' in args and b'ubi.mtd=21 ' in args
    image=lzma.decompress(tree['/images/kernel-1']['data'],format=lzma.FORMAT_ALONE)
    at=image.find(b'IKCFG_ST\x1f\x8b\x08');assert at>=0, 'embedded kernel config required'
    config=zlib.decompress(image[at+8:],31).decode()
    assert 'CONFIG_INITRAMFS_SOURCE=""\n' in config, 'RAM images cannot be sysupgraded'
    assert len(k)<=16*1024*1024
    raw=root.read_bytes();assert len(raw)>=96 and raw[:4]==b'hsqs'
    used=struct.unpack_from('<Q',raw,40)[0];assert 96<=used<=len(raw)
    r=raw[:used].ljust((used+4095)//4096*4096,b'\0');assert len(r)<=128*1024*1024
    manifest={'kind':'MF297D-SYSUPGRADE-1','model':'zte,mf297d','kernel_bytes':len(k),'root_bytes':len(r),
              'kernel_sha256':hashlib.sha256(k).hexdigest(),'root_sha256':hashlib.sha256(r).hexdigest()}
    meta={'metadata_version':'1.1','compat_version':'1.0','supported_devices':['zte,mf297d'],
          'mf297d_layout':'ubi-fixed-4-5-6-recovery-7-v1',
          'version':{'dist':'OpenWrt','version':'SNAPSHOT','revision':revision,'target':'qualcommax/ipq50xx','board':'zte_mf297d'}}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.mf297d-sysupgrade-',dir=out.parent) as temp:
        temp=Path(temp);archive=temp/'image.bin';base='sysupgrade-zte_mf297d'
        with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT) as tar:
            directory=tarfile.TarInfo(base+'/');directory.type=tarfile.DIRTYPE;directory.mode=0o755;tar.addfile(directory)
            for name,data in [('CONTROL',b'BOARD=zte,mf297d\n'),('kernel',k),('root',r),('manifest.json',(json.dumps(manifest,sort_keys=True)+'\n').encode())]:
                info=tarfile.TarInfo(base+'/'+name);info.mode=0o644;info.size=len(data);tar.addfile(info,io.BytesIO(data))
        metadata=temp/'metadata.json';metadata.write_text(json.dumps(meta,sort_keys=True)+'\n')
        subprocess.run([str(fwtool),'-I',str(metadata),str(archive)],check=True)
        check=temp/'checked.json';subprocess.run([str(fwtool),'-i',str(check),str(archive)],check=True)
        assert json.loads(check.read_text())==meta
        os.replace(archive,out)
    return {'file':out.name,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'sysupgrade_compatible':True,'recovery_included':False,'layout':meta['mf297d_layout']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--rootfs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--fwtool',type=Path,required=True);p.add_argument('--revision',default='mf297d-sysupgrade-v1');a=p.parse_args()
    print(json.dumps(package(a.kernel,a.rootfs,a.out,a.fwtool,a.revision),indent=2))
