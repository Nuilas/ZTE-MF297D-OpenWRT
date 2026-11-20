"""Prepare an owner-bound manual update for the EXISTING MF297D project layout.

This command creates local files and consistent backups. It does not flash.
Generated scripts require separate, explicit operator execution.
"""
from pathlib import Path
import argparse,hashlib,json,lzma,os,re,shlex,struct,subprocess,sys,tarfile,zlib
P=Path(__file__).resolve().parents[2];sys.path.insert(0,str(P/'tools'))
from inspect_fit import fdt,inspect
from fdt_codec import encode
def sha(b):return hashlib.sha256(b).hexdigest()
def replace_hashes(tree,node):
 for n,v in tree.items():
  if n.startswith(node+'/') and 'algo' in v:
   alg=v['algo'].rstrip(b'\0').decode();v['value']=struct.pack('>I',zlib.crc32(tree[node]['data'])) if alg=='crc32' else hashlib.new(alg,tree[node]['data']).digest()
def environment(raw,kernel,args):
 assert re.fullmatch(r'[A-Za-z0-9_.,=/:+ -]+',args),'Unsupported bootargs characters'
 assert 'root=/dev/ubiblock0_5' in args and 'ubi.mtd=21' in args
 assert len(raw)==524288 and raw[262144:]==b'\xff'*262144,'Unsupported ENV geometry/tail'
 old=raw[:262144];assert struct.unpack_from('<I',old)[0]==zlib.crc32(old[4:]),'ENV CRC mismatch'
 entries=old[4:].split(b'\0\0',1)[0].split(b'\0');commands=[x[8:].decode() for x in entries if x.startswith(b'bootcmd=')];assert len(commands)==1
 cmd=commands[0];assert 'owrt_recovery' in cmd and 'bootipq' not in cmd and 'saveenv' not in cmd,'Requires the existing single-OpenWrt project boot layout'
 pattern=r"(if ubi read 0x44000000 owrt_kernel; then if crc32 0x44000000 )0x[0-9a-f]+( 0x43000000; then if itest.l \*0x43000000 == )0x[0-9a-f]+(; then if setenv bootargs ')[^']*(';)"
 matches=list(re.finditer(pattern,cmd));assert len(matches)==1,'Unrecognised main/recovery script; no generic ENV write is allowed'
 m=matches[0];word=int.from_bytes(struct.pack('>I',zlib.crc32(kernel)),'little')
 newcmd=cmd[:m.start()]+m[1]+hex(len(kernel))+m[2]+f'0x{word:08x}'+m[3]+args+m[4]+cmd[m.end():]
 entries=[b'bootcmd='+newcmd.encode() if x.startswith(b'bootcmd=') else x for x in entries]
 data=(b'\0'.join(entries)+b'\0\0');assert len(data)<=262140
 data=data.ljust(262140,b'\0');new=struct.pack('<I',zlib.crc32(data))+data
 return old,new,newcmd,len(entries)
