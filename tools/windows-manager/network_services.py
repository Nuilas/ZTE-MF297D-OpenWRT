"""DHCP, limited DNS and NTP replies on exactly one selected Ethernet NIC."""
import socket
import struct
import threading
import time

ACS_DOMAIN = 'acs.superonline.net'

def allowed_dns(name):
    name = name.rstrip('.').lower()
    return name == ACS_DOMAIN or name == 'cpentp.superonline.net' or name == 'pool.ntp.org' or name.endswith('.pool.ntp.org')

def ntp_reply(data, now=None):
    if len(data) < 48 or data[0] & 7 != 3:
        return None
    now = time.time() if now is None else now
    def stamp(value):
        value += 2208988800
        integer = int(value)
        return struct.pack('!II', integer, int((value-integer)*2**32))
    response = bytearray(48)
    response[:4] = bytes([0x24, 2, 6, 0xEC])
    response[8:12] = struct.pack('!I', 65536)
    response[12:16] = b'LOCL'
    response[16:24] = stamp(now-1)
    response[24:32] = data[40:48]
    response[32:40] = stamp(now)
    response[40:48] = stamp(now)
    return bytes(response)

class EthernetServices:
    def __init__(self, adapter_name, adapter_mac, host='192.168.50.1',
                 peer='192.168.50.2', logger=lambda _: None):
        self.adapter_name, self.adapter_mac = adapter_name, adapter_mac.lower().replace('-', ':')
        self.host, self.peer, self.logger = host, peer, logger
        self.peer_mac = None
        self.sniffer = None
        self.interface = None
        self.sinks = []
        self.stop_event = threading.Event()
        self.stats = {'dhcp': 0, 'dns': 0, 'ntp': 0}

    @staticmethod
    def find_interface(adapter_name, adapter_mac):
        from scapy.config import conf
        from scapy.arch.windows import get_windows_if_list
        from scapy.interfaces import resolve_iface
        conf.use_pcap = True
        wanted = adapter_mac.lower().replace('-', ':')
        candidates = [i for i in get_windows_if_list()
            if i.get('mac', '').lower().replace('-', ':') == wanted and i.get('name') == adapter_name]
        if len(candidates) != 1:
            raise RuntimeError('Seçilen Ethernet adaptörü Npcap içinde tekil bulunamadı')
        candidate = candidates[0]
        identifier = candidate.get('network_name') or ('\\Device\\NPF_' + candidate['guid'])
        interface = resolve_iface(identifier)
        if interface.mac.lower().replace('-', ':') != wanted:
            raise RuntimeError('Npcap adaptör MAC adresi doğrulanamadı')
        return interface

    def start(self):
        from scapy.sendrecv import AsyncSniffer
        self.interface = self.find_interface(self.adapter_name, self.adapter_mac)
        self.stop_event.clear()
        # Bound sockets prevent the local stack from returning Port Unreachable.
        for port in (53, 67, 123):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((self.host, port))
                sock.settimeout(0.5)
                self.sinks.append(sock)
                threading.Thread(target=self._consume, args=(sock,), daemon=True).start()
            except OSError:
                sock.close()
                self.logger(f'UDP {port} soketi kullanılamıyor; seçili NIC üzerinde paket yanıtı kullanılacak')
        self.sniffer = AsyncSniffer(iface=self.interface, store=False, prn=self._handle,
            filter='udp port 53 or udp port 67 or udp port 123 or (vlan and (udp port 53 or udp port 67 or udp port 123))')
        self.sniffer.start()
        time.sleep(0.3)
        if not self.sniffer.running or getattr(self.sniffer, 'exception', None):
            raise RuntimeError('Npcap paket yakalama başlatılamadı')
        self.logger('DHCP / DNS / saat servisi yalnız seçili Ethernet üzerinde başladı')

    def _consume(self, sock):
        while not self.stop_event.is_set():
            try:
                sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break

    def _layer2(self, packet, destination):
        from scapy.layers.l2 import Ether, Dot1Q
        result = Ether(src=self.adapter_mac, dst=destination)
        if Dot1Q in packet:
            vlan = packet[Dot1Q]
            result /= Dot1Q(vlan=vlan.vlan, prio=vlan.prio)
        return result

    def _handle(self, packet):
        from scapy.layers.l2 import Ether
        from scapy.layers.inet import IP, UDP
        from scapy.layers.dhcp import BOOTP, DHCP
        from scapy.layers.dns import DNS, DNSRR
        from scapy.packet import Raw
        from scapy.sendrecv import sendp
        try:
            if Ether not in packet or IP not in packet or UDP not in packet:
                return
            mac = packet[Ether].src.lower()
            if mac == self.adapter_mac or packet[IP].src == self.host:
                return
            is_dhcp = DHCP in packet and BOOTP in packet and packet[UDP].dport == 67
            if not is_dhcp and packet[IP].src != self.peer:
                return
            if self.peer_mac and self.peer_mac != mac:
                return
            self.peer_mac = mac
            if is_dhcp:
                options = {o[0]: o[1] for o in packet[DHCP].options if isinstance(o, tuple) and len(o) > 1}
                kind = options.get('message-type')
                if kind not in (1, 3, 'discover', 'request'):
                    return
                if kind in (3, 'request'):
                    requested = options.get('requested_addr')
                    server = options.get('server_id')
                    if server and server != self.host:
                        return
                    if requested and requested != self.peer:
                        return
                reply_kind = 2 if kind in (1, 'discover') else 5
                response = (self._layer2(packet, 'ff:ff:ff:ff:ff:ff') /
                    IP(src=self.host, dst='255.255.255.255') / UDP(sport=67, dport=68) /
                    BOOTP(op=2, htype=1, hlen=6, xid=packet[BOOTP].xid,
                        yiaddr=self.peer, siaddr=self.host, chaddr=packet[BOOTP].chaddr,
                        flags=packet[BOOTP].flags) /
                    DHCP(options=[('message-type', reply_kind), ('server_id', self.host),
                        ('lease_time', 3600), ('subnet_mask', '255.255.255.0'),
                        ('router', self.host), ('name_server', self.host), 'end']))
                sendp(response, iface=self.interface, verbose=False)
                self.stats['dhcp'] += 1
                self.logger('DHCP yanıtı: ' + self.peer)
            elif DNS in packet and packet[UDP].dport == 53 and not packet[DNS].qr:
                dns = packet[DNS]
                if not dns.qd:
                    return
                query = dns.qd[0]
                domain = query.qname.decode('ascii', errors='ignore').rstrip('.')
                if not allowed_dns(domain):
                    return
                answer = DNS(id=dns.id, qr=1, aa=1, rd=dns.rd, ra=1, qd=dns.qd)
                if query.qtype == 1:
                    answer.an = DNSRR(rrname=query.qname, type='A', ttl=30, rdata=self.host)
                    answer.ancount = 1
                response = (self._layer2(packet, mac) / IP(src=packet[IP].dst, dst=packet[IP].src) /
                    UDP(sport=53, dport=packet[UDP].sport) / answer)
                sendp(response, iface=self.interface, verbose=False)
                self.stats['dns'] += 1
                self.logger('DNS: ' + domain + ' → ' + self.host)
            elif packet[UDP].dport == 123 and Raw in packet:
                payload = ntp_reply(bytes(packet[UDP].payload))
                if payload:
                    response = (self._layer2(packet, mac) / IP(src=packet[IP].dst, dst=packet[IP].src) /
                        UDP(sport=123, dport=packet[UDP].sport) / Raw(payload))
                    sendp(response, iface=self.interface, verbose=False)
                    self.stats['ntp'] += 1
        except Exception as error:
            self.logger('Paket işleme hatası: ' + type(error).__name__)

    def stop(self):
        self.stop_event.set()
        if self.sniffer:
            try:
                self.sniffer.stop()
            except Exception:
                pass
        for sock in self.sinks:
            sock.close()
        self.sinks.clear()
