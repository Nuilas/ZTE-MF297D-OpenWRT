#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real stage2 shell control flow with all flash commands intercepted."""
from pathlib import Path
import hashlib,io,json,os,subprocess,tarfile,tempfile
P=Path(__file__).resolve().parents[2]

def main():
    passed=[]
    with tempfile.TemporaryDirectory(prefix='mf297d-stage2-test-') as temp:
        t=Path(temp);payload=b'root-payload'*2048;kernel=b'kernel-fixture'*300
        image=t/'upgrade.bin'
        with tarfile.open(image,'w') as tar:
            item=tarfile.TarInfo('sysupgrade-zte_mf297d/root');item.size=len(payload);tar.addfile(item,io.BytesIO(payload))
        generic=t/'generic';generic.write_bytes(kernel)
        guard=t/'guard';guard.write_text('#!/bin/sh\n[ "$1" = --personalise ] || exit 1\ncp "$2" "$3"\n');guard.chmod(0o755)
        source=(P/'nss/overlay/files/lib/upgrade/mf297d.sh').read_text().replace('/usr/libexec/mf297d-upgrade-guard',str(guard))
        fake=r'''
mf297d_check_layout() { echo layout-check >> "$LOG"; [ "$MODE" != wrong-layout ]; }
mf297d_validate_payload() {
 MF297D_WORK=$WORK; mkdir "$WORK"; cp "$GENERIC" "$WORK/kernel.generic"
 MF297D_KERNEL_BYTES=4200; MF297D_ROOT_BYTES=$ROOT_BYTES
 MF297D_KERNEL_LEBS=38; MF297D_ROOT_LEBS=184; MF297D_OVERLAY_LEBS=1281
 MF297D_ROOT_SHA=$ROOT_SHA
}
mf297d_preserved_hashes() { echo snapshot-protected >> "$LOG"; echo 'fixture'; }
nand_remove_ubiblock() { echo "remove-block $*" >> "$LOG"; }
ubirmvol() { echo "remove-volume $*" >> "$LOG"; }
ubimkvol() { echo "create-volume $*" >> "$LOG"; }
ubiupdatevol() {
 echo "write-volume $*" >> "$LOG"
 if [ "$1" = /dev/ubi0_5 ]; then cat >/dev/null; [ "$MODE" != root-write-fails ]; else [ "$MODE" != kernel-write-fails ]; fi
}
sha256sum() {
 case "$1" in
 -c) echo verify-protected >> "$LOG"; return 0;;
 /dev/ubi0_5) echo verify-root >> "$LOG"; [ "$MODE" = root-readback-fails ] && echo BAD || echo "$ROOT_SHA  $1";;
 /dev/ubi0_4) echo verify-kernel >> "$LOG"; [ "$MODE" = kernel-readback-fails ] && echo BAD || echo "$KERNEL_SHA  $1";;
 *) command sha256sum "$@";;
 esac
}
nand_do_restore_config() { echo restore-settings >> "$LOG"; [ "$MODE" != settings-restore-fails ]; }
sync() { echo sync >> "$LOG"; }
'''
        cases=['success','wrong-layout','root-write-fails','root-readback-fails','settings-restore-fails','kernel-write-fails','kernel-readback-fails']
        for mode in cases:
            work=t/('work-'+mode);log=t/(mode+'.log');log.touch()
            env=dict(os.environ,MODE=mode,WORK=str(work),LOG=str(log),IMAGE=str(image),GENERIC=str(generic),ROOT_BYTES=str(len(payload)),ROOT_SHA=hashlib.sha256(payload).hexdigest(),KERNEL_SHA=hashlib.sha256(kernel).hexdigest())
            r=subprocess.run(['sh','-c',source+'\n'+fake+'\nmf297d_flash "$IMAGE"'],env=env,capture_output=True,text=True)
            assert (r.returncode==0)==(mode=='success'),(mode,r.stdout,r.stderr)
            ops=log.read_text().splitlines();writes=[x for x in ops if x.startswith('write-volume ')]
            mutations=[x for x in ops if x.startswith(('remove-volume ','create-volume ','write-volume '))]
            if mode=='wrong-layout':assert not mutations
            else:
                assert [x for x in ops if x.startswith('remove-volume ')]==['remove-volume /dev/ubi0 -n 4','remove-volume /dev/ubi0 -n 5','remove-volume /dev/ubi0 -n 6']
                assert mutations[0]=='remove-volume /dev/ubi0 -n 4','Main must be invalid before rootfs/settings mutations'
                assert all(any(token in x for token in ['-n 4','-n 5','-n 6']) for x in ops if x.startswith('create-volume '))
                assert all(x.split()[1] in ['/dev/ubi0_4','/dev/ubi0_5'] for x in writes)
                assert not any('owrt_recovery' in x or 'wifi_fw' in x or 'bt_fw' in x or '/dev/mtd' in x for x in mutations)
            if mode in ['root-write-fails','root-readback-fails','settings-restore-fails']:
                assert not any(x.startswith('write-volume /dev/ubi0_4') for x in ops),'Kernel must remain invalid if root/settings failed'
            if mode=='success':
                positions=[next(i for i,x in enumerate(ops) if x.startswith(s)) for s in ['verify-root','restore-settings','write-volume /dev/ubi0_4','verify-kernel','verify-protected','sync']]
                assert positions==sorted(positions)
            passed.append(mode)
    print(json.dumps({'passed':len(passed),'cases':passed,'all_device_io_mocked':True},indent=2))

if __name__=='__main__':main()
