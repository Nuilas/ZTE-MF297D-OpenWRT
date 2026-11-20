#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fixed-B18, RAM-only MF297D bootstrap. Default mode only checks stock identity."""
from pathlib import Path
import argparse,base64,getpass,hashlib,json,re,secrets,socket,struct,sys,threading,time,zlib
from telnet_client import TelnetClient

SYMBOLS={'kernel_restart_prepare':0x8033a9b0,'migrate_to_reboot_cpu':0x8033aa04,'cpu_hotplug_enable':0x80321808,'machine_shutdown':0x803122fc,'soft_restart':0x803122c8,'v7_coherent_kern_range':0x8030307c,'freeze_processes':0x8035856c,'thaw_processes':0x80358428,'sys_sync':0x804062c8}
FILES=[('Image','Image','/tmp/mf297d-Image'),('dtb','mf297d.dtb','/tmp/mf297d-ram.dtb'),('initrd','initramfs.cpio','/tmp/mf297d-initramfs.cpio')]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(c,cmd,timeout=30):
 text,rc=c.command(cmd,timeout=timeout)
 if rc:raise RuntimeError('Modem komutu basarisiz: '+cmd+'\n'+text[-500:])
 return text
def has_hash(text,value):return bool(re.search(r'(?m)^'+re.escape(value)+r'\s+',text))
def verify_bundle(b):
 m=json.loads((b/'MANIFEST.json').read_text())
 if m['format']!='MF297D-B18-STOCK-RAM-1' or not m['all_25_mtd_readonly'] or not m['no_nand_or_env_writer']:raise ValueError('Taninmayan RAM paketi')
 for n,v in m['files'].items():
  if Path(n).name!=n or (b/n).stat().st_size!=v['bytes'] or digest(b/n)!=v['sha256']:raise ValueError('Paket hash/boyut hatasi: '+n)
 for n in ['mf297d_ramboot_prepare.ko','mf297d_ramboot_execute.ko']:
  data=(b/n).read_bytes()
  if data[:6]!=b'\x7fELF\x01\x01' or struct.unpack_from('<HH',data,16)!=(1,40):raise ValueError('ARM32 modulu bekleniyordu')
 return m
def verify_stock(c,m):
 text=run(c,'uname -r; nv get cr_version; nv get model_name; sha256sum /lib/modules/4.4.60/bootconfig.ko')
 if not re.search(r'(?m)^4\.4\.60\r?$',text) or m['stock_firmware'] not in text or not re.search(r'(?m)^MF297D\r?$',text) or not has_hash(text,m['bootconfig_sha256']):raise ValueError('Yalniz eslesen B18 / Linux4.4.60 / bootconfig ABI destekleniyor')
 text=run(c,'grep -E " ('+'|'.join(SYMBOLS)+')$" /proc/kallsyms')
 found={n:int(v,16) for v,n in re.findall(r'(?m)^([0-9a-f]+) [Tt] (\w+)\r?$',text)}
 if found!=SYMBOLS:raise ValueError('Stok kernel gecis adresleri eslesmiyor')
 for path,value in [('soc/nss@40000000/reg','07a00000000001000b11100000001000'),('soc/watchdog@b017000/reg','0b01700000001000')]:
  text=run(c,'base64 /proc/device-tree/'+path)
  if not re.search(r'(?m)^'+re.escape(base64.b64encode(bytes.fromhex(value)).decode())+r'\s*$',text):raise ValueError('Stok donanim kimligi eslesmiyor: '+path)
 text,rc=c.command('grep "^mf297d_ramboot " /proc/modules')
 if rc==0:raise ValueError('Bir RAM modulu zaten yuklu; otomatik degistirilmez')
 return {'stock_firmware':m['stock_firmware'],'kernel':'4.4.60','root_telnet':True,'kernel_abi_and_symbols_verified':True}
def upload_small(c,p,remote):
 text,rc=c.command('sha256sum '+remote+' 2>/dev/null')
 if rc==0:
  if has_hash(text,digest(p)):return
  raise ValueError('Modemde farkli gecici dosya zaten var; once normal reboot yap: '+remote)
 run(c,'set -C; : > '+remote+'.b64')
 encoded=base64.b64encode(p.read_bytes()).decode()
 for i in range(0,len(encoded),256):run(c,"printf '%s' '"+encoded[i:i+256]+"' >> "+remote+'.b64')
 run(c,'set -C; base64 -d '+remote+'.b64 > '+remote+'; chmod 700 '+remote)
 if not has_hash(run(c,'sha256sum '+remote),digest(p)):raise ValueError('Yardimci dosya hash hatasi')
