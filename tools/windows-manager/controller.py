import json
import re
import secrets
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from cwmp import CwmpEngine, CwmpServers
from network_services import EthernetServices
from telnet_client import TelnetClient
import windows_net

USER1 = 'InternetGatewayDevice.User.1.Username'
PASS1 = 'InternetGatewayDevice.User.1.Password'
WAN_TELNET = 'InternetGatewayDevice.TelnetSwitch.WAN_Enable'
PERIOD = 'InternetGatewayDevice.ManagementServer.PeriodicInformInterval'
INFORM_ENABLE = 'InternetGatewayDevice.ManagementServer.PeriodicInformEnable'

def generate_password():
    return secrets.token_urlsafe(12) + 'aA7!'

def validate_password(password):
    if not 8 <= len(password) <= 32 or not all(33 <= ord(c) <= 126 for c in password):
        raise ValueError('Parola boşluksuz, 8–32 ASCII karakter olmalı')

def numeric_nv(reply, expected):
    lines = reply.replace('\r', '').splitlines()
    return any(line.strip() == str(expected) for line in lines)

class Manager:
    def __init__(self, data_dir, logger=lambda _: None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_callback = logger
        self.secrets = set()
        self.adapter = None
        self.original_network = None
        self.rules = None
        self.network = None
        self.engine = None
        self.servers = None
        self.original_period = None
        self.original_inform_enable = None
        self.ready = False
        self.active_job = False
        self.wan_pending = False
        self.stopping = threading.Event()
        self.status = 'Servisler kapalı'
        self.cleanup_file = self.data_dir / 'cleanup-pending.json'
        snapshot_path=self.data_dir/'original-network.json'
        if snapshot_path.exists():
            try:
                saved=json.loads(snapshot_path.read_text(encoding='utf-8'))
                if {'name','mac','index','dhcp','addresses','gateway'} <= set(saved):
                    self.original_network=saved
            except (ValueError,OSError):
                self.log('Eski ağ kaydı okunamadı; adaptör ayarları elle kontrol edilmeli')

    def log(self, message):
        message = str(message)
        for secret in self.secrets:
            if secret:
                message = message.replace(secret, '[PAROLA]')
        self.log_callback(message)

    def _set_values(self, parameters, timeout=110):
        result = self.engine.call('SetParameterValues', parameters, timeout)
        if result.get('status') not in ('0', '1'):
            raise RuntimeError('Modem ayar yazma durumunu doğrulamadı')
        return result

    def start(self, adapter):
        if self.engine:
            raise RuntimeError('ACS zaten çalışıyor')
        if not windows_net.is_admin():
            raise PermissionError('Yönetici olarak açın')
        # These checks do not change the NIC; fail before saving/changing anything.
        for port in (80, 443):
            probe = socket.socket()
            try:
                probe.bind(('0.0.0.0', port))
            except OSError as error:
                raise RuntimeError(f'{port} portu kullanımda. Diğer ACS/web sunucusunu kapatın.') from error
            finally:
                probe.close()
        EthernetServices.find_interface(adapter['Name'], adapter['MacAddress'])
        original_candidate = windows_net.snapshot(adapter)
        if len(original_candidate['addresses']) > 1:
            raise RuntimeError('Bu adaptörde birden fazla IPv4 var; otomatik değiştirilmedi')
        # Never overwrite an unrecovered network snapshot from an earlier crash.
        snapshot_path = self.data_dir / 'original-network.json'
        if snapshot_path.exists():
            saved = json.loads(snapshot_path.read_text(encoding='utf-8'))
            if saved.get('mac') != original_candidate['mac']:
                raise RuntimeError('Önce önceki adaptörün ağ ayarını geri yükleyin')
            self.original_network = saved
        else:
            self.original_network = original_candidate
            snapshot_path.write_text(json.dumps(self.original_network, indent=2), encoding='utf-8')
        self.adapter = adapter
        self.stopping.clear()
        try:
            windows_net.set_ipv4(adapter, '192.168.50.1')
            self.rules = windows_net.FirewallRules()
            self.rules.add(adapter, '192.168.50.1', '192.168.50.2', tcp=(80,443), udp=(53,67,123))
            self.engine = CwmpEngine(logger=self.log)
            self.servers = CwmpServers(self.engine, '192.168.50.1', self.data_dir / 'certificates')
            self.servers.start()
            self.network = EthernetServices(adapter['Name'], adapter['MacAddress'], logger=self.log)
            self.network.start()
            self.status = 'Modem bekleniyor — kablo WAN’da olmalı'
            threading.Thread(target=self._bootstrap, daemon=True).start()
        except Exception:
            self._close_services()
            if self.original_network:
                windows_net.restore(self.original_network)
                snapshot_path.unlink(missing_ok=True)
            raise

    def _bootstrap(self):
        try:
            engine = self.engine
            baseline = engine.call('GetParameterValues', [USER1, PERIOD, INFORM_ENABLE, WAN_TELNET], timeout=240)
            if self.stopping.is_set():
                return
            if baseline.get(USER1) != 'sUser':
                raise RuntimeError('User.1 hesabı sUser değil; bu firmware için otomatik işlem yapılmadı')
            self.original_period = baseline.get(PERIOD, '3600')
            self.original_inform_enable = baseline.get(INFORM_ENABLE, '1')
            if self.cleanup_file.exists():
                recovery = json.loads(self.cleanup_file.read_text(encoding='utf-8'))
                if recovery.get('serial') != engine.device['serial']:
                    raise RuntimeError('Önceki temizlik kaydı başka cihaza ait')
                self.original_period = recovery.get('original_period', self.original_period)
                self.original_inform_enable = recovery.get('original_inform_enable', self.original_inform_enable)
                self.log('Önceki oturumun WAN Telnet kapatma işlemi tamamlanıyor')
                self._set_values({WAN_TELNET: ('0','xsd:boolean')})
            self.cleanup_file.write_text(json.dumps({'serial':engine.device['serial'],
                'original_period':self.original_period,'original_inform_enable':self.original_inform_enable,
                'wan_telnet_pending':False},indent=2),encoding='utf-8')
            self._set_values({PERIOD: ('30','xsd:unsignedInt'), INFORM_ENABLE: ('1','xsd:boolean')})
            self.ready = True
            self.status = 'MF297D hazır'
            self.log('sUser hesabı ve MF297D modeli doğrulandı; işlem başlatılabilir')
        except Exception as error:
            if not self.stopping.is_set():
                self.status = 'Hazırlık tamamlanamadı'
                self.log('Hazırlık hatası: ' + str(error))

    def provision(self, password, change_password=True):
        validate_password(password)
        if not self.ready or self.active_job:
            raise RuntimeError('Önce ACS bağlantısını ve hazırlık durumunu bekleyin')
        self.secrets.add(password)
        self.active_job = True
        self.status = 'sUser / LAN Telnet uygulanıyor'
        self.wan_pending = True
        recovery = {'serial': self.engine.device['serial'], 'wan_telnet_target': '0', 'wan_telnet_pending':True,
            'original_period': self.original_period, 'original_inform_enable': self.original_inform_enable}
        self.cleanup_file.write_text(json.dumps(recovery, indent=2), encoding='utf-8')
        try:
            values = {WAN_TELNET: ('1', 'xsd:boolean')}
            if change_password:
                values[PASS1] = (password, 'xsd:string')
            self._set_values(values)
            self.log('Modem ayar isteğini kabul etti; Telnet 2323 sınanıyor')
            client = None
            last_error = None
            for _ in range(4):
                try:
                    client = TelnetClient('192.168.50.2', timeout=8)
                    client.login('sUser', password)
                    break
                except (OSError, PermissionError, TimeoutError) as error:
                    last_error = error
                    if client:
                        client.close()
                    client = None
                    time.sleep(2)
            if client is None:
                raise RuntimeError('Root Telnet doğrulanamadı: ' + str(last_error))
            try:
                self.log('Root yetkisi doğrulandı: uid=0(root)')
                before, code = client.command('nv get telnet_lan_enable')
                if code:
                    raise RuntimeError('LAN Telnet değeri okunamadı')
                if not numeric_nv(before, 1):
                    _, code = client.command('nv set telnet_lan_enable=1')
                    if code:
                        raise RuntimeError('LAN Telnet yazılamadı')
                _, code = client.command('nv save')
                if code:
                    raise RuntimeError('Ayar kalıcı kaydedilemedi')
                after, code = client.command('nv get telnet_lan_enable')
                if code or not numeric_nv(after, 1):
                    raise RuntimeError('LAN Telnet değeri 1 olarak doğrulanamadı')
                self.log('telnet_lan_enable=1 yazıldı ve kaydedildi')
            finally:
                client.close()
            self.status = 'LAN Telnet ayarı kaydedildi — LAN’dan doğrulayın'
        finally:
            cleanup_error = None
            try:
                self._set_values({WAN_TELNET: ('0', 'xsd:boolean')}, timeout=110)
                self.wan_pending = False
                recovery['wan_telnet_pending'] = False
                self.cleanup_file.write_text(json.dumps(recovery,indent=2),encoding='utf-8')
                self.log('WAN Telnet tekrar kapatıldı; modem onayladı')
            except Exception as error:
                cleanup_error = error
                self.status = 'WAN Telnet kapatma onayı bekleniyor'
                self.log('WAN kapatma doğrulanamadı. Servisleri açık tutup modemi WAN’a bağlayın: ' + str(error))
            self.active_job = False
            if cleanup_error:
                raise RuntimeError('WAN Telnet kapatma doğrulanamadı; uygulamayı ve WAN bağlantısını açık tutun') from cleanup_error

    def export_config(self, output):
        if not self.ready or self.active_job:
            raise RuntimeError('ACS bağlantısı hazır değil veya başka işlem var')
        self.active_job = True
        try:
            methods = self.engine.call('GetRPCMethods', timeout=100)
            if 'Upload' not in methods:
                raise RuntimeError('Bu firmware Upload işlemini bildirmedi')
            token, ticket = self.engine.upload_ticket(output)
            self.engine.call('Upload', 'http://192.168.50.1/upload/' + token, timeout=100)
            if not ticket['event'].wait(100):
                raise TimeoutError('Config aktarımı tamamlanmadı')
            if ticket['error']:
                raise RuntimeError(ticket['error'])
            return {'path': str(output), 'bytes': ticket['bytes'], 'sha256': ticket['sha256']}
        finally:
            self.active_job = False

    def stop(self, restore_network=True):
        if self.active_job:
            raise RuntimeError('İşlem bitmeden servisler kapatılamaz')
        if self.engine and self.wan_pending:
            self._set_values({WAN_TELNET: ('0','xsd:boolean')}, timeout=100)
            self.wan_pending = False
        if self.engine and self.ready and self.original_period is not None:
            self._set_values({PERIOD: (self.original_period, 'xsd:unsignedInt'),
                INFORM_ENABLE: (self.original_inform_enable, 'xsd:boolean')}, timeout=50)
            self.cleanup_file.unlink(missing_ok=True)
        self.stopping.set()
        self._close_services()
        if restore_network and self.original_network:
            windows_net.restore(self.original_network)
            (self.data_dir / 'original-network.json').unlink(missing_ok=True)
            self.original_network = None
        self.ready = False
        self.status = 'Servisler kapalı'

    def _close_services(self):
        if self.network:
            self.network.stop()
            self.network = None
        if self.servers:
            self.servers.stop()
            self.servers = None
        elif self.engine:
            self.engine.close()
        self.engine = None
        if self.rules:
            self.rules.remove()
            self.rules = None

    def prepare_lan(self, adapter, password):
        if self.active_job:
            raise RuntimeError('Önce mevcut işlemi tamamlayın')
        if self.engine:
            raise RuntimeError('Önce WAN servislerini durdurun; sonra kabloyu LAN’a geçirin')
        self.secrets.add(password)
        if not self.original_network:
            self.original_network = windows_net.snapshot(adapter)
            if len(self.original_network['addresses']) > 1:
                self.original_network = None
                raise RuntimeError('Bu adaptörde birden fazla IPv4 var; otomatik değiştirilmedi')
            (self.data_dir / 'original-network.json').write_text(json.dumps(self.original_network,indent=2),encoding='utf-8')
        windows_net.set_ipv4(adapter, '192.168.1.2')
        client = TelnetClient('192.168.1.1')
        try:
            result = client.login('sUser', password)
            self.status = 'LAN root Telnet doğrulandı — 192.168.1.1:2323'
            self.log(self.status)
            return result
        finally:
            client.close()
