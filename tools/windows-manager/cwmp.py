"""Single-device CWMP server for MF297D provisioning and config export."""
import hashlib
import ipaddress
import secrets
import ssl
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
XSD = 'http://www.w3.org/2001/XMLSchema'
ENC = 'http://schemas.xmlsoap.org/soap/encoding/'

def local(tag):
    return tag.split('}')[-1]

def text(node, name, default=''):
    if node is None:
        return default
    return next((item.text or '' for item in node.iter() if local(item.tag) == name), default)

@dataclass
class Rpc:
    method: str
    arguments: object
    ident: str = field(default_factory=lambda: 'mf-' + secrets.token_hex(8))
    event: threading.Event = field(default_factory=threading.Event)
    result: object = None
    error: str = ''
    sent: bool = False

class CwmpEngine:
    ALLOWED_METHODS = {'GetParameterValues', 'SetParameterValues', 'GetRPCMethods', 'Upload'}

    def __init__(self, peer='192.168.50.2', logger=lambda _: None):
        self.peer, self.logger = peer, logger
        self.condition = threading.Condition(threading.RLock())
        self.queue = deque()
        self.inflight = None
        self.namespace = 'urn:dslforum-org:cwmp-1-0'
        self.device = None
        self.informed = threading.Event()
        self.uploads = {}
        self.closed = False

    def submit(self, method, arguments=None):
        if method not in self.ALLOWED_METHODS:
            raise ValueError('This application does not implement that RPC')
        rpc = Rpc(method, arguments)
        with self.condition:
            if self.closed:
                raise RuntimeError('ACS is stopped')
            self.queue.append(rpc)
            self.condition.notify_all()
        self.logger(method + ' kuyruğa alındı')
        return rpc

    def call(self, method, arguments=None, timeout=100):
        rpc = self.submit(method, arguments)
        if not rpc.event.wait(timeout):
            with self.condition:
                if rpc in self.queue:
                    self.queue.remove(rpc)
                    rpc.error = 'Modem oturumu beklenirken süre doldu; gönderilmedi'
                else:
                    rpc.error = 'Modemden RPC cevabı alınamadı; sonuç belirsiz'
                    if self.inflight is rpc:
                        self.inflight = None
                rpc.event.set()
                self.condition.notify_all()
            raise TimeoutError(rpc.error)
        if rpc.error:
            raise RuntimeError(rpc.error)
        return rpc.result

    def close(self):
        with self.condition:
            self.closed = True
            for rpc in list(self.queue) + ([self.inflight] if self.inflight else []):
                rpc.error = 'ACS durduruldu'
                rpc.event.set()
            self.queue.clear()
            self.inflight = None
            self.condition.notify_all()

    def envelope(self, method, ident):
        ET.register_namespace('soap', SOAP)
        ET.register_namespace('cwmp', self.namespace)
        ET.register_namespace('xsi', XSI)
        root = ET.Element(f'{{{SOAP}}}Envelope', {'xmlns:xsd': XSD})
        header = ET.SubElement(root, f'{{{SOAP}}}Header')
        ET.SubElement(header, f'{{{self.namespace}}}ID', {f'{{{SOAP}}}mustUnderstand': '1'}).text = ident
        body = ET.SubElement(root, f'{{{SOAP}}}Body')
        method_node = ET.SubElement(body, f'{{{self.namespace}}}{method}')
        return root, method_node

    def response(self, method, ident):
        root, node = self.envelope(method + 'Response', ident)
        if method == 'Inform':
            ET.SubElement(node, 'MaxEnvelopes').text = '1'
        elif method == 'GetRPCMethods':
            methods = ['Inform', 'TransferComplete', 'GetRPCMethods']
            arr = ET.SubElement(node, 'MethodList', {f'{{{ENC}}}arrayType': 'xsd:string[3]'})
            for name in methods:
                ET.SubElement(arr, 'string').text = name
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)

    def request_xml(self, rpc):
        root, node = self.envelope(rpc.method, rpc.ident)
        if rpc.method == 'GetParameterValues':
            args = list(rpc.arguments)
            arr = ET.SubElement(node, 'ParameterNames', {f'{{{ENC}}}arrayType': f'xsd:string[{len(args)}]'})
            for name in args:
                ET.SubElement(arr, 'string').text = name
        elif rpc.method == 'SetParameterValues':
            args = rpc.arguments
            arr = ET.SubElement(node, 'ParameterList', {f'{{{ENC}}}arrayType': f'cwmp:ParameterValueStruct[{len(args)}]'})
            for name, (value, kind) in args.items():
                item = ET.SubElement(arr, 'ParameterValueStruct')
                ET.SubElement(item, 'Name').text = name
                ET.SubElement(item, 'Value', {f'{{{XSI}}}type': kind}).text = str(value)
            ET.SubElement(node, 'ParameterKey').text = 'mf297d-manager'
        elif rpc.method == 'Upload':
            for name, value in [('CommandKey', 'mf297d-config'), ('FileType', '1 Vendor Configuration File'),
                    ('URL', rpc.arguments), ('Username', ''), ('Password', ''), ('DelaySeconds', '0')]:
                ET.SubElement(node, name).text = value
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)

    def next_request(self, wait=0.25):
        with self.condition:
            if not self.queue and not self.inflight and not self.closed:
                self.condition.wait(wait)
            if self.closed or self.inflight or not self.queue:
                return b''
            self.inflight = self.queue.popleft()
            self.inflight.sent = True
            return self.request_xml(self.inflight)

    def handle(self, data):
        if not data.strip():
            return self.next_request()
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('DTD/entity definitions are rejected')
        root = ET.fromstring(data)
        body = root.find(f'{{{SOAP}}}Body')
        if body is None or not len(body):
            raise ValueError('Missing SOAP body')
        node = body[0]
        method = local(node.tag)
        ident = text(root.find(f'{{{SOAP}}}Header'), 'ID')
        if method == 'Inform':
            manufacturer, model, serial = text(node, 'Manufacturer'), text(node, 'ProductClass'), text(node, 'SerialNumber')
            if manufacturer.upper() != 'ZTE' or model != 'MF297D' or not serial:
                raise PermissionError('Only an identified ZTE MF297D is accepted')
            with self.condition:
                if self.device and self.device['serial'] != serial:
                    raise PermissionError('Another device is already selected')
                self.namespace = node.tag[1:].split('}')[0]
                firmware = ''
                for item in node.iter():
                    if local(item.tag) == 'ParameterValueStruct' and text(item, 'Name').endswith('.SoftwareVersion'):
                        firmware = text(item, 'Value')
                self.device = dict(manufacturer=manufacturer, model=model, serial=serial,
                    firmware=firmware or (self.device or {}).get('firmware', ''), last_inform=time.time())
                if self.inflight and not self.inflight.event.is_set():
                    self.queue.appendleft(self.inflight)
                    self.inflight = None
                self.informed.set()
            self.logger('MF297D ACS bağlantısı kuruldu')
            return self.response('Inform', ident)
        if method == 'GetRPCMethods':
            return self.response(method, ident)
        if method == 'TransferComplete':
            code = text(node, 'FaultCode', '0')
            if code != '0':
                self.logger('Dosya aktarımı hata kodu: ' + code)
            return self.response(method, ident)
        with self.condition:
            rpc = self.inflight
            if rpc is None or ident != rpc.ident:
                raise ValueError('Unexpected RPC response ID')
            if method == 'Fault':
                rpc.error = 'CWMP ' + text(node, 'FaultCode') + ': ' + text(node, 'FaultString')
            elif method != rpc.method + 'Response':
                raise ValueError('Unexpected RPC response method')
            elif rpc.method == 'GetParameterValues':
                result = {}
                for item in node.iter():
                    if local(item.tag) == 'ParameterValueStruct':
                        result[text(item, 'Name')] = text(item, 'Value')
                rpc.result = result
            elif rpc.method == 'GetRPCMethods':
                arr = next((e for e in node.iter() if local(e.tag) == 'MethodList'), None)
                rpc.result = [] if arr is None else [e.text for e in arr]
            else:
                rpc.result = {'status': text(node, 'Status')}
            self.inflight = None
            rpc.event.set()
            self.condition.notify_all()
        return self.next_request(wait=0.4)

    def upload_ticket(self, output):
        token = secrets.token_urlsafe(24)
        ticket = {'path': Path(output), 'event': threading.Event(), 'error': '',
            'bytes': 0, 'sha256': '', 'expires': time.monotonic() + 600}
        self.uploads[token] = ticket
        return token, ticket

class CwmpHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, TimeoutError):
            pass

    @property
    def engine(self):
        return self.server.engine

    def reply(self, status, data=b'', kind='text/xml; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if data:
            self.wfile.write(data)

    def body(self, maximum):
        self.connection.settimeout(15)
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            chunks, total = [], 0
            while True:
                line = self.rfile.readline(128)
                size = int(line.split(b';', 1)[0].strip(), 16)
                if size == 0:
                    while self.rfile.readline(8192).strip():
                        pass
                    break
                total += size
                if total > maximum:
                    raise ValueError('Request too large')
                block = self.rfile.read(size)
                if len(block) != size or self.rfile.read(2) != b'\r\n':
                    raise ValueError('Incomplete chunk')
                chunks.append(block)
            return b''.join(chunks)
        count = int(self.headers.get('Content-Length', '0'))
        if not 0 <= count <= maximum:
            raise ValueError('Request too large')
        data = self.rfile.read(count)
        if len(data) != count:
            raise ValueError('Incomplete body')
        return data

    def do_POST(self):
        if self.client_address[0] != self.engine.peer:
            return self.reply(403)
        try:
            output = self.engine.handle(self.body(2*1024*1024))
            self.reply(200 if output else 204, output)
        except PermissionError:
            self.reply(403)
        except (ValueError, ET.ParseError) as error:
            self.engine.logger('CWMP isteği reddedildi: ' + str(error))
            self.close_connection = True
            self.reply(400)

    def do_PUT(self):
        token = self.path.removeprefix('/upload/') if self.path.startswith('/upload/') else ''
        ticket = self.engine.uploads.get(token)
        if self.client_address[0] != self.engine.peer or not ticket or time.monotonic() > ticket['expires']:
            return self.reply(403)
        try:
            data = self.body(64*1024*1024)
            if not data:
                raise ValueError('Empty configuration upload')
            if ticket['bytes']:
                if hashlib.sha256(data).hexdigest()!=ticket['sha256']:
                    raise ValueError('Upload token already used for a different file')
                self.reply(201)
                return
            ticket['path'].parent.mkdir(parents=True, exist_ok=True)
            with ticket['path'].open('xb') as file:
                file.write(data)
            ticket['bytes'], ticket['sha256'] = len(data), hashlib.sha256(data).hexdigest()
            self.reply(201)
            self.engine.logger(f'Config yedeği alındı: {len(data)} bayt')
        except Exception as error:
            ticket['error'] = str(error)
            self.close_connection = True
            self.reply(400)
        finally:
            ticket['event'].set()

    def do_GET(self):
        self.reply(404)

def make_certificate(directory, host, domain='acs.superonline.net'):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    certificate, private = directory / 'local-acs.pem', directory / 'local-acs-key.pem'
    if not certificate.exists() or not private.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain), x509.IPAddress(ipaddress.ip_address(host))]), False)
            .sign(key, hashes.SHA256()))
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return certificate, private

class CwmpServers:
    def __init__(self, engine, host, directory, http_port=80, https_port=443):
        self.engine, self.host, self.directory = engine, host, directory
        self.http_port, self.https_port = http_port, https_port
        self.servers = []

    def start(self):
        try:
            for port, secure in [(self.http_port, False), (self.https_port, True)]:
                if port is None:
                    continue
                server = ThreadingHTTPServer((self.host, port), CwmpHandler)
                server.daemon_threads = True
                server.engine = self.engine
                if secure:
                    cert, key = make_certificate(self.directory, self.host)
                    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                    context.load_cert_chain(cert, key)
                    server.socket = context.wrap_socket(server.socket, server_side=True)
                self.servers.append(server)
                threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception:
            self.stop()
            raise

    def stop(self):
        self.engine.close()
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.servers.clear()
