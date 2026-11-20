# SPDX-License-Identifier: GPL-2.0-only
"""Offline FIT/CPIO derivation for the fixed MF297D layout; no device access."""
from pathlib import Path
import hashlib,json,lzma,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_fit import fdt,inspect
from fdt_codec import encode

def cpio_parse(data):
 out=[];at=0
 while True:
  if data[at:at+6]!=b'070701':raise ValueError('Expected newc CPIO')
  fields=[int(data[at+6+i*8:at+14+i*8],16) for i in range(13)];at+=110
  size=fields[6];namesize=fields[11]
  if not 1<=namesize<=4096 or at+namesize>len(data):raise ValueError('CPIO name')
  name=data[at:at+namesize-1].decode();at=(at+namesize+3)&~3
  if at+size>len(data):raise ValueError('CPIO body')
  payload=data[at:at+size];at=(at+size+3)&~3;out.append((name,fields,payload))
  if name=='TRAILER!!!':return out
def cpio_pack(entries):
 out=bytearray()
 for name,fields,payload in entries:
  h=list(fields);n=name.encode()+b'\0';h[6]=len(payload);h[11]=len(n)
  out+=b'070701'+b''.join(f'{x:08x}'.encode() for x in h)+n;out+=b'\0'*((-len(out))%4);out+=payload;out+=b'\0'*((-len(out))%4)
 return bytes(out)+b'\0'*((-len(out))%512)
def fit_blob(tree,old):
 for node in ['/images/kernel-1','/images/fdt-1']:
  for name,p in tree.items():
   if name.startswith(node+'/') and 'algo' in p:
    alg=p['algo'].rstrip(b'\0').decode();data=tree[node]['data'];p['value']=struct.pack('>I',zlib.crc32(data)) if alg=='crc32' else hashlib.new(alg,data).digest()
 return encode(tree,old)
def personalise(blob,lan,wan):
 t=fdt(blob);old=t['/images/fdt-1']['data'];dt=fdt(old);count=0
 for n,p in dt.items():
  if 'local-mac-address' in p:p['local-mac-address']=bytes.fromhex((wan if n.endswith('/ethernet-port@5') else lan).replace(':',''));count+=1
 if count!=2:raise ValueError('Expected two Ethernet MAC nodes')
 t['/images/fdt-1']['data']=encode(dt,old);return fit_blob(t,blob)
