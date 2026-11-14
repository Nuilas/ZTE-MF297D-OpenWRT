/* GPL-2.0-only. Experimental fixed-image MF297D RAM handoff module.
 * Stock ABI: Linux 4.4.60 ARM32, module_header verified from bootconfig.ko.
 * Default build PREPARES ONLY. No flash, boot environment or device-file writes.
 * A separately compiled execute build requires an exact root-only proc command.
 */
#include "ramboot_config.h"
#include "ramboot_a64_payload.h"
#include "ramfault_payload.h"
#include "mdio_probe_payload.h"
typedef unsigned int u32;
typedef unsigned long long u64;
typedef unsigned long usize;
typedef long ssize;
typedef long long loff;
extern int printk(const char *, ...);
extern void msleep(unsigned int);
extern int snprintf(char *,usize,const char *,...);
extern void *vmalloc(usize);
extern void vfree(const void *);
extern unsigned long vmalloc_to_pfn(const void *);
extern void *filp_open(const char *,int,unsigned short);
extern int filp_close(void *,void *);
extern int kernel_read(void *,loff,char *,unsigned long);
extern void *memcpy(void *,const void *,usize);
extern void *memset(void *,int,usize);
extern _Bool capable(int);
extern long strncpy_from_user(char *,const char *,long);
extern ssize simple_read_from_buffer(void *,usize,loff *,const void *,usize);
extern void *proc_create_data(const char *,unsigned short,void *,const void *,void *);
extern void remove_proc_entry(const char *,void *);
#if RAMBOOT_EXECUTE_ENABLED
extern void rtnl_lock(void);
extern void rtnl_unlock(void);
extern void *__dev_get_by_name(void *,const char *);
extern int dev_close(void *);
extern unsigned char init_net[];
extern void *ioremap(unsigned long,unsigned long);
extern void iounmap(void *);
static volatile u32 *watchdog_mmio,*nss_mmio,*gmac_mmio[2];
/* Synopsys DWMAC v3: DMA operation mode +0x1018, ST bit13/SR bit1.
 * Hold the old NSS core first so firmware cannot restart these DMA engines.
 * Bounded polling; no descriptor address, flash, GPIO or reset timeout writes. */
__attribute__((noinline)) static u32 mf_dma_quiesce(volatile u32 *nss,volatile u32 *g0,volatile u32 *g1) {
    volatile u32 *g[2]={g0,g1};u32 flags=0;
    nss[1]=1;__asm__ volatile("dsb sy":::"memory");
    if(nss[1]==1)flags|=1;
    for(u32 i=0;i<2;i++) {
        u32 old=g[i][0x1018/4];
        if(old&0x2002U)flags|=1U<<(8+i);
        g[i][0x1018/4]=old&~0x2002U;
        __asm__ volatile("dsb sy":::"memory");
        if(!(g[i][0x1018/4]&0x2002U))flags|=1U<<(1+i);
        for(u32 n=0;n<100000;n++)if(!(g[i][0x1014/4]&0x7e0000U)){flags|=1U<<(3+i);break;}
    }
    return flags;
}
static void pet_watchdog(void) {
    watchdog_mmio[1]=1;
    __asm__ volatile("dsb sy":::"memory");
}
#endif

struct module_header {
    u32 state;void *next,*prev;char name[60];
    unsigned char before_init[220-72];int (*init)(void);
    unsigned char before_exit[460-224];void (*exit)(void);
    unsigned char tail[512-464];
};
_Static_assert(sizeof(struct module_header)==512,"stock module ABI size");
_Static_assert(__builtin_offsetof(struct module_header,init)==220,"stock init ABI");
_Static_assert(__builtin_offsetof(struct module_header,exit)==460,"stock exit ABI");
extern struct module_header __this_module;

#define PAGE 4096U
#define IMAGE_DEST RAMBOOT_IMAGE_DEST
#define DTB_DEST 0x44000000U
#define INITRD_DEST 0x45000000U
#define DTB_RESERVED 0x10000U
#define DESC_PER_PAGE 338U
#define TRACE_AT 4064U
#define TRACE_MAGIC 0x4d465452U
#define PROC_NAME "mf297d_ramboot"

