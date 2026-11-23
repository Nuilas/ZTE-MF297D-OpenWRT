#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute an OWNER-PREPARED first install, with mandatory physical RESET proof.

--phase-a writes recovery + owner-bound ENV, keeping original OS volumes.
--verify-reset proves a GPIO-selected recovery boot, no flash writes.
--phase-b removes original OS ONLY after that proof, installing single OpenWrt.
"""
from pathlib import Path
import argparse,hashlib,json,socket,time
from prepare_install import Device

INPUTS=['kernel.bin','rootfs.bin','recovery.itb','overlay.ubifs','env-helper','erase-tail','kexec','install_phase_a.sh','install_phase_b.sh','SHA256SUMS','prefix.before.sha256','prefix.after.sha256']
def sha(b):return hashlib.sha256(b).hexdigest()
def upload(d,p,dst):
 data=p.read_bytes();c=d.t.open_session();c.settimeout(180);c.exec_command('test ! -L '+dst+'; umask 077; cat > '+dst);c.sendall(data);c.shutdown_write();c.makefile('rb').read();rc=c.recv_exit_status();c.close()
 if rc or d.read('sha256sum '+dst).decode().split()[0]!=sha(data):raise ValueError('Upload failed: '+p.name)
def ensure_stage(d,path):
 # A previous interrupted handoff may leave the owner-token directory in tmpfs.
 # Reuse only a real root-owned directory; reject symlinks and other objects.
 cmd='if test -e '+path+'; then test -d '+path+' && test ! -L '+path+' && test "$(stat -c %u '+path+')" = 0 && chmod 700 '+path+'; else mkdir -m 700 '+path+'; fi'
 d.read(cmd)
def token_args(d,plan,role):
 args=d.read('cat /proc/cmdline').decode().split()
 if 'root=/dev/ram0' not in args or 'mf297d.owner_token='+plan['owner_token'] not in args or role not in args:raise ValueError('Wrong RAM role/owner; no automatic retry')
 if d.read('cat /tmp/sysinfo/board_name').strip()!=b'zte,mf297d' or d.read('uname -r').strip()!=b'6.18.60':raise ValueError('Wrong model/kernel')
 return args
def prefix(d,plan):
 for i in range(21):
  expected=plan['env_after'] if i==10 else plan['prefix'][str(i)]
  if d.read(f'sha256sum /dev/mtd{i}ro').decode().split()[0]!=expected:raise ValueError(f'Protected MTD{i} changed')
def verify_reset(out,plan):
 d=Device(plan['router'])
 try:
  args=token_args(d,plan,'mf297d.recovery=1')
  if 'mf297d.recovery_source=uboot' not in args or 'mf297d.recovery_button=1' not in args:raise ValueError('A REAL RESET-selected U-Boot recovery boot is required, not a kexec/default boot')
  flags=d.read('for p in /sys/class/mtd/mtd[0-9]*/flags; do cat "$p"; done').split()
  if len(flags)!=22 or any(int(x,0)&0x400 for x in flags):raise ValueError('Recovery is not all-readonly expanded layout')
  prefix(d,plan);boot=d.read('cat /proc/sys/kernel/random/boot_id').decode().strip()
  lower=d.read('dd if=/dev/mtd21ro bs=131072 count=464 2>/dev/null | sha256sum').decode().split()[0]
  proof={'owner_token':plan['owner_token'],'boot_id':boot,'physical_button_boot_verified':True,'all_22_mtd_readonly':True,'prefix_verified':True,'lower_sha256':lower,'time':time.time()}
  (out/'RESET-PROOF.private.json').write_text(json.dumps(proof,indent=2)+'\n');print('Physical RESET recovery boot and protected prefix verified. Phase B is now eligible.')
  return proof
 finally:d.close()
def wait_role(plan,role,timeout=240):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  d=None
  try:
   d=Device(plan['router']);token_args(d,plan,role);return d
  except Exception:
   if d:d.close()
   time.sleep(3)
 raise TimeoutError('Expected RAM boot not observed. No automatic retry; do not continue with another phase.')
def handoff(out,plan,phase):
 d=Device(plan['router'])
 try:
  if phase=='a':
   args=d.read('cat /proc/cmdline').split()
   if b'mf297d.stock_bootstrap=1' not in args or b'root=/dev/ram0' not in args:raise ValueError('Phase A must begin in read-only stock RAM bootstrap')
   if d.read('sha256sum /dev/mtd10ro').decode().split()[0]!=plan['env_before']:raise ValueError('Original ENV changed')
  else:
   proof=json.loads((out/'RESET-PROOF.private.json').read_text());token_args(d,plan,'mf297d.recovery=1')
   if proof['owner_token']!=plan['owner_token'] or not proof['physical_button_boot_verified'] or d.read('cat /proc/sys/kernel/random/boot_id').decode().strip()!=proof['boot_id']:raise ValueError('Physical RESET proof belongs to another boot; repeat --verify-reset')
   prefix(d,plan)
  status=json.loads(d.read('nss-status -j'))
  if status['state']!='host':raise ValueError('Installation RAM must stay on host Ethernet path; NSS must be disabled')
  path='/tmp/mf297d-stage-'+plan['owner_token'];ensure_stage(d,path)
  for n in ['kexec','phase-'+phase+'-Image','phase-'+phase+'.dtb','phase-'+phase+'-args.txt']:upload(d,out/n,path+'/'+n)
  cmd='set -e; cd '+path+'; chmod 500 kexec; /etc/init.d/mf297d-wifi-led stop 2>/dev/null || true; wifi down; ifdown lte 2>/dev/null || true; '
  cmd+='for r in /sys/class/remoteproc/remoteproc*; do test ! -r "$r/state" || test "$(cat "$r/state")" = offline; done; '
  cmd+='if test -e /sys/class/ubi/ubi0/mtd_num; then ubidetach /dev/ubi_ctrl -d 0; fi; '
  cmd+='test "$(cat /sys/kernel/kexec_loaded)" = 0; ./kexec -c -l phase-'+phase+'-Image --dtb=phase-'+phase+'.dtb --append="$(cat phase-'+phase+'-args.txt)"; test "$(cat /sys/kernel/kexec_loaded)" = 1; sync'
  d.read(cmd,120);c=d.t.open_session();c.exec_command('cd '+path+'; ./kexec -c -e');time.sleep(2)
 finally:d.close()
def install_inputs(out,plan,phase):
 d=wait_role(plan,'mf297d.install_stock='+('1' if phase=='a' else '2'))
 try:
  path='/tmp/mf297d-first-install';ensure_stage(d,path)
  for n in INPUTS:upload(d,out/n,path+'/'+n)
  if phase=='b':
   proof=json.loads((out/'RESET-PROOF.private.json').read_text());(out/'RESET-PERMIT').write_bytes((plan['owner_token']+'\n').encode());(out/'LOWER-SHA256').write_bytes((proof['lower_sha256']+'\n').encode())
   for n in ['RESET-PERMIT','LOWER-SHA256']:upload(d,out/n,path+'/'+n)
  d.read('chmod 500 '+path+'/env-helper '+path+'/erase-tail '+path+'/kexec; cd '+path+'; sha256sum -c SHA256SUMS')
  log=out/('phase-'+phase+'-execution.private.log');c=d.t.open_session();c.settimeout(600);c.exec_command('cd '+path+'; sh install_phase_'+phase+'.sh 2>&1')
  with log.open('xb') as f:
   while data:=c.recv(16384):f.write(data);print(data.decode(errors='replace'),end='',flush=True)
  rc=c.recv_exit_status();c.close()
  if rc not in [0,-1]:raise RuntimeError('Install script stopped. Preserve log and backups; NO automatic retry: '+str(rc))
 finally:d.close()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ready',type=Path,required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--phase-a',action='store_true');g.add_argument('--verify-reset',action='store_true');g.add_argument('--phase-b',action='store_true');a=p.parse_args()
 out=a.ready.resolve();plan=json.loads((out/'owner-plan.private.json').read_text())
 if plan['format']!='MF297D-B18-FIRST-INSTALL-1':raise ValueError('Unsupported owner plan')
 if a.verify_reset:verify_reset(out,plan);return
 if a.phase_b and not (out/'RESET-PROOF.private.json').is_file():raise ValueError('Run --verify-reset after the physical RESET boot before phase B')
 phase='a' if a.phase_a else 'b';handoff(out,plan,phase);install_inputs(out,plan,phase)
 if phase=='a':print('\nNow power off, hold RESET while powering on, release after 7 seconds. Wait 90 seconds; run --verify-reset. Original OS is still present until phase B.')
 else:print('\nSingle OpenWrt NAND install requested. Wait 90 seconds; verify native boot before considering it successful. Recovery remains stored.')
if __name__=='__main__':main()
