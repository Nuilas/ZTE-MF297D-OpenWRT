"""Package extracted own-unit Wi-Fi firmware offline; keep output private."""
import argparse, hashlib, json, tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path);p.add_argument('output',type=Path)
def main():
    a=p.parse_args(); manifest={}
    if a.output.exists(): raise ValueError('Output exists')
    with tarfile.open(a.output,'w:gz') as t:
        for f in sorted(a.source.rglob('*')):
            if not f.is_file() or f.is_symlink(): continue
            rel=f.relative_to(a.source)
            if f.name.startswith(('q6_fw.','m3_fw.')):
                chip='QCN6122' if rel.parts[0]=='qcn6122' else 'IPQ5018'
                name=f'ath11k/{chip}/hw1.0/{f.name}'
            elif rel.as_posix()=='bdwlan.b24': name='ath11k/IPQ5018/hw1.0/board.bin'
            elif rel.as_posix()=='qcn6122/bdwlan.b60': name='ath11k/QCN6122/hw1.0/board.bin'
            else: continue
            if name in manifest: raise ValueError('Duplicate firmware destination')
            t.add(f,arcname=name);manifest[name]=hashlib.sha256(f.read_bytes()).hexdigest()
    if len(manifest)!=33: raise ValueError('Expected 33 matching stock firmware files; output is incomplete')
    a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(manifest,indent=2))
    print('Packaged 33 own-unit firmware files; do not commit output.')
if __name__=='__main__':main()
