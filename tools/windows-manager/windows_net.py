"""Explicit, reversible changes to one selected physical Ethernet adapter."""
import ctypes
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000

def is_admin():
    return os.name == 'nt' and bool(ctypes.windll.shell32.IsUserAnAdmin())

def powershell(script, payload=None):
    prefix = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); "
    if payload is not None:
        prefix += '$p=[Console]::In.ReadToEnd() | ConvertFrom-Json; '
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', prefix + script],
        input=None if payload is None else json.dumps(payload, ensure_ascii=False),
        text=True, encoding='utf-8', errors='replace', capture_output=True,
        creationflags=CREATE_NO_WINDOW, timeout=30)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-1200:])
    return result.stdout.strip()

def adapters():
    result = powershell("@(Get-NetAdapter -Physical | Select-Object Name,ifIndex,MacAddress,InterfaceDescription,Status,InterfaceType) | ConvertTo-Json -Depth 3 -Compress")
    data = json.loads(result or '[]')
    if isinstance(data, dict):
        data = [data]
    return [item for item in data if item.get('InterfaceType') == 6 and item.get('MacAddress')
        and not re.search(r'Remote NDIS|Internet Sharing|Tailscale|VMware|Hyper-V|Virtual|VPN|Loopback',
            item.get('InterfaceDescription',''), re.I)]

def snapshot(adapter):
    data = powershell("$a=Get-NetAdapter | Where-Object {$_.ifIndex -eq $p.index}; "
        "$ip=@(Get-NetIPAddress -InterfaceIndex $p.index -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.PrefixOrigin -ne 'WellKnown'}); "
        "$gw=@(Get-NetRoute -InterfaceIndex $p.index -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue); "
        "$iface=Get-NetIPInterface -InterfaceIndex $p.index -AddressFamily IPv4; "
        "[pscustomobject]@{name=$a.Name;mac=$a.MacAddress;index=$a.ifIndex;dhcp=($iface.Dhcp -eq 'Enabled');addresses=@($ip|Select-Object IPAddress,PrefixLength);gateway=($gw|Select-Object -First 1 -ExpandProperty NextHop)} | ConvertTo-Json -Depth 5 -Compress",
        {'index': adapter['ifIndex']})
    return json.loads(data)

def set_ipv4(adapter, address):
    if not is_admin():
        raise PermissionError('Ağ ayarı için yönetici yetkisi gerekiyor')
    current = next((item for item in adapters() if item['ifIndex'] == adapter['ifIndex']), None)
    if not current or current['MacAddress'] != adapter['MacAddress']:
        raise RuntimeError('Seçilen fiziksel Ethernet adaptörü değişti; işlem durduruldu')
    result = subprocess.run(['netsh', 'interface', 'ipv4', 'set', 'address',
        'name=' + current['Name'], 'source=static', 'address=' + address,
        'mask=255.255.255.0', 'gateway=none'], capture_output=True,
        creationflags=CREATE_NO_WINDOW, timeout=25)
    if result.returncode:
        raise RuntimeError('Ethernet IPv4 ayarı uygulanamadı')

def restore(snapshot_data):
    if not snapshot_data:
        return
    current = next((item for item in adapters() if item['MacAddress'] == snapshot_data['mac']), None)
    if not current:
        raise RuntimeError('Eski ağ ayarının adaptörü bulunamadı')
    args = ['netsh', 'interface', 'ipv4', 'set', 'address', 'name=' + current['Name']]
    if snapshot_data['dhcp']:
        args += ['source=dhcp']
    elif snapshot_data['addresses']:
        address = snapshot_data['addresses'][0]
        prefix = int(address['PrefixLength'])
        mask = (0xffffffff << (32-prefix)) & 0xffffffff if prefix else 0
        dotted = '.'.join(str((mask >> offset) & 255) for offset in (24, 16, 8, 0))
        args += ['source=static', 'address=' + address['IPAddress'], 'mask=' + dotted,
            'gateway=' + (snapshot_data.get('gateway') or 'none')]
    else:
        args += ['source=dhcp']
    result = subprocess.run(args, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=25)
    if result.returncode:
        raise RuntimeError('Eski Ethernet ayarı geri yüklenemedi')

class FirewallRules:
    def __init__(self):
        self.prefix = 'MF297DManager-' + uuid.uuid4().hex
        self.names = []

    def add(self, adapter, local_ip, peer_ip, tcp=(), udp=()):
        for protocol, ports in [('TCP', tcp), ('UDP', udp)]:
            if not ports:
                continue
            name = self.prefix + '-' + protocol
            powershell("New-NetFirewallRule -Name $p.name -DisplayName 'MF297D Manager - geçici yerel erişim' "
                "-Direction Inbound -Action Allow -Protocol $p.protocol -LocalPort $p.ports "
                "-LocalAddress $p.local -RemoteAddress $p.peer -InterfaceAlias $p.adapter -Profile Any | Out-Null",
                dict(name=name, protocol=protocol, ports=list(ports), local=local_ip,
                    peer=peer_ip, adapter=adapter['Name']))
            self.names.append(name)

    def remove(self):
        errors = []
        for name in self.names[:]:
            try:
                powershell('Remove-NetFirewallRule -Name $p.name -ErrorAction SilentlyContinue', {'name': name})
                self.names.remove(name)
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))

def relaunch_admin(arguments):
    command = sys.executable
    args = list(arguments)
    if not getattr(sys, 'frozen', False):
        args.insert(0, str(Path(__file__).with_name('gui.py')))
    result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', command,
        subprocess.list2cmdline(args), str(Path(command).parent), 1)
    return result > 32
