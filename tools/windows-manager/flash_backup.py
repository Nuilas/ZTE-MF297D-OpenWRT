"""Read-only MTD backup via authenticated root Telnet and TFTP PUT.

Only /dev/mtdNro inputs are read. No flash writer, erase, restore or reboot
operation exists in this module. NAND OOB is not included.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from telnet_client import TelnetClient

class TftpReceiver:
    def __init__(self, host, peer, directory, port=1069):
        self.host, self.peer, self.directory, self.port = host, peer, Path(directory), port
        self.token = secrets.token_hex(12)
        self.expected = {}
        self.active = {}
        self.results = {}
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.sock = None

    def register(self, index, expected_size):
        name = f'{self.token}_mtd{int(index)}.bin'
        with self.lock:
            self.expected[name] = (int(index), int(expected_size))
        return name

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.port = self.sock.getsockname()[1]
        self.sock.settimeout(0.5)
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.sock:
            self.sock.close()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2)

    def _listen(self):
        while not self.stop_event.is_set():
            try:
                data, peer = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if peer[0] != self.peer or data[:2] != b'\x00\x02':
                continue
            fields = data[2:].split(b'\0')
            if len(fields) < 3 or fields[1].lower() != b'octet':
                continue
            try:
                name = fields[0].decode('ascii')
            except UnicodeDecodeError:
                continue
            with self.lock:
                if name not in self.expected or name in self.results:
                    continue
                if peer in self.active:
                    transfer = self.active[peer]
                    try:
                        transfer['socket'].sendto(transfer['ack'], peer)
                    except OSError:
                        pass
                    continue
                transfer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                transfer.bind((self.host, 0))
                transfer.settimeout(2)
                self.active[peer] = {'socket': transfer, 'ack': b'\x00\x04\x00\x00'}
            threading.Thread(target=self._receive, args=(transfer, peer, name), daemon=True).start()

    def _receive(self, sock, peer, name):
        index, expected_size = self.expected[name]
        final = self.directory / f'mtd{index:02d}.bin'
        partial = final.with_suffix('.bin.partial')
        result = {'index': index, 'expected_bytes': expected_size, 'received_bytes': 0,
            'status': 'receiving', 'sha256': None, 'path': str(final)}
        digest = hashlib.sha256()
        last = 0
        timeout_count = 0
        try:
            if final.exists():
                raise FileExistsError('Existing backup will not be overwritten')
            with partial.open('xb') as output:
                sock.sendto(b'\x00\x04\x00\x00', peer)
                while not self.stop_event.is_set():
                    try:
                        data, source = sock.recvfrom(516)
                    except socket.timeout:
                        timeout_count += 1
                        if timeout_count > 15:
                            raise TimeoutError('TFTP transfer timed out')
                        sock.sendto(struct.pack('!HH', 4, last), peer)
                        continue
                    if source != peer or len(data) < 4:
                        continue
                    opcode, block = struct.unpack('!HH', data[:4])
                    if opcode == 5:
                        raise IOError('Device TFTP error: ' + data[4:].rstrip(b'\0').decode(errors='replace'))
                    if opcode != 3:
                        continue
                    expected_block = (last + 1) & 0xFFFF
                    if block == last:
                        sock.sendto(struct.pack('!HH', 4, last), peer)
                        continue
                    if block != expected_block:
                        continue
                    payload = data[4:]
                    if result['received_bytes'] + len(payload) > expected_size:
                        raise IOError('Device sent more bytes than the partition size')
                    output.write(payload)
                    digest.update(payload)
                    result['received_bytes'] += len(payload)
                    last = block
                    ack = struct.pack('!HH', 4, block)
                    with self.lock:
                        self.active[peer]['ack'] = ack
                    timeout_count = 0
                    if len(payload) < 512:
                        if result['received_bytes'] != expected_size:
                            raise IOError('Truncated partition transfer')
                        output.flush()
                        sock.sendto(ack, peer)
                        break
                    sock.sendto(ack, peer)
                else:
                    raise InterruptedError('Transfer stopped')
            partial.rename(final)
            result.update(status='complete', sha256=digest.hexdigest())
            with self.lock:
                self.results[name] = result.copy()
            # Re-ack a lost final ACK without accepting another file.
            end = time.monotonic() + 3
            while time.monotonic() < end:
                try:
                    data, source = sock.recvfrom(516)
                    if source == peer and data[:4] == struct.pack('!HH', 3, last):
                        sock.sendto(struct.pack('!HH', 4, last), peer)
                except socket.timeout:
                    break
        except Exception as error:
            result.update(status='failed', error=str(error))
            try:
                sock.sendto(b'\x00\x05\x00\x00' + str(error).encode()[:160] + b'\0', peer)
            except OSError:
                pass
        finally:
            with self.lock:
                self.results[name] = result.copy()
                self.active.pop(peer, None)
            sock.close()

    def wait_result(self, name, seconds=10):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            with self.lock:
                result = self.results.get(name)
                if result:
                    return result.copy()
            time.sleep(0.1)
        raise TimeoutError('TFTP receiver did not finish')

def discover_partitions(client):
    text, code = client.command('cat /proc/mtd')
    if code:
        raise RuntimeError('/proc/mtd could not be read')
    partitions = []
    for match in re.finditer(r'^mtd(\d+):\s+([0-9a-f]+)\s+([0-9a-f]+)\s+"([^"]+)"', text, re.M):
        index, size, erase, name = match.groups()
        index = int(index)
        cmd = f"for f in type offset writesize oobsize bad_blocks ecc_failures corrected_bits; do printf 'MF_META|%s|' $f; cat /sys/class/mtd/mtd{index}/$f 2>/dev/null; echo; done"
        details, _ = client.command(cmd)
        metadata = {}
        for line in details.replace('\r', '').splitlines():
            if line.startswith('MF_META|'):
                _, field, value = line.split('|', 2)
                metadata[field] = value
        partitions.append(dict(index=index, name=name, size=int(size, 16),
            erasesize=int(erase, 16), source=f'/dev/mtd{index}ro', **metadata))
    if not partitions:
        raise RuntimeError('No MTD partitions found')
    return partitions, text

def run_backup(host, local_ip, username, password, directory, progress=print):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest_path = directory / 'manifest.json'
    manifest = {'format': 'MTD data-area backup; NAND OOB excluded',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'host': host,
        'read_only_device_access': True, 'live_backup': True,
        'warning': 'Not a programmer-ready raw NAND image. OOB is excluded. Live writable partitions may change during capture.',
        'partitions': [], 'transfers': [], 'complete': False}
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    client = TelnetClient(host, timeout=12)
    receiver = TftpReceiver(local_ip, host, directory)
    try:
        client.login(username, password)
        partitions, table = discover_partitions(client)
        manifest['partitions'] = partitions
        (directory / 'proc-mtd.txt').write_text(table, encoding='utf-8')
        for source, filename in [('cat /proc/mounts', 'proc-mounts.txt'),
                ('uname -a', 'uname.txt'), ('nv show', 'current-nvram.txt')]:
            text, _ = client.command(source)
            (directory / filename).write_text(text, encoding='utf-8')
        save()
        receiver.start()
        total = sum(p['size'] for p in partitions)
        progress(f'BACKUP: {len(partitions)} partitions; {total} bytes including logical UBI volumes')
        for partition in partitions:
            index = partition['index']
            name = receiver.register(index, partition['size'])
            command = f'busybox tftp -p -l /dev/mtd{index}ro -r {name} {local_ip} {receiver.port}'
            progress(f"READ: mtd{index} {partition['name']} {partition['size']} bytes")
            output, code = client.command(command, timeout=900, max_bytes=65536)
            try:
                result = receiver.wait_result(name, seconds=35)
            except TimeoutError as error:
                result = dict(index=index, status='failed', error=str(error))
            result['device_exit_code'] = code
            if code:
                result['device_output'] = output
                result['status'] = 'failed'
            manifest['transfers'].append(result)
            save()
            progress(f"RESULT: mtd{index} {result['status']} {result.get('received_bytes', 0)} bytes")
        manifest['complete'] = all(r['status'] == 'complete' for r in manifest['transfers'])
        manifest['physical_nand_bytes'] = sum(p['size'] for p in partitions if p.get('type') == 'nand')
        save()
        progress('BACKUP COMPLETE: ' + str(manifest['complete']))
        return manifest
    finally:
        receiver.stop()
        client.close()
        save()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.1.1')
    parser.add_argument('--local-ip', default='192.168.1.2')
    parser.add_argument('--user', default='sUser')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    password = os.environ.pop('MF297D_BACKUP_PASSWORD')
    run_backup(args.host, args.local_ip, args.user, password, args.output,
        progress=lambda text: print(text, flush=True))

if __name__ == '__main__':
    main()
