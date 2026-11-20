#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Enable LAN Telnet in an owner's plain-text MF297D CFG; offline file edit only."""
import argparse,json,re,sys
from pathlib import Path

def patch(data):
 if not 100<=len(data)<=2*1024*1024 or b'\0' in data:
  raise ValueError('Duz metin MF297D CFG yedegi secilmeli; firmware BIN dosyasi olmaz.')
 pattern=rb'(?m)^(telnet_lan_enable=)([01])(?=\r?$)'
 matches=list(re.finditer(pattern,data))
 if len(matches)!=1:raise ValueError('CFG icinde tek bir telnet_lan_enable=0/1 satiri bulunamadi.')
 m=matches[0];result=data[:m.start(2)]+b'1'+data[m.end(2):]
 assert len(result)==len(data)
 assert result[:m.start(2)]==data[:m.start(2)] and result[m.end(2):]==data[m.end(2):]
 return result

def convert(source,target):
 source=Path(source);target=Path(target)
 if source.resolve()==target.resolve():raise ValueError('Orijinal yedegin uzerine yazilmaz.')
 result=patch(source.read_bytes())
 with target.open('xb') as f:f.write(result)
 return target

def self_test():
 for nl in [b'\n',b'\r\n']:
  original=nl.join([b'model=MF297D',b'Password=test-only',b'telnet_lan_enable=0',b'telnet_wan_enable=0',b'x='+b'A'*100])+nl
  result=patch(original);assert result==original.replace(b'telnet_lan_enable=0',b'telnet_lan_enable=1')
  assert patch(result)==result
 for bad in [b'firmware\0'*30,b'x=1\n'*100,b'telnet_lan_enable=0\n'*10]:
  try:patch(bad)
  except ValueError:pass
  else:raise AssertionError('Invalid/ambiguous file accepted')
 return {'passed':True,'only_lan_telnet_byte_changed':True,'lf_crlf_preserved':True,'ambiguous_binary_rejected':True,'device_or_network_access':False}

def gui():
 import tkinter as tk
 from tkinter import filedialog,messagebox
 root=tk.Tk();root.withdraw()
 source=filedialog.askopenfilename(title='1. Kendi modeminin orijinal CFG yedegini sec',filetypes=[('ZTE CFG','*.CFG *.cfg'),('Tum dosyalar','*.*')])
 if not source:return
 target=filedialog.asksaveasfilename(title='2. Telnet acik yeni dosyayi kaydet',initialdir=str(Path(source).parent),initialfile='MF297D-LAN-Telnet.CFG',defaultextension='.CFG',filetypes=[('ZTE CFG','*.CFG')])
 if not target:return
 try:
  output=convert(source,target)
  messagebox.showinfo('Dosya hazir',f'{output}\n\nModemin ayar/config geri yukleme ekraninda bu dosyayi sec.\nYalniz LAN Telnet degeri 1 yapildi; sifreler degismedi.\nBu dosya sana ozeldir; GitHub veya foruma yukleme.')
 except Exception as e:messagebox.showerror('Dosya olusturulamadi',str(e))
 finally:root.destroy()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',nargs='?');p.add_argument('--out');p.add_argument('--self-test',action='store_true');p.add_argument('--result');a=p.parse_args()
 if a.self_test:
  result=self_test()
  if a.result:Path(a.result).write_text(json.dumps(result,indent=2)+'\n')
  if sys.stdout:print(json.dumps(result))
 elif a.source:
  if not a.out:p.error('--out gerekli')
  print(convert(a.source,a.out))
 else:gui()
if __name__=='__main__':main()