def transfer(c,listener,key,p,remote):
 text,rc=c.command('sha256sum '+remote+' 2>/dev/null')
 if rc==0:
  if has_hash(text,digest(p)):return
  raise ValueError('Farkli gecici dosya var; once normal reboot yap: '+remote)
 token=secrets.token_hex(16);state={}
 def serve():
  try:
   conn,peer=listener.accept()
   with conn:
    conn.settimeout(45)
    if peer[0]!='192.168.1.1':raise ValueError('Beklenmeyen baglanti')
    line=bytearray()
    while not line.endswith(b'\n'):
     ch=conn.recv(1)
     if not ch or len(line)>=200:raise ValueError('Aktarim basligi')
     line.extend(ch)
    if json.loads(line)!={'token':token,'name':key}:raise ValueError('Aktarim kimligi')
    conn.sendall(struct.pack('>Q',p.stat().st_size))
    with p.open('rb') as f:
     while data:=f.read(65536):conn.sendall(data)
    conn.shutdown(socket.SHUT_WR);state['ok']=True
  except Exception as e:state['error']=str(e)
 th=threading.Thread(target=serve,daemon=True);th.start()
 text,rc=c.command('/tmp/mf297d-ramfetch '+key+' '+token,timeout=70);th.join(5)
 if rc or not state.get('ok'):raise RuntimeError('RAM aktarimi basarisiz. PC Ethernet/firewall TCP18869 kontrol et. '+str(state))
 if not has_hash(run(c,'sha256sum '+remote),digest(p)):raise ValueError('RAM aktarim hash hatasi: '+key)
 print(key+': aktarildi, SHA256 dogrulandi',flush=True)
def status(c,b,m,armed):
 text=run(c,'cat /proc/mf297d_ramboot');rows=[json.loads(x) for x in text.splitlines() if x.startswith('{')]
 if len(rows)!=1:raise ValueError('Modul durumu okunamadi')
 s=rows[0]
 if not s['prepared'] or s['execute_enabled']!=int(armed) or s['source_destination_overlap'] is not False or s['flash_written'] is not False:raise ValueError('Modul korumasi dogrulanamadi')
 for key,n in [('kernel_crc32','Image'),('dtb_crc32','mf297d.dtb'),('initrd_crc32','initramfs.cpio')]:
  if s[key]!=m['files'][n]['crc32']:raise ValueError('Modul CRC eslesmiyor: '+n)
 image=bytearray((b/'Image').read_bytes());struct.pack_into('<II',image,0,0x58000110,0xd61f0200);struct.pack_into('<Q',image,32,s['control_phys']+512)
 if s['relocated_image_crc32']!=f'{zlib.crc32(image):08x}':raise ValueError('Bagimsiz tasima CRC kontrolu')
 return s
def quiesce(c):
 path='/sys/bus/platform/devices/8a00000.dwc3'
 text=run(c,'base64 '+path+'/of_node/reg')
 if not re.search(r'(?m)^'+re.escape(base64.b64encode(bytes.fromhex('08a000000000e000')).decode())+r'\s*$',text):raise ValueError('USB denetleyicisi eslesmiyor')
 text=run(c,'for p in /sys/bus/usb/devices/[0-9]*-*/idVendor; do test ! -f "$p" || printf "%s %s\\n" "$p" "$(cat "$p")"; done; true')
 vendors=re.findall(r'(?m)^(/sys/bus/usb/devices/[^/]+/idVendor) ([0-9a-f]{4})\r?$',text)
 if any(p!='/sys/bus/usb/devices/2-1/idVendor' or v!='19d2' for p,v in vendors):raise ValueError('Harici USB aygitini cikar')
 run(c,'if test -L '+path+'/driver; then printf 8a00000.dwc3 > /sys/bus/platform/drivers/dwc3/unbind; fi',60)
 ids={2:'q6v5_wcss_userpd2',1:'q6v5_wcss_userpd1',0:'qcom_q6v5_wcss@CD00000'}
 for i,name in ids.items():
  if name not in run(c,f'readlink -f /sys/class/remoteproc/remoteproc{i}/device/of_node'):raise ValueError('Wi-Fi yardimci islemci kimligi')
 for n in ['ath0','ath1','wifi0','wifi1']:run(c,'ifconfig '+n+' down',25)
 for i in ids:
  p=f'/sys/class/remoteproc/remoteproc{i}/state';text=run(c,'cat '+p)
  if re.search(r'(?m)^running\r?$',text):run(c,'printf stop > '+p,30)
  if not re.search(r'(?m)^offline\r?$',run(c,'cat '+p)):raise ValueError('Wi-Fi yardimci islemci durmadi')
 text=run(c,'ubus call system watchdog');rows=re.findall(r'(?ms)^\{.*?^\}',text)
 if len(rows)!=1 or json.loads(rows[0]).get('status')!='running':raise ValueError('Watchdog korumasi dogrulanamadi')
 run(c,'sync')
