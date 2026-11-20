"""Small Telnet client; no implicit commands or credential logging."""
import re
import secrets
import socket
import time

class TelnetClient:
    def __init__(self, host, port=2323, timeout=8):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None
        self.pending = b''

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _decode(self, data):
        data = self.pending + data
        self.pending = b''
        output = bytearray()
        i = 0
        while i < len(data):
            if data[i] != 255:
                output.append(data[i]); i += 1; continue
            if i + 1 >= len(data):
                self.pending = data[i:]; break
            command = data[i+1]
            if command == 255:
                output.append(255); i += 2
            elif command in (251, 252, 253, 254):
                if i + 2 >= len(data):
                    self.pending = data[i:]; break
                option = data[i+2]
                if command == 251:
                    self.sock.sendall(bytes([255, 253 if option in (1, 3) else 254, option]))
                elif command == 253:
                    self.sock.sendall(bytes([255, 252, option]))
                i += 3
            elif command == 250:
                end = data.find(b'\xff\xf0', i+2)
                if end < 0:
                    self.pending = data[i:]; break
                i = end+2
            else:
                i += 2
        return bytes(output)

    def read_until(self, expression, timeout=None, max_bytes=4*1024*1024):
        pattern = re.compile(expression, re.I | re.M)
        end = time.monotonic() + (self.timeout if timeout is None else timeout)
        data = bytearray()
        while time.monotonic() < end:
            try:
                chunk = self.sock.recv(8192)
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionError('Telnet connection closed')
            data.extend(self._decode(chunk))
            if len(data) > max_bytes:
                raise ValueError('Telnet response exceeded size limit')
            if pattern.search(data):
                return bytes(data)
        raise TimeoutError('Telnet response timed out')

    def login(self, username, password):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(1)
        try:
            self.read_until(rb'(?:login|username|user name)\s*:')
            self.sock.sendall(username.encode() + b'\r\n')
            self.read_until(rb'password\s*:')
            self.sock.sendall(password.encode() + b'\r\n')
            reply = self.read_until(rb'(?:incorrect|failed|denied|[#>$]\s*$)')
            if re.search(rb'incorrect|failed|denied', reply, re.I):
                raise PermissionError('Telnet credentials were rejected')
            result, code = self.command('id')
            if code != 0 or not re.search(r'\buid=0\(root\)', result):
                raise PermissionError('Root uid=0 was not confirmed')
            return result
        except Exception:
            self.close()
            raise

    def command(self, command, timeout=None, max_bytes=4*1024*1024):
        if not self.sock:
            raise ConnectionError('Telnet is not connected')
        if '\n' in command or '\r' in command:
            raise ValueError('Only one-line shell commands are accepted')
        marker = '__MF_DONE_' + secrets.token_hex(8) + '__'
        wire = command + "; printf '\\n" + marker + ":%s\\n' \"$?\""
        self.sock.sendall(wire.encode() + b'\r\n')
        reply = self.read_until(rb'^' + marker.encode() + rb':(-?\d+)\r?$', timeout, max_bytes)
        text = reply.decode(errors='replace')
        match = re.search(r'^' + marker + r':(-?\d+)\r?$', text, re.M)
        return text[:match.start()], int(match.group(1))
