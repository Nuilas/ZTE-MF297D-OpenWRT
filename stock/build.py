#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild fixed-B18 modules/helpers for the supplied, CRC-matched RAM bundle."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,zlib
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--zig',required=True);a=p.parse_args();src=Path(__file__).resolve().parent/'loader';b=a.bundle.resolve();cfg=(src/'ramboot_config.h').read_text()
 for n,key in [('Image','IMAGE'),('mf297d.dtb','DTB'),('initramfs.cpio','INITRD')]:
  data=(b/n).read_bytes();v=int(re.search(r'RAMBOOT_'+key+r'_CRC32 (0x[0-9a-f]+)U',cfg)[1],16)
  if zlib.crc32(data)!=v:raise ValueError('Inputs differ from fixed loader config: '+n)
 for mode in ['prepare','execute']:
  subprocess.run([a.zig,'build-obj','-target','arm-freestanding-eabi','-mcpu','cortex_a7+soft_float','-fno-PIC','-fno-PIE','-fno-unwind-tables','-O','ReleaseSmall','-femit-bin='+str(b/f'mf297d_ramboot_{mode}.ko'),'-cflags','-DRAMBOOT_EXECUTE_ENABLED='+str(int(mode=='execute')),'-marm','-mfloat-abi=soft','-fno-vectorize','-fno-slp-vectorize','-ffreestanding','-fno-stack-protector','-fno-builtin','-fno-pic','-fno-pie','-Wall','-Wextra','-Werror','--',str(src/'mf297d_ramboot.c')],check=True)
 for n in ['ramfetch','ramcommit']:subprocess.run([a.zig,'cc','-target','arm-linux-musleabi','-static','-Os','-s','-Wall','-Wextra','-Werror','-o',str(b/n),str(src/(n+'.c'))],check=True)
 m=json.loads((b/'MANIFEST.json').read_text())
 for n in ['mf297d_ramboot_prepare.ko','mf297d_ramboot_execute.ko','ramfetch','ramcommit']:
  data=(b/n).read_bytes();m['files'][n]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'crc32':f'{zlib.crc32(data):08x}'}
 m['new_bundle_live_stock_boot_tested']=False;(b/'MANIFEST.json').write_text(json.dumps(m,indent=2)+'\n')
 print('Rebuilt fixed inputs. Re-run stock/tests/test_handoff.py before using the new modules.')
if __name__=='__main__':main()