static void *pool,*selection,*proc_entry;
static void **selected;
static u32 control_phys,records,descriptor_pages,selected_needed;
#if RAMBOOT_EXECUTE_ENABLED
static volatile u32 executing;
#endif
static int ready;
static char status_text[1024];
static usize status_length;
static u32 crc_table[256];

extern const unsigned char mf_stub_start[],mf_stub_end[];
/* Relocation stub executes from a checked page outside ALL destination pages.
 * Linux soft_restart() supplies MMU/cache shutdown. Source pages, descriptor
 * pages, control page and its physical stack all lie outside destination ranges.
 * No old Linux code, data, mappings or stack is used after the copy begins.
 */
__asm__(".pushsection .text.mf_stub,\"ax\",%progbits\n.arm\n.balign 4\n"
        ".global mf_stub_start\nmf_stub_start:\n"
        "sub r8,pc,#8\nadd sp,r8,#4096\nsub sp,sp,#16\n"
        /* Stock DT nphys=0x07a00000. Qualcomm IPQ50xx NSS_RESET_CTRL=+4:
         * hold UBI32/NSS in reset, preventing old firmware DMA into new RAM.
         * This runs ONLY after the exact commit and Linux CPU shutdown.
         * No GPIO, NAND, modem reset, or AP CPU reset register is touched. */
        "movw r12,#4\nmovt r12,#0x7a0\nmov r0,#1\nstr r0,[r12]\ndsb sy\nldr r0,[r12]\nstr r0,[r8,#448]\n"
        "mrc p15,0,r10,c1,c0,0\nmrc p15,0,r11,c2,c0,0\n"
        "str r10,[r8,#492]\nstr r11,[r8,#496]\n"
        "mov r9,#1\nadr lr,6f\nb 5f\n6:\n"
        "ldr r4,[r8,#304]\n"
        "1: ldr r5,[r4]\nldr r6,[r4,#4]\nadd r7,r4,#8\n"
        "2: ldmia r7!,{r0-r2}\n"
        "3: ldr r3,[r0],#4\nstr r3,[r1],#4\nsubs r2,r2,#4\nbne 3b\n"
        "subs r6,r6,#1\nbne 2b\nmov r4,r5\ncmp r4,#0\nbne 1b\n"
        "mov r9,#2\nadr lr,7f\nb 5f\n7:\n"
        "mov r0,#0\nmcr p15,0,r0,c7,c5,0\nmcr p15,0,r0,c7,c5,6\n"
        "dsb sy\nisb sy\n"
        "mov r9,#3\nadr lr,10f\nb 5f\n10:\n"
        "ldr r2,[r8,#308]\nmovw r0,#0x10f\nmovt r0,#0x200\n"
        "mov r1,#0x12\nmov r3,#80\nmov r4,#0\nmov r5,#0\n"
        ".arch_extension sec\nsmc #0\n"
        "mov r10,r0\nmov r11,r1\nsub r8,sp,#4080\nmov r9,#4\nadr lr,8f\nb 5f\n8:\n"
        /* If EL1SWITCH returns, attempt standard PSCI SYSTEM_RESET, then wait.
         * A power cycle still boots untouched stock firmware. */
        "movw r0,#9\nmovt r0,#0x8400\nsmc #0\n"
        "4: wfi\nb 4b\n"
        "5: ldr r4,[r8,#304]\n"
        "9: add r6,r4,#0xfe0\nstr r9,[r6,#8]\nstr r10,[r6,#12]\nstr r11,[r6,#16]\n"
        "ldr r12,[r8,#448]\nstr r12,[r6,#28]\n"
        "ldr r4,[r4]\ncmp r4,#0\nbne 9b\ndsb sy\nbx lr\n"
        ".global mf_stub_end\nmf_stub_end:\n.popsection\n");