def observe(b):
 import paramiko
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  t=None
  try:
   t=paramiko.Transport(socket.create_connection(('192.168.1.1',22),timeout=2));t.start_client(timeout=4);t.auth_none('root')
   def read(cmd):
    ch=t.open_session();ch.settimeout(20);ch.exec_command(cmd);out=ch.makefile('rb').read();rc=ch.recv_exit_status();ch.close()
    if rc:raise ValueError('RAM dogrulamasi komutu')
    return out
   args=read('cat /proc/cmdline');mounts=read('cat /proc/mounts')
   if b'mf297d.stock_bootstrap=1' not in args or b'root=/dev/ram0' not in args or b' /overlay ubifs ' in mounts:raise ValueError('Yeni RAM profili dogrulanamadi')
   flags=read('for p in /sys/class/mtd/mtd[0-9]*/flags; do echo "$p $(cat "$p")"; done').decode();vals={int(i):int(v,0) for i,v in re.findall(r'/mtd(\d+)/flags\s+(0x[0-9a-f]+|\d+)',flags)}
   if len(vals)!=25 or any(v&0x400 for v in vals.values()):raise ValueError('NAND salt-okunur dogrulanamadi')
   result={'ram_boot_verified':True,'kernel':read('uname -r').decode().strip(),'stock_bootstrap':True,'all_25_mtd_readonly':True,'nand_env_written':False}
   (b/'RAM-RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return
  except (OSError,EOFError,paramiko.SSHException,ValueError):time.sleep(3)
  finally:
   if t:t.close()
 raise TimeoutError('RAM acilisi dogrulanamadi. Flash yazilmadi. Fisi cikar/tak stok sistemi geri acmali; otomatik yeniden deneme yapma.')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,default=Path.cwd());g=p.add_mutually_exclusive_group();g.add_argument('--check',action='store_true');g.add_argument('--prepare',action='store_true');g.add_argument('--boot',action='store_true');a=p.parse_args()
 b=a.bundle.resolve();m=verify_bundle(b);password=getpass.getpass('Modemin sUser sifresi: ');c=TelnetClient('192.168.1.1',timeout=10);listener=None;loaded=False;jumped=False
 try:
  c.login('sUser',password);password='';identity=verify_stock(c,m);print(json.dumps(identity,indent=2),flush=True)
  if not a.prepare and not a.boot:return
  listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('192.168.1.2',18869));listener.listen(1);listener.settimeout(50)
  upload_small(c,b/'ramfetch','/tmp/mf297d-ramfetch');upload_small(c,b/'ramcommit','/tmp/mf297d-ramcommit')
  for key,n,remote in FILES:transfer(c,listener,key,b/n,remote)
  transfer(c,listener,'prepare',b/'mf297d_ramboot_prepare.ko','/tmp/mf297d_ramboot.ko');run(c,'insmod /tmp/mf297d_ramboot.ko',90);loaded=True;status(c,b,m,False)
  _,rc=c.command('/tmp/mf297d-ramcommit --check')
  if rc!=111:raise ValueError('Hazirlik modulu gecersiz komutu reddetmedi')
  run(c,'rmmod mf297d_ramboot');loaded=False;print('Hazirlik kontrolu gecti; modul kaldirildi.',flush=True)
  if not a.boot:return
  transfer(c,listener,'execute',b/'mf297d_ramboot_execute.ko','/tmp/mf297d_ramboot_exec.ko');run(c,'insmod /tmp/mf297d_ramboot_exec.ko',90);loaded=True;status(c,b,m,True)
  _,rc=c.command('/tmp/mf297d-ramcommit --check')
  if rc!=111:raise ValueError('Gecis modulu gecersiz komutu reddetmedi')
  quiesce(c);print('RAM gecisi baslatiliyor; NAND ve ENV yazilmayacak.',flush=True)
  try:
   text,rc=c.command('/tmp/mf297d-ramcommit --execute',timeout=15)
   raise RuntimeError('Gecis geri dondu/reddedildi; otomatik yeniden deneme yok: '+str(rc))
  except (TimeoutError,ConnectionError,OSError):jumped=True;loaded=False
  c.close();listener.close();listener=None;observe(b)
 finally:
  if loaded and not jumped:
   try:run(c,'rmmod mf297d_ramboot')
   except Exception:pass
  c.close()
  if listener:listener.close()
if __name__=='__main__':main()
