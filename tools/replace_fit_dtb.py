"""Replace inline DTB in a caller-provided FIT. Offline, never flashes."""
import argparse, hashlib, json, struct, zlib
from pathlib import Path
from inspect_fit import fdt, inspect
from fdt_codec import encode
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('template',type=Path);p.add_argument('dtb',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.resolve() in (a.template.resolve(),a.dtb.resolve()): raise ValueError('Output must be new')
    blob=a.template.read_bytes();tree=fdt(blob)
    if any('/signature' in name for name in tree): raise ValueError('Signed FIT not supported')
    before=inspect(a.template)
    if not before['images'] or any(not h['valid'] for v in before['images'].values() for h in v['hashes']):
        raise ValueError('Template hash verification failed')
    node='/images/fdt-1'
    if node not in tree or 'data' not in tree[node]: raise ValueError('Requires inline fdt-1 data')
    payload=a.dtb.read_bytes();fdt(payload)
    original_kernel={n:dict(v) for n,v in tree.items() if n.startswith('/images/kernel-')}
    tree[node]['data']=payload
    hashes=0
    for n,v in tree.items():
        if n.startswith(node+'/hash'):
            alg=v['algo'].rstrip(b'\0').decode()
            if alg not in ('crc32','sha1','sha256'): raise ValueError('Unsupported hash')
            v['value']=struct.pack('>I',zlib.crc32(payload)&0xffffffff) if alg=='crc32' else hashlib.new(alg,payload).digest()
            hashes+=1
    if not hashes: raise ValueError('DTB has no hash nodes')
    out=encode(tree,blob);decoded=fdt(out)
    assert all(decoded[n]==v for n,v in original_kernel.items())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(out)
    result=inspect(a.output)
    assert all(h['valid'] for v in result['images'].values() for h in v['hashes'])
    print(json.dumps({'bytes':len(out),'crc32':zlib.crc32(out)&0xffffffff,'sha256':hashlib.sha256(out).hexdigest(),'kernel_unchanged':True,'device_writes':False},indent=2))
if __name__=='__main__':main()