static u32 crc_update(u32 crc,const unsigned char *p,usize n) {
    for(usize i=0;i<n;i++)crc=crc_table[(crc^p[i])&255]^(crc>>8);
    return crc;
}
static u32 be32(const unsigned char *p) {return (u32)p[0]<<24|(u32)p[1]<<16|(u32)p[2]<<8|p[3];}
static int valid_source(u32 p) {
    if(p&(PAGE-1))return 0;
    if(!((p>=0x41000000U && p<0x4ab00000U)||(p>=0x4e900000U && p<0x60000000U)))return 0;
    if(p>=IMAGE_DEST && p<IMAGE_DEST+RAMBOOT_IMAGE_MEMORY_BYTES)return 0;
    if(p>=DTB_DEST && p<DTB_DEST+DTB_RESERVED)return 0;
    if(p>=INITRD_DEST && p<INITRD_DEST+((RAMBOOT_INITRD_BYTES+PAGE-1)&~(PAGE-1)))return 0;
    return 1;
}
static u32 physical(const void *p) {return (u32)(vmalloc_to_pfn(p)<<12);}
static void release_all(void) {
#if RAMBOOT_EXECUTE_ENABLED
    for(u32 i=0;i<2;i++)if(gmac_mmio[i]){iounmap((void*)gmac_mmio[i]);gmac_mmio[i]=0;}
    if(nss_mmio){iounmap((void*)nss_mmio);nss_mmio=0;}
    if(watchdog_mmio){iounmap((void*)watchdog_mmio);watchdog_mmio=0;}
#endif
    if(proc_entry){remove_proc_entry(PROC_NAME,0);proc_entry=0;}
    if(selection){vfree(selection);selection=0;selected=0;}
    if(pool){vfree(pool);pool=0;}
    ready=0;
}

static int load_file(const char *path,u32 file_bytes,u32 memory_bytes,
                     u32 selected_offset,u32 destination,u32 *checksum) {
    void *file=filp_open(path,0,0);
    if((u32)file>=0xfffff001U)return (int)(long)file;
    u32 pages=(memory_bytes+PAGE-1)/PAGE,crc=0xffffffffU;
    int error=0;
    for(u32 i=0;i<pages;i++) {
        unsigned char *data=selected[selected_offset+i];
        u32 pos=i*PAGE,want=pos<file_bytes?file_bytes-pos:0;
        if(want>PAGE)want=PAGE;
        memset(data,0,PAGE);
        if(want){int got=kernel_read(file,(loff)pos,(char*)data,want);if(got!=(int)want){error=got<0?got:-5;break;}crc=crc_update(crc,data,want);}
        u32 ordinal=(selected_offset-1-descriptor_pages)+i;
        u32 desc_index=ordinal/DESC_PER_PAGE,slot=ordinal%DESC_PER_PAGE;
        u32 *desc=(u32*)((unsigned char*)selected[1+desc_index]+8+slot*12);
        desc[0]=physical(data);desc[1]=destination+pos;desc[2]=PAGE;
        if(!valid_source(desc[0])){error=-22;break;}
    }
    if(!error){char byte;int extra=kernel_read(file,(loff)file_bytes,&byte,1);if(extra!=0)error=extra<0?extra:-22;}
    filp_close(file,0);*checksum=crc^0xffffffffU;return error;
}

