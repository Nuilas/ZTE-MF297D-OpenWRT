import argparse
import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from controller import Manager, generate_password
from flash_backup import run_backup
import windows_net

VERSION = '1.0.0'

class Application:
    def __init__(self, root, data_dir, preview=False):
        self.root, self.data_dir, self.preview = root, Path(data_dir), preview
        self.events = queue.Queue()
        self.manager = Manager(self.data_dir, logger=lambda text:self.events.put(('log', text)))
        self.busy = False
        self.adapter_items = []
        self.closing = False
        self.password = tk.StringVar(value=generate_password())
        self.change_password = tk.BooleanVar(value=True)
        self.show_password = tk.BooleanVar(value=False)
        self.adapter_choice = tk.StringVar()
        self.state_text = tk.StringVar(value='Servisler kapalı')
        self.device_text = tk.StringVar(value='Henüz modem bağlanmadı')
        root.title('MF297D Yerel Yönetici')
        root.geometry('1080x900')
        root.minsize(960,760)
        root.configure(bg='#101624')
        self.style()
        self.build()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.tick)
        self.refresh()

    def style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', background='#101624', foreground='#e8edf6', font=('Segoe UI',10))
        style.configure('TFrame', background='#101624')
        style.configure('Card.TFrame', background='#182236')
        style.configure('Card.TLabel', background='#182236', foreground='#e8edf6')
        style.configure('Muted.TLabel', foreground='#a9b8d2')
        style.configure('Title.TLabel', font=('Segoe UI Semibold',23), foreground='#ffffff')
        style.configure('Section.TLabel', font=('Segoe UI Semibold',12), background='#182236')
        style.configure('TButton', padding=(13,8), background='#293a56', borderwidth=0)
        style.map('TButton', background=[('active','#365175'),('disabled','#202d40')],foreground=[('disabled','#71809a')])
        style.configure('Accent.TButton', background='#6459ef', foreground='white')
        style.map('Accent.TButton',background=[('active','#786eff'),('disabled','#343650')])
        style.configure('TEntry', fieldbackground='#0f1829', foreground='#f0f5ff', insertcolor='white', borderwidth=1, padding=6)
        style.configure('TCombobox',fieldbackground='#0f1829',foreground='#f0f5ff',padding=6)
        style.map('TCombobox',fieldbackground=[('readonly','#0f1829')],foreground=[('readonly','#f0f5ff')])
        style.configure('TCheckbutton',background='#182236',foreground='#dce6f8')
        style.map('TCheckbutton',background=[('active','#182236')])
        style.configure('TNotebook',background='#101624',borderwidth=0)
        style.configure('TNotebook.Tab',padding=(20,10),background='#1b2940')
        style.map('TNotebook.Tab',background=[('selected','#6459ef')],foreground=[('selected','white')])
        style.configure('TProgressbar',background='#8278ff',troughcolor='#23314b',borderwidth=0)

    def card(self, parent, title, row):
        frame=ttk.Frame(parent,style='Card.TFrame',padding=16)
        frame.grid(row=row,column=0,sticky='ew',pady=(0,10))
        frame.columnconfigure(0,weight=1)
        ttk.Label(frame,text=title,style='Section.TLabel').grid(row=0,column=0,columnspan=4,sticky='w',pady=(0,10))
        return frame

    def scroll_page(self,parent):
        outer=ttk.Frame(parent)
        canvas=tk.Canvas(outer,bg='#101624',highlightthickness=0)
        bar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=bar.set)
        inner=ttk.Frame(canvas,padding=(0,14,8,0));inner.columnconfigure(0,weight=1)
        item=canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
        def wheel(event):
            widget=self.root.winfo_containing(event.x_root,event.y_root)
            while widget:
                if widget is outer:
                    canvas.yview_scroll(-int(event.delta/120),'units');break
                widget=getattr(widget,'master',None)
        self.root.bind_all('<MouseWheel>',wheel,add='+')
        return outer,inner

    def build(self):
        header=ttk.Frame(self.root,padding=(24,18))
        header.pack(fill='x')
        ttk.Label(header,text='MF297D Yerel Yönetici',style='Title.TLabel').pack(anchor='w')
        ttk.Label(header,text='Bağımsız ACS  ·  sUser  ·  LAN root Telnet  ·  Yedekleme',style='Muted.TLabel').pack(anchor='w',pady=(4,0))
        toolbar=ttk.Frame(header)
        toolbar.pack(fill='x',pady=(12,0))
        admin='Yönetici yetkisi açık' if windows_net.is_admin() else 'Ağ işlemleri için yönetici yetkisi gerekli'
        if self.preview:admin='ÖNİZLEME — tüm modem/ağ işlemleri kapalı'
        ttk.Label(toolbar,text=admin,style='Muted.TLabel').pack(side='left')
        if not windows_net.is_admin() and not self.preview:
            ttk.Button(toolbar,text='Yönetici olarak yeniden aç',command=self.elevate).pack(side='right')
        tabs=ttk.Notebook(self.root)
        tabs.pack(fill='both',expand=True,padx=24,pady=(0,12))
        setup_outer,setup=self.scroll_page(tabs)
        backup_outer,backup=self.scroll_page(tabs)
        logs=ttk.Frame(tabs,padding=(0,14));logs.columnconfigure(0,weight=1);logs.rowconfigure(0,weight=1)
        tabs.add(setup_outer,text='Kurulum');tabs.add(backup_outer,text='Yedekler');tabs.add(logs,text='Kayıtlar')

        net=self.card(setup,'1  Ethernet ve WAN bağlantısı',0)
        self.combo=ttk.Combobox(net,textvariable=self.adapter_choice,state='readonly',width=62)
        self.combo.grid(row=1,column=0,columnspan=2,sticky='ew',padx=(0,10))
        ttk.Button(net,text='Yenile',command=self.refresh).grid(row=1,column=2)
        ttk.Label(net,text='Modem kablosunu WAN’a takın. WAN modu: Dinamik IP (DHCP) veya 192.168.50.2/24.\nStatik modda ağ geçidi ve DNS: 192.168.50.1. Diğer ACS programlarını kapatın.',style='Card.TLabel',wraplength=960).grid(row=2,column=0,columnspan=4,sticky='w',pady=10)
        self.start_button=ttk.Button(net,text='WAN servislerini başlat',style='Accent.TButton',command=self.start)
        self.start_button.grid(row=3,column=0,sticky='w')
        ttk.Label(net,text='Yalnız seçili Ethernet  →  bilgisayar 192.168.50.1  /  modem 192.168.50.2',style='Card.TLabel').grid(row=4,column=0,columnspan=4,sticky='w',pady=(10,0))

        account=self.card(setup,'2  sUser parolası ve LAN Telnet',1)
        ttk.Label(account,text='sUser parolası',style='Card.TLabel').grid(row=1,column=0,sticky='w')
        self.password_entry=ttk.Entry(account,textvariable=self.password,show='●',width=37)
        self.password_entry.grid(row=1,column=1,sticky='ew',padx=10)
        ttk.Button(account,text='Yeni üret',command=lambda:self.password.set(generate_password())).grid(row=1,column=2,padx=(0,8))
        ttk.Checkbutton(account,text='Göster',variable=self.show_password,command=lambda:self.password_entry.configure(show='' if self.show_password.get() else '●')).grid(row=1,column=3)
        ttk.Checkbutton(account,text='sUser parolasını bu değerle değiştir (kapalıysa mevcut parolayı girin)',variable=self.change_password).grid(row=2,column=0,columnspan=4,sticky='w',pady=10)
        ttk.Label(account,text='Modem MF297D ve hesap sUser olarak doğrulanır. Geçici WAN Telnet 2323 açılır,\nroot kimliği kontrol edilir, LAN Telnet kaydedilir ve WAN Telnet tekrar kapatılır.',style='Card.TLabel').grid(row=3,column=0,columnspan=4,sticky='w',pady=(0,10))
        self.apply_button=ttk.Button(account,text='sUser + LAN Telnet uygula',style='Accent.TButton',command=self.apply)
        self.apply_button.grid(row=4,column=0,columnspan=2,sticky='w')
        ttk.Button(account,text='Parolayı kopyala',command=self.copy_password).grid(row=4,column=3,sticky='e')

        lan=self.card(setup,'3  WAN’ı kapat, LAN’dan doğrula',2)
        ttk.Label(lan,text='Önce WAN servislerini durdurun. Ardından kabloyu LAN’a taşıyıp LAN kontrolüne basın.\nLAN kontrolü seçili Ethernet’i 192.168.1.2 yapar ve 192.168.1.1:2323 üzerinde uid=0 doğrular.',style='Card.TLabel').grid(row=1,column=0,columnspan=4,sticky='w',pady=(0,10))
        self.stop_button=ttk.Button(lan,text='WAN servislerini durdur',command=self.stop)
        self.stop_button.grid(row=2,column=0,sticky='w')
        self.lan_button=ttk.Button(lan,text='LAN root bağlantısını doğrula',command=self.lan_check)
        self.lan_button.grid(row=2,column=1,sticky='w',padx=12)

        cfg=self.card(backup,'Config dosyası — WAN / ACS',0)
        ttk.Label(cfg,text='Modemin desteklediği Upload işlemiyle gerçek vendor config dosyasını alır.\nModem ACS’ye bağlı olmalı. Bu uygulama config veya firmware geri yüklemez.',style='Card.TLabel').grid(row=1,column=0,sticky='w',pady=(0,12))
        self.config_button=ttk.Button(cfg,text='Config yedeği al',style='Accent.TButton',command=self.config_backup)
        self.config_button.grid(row=2,column=0,sticky='w')
        flash=self.card(backup,'Flash veri alanı — LAN / root Telnet',1)
        ttk.Label(flash,text='Kablo LAN’da olmalı; yukarıdaki sUser alanında mevcut parola bulunmalı.\nBölümleri yalnız /dev/mtdNro aygıtlarından okur; boyut ve SHA256 kayıtları oluşturur.\nNAND OOB dahil değildir. Canlı yedek, programlayıcıya hazır ham NAND imajı değildir.',style='Card.TLabel',wraplength=950).grid(row=1,column=0,sticky='w',pady=(0,12))
        self.flash_button=ttk.Button(flash,text='LAN üzerinden flash veri yedeği al',command=self.flash_backup)
        self.flash_button.grid(row=2,column=0,sticky='w')
        ttk.Label(backup,text='Yedeklerde cihazınıza özel anahtarlar ve parolalar bulunabilir. Dosyalar yalnız seçtiğiniz klasöre kaydedilir.',style='Muted.TLabel',wraplength=970).grid(row=2,column=0,sticky='w',pady=12)

        self.log_text=tk.Text(logs,bg='#0c1220',fg='#b8cce8',insertbackground='white',relief='flat',font=('Consolas',10),wrap='word',state='disabled')
        self.log_text.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(logs,command=self.log_text.yview);scroll.grid(row=0,column=1,sticky='ns');self.log_text.configure(yscrollcommand=scroll.set)
        footer=ttk.Frame(self.root,padding=(24,0,24,16));footer.pack(fill='x')
        ttk.Label(footer,textvariable=self.state_text,font=('Segoe UI Semibold',11)).pack(anchor='w')
        ttk.Label(footer,textvariable=self.device_text,style='Muted.TLabel').pack(anchor='w',pady=(4,8))
        self.progress=ttk.Progressbar(footer,mode='indeterminate');self.progress.pack(fill='x')
        ttk.Label(footer,text=f'v{VERSION}  ·  Hedef ZTE MF297D  ·  Npcap gerekir  ·  Telnet portu 2323',style='Muted.TLabel').pack(anchor='w',pady=(8,0))

    def chosen_adapter(self):
        index=self.combo.current()
        if index<0 or index>=len(self.adapter_items):
            raise RuntimeError('Fiziksel Ethernet adaptörünü seçin')
        return self.adapter_items[index]

    def run(self, task, done=None):
        if self.preview:
            messagebox.showinfo('Önizleme','Bu pencerede ağ ve modem işlemleri kapalıdır.');return
        if self.busy:
            return
        self.busy=True;self.progress.start(12)
        def worker():
            try:self.events.put(('done',done,task()))
            except Exception as error:self.events.put(('error',str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def refresh(self):
        if self.busy:return
        if self.preview:
            self.adapter_items=[dict(Name='Ethernet',ifIndex=6,MacAddress='00-00-00-00-00-00',Status='Up')]
            self.combo.configure(values=['Ethernet — önizleme']);self.combo.current(0);return
        def done(items):
            self.adapter_items=items
            self.combo.configure(values=[f"{i['Name']}  ·  {i['MacAddress']}  ·  {i['Status']}" for i in items])
            self.adapter_choice.set('Ethernet adaptörünü açıkça seçin')
        self.run(windows_net.adapters,done)

    def start(self):
        try:adapter=self.chosen_adapter()
        except Exception as error:messagebox.showerror('Adaptör',str(error));return
        self.run(lambda:self.manager.start(adapter))

    def apply(self):
        password=self.password.get();change=self.change_password.get()
        self.run(lambda:self.manager.provision(password,change),lambda _:messagebox.showinfo('Tamamlandı','LAN Telnet kaydedildi. WAN Telnet kapatma durumunu kayıtlar bölümünden kontrol edin.'))

    def stop(self):
        self.run(lambda:self.manager.stop())

    def lan_check(self):
        try:adapter=self.chosen_adapter()
        except Exception as error:messagebox.showerror('Adaptör',str(error));return
        password=self.password.get()
        self.run(lambda:self.manager.prepare_lan(adapter,password),lambda _:messagebox.showinfo('Doğrulandı','LAN Telnet 192.168.1.1:2323 üzerinde uid=0(root) doğrulandı.'))

    def config_backup(self):
        path=filedialog.asksaveasfilename(title='Config yedeği',defaultextension='.CFG',initialfile='MF297D-config.CFG',filetypes=[('Config','*.CFG')])
        if path:self.run(lambda:self.manager.export_config(path),lambda result:messagebox.showinfo('Yedek alındı',f"{result['bytes']} bayt\n{result['path']}"))

    def flash_backup(self):
        if self.manager.engine:
            messagebox.showinfo('WAN açık','Önce WAN servislerini durdurun, sonra kabloyu LAN’a taşıyın.');return
        parent=filedialog.askdirectory(title='Flash yedeği için üst klasör seçin')
        if not parent:return
        try:adapter=self.chosen_adapter()
        except Exception as error:messagebox.showerror('Adaptör',str(error));return
        password=self.password.get()
        directory=Path(parent)/('MF297D-flash-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        def task():
            if not windows_net.is_admin():raise PermissionError('Yönetici olarak açın')
            self.manager.secrets.add(password)
            self.manager.prepare_lan(adapter,password)
            rules=windows_net.FirewallRules()
            try:
                rules.add(adapter,'192.168.1.2','192.168.1.1',udp=(1069,))
                return run_backup('192.168.1.1','192.168.1.2','sUser',password,directory,self.manager.log)
            finally:rules.remove()
        self.run(task,lambda result:messagebox.showinfo('Yedekleme',f"Tüm bölümler alındı: {result['complete']}\n{directory}\nOOB dahil değildir."))

    def copy_password(self):
        self.root.clipboard_clear();self.root.clipboard_append(self.password.get())

    def elevate(self):
        if windows_net.relaunch_admin(['--data-dir',str(self.data_dir)]):self.root.destroy()

    def tick(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='log':
                    self.log_text.configure(state='normal');self.log_text.insert('end',datetime.now().strftime('%H:%M:%S')+'  '+event[1]+'\n');self.log_text.see('end');self.log_text.configure(state='disabled')
                elif event[0]=='done':
                    self.busy=False;self.progress.stop()
                    if event[1]:event[1](event[2])
                elif event[0]=='error':
                    self.busy=False;self.progress.stop();self.manager.log(event[1]);messagebox.showerror('İşlem tamamlanamadı',event[1])
        except queue.Empty:pass
        self.state_text.set(self.manager.status)
        if self.manager.engine and self.manager.engine.device:
            d=self.manager.engine.device;self.device_text.set(f"{d['model']}  ·  {d['serial']}  ·  {d['firmware']}")
        for button,enabled in [(self.start_button,not self.manager.engine),(self.apply_button,self.manager.ready),(self.config_button,self.manager.ready),(self.stop_button,bool(self.manager.engine or self.manager.original_network)),(self.lan_button,not self.manager.engine),(self.flash_button,not self.manager.engine)]:
            button.configure(state='normal' if enabled and not self.busy else 'disabled')
        self.combo.configure(state='disabled' if self.manager.engine or self.busy else 'readonly')
        self.root.after(150,self.tick)

    def close(self):
        if self.busy:
            messagebox.showinfo('İşlem sürüyor','Mevcut işlem ve WAN kapatma doğrulaması tamamlanana kadar bekleyin.');return
        if self.manager.engine or self.manager.original_network:
            self.run(lambda:self.manager.stop(),lambda _:self.root.destroy());return
        self.root.destroy()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--gui-smoke-test',action='store_true')
    parser.add_argument('--report')
    args=parser.parse_args()
    if args.self_test:
        import scapy.arch.windows
        import cryptography
        result={'version':VERSION,'imports':'ok','device_changes':False}
        if args.report:Path(args.report).write_text(json.dumps(result),encoding='utf-8')
        else:print(json.dumps(result))
        return
    directory=Path(args.data_dir) if args.data_dir else Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'MF297DManager'
    root=tk.Tk()
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    try:root.iconbitmap(str(resources/'assets'/'app.ico'))
    except tk.TclError:pass
    if args.gui_smoke_test:root.withdraw()
    app=Application(root,directory,args.preview or args.gui_smoke_test)
    if args.gui_smoke_test:
        root.update_idletasks();root.update()
        assert app.preview and app.manager.engine is None and hasattr(app,'apply_button')
        result={'version':VERSION,'gui':'ok','device_changes':False,'preview':True}
        if args.report:Path(args.report).write_text(json.dumps(result),encoding='utf-8')
        root.destroy();return
    root.mainloop()

if __name__=='__main__':main()
