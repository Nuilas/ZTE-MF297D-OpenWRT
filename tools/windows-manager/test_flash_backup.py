import hashlib
import socket
import struct
import tempfile
import unittest
from pathlib import Path

from flash_backup import TftpReceiver

class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=self.root, prefix='tftp-test-')
        self.receiver = TftpReceiver('127.0.0.1', '127.0.0.1', self.temp.name, port=0)
        self.receiver.start()

    def tearDown(self):
        self.receiver.stop()
        assert Path(self.temp.name).resolve().is_relative_to(self.root)
        self.temp.cleanup()

    def transfer(self, payload, expected_size=None, duplicate=False):
        name = self.receiver.register(0, len(payload) if expected_size is None else expected_size)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            sock.sendto(b'\x00\x02' + name.encode() + b'\0octet\0', ('127.0.0.1', self.receiver.port))
            ack, peer = sock.recvfrom(1024)
            self.assertEqual(ack, b'\x00\x04\x00\x00')
            blocks = len(payload) // 512 + 1
            for index in range(blocks):
                block = (index + 1) & 65535
                packet = struct.pack('!HH', 3, block) + payload[index*512:(index+1)*512]
                sock.sendto(packet, peer)
                ack, _ = sock.recvfrom(1024)
                if duplicate and index == 0:
                    sock.sendto(packet, peer)
                    ack, _ = sock.recvfrom(1024)
                if ack[:2] == b'\x00\x05':
                    break
                self.assertEqual(ack, struct.pack('!HH', 4, block))
            return self.receiver.wait_result(name, seconds=3)
        finally:
            sock.close()

    def test_exact_multiple_and_duplicate(self):
        payload = b'backup-content--' * 64
        result = self.transfer(payload, duplicate=True)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(Path(result['path']).read_bytes(), payload)

    def test_truncated_partition_is_rejected(self):
        result = self.transfer(b'short', expected_size=100)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse((Path(self.temp.name) / 'mtd00.bin').exists())

    def test_block_counter_wrap(self):
        payload = b'X' * (512 * 65536 + 7)
        result = self.transfer(payload)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['received_bytes'], len(payload))
        self.assertEqual(result['sha256'], hashlib.sha256(payload).hexdigest())

    def test_unregistered_path_is_ignored(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.25)
        try:
            sock.sendto(b'\x00\x02../escape\0octet\0', ('127.0.0.1', self.receiver.port))
            with self.assertRaises(socket.timeout):
                sock.recvfrom(100)
        finally:
            sock.close()
        self.assertFalse((self.root / 'escape').exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