static ssize status_read(void *file,char *user,usize count,loff *position) {
    (void)file;
    return simple_read_from_buffer(user,count,position,status_text,status_length);
}
static ssize control_write(void *file,const char *user,usize count,loff *position) {
    (void)file;(void)user;(void)count;(void)position;
#if RAMBOOT_EXECUTE_ENABLED
    static const char command[]="MF297D_EXECUTE_RAM_ONLY\n";
    char supplied[sizeof(command)];
    if(!capable(22)){printk("<3>MF297D_RAMBOOT reject: CAP_SYS_BOOT missing\n");return -1;}
    if(!ready || count!=sizeof(command)-1){printk("<3>MF297D_RAMBOOT reject: ready=%d count=%u expected=%u\n",ready,(unsigned)count,(unsigned)sizeof(command)-1);return -22;}
    long copied=strncpy_from_user(supplied,user,(long)count);
    if(copied!=(long)count){printk("<3>MF297D_RAMBOOT reject: copied=%ld expected=%u\n",copied,(unsigned)count);return -14;}
    for(usize i=0;i<count;i++)if(supplied[i]!=command[i]){printk("<3>MF297D_RAMBOOT reject: byte %u got=%u expected=%u\n",(unsigned)i,(unsigned char)supplied[i],(unsigned char)command[i]);return -22;}
    if(__atomic_exchange_n(&executing,1,__ATOMIC_SEQ_CST))return -16;
    printk("<0>MF297D_RAMBOOT: explicit RAM-only handoff requested; flash untouched\n");
    msleep(250);
    /* Leave kernel workers alive to drain IO; freeze userspace writers first.
     * The current committing task is excluded by the kernel freezer. */
    pet_watchdog();
    int frozen=((int(*)(void))RAMBOOT_ADDR_FREEZE_PROCESSES)();
    if(frozen) {
        ((void(*)(void))RAMBOOT_ADDR_THAW_PROCESSES)();
        __atomic_store_n(&executing,0,__ATOMIC_SEQ_CST);
        printk("<3>MF297D_RAMBOOT: userspace freeze failed; thawed, no handoff\n");
        return frozen;
    }
    pet_watchdog();
    ((long(*)(void))RAMBOOT_ADDR_SYS_SYNC)();
    pet_watchdog();
    /* Vendor drivers often lack device.shutdown despite active DMA. Invoke
     * their normal ndo_stop paths under RTNL before generic device shutdown.
     * Only runs after the exact execute command; prepare never alters links. */
    static const char *const links[]={"br-Guest","br-lan","bond0","ath0","ath1",
        "eth1.1","eth1.2","eth1.3","eth1.4","eth0","eth1",
        "wifi0","wifi1","soc0","soc1","usb0","rndis0"};
    printk("<0>MF297D_RAMBOOT: closing vendor network interfaces before DMA handoff\n");
    rtnl_lock();
    for(u32 i=0;i<sizeof(links)/sizeof(links[0]);i++) {
        void *netdev=__dev_get_by_name(init_net,links[i]);
        if(netdev)dev_close(netdev);
    }
    rtnl_unlock();
    pet_watchdog();
    msleep(1000);
    printk("<0>MF297D_RAMBOOT: vendor network stop paths completed\n");
    /* Match Linux 4.4 kernel_kexec() ordering. These exact device addresses
     * are checked against live /proc/kallsyms by the host launcher. */
    ((void(*)(char*))RAMBOOT_ADDR_KERNEL_RESTART_PREPARE)(0);
    printk("<0>MF297D_RAMBOOT: restart preparation returned\n");msleep(250);
    ((void(*)(void))RAMBOOT_ADDR_MIGRATE_TO_REBOOT_CPU)();
    printk("<0>MF297D_RAMBOOT: migrated to reboot CPU\n");msleep(250);
    ((void(*)(void))RAMBOOT_ADDR_CPU_HOTPLUG_ENABLE)();
    ((void(*)(void))RAMBOOT_ADDR_MACHINE_SHUTDOWN)();
    pet_watchdog();
    printk("<0>MF297D_RAMBOOT: secondary CPUs stopped; entering physical stub\n");msleep(250);
    u32 dma_flags=mf_dma_quiesce(nss_mmio,gmac_mmio[0],gmac_mmio[1]);
    *(u32*)((unsigned char*)selected[0]+476)=dma_flags;
    ((void(*)(unsigned long,unsigned long))RAMBOOT_ADDR_COHERENT_KERN_RANGE)((unsigned long)selected[0],(unsigned long)selected[0]+4096);
    ((void(*)(unsigned long))RAMBOOT_ADDR_SOFT_RESTART)(control_phys);
    for(;;)__asm__ volatile("wfi");
#else
    return -1; /* Preparing this module cannot cause a kernel jump. */
#endif
}
struct file_ops_prefix {
    void *owner,*llseek;
    ssize (*read)(void*,char*,usize,loff*);
    ssize (*write)(void*,const char*,usize,loff*);
    void *unused[28];
};
static const struct file_ops_prefix operations={.owner=&__this_module,.read=status_read,.write=control_write};