def ram_variant(template,profile,mode,token):
 if mode not in ['recovery','phase-a','phase-b']:raise ValueError('Unknown RAM role')
 if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid owner token')
 blob=Path(template).read_bytes()
 if hashlib.sha256(blob).hexdigest()!=profile['template_sha256']:raise ValueError('RAM template does not match its profile hash')
 fit=fdt(blob);dt_old=fit['/images/fdt-1']['data'];dt=fdt(dt_old)
 image=bytearray(lzma.decompress(fit['/images/kernel-1']['data'],format=lzma.FORMAT_ALONE))
 # Profile describes the initramfs section offset/size, not an arbitrary guess.
 offset=profile['cpio_embedded_offset'];reserved=profile['cpio_section_bytes'];used=profile['cpio_used_bytes']
 if not 0<used<=reserved or offset+reserved>len(image):raise ValueError('Initramfs bounds')
 entries=cpio_parse(image[offset:offset+used]);changed=[]
 for n,h,p in entries:
  if n=='etc/rc.d/S18mf297d-radio':continue # no UBI autoattach / Q6 in maintenance
  if n=='etc/config/nss':p=p.replace(b"option enabled '1'",b"option enabled '0'").replace(b"option wifi_offload '1'",b"option wifi_offload '0'")
  changed.append((n,h,p))
 cpio=cpio_pack(changed)
 if len(cpio)>reserved:raise ValueError('Initramfs outgrew section')
 image[offset:offset+reserved]=cpio.ljust(reserved,b'\0')
 for k in ['linux,initrd-start','linux,initrd-end']:dt['/chosen'].pop(k,None)
 args='console=ttyMSM0,115200n8 root=/dev/ram0 rdinit=/init rootfstype=ramfs coherent_pool=2M reset_devices maxcpus=1 clk_ignore_unused panic=20'
 args+=(' mf297d.recovery=1' if mode=='recovery' else ' mf297d.install_stock='+('1' if mode=='phase-a' else '2'))+' mf297d.owner_token='+token
 dt['/chosen']['bootargs']=(args+'\0').encode()
 part=[n for n,p in dt.items() if p.get('label')==b'rootfs\0']
 if len(part)!=1:raise ValueError('Root partition')
 parent=part[0].rsplit('/',1)[0]
 # Rebuild only partition metadata; all peripheral bindings remain identical.
 for n in list(dt):
  if n.startswith(parent+'/') and 'reg' in dt[n] and 'label' in dt[n]:
   addr,size=struct.unpack('>II',dt[n]['reg'])
   if addr>=0x2cc0000 and n!=part[0]:del dt[n]
   else:dt[n]['read-only']=b''
 short=mode=='phase-a';dt[part[0]]['reg']=struct.pack('>II',0x2cc0000,0x3a00000 if short else 0xd340000)
 if short:
  for off,size,label in [(0x66c0000,0x200000,'openwrt_data'),(0x68c0000,0x3500000,'data'),(0x9dc0000,0x6240000,'fota')]:dt[parent+f'/partition@{off:x}']={'reg':struct.pack('>II',off,size),'label':(label+'\0').encode(),'read-only':b''}
 if mode!='recovery':
  dt[part[0]].pop('read-only',None);dt[part[0]]['label']=b'maintenance_storage\0'
  if mode=='phase-a':
   env=[n for n,p in dt.items() if p.get('label',b'').lower()==b'0:appsblenv\0']
   if len(env)!=1:raise ValueError('ENV partition')
   dt[env[0]].pop('read-only',None)
 if mode=='recovery' and 0x41000000+struct.unpack_from('<Q',image,16)[0]>0x44000000:raise ValueError('FIT decompression would overlap source')
 fit['/images/fdt-1']['data']=encode(dt,dt_old);fit['/images/kernel-1']['data']=lzma.compress(bytes(image),format=lzma.FORMAT_ALONE,preset=6)
 return fit_blob(fit,blob),bytes(image),fit['/images/fdt-1']['data'],args
def bootcmd(kernel,recovery,native_args,recovery_args,original_bootcmd,original_bootargs,original_mtdids,original_mtdparts):
 # This command is only generated after stock loader/bootloader hashes match.
 def safe(s):
  if any(c in s for c in ["'",'\n','\r','\0']):raise ValueError('Unsupported ENV quoting')
  return s
 for v in [native_args,recovery_args,original_bootargs,original_mtdids,original_mtdparts]:safe(v)
 if original_bootcmd.strip()!='bootipq':raise ValueError('Only original bootipq baseline is supported')
 def attempt(volume,payload,args,span):
  length=hex(len(payload));word=int.from_bytes(struct.pack('>I',zlib.crc32(payload)),'little')
  steps=['setenv mtdids nand0=nand0',"setenv mtdparts 'mtdparts=nand0:"+span+"@0x2cc0000(fs)'",'ubi part fs','ubi read 0x44000000 '+volume,'crc32 0x44000000 '+length+' 0x43000000',f'itest.l *0x43000000 == 0x{word:08x}',"setenv bootargs '"+safe(args)+"'"]
  return ''.join('if '+x+'; then ' for x in steps)+'bootm 0x44000000#config@mp03.3; '+'fi; '*len(steps)
 recovery_args+=' mf297d.recovery_source=uboot'
 rec_button=attempt('owrt_recovery',recovery,recovery_args+' mf297d.recovery_button=1','0xd340000')+attempt('owrt_recovery',recovery,recovery_args+' mf297d.recovery_button=1','0x3a00000')
 normal=attempt('owrt_kernel',kernel,native_args,'0xd340000')
 fallback=attempt('owrt_recovery',recovery,recovery_args+' mf297d.recovery_button=0','0xd340000')+attempt('owrt_recovery',recovery,recovery_args+' mf297d.recovery_button=0','0x3a00000')
 restore="setenv mtdids '"+original_mtdids+"'; setenv mtdparts '"+original_mtdparts+"'; setenv bootargs '"+original_bootargs+"'; bootipq"
 return "sleep 2; if setexpr.l mf297d_button *0x01020004 '&' 1; then if itest.l ${mf297d_button} == 0; then "+rec_button+'fi; fi; '+normal+fallback+restore