def prepare(a):
 out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);back=out/'backups';back.mkdir(mode=0o700)
 assert re.fullmatch(r'[A-Za-z0-9.:-]+',a.router),'Invalid router address'
 target='root@'+a.router;control=out/'ssh-control'
 subprocess.run(['ssh','-M','-S',str(control),'-o','ControlMaster=auto','-o','ControlPersist=600','-fN',target],check=True)
 def read(cmd):return subprocess.check_output(['ssh','-S',str(control),target,cmd])
 assert b'MF297D' in read('cat /proc/device-tree/model')
 assert read('uname -r').strip() in [b'6.18.55',b'6.18.60']
 assert b'root=/dev/ubiblock0_5' in read('cat /proc/cmdline'),'Run from the installed project NAND system'
 assert b'/dev/ubi0_6 /overlay ubifs rw' in read('cat /proc/mounts')
 assert read('cat /sys/class/mtd/mtd21/size').strip()==b'221511680'
 assert read('cat /sys/class/ubi/ubi0/mtd_num').strip()==b'21'
 volumes={}
 for i,name in [(1,'wifi_fw'),(2,'bt_fw'),(4,'owrt_kernel'),(5,'owrt_rootfs'),(6,'rootfs_data'),(7,'owrt_recovery')]:
  fields=read(f'cat /sys/class/ubi/ubi0_{i}/name /sys/class/ubi/ubi0_{i}/reserved_ebs /sys/class/ubi/ubi0_{i}/type').decode().splitlines();assert fields[0]==name
  volumes[i]={'name':name,'lebs':int(fields[1]),'type':fields[2]}
 assert read('cat /sys/class/ubi/ubi0/volumes_count').strip()==b'6'
 assert read('cat /sys/class/ubi/ubi0/reserved_for_bad').strip()==b'40'
 parts={}
 with tarfile.open(a.firmware) as archive:
  for n in ['kernel.bin','rootfs.bin','NAND-MANIFEST.json']:
   member=archive.getmember('mf297d-nand/'+n);assert member.isfile() and member.size<=67108864;parts[n]=archive.extractfile(member).read()
 manifest=json.loads(parts['NAND-MANIFEST.json']);assert manifest['kind']=='MF297D-NAND-BUNDLE-1' and manifest['model']=='zte,mf297d'
 for n in ['kernel.bin','rootfs.bin']:assert sha(parts[n])==manifest['files'][n]['sha256']
 assert len(parts['rootfs.bin'])%4096==0
 raw=read('cat /dev/mtd10ro');(back/'ENV.private.bin').write_bytes(raw)
 mac=read('head -c 6 /dev/mtd16ro');assert len(mac)==6 and not(mac[0]&1);base=int.from_bytes(mac,'big')
 tree=fdt(parts['kernel.bin']);old_dt=tree['/images/fdt-1']['data'];dt=fdt(old_dt)
 for n,v in dt.items():
  if 'local-mac-address' in v:v['local-mac-address']=(base-(0x10000 if n.endswith('/ethernet-port@5') else 0x20000)).to_bytes(6,'big')
 tree['/images/fdt-1']['data']=encode(dt,old_dt);replace_hashes(tree,'/images/fdt-1');kernel=encode(tree,parts['kernel.bin'])
 old,new,newcmd,varcount=environment(raw,kernel,dt['/chosen']['bootargs'].rstrip(b'\0').decode())
 before={}
 for i in [1,2,4,5,7]:
  data=read(f'cat /dev/ubi0_{i}');(back/f'ubi{i}.bin').write_bytes(data);before[i]=sha(data)
 bootcmd=next(x[8:].decode() for x in old[4:].split(b'\0\0',1)[0].split(b'\0') if x.startswith(b'bootcmd='))
 for i,name in [(4,'owrt_kernel'),(7,'owrt_recovery')]:
  data=(back/f'ubi{i}.bin').read_bytes();word=int.from_bytes(struct.pack('>I',zlib.crc32(data)),'little')
  assert f'ubi read 0x44000000 {name}; then if crc32 0x44000000 0x{len(data):x} 0x43000000; then if itest.l *0x43000000 == 0x{word:08x}' in bootcmd,'Existing main/recovery CRC does not match backup'
  assert all(h['valid'] for v in inspect(back/f'ubi{i}.bin')['images'].values() for h in v['hashes'])
 # Snapshot upper/raw while read-only; restore the original mount mode even on error.
 read('sync; mount -o remount,ro /overlay')
 try:
  (back/'overlay.private.ubifs').write_bytes(read('cat /dev/ubi0_6'))
  config=read('tar -C / -czf - etc/config etc/dropbear etc/passwd etc/shadow etc/group etc/hosts root')
  (back/'settings.private.tgz').write_bytes(config)
 finally:read('mount -o remount,rw /overlay')
 (back/'prefix.sha256').write_bytes(read('for i in $(seq 0 20); do sha256sum /dev/mtd${i}ro; done'))
 (out/'prefix.before.sha256').write_bytes((back/'prefix.sha256').read_bytes())
 # The owner's already verified recovery supplies the maintenance kernel/userspace.
 recovery=fdt((back/'ubi7.bin').read_bytes());image=lzma.decompress(recovery['/images/kernel-1']['data'],format=lzma.FORMAT_ALONE)
 assert b'Linux version 6.18.55 ' in image,'Requires this project\'s verified 6.18.55 recovery'
 md_old=recovery['/images/fdt-1']['data'];md=fdt(md_old);md['/chosen']['mf297d,storage-expand']=b''
 for n,v in md.items():
  if '/partitions/partition@' not in n or 'reg' not in v or 'label' not in v:continue
  if v['label'].lower()==b'0:appsblenv\0':v.pop('read-only',None)
  elif v['reg']==bytes.fromhex('02cc00000d340000'):v.pop('read-only',None);v['label']=b'maintenance_storage\0'
  else:v['read-only']=b''
 args=md['/chosen']['bootargs'].rstrip(b'\0').decode()+' mf297d.storage_expand=1'
 (out/'Image').write_bytes(image);(out/'maintenance.dtb').write_bytes(encode(md,md_old));(out/'bootargs.txt').write_text(args+'\n')
 (out/'kernel.bin').write_bytes(kernel);(out/'rootfs.bin').write_bytes(parts['rootfs.bin'])
 def array(n,b):return 'static const unsigned char '+n+'[262144]={\n'+''.join(','.join(f'0x{x:02x}' for x in b[i:i+32])+',\n' for i in range(0,len(b),32))+'};\n'
 (out/'owner_env.h').write_text(array('probe_data',new)+array('before_data',old)+'\n#define EXPECTED_VAR_COUNT '+str(varcount)+'\nstatic const char expected_bootcmd[]='+json.dumps('bootcmd='+newcmd)+';\n')
 source=(P/'nss/src/env_transition.c').read_bytes();(out/'env_transition.c').write_bytes(source)
 compiler=a.cc or 'aarch64-linux-gnu-gcc'
 subprocess.run([compiler,'-static','-Os','-s','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(out/'env_transition.c'),'-o',str(out/'env-helper')],check=True)
 ov=out/'overlay-tree';(ov/'upper').mkdir(parents=True);(ov/'work').mkdir(mode=0o700);(ov/'.fs_state').symlink_to('2')
 with tarfile.open(back/'settings.private.tgz') as archive:archive.extractall(ov/'upper',filter='data')
 token=os.urandom(16).hex();(ov/'upper/etc/mf297d-nss-install-proof').write_text(token+'\n')
 subprocess.run(['mkfs.ubifs','-m','2048','-e','126976','-c','2048','-j','380928','-l','2','-x','zlib','-F','-U','-r',str(ov),'-o',str(out/'overlay.ubifs')],check=True)
 eb=126976;k=(len(kernel)+eb-1)//eb+1;r=(len(parts['rootfs.bin'])+eb-1)//eb+1
 budget=sum(v['lebs'] for i,v in volumes.items() if i in [4,5,6])+int(read('cat /sys/class/ubi/ubi0/avail_eraseblocks'))
 assert budget-k-r>100,'Insufficient room'
 state={'router':a.router,'env_before':sha(raw),'env_after':sha(new+raw[262144:]),'kernel_before':before[4],'root_before':before[5],'recovery':before[7],'controllers':{str(i):before[i] for i in [1,2]},'volumes_before':volumes,'kernel_lebs':k,'root_lebs':r,'overlay_lebs':budget-k-r,'proof':token,'kernel_after':sha(kernel),'root_after':sha(parts['rootfs.bin'])}
 (out/'owner-plan.private.json').write_text(json.dumps(state,indent=2));(out/'ENV-target.private.bin').write_bytes(new)
 kexec=a.kexec;assert kexec.is_file();(out/'kexec').write_bytes(kexec.read_bytes())
 for n in ['boot-maintenance.sh','install-from-ram.sh']:
  text=(P/'nss/tools'/n).read_text()
  if n=='boot-maintenance.sh':text=text.replace('@ROUTER@',a.router)
  else:
   values={'@ENV_BEFORE@':state['env_before'],'@ENV_AFTER@':state['env_after'],'@OLD_KERNEL@':before[4],'@OLD_ROOT@':before[5],'@RECOVERY@':before[7],'@CONTROLLER1@':before[1],'@CONTROLLER2@':before[2],'@NEW_KERNEL@':state['kernel_after'],'@NEW_ROOT@':state['root_after'],'@KLEBS@':str(k),'@RLEBS@':str(r),'@OLEBS@':str(budget-k-r),'@PROOF@':token}
   for old,value in values.items():text=text.replace(old,value)
  (out/n).write_text(text);subprocess.run(['sh','-n',str(out/n)],check=True)
 names=['Image','maintenance.dtb','bootargs.txt','kernel.bin','rootfs.bin','overlay.ubifs','env-helper','kexec','install-from-ram.sh','prefix.before.sha256']
 (out/'SHA256SUMS').write_text(''.join(sha((out/n).read_bytes())+'  '+n+'\n' for n in names))
 print('Hazirlandi:',out,'\nHenuz flash yazilmadi. ready/backups ve owner dosyalarini paylasmayin.\nSonraki adim: sh '+str(out/'boot-maintenance.sh'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--router',default='192.168.1.1');p.add_argument('--firmware',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('ready'));p.add_argument('--cc');p.add_argument('--kexec',type=Path,required=True);prepare(p.parse_args())
