#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install reversible LuCI sysupgrade support files into an existing NAND port.

Only overlay files are changed. Firmware volumes and ENV are hash-checked,
never written. The one-time boot migration is prepared/applied separately.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,subprocess
P=Path(__file__).resolve().parents[2]

def install(a):
    assert re.fullmatch(r'(?:[A-Za-z0-9_-]+@)?[A-Za-z0-9.:-]+',a.router)
    data=a.guard.read_bytes();assert data[:6]==b'\x7fELF\x02\x01' and int.from_bytes(data[18:20],'little')==183
    spec=importlib.util.spec_from_file_location('enable',Path(__file__).with_name('enable-sysupgrade.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    def read(cmd):return subprocess.check_output(['ssh',a.router,cmd])
    assert read('cat /tmp/sysinfo/board_name').strip()==b'zte,mf297d'
    assert b'root=/dev/ubiblock0_5' in read('cat /proc/cmdline')
    before=read('sha256sum /dev/mtd10ro /dev/ubi0_4 /dev/ubi0_5 /dev/ubi0_7')
    a.backup.mkdir(parents=True,mode=0o700,exist_ok=False)
    old=read('cat /lib/upgrade/platform.sh');(a.backup/'platform-before.sh').write_bytes(old)
    files=[('/usr/libexec/mf297d-upgrade-guard',data,'755'),('/lib/upgrade/mf297d.sh',(P/'nss/overlay/files/lib/upgrade/mf297d.sh').read_bytes(),'644'),('/etc/mf297d-sysupgrade-version',b'fit-v1\n','644'),('/lib/upgrade/platform.sh',mod.patch_platform(old.decode()).encode(),'644')]
    saved={}
    for i,(name,body,mode) in enumerate(files):
        exists=read('if [ -f '+name+' ]; then echo yes; fi').strip()==b'yes'
        if exists:(a.backup/('before-'+str(i))).write_bytes(read('cat '+name))
        saved[name]={'existed':exists,'new_sha256':hashlib.sha256(body).hexdigest()}
    (a.backup/'metadata.private.json').write_text(json.dumps(saved,indent=2)+'\n')
    # Guard and functions first, platform entry point last. No partially
    # installed entry point can begin a flash transaction.
    for name,body,mode in files:
        pending=name+'.mf297d-pending'
        subprocess.run(['ssh',a.router,'umask 077; set -C; cat > '+pending],input=body,check=True)
        assert read('sha256sum '+pending).decode().split()[0]==hashlib.sha256(body).hexdigest()
        read('chmod '+mode+' '+pending+'; mv '+pending+' '+name)
    read('sh -n /lib/upgrade/platform.sh; sh -n /lib/upgrade/mf297d.sh; sync')
    assert read('sha256sum /dev/mtd10ro /dev/ubi0_4 /dev/ubi0_5 /dev/ubi0_7')==before
    (a.backup/'protected-before.sha256').write_bytes(before)
    print('LuCI sysupgrade support files installed; firmware, ENV and recovery unchanged. Boot migration must also be ready.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--router',default='root@192.168.1.1');p.add_argument('--guard',type=Path,required=True);p.add_argument('--backup',type=Path,required=True);install(p.parse_args())