int init_module(void) {
    int error=-22;u32 image_pages=(RAMBOOT_IMAGE_MEMORY_BYTES+PAGE-1)/PAGE;
    if(RAMBOOT_IMAGE_FILE_BYTES>RAMBOOT_IMAGE_MEMORY_BYTES || RAMBOOT_DTB_FILE_BYTES>DTB_RESERVED)return -22;
#if RAMBOOT_EXECUTE_ENABLED
    /* Maps/read-only hardware identity checks; all writes remain commit-only. */
    watchdog_mmio=ioremap(0x0b017000U,PAGE);
    if(!watchdog_mmio)return -12;
    nss_mmio=ioremap(0x07a00000U,PAGE);
    gmac_mmio[0]=ioremap(0x39c00000U,2*PAGE);
    gmac_mmio[1]=ioremap(0x39d00000U,2*PAGE);
    if(!nss_mmio || !gmac_mmio[0] || !gmac_mmio[1]){release_all();return -12;}
    if(gmac_mmio[0][0x20/4]!=0x1137U || gmac_mmio[1][0x20/4]!=0x1137U){release_all();return -22;}
#endif
    u32 dtb_pages=(RAMBOOT_DTB_FILE_BYTES+PAGE-1)/PAGE;
    u32 initrd_pages=(RAMBOOT_INITRD_BYTES+PAGE-1)/PAGE;
    records=image_pages+dtb_pages+initrd_pages;descriptor_pages=(records+DESC_PER_PAGE-1)/DESC_PER_PAGE;
    selected_needed=1+descriptor_pages+records;
    /* At most this many allocated physical pages can overlap destinations.
     * Holding them unused guarantees enough safe staging pages without relying
     * on allocator ordering. No target memory is touched during preparation. */
    u32 forbidden_pages=image_pages+DTB_RESERVED/PAGE+initrd_pages;
    u32 pool_pages=selected_needed+forbidden_pages+16;
    pool=vmalloc((usize)pool_pages*PAGE);
    selection=vmalloc((usize)pool_pages*sizeof(void*));selected=selection;
    if(!pool || !selection){error=-12;goto failed;}
    u32 found=0;
    for(u32 i=0;i<pool_pages;i++) {
        void *p=(unsigned char*)pool+i*PAGE;
        if(valid_source(physical(p)))selected[found++]=p;
    }
    if(found<selected_needed){error=-12;goto failed;}
    /* Spread trace/control pages across the entire owned allocation, rather
     * than clustering them where stock boot allocations may reuse all at once.
     * Swapping is a permutation, so sources remain unique and owned. */
    for(u32 i=0;i<=descriptor_pages;i++) {
        u32 at=i*(found-1)/descriptor_pages;
        void *temp=selected[i];selected[i]=selected[at];selected[at]=temp;
    }
    for(u32 i=0;i<256;i++){u32 c=i;for(int k=0;k<8;k++)c=(c>>1)^((c&1)?0xedb88320U:0);crc_table[i]=c;}
    for(u32 i=0;i<descriptor_pages;i++) {
        u32 *desc=selected[1+i];memset(desc,0,PAGE);
        desc[0]=i+1<descriptor_pages?physical(selected[2+i]):0;
        u32 remaining=records-i*DESC_PER_PAGE;desc[1]=remaining>DESC_PER_PAGE?DESC_PER_PAGE:remaining;
    }
    u32 kernel_crc=0,dtb_crc=0;
    error=load_file("/tmp/mf297d-Image",RAMBOOT_IMAGE_FILE_BYTES,RAMBOOT_IMAGE_MEMORY_BYTES,1+descriptor_pages,IMAGE_DEST,&kernel_crc);
    if(error)goto failed;
    unsigned char *image=selected[1+descriptor_pages];
    if(image[56]!='A'||image[57]!='R'||image[58]!='M'||image[59]!='d'){error=-22;goto failed;}
    if(*(u64*)(image+8)!=0 || *(u64*)(image+16)!=RAMBOOT_IMAGE_MEMORY_BYTES){error=-22;goto failed;}
    /* Header flag bit 3 permits any suitable 2MiB-aligned RAM placement. */
    if(!(*(u64*)(image+24)&8U) || (IMAGE_DEST&0x1fffffU) ||
        IMAGE_DEST<0x48000000U || IMAGE_DEST+RAMBOOT_IMAGE_MEMORY_BYTES>0x4a400000U){error=-22;goto failed;}
    error=load_file("/tmp/mf297d-ram.dtb",RAMBOOT_DTB_FILE_BYTES,RAMBOOT_DTB_FILE_BYTES,1+descriptor_pages+image_pages,DTB_DEST,&dtb_crc);
    if(error)goto failed;
    unsigned char *dtb=selected[1+descriptor_pages+image_pages];
    if(be32(dtb)!=0xd00dfeedU || be32(dtb+4)!=RAMBOOT_DTB_FILE_BYTES){error=-22;goto failed;}
    if(kernel_crc!=RAMBOOT_IMAGE_CRC32 || dtb_crc!=RAMBOOT_DTB_CRC32){error=-74;goto failed;}
    u32 initrd_crc=0;
    error=load_file("/tmp/mf297d-initramfs.cpio",RAMBOOT_INITRD_BYTES,RAMBOOT_INITRD_BYTES,
        1+descriptor_pages+image_pages+dtb_pages,INITRD_DEST,&initrd_crc);
    if(error)goto failed;
    if(initrd_crc!=RAMBOOT_INITRD_CRC32){error=-74;goto failed;}
    /* Preserve only our own allocated pages in the new kernel. The fatal
     * diagnostic writes these pages through the normal linear RAM mapping. */
    if(RAMBOOT_TRACE_REG_COUNT!=descriptor_pages+1 || RAMBOOT_TRACE_REG_OFFSET+16*RAMBOOT_TRACE_REG_COUNT>RAMBOOT_DTB_FILE_BYTES){error=-22;goto failed;}
    for(u32 i=0;i<RAMBOOT_TRACE_REG_COUNT;i++) {
        u32 values[4]={0,physical(selected[i]),0,PAGE};
        for(u32 word=0;word<4;word++) {
            u32 at=RAMBOOT_TRACE_REG_OFFSET+i*16+word*4,v=values[word];
            unsigned char *p=(unsigned char*)selected[1+descriptor_pages+image_pages+at/PAGE]+at%PAGE;
            p[0]=(unsigned char)(v>>24);p[1]=(unsigned char)(v>>16);p[2]=(unsigned char)(v>>8);p[3]=(unsigned char)v;
        }
    }
    /* This image's die() is 0x180 bytes. Replace only that already-fatal
     * path in owned staging RAM, so its exact PC/opcode survive reboot. */
    const u32 die_offset=0x298e0U;
    unsigned char *die=(unsigned char*)selected[1+descriptor_pages+die_offset/PAGE]+die_offset%PAGE;
    if(sizeof(fault_payload)>0x180 || die_offset%PAGE+sizeof(fault_payload)>PAGE || *(u32*)die!=0xd503233fU){error=-22;goto failed;}
    memcpy(die,fault_payload,sizeof(fault_payload));
    *(u32*)(die+RAMFAULT_HEAD_OFFSET)=physical(selected[1]);
    /* MDIO board diagnostic in unused tail of the replaced fatal function.
     * Rejoin the exact original mode-write sequence with a direct branch.
     * The forced mode is stock 0x1500f with slower supported /64 divider. */
    const u32 mdio_hook=0x5e19f0U,mdio_code=0x29980U;
    unsigned char *mdio=(unsigned char*)selected[1+descriptor_pages+mdio_code/PAGE]+mdio_code%PAGE;
    u32 *hook=(u32*)((unsigned char*)selected[1+descriptor_pages+mdio_hook/PAGE]+mdio_hook%PAGE);
    if(sizeof(fault_payload)>160 || sizeof(mdio_payload)>224 || *hook!=0x12177863U){error=-22;goto failed;}
    memcpy(mdio,mdio_payload,sizeof(mdio_payload));
    *(u32*)(mdio+MDIO_HEAD_LITERAL_OFFSET)=physical(selected[1]);
    *(u32*)(mdio+MDIO_FORCE_LITERAL_OFFSET)=RAMBOOT_MDIO_FORCE_MODE;
    *(u32*)(mdio+MDIO_RETURN_BRANCH_OFFSET)=0x14000000U|(((mdio_hook+4-mdio_code-MDIO_RETURN_BRANCH_OFFSET)>>2)&0x3ffffffU);
    *hook=0x14000000U|(((mdio_code-mdio_hook)>>2)&0x3ffffffU);
    /* Same kernel and exact CPIO content as supplied FIT. Avoid only the
     * embedded ZSTD decoder path; Linux reads chosen linux,initrd-start/end. */
    const u32 size_offset=0x14f09a0U;
    u64 *embedded_size=(u64*)((unsigned char*)selected[1+descriptor_pages+size_offset/PAGE]+size_offset%PAGE);
    if(*embedded_size!=RAMBOOT_ZSTD_BYTES){error=-22;goto failed;}
    *embedded_size=0;
    usize stub_bytes=(usize)(mf_stub_end-mf_stub_start);
    if(stub_bytes>304){error=-22;goto failed;}
    unsigned char *control=selected[0];memset(control,0,PAGE);memcpy(control,mf_stub_start,stub_bytes);
    control_phys=physical(control);
    /* CRC checked ORIGINAL image above. Patch only owned staging RAM with a
     * temporary header trampoline; ARM64 shim restores both original words. */
    u32 branch=*(u32*)(image+4);
    if((branch&0xfc000000U)!=0x14000000U){error=-22;goto failed;}
    int displacement=((int)(branch<<6))>>4;
    u32 entry=IMAGE_DEST+4+displacement;
    if(entry<IMAGE_DEST+64 || entry>=IMAGE_DEST+RAMBOOT_IMAGE_FILE_BYTES){error=-22;goto failed;}
    *(u64*)(control+400)=*(u64*)image;
    *(u64*)(control+408)=*(u64*)(image+32);
    *(u64*)(control+416)=entry;
    u32 *head=(u32*)((unsigned char*)selected[1+descriptor_pages+(entry-IMAGE_DEST)/PAGE]+(entry-IMAGE_DEST)%PAGE);
    for(u32 j=0;j<2;j++) {
        u32 call=head[j];
        if((call&0xfc000000U)!=0x94000000U){error=-22;goto failed;}
        int relative=((int)(call<<6))>>4;
        u32 target=entry+j*4+relative;
        if(target<IMAGE_DEST+64 || target>=IMAGE_DEST+RAMBOOT_IMAGE_FILE_BYTES){error=-22;goto failed;}
        *(u64*)(control+424+j*8)=target;
    }
    memcpy(control+512,a64_payload,sizeof(a64_payload));
    for(u32 j=0;j<16;j++) {
        u32 v=j;
        for(u32 bit=0;bit<4;bit++)v=(v>>1)^((v&1)?0xedb88320U:0);
        *(u32*)(control+1536+j*4)=v;
    }
    *(u32*)(control+460)=RAMBOOT_IMAGE_FILE_BYTES;
    *(u32*)(control+464)=RAMBOOT_INITRD_BYTES;
    *(u32*)(control+468)=RAMBOOT_INITRD_CRC32;
    *(u32*)image=0x58000110U;*(u32*)(image+4)=0xd61f0200U;
    *(u64*)(image+32)=control_phys+512;
    u32 relocated_crc=0xffffffffU;
    for(u32 pos=0;pos<RAMBOOT_IMAGE_FILE_BYTES;pos+=PAGE) {
        u32 remaining=RAMBOOT_IMAGE_FILE_BYTES-pos;
        relocated_crc=crc_update(relocated_crc,selected[1+descriptor_pages+pos/PAGE],remaining<PAGE?remaining:PAGE);
    }
    relocated_crc^=0xffffffffU;
    *(u32*)(control+456)=relocated_crc;
    *(u32*)(control+304)=physical(selected[1]);*(u32*)(control+308)=control_phys+320;
    u64 *parameters=(u64*)(control+320);parameters[0]=DTB_DEST;parameters[9]=IMAGE_DEST;
    if(!valid_source(control_phys)){error=-22;goto failed;}
    for(u32 i=0;i<descriptor_pages;i++) {
        u32 *trace=(u32*)((unsigned char*)selected[1+i]+TRACE_AT);
        trace[0]=TRACE_MAGIC;trace[1]=RAMBOOT_TRACE_NONCE;trace[2]=0;
        trace[3]=trace[4]=0;trace[5]=control_phys;trace[6]=kernel_crc;trace[7]=0;
        ((void(*)(unsigned long,unsigned long))RAMBOOT_ADDR_COHERENT_KERN_RANGE)((unsigned long)selected[1+i],(unsigned long)selected[1+i]+PAGE);
    }
    /* Match ARM fncpy(): make the freshly written stub instruction-coherent.
     * The later soft_restart() performs the full CPU cache/MMU shutdown. */
    ((void(*)(unsigned long,unsigned long))RAMBOOT_ADDR_COHERENT_KERN_RANGE)((unsigned long)control,(unsigned long)control+PAGE);
    ready=1;
    status_length=(usize)snprintf(status_text,sizeof(status_text),
        "{\"prepared\":true,\"execute_enabled\":%u,\"records\":%u,\"descriptor_pages\":%u,\"control_phys\":%u,\"kernel_dest\":%u,\"dtb_dest\":%u,\"kernel_crc32\":\"%08x\",\"dtb_crc32\":\"%08x\",\"dma_quiesce_probe\":true,\"mdio_mode_probe\":true,\"a64_coherency_probe\":true,\"a64_cache_clean\":true,\"relocated_image_crc32\":\"%08x\",\"external_initrd\":true,\"initrd_crc32\":\"%08x\",\"source_destination_overlap\":false,\"flash_written\":false,\"trace_nonce\":%u,\"trace_pages\":[",
        RAMBOOT_EXECUTE_ENABLED,records,descriptor_pages,control_phys,IMAGE_DEST,DTB_DEST,kernel_crc,dtb_crc,relocated_crc,initrd_crc,RAMBOOT_TRACE_NONCE);
    for(u32 i=0;i<descriptor_pages && status_length<sizeof(status_text);i++)
        status_length+=(usize)snprintf(status_text+status_length,sizeof(status_text)-status_length,"%s%u",i?",":"",physical(selected[1+i]));
    if(status_length<sizeof(status_text))status_length+=(usize)snprintf(status_text+status_length,sizeof(status_text)-status_length,"]}\n");
    if(status_length>=sizeof(status_text)){error=-22;goto failed;}
    proc_entry=proc_create_data(PROC_NAME,0600,0,&operations,0);
    if(!proc_entry){error=-12;goto failed;}
    printk("<6>MF297D_RAMBOOT prepared: execute=%u, safe pages=%u, stub=%u bytes, image_crc=%08x dtb_crc=%08x\n",RAMBOOT_EXECUTE_ENABLED,selected_needed,(unsigned)stub_bytes,kernel_crc,dtb_crc);
    return 0;
failed:
    printk("<3>MF297D_RAMBOOT prepare failed: %d; flash untouched\n",error);
    release_all();return error;
}
void cleanup_module(void) {
    release_all();printk("<6>MF297D_RAMBOOT staging freed; no handoff occurred\n");
}
__attribute__((section(".gnu.linkonce.this_module"),used,aligned(64)))
struct module_header __this_module={.name="mf297d_ramboot",.init=init_module,.exit=cleanup_module};
__attribute__((section(".modinfo"),used)) static const char license[]="license=GPL";
__attribute__((section(".modinfo"),used)) static const char depends[]="depends=";
__attribute__((section(".modinfo"),used)) static const char vermagic[]="vermagic=4.4.60 SMP preempt mod_unload ARMv7 p2v8 ";
__attribute__((section(".modinfo"),used)) static const char description[]="description=Experimental MF297D fixed-image RAM-only handoff; stock ABI only";
__asm__(".pushsection .core.plt,\"ax\",%nobits\n.skip 1\n.popsection\n.pushsection .init.plt,\"ax\",%nobits\n.skip 1\n.popsection\n");
