"""FDT serializer used by the MF297D development tools. GPL-2.0-only."""
import struct
from inspect_fit import fdt

def encode(tree, original):
    header=struct.unpack('>10I',original[:40])
    reserve=bytearray();at=header[4]
    while True:
        entry=original[at:at+16]
        if len(entry)!=16:raise ValueError('Invalid memory reserve map')
        reserve.extend(entry);at+=16
        if entry==b'\0'*16:break
    children={name:[] for name in tree}
    for name in tree:
        if name=='/':continue
        parent=name.rsplit('/',1)[0] or '/'
        children[parent].append(name)
    strings=bytearray(); offsets={}; structure=bytearray()
    def pad():
        while len(structure)%4:structure.append(0)
    def node(name):
        structure.extend(struct.pack('>I',1))
        structure.extend((name.rsplit('/',1)[-1] if name!='/' else '').encode()+b'\0');pad()
        for key,value in tree[name].items():
            if key not in offsets:
                offsets[key]=len(strings);strings.extend(key.encode()+b'\0')
            structure.extend(struct.pack('>III',3,len(value),offsets[key]));structure.extend(value);pad()
        for child in children[name]:node(child)
        structure.extend(struct.pack('>I',2))
    node('/');structure.extend(struct.pack('>I',9))
    reserve_at=40;struct_at=reserve_at+len(reserve);strings_at=struct_at+len(structure)
    total=strings_at+len(strings)
    result=struct.pack('>10I',0xd00dfeed,total,struct_at,strings_at,reserve_at,
        header[5],header[6],header[7],len(strings),len(structure))+reserve+structure+strings
    if fdt(result)!=tree:raise ValueError('DTB encoder roundtrip mismatch')
    return bytes(result)
