#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage/restore one clean native boot before MF297D kexec; no firmware/ENV writes."""
from pathlib import Path
import argparse,getpass,hashlib,json,shlex,socket

FILES={'cpu':'/etc/init.d/mf297d-cpu','nss':'/etc/init.d/nss','config':'/etc/config/nss'}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('phase',choices=['stage','restore']);p.add_argument('--host',default='192.168.1.1');p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();import paramiko
 t=paramiko.Transport(socket.create_connection((a.host,22),timeout=5));t.start_client(timeout=8)
 try:
  fingerprint=hashlib.sha256(t.get_remote_server_key().asbytes()).hexdigest()
  try:t.auth_none('root')
  except paramiko.AuthenticationException:t.auth_password('root',getpass.getpass('OpenWrt root SSH password: '))
  def read(cmd):
   c=t.open_session();c.settimeout(30);c.exec_command(cmd);b=c.makefile('rb').read();e=c.makefile_stderr('rb').read();rc=c.recv_exit_status();c.close()
   if rc:raise RuntimeError(cmd+': '+e.decode(errors='replace')[-300:])
   return b
  def put(data,path,mode):
   temporary=path+'.mf297d-ram-pending'
   read('test ! -e '+shlex.quote(temporary))
   c=t.open_session();c.settimeout(30);c.exec_command('umask 077; set -C; cat > '+shlex.quote(temporary));c.sendall(data);c.shutdown_write();c.makefile('rb').read();rc=c.recv_exit_status();c.close()
   if rc:raise RuntimeError('Staging failed: '+path)
   assert read('sha256sum '+shlex.quote(temporary)).split()[0].decode()==hashlib.sha256(data).hexdigest()
   read('chmod '+mode+' '+shlex.quote(temporary)+'; mv '+shlex.quote(temporary)+' '+shlex.quote(path))
  assert read('cat /tmp/sysinfo/board_name').strip()==b'zte,mf297d'
  assert b'mf297d.permanent=1' in read('cat /proc/cmdline')
  if a.phase=='stage':
   assert not a.out.exists(),'Use a new backup folder; keep previous backups'
   # Check every required input before changing any file.
   original={k:read('cat '+v) for k,v in FILES.items()}
   assert all(original[k].startswith(b'#!/bin/sh') for k in ['cpu','nss'])
   assert all(b'mf297d-ram-skip-' not in original[k] for k in ['cpu','nss'])
   assert read('cat /sys/kernel/kexec_loaded').strip()==b'0'
   a.out.mkdir(parents=True,mode=0o700)
   meta={'host':a.host,'ssh_key_sha256':fingerprint,'boot_id':read('cat /proc/sys/kernel/random/boot_id').decode().strip(),'backup_sha256':{k:hashlib.sha256(b).hexdigest() for k,b in original.items()}}
   for k,b in original.items():(a.out/(k+'.private')).write_bytes(b)
   (a.out/'metadata.private.json').write_text(json.dumps(meta,indent=2)+'\n')
   try:
    for k in ['cpu','nss']:
     marker='/etc/mf297d-ram-skip-'+k
     first,rest=original[k].split(b'\n',1)
     wrapped=first+b'\n'+('if [ -f '+marker+' ]; then\n rm -f '+marker+'\n exit 0\nfi\n').encode()+rest
     put(wrapped,FILES[k],'755');read('touch '+marker)
    read('uci set nss.general.enabled=0; uci set nss.general.wifi_offload=0; uci commit nss; sync')
   except Exception:
    for k,b in original.items():put(b,FILES[k],'600' if k=='config' else '755')
    read('rm -f /etc/mf297d-ram-skip-cpu /etc/mf297d-ram-skip-nss; sync')
    raise
   print('One-shot clean boot staged. Reboot, wait 2 minutes, then run restore. Keep the backup folder private.')
  else:
   meta=json.loads((a.out/'metadata.private.json').read_text())
   assert meta['host']==a.host and meta['ssh_key_sha256']==fingerprint,'Different device/SSH host key'
   for k in FILES:assert hashlib.sha256((a.out/(k+'.private')).read_bytes()).hexdigest()==meta['backup_sha256'][k],'Backup checksum mismatch'
   assert read('cat /proc/sys/kernel/random/boot_id').decode().strip()!=meta['boot_id'],'Reboot first'
   assert read('cat /sys/devices/system/cpu/online').strip()==b'0','CPU1 must not have started in this boot'
   modules=read('cat /proc/modules');assert b'ath11k ' not in modules and b'qca_nss_drv ' not in modules,'Radio/NSS started; stop and inspect'
   read('test ! -e /etc/mf297d-ram-skip-cpu; test ! -e /etc/mf297d-ram-skip-nss')
   for k,path in FILES.items():put((a.out/(k+'.private')).read_bytes(),path,'600' if k=='config' else '755')
   read('sync');print('Original startup and NSS settings restored. Do not restart services; proceed to RAM handoff, or reboot to return to normal.')
 finally:t.close()
if __name__=='__main__':main()
