import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

def fdt(data):
    header = struct.unpack('>10I', data[:40])
    magic, total, struct_at, strings_at, reserve, version, last, boot, strings_size, struct_size = header
    if magic != 0xd00dfeed or total > len(data):
        raise ValueError('Invalid FDT header')
    strings = data[strings_at:strings_at+strings_size]
    tree, stack, position = {}, [], struct_at
    while position < struct_at+struct_size:
        token = struct.unpack_from('>I', data, position)[0]; position += 4
        if token == 1:
            end = data.index(b'\0', position)
            name = data[position:end].decode()
            stack.append(name)
            position = (end+4) & ~3
            tree.setdefault('/' + '/'.join(x for x in stack if x), {})
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, offset = struct.unpack_from('>II', data, position); position += 8
            end = strings.index(b'\0', offset)
            name = strings[offset:end].decode()
            tree['/' + '/'.join(x for x in stack if x)][name] = data[position:position+length]
            position = (position+length+3)&~3
        elif token == 4:
            pass
        elif token == 9:
            return tree
        else:
            raise ValueError('Invalid FDT token')
    raise ValueError('No FDT end token')

def show(data):
    if not data:
        return True
    if data.endswith(b'\0') and all(c in (0,9,10,13) or 32 <= c < 127 for c in data):
        return data.rstrip(b'\0').decode().split('\0')
    if len(data) <= 32 and len(data)%4==0:
        return [hex(x) for x in struct.unpack('>'+'I'*(len(data)//4), data)]
    return {'bytes':len(data), 'hex_prefix':data[:24].hex()}

def inspect(path):
    blob=Path(path).read_bytes()
    tree=fdt(blob)
    result={'file':str(path),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
        'root':{k:show(v) for k,v in tree['/'].items()},'images':{},'configurations':{}}
    for name,props in tree.items():
        if name.startswith('/configurations'):
            result['configurations'][name]={k:show(v) for k,v in props.items()}
        if not name.startswith('/images/') or name.count('/')!=2:
            continue
        info={k:show(v) for k,v in props.items() if k!='data'}
        data=props.get('data',b'')
        info['data_bytes']=len(data)
        info['hashes']=[]
        for sub,subprops in tree.items():
            if sub.startswith(name+'/hash'):
                algo=subprops.get('algo',b'').rstrip(b'\0').decode()
                expected=subprops.get('value',b'')
                actual=struct.pack('>I',zlib.crc32(data)&0xffffffff) if algo=='crc32' else hashlib.new(algo,data).digest()
                info['hashes'].append({'algorithm':algo,'valid':actual==expected})
        if data.startswith(b'\xd0\x0d\xfe\xed'):
            dt=fdt(data)
            info['device_tree']={n:{k:show(v) for k,v in p.items()} for n,p in dt.items()
                if n in ('/','/chosen') or 'memory@' in n or 'partition' in n}
        result['images'][name]=info
    return result

if __name__=='__main__':
    result=inspect(sys.argv[1]);print(json.dumps(result,indent=2))
