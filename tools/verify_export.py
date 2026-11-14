"""Verify published source hashes and reject private/generated export mistakes."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    lock = json.loads((ROOT / 'config/source-lock.json').read_text())
    for name, expected in lock['exported_kernel_sources'].items():
        actual = hashlib.sha256((ROOT / 'src/kernel' / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Source hash mismatch: ' + name)
    forbidden = {'.bin', '.itb', '.dtb', '.ko', '.o', '.exe', '.cpio', '.squashfs', '.ubifs', '.ubi', '.zip'}
    count = 0
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in ('.git', '__pycache__', 'build', 'dist') for x in p.relative_to(ROOT).parts):
            continue
        name = p.relative_to(ROOT).as_posix()
        if p.suffix in forbidden or p.name.endswith('_payload.h') or p.name in ('credentials.json', '.env'):
            raise ValueError('Generated/private artifact: ' + name)
        data = p.read_bytes()
        if p.suffix in ('.png', '.ico'):
            continue
        text = data.decode('utf-8')
        if '\r' in text:
            raise ValueError('CRLF in source: ' + name)
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}', text):
            raise ValueError('Credential pattern: ' + name)
        if re.search(r'(?:C:[/\\]Users[/\\]|[/]mnt/c/Users/|[/]home/build/)', text, re.I):
            raise ValueError('Private local path: ' + name)
        count += 1
    print(json.dumps({'passed': True, 'text_files_checked': count, 'kernel_sources_checked': len(lock['exported_kernel_sources']), 'device_writes': False}))

if __name__ == '__main__':
    main()
