"""Emulate the ACTUAL compiled ARM32 relocation stub with the supplied image.
Stops immediately before SMC; verifies destination bytes, chain traversal,
physical stack and Qualcomm ARM64 handoff arguments. No device access.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib
import re
HERE=Path(sys.argv[1]).resolve()
MANIFEST=json.loads((HERE/'MANIFEST.json').read_text())
TRACE_COUNT=MANIFEST['trace_count']
ENTRY=MANIFEST['image_entry_offset']
CALLS=MANIFEST['kernel_calls']
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
sys.path.insert(0,str(HERE.parents[1]/'ramboot-investigation/build-tools'))
sys.path.insert(0,str(HERE.parents[1]))
sys.path.insert(0,str(HERE/'build-tools'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP

def stub_from_elf(path):
    b=path.read_bytes();off=struct.unpack_from('<I',b,32)[0]
    es,n,si=struct.unpack_from('<HHH',b,46)
    sections=[struct.unpack_from('<10I',b,off+i*es) for i in range(n)]
    names=b[sections[si][4]:sections[si][4]+sections[si][5]]
    named={names[s[0]:].split(b'\0')[0].decode():s for s in sections}
    section=named['.text.mf_stub']
    # This code must be entirely position-independent, without loader relocations.
    assert '.rel.text.mf_stub' not in named
    code=b[section[4]:section[4]+section[5]]
    smcs=[i.address for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,0) if i.mnemonic=='smc']
    assert len(smcs)==2 and len(code)<=304
    return code,smcs[0]

def main():
    code,smc=stub_from_elf(HERE/'mf297d_ramboot_prepare.ko')
    image=(HERE/'Image').read_bytes()
    dtb=(HERE/'mf297d.dtb').read_bytes()
    initrd=(HERE/'initramfs.cpio').read_bytes()
    initrd_padded=initrd+b'\0'*((-len(initrd))%4096)
    memory_size=struct.unpack_from('<Q',image,16)[0]
    image_dest=int(re.search(r'RAMBOOT_IMAGE_DEST (0x[0-9a-f]+)U',(Path(__file__).resolve().parents[1]/'loader/ramboot_config.h').read_text())[1],16)
    assert struct.unpack_from('<Q',image,24)[0]&8
    assert image_dest%0x200000==0 and image_dest+memory_size<=0x4a400000
    control=0x50000000;source=0x51000000
    original=image
    patched=bytearray(image)
    struct.pack_into('<II',patched,0,0x58000110,0xd61f0200)
    struct.pack_into('<Q',patched,32,control+512)
    image=bytes(patched)
    image_padded=image+b'\0'*(memory_size-len(image))
    dtb=bytearray(dtb)
    trace_reg=dtb.index(struct.pack('>4I',0,0xfeed0000,0,4096))
    for i in range(TRACE_COUNT):struct.pack_into('>4I',dtb,trace_reg+i*16,0,control+i*4096,0,4096)
    dtb=bytes(dtb)
    sys.path.insert(0,str(HERE.parent))
    from inspect_fit import fdt
    assert fdt(dtb)['/reserved-memory/ramboot-trace']['reg']==b''.join(struct.pack('>4I',0,control+i*4096,0,4096) for i in range(TRACE_COUNT))
    dtb_padded=dtb+b'\0'*((-len(dtb))%4096)
    data=image_padded+dtb_padded+initrd_padded
    records=len(data)//4096;descriptor_pages=(records+337)//338
    emulator=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    emulator.mem_map(0x07a00000,4096)
    emulator.mem_map(control,(1+descriptor_pages)*4096)
    emulator.mem_map(source,len(data));emulator.mem_write(source,data)
    emulator.mem_map(image_dest,len(image_padded))
    emulator.mem_map(0x44000000,len(dtb_padded))
    emulator.mem_map(0x45000000,len(initrd_padded))
    emulator.mem_write(control,code)
    payload=(HERE/'ramboot_a64.bin').read_bytes()
    emulator.mem_write(control+512,payload)
    emulator.mem_write(control+400,original[:8]+original[32:40]+struct.pack('<Q',(image_dest+ENTRY)))
    emulator.mem_write(control+424,struct.pack('<QQ',(image_dest+CALLS[0]),(image_dest+CALLS[1])))
    for j in range(16):
        v=j
        for bit in range(4):v=(v>>1)^(0xedb88320 if v&1 else 0)
        emulator.mem_write(control+1536+j*4,struct.pack('<I',v))
    image_crc=zlib.crc32(image)
    emulator.mem_write(control+456,struct.pack('<II',image_crc,len(image)))
    initrd_crc=zlib.crc32(initrd)
    emulator.mem_write(control+464,struct.pack('<II',len(initrd),initrd_crc))
    emulator.mem_write(control+304,struct.pack('<II',control+4096,control+320))
    parameters=[0x44000000]+[0]*8+[image_dest]
    emulator.mem_write(control+320,struct.pack('<10Q',*parameters))
    for d in range(descriptor_pages):
        at=control+(d+1)*4096;count=min(338,records-d*338)
        nxt=at+4096 if d+1<descriptor_pages else 0
        emulator.mem_write(at,struct.pack('<II',nxt,count))
        for slot in range(count):
            index=d*338+slot
            image_pages=len(image_padded)//4096;dtb_pages=len(dtb_padded)//4096
            if index<image_pages:dest=image_dest+index*4096
            elif index<image_pages+dtb_pages:dest=0x44000000+(index-image_pages)*4096
            else:dest=0x45000000+(index-image_pages-dtb_pages)*4096
            emulator.mem_write(at+8+slot*12,struct.pack('<III',source+index*4096,dest,4096))
        emulator.mem_write(at+4064,struct.pack('<8I',0x4d465452,0x20261120,0,0,0,control,zlib.crc32(original),0))
    state={}
    def stop_before_smc(uc,address,size,user):
        state['registers']=[uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
        state['sp']=uc.reg_read(UC_ARM_REG_SP)
        uc.emu_stop()
    emulator.hook_add(UC_HOOK_CODE,stop_before_smc,begin=control+smc,end=control+smc)
    emulator.emu_start(control,control+len(code),count=100000000)
    assert state['registers']==[0x0200010f,0x12,control+320,80],state
    assert state['sp']==control+4096-16
    assert bytes(emulator.mem_read(0x07a00004,4))==struct.pack('<I',1)
    assert bytes(emulator.mem_read(image_dest,len(image_padded)))==image_padded
    assert bytes(emulator.mem_read(0x44000000,len(dtb_padded)))==dtb_padded
    assert bytes(emulator.mem_read(0x45000000,len(initrd_padded)))==initrd_padded
    assert bytes(emulator.mem_read(control+320,80))==struct.pack('<10Q',*parameters)
    for d in range(descriptor_pages):
        trace=struct.unpack('<8I',bytes(emulator.mem_read(control+(d+1)*4096+4064,32)))
        assert trace[:3]==(0x4d465452,0x20261120,3),trace
        assert trace[5:7]==(control,zlib.crc32(original))
        assert trace[7]==1
    # Simulate a service-level denial, including scratch-register clobbering.
    # Continue after SMC without executing it; verify that diagnostics reach
    # every owned trace page before the fallback PSCI call.
    smcs=[i.address for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,0) if i.mnemonic=='smc']
    emulator.reg_write(UC_ARM_REG_R0,0);emulator.reg_write(UC_ARM_REG_R1,0xfffffff3)
    from unicorn.arm_const import UC_ARM_REG_R8
    emulator.reg_write(UC_ARM_REG_R8,0)
    second={}
    def stop_at_reset(uc,address,size,user):
        second['r0']=uc.reg_read(UC_ARM_REG_R0);uc.emu_stop()
    emulator.hook_add(UC_HOOK_CODE,stop_at_reset,begin=control+smcs[1],end=control+smcs[1])
    emulator.emu_start(control+smc+4,control+len(code),count=100000)
    assert second['r0']==0x84000009
    for d in range(descriptor_pages):
        trace=struct.unpack('<8I',bytes(emulator.mem_read(control+(d+1)*4096+4064,32)))
        assert trace[:5]==(0x4d465452,0x20261120,4,0,0xfffffff3),trace
    # Independently execute the real AArch64 shim from its Image trampoline.
    from unicorn import UC_ARCH_ARM64
    from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_PSTATE
    arm64=Uc(UC_ARCH_ARM64,0)
    arm64.mem_map(0x0b017000,4096)
    from unicorn import UC_HOOK_MEM_WRITE
    watchdog_writes=[]
    def watchdog_write(uc,access,address,size,value,user):
        assert address==0x0b017004 and size==4 and value==1
        watchdog_writes.append(address)
    arm64.hook_add(UC_HOOK_MEM_WRITE,watchdog_write,begin=0x0b017000,end=0x0b017fff)
    arm64.mem_map(control,(1+descriptor_pages)*4096)
    arm64.mem_write(control,bytes(emulator.mem_read(control,(1+descriptor_pages)*4096)))
    arm64.mem_map(image_dest,len(image_padded));arm64.mem_write(image_dest,image_padded)
    arm64.mem_map(0x45000000,len(initrd_padded));arm64.mem_write(0x45000000,initrd_padded)
    arm64.reg_write(UC_ARM64_REG_PSTATE,0x3c5)
    arm64.reg_write(UC_ARM64_REG_X0,0x44000000)
    from capstone import CS_ARCH_ARM64
    from unicorn.arm64_const import UC_ARM64_REG_PC
    import unicorn.arm64_const as ar
    probe=[i.address for i in Cs(CS_ARCH_ARM64,0).disasm(payload[:1024],control+512)
        if i.mnemonic=='mrs' and i.op_str.lower()=='x17, s3_1_c15_c2_1']
    assert len(probe)==1
    def coherency_probe(uc,address,size,user):
        uc.reg_write(ar.UC_ARM64_REG_X17,64);uc.reg_write(UC_ARM64_REG_PC,address+4)
    arm64.hook_add(UC_HOOK_CODE,coherency_probe,begin=probe[0],end=probe[0])
    cache_instructions={i.address:i for i in Cs(CS_ARCH_ARM64,0).disasm(payload[1088:1536],control+1600)}
    cache_state={'selector':0,'ops':[],'selectors':[]}
    def cache_registers(uc,address,size,user):
        ins=cache_instructions.get(address)
        if not ins:return
        skip=False
        if ins.mnemonic=='mrs' and ins.op_str=='x0, clidr_el1':
            uc.reg_write(ar.UC_ARM64_REG_X0,0x02000023);skip=True
        elif ins.mnemonic=='msr' and ins.op_str.startswith('csselr_el1,'):
            value=0 if ins.op_str.endswith('xzr') else uc.reg_read(ar.UC_ARM64_REG_X10)
            cache_state['selector']=value;cache_state['selectors'].append(value);skip=True
        elif ins.mnemonic=='mrs' and ins.op_str=='x1, ccsidr_el1':
            assert cache_state['selector'] in [0,2]
            sets,ways=(64,4) if cache_state['selector']==0 else (256,8)
            uc.reg_write(ar.UC_ARM64_REG_X1,((sets-1)<<13)|((ways-1)<<3)|2);skip=True
        elif ins.mnemonic=='dc' and ins.op_str=='cisw, x9':
            cache_state['ops'].append(uc.reg_read(ar.UC_ARM64_REG_X9));skip=True
        if skip:uc.reg_write(UC_ARM64_REG_PC,address+4)
    arm64.hook_add(UC_HOOK_CODE,cache_registers,begin=control+1600,end=control+2047)
    smcs64=[i.address for i in Cs(CS_ARCH_ARM64,0).disasm(payload[:1024],control+512) if i.mnemonic=='smc']
    assert len(smcs64)==2
    def affinity_info(uc,address,size,user):
        assert uc.reg_read(UC_ARM64_REG_X0)==0x84000004
        assert uc.reg_read(UC_ARM64_REG_X1)==1 and uc.reg_read(UC_ARM64_REG_X2)==0
        uc.reg_write(UC_ARM64_REG_X0,1) # PSCI_AFFINITY_LEVEL_OFF
        uc.reg_write(UC_ARM64_REG_PC,address+4)
    arm64.hook_add(UC_HOOK_CODE,affinity_info,begin=smcs64[0],end=smcs64[0])
    reached=[]
    def at_primary(uc,address,size,user):
        reached.append(address);uc.emu_stop()
    arm64.hook_add(UC_HOOK_CODE,at_primary,begin=(image_dest+(ENTRY+8)),end=(image_dest+(ENTRY+8)))
    arm64.emu_start(image_dest,(image_dest+(ENTRY+12)),count=1000000000)
    assert reached==[(image_dest+(ENTRY+8))]
    expected_cache_ops={way<<30|s<<6 for way in range(4) for s in range(64)} | {way<<29|s<<6|2 for way in range(8) for s in range(256)}
    assert len(cache_state['ops'])==2304 and set(cache_state['ops'])==expected_cache_ops
    assert cache_state['selectors']==[0,2,0]
    assert bytes(arm64.mem_read(image_dest,64))==original[:64]
    for d in range(descriptor_pages):
        trace=struct.unpack('<8I',bytes(arm64.mem_read(control+(d+1)*4096+4064,32)))
        assert trace[2]==8,trace
        assert trace[4]==image_crc,trace
        assert trace[3]==initrd_crc,trace
        assert trace[7]&255==1,trace
        extra=struct.unpack('<6I',bytes(arm64.mem_read(control+(d+1)*4096+4000,24)))
        assert extra[2:]==(0x4d464558,1,0,2304),extra
        assert struct.unpack('<Q',bytes(arm64.mem_read(control+(d+1)*4096+4024,8)))[0]==64
    assert len(watchdog_writes)>=30
    # Inject an EL1 exception through the actual aligned vector table.
    reset=[]
    from capstone import CS_ARCH_ARM64
    smc64=smcs64[-1]
    def at_reset64(uc,address,size,user):
        reset.append(uc.reg_read(UC_ARM64_REG_X0));uc.emu_stop()
    arm64.hook_add(UC_HOOK_CODE,at_reset64,begin=smc64,end=smc64)
    arm64.emu_start(control+2048+512,control+4096,count=100000)
    assert reset==[0x84000009]
    for d in range(descriptor_pages):
        assert struct.unpack('<8I',bytes(arm64.mem_read(control+(d+1)*4096+4064,32)))[2]==6
    # Corrupt one relocated kernel instruction byte and verify rejection BEFORE kernel calls.
    arm64.mem_write(image_dest,image[:64])
    bad_at=(image_dest+0x205d80)
    old=bytes(arm64.mem_read(bad_at,1))[0]
    arm64.mem_write(bad_at,bytes([old^1]))
    arm64.reg_write(UC_ARM64_REG_PSTATE,0x3c5)
    arm64.reg_write(UC_ARM64_REG_X0,0x44000000)
    reached.clear();reset.clear()
    arm64.emu_start(image_dest,control+4096,count=500000000)
    assert not reached and reset==[0x84000009]
    for d in range(descriptor_pages):
        trace=struct.unpack('<8I',bytes(arm64.mem_read(control+(d+1)*4096+4064,32)))
        assert trace[2]==10 and trace[3]!=trace[4] and trace[4]==image_crc,trace
    report={'passed':True,'records_copied':records,'descriptor_pages':descriptor_pages,'all_relocated_bytes_verified':True,'image_header_restored':True,'source_entry_first_two_calls_executed':True,'cache_setway_operations':len(cache_state['ops']),'bad_image_crc_rejected':True,'exception_reset_verified':True,'flash_written':False,'device_access':False,'kernel_sha256':hashlib.sha256(original).hexdigest(),'module_sha256':{m:hashlib.sha256((HERE/f'mf297d_ramboot_{m}.ko').read_bytes()).hexdigest() for m in ('prepare','execute')}}
    (HERE/'stub-emulation-result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
