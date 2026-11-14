"""Offline regression checks: public DT layout, FIT replacement and caldata."""
import functools
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fdt_codec import encode
from inspect_fit import fdt, inspect

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

class OfflineChecks(unittest.TestCase):
    def test_device_tree_variants_and_write_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            for variant, writable in [('native', [21]), ('recovery', []), ('maintenance', [21]), ('maintenance-env', [10, 21])]:
                out = Path(tmp) / (variant + '.dtb')
                subprocess.run([PYTHON, str(ROOT/'tools/build_dtb.py'), '--variant', variant,
                    '--lan-mac', '02:11:22:33:44:50', '--wan-mac', '02:11:22:33:44:51', '--out', str(out)],
                    check=True, capture_output=True)
                blob = out.read_bytes()
                tree = fdt(blob)
                self.assertEqual(fdt(encode(tree, blob)), tree)
                parts = [v for n, v in tree.items() if '/partitions/partition@' in n and 'reg' in v and 'label' in v]
                self.assertEqual(len(parts), 22)
                self.assertEqual([i for i, v in enumerate(parts) if 'read-only' not in v], writable)
                self.assertEqual(struct.unpack('>II', parts[-1]['reg']), (0x2cc0000, 0xd340000))
                macs = [v['local-mac-address'] for v in tree.values() if 'local-mac-address' in v]
                self.assertEqual(set(macs), {bytes.fromhex('021122334450'), bytes.fromhex('021122334451')})

    def test_fit_replacement_preserves_kernel_and_refreshes_hash(self):
        # Minimal inline FIT, no external templates or device identifiers needed.
        header = struct.pack('>10I', 0xd00dfeed, 56, 56, 56, 40, 17, 16, 0, 0, 0) + b'\0'*16
        kernel = b'unchanged-kernel'
        tree = {'/': {}, '/images': {}, '/images/kernel-1': {'data': kernel},
            '/images/kernel-1/hash-1': {'algo': b'sha256\0', 'value': hashlib.sha256(kernel).digest()},
            '/images/fdt-1': {'data': b'old'},
            '/images/fdt-1/hash-1': {'algo': b'sha256\0', 'value': hashlib.sha256(b'old').digest()}}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            template = tmp/'in.itb'; dtb = tmp/'new.dtb'; output = tmp/'out.itb'
            template.write_bytes(encode(tree, header))
            dtb.write_bytes(encode({'/': {'model': b'test\0'}}, header))
            result = subprocess.run([PYTHON, str(ROOT/'tools/replace_fit_dtb.py'), str(template), str(dtb), str(output)], check=True, capture_output=True)
            self.assertTrue(json.loads(result.stdout)['kernel_unchanged'])
            self.assertEqual(fdt(output.read_bytes())['/images/kernel-1']['data'], kernel)
            self.assertEqual(fdt(output.read_bytes())['/images/fdt-1']['data'], dtb.read_bytes())
            self.assertTrue(all(h['valid'] for v in inspect(output)['images'].values() for h in v['hashes']))
            bad = bytearray(template.read_bytes()); bad[bad.index(kernel)] ^= 1
            template.write_bytes(bad)
            result = subprocess.run([PYTHON, str(ROOT/'tools/replace_fit_dtb.py'), str(template), str(dtb), str(tmp/'bad.itb')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((tmp/'bad.itb').exists())

    def test_calibration_checksum_and_invalid_input_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            art = bytearray(0x50000)
            for offset in (0x1000, 0x26800):
                struct.pack_into('<H', art, offset + 10, 0xffff)
            (tmp/'art').write_bytes(art)
            (tmp/'mac').write_bytes(bytes.fromhex('021122334450'))
            command = [PYTHON, str(ROOT/'tools/prepare_caldata.py'), '--art', str(tmp/'art'), '--mac-partition', str(tmp/'mac')]
            subprocess.run(command + ['--out', str(tmp/'cal')], check=True, capture_output=True)
            for name, expected in [('cal-ahb-c000000.wifi.bin', '021122334452'), ('cal-ahb-b00a040.wifi.bin', '021122334453')]:
                data = (tmp/'cal'/name).read_bytes()
                self.assertEqual(data[14:20], bytes.fromhex(expected))
                self.assertEqual(functools.reduce(int.__xor__, struct.unpack('<65536H', data)), 0xffff)
            art[0x1000] ^= 1
            (tmp/'art').write_bytes(art)
            result = subprocess.run(command + ['--out', str(tmp/'bad')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((tmp/'bad').exists())

if __name__ == '__main__':
    unittest.main()
