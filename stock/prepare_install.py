#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare a device-bound two-phase FIRST install from read-only stock RAM.

Preparation reads/backups only. Generated scripts require explicit execution.
The current installed OpenWrt layout is deliberately rejected.
"""
from pathlib import Path
import argparse,hashlib,json,lzma,os,re,shlex,socket,struct,subprocess,sys,tarfile,zlib
from images import fdt,personalise,ram_variant,bootcmd

BOOTLOADER_SHA='ab6b0f064965af4f3782d06ad55c9db77e4ad40f1b7bbe034f230e29a9e2f1d6'
def sha(b):return hashlib.sha256(b).hexdigest()
def stock_defaults(bootloader):
 if sha(bootloader)!=BOOTLOADER_SHA:raise ValueError('Bootloader defaults require the supported exact APPSBL')
 marker=bootloader.index(b'bootcmd=bootipq');start=bootloader.index(b'bootargs=',max(0,marker-100));end=bootloader.index(b'\0\0',start)
 entries=bootloader[start:end].split(b'\0');values=dict(x.split(b'=',1) for x in entries)
 if values.get(b'bootcmd')!=b'bootipq' or len(values)!=14:raise ValueError('Unexpected compiled ENV defaults')
 return entries
def environment(raw,newcmd,defaults=None):
 if len(raw)!=524288 or raw[262144:]!=b'\xff'*262144:raise ValueError('Unsupported ENV geometry/redundant tail')
 old=raw[:262144]
 if raw==b'\xff'*524288:
  if defaults is None:raise ValueError('Pristine erased ENV requires exact bootloader defaults')
  entries=defaults
 else:
  if struct.unpack_from('<I',old)[0]!=zlib.crc32(old[4:]):raise ValueError('Original ENV CRC invalid')
  entries=old[4:].split(b'\0\0',1)[0].split(b'\0')
 values=dict(e.split(b'=',1) for e in entries)
 if len(values)!=len(entries):raise ValueError('Duplicate ENV keys are not supported')
 if values.get(b'bootcmd')!=b'bootipq':raise ValueError('Only untouched stock bootipq ENV is accepted')
 target=[b'bootcmd='+newcmd.encode() if x.startswith(b'bootcmd=') else x for x in entries]
 data=b'\0'.join(target)+b'\0\0'
 if len(data)>262140:raise ValueError('ENV capacity exceeded')
 data=data.ljust(262140,b'\0');new=struct.pack('<I',zlib.crc32(data))+data
 return old,new,len(entries),values
class Device:
 def __init__(self,host):
  import paramiko
  self.t=paramiko.Transport(socket.create_connection((host,22),timeout=5));self.t.start_client(timeout=8);self.t.auth_none('root')
 def read(self,cmd,timeout=180):
  c=self.t.open_session();c.settimeout(timeout);c.exec_command(cmd);data=c.makefile('rb').read();err=c.makefile_stderr('rb').read();rc=c.recv_exit_status();c.close()
  if rc:raise RuntimeError('Read command failed: '+cmd+' '+err.decode(errors='replace')[-200:])
  return data
 def backup(self,source,path,size):
  expected=self.read('sha256sum '+source).decode().split()[0];c=self.t.open_session();c.settimeout(180);c.exec_command('cat '+source);h=hashlib.sha256();got=0
  with path.open('xb') as out:
   while data:=c.recv(1048576):out.write(data);h.update(data);got+=len(data)
  rc=c.recv_exit_status();c.close()
  if rc or got!=size or h.hexdigest()!=expected or self.read('sha256sum '+source).decode().split()[0]!=expected:raise ValueError('Backup verification failed: '+source)
  return {'bytes':got,'sha256':expected}
 def close(self):self.t.close()
def make_header(before,target,count,cmd):
 def array(n,b):return 'static const unsigned char '+n+'[]={\n'+',\n'.join(','.join(f'0x{x:02x}' for x in b[i:i+32]) for i in range(0,len(b),32))+'\n};\n'
 return '#define EXPECTED_VAR_COUNT '+str(count)+'\nstatic const char expected_bootcmd[]='+json.dumps('bootcmd='+cmd)+';\n'+array('before_data',before)+array('probe_data',target)
def env_writer_source(mac_prefix):
 source=Path(__file__).resolve().parents[1]/'nss/src/env_transition.c'
 code=source.read_text().replace('strcmp(uts.release,"6.18.55")','strcmp(uts.release,"6.18.60")').replace('"221511680"','"60817408"')
 if len(mac_prefix)!=16 or mac_prefix==b'\xff'*16:raise ValueError('Owner MAC partition prefix')
 identity='static void owner_identity(void) {\nstatic const unsigned char expected[16]={'+','.join(str(x) for x in mac_prefix)+'};\nunsigned char got[16];int fd=open("/dev/mtd16ro",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0 || read(fd,got,16)!=16 || memcmp(expected,got,16))fail("wrong owner MAC partition");close(fd);\n}\n'
 code=code.replace('int main(int argc,char **argv) {',identity+'\nint main(int argc,char **argv) {').replace('    layout_ready();','    layout_ready();owner_identity();')
 if code.count('owner_identity();')!=1:raise ValueError('Owner binding injection failed')
 return code
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--router',default='192.168.1.1');p.add_argument('--nand',type=Path,required=True);p.add_argument('--ram',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--kexec',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='aarch64-linux-gnu-gcc');a=p.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9.:-]+',a.router):raise ValueError('Router address')
 out=a.out.resolve();repository=Path(__file__).resolve().parents[1]
 if out==repository or repository in out.parents:raise ValueError('Keep private owner backups OUTSIDE the source checkout')
 out.mkdir(mode=0o700,parents=True,exist_ok=False);back=out/'backups';back.mkdir(mode=0o700);d=Device(a.router)
 try:
  args=d.read('cat /proc/cmdline')
  if b'mf297d.stock_bootstrap=1' not in args or b'root=/dev/ram0' not in args or b'ubi.mtd=' in args:raise ValueError('Start from the matching read-only STOCK RAM bootstrap, not installed NAND')
  if d.read('cat /tmp/sysinfo/board_name').strip()!=b'zte,mf297d' or d.read('uname -r').strip()!=b'6.18.60':raise ValueError('Kernel/model mismatch')
  flags=d.read('for p in /sys/class/mtd/mtd[0-9]*/flags; do echo "$p $(cat "$p")"; done').decode();vals={int(i):int(v,0) for i,v in re.findall(r'/mtd(\d+)/flags\s+(0x[0-9a-f]+|\d+)',flags)}
  if len(vals)!=25 or any(v&0x400 for v in vals.values()):raise ValueError('All 25 physical partitions must be read-only before preparation')
  if d.read('cat /sys/class/mtd/mtd21/size').strip()!=b'60817408':raise ValueError('Stock UBI extent mismatch')
  print('Reading and verifying all 25 physical MTD data areas; keep power connected.',flush=True)
  backups={}
  for i in range(25):
   size=int(d.read(f'cat /sys/class/mtd/mtd{i}/size'));backups[str(i)]=d.backup(f'/dev/mtd{i}ro',back/f'mtd{i:02}.bin',size);print(f'MTD{i}: backup + double SHA256 verified',flush=True)
  if any(backups[str(i)]['sha256']!=BOOTLOADER_SHA for i in [11,12]):raise ValueError('Unsupported bootloader; no plan generated')
  # Attachment is read-only because ALL 25 MTDs were checked read-only above.
  if b'ubi0' not in d.read('ls /sys/class/ubi'):d.read('ubiattach /dev/ubi_ctrl -m 21 -d 0')
  if d.read('cat /sys/class/ubi/ubi0/mtd_num').strip()!=b'21':raise ValueError('Stock UBI must be attached read-only')
  vols={}
  for i,name in [(0,'kernel'),(1,'wifi_fw'),(2,'bt_fw'),(3,'ubi_rootfs')]:
   if d.read(f'cat /sys/class/ubi/ubi0_{i}/name').decode().strip()!=name:raise ValueError('Original stock volume layout required')
   size=int(d.read(f'cat /sys/class/ubi/ubi0_{i}/data_bytes'));v=d.backup(f'/dev/ubi0_{i}',back/f'ubi{i}-{name}.bin',size);v['lebs']=int(d.read(f'cat /sys/class/ubi/ubi0_{i}/reserved_ebs'));vols[str(i)]=v
  if int(d.read('cat /sys/class/ubi/ubi0/volumes_count'))!=4:raise ValueError('Only untouched four-volume stock UBI is accepted')
  available=int(d.read('cat /sys/class/ubi/ubi0/avail_eraseblocks'));reserved=int(d.read('cat /sys/class/ubi/ubi0/reserved_for_bad'))
  macs=d.read('/usr/sbin/mf297d-factory-data macs /dev/mtd16ro').decode();macs=dict(re.findall(r'(?m)^(lan|wan)=([0-9a-f:]{17})$',macs))
  if set(macs)!={'lan','wan'}:raise ValueError('Factory MAC derivation failed')
 finally:d.close()
 with tarfile.open(a.nand) as tar:
  expected={'mf297d-nand/'+n for n in ['kernel.bin','rootfs.bin','NAND-MANIFEST.json']}
  members=tar.getmembers()
  if {m.name for m in members}!=expected or len(members)!=3 or any(not m.isfile() or m.size>64*1024*1024 for m in members):raise ValueError('NAND bundle members')
  parts={m.name.split('/')[-1]:tar.extractfile(m).read() for m in members}
 meta=json.loads(parts['NAND-MANIFEST.json'])
 for n in ['kernel.bin','rootfs.bin']:
  if sha(parts[n])!=meta['files'][n]['sha256'] or len(parts[n])!=meta['files'][n]['bytes']:raise ValueError('NAND bundle checksum')
 if len(parts['rootfs.bin'])%4096:raise ValueError('Rootfs must be 4KiB aligned')
 token=os.urandom(16).hex();profile=json.loads(a.profile.read_text());profile['owner_token']=token
 kernel=personalise(parts['kernel.bin'],macs['lan'],macs['wan']);(out/'kernel.bin').write_bytes(kernel);(out/'rootfs.bin').write_bytes(parts['rootfs.bin'])
 rec,_,_,recargs=ram_variant(a.ram,profile,'recovery',token);rec=personalise(rec,macs['lan'],macs['wan']);(out/'recovery.itb').write_bytes(rec)
 needed=(len(rec)+126975)//126976+1
 if available-max(0,40-reserved)<needed:raise ValueError('Not enough original free UBI space for recovery BEFORE stock OS removal')
 from images import fit_blob,encode
 for mode,label in [('phase-a','phase-a'),('phase-b','phase-b')]:
  fit,image,dtb,args=ram_variant(a.ram,profile,mode,token);fit=personalise(fit,macs['lan'],macs['wan']);t=fdt(fit);dtb=t['/images/fdt-1']['data']
  (out/(label+'-Image')).write_bytes(image);(out/(label+'.dtb')).write_bytes(dtb);(out/(label+'-args.txt')).write_text(args+'\n')
 nativeargs=fdt(fdt(kernel)['/images/fdt-1']['data'])['/chosen']['bootargs'].rstrip(b'\0').decode()
 raw=(back/'mtd10.bin').read_bytes();defaults=stock_defaults((back/'mtd11.bin').read_bytes());_,_,_,oldvals=environment(raw,'bootipq',defaults)
 cmd=bootcmd(kernel,rec,nativeargs,recargs,oldvals[b'bootcmd'].decode(),oldvals.get(b'bootargs',b'console=ttyMSM0,115200n8').decode(),oldvals.get(b'mtdids',b'').decode(),oldvals.get(b'mtdparts',b'').decode())
 before,new,count,_=environment(raw,cmd,defaults);(out/'owner_env.h').write_bytes(make_header(before,new,count,cmd).encode());(out/'ENV-target.private.bin').write_bytes(new+raw[262144:])
 code=env_writer_source((back/'mtd16.bin').read_bytes()[:16])
 if 'strcmp(uts.release,"6.18.55")' in code:raise ValueError('ENV writer adaptation failed')
 (out/'env_transition.c').write_bytes(code.encode());subprocess.run([a.cc,'-static','-Os','-s','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(out/'env_transition.c'),'-o',str(out/'env-helper')],check=True)
 src=Path(__file__).resolve().parent
 subprocess.run([a.cc,'-static','-Os','-s','-Wall','-Wextra','-Werror',str(src/'erase_tail.c'),'-o',str(out/'erase-tail')],check=True)
 empty=out/'empty-overlay';(empty/'upper').mkdir(parents=True);(empty/'work').mkdir();(empty/'.fs_state').symlink_to('2')
 subprocess.run(['mkfs.ubifs','-m','2048','-e','126976','-c','2048','-j','380928','-l','2','-x','zlib','-F','-U','-r',str(empty),'-o',str(out/'overlay.ubifs')],check=True)
 (out/'kexec').write_bytes(a.kexec.read_bytes())
 plan={'format':'MF297D-B18-FIRST-INSTALL-1','router':a.router,'owner_token':token,'prefix':{str(i):backups[str(i)]['sha256'] for i in range(21)},'env_before':sha(raw),'env_after':sha(new+raw[262144:]),'stock_volumes':vols,'recovery_lebs':needed,'kernel_lebs':(len(kernel)+126975)//126976+1,'rootfs_lebs':(len(parts['rootfs.bin'])+126975)//126976+1,'physical_reset_proof_required':True,'backup_format':'MTD data-only, ECC-corrected; NOT raw page+OOB','first_install_live_tested':False}
 for n,envsha in [('prefix.before.sha256',plan['env_before']),('prefix.after.sha256',plan['env_after'])]:
  (out/n).write_bytes(''.join((envsha if i==10 else plan['prefix'][str(i)])+f'  /dev/mtd{i}ro\n' for i in range(21)).encode())
 (out/'owner-plan.private.json').write_text(json.dumps(plan,indent=2)+'\n')
 for n in ['install_phase_a.sh','install_phase_b.sh']:
  text=(src/n).read_text();values={'@TOKEN@':token,'@ENV_BEFORE@':plan['env_before'],'@ENV_AFTER@':plan['env_after'],'@RECOVERY_LEBS@':str(needed),'@KERNEL_LEBS@':str(plan['kernel_lebs']),'@ROOT_LEBS@':str(plan['rootfs_lebs']),'@RECOVERY_SHA@':sha(rec),'@KERNEL_SHA@':sha(kernel),'@ROOT_SHA@':sha(parts['rootfs.bin']),'@FW1_SHA@':vols['1']['sha256'],'@FW2_SHA@':vols['2']['sha256'],'@OLD0_SHA@':vols['0']['sha256'],'@OLD3_SHA@':vols['3']['sha256']}
  for key,val in values.items():text=text.replace(key,val)
  if re.search(r'@[A-Z0-9_]+@',text):raise ValueError('Unexpanded installation placeholder')
  (out/n).write_bytes(text.encode())
 files=['kernel.bin','rootfs.bin','recovery.itb','overlay.ubifs','env-helper','erase-tail','kexec','install_phase_a.sh','install_phase_b.sh']
 (out/'SHA256SUMS').write_bytes(''.join(sha((out/n).read_bytes())+'  '+n+'\n' for n in files).encode())
 print('Prepared: '+str(out)+'\nBackups verified. No flash writes performed. Physical RESET proof is mandatory between phase A and B.')
if __name__=='__main__':main()
